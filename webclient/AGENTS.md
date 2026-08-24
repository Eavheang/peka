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

<!-- ASTRYX:START -->
Astryx v0.4.7 · 158 components
CLI: run every command as `bunx astryx <cmd>` (shown below as `astryx ...`).

SETUP (once, in your app entry e.g. main.tsx) — without these, components render unstyled:
  import "@astryxdesign/core/reset.css";
  import "@astryxdesign/core/astryx.css";

WORKFLOW — discover, don't guess. Before writing UI:
1. `astryx build "<idea>"` — START HERE: returns a kit (closest [page] + [block]s + [component]s). No args = full playbook.
2. `astryx template <name> [--skeleton]` — scaffold the [page]/[block]s it named, or study their layout. Templates are reference code.
3. `astryx component <Name>` — props + examples for every component you use.

RULES:
- No <div> — components do all layout/spacing, page frame included.
- Frame first: read `astryx docs layout` before writing any page or screen — page frame, region widths, breakpoint behavior.
- Dense data = rows (Table, List/Item), never Card-wrapped list items; Card is for standalone widgets. Status = StatusDot/Token; Badge = counts only.
- Custom styling: component props first; else Tailwind utilities backed by tokens (bg-surface, text-primary, rounded-lg) via tailwind-theme.css. No raw hex/px.
- Tokens for every value (`astryx docs tokens`). Brand/accent belongs in the theme (`astryx theme list` / `theme add <slug>`, or `astryx theme template` for a custom one) — never override --color-* in :root.
- SELF-CHECK before you finish: re-read the file and replace any style={{…}}, raw <div>/<span> layout, imported .css/@apply, or hardcoded/arbitrary value (e.g. bg-[#fff], p-[13px]) with the component or a token-backed utility. If unsure a component/prop exists, run `astryx component <Name>` / `astryx search "<thing>"`; don't hand-roll CSS.

MORE CLI:
  search "<query>"   find any component / hook / doc / template / block
  component --list   158 components by category
  template --list    page + block recipes
  docs <topic>       browser-support, cli-integrations, color, elevation, getting-started, icons, illustrations, internationalization, layout, migration, motion, principles, shape, spacing, styling-libraries, styling, theme, tokens, typography, working-with-ai
  swizzle <Name>     eject component source for deep customization
  upgrade --apply    run after any @astryxdesign/core bump
<!-- ASTRYX:END -->
