---
title: Component Organization
description: Rules for shared components, route partials, hooks, form inputs, and naming.
read_when:

* Creating, moving, or refactoring a component
* Deciding between shared components and route-local components
* Changing form component structure or shared component props
avoid_when:

* Only changing page layout or visual design
* Only changing API logic or TypeScript types
* Only changing non-component business logic
---

# Component Organization

## Quick rules

* Shared components live in the shared component directory; route-specific
  pieces live in the route-local partial directory.
* If a component is used by 2+ routes, put it in `components/`.
* Shared components should stay reusable: no route-local data fetching or route-specific translation assumptions inside them.
* Route-specific partials may use route-local hooks.
* Reuse shared primitives for repeated concerns such as page headings.
* Follow the selected form library's field integration pattern; do not mix
  controlled and uncontrolled approaches without a reason.
* Reusable form inputs accept field state and callbacks; they do not submit forms or call APIs.
* Keep components minimal; avoid unnecessary props and boolean flags.
* Leaf components expose events through callbacks only; their nearest orchestration parent owns stores, dialogs, and actions.
* Do not drill callbacks through intermediate components that do not use them; the orchestrating parent should call context hooks directly.
* Use `clsx` for `className` composition.
* Prefer named exports for shared components.
* Add `'use client'` only when component behavior needs browser APIs, state, effects, or event handlers.

## Details

### File placement

| Usage | Location |
|---|---|
| Reusable across 2+ routes | shared component directory |
| Single route only | route-local partial directory |

The exact directory names and whether route groups or underscore-prefixed
partial directories are used are project decisions. Document them in the
project's root instructions, not in this reusable baseline.

### Component structure

A shared component should contain only types, props, and render logic.
Do not call route-local hooks, fetch route data, or assume route-specific
translations inside shared components.

Leaf UI components (for example, `Card`) expose events through callbacks only;
they do not access dialogs, stores, or APIs. The nearest parent layer (for
example, `Shell`) owns orchestration: reading stores, opening dialogs, and
calling actions. Do not drill callbacks through intermediate components that do
not need them. Use context hooks directly in the orchestrating parent instead;
context hooks return stable references and are safe to call inside `.map()`.

Route-local components may use route-local hooks, data hooks, and translation
hooks because they are not shared.

Use a shared `Heading` component for page titles instead of inlining `<h1>` + `<p>`.

### Form components

Use the chosen form library's reusable field adapter instead of duplicating
registration, error, and accessibility wiring in every form.

Form fields expose label, error, required, disabled, and described-by semantics
through accessible HTML. Route-level forms own schema, submit mutation, and
success/error feedback; field components own rendering only.

### Hooks

Put reusable browser behavior in `hooks/`. Hooks must not hide unrelated API
calls, navigation, or global side effects. Keep pure parsing/formatting in
`utils/` so it can run without React.

### Code style

- Single quotes, not double quotes.
- Components should be minimal. Avoid unnecessary props and boolean flags.
- Use `clsx` for `className` composition, not array `.join(' ')`.
- Order props by category: content/functionality first, then callback/action,
  then boolean props, then dialog/modal props.

### Naming conventions

- Shared and route-local component naming follows the conventions selected by
  the project. Keep the distinction consistent.
