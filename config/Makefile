.PHONY: help setup up down migrate llm llm-down prod-up prod-down

help:
	@echo "PEKA commands. Run them from config/."
	@echo ""
	@echo "First time, in this order:"
	@echo "  make setup      Create .env if missing, build images, install dependencies, run migrations"
	@echo "  make llm        Start the local model (needs the GPU and the model file)"
	@echo "  make up         Start the stack with hot reload"
	@echo ""
	@echo "Every day:"
	@echo "  make llm        Start the local model"
	@echo "  make up         Start the stack with hot reload"
	@echo "  make down       Stop the stack"
	@echo "  make llm-down   Stop the local model"
	@echo ""
	@echo "When needed:"
	@echo "  make setup      Rerun after Dockerfile or lockfile changes"
	@echo "  make migrate    Apply pending database migrations"
	@echo "  make prod-up    Start the stack from built images, no hot reload"
	@echo "  make prod-down  Stop the prod-style stack"

setup:
	@test -f .env || cp .env.example .env
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build postgres pgadmin embeddings reranker
	$(MAKE) migrate
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build service index-worker
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
	docker compose -f compose.yaml --profile llama rm -sf llama
