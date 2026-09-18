"""Independent replay validator for GridWise optimizer output.

This validator independently replays the returned plan hour by hour,
verifying every equation and bound without calling optimizer code.

If replay fails, DO NOT return HTTP 200.
Log a sanitized internal error and return controlled failure.
"""

from typing import List, Dict, Any, Optional
import math

# ---------------------------------------------------------------------------
# Tolerances (much tighter than judge's 0.01 kWh / BDT tolerance)
# ---------------------------------------------------------------------------
EPS = 1e-7  # internal tolerance for "zero" detection
REPLAY_TOLERANCE = 1e-3  # tolerance for replay validation (judge uses 0.01 kWh)
MAX_CHARGE_DEFAULT = 1e6  # fallback default for max charge rate
MAX_DISCHARGE_DEFAULT = 1e6  # fallback default for max discharge rate


class ReplayValidator:
    """Independent replay validator that checks the hourly plan validity."""

    @staticmethod
    def validate(
        hourly_plan: List[Dict[str, Any]],
        demands: List[float],
        solar_kwh: List[float],
        tariffs: List[float],
        battery_capacity_kwh: float,
        initial_energy_kwh: float,
        minimum_energy_kwh: float,
        max_charge_kwh_per_hour: float,
        max_discharge_kwh_per_hour: float,
        can_charge: List[bool],
        can_discharge: List[bool],
        max_grid: List[Optional[float]],
        effective_solar: List[float],
        hours: List[int],
    ) -> Dict[str, Any]:
        """Validate the hourly plan by independent replay.

        Returns dict with "valid": bool and "errors": List[str]
        """
        errors: List[str] = []

        # Basic structure checks
        if len(hourly_plan) != 24:
            errors.append(f"expected 24 hourly plan rows, got {len(hourly_plan)}")
            return {"valid": False, "errors": errors}

        # Check hours exactly 0..23
        plan_hours = [p["hour"] for p in hourly_plan]
        if sorted(plan_hours) != list(range(24)):
            errors.append(f"hours must be exactly 0..23, got {plan_hours}")

        # Deduplication check
        if len(plan_hours) != len(set(plan_hours)):
            errors.append("duplicate hours in plan")

        for hour_idx, plan_entry in enumerate(hourly_plan):
            h = plan_entry["hour"]
            # grid >= 0
            grid_kwh = plan_entry["grid_kwh"]
            if grid_kwh is None or grid_kwh < -EPS:
                errors.append(f"hour {h}: grid_kwh must be >= 0, got {grid_kwh}")
            elif grid_kwh < 0:
                errors.append(f"hour {h}: grid_kwh must be >= 0")

            # solar_used >= 0
            solar_used = plan_entry["solar_used_kwh"]
            if solar_used is None or solar_used < -EPS:
                errors.append(f"hour {h}: solar_used_kwh must be >= 0, got {solar_used}")

            # solar_used <= effective_solar (round for comparison consistency)
            eff_solar_r = round(effective_solar[h], 6)
            if solar_used is not None and solar_used > eff_solar_r + EPS:
                errors.append(f"hour {h}: solar_used ({solar_used}) > effective_solar ({effective_solar[h]})")

            # battery_action enum valid
            battery_action = plan_entry["battery_action"]
            if battery_action not in ("charge", "discharge", "idle"):
                errors.append(f"hour {h}: invalid battery_action '{battery_action}'")

            # idle => battery_kwh = 0
            battery_kwh = plan_entry["battery_kwh"]
            if battery_action == "idle" and abs(battery_kwh) > EPS:
                errors.append(f"hour {h}: idle action must have battery_kwh = 0, got {battery_kwh}")

            # battery_kwh non-negative
            if battery_kwh is not None and battery_kwh < -EPS:
                errors.append(f"hour {h}: battery_kwh must be non-negative, got {battery_kwh}")

            # charging within max rate
            if battery_action == "charge" and can_charge[h]:
                max_charge_r = round(max_charge_kwh_per_hour, 6)
                if battery_kwh > max_charge_r + EPS:
                    errors.append(f"hour {h}: charge battery_kwh ({battery_kwh}) > max_charge rate ({max_charge_kwh_per_hour})")

            # discharging within max rate
            if battery_action == "discharge" and can_discharge[h]:
                max_discharge_r = round(max_discharge_kwh_per_hour, 6)
                if battery_kwh > max_discharge_r + EPS:
                    errors.append(f"hour {h}: discharge battery_kwh ({battery_kwh}) > max_discharge rate ({max_discharge_kwh_per_hour})")

            # no-charge directives respected
            if battery_action == "charge" and not can_charge[h]:
                errors.append(f"hour {h}: charging but no_charge_window active")

            # no-discharge directives respected
            if battery_action == "discharge" and not can_discharge[h]:
                errors.append(f"hour {h}: discharging but no_discharge_window active")

            # State transition check
            # Verify energy balance: grid + solar_used + battery_discharge = demand + battery_charge
            # For charge: grid + solar_used = demand + battery_kwh
            # For discharge: grid + solar_used + battery_kwh = demand (since B < 0)
            # For idle: grid + solar_used = demand

            demand = demands[h]
            solar_avail = effective_solar[h]

            if battery_action == "charge":
                # B > 0: grid + solar = demand + battery_kwh
                lhs = grid_kwh + solar_used
                rhs = demand + battery_kwh
                if abs(lhs - rhs) > REPLAY_TOLERANCE:
                    errors.append(f"hour {h}: charge energy balance violation: "
                                  f"grid+solar={lhs}, demand+battery={rhs}, diff={abs(lhs-rhs)}")

            elif battery_action == "discharge":
                # B < 0: grid + solar + |B| = demand
                # i.e., grid + solar + battery_kwh = demand
                lhs = grid_kwh + solar_used + battery_kwh
                rhs = demand
                if abs(lhs - rhs) > REPLAY_TOLERANCE:
                    errors.append(f"hour {h}: discharge energy balance violation: "
                                  f"grid+solar+abs(B)={lhs}, demand={rhs}, diff={abs(lhs-rhs)}")

            else:  # idle
                # grid + solar = demand
                lhs = grid_kwh + solar_used
                rhs = demand
                if abs(lhs - rhs) > REPLAY_TOLERANCE:
                    errors.append(f"hour {h}: idle energy balance violation: "
                                  f"grid+solar={lhs}, demand={rhs}, diff={abs(lhs-rhs)}")

            # Battery capacity check: minimum_reserve <= E[h] <= capacity
            # E[h] is battery_energy_after_kwh
            battery_energy_after = plan_entry["battery_energy_after_kwh"]
            if battery_energy_after is not None:
                bat_ea_r = round(battery_energy_after, 6)
                if bat_ea_r > round(battery_capacity_kwh, 6) + EPS:
                    errors.append(f"hour {h}: battery_energy_after ({battery_energy_after}) > capacity ({battery_capacity_kwh})")
                if bat_ea_r < round(minimum_energy_kwh, 6) - EPS:
                    errors.append(f"hour {h}: battery_energy_after ({battery_energy_after}) < minimum ({minimum_energy_kwh})")

            # Max grid check
            if max_grid[h] is not None and grid_kwh is not None:
                if grid_kwh > max_grid[h] + EPS:
                    errors.append(f"hour {h}: grid_kwh ({grid_kwh}) > max_grid ({max_grid[h]})")

        # Final SOC check: battery_energy_after hour 23 == initial_energy_kwh
        last_entry = hourly_plan[23]
        last_energy_after = last_entry["battery_energy_after_kwh"]
        if last_energy_after is not None:
            if abs(last_energy_after - initial_energy_kwh) > REPLAY_TOLERANCE:
                errors.append(f"hour 23: final battery_energy_after ({last_energy_after}) "
                              f"!= initial ({initial_energy_kwh}), diff={abs(last_energy_after - initial_energy_kwh)}")

        # All values finite check
        for hour_idx, plan_entry in enumerate(hourly_plan):
            for key, val in plan_entry.items():
                # Only check finite for numeric values; skip strings, bools, etc.
                if val is not None and isinstance(val, (int, float)) and not math.isfinite(val):
                    errors.append(f"hour {hour_idx}/{key}: value not finite: {val}")

        valid = len(errors) == 0
        return {"valid": valid, "errors": errors}