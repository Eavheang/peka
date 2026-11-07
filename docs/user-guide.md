# User guide

Practical walkthrough of the web UI. Technical detail lives in [How it works](how-it-works.md).

## Sign in

1. Open the app (Docker: http://localhost:3000).
2. Go to **Sign in** (`/sign-in`).
3. Enter email and password. Optional **Remember me** keeps the session in `localStorage` across browser restarts.
4. After success you land on `/workspace` (or the `?next=` path if it was safe).

If your session expires, the client tries one token refresh; if that fails you return to sign-in.

---

## Workspace: chat

**Who:** all roles.

### New chat

1. Open **New chat** in the sidebar (`/workspace`).
2. Optionally enable **web search** (stored in browser as `peka_web_search_enabled`). Needs a configured Exa key on the server.
3. Type a question (max 4000 characters) and send.
4. Watch streaming status/text. When finished, citations may appear under the answer.
5. The URL updates to `/workspace/<conversationId>` after the first message.

### Continuing a chat

- Pick a thread from the sidebar history (infinite scroll / load more).
- Follow-ups reuse conversation context; the server may rewrite search queries accordingly.
- Delete a conversation from the sidebar (confirm dialog).

### Citations & sources

- Numbered markers `[1]`, `[2]` point at retrieved knowledge chunks or web results.
- Open a citation to preview source text (knowledge) or follow a web URL/excerpt.
- Where a file id is available, download the original upload.

### When PEKA does not answer

- **Not enough evidence:** no passage in the documents you can access matches a question for a specific fact, so PEKA does not guess. Rephrase with the document's own terms, or upload a document that covers it.
- **"This answer was cut off":** the answer reached the length limit. Ask for less, or for one part at a time.

**Tips for better answers**

- Prefer specific questions (“What is the October launch date in the Q3 plan?”).
- Wait until Knowledge shows the file as **completed** before asking about a new upload.
- Turn web search on only for public/current facts; leave it off for internal-only topics.

---

## Knowledge library

**Who:** all roles can view and upload within ACL rules.

Path: `/workspace/knowledge`.

### Upload

1. Drag/drop or choose files: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.md`, `.txt` (max 25 MB each).
2. Choose access level:
   - **General** — visible to staff, senior, admin  
   - **Confidential** — senior + admin only (**setting confidential requires admin**)
3. Submit. Files appear with indexing status.

### Status meanings

| Status | Meaning |
|--------|---------|
| `queued` | Waiting for the indexing worker |
| `processing` | Chunking / embedding |
| `completed` | Searchable in chat |
| `failed` | Error after attempts; use **Retry OKF** (author or admin) |

### Table actions

- Download original
- Retry failed indexing
- Delete (author or admin)
- Admins: change access level (including bulk)

---

## Account settings

**Who:** all roles. Path: `/workspace/settings`.

- Update **display name**
- Change **password** (min 12 characters). After a successful change you are signed out and must sign in again (tokens revoked).

---

## Admin: users

**Who:** `admin` only. Path: `/workspace/admin`. Non-admins are redirected to `/workspace`.

| Task | Behavior |
|------|----------|
| Invite user | Email and role. The person gets an email with a link, chooses their name and a password (≥12 characters) and is signed in. If email is not configured, copy the invite link from the dialog and send it yourself |
| Pending invitations | Resend (issues a new link; the old one stops working) or revoke. Links are single-use and expire after 7 days |
| Change role | `admin` / `senior` / `staff` |
| Activate / deactivate | Inactive users cannot authenticate usefully; tokens invalidated on change |
| Delete | Only when inactive; blocked if related records prevent delete |

First admin can also be bootstrapped via `ADMIN_EMAIL` / `ADMIN_PASSWORD` on API startup (see [Security](security.md)).

---

## Admin: provider settings

**Who:** `admin` only. Path: `/workspace/admin/settings`.

Configure or override:

- LLM base URL, model, API key  
- Exa base URL, API key  

Actions: **Test** connection, **Save**. Keys are never returned on GET—only “configured” flags. Saved values live in the database and override env for LLM/Exa at runtime. Embeddings stay on environment variables.

---

## Role cheat sheet

| Capability | staff | senior | admin |
|------------|:-----:|:------:|:-----:|
| Chat + own conversations | ✓ | ✓ | ✓ |
| Knowledge: general files | ✓ | ✓ | ✓ |
| Knowledge: confidential files | | ✓ | ✓ |
| Upload confidential | | | ✓ |
| Change file access level | | | ✓ |
| Manage users | | | ✓ |
| Provider settings | | | ✓ |

---

## Public landing page

`/` is marketing only (hero, how-it-works, privacy). It does not require login. “Open workspace” hits `/workspace`, which redirects to sign-in if you are not authenticated.
