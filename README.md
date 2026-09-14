# 🏙️ AI Laboratory | EcoSim

[![GitHub](https://img.shields.io/badge/GitHub-Emon0036-E8ECF1?style=for-the-badge&logo=github)](https://github.com/Emon0036)
[![License](https://img.shields.io/badge/License-Unknown-555?style=for-the-badge)](#)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white)](#)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](#)
[![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](#)
[![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](#)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white)](#)

**An educational, agent-based urban economy simulator.** Explore how household finances, employment, and synthetic financial stress respond to controlled economic scenarios.

The project combines a Next.js dashboard (branded UrbanLab), a Python FastAPI service (EcoSim), and persistent MySQL/TiDB storage. It demonstrates constraint satisfaction, A* search, and logistic regression through a reproducible 500-agent simulation, not a forecast of a real city.

**Project and team owner:** [Emon0036](https://github.com/Emon0036). No additional team identities or affiliations are asserted.

## What You Can Explore

- **Overview:** current population metrics, monthly history, and an interactive city map.
- **Simulation:** create seeded runs, schedule economic interventions, and advance 1-24 months per request. Creating a new run preserves earlier experiments.
- **Agents:** search and filter residents, inspect household finances, decisions, and recorded monthly histories.
- **Analytics:** compare baseline and current outcomes, income distributions, risk distributions, and trends.
- **Methodology:** inspect algorithm explanations and evaluation metadata from the packaged risk-model artifact.

All residents and training labels are synthetic. Financial amounts use synthetic currency units; the dashboard's `$` symbol does not imply real-world calibration. This project is not suitable for lending, benefits eligibility, personal financial advice, or policy decisions.

## Architecture

```mermaid
flowchart LR
    Browser[Browser: UrbanLab dashboard] --> Next[Next.js / React]
    Next -->|same-origin /api requests| API[FastAPI: api/main.py]
    API --> Engine[Monthly simulation]
    Engine --> CSP[CSP job allocation]
    Engine --> AStar[A* city routing]
    Engine --> Risk[JSON logistic risk inference]
    API --> ORM[SQLAlchemy / PyMySQL]
    Engine --> ORM
    ORM -->|verified TLS| DB[(TiDB / MySQL)]
    Training[Offline synthetic training: 80/20 split] --> Artifact[risk_model.json]
    Artifact --> Risk
    Artifact --> API
```

In development, Next.js proxies `/api/*` to `127.0.0.1:8000`. The Vercel deployment target serves Next.js and routes API requests to the Python entrypoint `api/index.py`; see the deployment checklist before publishing.

**No database means no live simulation data.** The API reports degraded health and database-backed routes return unavailable errors. There is no production SQLite, in-memory, JSON, or browser-generated data fallback. Offline calibration and explicitly injected SQLite test fixtures are separate from production storage.

## Requirements

- Python **3.12** with pip and virtual-environment support.
- Node.js **22 LTS** and npm; install frontend dependencies using the committed lockfile.
- A reachable TiDB or MySQL database, database credentials, and permission to create the initial schema.
- Trusted CA certificates for verified TLS. A private CA may require `DB_SSL_CA`.

Run commands from the repository root. Do not put database credentials in a `NEXT_PUBLIC_*` variable.

## Local Setup

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
Copy-Item .env.example .env
```

Using the virtual environment's executable directly avoids changing PowerShell execution policy. Edit `.env` with your actual database connection before continuing; the example credentials are deliberately nonfunctional.

```powershell
.\.venv\Scripts\python.exe scripts/init_db.py
.\.venv\Scripts\python.exe scripts/seed_db.py
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal at the repository root:

```powershell
npm run dev
```

### Linux

Install Python 3.12 and its venv support using your distribution's packages, then:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm ci
cp .env.example .env
```

Edit `.env` with your actual database connection, then:

```bash
python scripts/init_db.py
python scripts/seed_db.py
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal at the repository root, run `npm run dev`.

Open the dashboard at <http://localhost:3000>, API documentation at <http://127.0.0.1:8000/docs>, and health status at <http://localhost:3000/api/health>. A connected health response confirms connectivity only, not that the schema is initialized or a run exists.

### Database and TLS

1. Create an empty database in your TiDB/MySQL service and obtain its host, port, username, and password.
2. Set `DATABASE_URL` to `mysql+pymysql://USERNAME:PASSWORD@HOST:4000/DATABASE`, using the provider's actual port (often `4000` for TiDB and `3306` for MySQL). Percent-encode reserved characters in credentials.
3. Keep `DB_REQUIRE_TLS=true`. Omit `DB_SSL_CA` to use the system trust store, or set it to a readable PEM CA-bundle path. Never disable certificate verification to work around a certificate error.
4. Do not add URL query parameters: the backend rejects them so they cannot override TLS and timeout settings.
5. Run initialization and seeding once from a trusted administrative environment. Initialization creates missing tables without dropping data; it is not a schema migration system. Seeding creates the seed-42 baseline only when there is no current run.

For a deliberately isolated local MySQL instance without TLS, `DB_REQUIRE_TLS=false` is an explicit development-only opt-out. Never use it for TiDB Cloud or a remote production database.

### Configuration

The Python settings loader reads the root `.env`; environment variables take precedence. It does not automatically read Next.js's `.env.local`. Restart running services after changes.

| Variable | Default / Example | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Unset | Required for live MySQL/TiDB persistence; no fallback when absent. |
| `DB_REQUIRE_TLS` | `true` | Require TLS with certificate and hostname verification. |
| `DB_SSL_CA` | Unset | Optional CA-bundle path; omit rather than set to an empty path. |
| `DB_CONNECT_TIMEOUT` | `10` | Connection timeout in seconds, from 1 to 60. |
| `MAX_RUNS` | `100` | Database registry run limit, from 1 to 10000. |
| `MAX_SIMULATION_MONTHS` | `120` | Maximum run horizon, from 1 to 1200; per-request limit remains 24. |
| `CORS_ORIGINS` | Localhost ports 5173 and 3000 | JSON array of allowed browser origins for direct API access. Same-origin deployment needs no cross-origin proxy setting. |
| `NEXT_PUBLIC_APP_NAME` | `AI Laboratory` in example | Optional public branding value reserved for frontend use. The inspected frontend currently uses static UrbanLab branding; setting this alone does not rename it. |

## Verification

With the virtual environment active (`.\.venv\Scripts\Activate.ps1` on Windows, if permitted, or `source .venv/bin/activate` on Linux):

```bash
python -m pytest
npm run lint
npx tsc --noEmit
npm run build
```

On Windows, `.\.venv\Scripts\python.exe -m pytest` also works without activation. The Python suite covers routing, job constraints, metrics, API validation, financial conservation, history, transactions, unavailable-database behavior, and model reproducibility. SQLite is explicitly injected for isolated tests; these tests do not prove TiDB connectivity, TLS handshakes, or production concurrency behavior.

Test counts change as development continues. Run the suite for the current result; this documentation does not assert a passing count, a successful build, or a completed deployment. No live database or deployed smoke test was verified as part of this documentation update.

For offline model and scenario reproduction:

```bash
python scripts/train_model.py --help
python scripts/train_model.py
python scripts/calibrate.py --help
python scripts/calibrate.py
```

Training writes `backend/artifacts/risk_model.json`; calibration writes `data/calibration.json`. These commands regenerate versioned evidence, so review their diffs. The training workflow uses a stratified **80% training / 20% held-out test split**; confirm the regenerated artifact metadata reflects this before reporting scores. Configurable calibration is being integrated: consult `--help` for the options available in your checkout instead of assuming flags. Neither script needs a live database, and neither runs inside an API request.

## Repository Guide

| Path | Responsibility |
| --- | --- |
| `app/`, `components/`, `lib/` | Next.js pages, dashboard UI, typed same-origin API client. |
| `api/main.py`, `api/schemas.py` | FastAPI application, routes, and request validation. |
| `api/index.py` | Vercel Python entrypoint being integrated for deployment. |
| `backend/` | Simulation, CSP, A*, risk inference, settings, persistence, and initialization. |
| `backend/artifacts/risk_model.json` | Packaged inference coefficients, evaluation, and provenance. |
| `scripts/` | Explicit database initialization/seeding and offline training/calibration. |
| `data/` | Synthetic scenario evidence, not production run storage. |
| `tests/` | Algorithm, API, persistence, and model tests. |
| `docs/` | Detailed design, methods, dataset, and deployment guidance. |

## 🏷️ Topics

> Add these topics to your GitHub repository settings to help others discover EcoSim:
> `simulation` `agent-based-modeling` `urban-economy` `python` `typescript` `next.js` `fastapi` `machine-learning` `csp` `a-star` `optimization` `financial-simulation` `educational`

## Documentation

- [Architecture](docs/ARCHITECTURE.md): boundaries, persistence model, request lifecycle, and API map.
- [AI Methods](docs/AI_METHODS.md): CSP, A*, logistic regression, economic rules, and evaluation limits.
- [Dataset](docs/DATASET.md): synthetic provenance, features, labels, split, artifacts, and reproducibility.
- [Deployment](docs/DEPLOYMENT.md): Vercel Next.js + Python setup, TiDB TLS, security, and smoke checks.

## Limitations and Ownership

The city layout, wages, household distributions, benefits, job capacities, and behavioral rules are hand-designed. Agents do not learn policies or negotiate prices. Classifier labels are generated from a known synthetic formula, so held-out accuracy measures recovery of that formula rather than real-world validity. Paired scenario checks test sensitivity, not empirical economic calibration or causal identification.

The API has no application-level authentication or per-user isolation. The default current run is shared. Protect any hosted instance before exposing mutation endpoints, and use separate databases for development, previews, and production.

Project decisions, attribution, and release readiness belong to **Emon0036**. Add contributors only with verified attribution. No license grant is asserted here; confirm licensing with the owner before redistribution.
