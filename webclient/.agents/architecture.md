---
title: Application Architecture
description: App Router boundaries, optional route groups, file placement, and server/client rules.
read_when:

* Creating a route, layout, loading state, error state, or API route
* Deciding where a component, hook, type, utility, or service belongs
* Adding browser-only or server-only code
---

# Application Architecture

## Directory map

| Concern | Location | Rule |
|---|---|---|
| Routes and layouts | framework route directory | Use framework conventions only |
| Route-only UI | route-local partial directory | Keep local to route |
| Reusable UI | shared component directory | Move here after a second consumer needs it |
| Client hooks | hooks directory | Reusable stateful browser behavior |
| API/query hooks | services/data directory | Domain-oriented data access |
| Pure helpers | utilities directory | Stateless, framework-independent functions |
| Domain types | types/interfaces directory | Keep request, response, and form types explicit |
| Constants and route metadata | constants/config directory | No secrets; avoid catch-all constants |
| App configuration | config directory | Framework and application configuration |

## App Router rules

* `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`, and `not-found.tsx` use
  Next.js reserved names; do not rename them to describe the route.
* Keep page files thin: compose a page from route partials and shared
  components. Layouts own shell, navigation, page width, and outer spacing.
* If the framework supports route groups, use them only when routes need a
  shared shell, loading boundary, authorization boundary, or other behavior
  without changing the public URL. Names and groups are project decisions.
* Put route-specific dialogs, tables, and forms under a route-local partial
  directory when the project uses that convention.
* Add `loading.tsx` and `error.tsx` at the route boundary when the route has a
  meaningful loading or failure state.
* Add `'use client'` only to the smallest module that needs browser APIs,
  state, effects, event handlers, or client-only libraries.
* Server components may import server-safe modules; client components must not
  import secrets, server-only code, or server request APIs.
* Do not fetch the same data in both a page and its client query hook without a
  deliberate hydration strategy.

## Naming

* Framework-reserved route files keep their required names.
* Route partials use camelCase; shared component files use PascalCase.
* Hooks start with `use`; services are named by domain, not screen.
* Prefer named exports for reusable modules. Use default exports where the
  framework convention requires them.
