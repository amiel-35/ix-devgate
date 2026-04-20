.PHONY: dev build stop db migrate seed test test-api test-web lint fmt

# ── Dev ──────────────────────────────────────────────────────────
dev:
	docker compose up

stop:
	docker compose down

# ── DB ───────────────────────────────────────────────────────────
db:
	docker compose up db -d

migrate:
	docker compose run --rm api alembic upgrade head

migrate-down:
	docker compose run --rm api alembic downgrade -1

seed:
	docker compose run --rm api python -m app.migrations.seed

# ── API ──────────────────────────────────────────────────────────
api-dev:
	cd apps/api && uvicorn app.main:app --reload --port 8000

api-install:
	cd apps/api && pip install -r requirements.txt

test-api:
	cd apps/api && pytest tests/ -v

lint-api:
	cd apps/api && ruff check app/ && mypy app/

fmt-api:
	cd apps/api && ruff format app/

# ── Web ──────────────────────────────────────────────────────────
web-dev:
	cd apps/web && npm run dev

web-install:
	cd apps/web && npm install

web-build:
	cd apps/web && npm run build

test-web:
	cd apps/web && npm run test

lint-web:
	cd apps/web && npm run lint

# ── All ──────────────────────────────────────────────────────────
install: api-install web-install

test: test-api test-web

lint: lint-api lint-web
