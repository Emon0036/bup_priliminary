# GridWise Architecture

## Overview

GridWise is a smart campus energy optimization system that combines LLM-powered natural language understanding with deterministic mathematical optimization. The system interprets free-text operator notes and converts them into a cost-minimized 24-hour energy schedule.

## Pipeline

```
┌─────────────────┐
│   HTTP Request   │  POST /optimize-energy
└────────┬────────┘
         ▼
┌─────────────────┐
│  Pydantic        │  Request validation (schema, types, ranges)
│  Validation      │
└────────┬────────┘
         ▼
┌─────────────────┐
│  LLM             │  Single call: interpret 1-3 operator notes
│  Interpreter     │  → structured JSON directives
└────────┬────────┘
         ▼
┌─────────────────┐
│  Deterministic   │  Validate every LLM output field
│  Guardrails      │  Repair if possible, reject if not
└────────┬────────┘
         ▼
┌─────────────────┐
│  Directive       │  Convert interpretations → per-hour constraints
│  Compiler        │  effective_solar, minimum_reserve, can_charge, etc.
└────────┬────────┘
         ▼
┌─────────────────┐
│  LP Optimizer    │  scipy linprog (HiGHS) — 72 variables
│  (HiGHS)         │  minimize Σ G[h] × tariff[h]
└────────┬────────┘
         ▼
┌─────────────────┐
│  Replay          │  Independent validation — no optimizer code reused
│  Validator       │  Check all equations, bounds, state transitions
└────────┬────────┘
         ▼
┌─────────────────┐
│  Totals &        │  Compute total_grid, total_cost, peak_grid
│  Summary         │  Generate deterministic plan_summary
└────────┬────────┘
         ▼
┌─────────────────┐
│  JSON Response   │  POST 200 with full plan
└─────────────────┘
```

## Components

### 1. Request Validation (`models.py`)
- Pydantic v2 with `extra="forbid"` to reject unexpected fields
- Exactly 24 hour entries, each 0..23
- Non-negative demand, solar, tariff
- Battery capacity > 0, initial within bounds

### 2. LLM Interpreter (`llm/`)
- Single OpenAI-compatible API call per request
- System prompt instructs structured JSON output
- Supports any OpenAI-compatible provider (OpenAI, Anthropic, local)
- Post-processing extracts JSON from potential markdown fences

### 3. Guardrails (`guardrails.py`)
- Validates every interpretation entry:
  - Correct directive type
  - `applies` flag matches type semantics
  - `structured_adjustment` has correct keys and value ranges
  - Hour arrays: sorted, unique, integers 0..23
- Repairs common issues or rejects with 422

### 4. Directive Compiler (`directives.py`)
- Converts validated interpretations → per-hour constraint arrays
- `effective_solar[h]`: solar available after reductions
- `minimum_reserve[h]`: floor for battery SOC
- `can_charge[h]`, `can_discharge[h]`: boolean windows
- `max_grid[h]`: optional grid import cap

### 5. LP Optimizer (`optimizer.py`)
- **72 variables**: 3 per hour (G, S, B)
- **Objective**: minimize total grid import cost
- **Equality constraints**: energy balance + end-of-day neutrality
- **Inequality constraints**: rate limits, capacity bounds, directive windows
- Uses HiGHS solver via scipy.optimize.linprog

### 6. Replay Validator (`validator.py`)
- Independent check — no optimizer code reused
- Verifies: non-negativity, energy balance, SOC bounds, neutrality
- Tolerance: 1e-4 kWh (tighter than judge's 0.01 kWh)
- If validation fails → HTTP 422 instead of 200

## Energy Balance Equation

For each hour h:
```
G[h] + S[h] = demand[h] + B[h]
```

Where:
- `G[h]` = grid import (≥ 0)
- `S[h]` = solar used (0 ≤ S[h] ≤ effective_solar[h])
- `B[h]` = signed battery change (+ charge, − discharge, 0 idle)

## Battery State

```
E[h] = initial_energy + Σ B[0..h]
```

Constraints:
- `minimum_energy_kwh ≤ E[h] ≤ capacity_kwh` for all h
- `E[23] = initial_energy` (end-of-day neutrality)

## Directive Types

| Type | structured_adjustment | Constraint |
|------|----------------------|------------|
| `solar_reduction` | `{"hours": [...], "factor": 0.0-1.0}` | `S[h] ≤ solar_kwh[h] × factor` |
| `minimum_battery_reserve` | `{"hours": [...], "minimum_energy_kwh": N}` | `E[h] ≥ N` |
| `no_charge_window` | `{"hours": [...]}` | `B[h] ≤ 0` |
| `no_discharge_window` | `{"hours": [...]}` | `B[h] ≥ 0` |
| `max_grid_window` | `{"hours": [...], "max_grid_kwh": N}` | `G[h] ≤ N` |
| `no_op` | `null` | (no constraint) |

## Error Handling

- **Pydantic validation error** → HTTP 422 with field-level details
- **Guardrails failure** → HTTP 422 with sanitised error list
- **Optimizer infeasible** → HTTP 422 "infeasible or solver error"
- **Replay validation failure** → HTTP 422 with first error
- **Unexpected exception** → HTTP 500 "internal server error"

## Security

- API key stored in environment variable, never logged
- Stack traces not exposed to clients
- `.env` files excluded via `.gitignore`
- Docker runs as non-root user
- No secrets in Docker image layers
