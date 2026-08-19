---
title: Code Standards
description: TypeScript, naming, imports, validation, errors, lint, and typecheck.
read_when:

* Changing TypeScript types, interfaces, naming, or imports
* Changing API calls, services, env usage, auth, or validation
* Changing lint/typecheck behavior
avoid_when:

* Only changing layout, spacing, colors, cards, or responsive UI
* Only changing component placement or route structure
* Only changing business logic that does not touch shared conventions
---

# Code Standards

## Quick rules

* Use ES modules, single quotes, strict TypeScript, and type-only imports where appropriate.
* Keep route entry files thin: render content, not layout chrome.
* Use the framework's naming conventions for route files; use a consistent
  convention for route-local partials and shared components.
* Keep route-only pieces in the project's route-local partial directory.
* Use separate interfaces for API payloads and form UI when they differ.
* Put small pure helpers in `utils/`.
* Put API calls in a dedicated data-access area and use the project's server-state solution for fetching/mutations.
* Do not hardcode env-dependent URLs or secrets.
* Reuse shared primitives for repeated page concerns such as headings.
* Use repository-provided wrappers for lint/typecheck when available.

## Details

### File and directory naming

- Follow framework-reserved names for entry files.
- Choose one naming convention per file category and apply it consistently.
- Make shared component names distinguishable from route-local component names.

### Page structure

- Route entry files compose route-local and shared UI; they do not own global
  layout chrome.
- Use the project's module and formatting conventions consistently.

### Interfaces

Use separate interfaces for form payloads and form UI, even if properties overlap.
Extend from a shared base when that helps future changes.

Prefer domain-specific names over generic `Data`, `Item`, or `Response` names.
Type API response data at the Axios call. Use `unknown` at untrusted boundaries
and narrow it before use; avoid `any`.

### Utilities

Small, pure compute functions belong in `utils/`. Keep them focused and stateless.

### Services / API layer

API calls live in the project's data-access area and use its selected fetching,
caching, and mutation solution.

Authenticated and public requests use separate configured clients when the
project needs both. Components must not create ad-hoc request clients.

### Errors and validation

- Validate form and external input at trust boundaries with the project's schema
  tooling. Keep validation messages independent from presentation language.
- Handle expected API failures in the UI and keep diagnostic logging free of
  tokens, credentials, and private payloads.
- Do not swallow errors silently. Re-throw or return a typed failure when a
  caller needs to render an error state.

### Imports and formatting

- Use the `@/*` alias for project imports instead of long relative paths.
- Keep type imports separate when it improves clarity; let Oxlint/Oxfmt be
  the final authority on ordering and formatting.
- Do not disable lint rules inline without a reason in the same comment.

### General principles

- YAGNI: don't overengineer. Build the minimal version that works.
- Single quotes for strings.
- ES6+ syntax throughout.
- No premature abstractions: one implementation doesn't need an interface, one
  product doesn't need a factory, one config value doesn't need a constant file.
