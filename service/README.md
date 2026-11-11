# PEKA Service

## Development

Run project setup from `config/`. It creates local environment configuration,
starts PostgreSQL and application containers, and runs database migrations:

```bash
cd config
make up
```

Useful URLs:

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- pgAdmin (optional, `--profile pgadmin` in `config/`): http://127.0.0.1:5050

## Database migrations

Create a migration after changing an ORM model. Run this command from
`service/`:

```bash
alembic revision --autogenerate -m "describe schema change"
```

Review the generated file in `alembic/versions/`, then apply migrations from
`config/`:

```bash
make migrate
```

`make up` runs pending migrations automatically. Do not create tables from
FastAPI startup.

## Stop development environment

```bash
cd config
make down
```
