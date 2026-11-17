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
2. Optionally enable **web search** (stored in browser as `peka_web_search_enabled`). The toggle shows only when the server has an Exa key. When the server has no internet, the sidebar shows **Offline**, web search and Google Drive are greyed out (clicking them explains why), and invitations give a link to copy instead of sending an email. Documents and chat keep working.
3. Type a question (max 4000 characters) and send.
4. Watch streaming status/text. When finished, citations may appear under the answer. If other people's answers are being generated, the status reads "Waiting for other answers to finish..." until a model slot is free.
5. The URL updates to `/workspace/<conversationId>` after the first message.

**Stop and regenerate:** **Stop response** ends an answer while it streams; the text shown so far is kept and marked "Response stopped". **Regenerate response** asks the last question again and replaces the last answer.

### Continuing a chat

- Pick a thread from the sidebar history (infinite scroll / load more).
- Follow-ups reuse conversation context; the server may rewrite search queries accordingly.
- Delete a conversation from the sidebar (confirm dialog).

### Citations & sources

- Numbered markers `[1]`, `[2]` point at retrieved knowledge chunks or web results.
- Open a citation to preview source text (knowledge) or follow a web URL/excerpt.
- Where a file id is available, download the original upload.

### When PEKA does not answer

- **Need more detail:** no passage in the documents you can access clearly matches a question for a specific fact, so PEKA does not guess. It lists the closest documents and asks what you meant. Name one, add detail, or upload a document that covers it.
- **"This answer was cut off":** the answer usually reached the length limit, and its last part has no sources attached. Ask for less, or for one part at a time.

**Tips for better answers**

- Prefer specific questions (“What is the October launch date in the Q3 plan?”).
- Wait until Knowledge shows the file as **completed** before asking about a new upload.
- Turn web search on only for public/current facts; leave it off for internal-only topics.

---

## Knowledge library

**Who:** all roles can view and upload within ACL rules.

Path: `/workspace/knowledge`.

### Upload

1. Drag/drop or choose files under **Your computer**: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.md`, `.txt` (max 25 MB each). Or use **Import from Drive** (see below).
2. Choose access level:
   - **General** — visible to staff, senior, admin  
   - **Confidential** — senior + admin only (**setting confidential requires admin**)
3. Submit. Files appear with indexing status.

### Import from Google Drive

Available when the server has Google credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_API_KEY`, `GOOGLE_APP_ID`) and internet access.

1. Under **Google Drive**, choose **Import from Drive**. The first time, sign in with Google and allow access; you return to the Knowledge library with "Google Drive connected."
2. Pick up to 50 files in the Google Picker. Google Docs, Sheets and Slides are exported as DOCX, XLSX and PPTX.
3. Set each file's access level and submit. Keep the page open until the import finishes.

The import is a one-time copy: later edits in Drive are not picked up. To refresh a file, delete the old copy and import it again. PEKA only sees the files you pick (Google scope `drive.file`). To keep a whole folder in step, an admin sets up folder sync.

### Google Drive folder sync (admin)

An admin picks one Drive folder as the source of truth under **Admin → Workspace settings → Google Drive sync**.

1. Choose **Choose folder**. The first time, Google asks for read access to your whole Drive (`drive.readonly`), because PEKA must see files added to the folder later. You return to the settings page; choose the folder again.
2. Set the **daily sync time** (default 00:00, in this browser's time zone) and the access level for synced files, then **Save folder sync**.
3. Each day at that time, files added to the folder or its subfolders, and files edited there, are added to the knowledge base. Files deleted from the folder are removed. Files already in the folder when you pick it are added by the first sync, which starts within a minute.
4. **Sync now** runs within a minute. The card shows the last run, for example "3 added, 1 updated, 0 removed". **Stop syncing** keeps the files already synced; so does picking another folder.

If the server is offline at sync time, the sync runs once it is back online. Manual uploads and imports keep working alongside the sync.

### Status meanings

| Status | Meaning |
|--------|---------|
| `queued` | Waiting for the indexing worker |
| `processing` | Chunking / embedding |
| `completed` | Searchable in chat |
| `failed` | Error after attempts; use **Retry indexing** (author or admin) |

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
- **Appearance:** pick one of four themes (Clay, Daylight, Sage, Midnight). It applies right away and is saved in this browser only.

---

## Admin: users

**Who:** `admin` only. Path: `/workspace/admin` (**Users** tab). Non-admins are redirected to `/workspace`. The Admin area has three tabs: **Users**, **Workspace settings** and **Audit log**.

| Task | Behavior |
|------|----------|
| Invite user | Email and role. The person gets an email with a link, chooses their name and a password (≥12 characters) and is signed in. If email is not configured, copy the invite link from the dialog and send it yourself |
| Pending invitations | Resend (issues a new link; the old one stops working) or revoke. Links are single-use and expire after 7 days |
| Change role | `admin` / `senior` / `staff` |
| Activate / deactivate | Inactive users cannot authenticate usefully; tokens invalidated on change |
| Delete | Only when inactive; blocked if related records prevent delete |

First admin can also be bootstrapped via `ADMIN_EMAIL` / `ADMIN_PASSWORD` on API startup (see [Security](security.md)).

---

## Admin: audit log

**Who:** `admin` only. Path: `/workspace/admin/audit` (**Audit log** tab).

The table lists sync (indexing finished or failed), query (a chat turn) and system (sign-in, denied admin request) events, newest first, with the actor and a summary. Filter by type and page with **Next**. Questions and answers themselves are never stored in the log.

---

## Admin: workspace settings

**Who:** `admin` only. Path: `/workspace/admin/settings` (**Workspace settings** tab).

Three sections:

- **Language model**: base URL, model, API key  
- **Web search**: Exa base URL, API key  
- **Google Drive sync**: see [Google Drive folder sync](#google-drive-folder-sync-admin) (shown only when Google Drive is configured)

Actions: **Test connection** (tests the saved settings, so save first) and **Save provider settings** (saves the language model and web search together). Keys are never returned on GET—only “configured” flags. Saved values live in the database and override env for LLM/Exa at runtime. Embeddings stay on environment variables.

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
| Workspace settings | | | ✓ |
| Audit log | | | ✓ |
| Import from Google Drive (general files) | ✓ | ✓ | ✓ |
| Google Drive folder sync | | | ✓ |

---

## Public landing page

`/` is marketing only (hero, how-it-works, privacy). It does not require login. “Open workspace” hits `/workspace`, which redirects to sign-in if you are not authenticated.
