.PHONY: setup up down migrate llm llm-down prod-up prod-down

setup:
	@test -f .env || cp .env.example .env
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build postgres pgadmin embeddings reranker
	$(MAKE) migrate
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build service okf-worker
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient bun install --frozen-lockfile
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient rm -rf .next
	docker compose -f compose.yaml -f compose.dev.yaml up -d webclient proxy

up:
	docker compose -f compose.yaml -f compose.dev.yaml stop webclient
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient rm -rf .next
	docker compose -f compose.yaml -f compose.dev.yaml up -d

migrate:
	docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres
	docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps service alembic upgrade head

down:
	docker compose -f compose.yaml -f compose.dev.yaml down

prod-up:
	@test -f .env || cp .env.example .env
	docker compose -f compose.yaml up -d --build

prod-down:
	docker compose -f compose.yaml down

llm:
	docker compose -f compose.yaml --profile llama up -d llama

llm-down:
	docker compose -f compose.yaml --profile llama stop llama
