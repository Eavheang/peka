.PHONY: up down migrate

up:
	@if not exist ".env" copy /Y ".env.example" ".env"
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build
	$(MAKE) migrate

migrate:
	docker compose -f compose.yaml -f compose.dev.yaml exec -T service alembic upgrade head

down:
	docker compose -f compose.yaml -f compose.dev.yaml down
