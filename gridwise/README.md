# GridWise — Smart Campus Energy Optimization

> **BUP CSE FEST 2026 Hackathon — Preliminary Round**

GridWise is a deterministic, LLM-assisted smart campus energy optimization service.
It interprets free-text operator notes via an LLM, converts them into strict machine-readable directives, then feeds them into a mathematical linear-programming optimizer to produce a cost-minimized 24-hour energy schedule.

---

## Table of Contents

- [Challenge Understanding](#challenge-understanding)
- [Architecture](#architecture)
- [LLM Role](#llm-role)
- [Deterministic Guardrails](#deterministic-guardrails)
- [Mathematical Optimizer](#mathematical-optimizer)
- [Independent Replay Validator](#independent-replay-validator)
- [Supported Directives](#supported-directives)
- [Requirements](#requirements)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Install](#install)
- [Run](#run)
- [Health Check](#health-check)
- [Optimize Energy](#optimize-energy)
- [Run Tests](#run-tests)
- [Validate Public Samples](#validate-public-samples)
- [Docker](#docker)
- [Model / Provider Configuration](#model--provider-configuration)
- [Dependencies](#dependencies)
- [Known Limitations](#known-limitations)
- [Security Guidance](#security-guidance)
- [Deployment](#deployment)
- [Attribution](#attribution)

---

## Challenge Understanding

Campus energy operators write brief, informal notes such as *"Reduce solar import by 40% from 10am to 2pm"* or *"Keep battery above 50% overnight"*. The challenge is to:

1. **Interpret** those notes into structured, validated directives.
2. **Compile** directives into hard mathematical constraints.
3. **Optimize** the 24-hour schedule to minimize grid import cost while respecting all constraints.
4. **Validate** the result independently before returning it.

---

## Architecture

```
Request ──▶ Pydantic Validation ──▶ LLM Interpreter ──▶ Guardrails ──▶ Directive Compiler
                                                                          │
                                                                          ▼
JSON Response ◀── Totals / Summary ◀── Replay Validator ◀── LP Optimizer (HiGHS)
```

**Key design principle:** The LLM never touches the optimizer directly. Every LLM output is validated by deterministic guardrails before it becomes a constraint.

---

## LLM Role

A single LLM call per request interprets 1–3 operator notes into structured JSON objects. The LLM is instructed to:

- Use only the six supported directive types.
- Never invent demand, tariff, solar forecasts, battery parameters, or unstated time windows.
- Treat unrelated notes as `no_op`.
- Output JSON matching the exact schema.

The LLM output is **never trusted** — it is always validated and potentially repaired by the guardrail layer.

---

## Deterministic Guardrails

After the LLM responds, every interpretation entry is validated:

- Correct directive type (one of six allowed).
- `applies` flag matches type (`no_op` → false; all others → true).
- `structured_adjustment` contains exactly the required keys for the type.
- Hour arrays are sorted, unique, integers in 0..23.
- Solar factor is in [0, 1].
- Minimum reserve does not exceed battery capacity.
- `max_grid_kwh` is non-negative.

Invalid entries are either repaired or rejected with a controlled 422 error.

---

## Mathematical Optimizer

The optimizer uses **scipy.optimize.linprog (HiGHS)** to solve a linear program:

- **Variables:** 72 (3 per hour: grid G[h], solar S[h], signed battery B[h]).
- **Objective:** minimize total grid import cost = Σ G[h] × tariff[h].
- **Equality constraints:**
  - Energy balance per hour: G[h] + S[h] = demand[h] + B[h]
  - End-of-day battery neutrality: Σ B[0..23] = 0
- **Inequality constraints:**
  - 0 ≤ G[h]
  - 0 ≤ S[h] ≤ effective_solar[h]
  - −max_discharge ≤ B[h] ≤ max_charge
  - minimum_reserve[h] ≤ initial_energy + Σ B[0..h] ≤ capacity
  - Directive-specific: no-charge, no-discharge, max-grid windows

---

## Independent Replay Validator

After the optimizer produces a plan, an independent validator replays every hour without calling any optimizer code, checking:

- Grid and solar values are non-negative.
- Solar used ≤ effective solar available.
- Battery action matches kWh sign and idle semantics.
- Energy balance: grid + solar = demand ± battery flow.
- Battery state of charge stays within [minimum, capacity].
- Final SOC = initial SOC (neutrality).
- All values are finite.
- Max grid limits respected.

If replay fails, the endpoint returns 422 instead of 200.

---

## Supported Directives

| Directive | Key Fields | Effect |
|-----------|-----------|--------|
| `solar_reduction` | `hours`, `factor` (fraction remaining) | S[h] ≤ solar_kwh[h] × factor |
| `minimum_battery_reserve` | `hours`, `minimum_energy_kwh` | E[h] ≥ minimum_energy_kwh |
| `no_charge_window` | `hours` | B[h] ≤ 0 (charge forbidden) |
| `no_discharge_window` | `hours` | B[h] ≥ 0 (discharge forbidden) |
| `max_grid_window` | `hours`, `max_grid_kwh` | G[h] ≤ max_grid_kwh |
| `no_op` | none | Note ignored; no constraint change |

---

## Requirements

- Python 3.11+
- Docker (optional, for containerized deployment)
- An OpenAI-compatible LLM API key (OpenAI, Anthropic via compatible endpoint, etc.)

---

## Local Setup

```bash
git clone https://github.com/Emon0036/bup_priliminary.git
cd bup_priliminary/gridwise
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_API_KEY` | Yes | — | API key for the LLM provider |
| `LLM_MODEL` | Yes | — | Model identifier (e.g. `gpt-4o-mini`) |
| `LLM_BASE_URL` | No | `https://api.openai.com/v1` | OpenAI-compatible base URL |
| `LLM_TIMEOUT_SECONDS` | No | `30` | Request timeout |
| `LLM_MAX_RETRIES` | No | `2` | Max retries on transient failure |

---

## Install

```bash
pip install -r requirements.txt
```

Or with pyproject.toml:

```bash
pip install -e .
```

---

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok"}
```

---

## Optimize Energy

```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "test-001",
    "operator_notes": ["Reduce solar import by 40% from 10am to 2pm"],
    "hours": [
      {"hour": 0, "demand_kwh": 50.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 1, "demand_kwh": 45.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 2, "demand_kwh": 40.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 3, "demand_kwh": 35.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 4, "demand_kwh": 30.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 5, "demand_kwh": 35.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 6, "demand_kwh": 50.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 6.0},
      {"hour": 7, "demand_kwh": 60.0, "solar_kwh": 15.0, "tariff_bdt_per_kwh": 7.0},
      {"hour": 8, "demand_kwh": 70.0, "solar_kwh": 30.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 9, "demand_kwh": 80.0, "solar_kwh": 45.0, "tariff_bdt_per_kwh": 9.0},
      {"hour": 10, "demand_kwh": 85.0, "solar_kwh": 55.0, "tariff_bdt_per_kwh": 10.0},
      {"hour": 11, "demand_kwh": 90.0, "solar_kwh": 60.0, "tariff_bdt_per_kwh": 10.0},
      {"hour": 12, "demand_kwh": 85.0, "solar_kwh": 55.0, "tariff_bdt_per_kwh": 10.0},
      {"hour": 13, "demand_kwh": 80.0, "solar_kwh": 45.0, "tariff_bdt_per_kwh": 9.0},
      {"hour": 14, "demand_kwh": 75.0, "solar_kwh": 35.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 15, "demand_kwh": 70.0, "solar_kwh": 25.0, "tariff_bdt_per_kwh": 7.0},
      {"hour": 16, "demand_kwh": 65.0, "solar_kwh": 15.0, "tariff_bdt_per_kwh": 6.0},
      {"hour": 17, "demand_kwh": 60.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 6.0},
      {"hour": 18, "demand_kwh": 55.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 6.0},
      {"hour": 19, "demand_kwh": 50.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 20, "demand_kwh": 55.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 21, "demand_kwh": 60.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 22, "demand_kwh": 55.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0},
      {"hour": 23, "demand_kwh": 50.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0}
    ],
    "battery": {
      "capacity_kwh": 200.0,
      "initial_energy_kwh": 100.0,
      "minimum_energy_kwh": 20.0,
      "max_charge_kwh_per_hour": 50.0,
      "max_discharge_kwh_per_hour": 50.0
    }
  }'
```

---

## Run Tests

```bash
python -m pytest gridwise/tests/ -v
```

---

## Validate Public Samples

```bash
python gridwise/scripts/validate_public_samples.py
```

---

## Docker

### Build

```bash
docker build -t gridwise:local -f gridwise/Dockerfile .
```

### Run

```bash
docker run --rm \
  -p 8000:8000 \
  -e LLM_API_KEY="your-key-here" \
  -e LLM_MODEL="gpt-4o-mini" \
  gridwise:local
```

### Verify

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## Model / Provider Configuration

GridWise supports any OpenAI-compatible API. Set `LLM_BASE_URL` to your provider's endpoint:

| Provider | `LLM_MODEL` | `LLM_BASE_URL` |
|----------|-------------|-----------------|
| OpenAI | `gpt-4o-mini` | `https://api.openai.com/v1` |
| Anthropic (compatible) | `claude-3-haiku` | Your compatible proxy URL |
| Local | `llama-3` | `http://localhost:11434/v1` |

---

## Dependencies

- `fastapi` — web framework
- `pydantic` — request/response validation
- `scipy` — LP optimization (HiGHS solver)
- `uvicorn` — ASGI server
- `httpx` — LLM API client
- `python-dotenv` — environment variable loading

---

## Known Limitations

- **LLM dependency:** Without a valid `LLM_API_KEY`, all operator notes are treated as `no_op`.
- **Single LLM call:** Only one call per request; no chain-of-thought or multi-step reasoning.
- **No persistent state:** Each request is independent; no cross-request learning.
- **Tariff must be > 0:** The model requires positive tariff values (spec allows zero in theory).
- **Deterministic guardrails:** Strict validation may reject creative but valid LLM interpretations.

---

## Security Guidance

- **Never commit `.env` files** containing API keys.
- Use environment variables or Docker secrets for all credentials.
- The API key is never logged or included in responses.
- LLM errors are sanitized; stack traces are not exposed to clients.
- The container runs as a non-root user.

---

## Deployment

1. Build the Docker image.
2. Set environment variables (`LLM_API_KEY`, `LLM_MODEL`, etc.).
3. Run the container on port 8000.
4. Verify with `GET /health`.
5. Submit requests to `POST /optimize-energy`.

The judge timeout is 30 seconds; target p95 latency is ≤ 5 seconds.

---

## Attribution

- **FastAPI** —tiangolo / FastAPI team
- **Pydantic** — Samuel Colvin / pydantic team
- **SciPy / HiGHS** — SciPy developers
- **uvicorn** — Encode OSS
- **httpx** — Encode OSS
- Built with AI coding assistance (Claude, GPT-4)
