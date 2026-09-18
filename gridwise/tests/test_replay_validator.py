"""Tests for GridWise replay validator."""

import pytest
from gridwise.app.validator import ReplayValidator


class TestReplayValidator:
    """Replay validator tests."""

    def test_valid_plan_idle(self):
        """A completely idle valid plan should pass replay."""
        hourly_plan = [
            {
                "hour": h,
                "grid_kwh": 0.0,
                "solar_used_kwh": 0.0,
                "battery_action": "idle",
                "battery_kwh": 0.0,
                "battery_energy_after_kwh": 100.0,
            }
            for h in range(24)
        ]

        result = ReplayValidator.validate(
            hourly_plan=hourly_plan,
            demands=[0.0] * 24,
            solar_kwh=[0.0] * 24,
            tariffs=[5.0] * 24,
            battery_capacity_kwh=200.0,
            initial_energy_kwh=100.0,
            minimum_energy_kwh=20.0,
            max_charge_kwh_per_hour=50.0,
            max_discharge_kwh_per_hour=50.0,
            can_charge=[True] * 24,
            can_discharge=[True] * 24,
            max_grid=[None] * 24,
            effective_solar=[0.0] * 24,
            hours=list(range(24)),
        )

        assert result["valid"] is True

    def test_energy_balance_charge(self):
        """Verify energy balance for a charge hour."""
        # For charge: grid + solar = demand + battery_kwh
        # Let's use: demand=8, grid=5, solar=3, battery_kwh=0, idle
        # 5 + 3 = 8 ✓

        hourly_plan_24 = [
            {
                "hour": h,
                "grid_kwh": 5.0 if h == 0 else 0.0,
                "solar_used_kwh": 3.0 if h == 0 else 0.0,
                "battery_action": "idle" if h == 0 else "idle",
                "battery_kwh": 0.0,
                "battery_energy_after_kwh": 100.0,
            }
            for h in range(24)
        ]

        result = ReplayValidator.validate(
            hourly_plan=hourly_plan_24,
            demands=[8.0] + [0.0] * 23,
            solar_kwh=[3.0] + [0.0] * 23,
            tariffs=[5.0] * 24,
            battery_capacity_kwh=200.0,
            initial_energy_kwh=100.0,
            minimum_energy_kwh=20.0,
            max_charge_kwh_per_hour=50.0,
            max_discharge_kwh_per_hour=50.0,
            can_charge=[True] * 24,
            can_discharge=[True] * 24,
            max_grid=[None] * 24,
            effective_solar=[3.0] + [0.0] * 23,
            hours=list(range(24)),
        )

        assert result["valid"] is True

    def test_energy_balance_discharge(self):
        """Verify energy balance for a discharge hour."""
        # For discharge: grid + solar + battery_kwh = demand
        # Let's say: demand=5, grid=2, solar=0, battery discharge=3
        # 2 + 0 + 3 = 5 ✓

        hourly_plan_24 = [
            {
                "hour": h,
                "grid_kwh": 2.0 if h == 0 else 0.0,
                "solar_used_kwh": 0.0,
                "battery_action": "discharge" if h == 0 else "idle",
                "battery_kwh": 3.0 if h == 0 else 0.0,
                "battery_energy_after_kwh": 97.0 if h == 0 else 100.0 - (3.0 if h == 0 else 0.0),
            }
            for h in range(24)
        ]

        result = ReplayValidator.validate(
            hourly_plan=hourly_plan_24,
            demands=[5.0] + [0.0] * 23,
            solar_kwh=[0.0] * 24,
            tariffs=[5.0] * 24,
            battery_capacity_kwh=200.0,
            initial_energy_kwh=100.0,
            minimum_energy_kwh=20.0,
            max_charge_kwh_per_hour=50.0,
            max_discharge_kwh_per_hour=50.0,
            can_charge=[True] * 24,
            can_discharge=[True] * 24,
            max_grid=[None] * 24,
            effective_solar=[0.0] * 24,
            hours=list(range(24)),
        )

        assert result["valid"] is True