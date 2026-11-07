# Security and access control

## Authentication

- **Passwords**: Argon2 via `pwdlib[argon2]`
- **Login hardening**: unknown emails still run a password verify against a dummy hash (timing)
- **Tokens**: JWT HS256
  - Claims include `sub`, `role`, `ver` (token version), `typ` (`access` | `refresh`), `iss`, `aud`, `iat`, `nbf`, `exp`, `jti`
  - Access TTL: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (1–60)
  - Refresh TTL: `JWT_REFRESH_TOKEN_EXPIRE_DAYS` (default 30)
  - Issuer / audience must match `JWT_ISSUER` / `JWT_AUDIENCE`
  - `JWT_SECRET_KEY` must be ≥32 characters; placeholder secrets are rejected
- **Revocation**: incrementing `users.token_version` invalidates outstanding tokens (logout, password change, role/activation updates)

## Roles

| Role | Capabilities |
|------|----------------|
| `admin` | Full user management, provider settings, confidential uploads, all file ACL, delete users when inactive |
| `senior` | Chat, knowledge (general + confidential), no admin APIs |
| `staff` | Chat, knowledge **general** only |

### Document ACL

| `access_level` | Visible to |
|----------------|------------|
| `general` | admin, senior, staff |
| `confidential` | admin, senior |

Only admins may set/upload `confidential` and change a file's access level after upload.

## Audit log (FR10 / D-02)

D-02 is closed on the service: admins can list `audit_events`, and FR10 is no longer partial for the backend.

| Event | `type` | When | Metadata |
|-------|--------|------|----------|
| Sync completed / Sync failed | `sync` | index worker finishes a job (re-queue is not logged) | `event=sync_completed` / `sync_failed`, `file_id`, `status` |
| Chat turn | `query` | After the conversation row exists, including the first turn | `event=chat_turn`, `conversation_id` only |
| Login success | `system` | Successful login | `event=login_success` |
| Admin gate deny | `system` | Authenticated non-admin hits `admin_only`, or a non-admin changes a file access level | `event=admin_gate_deny`, `path` |

Recording never blocks the caller. Prompt and message bodies are not stored. `GET /admin/audit-events` is admin-only.

## Frontend gates

1. **Edge**: `webclient/proxy.ts` redirects unauthenticated `/workspace/*` to `/sign-in?next=…` based on cookie `peka_access_token`
2. **Session**: workspace layout loads `GET /auth/me`; failure clears storage and sends user to sign-in
3. **Admin pages**: client redirect to `/workspace` if `role !== "admin"`

Remember-me stores tokens in `localStorage` and sets cookie `Max-Age`; otherwise `sessionStorage` + session cookie.

Storage keys: `peka_access_token`, `peka_refresh_token`, `peka_remember_me`.

## Path and upload safety

- Downloads/deletes/worker paths resolve under `FILE_STORAGE_DIR` and reject traversal
- Upload size capped by `max_upload_bytes` (default 25 MiB)
- Content-addressed dedup via unique `files.sha256`
- Supported types: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.md`, `.txt`

## Admin bootstrap

On API lifespan, if both `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set and no admin exists, an admin user is created under a Postgres advisory lock. Do not commit real bootstrap credentials; leave unset after first admin exists.

## Secrets checklist

| Secret | Where |
|--------|-------|
| `JWT_SECRET_KEY` | `service/.env` / Compose |
| `LLM_API_KEY` | `service/.env` (+ optional DB override) |
| `EXA_API_KEY` | `service/.env` (+ optional DB override) |
| `POSTGRES_PASSWORD` | `config/.env` |
| `ADMIN_PASSWORD` | `service/.env` (bootstrap only) |

Use a secret manager in real deployments. Prefer removing the llama host port publish so only the backend network can reach the LLM.
