---
title: Frontend Design Standard
description: Layout, spacing, colors, cards, responsive behavior, global CSS, fonts, and styling-system configuration.
read_when:

* Changing page layout
* Changing card design
* Changing spacing, colors, radius, typography, or responsive behavior
* Refactoring visual UI code
avoid_when:

* Only changing API logic
* Only changing TypeScript types
* Only changing business logic
---

# Frontend Design Standard

## Quick rules

* Pages should be thin. Layout padding and max-width belong in route layouts.
* Reuse shared primitives for page headings and repeated visual patterns.
* Establish a small, documented scale for card surfaces, nesting, spacing, and
  responsive breakpoints; use it consistently.
* Prefer parent layout gaps over child spacing hacks.
* Use the styling system's supported composition mechanism for dynamic classes;
  do not concatenate class names in fragile ways.
* Use design tokens instead of repeated arbitrary colors and sizes.
* Pressable cards must have hover feedback.
* Card grids should use sibling skeleton components, not inline skeleton blocks.

## Details

This document codifies UI patterns as the standard for all new and refactored
frontend code. Existing routes that do not follow these rules are tech debt to
be migrated.

### Pages are thin; layouts own the chrome

A route entry file renders content only. It does not define global shell chrome,
outer padding, or max-width containers when those concerns belong to a shared
layout boundary.

### Shared components live in `components/`

Use the project's shared component, primitive, loading, and route-local
directories. If a component is used by multiple consumers, put it in the shared
area; if only one route uses it, keep it route-local.

### Card system

- Define primary and secondary surface treatments in the design system.
- Use stronger visual treatments for emphasis, not for every content surface.
- Make nesting, borders, radius, and elevation visually predictable.

Pressable cards must declare hover feedback. Gradient cards that are pressable
must also have a hover state.

Repeated content components should have a reusable loading representation in
the project's loading/skeleton area. Do not duplicate large loading blocks in
pages or use a generic placeholder when layout stability matters.

### Class composition and spacing

Use bare strings for static classes and template literals for dynamic ones.
Do not use `[array].join(' ')`.

Prefer `gap-*` on the parent over `space-y-*` / `space-x-*` on children.

### Responsive behavior

Use the project's smaller breakpoint for component-internal sizing and larger
breakpoints for page-level layout changes. Avoid adding breakpoints without a
design requirement.

### Gradient syntax

Use the current syntax of the selected styling system; do not mix deprecated
and current forms.

### Global CSS and theme configuration

* Keep global CSS limited to resets, semantic element defaults, third-party
  library overrides, and truly global utilities. Prefer component classes for
  route-specific styling.
* Keep fonts, semantic text sizes, colors, radii, and breakpoints in the Tailwind
  or design-system configuration. Do not scatter duplicate magic values through
  JSX or CSS.
* When using a UI library theme, define light/dark tokens in one configuration
  and consume semantic classes such as `primary`, `secondary`, `danger`, and
  `success`.
* Import global CSS once from the root layout. Avoid importing global CSS from
  components or route partials.
* Scope third-party overrides to the library selector and document why elevated
  `z-index`, `!important`, or other escape hatches are required.
* Load fonts through the framework font integration and expose them as CSS
  variables; keep fallback fonts defined.

### Dark mode and responsive behavior

* Design both light and dark states for text, borders, surfaces, focus rings,
  and status colors when dark mode is enabled.
* Use mobile-first styles. Keep component sizing and page layout changes tied to
  the project's documented breakpoint roles unless a measured design
  requirement says otherwise.
* Interactive states include hover, focus-visible, disabled, pending, and error;
  do not remove visible focus indicators.

### Heading component

Use the shared heading primitive for repeated page title patterns. Do not
duplicate heading markup when a project-level primitive exists.

### Checklist for new pages

- Entry file does not duplicate shared shell chrome.
- Shared primitives are reused.
- Surface treatments follow the project's token scale.
- Loading, empty, error, and success states are deliberate.
- Dynamic classes use the styling system's supported composition pattern.
- Interactive elements define hover, focus-visible, disabled, pending, and error states.
