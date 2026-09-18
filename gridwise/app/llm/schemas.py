"""LLM output schemas for GridWise directive interpretation."""

from typing import Optional, Literal, List, Dict, Any

from pydantic import BaseModel, Field


# Helper for building the system prompt
DIRECTIVE_TYPES = [
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]

NO_OP_ADJUSTMENT = None
SOLAR_REDUCTION_KEYS = {"hours", "factor"}
MINIMUM_BATTERY_RESERVE_KEYS = {"hours", "minimum_energy_kwh"}
NO_CHARGE_WINDOW_KEYS = {"hours"}
NO_DISCHARGE_WINDOW_KEYS = {"hours"}
MAX_GRID_WINDOW_KEYS = {"hours", "max_grid_kwh"}


class ValidationResult(BaseModel):
    """Result of guardrail validation."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    repaired: Optional[Dict[str, Any]] = None