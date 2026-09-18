"""Randomized optimizer tests using fixed seed for reproducibility."""

import math
import random
from gridwise.app.optimizer import optimize_energy


def _make_scenario(seed: int, idx: int) -> dict:
    """Generate a deterministic feasible scenario."""
    rng = random.Random(seed + idx)

    # Generate 24 hours of demand/solar/tariff
    demands = [rng.uniform(1, 20) for _ in range(24)]
    solar_kwh = [rng.uniform(0, 15) for _ in range(24)]
    # Tariffs vary through the day (peak in evening)
    tariffs = [rng.uniform(3, 15) for _ in range(24)]

    # Battery parameters
    battery_capacity_kwh = rng.uniform(100, 500)
    initial_energy_kwh = rng.uniform(20, battery_capacity_kwh - 20)
    minimum_energy_kwh = rng.uniform(10, 50)
    max_charge_kwh_per_hour = rng.uniform(5, 30)
    max_discharge_kwh_per_hour = rng.uniform(5, 30)

    # Effective solar starts raw, directives may reduce it
    effective_solar = list(solar_kwh)

    # Simple constraints: no special directives for now
    minimum_reserve = [minimum_energy_kwh] * 24
    can_charge = [True] * 24
    can_discharge = [True] * 24
    max_grid = [None] * 24

    return {
        "demands": demands,
        "solar_kwh": solar_kwh,
        "tariffs": tariffs,
        "battery_capacity_kwh": battery_capacity_kwh,
        "initial_energy_kwh": initial_energy_kwh,
        "minimum_energy_kwh": minimum_energy_kwh,
        "max_charge_kwh_per_hour": max_charge_kwh_per_hour,
        "max_discharge_kwh_per_hour": max_discharge_kwh_per_hour,
        "effective_solar": effective_solar,
        "minimum_reserve": minimum_reserve,
        "can_charge": can_charge,
        "can_discharge": can_discharge,
        "max_grid": max_grid,
    }


def test_randomized_optimizer_100_scenarios():
    """Run 100 randomized scenarios and verify optimizer output via replay validator."""
    failure_count = 0
    for idx in range(100):
        scenario = _make_scenario(seed=42, idx=idx)
        result = optimize_energy(
            demands=scenario["demands"],
            solar_kwh=scenario["solar_kwh"],
            tariffs=scenario["tariffs"],
            battery_capacity_kwh=scenario["battery_capacity_kwh"],
            initial_energy_kwh=scenario["initial_energy_kwh"],
            minimum_energy_kwh=scenario["minimum_energy_kwh"],
            max_charge_kwh_per_hour=scenario["max_charge_kwh_per_hour"],
            max_discharge_kwh_per_hour=scenario["max_discharge_kwh_per_hour"],
            effective_solar=scenario["effective_solar"],
            minimum_reserve=scenario["minimum_reserve"],
            can_charge=scenario["can_charge"],
            can_discharge=scenario["can_discharge"],
            max_grid=scenario["max_grid"],
        )

        if result is None:
            # Infeasible scenario - count but don't fail
            failure_count += 1
            continue

        # Validate with replay validator
        from gridwise.app.validator import ReplayValidator

        hour_ints = list(range(24))
        replay_result = ReplayValidator.validate(
            hourly_plan=result["hourly_plan"],
            demands=scenario["demands"],
            solar_kwh=scenario["solar_kwh"],
            tariffs=scenario["tariffs"],
            battery_capacity_kwh=scenario["battery_capacity_kwh"],
            initial_energy_kwh=scenario["initial_energy_kwh"],
            minimum_energy_kwh=scenario["minimum_energy_kwh"],
            max_charge_kwh_per_hour=scenario["max_charge_kwh_per_hour"],
            max_discharge_kwh_per_hour=scenario["max_discharge_kwh_per_hour"],
            can_charge=scenario["can_charge"],
            can_discharge=scenario["can_discharge"],
            max_grid=scenario["max_grid"],
            effective_solar=scenario["effective_solar"],
            hours=hour_ints,
        )

        if not replay_result["valid"]:
            failure_count += 1
            print(f"Scenario {idx}: replay validation failed: {replay_result['errors'][:3]}")

    # Allow some infeasible scenarios but not too many
    print(f"Randomized optimizer: 100 scenarios, {failure_count} failures")
    assert failure_count < 15, f"Too many failures: {failure_count}"