.PHONY: install server frontend dev test lint lint-fix clean proto-gen proto-lint infra-up infra-down

# Install all dependencies (Python with uv, frontend with pnpm)
install:
	cd server && uv sync --extra dev
	pnpm install

# Run the API server (FastAPI)
server:
	cd server && uv run uvicorn democrata_server.main:app --reload

# Run the frontend dev server (Svelte + Vite)
frontend:
	pnpm --filter frontend dev

# Run server and frontend in parallel
dev:
	$(MAKE) -j2 server frontend

# Run tests
test:
	cd server && uv run pytest

# Lint
lint:
	cd server && uv run ruff check src
	cd server && uv run ruff format --check src

# Fix lint (format + auto-fix)
lint-fix:
	cd server && uv run ruff check src --fix
	cd server && uv run ruff format src

# Proto generation (requires buf CLI: https://buf.build/docs/installation)
proto-gen:
	buf generate proto

# Proto linting
proto-lint:
	buf lint proto

# Start infrastructure (Redis, Qdrant)
infra-up:
	docker compose up -d

# Stop infrastructure
infra-down:
	docker compose down

# Remove generated/cached artifacts
clean:
	rm -rf server/.venv
	rm -rf node_modules frontend/node_modules
	rm -rf frontend/dist
	rm -rf server/src/democrata_server/gen
	rm -rf frontend/src/gen
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
