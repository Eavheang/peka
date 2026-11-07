# Web client (frontend)

Next.js App Router UI for PEKA: marketing landing, sign-in, workspace chat with citations, knowledge library, account settings, and admin user/provider management.

App metadata title: **PEKA** — description: **PEKA - Personal Knowledge Base**.

## Tech stack

| Layer | Package | Version (package.json) |
|-------|---------|------------------------|
| Framework | `next` | 16.2.10 |
| UI | `react` / `react-dom` | 19.2.4 |
| Server state | `@tanstack/react-query` | ^5.102.4 |
| HTTP | `axios` | ^1.19.0 |
| Forms | `react-hook-form` | ^7.86.0 |
| Markdown | `react-markdown` + `remark-gfm` | ^10 / ^4 |
| UI kit | shadcn (`base-nova`) + `@base-ui/react` | — |
| Styling | Tailwind CSS v4 | ^4 |
| Icons | `lucide-react` | — |
| Lint/format | oxlint, oxfmt | — |
| Package manager | **Bun** (`bun.lock`) | — |

Scripts: `dev`, `build`, `start`, `lint`, `lint-fix`, `format`, `format-check`, `tsc`.

`next.config.ts` sets `output: "standalone"` for the Docker image.

## Directory map

```text
webclient/
├── app/
│   ├── layout.tsx                 # root HTML, fonts, providers
│   ├── globals.css
│   ├── sign-in/page.tsx
│   ├── (public)/                  # landing /
│   └── (workspace)/workspace/     # authenticated area
├── components/
│   ├── ui/                        # shadcn primitives
│   ├── Theme/public|workspace/    # shells, sidebar, nav
│   ├── providers.tsx              # QueryClient + toaster
│   └── Alertdialog.tsx
├── services/                      # API hooks / stream helpers
├── interface/                     # auth, chat, files types
├── utils/                         # auth-storage, axios
├── variables/routes.ts            # nav + role ACL
├── constants/landing.tsx
├── lib/utils.ts                   # cn()
├── proxy.ts                       # Next 16 auth gate (ex-middleware)
├── public/peka.svg
├── Dockerfile
└── .env.example
```

Path alias: `@/*` → project root.

## Routes

Route groups `(public)` / `(workspace)` do not appear in the URL.

| URL | Purpose |
|-----|---------|
| `/` | Marketing landing |
| `/sign-in` | Login; optional `?next=` |
| `/workspace` | New chat |
| `/workspace/[conversationId]` | Existing conversation |
| `/workspace/knowledge` | Upload + file table |
| `/workspace/settings` | Profile + password |
| `/workspace/admin` | User management (admin) |
| `/workspace/admin/settings` | LLM / Exa providers (admin) |

### Sidebar nav (`variables/routes.ts`)

| Item | Path | Roles |
|------|------|-------|
| New chat | `/workspace` | admin, senior, staff |
| Knowledge | `/workspace/knowledge` | admin, senior, staff |
| Admin | `/workspace/admin` | admin |

Settings is reached from the profile menu, not the main `Routes` array.

## Auth (client)

1. Login stores tokens via `utils/auth-storage.ts` (local vs session storage + cookie)
2. `proxy.ts` protects `/workspace/:path*` using cookie `peka_access_token`
3. `utils/axios.ts` attaches Bearer token; on 401 refreshes once then retries
4. Streaming chat uses `fetchAuthenticated()` with the same refresh behavior
5. Logout / password change clears storage and returns to `/sign-in`

Keys: `peka_access_token`, `peka_refresh_token`, `peka_remember_me`  
Chat preference: `peka_web_search_enabled` in `localStorage`

## Data services

| Module | Responsibility |
|--------|----------------|
| `services/auth.ts` | login, me, logout, profile, password |
| `services/user.ts` | admin user CRUD / role / activation |
| `services/chat.ts` | SSE chat, conversations, source preview, citation download |
| `services/files.ts` | list/upload/retry/access/delete/download |
| `services/providerSettings.ts` | get/save/test LLM & Exa |

Notable React Query behavior:

- Current user: `["users","me"]`, 5 min staleTime
- Conversations: infinite query with cursor, 30s staleTime
- Files: refetch every **3s** while any indexing job is queued/processing

## Environment

`.env.example`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

| Context | Typical value |
|---------|----------------|
| Local Bun | `http://localhost:8000` |
| Docker Compose build | `/api` |

## Docker

Multi-stage Bun image: install → `next build` with `NEXT_PUBLIC_API_URL` build arg → alpine runner with standalone output on port **3000**.

## Conventions

See `webclient/AGENTS.md` and `webclient/.agents/*.md`:

- Thin pages; route-local `_partials/` (camelCase)
- Shared components PascalCase under `components/`
- Server Components by default; `'use client'` only when needed
- Do not replace `bun.lock`

## Further reading

- [Architecture](../architecture/overview.md)
- [Key flows](../architecture/flows.md)
- [API reference](../service/api-reference.md)
- [Security](../security.md)
