.PHONY: help setup up down migrate llm llm-down prod-up prod-down check-env

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
	@echo "  pgAdmin:        docker compose -f compose.yaml -f compose.dev.yaml --profile pgadmin up -d pgadmin"

.env:
	cp .env.example $@
	sed -i -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$$(openssl rand -hex 24)/" -e "s/^PGADMIN_DEFAULT_PASSWORD=.*/PGADMIN_DEFAULT_PASSWORD=$$(openssl rand -hex 24)/" $@

check-env:
	@test -f .env || { echo "Missing config/.env. Run make setup."; exit 1; }
	@if grep -qE '^(POSTGRES_PASSWORD|PGADMIN_DEFAULT_PASSWORD)=["'\'']?(peka_dev_password|peka_admin_password)?["'\'']?$$' .env; then \
		echo "config/.env has an empty password or a removed default. See docs/getting-started.md (Existing install)."; \
		exit 1; \
	fi

setup: .env check-env
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build postgres embeddings reranker
	$(MAKE) migrate
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build service index-worker
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient bun install --frozen-lockfile
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient rm -rf .next
	docker compose -f compose.yaml -f compose.dev.yaml up -d webclient proxy

up: check-env
	docker compose -f compose.yaml -f compose.dev.yaml stop webclient
	docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient rm -rf .next
	docker compose -f compose.yaml -f compose.dev.yaml up -d

migrate: check-env
	docker compose -f compose.yaml -f compose.dev.yaml up -d --wait postgres
	docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps service alembic upgrade head

down:
	docker compose -f compose.yaml -f compose.dev.yaml down

prod-up: .env check-env
	docker compose -f compose.yaml up -d --build

prod-down:
	docker compose -f compose.yaml down

llm:
	docker compose -f compose.yaml --profile llama up -d llama

llm-down:
	docker compose -f compose.yaml --profile llama rm -sf llama
