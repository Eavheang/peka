# PEKA Docker Compose

Run commands from this directory.

## Development

Starts both apps with hot reload and source-code mounts:

```bash
docker compose -f compose.dev.yaml up --build
```

Use `--build` after changing `service/requirements.txt`, either Dockerfile,
`webclient/package.json`, `webclient/bun.lock`, or Compose build settings.
For normal code changes, start without rebuilding:

```bash
docker compose -f compose.dev.yaml up -d
```

Development containers hot reload source-code changes automatically.

Open:

- Webclient: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Stop development containers:

```bash
docker compose -f compose.dev.yaml down
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
