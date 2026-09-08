# Deployment

Create a free TiDB Cloud Starter database and set `DATABASE_URL` in local and Vercel environment settings. Run `python scripts/init_db.py` then `python scripts/seed_db.py`. Deploy the repository with Vercel; the rewrite sends `/api/*` to `api/index.py`. Use a TLS TiDB URL and never commit it.
