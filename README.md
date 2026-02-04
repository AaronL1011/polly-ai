# Demócrata

Demócrata is a political, social and government data ingestion engine that provides file-based RAG with a non-partisan, simple and accessible research portal.

![democrata-landing-page](https://github.com/user-attachments/assets/3a456ee2-55cf-4ef8-ad6f-fb61a606132c)
![democrata-query-result-page](https://github.com/user-attachments/assets/7a8f039e-f9a3-4425-b642-f1607e0d5c1e)


See [SPEC.md](SPEC.md) for the full spec.

**Documentation:** [SPEC.md](SPEC.md) (product spec) · [docs/](docs/) — [Architecture](docs/ARCHITECTURE.md), [Schemas](docs/SCHEMAS.md), [Data models](docs/DATA_MODELS.md), [Implementation](docs/IMPLEMENTATION.md), [Cost model](docs/COST_MODEL.md)

## Prerequisites

- **Python 3.12+** and [uv](https://docs.astral.sh/uv/)
- **Node.js** and [pnpm](https://pnpm.io/) (e.g. `corepack enable && corepack prepare pnpm@latest --activate`)

## Monorepo layout

- `server/` — Python FastAPI + gRPC app (uv, `pyproject.toml`)
- `frontend/` — Svelte + Vite app (pnpm workspace)

## Quick start

```bash
make install    # uv sync (server) + pnpm install (frontend)
make server     # Run API server (http://127.0.0.1:8000)
make frontend   # Run frontend dev server (separate terminal)
make test       # Run server tests
make lint       # Lint server (ruff)
```

## Makefile targets

| Target      | Description                    |
|------------|--------------------------------|
| `install`  | Install server + frontend deps |
| `server`   | Run FastAPI server             |
| `frontend` | Run Svelte dev server          |
| `dev`      | Run server and frontend (-j2)  |
| `test`     | Run server tests               |
| `lint`     | Ruff check + format check      |
| `lint-fix` | Ruff fix + format              |
| `clean`    | Remove .venv, node_modules, dist |
