# PEKA Development Commands

Run commands from this directory.

## Development

Starts both apps with hot reload and source-code mounts:

```bash
make up
```

`make up` rebuilds images before starting containers. Development containers
hot reload normal source-code changes automatically.


Open:

- Webclient: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Stop development containers:

```bash
make down
```

## Deployment-style run

Builds and runs production containers:

```bash
docker compose up -d --build
```

Stop deployment containers:

```bash
docker compose down
```
