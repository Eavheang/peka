.PHONY: up down migrate

up:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build
	$(MAKE) migrate

migrate:
	docker compose -f compose.yaml -f compose.dev.yaml exec -T service alembic upgrade head

down:
	docker compose -f compose.yaml -f compose.dev.yaml down
