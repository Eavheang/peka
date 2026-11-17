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
| `GET` | `/status` | bearer | `{ "online": bool, "configured": { "web_search": bool, "google_drive": bool, "email": bool } }`. `configured` says what an admin has set up; each feature also needs `online` |

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
**InvitationResponse:** `id`, `email`, `role`, `expires_at`, `created_at`, `invite_url`, `email_sent`, `email_error`. `invite_url` is returned only when an invitation is created or resent (only a hash is stored); `email_sent` is `false` when SMTP is unconfigured, the server is offline, or sending failed, so the admin can copy the link instead. `email_error` says which: `not_configured`, `offline` or `failed` (`null` when sent).

---

## Files — `/files`

| Method | Path | Auth | Notes | Response |
|--------|------|------|-------|----------|
| `POST` | `/files` | bearer | multipart `files` + optional `access_levels`; 413 size, 409 SHA dup, 415 bad type, 403 confidential non-admin | `FileResponse[]` 201 |
| `GET` | `/files` | bearer | ACL-filtered list | `FileResponse[]` |
| `GET` | `/files/{file_id}` | bearer | download stream | file bytes |
| `GET` | `/files/{file_id}/index-status` | bearer | — | `{ file_id, index_status, index_attempts, index_error }` |
| `POST` | `/files/{file_id}/retry-indexing` | author or admin | only if failed | `FileResponse`; 409 otherwise |
| `PATCH` | `/files/{file_id}/access-level` | admin | `{ access_level }` | `FileResponse` |
| `DELETE` | `/files/{file_id}` | author or admin | — | 204 |

**FileResponse:** `id`, `path`, `content_type`, `sha256`, `author_id`, `access_level`, `created_at`, `index_status`, `index_attempts`, `index_error`

`access_level`: `general` | `confidential`  
`index_status`: `queued` | `processing` | `completed` | `failed`

---

## Search — `/search`

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| `POST` | `/search` | bearer | `{ query }` | `SearchResponse[]`; 503 on embed failure |

**SearchResponse:** `file_id`, `title`, `heading`, `snippet`, `source_locations`, `score`

`source_locations` holds extractor locators such as `{"page": 3}`, `{"slide": 3}`, `{"sheet": 1, "name": "Q1"}`, or `{"section": 2}`.

---

## Chat — `/chat`

| Method | Path | Auth | Body / query | Response |
|--------|------|------|--------------|----------|
| `POST` | `/chat` | bearer | `{ query, conversation_id?, new_conversation_id?, web_search?, regenerate?, timezone? }` | `ChatResponse`; 409 when `regenerate` has no last answer to replace |
| `POST` | `/chat/stream` | bearer | same | SSE `text/event-stream` |
| `POST` | `/chat/source-preview` | bearer | `{ chunk_id?, title, heading }` | `{ content, file_id? }` or 404 |
| `GET` | `/chat/conversations` | bearer | `limit` 1–50 (default 15), `cursor?` | `{ items, next_cursor }` |
| `GET` | `/chat/conversations/{id}` | owner | — | conversation + messages |
| `DELETE` | `/chat/conversations/{id}` | owner | — | 204 |

**ChatResponse:** `answer`, `refused`, `citations`, `conversation_id`, `messages`

### Stream events

Lines of the form `data: <payload>`. Event kinds: `status`, `text`, `done`, `error`, then `data: [DONE]`.

---

## Google Drive import — `/integrations/google`

Needs `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_API_KEY`, `GOOGLE_APP_ID` and `APP_BASE_URL`; otherwise 503. Import uses scope `drive.file`: PEKA only reaches files the user picks. Folder sync (admin only, `/integrations/google/sync/*`) adds `drive.readonly`, because it lists files nobody picked.

| Method | Path | Auth | Body / notes | Response |
|--------|------|------|--------------|----------|
| `GET` | `/integrations/google/connect` | bearer | Start Google sign-in | `{ url }`; 503 not configured |
| `GET` | `/integrations/google/callback` | none (signed `state`) | Google redirects here; stores the encrypted refresh token for the user in `state` | Redirect to the page that started it (`/workspace/knowledge` or `/workspace/admin/settings`) with `?google_drive=connected` or `error` |
| `GET` | `/integrations/google/picker` | bearer | Short-lived token for the Google Picker | `{ access_token, api_key, app_id }`; 409 not connected; 502 Google error |
| `POST` | `/integrations/google/files` | bearer | `{ files: [{ id, access_level }] }`, 1 to 50 files. Google Docs, Sheets and Slides are exported as DOCX, XLSX and PPTX | `FileResponse[]` 201; 403 confidential non-admin; 409 duplicate or not connected; 413 too large; 415 unsupported |

The import is a one-time copy; later changes in Drive are not synced. For that, an admin sets up folder sync.

### Folder sync — admin only

One workspace-wide folder. Once a day at `sync_time` in `timezone`, or within a minute of **Sync now**, the index worker lists the folder and all its subfolders and:

- imports files that are new since the last run, and files that changed in Drive (the old copy is deleted after the new one is stored);
- deletes the PEKA copy of files removed from the tree (deleted, trashed or moved out). Nothing is deleted unless every folder in the tree listed without error;
- skips unsupported, too large and duplicate files.

Picking a folder starts a run within a minute that imports every file already in it. Stopping the sync or picking another folder keeps the files already synced. Each run writes a `sync` audit event.

| Method | Path | Auth | Body / notes | Response |
|--------|------|------|--------------|----------|
| `GET` | `/integrations/google/sync/connect` | admin | Start Google sign-in with `drive.readonly` added; returns to the admin settings page | `{ url }`; 503 not configured |
| `GET` | `/integrations/google/sync/picker` | admin | Picker token for choosing the sync folder | `{ access_token, api_key, app_id }`; 409 until the connection has `drive.readonly`; 502 Google error |
| `GET` | `/integrations/google/sync` | admin | Current settings and the last run | `DriveSyncSettings` or `null` |
| `PUT` | `/integrations/google/sync` | admin | `{ folder_id, folder_name, access_level, timezone (IANA), sync_time ("HH:MM") }`. Makes this admin the owner (their Drive is read). A different folder starts over and is listed again; a changed time or time zone applies today | `DriveSyncSettings`; 422 bad time zone or folder ID |
| `POST` | `/integrations/google/sync/run` | admin | Sync now | 202; 404 not set up; 503 offline |
| `DELETE` | `/integrations/google/sync` | admin | Stop syncing; synced files stay | 204 |

`DriveSyncSettings` adds `owner_email`, `run_requested` (true from **Sync now** or a new folder until that run finishes), `last_synced_at` and `last_result` to the `PUT` body.

---

## Audit events — `/admin/audit-events`

| Method | Path | Auth | Query | Response |
|--------|------|------|-------|----------|
| `GET` | `/admin/audit-events` | admin | `type` (`sync` \| `query` \| `system`), `limit` (1–100, default 50), `cursor` | `{ items, next_cursor }` |

**AuditEvent:** `id`, `type`, `actor_id`, `summary`, `metadata`, `created_at`

`next_cursor` is a keyset token of `created_at` and `id` (`created_at DESC, id DESC`). An invalid cursor is 400. Every event sets `metadata.event`: `sync_completed` / `sync_failed` (sync, plus `file_id` and `status`), `chat_turn` (query, plus `conversation_id` only — no prompt or message body), `login_success` / `admin_gate_deny` (system; deny adds `path`).

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
