# FastAPI Project Setup

General project structure for a maintainable FastAPI backend. This is a practical convention, not a framework requirement. Add directories only when the project needs them.

## Recommended structure

```text
project-root/
├── app/
│   ├── main.py                 # Creates FastAPI application and registers routers
│   ├── routes/
│   │   ├── __init__.py         # Combines and exports feature routers
│   │   └── <feature>.py        # HTTP endpoints grouped by feature
│   ├── schemas/
│   │   └── <feature>.py        # Pydantic request and response models
│   ├── services/
│   │   └── <feature>.py        # Business logic and use cases
│   ├── repositories/
│   │   └── <feature>.py        # Database or external data access
│   ├── models/
│   │   └── <feature>.py        # Database models, when needed
│   ├── db/
│   │   ├── __init__.py
│   │   └── session.py          # Database connection/session setup
│   ├── core/
│   │   ├── security.py         # Authentication/security helpers
│   │   └── errors.py           # Shared application errors
│   ├── utils/                  # Small reusable helpers
│   ├── middleware/             # Custom middleware, when needed
│   └── scripts/                # Maintenance and import scripts
├── storage/                    # Runtime files, generated files, or local assets
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   └── test_<feature>.py
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md
```

## Responsibilities

### `app/main.py`

Application entrypoint. It should:

1. Load configuration.
2. Create the `FastAPI` instance.
3. Register middleware and exception handlers.
4. Include all routers from `app.routes`.
5. Register startup/shutdown hooks only when required.

```python
from fastapi import FastAPI

from app.routes import routers

app = FastAPI(title="Service name", version="1.0.0")

for router in routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def healthcheck():
    return {"status": "ok"}
```

Run it with:

```bash
uvicorn app.main:app --reload --port 8000
```

### `app/routes/`

Contains HTTP-specific code:

- URL paths and HTTP methods
- Query, path, and body parameters
- Dependency injection
- Authentication checks
- HTTP status codes and response models

Keep business rules and database queries outside route handlers.

```python
from fastapi import APIRouter

from app.schemas.items import ItemCreate, ItemResponse
from app.services.items import create_item

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemResponse, status_code=201)
async def create(data: ItemCreate):
    return await create_item(data)
```

`app/routes/__init__.py` is the central router registry:

```python
from app.routes.items import router as items_router
from app.routes.users import router as users_router

routers = [
    items_router,
    users_router,
]
```

Every new feature router must be included in this list. `app/main.py` includes each router in `routers`.

### `app/schemas/`

Pydantic models for input validation and output serialization. Keep API models separate from database models when their responsibilities differ.

```python
from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)


class ItemResponse(BaseModel):
    id: str
    name: str
```

### `app/services/`

Business logic and use cases. Services coordinate repositories, validation, and other services. They should not depend on FastAPI request objects.

```python
from app.repositories.items import item_repository


async def create_item(data):
    item_id = await item_repository.create(data.model_dump())
    return await item_repository.get(item_id)
```

### `app/repositories/`

Data access layer. Repositories contain database queries or calls to external persistence systems. Keep this layer independent from HTTP concepts.

If the project does not need a database, omit `repositories/`, `models/`, and `db/`.

### `app/config.py`

Centralize environment configuration. Use `.env.example` to document required variable names without committing secrets.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI service"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

Do not read environment variables throughout the application when one settings object can provide them.

## Feature structure

For a feature named `items`, use:

```text
app/
├── routes/items.py
├── schemas/items.py
├── services/items.py
├── repositories/items.py       # Only if persistence is needed
└── models/items.py             # Only if database models are needed
```

The normal dependency direction is:

```text
route -> service -> repository -> database/external system
```

Schemas can be used by routes and services. Shared utilities should not import route modules.

## Authentication and dependencies

Put reusable dependencies in `app/dependencies.py` or `app/core/security.py`:

- Current-user resolution
- Role or permission checks
- Database sessions
- Request-scoped services
- Common pagination or filtering

Use FastAPI's `Depends()` rather than manually creating shared resources inside each route.

## Storage

Use `storage/` for runtime-generated files. Keep uploaded or generated files out of source control.

```text
storage/
├── uploads/
├── exports/
└── .gitkeep
```

For production, prefer external or persistent storage when files must survive deployment. Keep the storage path configurable through environment variables.

## Tests

Tests should mirror application behavior, not necessarily application folders.

```text
tests/
├── conftest.py             # Shared fixtures and test application setup
├── test_health.py          # Basic application smoke test
├── test_items_api.py       # HTTP/API behavior
└── test_items_service.py   # Business logic behavior
```

Use `TestClient` for simple synchronous endpoint tests or `httpx.AsyncClient` for async tests. At minimum, test:

- Health endpoint
- Successful request
- Validation failure
- Not-found/error response
- Authentication/authorization behavior when applicable

Example smoke test:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

## Dependencies and local setup

Keep runtime dependencies in `requirements.txt` or the project's chosen dependency file. A minimal FastAPI setup normally includes:

```text
fastapi
uvicorn[standard]
```

Add only dependencies required by the project, such as a database driver, authentication library, multipart upload support, or test tools.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

API documentation is automatically available at `/docs` and `/redoc` unless disabled.

## Docker

A basic Dockerfile should install dependencies, copy application code, expose the application port, and run Uvicorn:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY storage ./storage

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Do not use `--reload` in production containers.

## General conventions

- Use async route handlers and async libraries when the operation is I/O-bound.
- Keep route handlers short and explicit.
- Validate external input at the API boundary.
- Return consistent response shapes and status codes.
- Use type hints throughout the application.
- Keep configuration and secrets outside source code.
- Add a router to the central registry whenever a new feature is created.
- Avoid global mutable state unless it is intentionally application-wide.
- Add a small test whenever adding non-trivial business logic.
- Prefer the existing project pattern over introducing a new abstraction.

## Instructions for generating a new project

When using this document as an AI generation reference:

1. Create `app/main.py` as the FastAPI entrypoint.
2. Create `app/routes/__init__.py` as the central router registry.
3. Group endpoints by feature under `app/routes`.
4. Put Pydantic models under `app/schemas`.
5. Put business logic under `app/services`.
6. Add repositories, models, and database setup only when persistence is required.
7. Add `config.py`, `.env.example`, `storage/`, and `tests/`.
8. Add a health endpoint and one basic test.
9. Add a Dockerfile and dependency file.
10. Keep optional integrations out of the core structure until the feature needs them.
