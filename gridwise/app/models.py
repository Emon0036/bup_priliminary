from __future__ import annotations

from typing import Literal, Optional, List, Dict, Any
from pydantic import field_validator, model_validator
from pydantic import BaseModel, Extra, RootModel, Field


# ---------------------------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------------------------


class HourlyInput(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    demand_kwh: float = Field(..., ge=0)
    solar_kwh: float = Field(..., ge=0)
    tariff_bdt_per_kwh: float = Field(..., gt=0)

    model_config = {"extra": "forbid"}

    @field_validator("hour")
    def hour_must_be_int(cls, v):
        if not isinstance(v, int):
            raise ValueError("hour must be an integer")
        return v

    @field_validator("demand_kwh", "solar_kwh", "tariff_bdt_per_kwh")
    def no_nan_inf(cls, v):
        import math
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise ValueError("must be finite")
        return v


class BatteryInput(BaseModel):
    capacity_kwh: float = Field(..., gt=0)
    initial_energy_kwh: float
    minimum_energy_kwh: float = Field(..., ge=0)
    max_charge_kwh_per_hour: float = Field(..., ge=0)
    max_discharge_kwh_per_hour: float = Field(..., ge=0)

    model_config = {"extra": "forbid"}

    @field_validator("initial_energy_kwh", "minimum_energy_kwh")
    def non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("must be non-negative")
        return v

    @field_validator("initial_energy_kwh")
    def initial_within_bounds(cls, v, info):
        if v is not None:
            capacity = info.data.get("capacity_kwh", v)
            if v > capacity:
                raise ValueError("initial_energy_kwh must not exceed capacity")
        return v

    @field_validator("minimum_energy_kwh")
    def minimum_not_exceed_capacity(cls, v, info):
        if v is not None:
            capacity = info.data.get("capacity_kwh", v)
            if v > capacity:
                raise ValueError("minimum_energy_kwh must not exceed capacity")
        return v

    @field_validator("max_charge_kwh_per_hour", "max_discharge_kwh_per_hour")
    def non_negative_rates(cls, v):
        if v < 0:
            raise ValueError("rate must be non-negative")
        return v


class OptimizeEnergyRequest(BaseModel):
    scenario_id: str
    operator_notes: List[str] = Field(..., min_length=1, max_length=3)
    hours: List[HourlyInput]
    battery: BatteryInput

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_24_hours(self):
        if len(self.hours) != 24:
            raise ValueError("must have exactly 24 hour entries")
        hour_vals = [h.hour for h in self.hours]
        if sorted(hour_vals) != list(range(24)):
            raise ValueError("hours must contain each integer 0..23 exactly once")
        return self


# ---------------------------------------------------------------------------
# RESPONSE MODELS
# ---------------------------------------------------------------------------


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: Literal[
        "solar_reduction",
        "minimum_battery_reserve",
        "no_charge_window",
        "no_discharge_window",
        "max_grid_window",
        "no_op",
    ]
    structured_adjustment: Optional[Dict[str, Any]] = None
    explanation: str

    model_config = {"extra": "forbid"}


class HourlyPlanOutput(BaseModel):
    hour: int
    grid_kwh: float = Field(..., ge=0)
    solar_used_kwh: float = Field(..., ge=0)
    battery_action: Literal["charge", "discharge", "idle"]
    battery_kwh: float = Field(..., ge=0)
    battery_energy_after_kwh: float

    model_config = {"extra": "forbid"}


class OptimizeEnergyResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlanOutput]
    total_grid_kwh: float = Field(..., ge=0)
    total_cost_bdt: float = Field(..., ge=0)
    peak_grid_kwh: float = Field(..., ge=0)
    plan_summary: str

    model_config = {"extra": "forbid"}