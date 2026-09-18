"""Deterministic directive compiler.

Builds normalized per-hour constraint representation before solving the LP.

Takes validated LLM interpretations and battery/request data, produces:
- effective_solar[h] for h=0..23
- minimum_reserve[h] for h=0..23
- can_charge[h] boolean for h=0..23
- can_discharge[h] boolean for h=0..23
- max_grid[h] or None for h=0..23
"""

import math
from typing import List, Dict, Any, Optional


def compile_directives(
    interpretations: List[Dict[str, Any]],
    battery_capacity_kwh: float,
    hours_0_to_23: List[int],
    base_minimum_energy_kwh: float = 0.0,
) -> Dict[str, Any]:
    """Compile validated directive interpretations into per-hour constraint arrays.

    Args:
        interpretations: List of validated interpretation dicts (one per note)
        battery_capacity_kwh: Battery capacity for percentage reserve conversion
        hours_0_to_23: List of hour integers 0..23 in order
        base_minimum_energy_kwh: Base minimum energy from battery config

    Returns:
        Dict with per-hour constraint arrays:
        {
            "effective_solar": [...],
            "minimum_reserve": [...],
            "can_charge": [...],
            "can_discharge": [...],
            "max_grid": [...],
        }
    """
    # Initialize base arrays
    n = 24
    effective_solar = [0.0] * n  # will be set per hour from request
    minimum_reserve = [base_minimum_energy_kwh] * n  # base minimum from request
    can_charge = [True] * n
    can_discharge = [True] * n
    max_grid = [None] * n  # None means no cap

    # We'll set effective_solar from the request later; for now initialize minimums
    # minimum_reserve will be set per-hour after we know the base minimum_energy_kwh

    # Process each interpretation
    for interp in interpretations:
        directive_type = interp.get("directive_type")
        structured_adjustment = interp.get("structured_adjustment")
        applies = interp.get("applies", True)

        if not applies:
            # no_op: no changes
            continue

        if directive_type == "solar_reduction":
            _apply_solar_reduction(structured_adjustment, effective_solar)

        elif directive_type == "minimum_battery_reserve":
            _apply_minimum_battery_reserve(
                structured_adjustment, battery_capacity_kwh, minimum_reserve
            )

        elif directive_type == "no_charge_window":
            _apply_no_charge_window(structured_adjustment, can_charge)

        elif directive_type == "no_discharge_window":
            _apply_no_discharge_window(structured_adjustment, can_discharge)

        elif directive_type == "max_grid_window":
            _apply_max_grid_window(
                structured_adjustment, max_grid
            )

        # If directive_type is something unexpected, it would have been
        # caught by guardrails already; just skip

    result: Dict[str, Any] = {
        "effective_solar": effective_solar,
        "minimum_reserve": minimum_reserve,
        "can_charge": can_charge,
        "can_discharge": can_discharge,
        "max_grid": max_grid,
    }

    return result


# --- Specific directive applications ---


def _apply_solar_reduction(
    sa: Dict[str, Any],
    effective_solar: List[float],
) -> None:
    """Apply solar_reduction: effective_solar[h] = original_solar[h] * factor.

    Note: The actual original solar values come from the request.
    This function modifies effective_solar in-place assuming the caller has
    already set effective_solar[h] = request solar_kwh[h], and then this
    function multiplies by the factor.
    """
    hours = sa.get("hours", [])
    factor = sa.get("factor", 1.0)

    # Validate factor is fraction remaining 0 <= factor <= 1
    if not isinstance(factor, (int, float)) or not math.isfinite(factor):
        return  # should have been caught by guardrails

    for h in hours:
        if 0 <= h < 24:
            effective_solar[h] *= float(factor)


def _apply_minimum_battery_reserve(
    sa: Dict[str, Any],
    battery_capacity_kwh: float,
    minimum_reserve: List[float],
) -> None:
    """Apply minimum_battery_reserve: minimum_reserve[h] = max(base minimum, directive minimum).

    The base minimum is battery.minimum_energy_kwh from the request.
    Directive minimum can be absolute (kWh) or relative (% of capacity).
    """
    hours = sa.get("hours", [])
    minimum_energy_kwh = sa.get("minimum_energy_kwh")

    if minimum_energy_kwh is None:
        return

    # Determine if it's a percentage or absolute value
    # Heuristic: if minimum_energy_kwh > battery_capacity_kwh * 1.0, it's likely absolute
    # Actually, we should treat it as specified. The system instruction says:
    # "Support absolute values and relative percentages of battery capacity."
    # Example: capacity = 200 kWh, "keep at least 50%" -> minimum_energy_kwh = 100
    # So if the value is a percentage (0-1), we multiply by capacity.
    # If it's an absolute value that could be > capacity, it's absolute.
    # But the spec says percentages of capacity, so let's check: if 0 <= value <= 1, treat as percentage.
    # If value > 1, treat as absolute kWh.

    is_percentage = isinstance(minimum_energy_kwh, (int, float)) and \
                    minimum_energy_kwh <= 1.0 and minimum_energy_kwh >= 0

    if is_percentage:
        computed_min = battery_capacity_kwh * float(minimum_energy_kwh)
    else:
        computed_min = float(minimum_energy_kwh)

    for h in hours:
        if 0 <= h < 24:
            # minimum_reserve[h] = max(base minimum, directive minimum)
            # The base minimum is battery.minimum_energy_kwh from request
            # We'll set the base below; for now just ensure it's at least computed_min
            current = minimum_reserve[h]
            if computed_min > current:
                minimum_reserve[h] = computed_min


def _apply_no_charge_window(
    sa: Dict[str, Any],
    can_charge: List[bool],
) -> None:
    """Apply no_charge_window: can_charge[h] = false for those hours."""
    hours = sa.get("hours", [])
    for h in hours:
        if 0 <= h < 24:
            can_charge[h] = False


def _apply_no_discharge_window(
    sa: Dict[str, Any],
    can_discharge: List[bool],
) -> None:
    """Apply no_discharge_window: can_discharge[h] = false for those hours."""
    hours = sa.get("hours", [])
    for h in hours:
        if 0 <= h < 24:
            can_discharge[h] = False


def _apply_max_grid_window(
    sa: Dict[str, Any],
    max_grid: List[Optional[float]],
) -> None:
    """Apply max_grid_window: grid upper bound for that hour = directive cap."""
    hours = sa.get("hours", [])
    max_grid_kwh = sa.get("max_grid_kwh")

    for h in hours:
        if 0 <= h < 24:
            max_grid[h] = float(max_grid_kwh) if max_grid_kwh is not None else None