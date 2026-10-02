# API reference

Base URL locally: `http://localhost:8000`  
Via Compose nginx: `http://localhost:3000/api` (prefix stripped before the API).

Unless noted, authenticated endpoints expect:

```http
Authorization: Bearer <access_token>
```

Roles: `admin` | `senior` | `staff`.

---

## Health

| Method | Path | Auth | Response |
|--------|------|------|----------|
| `GET` | `/health` | none | `{ "status": "ok" }` |

---

## Auth — `/auth`

| Method | Path | Auth | Body / notes | Response |
|--------|------|------|--------------|----------|
| `POST` | `/auth/login` | none | `{ email, password }` | `TokenResponse` |
| `POST` | `/auth/refresh` | none | `{ refresh_token }` | `TokenResponse` |
| `POST` | `/auth/logout` | bearer | — | 204 |
| `GET` | `/auth/me` | bearer | — | `UserResponse` |
| `PATCH` | `/auth/me` | bearer | `{ display_name }` | `UserResponse` |
| `POST` | `/auth/password` | bearer | `{ current_password, new_password }` | 204 |
| `GET` | `/auth/users` | admin | — | `UserResponse[]` |
| `POST` | `/auth/invitations` | admin | `{ email, role? }` | `InvitationResponse` 201; 409 user exists or invite pending |
| `GET` | `/auth/invitations` | admin | pending invitations | `InvitationSummary[]` |
| `POST` | `/auth/invitations/{id}/resend` | admin | new token and expiry; old link stops working | `InvitationResponse`; 404 |
| `DELETE` | `/auth/invitations/{id}` | admin | revoke a pending invitation | 204; 404 |
| `POST` | `/auth/invitations/lookup` | none | `{ token }` (POST keeps the token out of URLs/logs) | `{ email, role }`; 404 invalid/expired |
| `POST` | `/auth/invitations/accept` | none | `{ token, display_name, password }` (≥12 chars) | `TokenResponse` (signed in); 404 invalid/expired; 409 email taken |
| `PATCH` | `/auth/users/{user_id}/role` | admin | `{ role }` | `UserResponse`; 409 demoting self |
| `PATCH` | `/auth/users/{user_id}` | admin | `{ is_active }` | `UserResponse` |
| `DELETE` | `/auth/users/{user_id}` | admin | user must be inactive | 204; 409 if FK refs |

**TokenResponse:** `access_token`, `refresh_token`, `token_type`, `expires_in`  
**UserResponse:** `id`, `email`, `display_name`, `role`, `is_active`  
**InvitationResponse:** `id`, `email`, `role`, `expires_at`, `created_at`, `invite_url`, `email_sent`. `invite_url` is returned only when an invitation is created or resent (only a hash is stored); `email_sent` is `false` when SMTP is unconfigured or sending failed, so the admin can copy the link instead.

---

## Files — `/files`

| Method | Path | Auth | Notes | Response |
|--------|------|------|-------|----------|
| `POST` | `/files` | bearer | multipart `files` + optional `access_levels`; 413 size, 409 SHA dup, 415 bad type, 403 confidential non-admin | `FileResponse[]` 201 |
| `GET` | `/files` | bearer | ACL-filtered list | `FileResponse[]` |
| `GET` | `/files/{file_id}` | bearer | download stream | file bytes |
| `GET` | `/files/{file_id}/okf-status` | bearer | — | `{ file_id, okf_status, okf_attempts, okf_error }` |
| `POST` | `/files/{file_id}/retry-okf` | author or admin | only if failed | `FileResponse`; 409 otherwise |
| `PATCH` | `/files/{file_id}/access-level` | admin | `{ access_level }` | `FileResponse` |
| `DELETE` | `/files/{file_id}` | author or admin | — | 204 |

**FileResponse:** `id`, `path`, `content_type`, `sha256`, `author_id`, `access_level`, `created_at`, `okf_status`, `okf_attempts`, `okf_error`

`access_level`: `general` | `confidential`  
`okf_status`: `queued` | `processing` | `completed` | `failed`

---

## Search — `/search`

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| `POST` | `/search` | bearer | `{ query }` | `SearchResponse[]`; 503 on embed failure |

**SearchResponse:** `file_id`, `title`, `heading`, `snippet`, `source_locations`, `score`

---

## Chat — `/chat`

| Method | Path | Auth | Body / query | Response |
|--------|------|------|--------------|----------|
| `POST` | `/chat` | bearer | `{ query, conversation_id?, web_search? }` | `ChatResponse` |
| `POST` | `/chat/stream` | bearer | same | SSE `text/event-stream` |
| `POST` | `/chat/source-preview` | bearer | `{ chunk_id?, title, heading }` | `{ content, file_id? }` or 404 |
| `GET` | `/chat/conversations` | bearer | `limit` 1–50 (default 15), `cursor?` | `{ items, next_cursor }` |
| `GET` | `/chat/conversations/{id}` | owner | — | conversation + messages |
| `DELETE` | `/chat/conversations/{id}` | owner | — | 204 |

**ChatResponse:** `answer`, `refused`, `citations`, `conversation_id`, `messages`

### Stream events

Lines of the form `data: <payload>`. Event kinds: `status`, `text`, `done`, `error`, then `data: [DONE]`.

---

## Audit events — `/admin/audit-events`

| Method | Path | Auth | Query | Response |
|--------|------|------|-------|----------|
| `GET` | `/admin/audit-events` | admin | `type` (`sync` \| `query` \| `system`), `limit` (1–100, default 50), `cursor` | `{ items, next_cursor }` |

**AuditEvent:** `id`, `type`, `actor_id`, `summary`, `metadata`, `created_at`

`next_cursor` is a keyset token of `created_at` and `id` (`created_at DESC, id DESC`). An invalid cursor is 400. System events set `metadata.event` to `login_success` or `admin_gate_deny`. Query events store `metadata.conversation_id` only (no prompt or message body). Sync events store `metadata.file_id` and `metadata.status` (`completed` \| `failed`).

Writers are fail-open: a database error while recording does not fail chat, sync, or login.

---

## Admin provider settings — `/admin/settings/providers`

| Method | Path | Auth | Notes | Response |
|--------|------|------|-------|----------|
| `GET` | `/admin/settings/providers` | admin | keys not returned | URLs/models + `llm_configured` / `exa_configured` |
| `PUT` | `/admin/settings/providers` | admin | `{ llm_base_url, llm_api_key?, llm_model, exa_base_url?, exa_api_key? }`; omitted keys keep previous | same as GET |
| `POST` | `/admin/settings/providers/test/{provider}` | admin | `provider` = `llm` \| `exa` | `{ ok, status, message }` |

---

## Error patterns (common)

| Status | Typical cause |
|--------|----------------|
| 401 | Missing/invalid/expired token or stale `ver` |
| 403 | Role/ACL insufficient |
| 404 | Missing resource or ACL hide |
| 409 | Duplicate email/SHA, invalid state transition |
| 413 | Upload too large |
| 415 | Unsupported or unextractable file |
| 503 | Embedding service failure |
