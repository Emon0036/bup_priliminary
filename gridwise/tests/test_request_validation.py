"""Tests for GridWise request validation."""

import pytest
from fastapi.testclient import TestClient
from gridwise.app.main import app
from gridwise.app.models import OptimizeEnergyRequest


class TestRequestValidation:
    """Request model validation tests."""

    def test_valid_request(self):
        """A valid request should pass Pydantic validation."""
        client = TestClient(app)
        request = {
            "scenario_id": "test-001",
            "operator_notes": ["solar reduction during afternoon"],
            "hours": [
                {"hour": h, "demand_kwh": 10.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 5.0}
                for h in range(24)
            ],
            "battery": {
                "capacity_kwh": 200.0,
                "initial_energy_kwh": 100.0,
                "minimum_energy_kwh": 20.0,
                "max_charge_kwh_per_hour": 50.0,
                "max_discharge_kwh_per_hour": 50.0,
            },
        }
        response = client.post("/optimize-energy", json=request)
        # Should either succeed or fail with validation/LLM errors, but not 422 from Pydantic
        # (Pydantic validation should have passed)
        assert response.status_code != 422  # Pydantic should have accepted it

    def test_missing_scenario_id(self):
        """Request without scenario_id should be rejected."""
        client = TestClient(app)
        request = {
            "operator_notes": ["test"],
            "hours": [
                {"hour": h, "demand_kwh": 10.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 5.0}
                for h in range(24)
            ],
            "battery": {
                "capacity_kwh": 200.0,
                "initial_energy_kwh": 100.0,
                "minimum_energy_kwh": 20.0,
                "max_charge_kwh_per_hour": 50.0,
                "max_discharge_kwh_per_hour": 50.0,
            },
        }
        response = client.post("/optimize-energy", json=request)
        # Pydantic validation should reject this
        assert response.status_code in (400, 422)

    def test_duplicate_hours(self):
        """Request with duplicate hours should be rejected."""
        client = TestClient(app)
        hours = [
            {"hour": 0, "demand_kwh": 10.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 5.0}
        ] * 24  # 24 copies of hour 0
        request = {
            "scenario_id": "test-002",
            "operator_notes": ["test"],
            "hours": hours,
            "battery": {
                "capacity_kwh": 200.0,
                "initial_energy_kwh": 100.0,
                "minimum_energy_kwh": 20.0,
                "max_charge_kwh_per_hour": 50.0,
                "max_discharge_kwh_per_hour": 50.0,
            },
        }
        response = client.post("/optimize-energy", json=request)
        assert response.status_code in (400, 422)

    def test_wrong_number_of_hours(self):
        """Request with fewer/more than 24 hours should be rejected."""
        client = TestClient(app)
        hours = [
            {"hour": h, "demand_kwh": 10.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 5.0}
            for h in range(23)  # only 23 hours
        ]
        request = {
            "scenario_id": "test-003",
            "operator_notes": ["test"],
            "hours": hours,
            "battery": {
                "capacity_kwh": 200.0,
                "initial_energy_kwh": 100.0,
                "minimum_energy_kwh": 20.0,
                "max_charge_kwh_per_hour": 50.0,
                "max_discharge_kwh_per_hour": 50.0,
            },
        }
        response = client.post("/optimize-energy", json=request)
        assert response.status_code in (400, 422)