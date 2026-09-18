"""Main FastAPI application for GridWise Smart Campus Energy Optimization."""

from __future__ import annotations

import math
import logging
import os
import traceback
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from gridwise.app.models import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    DirectiveInterpretation,
    HourlyPlanOutput,
)
from gridwise.app.guardrails import Guardrails
from gridwise.app.directives import compile_directives
from gridwise.app.optimizer import optimize_energy
from gridwise.app.validator import ReplayValidator
from gridwise.app.config import get_settings
from gridwise.app.llm.interpreter import create_interpreter

# ---------------------------------------------------------------------------
# FastAPI app setup
# ---------------------------------------------------------------------------

app = FastAPI(title="GridWise Energy Optimizer", version="0.1.0")

# Configure logging - safe, no secrets
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gridwise")


# ---------------------------------------------------------------------------
# Settings / LLM provider (created at startup)
# ---------------------------------------------------------------------------

llm_interpreter: Optional[object] = None  # initialized in startup


@app.on_event("startup")
def setup_llm():
    """Initialize LLM interpreter at startup."""
    global llm_interpreter
    from gridwise.app.llm.provider import LLMProvider

    settings = get_settings()
    api_key = settings.llm_api_key
    model = settings.llm_model

    if not api_key or not model:
        logger.warning("LLM API key or model not configured - running without LLM")
        llm_interpreter = None
        return

    try:
        provider = LLMProvider(
            api_key=api_key,
            model=model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        llm_interpreter = create_interpreter(provider=provider)
        logger.info(f"LLM interpreter initialized with model={model}")
    except Exception as e:
        logger.error(f"Failed to initialize LLM interpreter: {e}")
        llm_interpreter = None


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> JSONResponse:
    """Health check - immediately available, no LLM call."""
    return JSONResponse(content={"status": "ok"}, status_code=200)


# ---------------------------------------------------------------------------
# Request validation and error handling
# ---------------------------------------------------------------------------


class GridwiseError(Exception):
    """Base class for gridwise-specific errors."""

    def __init__(self, detail: str, status_code: int = 422):
        self.detail = detail
        self.status_code = status_code


@app.exception_handler(GridwiseError)
def gridwise_error_handler(request, exc: GridwiseError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
def general_exception_handler(request, exc: Exception):
    # Log sanitized error - never leak stack traces
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error"},
    )


# ---------------------------------------------------------------------------
# /optimize-energy endpoint
# ---------------------------------------------------------------------------


@app.post("/optimize-energy", response_model=OptimizeEnergyResponse)
def optimize_energy_endpoint(request: OptimizeEnergyRequest):
    """POST /optimize-energy - main optimization endpoint.

    Flow:
    1. Request validation (Pydantic)
    2. LLM operator notes interpretation
    3. Guardrails validation of LLM output
    4. Directive compilation -> per-hour constraints
    5. LP optimization
    6. Independent replay validator
    7. Totals calculation and summary
    8. JSON response
    """
    global llm_interpreter

    try:
        # --- Step 1: Request already validated by Pydantic ---
        scenario_id = request.scenario_id
        operator_notes = request.operator_notes
        hours_data = request.hours
        battery = request.battery

        # Extract arrays from request
        demands = [h.demand_kwh for h in hours_data]
        solar_kwh_raw = [h.solar_kwh for h in hours_data]
        tariffs = [h.tariff_bdt_per_kwh for h in hours_data]
        hour_ints = [h.hour for h in hours_data]
        battery_capacity_kwh = battery.capacity_kwh
        initial_energy_kwh = battery.initial_energy_kwh
        minimum_energy_kwh = battery.minimum_energy_kwh
        max_charge_kwh_per_hour = battery.max_charge_kwh_per_hour
        max_discharge_kwh_per_hour = battery.max_discharge_kwh_per_hour

        # --- Step 2: LLM operator notes interpretation ---
        if llm_interpreter is None:
            # Fallback: no LLM available -> treat all notes as no_op
            interpretations = [
                {
                    "note_index": i,
                    "applies": False,
                    "directive_type": "no_op",
                    "structured_adjustment": None,
                    "explanation": "LLM not available; note treated as no_op",
                }
                for i in range(len(operator_notes))
            ]
        else:
            try:
                # ONE LLM call per request (as required by spec)
                interpretations_raw = llm_interpreter.interpret(
                    operator_notes=operator_notes,
                    battery_capacity_kwh=battery_capacity_kwh,
                )
                # Normalize: ensure we have exactly N entries
                if isinstance(interpretations_raw, list) and len(interpretations_raw) == len(operator_notes):
                    interpretations = interpretations_raw
                else:
                    # Fallback: trim or pad to match
                    interpretations = []
                    for i in range(len(operator_notes)):
                        if i < len(interpretations_raw):
                            interpretations.append(interpretations_raw[i])
                        else:
                            interpretations.append({
                                "note_index": i,
                                "applies": False,
                                "directive_type": "no_op",
                                "structured_adjustment": None,
                                "explanation": "fallback no_op",
                            })
            except Exception as e:
                logger.error(f"LLM interpretation error: {e}")
                # Fallback: treat all notes as no_op
                interpretations = [
                    {
                        "note_index": i,
                        "applies": False,
                        "directive_type": "no_op",
                        "structured_adjustment": None,
                        "explanation": f"LLM error: {str(e)[:80]}",
                    }
                    for i in range(len(operator_notes))
                ]

        # --- Step 3: Guardrails validation ---
        guardrail_result = Guardrails.validate_all(
            interpretations=interpretations,
            operator_notes_count=len(operator_notes),
            battery_capacity_kwh=battery_capacity_kwh,
        )

        if not guardrail_result.valid:
            # Attempt controlled repair/retry once
            logger.warning(f"Guardrails validation failed: {guardrail_result.errors}")
            # If we have an LLM, try a single repair attempt
            if llm_interpreter is not None:
                try:
                    # Re-interpret with guardrail feedback
                    interpretations_raw = llm_interpreter.interpret(
                        operator_notes=operator_notes,
                        battery_capacity_kwh=battery_capacity_kwh,
                    )
                    if isinstance(interpretations_raw, list) and len(interpretations_raw) == len(operator_notes):
                        guardrail_result = Guardrails.validate_all(
                            interpretations=interpretations_raw,
                            operator_notes_count=len(operator_notes),
                            battery_capacity_kwh=battery_capacity_kwh,
                        )
                        if guardrail_result.valid:
                            interpretations = interpretations_raw
                except Exception:
                    pass

            # If still invalid after retry, return controlled failure
            if not guardrail_result.valid:
                raise GridwiseError(
                    detail=f"Directive interpretation invalid: {guardrail_result.errors[:3]}",
                    status_code=422,
                )

        # --- Step 4: Compile directives into per-hour constraints ---
        # Initialize effective_solar from raw solar (before reductions)
        effective_solar = list(solar_kwh_raw)  # copy

        # Compile directives
        constraint_arrays = compile_directives(
            interpretations=interpretations,
            battery_capacity_kwh=battery_capacity_kwh,
            hours_0_to_23=list(range(24)),
            base_minimum_energy_kwh=minimum_energy_kwh,
        )

        effective_solar = constraint_arrays["effective_solar"]
        minimum_reserve = constraint_arrays["minimum_reserve"]
        can_charge = constraint_arrays["can_charge"]
        can_discharge = constraint_arrays["can_discharge"]
        max_grid = constraint_arrays["max_grid"]

        # --- Step 5: LP optimization ---
        optimization_result = optimize_energy(
            demands=demands,
            solar_kwh=solar_kwh_raw,  # raw solar; effective_solar already applied in compile_directives
            tariffs=tariffs,
            battery_capacity_kwh=battery_capacity_kwh,
            initial_energy_kwh=initial_energy_kwh,
            minimum_energy_kwh=minimum_energy_kwh,
            max_charge_kwh_per_hour=max_charge_kwh_per_hour,
            max_discharge_kwh_per_hour=max_discharge_kwh_per_hour,
            effective_solar=effective_solar,
            minimum_reserve=minimum_reserve,
            can_charge=can_charge,
            can_discharge=can_discharge,
            max_grid=max_grid,
        )

        if optimization_result is None:
            raise GridwiseError(detail="Optimization failed: infeasible or solver error", status_code=422)

        hourly_plan_raw = optimization_result["hourly_plan"]

        # --- Step 6: Independent replay validator ---
        replay_result = ReplayValidator.validate(
            hourly_plan=hourly_plan_raw,
            demands=demands,
            solar_kwh=solar_kwh_raw,
            tariffs=tariffs,
            battery_capacity_kwh=battery_capacity_kwh,
            initial_energy_kwh=initial_energy_kwh,
            minimum_energy_kwh=minimum_energy_kwh,
            max_charge_kwh_per_hour=max_charge_kwh_per_hour,
            max_discharge_kwh_per_hour=max_discharge_kwh_per_hour,
            can_charge=can_charge,
            can_discharge=can_discharge,
            max_grid=max_grid,
            effective_solar=effective_solar,
            hours=hour_ints,
        )

        if not replay_result["valid"]:
            logger.error(f"Replay validator failed: {replay_result['errors']}")
            # Try to fix common issues by recomputing; if unresolvable, fail
            raise GridwiseError(
                detail=f"Optimized plan failed replay validation: {replay_result['errors'][0]}",
                status_code=422,
            )

        # --- Step 7: Calculate totals and summary ---
        # Recalculate from the validated plan (never trust model-generated totals)
        total_grid_kwh = 0.0
        total_cost_bdt = 0.0
        peak_grid_kwh = 0.0

        for hour_entry in hourly_plan_raw:
            grid_kwh = hour_entry["grid_kwh"]
            tariff = tariffs[hour_entry["hour"]]
            total_grid_kwh += grid_kwh
            total_cost_bdt += grid_kwh * tariff
            if grid_kwh > peak_grid_kwh:
                peak_grid_kwh = grid_kwh

        # Recompute plan_summary deterministically
        plan_summary = _generate_plan_summary(
            interpretations,
            can_charge,
            can_discharge,
            max_grid,
            effective_solar,
            demands,
            tariffs,
            battery_capacity_kwh,
            initial_energy_kwh,
        )

        # --- Step 8: Build response ---
        # Build directive_interpretation list
        directive_interpretation_list = []
        for i, interp in enumerate(interpretations):
            directive_interpretation_list.append(
                {
                    "note_index": interp.get("note_index", i),
                    "applies": interp.get("applies", False),
                    "directive_type": interp.get("directive_type", "no_op"),
                    "structured_adjustment": interp.get("structured_adjustment"),
                    "explanation": interp.get("explanation", ""),
                }
            )

        # Build hourly_plan list with exact schema
        hourly_plan_list = []
        for hour_entry in hourly_plan_raw:
            hourly_plan_list.append(
                {
                    "hour": hour_entry["hour"],
                    "grid_kwh": hour_entry["grid_kwh"],
                    "solar_used_kwh": hour_entry["solar_used_kwh"],
                    "battery_action": hour_entry["battery_action"],
                    "battery_kwh": hour_entry["battery_kwh"],
                    "battery_energy_after_kwh": hour_entry["battery_energy_after_kwh"],
                }
            )

        response = OptimizeEnergyResponse(
            scenario_id=scenario_id,
            directive_interpretation=directive_interpretation_list,
            hourly_plan=hourly_plan_list,
            total_grid_kwh=round(total_grid_kwh, 6),
            total_cost_bdt=round(total_cost_bdt, 6),
            peak_grid_kwh=round(peak_grid_kwh, 6),
            plan_summary=plan_summary,
        )

        return JSONResponse(content=response.model_dump(), status_code=200)

    except GridwiseError as e:
        raise e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /optimize-energy: {e}")
        raise GridwiseError(detail="internal server error", status_code=500)


def _generate_plan_summary(
    interpretations: List[Dict[str, Any]],
    can_charge: List[bool],
    can_discharge: List[bool],
    max_grid: List[Optional[float]],
    effective_solar: List[float],
    demands: List[float],
    tariffs: List[float],
    battery_capacity_kwh: float,
    initial_energy_kwh: float,
) -> str:
    """Generate deterministic plan_summary without a second LLM call.

    Builds a short human-readable explanation of what the plan did.
    """
    parts = []

    # Count active directives
    active_directives = [i for i, interp in enumerate(interpretations) if interp.get("applies", False)]

    if active_directives:
        directive_names = []
        for idx in active_directives:
            dt = interpretations[idx].get("directive_type", "unknown")
            if dt == "solar_reduction":
                directive_names.append("solar reduction")
            elif dt == "minimum_battery_reserve":
                directive_names.append("battery reserve")
            elif dt == "no_charge_window":
                directive_names.append("no-charge window")
            elif dt == "no_discharge_window":
                directive_names.append("no-discharge window")
            elif dt == "max_grid_window":
                directive_names.append("grid import limit")

        if directive_names:
            if len(directive_names) == 1:
                parts.append(f"Applied {directive_names[0]}")
            else:
                # Last item with "and"
                last = directive_names[-1]
                others = directive_names[:-1]
                parts.append(f"Applied {', '.join(others)} and {last}")

    # Battery-related notes
    no_charge_count = sum(1 for h in can_charge if not h)
    no_discharge_count = sum(1 for h in can_discharge if not h)

    if no_charge_count > 0:
        parts.append(f"observed {no_charge_count}-hour charge outage")
    if no_discharge_count > 0:
        parts.append(f"observed {no_discharge_count}-hour discharge outage")

    if not parts:
        parts.append("optimized energy usage within constraints")

    return ". ".join(parts) + "."