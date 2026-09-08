# Architecture

Next.js App Router renders the dashboard and calls same-origin `/api` endpoints. Vercel routes those endpoints to FastAPI in `api/index.py`. FastAPI uses transparent simulation algorithms and SQLAlchemy models designed for TiDB/MySQL persistence. Each bounded request advances monthly states; no background process is required.
