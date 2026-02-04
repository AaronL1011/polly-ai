# Demócrata Server

Python FastAPI + gRPC server. See [SPEC.md](../SPEC.md) for the project spec.

## Setup

From repo root:

```bash
make install
```

Or with uv directly:

```bash
cd server && uv sync
```

## Run

```bash
make server
# or: cd server && uv run uvicorn polly_pipeline_server.main:app --reload
```

## Tests

```bash
make test
# or: cd server && uv run pytest
```
