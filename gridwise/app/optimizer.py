"""Deterministic LP optimizer for GridWise energy scheduling.

Uses scipy.optimize.linprog(method="highs") / HiGHS to minimize grid import cost.

Builds the linear program from per-hour constraints compiled from directive
interpretations. Does NOT modify LLM output directly - only applies guardrail-
validated constraints.
"""

import math
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from scipy.optimize import linprog


# ---------------------------------------------------------------------------
# LP optimization entry point
# ---------------------------------------------------------------------------

def optimize_energy(
    demands: List[float],
    solar_kwh: List[float],
    tariffs: List[float],
    battery_capacity_kwh: float,
    initial_energy_kwh: float,
    minimum_energy_kwh: float,
    max_charge_kwh_per_hour: float,
    max_discharge_kwh_per_hour: float,
    effective_solar: List[float],
    minimum_reserve: List[float],
    can_charge: List[bool],
    can_discharge: List[bool],
    max_grid: List[Optional[float]],
) -> Optional[Dict[str, Any]]:
    """Run the LP optimizer and return the solution.

    Returns dict with per-hour results or None if infeasible.

    Variables per hour h (0..23), total 72 variables:
      x[3*h + 0] = G[h] = grid import (>= 0)
      x[3*h + 1] = S[h] = solar used (0 <= S[h] <= effective_solar[h])
      x[3*h + 2] = B[h] = signed battery change
        B[h] > 0 = charge, B[h] < 0 = discharge, B[h] = 0 = idle

    Objective: minimize sum(G[h] * tariff[h])
    """

    n_hours = 24
    n_vars = 3 * n_hours  # 72

    # --- Objective: minimize SUM(G[h] * tariff[h])
    c = np.zeros(n_vars)
    for h in range(n_hours):
        c[3 * h] = tariffs[h]

    # --- Build inequality constraints (A_ub @ x <= b_ub)
    A_ub_rows = []
    b_ub_rows = []

    for h in range(n_hours):
        posG = 3 * h   # G[h]
        posS = 3 * h + 1   # S[h]
        posB = 3 * h + 2   # B[h]

        # Battery charge rate limit: B[h] <= max_charge
        row = np.zeros(n_vars)
        row[posB] = 1.0
        A_ub_rows.append(row)
        b_ub_rows.append(max_charge_kwh_per_hour)

        # Battery discharge rate limit: -B[h] <= max_discharge  => B[h] >= -max_discharge
        row = np.zeros(n_vars)
        row[posB] = -1.0
        A_ub_rows.append(row)
        b_ub_rows.append(max_discharge_kwh_per_hour)

        # Solar used <= effective solar: S[h] <= effective_solar[h]
        row = np.zeros(n_vars)
        row[posS] = 1.0
        A_ub_rows.append(row)
        b_ub_rows.append(effective_solar[h])

        # no_charge: B[h] <= 0  (if no_charge_window active)
        if not can_charge[h]:
            row = np.zeros(n_vars)
            row[posB] = 1.0
            A_ub_rows.append(row)
            b_ub_rows.append(0.0)

        # no_discharge: -B[h] <= 0  => B[h] >= 0  (if no_discharge_window active)
        if not can_discharge[h]:
            row = np.zeros(n_vars)
            row[posB] = -1.0
            A_ub_rows.append(row)
            b_ub_rows.append(0.0)

        # max_grid_window: G[h] <= max_grid_kwh
        if max_grid[h] is not None:
            row = np.zeros(n_vars)
            row[posG] = 1.0
            A_ub_rows.append(row)
            b_ub_rows.append(float(max_grid[h]))

    # Battery capacity inequality constraints:
    # E[h] = initial_energy + sum(B[0..h]) <= battery_capacity_kwh
    # => sum(B[0..h]) <= battery_capacity_kwh - initial_energy
    for h in range(n_hours):
        row = np.zeros(n_vars)
        for i in range(h + 1):
            row[3 * i + 2] = 1.0  # coefficient for B[i]
        A_ub_rows.append(row)
        b_ub_rows.append(battery_capacity_kwh - initial_energy_kwh)

    # E[h] >= minimum_reserve[k]
    # initial_energy + sum(B[0..h]) >= minimum_energy_kwh
    # sum(B[0..h]) >= minimum_energy_kwh - initial_energy
    # => -sum(B[0..h]) <= initial_energy - minimum_energy_kwh
    for h in range(n_hours):
        row = np.zeros(n_vars)
        for i in range(h + 1):
            row[3 * i + 2] = -1.0  # coefficient for -B[i]
        A_ub_rows.append(row)
        b_ub_rows.append(initial_energy_kwh - minimum_reserve[h])

    A_ub = np.array(A_ub_rows) if A_ub_rows else np.zeros((0, n_vars))
    b_ub = np.array(b_ub_rows) if b_ub_rows else np.zeros(0)

    # --- Build equality constraints (A_eq @ x == b_eq)
    A_eq_rows = []
    b_eq_rows = []

    # Energy balance per hour: G[h] + S[h] - B[h] = demand[h]
    for h in range(n_hours):
        posG = 3 * h
        posS = 3 * h + 1
        posB = 3 * h + 2
        row = np.zeros(n_vars)
        row[posG] = 1.0
        row[posS] = 1.0
        row[posB] = -1.0
        A_eq_rows.append(row)
        b_eq_rows.append(demands[h])

    # End-of-day neutrality: E[23] = initial_energy
    # => initial_energy + sum(B[0..23]) = initial_energy
    # => sum(B[0..23]) = 0
    row = np.zeros(n_vars)
    for h in range(n_hours):
        row[3 * h + 2] = 1.0  # coefficient for B[h]
    A_eq_rows.append(row)
    b_eq_rows.append(0.0)

    A_eq = np.array(A_eq_rows) if A_eq_rows else np.zeros((0, n_vars))
    b_eq = np.array(b_eq_rows) if b_eq_rows else np.zeros(0)

    # --- Bounds per variable
    # G[h] >= 0, S[h] >= 0, B[h] unconstrained (handled by inequality constraints)
    bounds = []
    for h in range(n_hours):
        # G[h] at position 3*h, lower bound 0
        bounds.append((0, None))
        # S[h] at position 3*h+1, lower bound 0
        bounds.append((0, None))
        # B[h] at position 3*h+2, unconstrained
        bounds.append((None, None))

    # --- Solve
    result = linprog(
        c=c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        print(f"LP solver failed: {result.message}")
        return None

    x = result.x

    # Parse results and build hourly plan
    hourly_plan = []
    # Track cumulative battery energy for state validation
    cum_B = 0.0  # cumulative sum of B[0..h-1] before current hour

    for h in range(n_hours):
        posG = 3 * h
        posS = 3 * h + 1
        posB = 3 * h + 2
        G = x[posG]  # grid import
        S = x[posS]  # solar used
        B = x[posB]  # signed battery change

        # Determine battery action using tight EPSILON
        if B > 1e-7:
            action = "charge"
            battery_kwh = B
        elif B < -1e-7:
            action = "discharge"
            battery_kwh = -B  # absolute value
        else:
            action = "idle"
            battery_kwh = 0.0

        # Normalize tiny values to 0.0
        if abs(battery_kwh) < 1e-6:
            battery_kwh = 0.0
            action = "idle"

        # Compute battery energy after this hour
        # E[h] = initial_energy + cum_B + B
        # But we need to check bounds; the LP already enforced them
        battery_energy_after = initial_energy_kwh + cum_B + B

        # Round values for stable JSON output
        # Also round effective_solar to match solar_used rounding
        eff_solar_rounded = round(effective_solar[h], 6)
        G_rounded = round(max(G, 0), 6)
        S_rounded = round(min(S, effective_solar[h]), 6)
        # Ensure S_rounded does not exceed rounded effective_solar
        if S_rounded > eff_solar_rounded:
            S_rounded = eff_solar_rounded
        battery_kwh_rounded = round(max(battery_kwh, 0), 6)
        battery_energy_after_rounded = round(battery_energy_after, 6)

        hourly_plan.append({
            "hour": h,
            "grid_kwh": G_rounded,
            "solar_used_kwh": S_rounded,
            "battery_action": action,
            "battery_kwh": battery_kwh_rounded,
            "battery_energy_after_kwh": battery_energy_after_rounded,
        })

        # Update cumulative B for next hour
        cum_B += B

    # Verify end-of-day neutrality
    # cum_B after hour 23 should be 0 (since sum(B) = 0 from equality constraint)
    # But due to floating point, check
    if abs(cum_B) > 1e-4:
        print(f"Warning: end-of-day neutrality violated, cum_B = {cum_B}")

    return {"hourly_plan": hourly_plan}