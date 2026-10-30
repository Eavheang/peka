# peka

Organization-private RAG assistant: upload documents, index them into a knowledge base, and chat with cited answers.

## Documentation

Full documentation lives in [`docs/`](docs/README.md).

**Understand the system:** [What is PEKA?](docs/what-is-peka.md) · [How it works](docs/how-it-works.md) · [User guide](docs/user-guide.md)

**Run it:** [System requirements and quick start](docs/system-requirements.md) · [Final report](docs/final-report.md)

**Build & operate:** [Getting started](docs/getting-started.md) · [Architecture](docs/architecture/overview.md) · [API reference](docs/service/api-reference.md) · [Service](docs/service/README.md) · [Web client](docs/webclient/README.md) · [Config / Docker](docs/config/README.md)

## Development

From `config/`, run setup once:

```bash
make setup
```

Start development servers afterward:

```bash
make up
```

Run `make setup` again when dependencies, lockfiles, or Dockerfiles change.
