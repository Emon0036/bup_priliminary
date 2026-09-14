# 🐍 EcoSim Backend

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](#)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-46AAE6?style=for-the-badge&logo=sqlalchemy&logoColor=white)](#)
[![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](#)
[![TiDB](https://img.shields.io/badge/TiDB-0066CC?style=for-the-badge&logo=tidb&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-Unknown-555?style=for-the-badge)](#)

Python 3.12, FastAPI, SQLAlchemy 2 and MySQL/TiDB. All households, labels and
currency amounts are synthetic. This is not an empirically validated economic
forecast, a credit model, or a tool for making decisions about real people.

## Run

From the repository root in PowerShell:

```powershell
py -3.12 -m pip install -r requirements.txt
$env:DATABASE_URL = 'mysql+pymysql://USER:PASSWORD@HOST:4000/ecosim'
$env:DB_SSL_CA = 'C:\certificates\ca.pem'
py -3.12 scripts/init_db.py
py -3.12 scripts/seed_db.py
py -3.12 -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The database must already exist. URL-encode special characters in credentials.
TLS is enabled by default with certificate and hostname verification; omit
`DB_SSL_CA` to use the operating system trust store. For an explicitly local,
non-TLS MySQL server only, set `DB_REQUIRE_TLS=false`. URL query options are
rejected so they cannot disable certificate verification. Connections use
`NullPool`, a 10-second connection timeout, and bounded read/write timeouts.
`DATABASE_URL` and settings may also be provided by a root `.env` file.

Initialization is additive (`create_all`), not a migration or reset operation.
Seeding is idempotent and preserves the existing current run. Neither script
drops tables, deletes history, or silently replaces a population. Schema
upgrades from the initial schema require `py -3.12 scripts/migrate_db.py` before
deploying this revision. Stop API writers and take a backup first. This additive,
idempotent MySQL/TiDB migration inserts missing catalog jobs, snapshots the old
hardcoded calibration for existing runs, and adds the job foreign key. It refuses
unknown historical job IDs rather than deleting or rewriting them. MySQL DDL
is not transactionally atomic; rerun after resolving a failure. Fresh databases
only need initialization and seed. `create_all` does not upgrade existing tables.

Production never falls back to SQLite. Without a database, data endpoints return
503; `/health`, `/model/metrics`, and `/pathfinding` still work. `/health` returns
HTTP 200 with `status=degraded` and database `unconfigured` or `unavailable`.
Missing initialized runs return 404 with an instruction to create one.

## Frontend Contract

All required routes exist under `/api` and identically without that prefix.
OpenAPI is at `/docs`. Success responses have the requested shapes; POSTs return
200. Errors have `detail`, with validation errors returning 422 and conflicts
409. No raw database messages or stack traces are returned.

- `GET /dashboard`, `GET /simulation/current`: run, metrics, history, events, csp_stats.
- `POST /simulation/create`: optional name, seed (default 42); new 500-agent run.
- `POST /simulation/run`: simulation_run_id and months (1-24).
- `GET /agents`: page, limit (1-500), search, occupation, skill, employment, risk.
- `GET /agents/{id}`: flattened profile, flattened latest_state, monthly state history.
- `POST /events`: simulation_run_id, event_type, magnitude, duration_months, optional start_month, target, description.
- `GET /events`: items array.
- `POST /pathfinding`: integer start and goal coordinate pairs; path, cost, explored.
- `GET /analytics`: history, income_distribution, risk_distribution, before, after, events.
- `GET /model/metrics`: accuracy, precision, recall, f1, confusion_matrix, feature_names, metadata; also ROC AUC, Brier score and calibration curve.
- `GET /city`: fixed grid, named entrances, 500 current agent positions.
- `GET /simulation/runs`: bounded paginated run list for revisiting preserved runs.

All run-scoped GETs accept optional `simulation_run_id`, except agent detail,
whose globally unique ID determines its run. The default is the most recently
created run, not the most recently advanced historical run. Read requests lock
the run as well, so dashboards cannot mix months during concurrent advancement.

Canonical event types are `food`, `inflation`, `tax`, `job`, `salary`. Magnitude
is a signed percentage change (-90 through 300); `tax` is an additive change in
percentage points to the baseline 12% tax. A `job` event of -30 removes 30% of
job capacity; +30 adds 30%. Food and inflation affect expenses, salary affects
employed gross pay, and unemployed households receive 600 untaxed support.
Targets are `ALL`, `Retail`, `Manufacturing`, `Services`, `Technology`,
`Healthcare`, or `Education` (input case insensitive). Events are active for
`start_month <= month < start_month + duration_months`; default start is next
month. They are temporary level changes, not cumulatively compounded monthly
rates. Overlapping events multiply, taxes add; combined factors are capped at
20 and taxes at 80%. Historical months are never retroactively modified.

Skills are `low`, `medium`, `high`; employment is `employed` or `unemployed`;
risk is `stable` or `at_risk`. These are also the accepted filter values.
Filters accept uppercase frontend values as well. Frontend event inputs
`FOOD_PRICE_SHOCK`, `GENERAL_INFLATION`, `TAX_CHANGE`, and `SALARY_CHANGE` map
to the corresponding canonical type. `JOB_SHORTAGE` is stored as `job_shortage`
and accepts a positive 0-100 capacity reduction, so 15 removes 15% of jobs.
Event duration accepts 1-120 months (within the run horizon); descriptions
accept up to 1,000 characters. Event responses use normalized lowercase types.
Occupation strings are title case. Population is a count; rate and percentage
metrics are 0-100; Gini and risk_probability are 0-1. Average income is net
income; disposable income is net income minus total expenses. Analytics
`before` is month 0 and `after` is the latest month, including when there are
multiple events. Month 0 records initial balances without accrual.

## Algorithms And Limits

Every run has 500 deterministically seeded agents with walkable homes. Random
streams do not use database IDs or global random state; splitting a run request
into smaller requests gives identical results. The four-neighbor A* uses a
Manhattan heuristic, a heap frontier, g-scores, and path reconstruction. Grid
indexing is `grid[y][x]`; blocked endpoints produce 422; unreachable goals return
an empty path, null cost, and the actual explored count.

Jobs are assigned by a real bounded backtracking CSP with dynamic MRV, remaining
capacity checks, skill/occupation/commute constraints, and best partial result.
It explores at most 1,500 nodes per month and does not claim optimal matching.
Unassigned agents remain unemployed. The reported constraints_checked counts
domain checks, not search nodes. Job IDs identify deterministic job categories,
backed by actual rows in the relational `jobs` table. Each non-null state job_id
has a database-enforced foreign key to that table; deletion of referenced jobs
is restricted. A row describes a shared job offer with multiple vacancies, not
a single employee's seat. The solver reads occupation, skill, salary, location,
and baseline capacity from these rows, then derives temporary capacity changes
from events. Initialization inserts missing jobs without overwriting existing
ones. Treat the catalog as immutable once runs exist; no catalog mutation API
is exposed. Test SQLite connections enable foreign-key enforcement explicitly.
A* determines commute costs and walkable movement toward financial destinations.
Surpluses repay debt before accumulating savings; deficits consume savings
before adding debt. Money is rounded to two decimal places.

Mutuation transactions use `SELECT ... FOR UPDATE` on the run with MySQL
`READ COMMITTED` isolation to avoid stale snapshots after waiting for a lock.
Dependency cleanup commits before HTTP success is sent. Creation and seed
use a singleton registry lock, bounding simultaneous creation. A whole multi-
month advance is committed atomically or rolled back. Unique monthly snapshot
and agent-state constraints provide additional protection. Defaults cap stored
data at 100 runs, 120 months per run, and 100 events per run; configure `MAX_RUNS`
and `MAX_SIMULATION_MONTHS` explicitly if needed. No automatic pruning exists.
Two successful simultaneous advance calls each advance by their requested
months; requests are serialized, not deduplicated. Do not blindly retry POSTs.

## Training And Calibration

```powershell
py -3.12 -m pip install -r requirements-dev.txt
py -3.12 scripts/train_model.py
py -3.12 scripts/calibrate.py
py -3.12 -m pytest
```

Training generates 20,000 deterministic synthetic examples, uses a stratified
80/20 train/test split with `random_state=42` (16,000 training, 4,000 test),
fits StandardScaler on training data only, and trains
scikit-learn logistic regression. Exported JSON folds scaling into coefficients
and verifies parity with sklearn predictions. The API only uses this artifact
and standard-library sigmoid inference; it does not import sklearn or train
during requests. Restart workers after replacing an artifact. Metrics are on
the held-out synthetic test set, not on seed agents or real observations.

`backend/artifacts/risk_model.json` contains coefficients, feature definitions,
test metrics, a calibration curve, and provenance.

`data/calibration.json` is editable generator INPUT, not a sensitivity report.
It includes an explicit synthetic disclaimer, age range, occupation/skill/family
size/goal sampling weights, goal amounts, initial savings range, and household
expense, tax, and support assumptions. Weights need not sum to 1 but must be
finite, nonnegative, and have positive total mass. Population remains exactly
500; supported occupations, skill levels, and family sizes preserve the API and
model feature domain. Invalid inputs fail run creation safely with 503.

Edit that JSON or set server-only `ECOSIM_CALIBRATION_PATH` to another validated
file. Each new run snapshots all calibration inputs in `simulation_runs.calibration`;
later file edits affect new runs only, never existing runs or their future steps.
The generator uses those distributions and the simulator uses the snapshotted
household assumptions. These are adjustable synthetic assumptions, not measured
demographics. The offline classifier has its own labeled synthetic training
distribution; modifying population calibration does not retrain it automatically.

`data/sensitivity_report.json` records paired baseline and five event scenarios,
seed 42, 500 agents, three months, plus the exact calibration used. Run
`scripts/calibrate.py --calibration PATH --output PATH` for alternate inputs and
reports. Output cannot overwrite the input file. Sensitivity runs fully in memory
without a database; directional checks demonstrate behavior, not realism.

## Vercel Runtime

`api/index.py` exports the same ASGI `app` as `api/main` for Vercel's Python
runtime. Deployment routing must send API paths to this entry point; this change
does not alter the frontend or its routing configuration. Include `backend/`,
`api/`, the packaged `data/calibration.json`, and the risk JSON artifact. Set DB
and TLS variables in the server environment. Initialize/migrate/seed explicitly
outside request handling; the serverless function never initializes the schema.

`requirements.txt` contains runtime dependencies only. NumPy, SciPy, sklearn,
pytest and httpx live in `requirements-dev.txt`, which also installs runtime
requirements. Inference uses standard-library JSON and sigmoid math, with no
scientific Python dependency. Configure the deployment to install runtime
requirements only. Long multi-month requests still need a sufficient platform
execution timeout; no background queue or new authentication contract is added.

Tests use explicitly injected isolated SQLite databases only and never read
production database settings. They exercise algorithm correctness, model
export, validation, transactions, idempotent seed, persistence, and API shock
integration. Actual MySQL/TiDB TLS and concurrent row-lock behavior must also
be verified in a deployment environment; SQLite cannot validate those locks.

The service is intended for local educational use. Place it behind authentication
and request rate limits before public deployment. CORS defaults to localhost
ports 5173 and 3000; configure `CORS_ORIGINS` as a JSON array if necessary.
