# PEKA Docker Setup

Run commands from this directory.

## Quick start

Run one command to create local environment configuration and start the full
development stack:

```bash
make up
```

This starts the API, webclient, PostgreSQL, and pgAdmin. No manual `.env` or
Docker commands are required.

## Development

Starts both apps with hot reload and source-code mounts:

```bash
make up
```

This runs `compose.yaml` together with `compose.dev.yaml`; PostgreSQL and
pgAdmin are included through the base Compose file. It also creates `.env`
from `.env.example` when `.env` does not exist.

`make up` rebuilds images before starting containers. Development containers
hot reload normal source-code changes automatically.


Open:

- Webclient: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- pgAdmin: http://localhost:5050

Default database connection in pgAdmin:

- Host: `postgres`
- Port: `5432`
- Database: `peka`
- Username: `peka`
- Password: `peka_dev_password`

pgAdmin login defaults to `admin@peka.local` / `peka_admin_password`.
Override these values with `POSTGRES_*` and `PGADMIN_*` variables in a
`.env` file in this directory. Copy `.env.example` first if needed.

Stop development containers:

```bash
make down
```

## Deployment-style run

Builds and runs production containers:

```bash
docker compose -f compose.yaml up -d --build
```

Stop deployment containers:

```bash
docker compose -f compose.yaml down
```
