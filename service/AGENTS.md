# Service instructions

- Run commands from `service/`; CI uses Python 3.12 and installs `requirements.txt` before running `python -m pytest`.
- Local setup: `python -m venv .venv`, activate it, `python -m pip install -r requirements.txt`, then copy `.env.example` to `.env`.
- Run the API with `uvicorn app.main:app --reload`; the entrypoint is `app.main:app`, with `/health` and `/docs` available.
- Focus tests with `python -m pytest tests/test_health.py` or `python -m pytest tests/test_health.py::test_healthcheck`.
- `app/main.py` creates the FastAPI app and includes routers listed explicitly in `app/__init__.py`; add every new feature router there.
- Keep feature code under `app/<feature>/` with dependencies flowing `routes -> service -> repository`; keep HTTP concerns out of services and repositories.
- Put environment configuration in `app/config.py` and document new variables in `.env.example`; runtime-generated files belong in `storage/`.
- Read `setup.md` before changing the feature structure or adding a feature.
