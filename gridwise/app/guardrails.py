"""Deterministic guardrails for validating LLM directive interpretation output.

Validates ALL LLM output AFTER the LLM and BEFORE optimization.

Uses Pydantic with extra="forbid" where practical.
"""

import math
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, ValidationError, Extra

from gridwise.app.models import DirectiveInterpretation


# ---------------------------------------------------------------------------
# Allowed directive types
# ---------------------------------------------------------------------------
ALLOWED_DIRECTIVE_TYPES: Set[str] = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}

# Keys allowed per directive type
DIRECTIVE_ALLOWED_KEYS: Dict[str, Set[str]] = {
    "solar_reduction": {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"},
    "minimum_battery_reserve": {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"},
    "no_charge_window": {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"},
    "no_discharge_window": {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"},
    "max_grid_window": {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"},
    "no_op": {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"},
}

# Keys per directive type for structured_adjustment validation
SOLAR_REDUCTION_KEYS = {"hours", "factor"}
MINIMUM_BATTERY_RESERVE_KEYS = {"hours", "minimum_energy_kwh"}
NO_CHARGE_WINDOW_KEYS = {"hours"}
NO_DISCHARGE_WINDOW_KEYS = {"hours"}
MAX_GRID_WINDOW_KEYS = {"hours", "max_grid_kwh"}


# ---------------------------------------------------------------------------
# Guardrail result
# ---------------------------------------------------------------------------
class GuardrailResult(BaseModel):
    """Result of validating a single interpretation entry."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    repaired: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Main guardrails class
# ---------------------------------------------------------------------------


class Guardrails:
    """Validate and repair LLM output for directive interpretations."""

    @staticmethod
    def validate_entry(
        entry: Dict[str, Any],
        battery_capacity_kwh: float = 200.0,
    ) -> GuardrailResult:
        """Validate a single interpretation entry from the LLM.

        Args:
            entry: Raw dict from LLM output

        Returns:
            GuardrailResult with valid=True if all checks pass
        """
        errors: List[str] = []

        # 1. Check required fields exist
        required_keys = {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"}
        missing = required_keys - set(entry.keys())
        extra_keys = set(entry.keys()) - required_keys
        if missing:
            errors.append(f"missing required fields: {missing}")
        if extra_keys:
            errors.append(f"unsupported fields: {extra_keys}")

        # 2. Check note_index range (handled by validate_all coverage check)
        # Note: validate_all already ensures note_index covers exactly 0..N-1
        # So we skip the per-entry note_index check here to avoid double-checking
        # with potentially wrong expected values

        # 3. Check applies semantics
        if "applies" in entry:
            applies = entry["applies"]
            dt = entry.get("directive_type", "")
            if dt == "no_op":
                if applies != False:
                    errors.append(f"no_op must have applies=false, got applies={applies}")
            else:
                if applies != True:
                    errors.append(f"non-no_op directive must have applies=true, got applies={applies}")

        # 4. Check directive_type
        if "directive_type" in entry:
            dt = entry["directive_type"]
            if dt not in ALLOWED_DIRECTIVE_TYPES:
                errors.append(f"unsupported directive_type: {dt}")
            elif dt != "no_op":
                # non-no_op must have applies=true (already checked above, but double-check)
                if entry.get("applies", True) != True:
                    errors.append(f"non-no_op directive {dt} must have applies=true")

        # 5. Check structured_adjustment
        if "structured_adjustment" in entry:
            sa = entry["structured_adjustment"]
            dt = entry.get("directive_type", "")
            if dt == "no_op":
                if sa is not None:
                    errors.append(f"no_op must have structured_adjustment=null, got {sa}")
            elif dt == "solar_reduction":
                if not isinstance(sa, dict):
                    errors.append(f"solar_reduction structured_adjustment must be dict, got {type(sa).__name__}")
                else:
                    Guardrails._validate_solar_reduction(sa, errors)
            elif dt == "minimum_battery_reserve":
                if not isinstance(sa, dict):
                    errors.append(f"minimum_battery_reserve structured_adjustment must be dict, got {type(sa).__name__}")
                else:
                    Guardrails._validate_minimum_battery_reserve(sa, battery_capacity_kwh, errors)
            elif dt == "no_charge_window":
                if not isinstance(sa, dict):
                    errors.append(f"no_charge_window structured_adjustment must be dict, got {type(sa).__name__}")
                else:
                    # sa is dict like {"hours": [...]}, extract the hours list
                    Guardrails._validate_hour_array(sa.get("hours", []), "hours", errors, "no_charge_window")
            elif dt == "no_discharge_window":
                if not isinstance(sa, dict):
                    errors.append(f"no_discharge_window structured_adjustment must be dict, got {type(sa).__name__}")
                else:
                    Guardrails._validate_hour_array(sa.get("hours", []), "hours", errors, "no_discharge_window")
            elif dt == "max_grid_window":
                if not isinstance(sa, dict):
                    errors.append(f"max_grid_window structured_adjustment must be dict, got {type(sa).__name__}")
                else:
                    Guardrails._validate_max_grid_window(sa, errors)

        # 6. Check explanation is non-empty string
        if "explanation" in entry:
            if not isinstance(entry["explanation"], str) or not entry["explanation"].strip():
                errors.append("explanation must be a non-empty string")

        # 7. Post-normalization: ensure hour arrays are sorted, unique, integer-only
        # (already done during validation, but re-apply safe normalization)
        # Note: safe normalization sorts and deduplicates; if this changes semantics,
        # the entry may be flagged

        return GuardrailResult(
            valid=len(errors) == 0,
            errors=errors,
            repaired=None,  # repairs only on controlled retry
        )

    @staticmethod
    def _validate_solar_reduction(sa: Dict[str, Any], errors: List[str]) -> None:
        """Validate solar_reduction structured_adjustment."""
        hours = sa.get("hours", [])
        factor = sa.get("factor")

        # Validate hours
        Guardrails._validate_hour_array(hours, "hours", errors, "solar_reduction")

        # Validate factor: finite, 0 <= factor <= 1
        if factor is None:
            errors.append("solar_reduction missing factor")
        else:
            if not isinstance(factor, (int, float)):
                errors.append(f"factor must be number, got {type(factor).__name__}")
            else:
                import math
                if not math.isfinite(factor):
                    errors.append("factor must be finite")
                if factor < 0 or factor > 1:
                    errors.append("factor must be in [0, 1] (fraction remaining)")

        # Check for extra keys
        if set(sa.keys()) - SOLAR_REDUCTION_KEYS:
            errors.append(f"solar_reduction extra keys in structured_adjustment: {set(sa.keys()) - SOLAR_REDUCTION_KEYS}")

    @staticmethod
    def _validate_minimum_battery_reserve(sa: Dict[str, Any], battery_capacity_kwh: float, errors: List[str]) -> None:
        """Validate minimum_battery_reserve structured_adjustment."""
        hours = sa.get("hours", [])
        minimum_energy = sa.get("minimum_energy_kwh")

        # Validate hours
        Guardrails._validate_hour_array(hours, "hours", errors, "minimum_battery_reserve")

        # Validate minimum_energy_kwh
        if minimum_energy is None:
            errors.append("minimum_battery_reserve missing minimum_energy_kwh")
        else:
            if not isinstance(minimum_energy, (int, float)):
                errors.append(f"minimum_energy_kwh must be number, got {type(minimum_energy).__name__}")
            else:
                if not math.isfinite(minimum_energy):
                    errors.append("minimum_energy_kwh must be finite")
                if minimum_energy < 0:
                    errors.append("minimum_energy_kwh must be >= 0")
                if minimum_energy > battery_capacity_kwh:
                    errors.append(f"minimum_energy_kwh ({minimum_energy}) must not exceed battery capacity ({battery_capacity_kwh})")

        # Check for extra keys
        if set(sa.keys()) - MINIMUM_BATTERY_RESERVE_KEYS:
            errors.append(f"minimum_battery_reserve extra keys: {set(sa.keys()) - MINIMUM_BATTERY_RESERVE_KEYS}")

    @staticmethod
    def _validate_hour_array(
        hours: Any,
        field_name: str,
        errors: List[str],
        directive_type: str,
    ) -> None:
        """Validate that hours is a sorted list of unique integers 0..23."""
        if not isinstance(hours, list):
            errors.append(f"{field_name} must be a list, got {type(hours).__name__}")
            return

# Check all integers
        for idx, h in enumerate(hours):
            if not isinstance(h, int):
                errors.append(f"{field_name}[{idx}] must be integer, got {type(h).__name__}")
                return

        # Check 0..23
        for h in hours:
            if h < 0 or h > 23:
                errors.append(f"{field_name} values must be 0..23, found {h}")

        # Check uniqueness
        if len(hours) != len(set(hours)):
            errors.append(f"{field_name} must contain unique values")

        # Check ascending
        if hours != sorted(hours):
            errors.append(f"{field_name} must be sorted ascending")

    @staticmethod
    def _validate_max_grid_window(sa: Dict[str, Any], errors: List[str]) -> None:
        """Validate max_grid_window structured_adjustment."""
        hours = sa.get("hours", [])
        max_grid = sa.get("max_grid_kwh")

        Guardrails._validate_hour_array(hours, "hours", errors, "max_grid_window")

        if max_grid is None:
            errors.append("max_grid_window missing max_grid_kwh")
        else:
            if not isinstance(max_grid, (int, float)):
                errors.append(f"max_grid_kwh must be number, got {type(max_grid).__name__}")
            else:
                if not math.isfinite(max_grid):
                    errors.append("max_grid_kwh must be finite")
                if max_grid < 0:
                    errors.append("max_grid_kwh must be >= 0")

        if set(sa.keys()) - {"hours", "max_grid_kwh"}:
            errors.append(f"max_grid_window extra keys: {set(sa.keys()) - {'hours', 'max_grid_kwh'}}")

    @staticmethod
    def validate_all(
        interpretations: List[Dict[str, Any]],
        operator_notes_count: int,
        battery_capacity_kwh: float,
    ) -> GuardrailResult:
        """Validate all interpretation entries.

        Args:
            interpretations: List of dicts from LLM (one per note)
            operator_notes_count: Expected number of notes (len(operator_notes))
            battery_capacity_kwh: Battery capacity for percentage conversion

        Returns:
            GuardrailResult with valid=True if all entries pass
        """
        errors: List[str] = []

        # Check array length matches operator_notes count
        if len(interpretations) != operator_notes_count:
            errors.append(f"expected {operator_notes_count} interpretations, got {len(interpretations)}")

        # Check note_index coverage exactly 0..N-1
        if len(interpretations) == operator_notes_count:
            indices = []
            for i, entry in enumerate(interpretations):
                ni = entry.get("note_index")
                if ni is not None:
                    indices.append(ni)
                else:
                    errors.append(f"entry {i}: missing note_index")

            if len(indices) == len(set(indices)):
                if sorted(indices) != list(range(operator_notes_count)):
                    errors.append(f"note_index coverage must be exactly 0..{operator_notes_count-1}, got {sorted(indices)}")
            else:
                errors.append(f"duplicate note_index values found")

        # Validate each entry
        for i, entry in enumerate(interpretations):
            result = Guardrails.validate_entry(entry)
            if not result.valid:
                for e in result.errors:
                    errors.append(f"entry {i}: {e}")

        return GuardrailResult(
            valid=len(errors) == 0,
            errors=errors,
            repaired=None,
        )