# CNPJ Due Diligence

A due-diligence platform for Brazilian companies, built exclusively on official public data
sources (Receita Federal, Portal da Transparência, MTE's forced-labor registry). Given a
CNPJ, it shows cadastral data, the corporate ownership graph (shared partners, shared
addresses, ownership chains), cross-references it against government restrictive lists and federal debt, and
computes an explainable 0 to 100 risk score. Dossiers export to PDF. Logged-in users can
monitor a CNPJ on a watchlist, get alerted when something changes, and check up to 50 CNPJs at
once from a pasted list or a CSV (read in the browser; only the CNPJs are sent).

**Live demo**: https://lucianookdp.github.io/cnpj-due-diligence/

Search is CNPJ-only, no lookup by natural-person name (per Brazil's LGPD). People appear only
as company partners, with the same fields Receita Federal already discloses publicly.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, PostgreSQL.
- **Frontend**: React, TypeScript, Vite, Cytoscape.js (graph view).
- **Data sources**: Minha Receita, BrasilAPI, Portal da Transparência.
- **Deploy**: frontend on GitHub Pages, API and database on Railway (Hobby plan).
- **Job queue**: Postgres as the queue (no Redis/Celery).

## Running locally

```bash
cd backend
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Copy `.env.example` to `backend/.env`, set `DATABASE_URL`, then run migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

And the frontend:

```bash
cd frontend
npm install
npm run dev
```

Tests:

```bash
cd backend
pytest
```

Or everything at once via Docker:

```bash
docker compose up --build
```

## Deploy

The API and Postgres database run on Railway, deployed straight from this repo's
`backend/Dockerfile`. The frontend is published to GitHub Pages via GitHub Actions on every
push to `main`. A GitHub Actions cron calls an internal endpoint every 6 hours to run periodic
tasks (refreshing restrictive lists, reprocessing the watchlist), authenticated with a
`WORKER_TRIGGER_SECRET` shared between Railway and a matching GitHub Actions secret.

Federal debt ("dívida ativa da União") comes from PGFN's quarterly open data, about 1.4 GB
zipped. A monthly GitHub Actions job (`pgfn-refresh.yml`) checks whether a new quarter is out,
and only then downloads it on the runner, keeps companies with at least R$ 100,000 being actively
collected (about 670,000 of them, ~70 MB), and uploads that small summary to the API with the same secret. The server never
downloads the raw files, and the table is swapped in one transaction.

## Configuration

See `.env.example` for all environment variables.

## License

All rights reserved. See [LICENSE](LICENSE). This repository is public for portfolio and
demonstration purposes only; it is not licensed for reuse.
