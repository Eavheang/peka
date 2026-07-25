# FastAPI Project Setup

Feature-based FastAPI structure used by this service. Each feature keeps its routes, schemas, business logic, and data access together.

## Project structure

```text
project-root/
├── app/
│   ├── __init__.py             # Central router registry
│   ├── config.py               # Environment configuration
│   ├── main.py                 # Creates FastAPI application
│   └── todos/                  # Todo feature
│       ├── repository.py       # Data access
│       ├── routes.py           # HTTP endpoints
│       ├── schemas.py          # Pydantic request/response models
│       └── service.py          # Business logic
├── storage/                    # Runtime-generated files
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   └── test_todos_api.py
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md
```

Feature folders do not need `__init__.py`. Python can import their modules directly through namespace packages.

## Router registry

`app/__init__.py` imports every feature router and exposes one list:

```python
from app.todos.routes import router as todos_router

routers = [
    todos_router,
]
```

For another feature:

```python
from app.todos.routes import router as todos_router
from app.users.routes import router as users_router

routers = [
    todos_router,
    users_router,
]
```

Every new feature router must be added here. Avoid dynamic router discovery; explicit imports are easier to trace and debug.

## Application entrypoint

`app/main.py` creates the application and registers routers from `app`:

```python
from fastapi import FastAPI

from app import routers
from app.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

for router in routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
```

Run it with:

```bash
uvicorn app.main:app --reload --port 8000
```

## Feature structure

Each feature owns its code:

```text
app/<feature>/
├── repository.py       # Persistence or external data access
├── routes.py           # FastAPI router and endpoint handlers
├── schemas.py          # Pydantic input/output models
└── service.py          # Business rules and use cases
```

Add `model.py` only when the feature has a database/ORM model. Add other files only when the feature needs them.

Normal dependency direction:

```text
routes -> service -> repository -> database/external system
```

`schemas.py` may be used by routes and services. Repository code must not import routes.

### `routes.py`

Contains HTTP-specific code: paths, methods, request parameters, dependencies, status codes, and response models.

```python
from fastapi import APIRouter, status

from app.items.schemas import ItemCreate, ItemResponse
from app.items.service import create_item

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create(data: ItemCreate):
    return create_item(data)
```

Keep route handlers short. Put business rules and persistence outside route handlers.

### `schemas.py`

Pydantic models validate input and serialize output:

```python
from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1)


class ItemResponse(BaseModel):
    id: int
    name: str
```

Keep API schemas separate from ORM models when their responsibilities differ.

### `service.py`

Coordinates business rules and repositories. It must not depend on FastAPI request objects.

```python
from app.items.repository import item_repository
from app.items.schemas import ItemCreate


def create_item(data: ItemCreate) -> dict:
    return item_repository.create(data.name)
```

### `repository.py`

Contains database queries or calls to external persistence systems. Keep HTTP concepts out of this file.

Omit `repository.py` when the feature has no persistence or external data access.

## Adding a feature

For a `users` feature:

1. Create `app/users/routes.py`.
2. Add `schemas.py`, `service.py`, and `repository.py` only as needed.
3. Import its router in `app/__init__.py`.
4. Add its router to `routers`.
5. Add behavior tests under `tests/`.

```text
app/users/
├── repository.py
├── routes.py
├── schemas.py
└── service.py
```

## Configuration

Keep environment configuration in `app/config.py` and document variables in `.env.example`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI service"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

Do not read environment variables throughout feature modules when the settings object can provide them.

## Tests

Tests verify behavior rather than mirror source folders:

```text
tests/
├── conftest.py
├── test_health.py
├── test_todos_api.py
└── test_users_api.py
```

At minimum, test successful requests, validation failures, not-found responses, and authentication rules when applicable.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

API documentation is available at `/docs` and `/redoc`.

## Docker

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

Do not use `--reload` in production.

## Conventions

- Group code by feature, not technical layer.
- Register every feature router in `app/__init__.py`.
- Keep route handlers short and explicit.
- Validate external input at the API boundary.
- Keep configuration and secrets outside source code.
- Add files and abstractions only when a feature needs them.
- Prefer existing project patterns over new conventions.
