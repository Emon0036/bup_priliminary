GridWise Specification Notes
============================

This document summarizes the canonical specification from the official problem statement
and participant guide for the BUP CSE FEST 2026 Hackathon Preliminary - GridWise project.

================================================================================
0. CANONICAL SOURCES
================================================================================

Problem Statement (CANONICAL for):
- Endpoints: GET /health, POST /optimize-energy
- Input schema: scenario_id, operator_notes [1-3 strings], hours [24 objects], battery
- Output schema: directive_interpretation, hourly_plan, total_grid_kwh, total_cost_bdt, peak_grid_kwh, plan_summary
- Directive types: solar_reduction, minimum_battery_reserve, no_charge_window, no_discharge_window, max_grid_window, no_op
- Guardrails and validation rules
- Battery behavior and energy equations
- Optimization validity constraints

Participant Guide (CANONICAL for):
- Scoring categories and point values
- Performance targets (p95 <= 5 seconds)
- Deployment requirements (Docker, 0.0.0.0 binding)
- Repository requirements
- Documentation standards
- Tie-breaking rules
- CI/CD guidelines

================================================================================
1. API CONTRACT
================================================================================

GET /health
  Response: HTTP 200 {"status": "ok"}
  No LLM call required

POST /optimize-energy
  Request body:
  {
    "scenario_id": string,
    "operator_notes": [1 to 3 non-empty natural-language strings],
    "hours": [exactly 24 objects with hour, demand_kwh, solar_kwh, tariff_bdt_per_kwh],
    "battery": {
      "capacity_kwh": number,
      "initial_energy_kwh": number,
      "minimum_energy_kwh": number,
      "max_charge_kwh_per_hour": number,
      "max_discharge_kwh_per_hour": number
    }
  }

  Each hour object:
  {
    "hour": integer (0..23, each integer 0..23 exactly once),
    "demand_kwh": number,
    "solar_kwh": number,
    "tariff_bdt_per_kwh": number
  }

  Battery object:
  {
    "capacity_kwh": number,
    "initial_energy_kwh": number,
    "minimum_energy_kwh": number,
    "max_charge_kwh_per_hour": number,
    "max_discharge_kwh_per_hour": number
  }

Response body (exact schema):
{
  "scenario_id": "...",
  "directive_interpretation": [
    {
      "note_index": integer,
      "applies": boolean,
      "directive_type": one of solar_reduction/minimum_battery_reserve/no_charge_window/no_discharge_window/max_grid_window/no_op,
      "structured_adjustment": object or null,
      "explanation": string
    }
  ],
  "hourly_plan": [
    {
      "hour": 0..23,
      "grid_kwh": number,
      "solar_used_kwh": number,
      "battery_action": "charge" | "discharge" | "idle",
      "battery_kwh": number,
      "battery_energy_after_kwh": number
    }
  ],
  "total_grid_kwh": number,
  "total_cost_bdt": number,
  "peak_grid_kwh": number,
  "plan_summary": "short human-readable explanation"
}

================================================================================
2. SIX DIRECTIVE TYPES
================================================================================

1. solar_reduction
   - structured_adjustment: {"hours": [...], "factor": number}
   - factor = FRACTION REMAINING (not percentage removed)
   - "solar reduced by 80%" -> factor 0.20
   - "solar at 20% of normal" -> factor 0.20
   - "half the normal output" -> factor 0.50

2. minimum_battery_reserve
   - structured_adjustment: {"hours": [...], "minimum_energy_kwh": number}
   - Can be absolute (kWh) or relative (% of capacity)
   - Example: capacity=200, "keep at least 50%" -> minimum_energy_kwh=100

3. no_charge_window
   - structured_adjustment: {"hours": [...]}
   - can_charge[h] = false for those hours

4. no_discharge_window
   - structured_adjustment: {"hours": [...]}
   - can_discharge[h] = false for those hours

5. max_grid_window
   - structured_adjustment: {"hours": [...], "max_grid_kwh": number}
   - G[h] <= max_grid_kwh for those hours

6. no_op
   - structured_adjustment = null
   - applies = false
   - Every other directive: applies = true

================================================================================
3. TIME WINDOW SEMANTICS
================================================================================

- Whole-hour intervals
- START INCLUDED, END EXCLUDED
- 1 PM to 3 PM -> [13, 14]
- 2 AM until 5 AM -> [2, 3, 4]
- 6 PM until 9 PM -> [18, 19, 20]
- 11 AM until 1 PM -> [11, 12]
- Phrases: "from X until Y", "between X and Y", "X-Y", "X to Y", "noon", "midnight", "13:00", etc.
- All hour arrays: integers only, 0..23, unique, ascending

================================================================================
4. LLM REQUIREMENT
================================================================================

- ONE LLM call per request (interpret all 1-3 notes)
- LLM must produce semantic structured interpretation
- Cannot replace with regex/keyword matching only
- System prompt must be strict and deterministic
- Provider abstraction: app/llm/base.py, app/llm/interpreter.py, app/llm/provider.py
- Environment: LLM_API_KEY, LLM_MODEL, LLM_BASE_URL (optional), LLM_TIMEOUT_SECONDS, LLM_MAX_RETRIES
- Never commit API keys to source/Docker/README/logs/history
- Structured output/schema-constrained generation preferred

================================================================================
5. GUARDRAILS (DETERMINISTIC)
================================================================================

Validate ALL LLM output AFTER LLM and BEFORE optimization:

- array length == operator_notes length
- note_index coverage exactly 0..N-1
- ascending note_index, no duplicates
- allowed directive_type only
- applies semantics: no_op => applies=false, adjustment=null; non-no_op => applies=true
- exact keys for each directive
- hour arrays: integer-only, 0..23, sorted, no duplicates
- solar factor: finite, 0 <= factor <= 1
- minimum reserve: finite, >= 0, <= battery capacity
- max grid: finite, >= 0
- no unsupported fields
- no attempt to alter demand/tariff/battery parameters
- Use Pydantic with extra="forbid"

Safe normalization allowed:
- sort hour arrays
- deduplicate valid hour list per official rules
- normalize tiny floating representation artifacts

DO NOT:
- clamp invalid factors
- invent missing hours
- guess numeric values
- turn unknown directive into different one

If model output structurally invalid:
1. at most one controlled repair/retry
2. validate again
3. if still invalid, return controlled safe server/provider failure

================================================================================
6. MATHEMATICAL OPTIMIZER
================================================================================

- Use scipy.optimize.linprog(method="highs") / HiGHS
- Variables per hour h:
  - G[h] = grid import (G >= 0)
  - S[h] = solar used (0 <= S[h] <= effective_solar[h])
  - B[h] = signed battery change (B[h] > 0 = charge, B[h] < 0 = discharge, B[h] = 0 = idle)
- Bounds:
  -max_discharge <= B[h] <= max_charge
  - no_charge: B[h] <= 0
  - no_discharge: B[h] >= 0
  - both: B[h] = 0
- Energy balance: G[h] + S[h] = demand_kwh[h] + B[h]
- Battery state transition:
  - E[0] = initial_energy_kwh + B[0]
  - E[h] = E[h-1] + B[h] for h=1..23
- Battery bounds: minimum_reserve[h] <= E[h] <= capacity_kwh
- End-of-day neutrality: E[23] = initial_energy_kwh
- Grid directive: if max_grid_window active, G[h] <= max_grid_kwh
- Objective: minimize SUM(G[h] * tariff_bdt_per_kwh[h]) for h=0..23

================================================================================
7. REPLAY VALIDATOR
================================================================================

Independent replay of returned plan hour-by-hour verifying:

1. exactly 24 plan rows
2. hours exactly 0..23
3. grid >= 0
4. solar_used >= 0
5. solar_used <= effective_solar
6. battery_action enum valid
7. idle => battery_kwh = 0
8. battery_kwh non-negative
9. charging within max rate
10. discharging within max rate
11. no-charge directives respected
12. no-discharge directives respected
13. state transition exact
14. active reserve respected
15. battery capacity respected
16. grid cap respected
17. energy balance respected
18. no negative/impossible values
19. final battery state == initial battery state
20. all values finite

Energy balance:
  grid_kwh + solar_used_kwh + battery_discharge_kwh = demand_kwh + battery_charge_kwh

If replay fails: do NOT return HTTP 200. Log sanitized error, return controlled failure.

================================================================================
8. NUMERIC HANDLING
================================================================================

- Internal tolerance ~1e-7 (tighter than judge's 0.01)
- Before JSON serialization:
  - eliminate -0.0
  - round to 6 decimal places for stable JSON
  - replay rounded values again if rounding could affect validity
  - recompute totals after canonicalization
- Never round to only two decimals during optimization

================================================================================
9. ERROR HANDLING
================================================================================

Never crash. Handle:
- malformed JSON
- validation errors (400/422)
- LLM timeout / rate limit
- malformed model response
- schema mismatch
- optimizer failure / infeasible
- unexpected internal exceptions

Return structured JSON errors without stack traces, API keys, or sensitive metadata.

================================================================================
10. PERFORMANCE
================================================================================

- Official timeout: 30 seconds
- Target p95 <= 5 seconds
- Strategies:
  - one LLM call per request
  - strict token-limited output
  - no chain-of-thought request
  - small structured prompt
  - fast model
  - connection reuse
  - provider timeout
  - max one repair retry
  - deterministic optimization locally
  - no second LLM call for summary
  - no database
  - no network calls other than configured LLM

================================================================================
11. PROJECT STRUCTURE
================================================================================

gridwise/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── errors.py
│   ├── guardrails.py
│   ├── directives.py
│   ├── optimizer.py
│   ├── validator.py
│   └── summary.py
│   └── llm/
│       ├── __init__.py
│       ├── base.py
│       ├── provider.py
│       ├── interpreter.py
│       └── schemas.py
├── tests/
│   ├── test_health.py
│   ├── test_request_validation.py
│   ├── test_guardrails.py
│   ├── test_directive_application.py
│   ├── test_optimizer.py
│   ├── test_replay_validator.py
│   ├── test_api_failures.py
│   └── test_randomized_optimizer.py
├── scripts/
│   ├── validate_public_samples.py
│   ├── smoke_test.py
│   └── generate_local_test.py
├── docs/
│   ├── spec_notes.md
│   ├── architecture.md
│   └── video_script.md
├── .env.example
├── .gitignore
├── Dockerfile
├── pyproject.toml
├── README.md
└── LICENSE