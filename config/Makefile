.PHONY: setup up down migrate

setup:
	@if not exist ".env" copy /Y ".env.example" ".env"
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build postgres pgadmin service llama embeddings okf-worker
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient bun install --frozen-lockfile
	docker compose -f compose.yaml -f compose.dev.yaml up -d webclient
	$(MAKE) migrate

up:
	docker compose -f compose.yaml -f compose.dev.yaml up -d

migrate:
	docker compose -f compose.yaml -f compose.dev.yaml exec -T service alembic upgrade head

down:
	docker compose -f compose.yaml -f compose.dev.yaml down
