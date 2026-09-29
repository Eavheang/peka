.PHONY: setup up down migrate

setup:
	@test -f .env || cp .env.example .env
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build postgres pgadmin service embeddings okf-worker
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient bun install --frozen-lockfile
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient rm -rf .next
	docker compose -f compose.yaml -f compose.dev.yaml up -d webclient proxy
	$(MAKE) migrate

up:
	docker compose -f compose.yaml -f compose.dev.yaml stop webclient
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient rm -rf .next
	docker compose -f compose.yaml -f compose.dev.yaml up -d

migrate:
	docker compose -f compose.yaml -f compose.dev.yaml exec -T service alembic upgrade head

down:
	docker compose -f compose.yaml -f compose.dev.yaml down
