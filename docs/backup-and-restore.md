# Backup and restore

What to back up, and how to restore it. Run the commands from `config/`. The examples use the production-style stack (`make prod-up`); for the development stack (`make up`), add `-f compose.yaml -f compose.dev.yaml` after `docker compose`.

## What holds state

| Data | Where | Back up? |
|------|-------|----------|
| Database: users, invitations, files metadata, jobs, chunks and vectors, conversations, audit events, settings | Postgres, volume `config_postgres_data` | **Yes** |
| Uploaded originals and extraction records | Volume `config_file_storage` (production style) or the folder `service/storage/` (development) | **Yes** |
| Configuration and secrets | `config/.env`, `service/.env` | **Yes**, kept somewhere private. They hold the database password, `JWT_SECRET_KEY` and any API keys |
| Embedding and reranking models | Volume `config_embedding_models` | No. They download again on start (needs internet) |
| Language model file | `config/model/*.gguf` | Optional. Keep a copy if the machine will be offline when restoring |

The database and the stored files must be backed up together: each `files` row points at a stored original.

## Back up

```bash
cd config
mkdir -p ../backups

# 1. Database: a compressed custom-format dump, taken while the stack runs
docker compose exec -T postgres pg_dump -U peka -d peka -Fc > ../backups/peka-$(date +%F).dump

# 2. Stored files (production style: the file_storage volume)
docker run --rm -v config_file_storage:/data -v "$PWD/../backups":/backup alpine:3 \
  tar czf /backup/storage-$(date +%F).tar.gz -C /data .
#    Development: tar czf ../backups/storage-$(date +%F).tar.gz -C ../service/storage .

# 3. Environment files, kept private
tar czf ../backups/env-$(date +%F).tar.gz .env ../service/.env
```

`backups/` is not in `.gitignore`; keep it outside the repository, or never `git add` it. The dump and the environment files contain everything needed to read the documents.

## Restore

On a fresh machine, first follow [System requirements](system-requirements.md#start-peka) up to `make setup`, then put back the environment files from the backup **before** starting, so `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` match the data.

```bash
cd config

# 1. Stop the API and worker so nothing writes during the restore
docker compose stop service index-worker

# 2. Database
docker compose exec -T postgres pg_restore -U peka -d peka --clean --if-exists --no-owner < ../backups/peka-YYYY-MM-DD.dump

# 3. Stored files (production style)
docker run --rm -v config_file_storage:/data -v "$PWD/../backups":/backup alpine:3 \
  sh -c 'rm -rf /data/* && tar xzf /backup/storage-YYYY-MM-DD.tar.gz -C /data'
#    Development: tar xzf ../backups/storage-YYYY-MM-DD.tar.gz -C ../service/storage

# 4. Apply any newer migrations, then start again
make migrate
docker compose up -d service index-worker
```

After restoring, sign in and open a past conversation and a cited source to check that answers and citations still resolve.

**Tested:** on 17 November 2026, a `pg_dump -Fc` and `pg_restore --clean --if-exists --no-owner` round trip on `pgvector/pgvector:pg16` kept a `vector` column with its HNSW index, a generated `tsvector` column and a trigger, the features PEKA's schema uses. A full restore of a running PEKA database was not tested.

## Maintenance notes

- **Volume names** start with the Compose project name, which is the folder name `config` unless `COMPOSE_PROJECT_NAME` is set. Check with `docker volume ls`.
- **Re-indexing is automatic.** When an update changes the extractor or chunker version, the index worker re-indexes stored files on start; a backup of the database and files is enough, and vectors never need a separate backup.
- **Deleting volumes** with `docker compose down -v` deletes the database and stored files. Back up first.
- **llama.cpp memory** grows over long sessions; restart the `llama` service if the machine runs short of memory (see [Final report: limitations](final-report.md#limitations)).
