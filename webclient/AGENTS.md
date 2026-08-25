# Repository instructions

## Commands

- Use Bun; `bun.lock` is the committed lockfile. Do not replace it with another lockfile.
- `bun run dev` starts the Next.js dev server at `http://localhost:3000`.
- Run `bun run lint` after edits. For type checking use `bunx tsc --noEmit`; use `bun run build` for routing, environment, or build-system changes.

## Structure

- This is a single Next.js 16.2.10 App Router app. Routes and root layout live in `app/`; `app/layout.tsx` is the sole global CSS import and font boundary.
- Tailwind CSS v4 is wired through `postcss.config.mjs`; keep global CSS in `app/globals.css` and use the `@/*` TypeScript alias for project imports.
- Keep server components as the default. Add `'use client'` only to the smallest module needing browser APIs, state, effects, or event handlers; never expose secrets or server-only code to client modules.
- Keep route entry files thin. When shared UI or route-local modules are introduced, follow `.agents/architecture.md` and `.agents/component.md` for placement and naming.

## Conditional rules

Read matching `.agents/*.md` guidance before working in these areas:

- auth, authorization, localization, or environment variables: `.agents/auth-i18n.md`
- API calls, uploads/downloads, caching, or server/local state: `.agents/data-access.md`
- TypeScript, imports, validation, errors, or lint/typecheck behavior: `.agents/code-standard.md`
- components, hooks, forms, or shared-vs-route-local placement: `.agents/component.md`
- routes, layouts, loading/error boundaries, or server/client boundaries: `.agents/architecture.md`
- layout, styling, responsive behavior, or global CSS: `.agents/design.md`
- feature completion, accessibility, UI states, or verification: `.agents/quality.md`

## Next.js

Next.js 16.2.10 has breaking changes from older versions. Before changing framework APIs or conventions, check relevant guidance under `node_modules/next/dist/docs/` when available and heed deprecation notices.

