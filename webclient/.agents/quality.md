---
title: Frontend Quality Baseline
description: Accessibility, UI states, checks, and safe delivery practices.
read_when:

* Adding a feature, form, table, async state, or interactive control
* Reviewing a change before commit or deployment
---

# Frontend Quality Baseline

## Required UI states

Async screens define loading, error, empty, and success states. Use the
project's shared loading/skeleton pattern for repeated content; do not leave a
blank screen or use a generic loading paragraph.

Forms define labels, validation messages, disabled/pending behavior, submit
failure feedback, and successful completion behavior. Preserve entered values
when a recoverable request fails.

## Accessibility

* Prefer semantic HTML and native controls.
* Every input has an accessible label; icon-only buttons have an accessible name.
* Keyboard users can reach and operate every interactive control.
* Dialogs manage focus and close behavior; destructive actions require clear
  confirmation.
* Do not rely on color alone for status or errors. Respect reduced motion when
  adding animation.
* Images have meaningful alt text or an explicit empty alt for decoration.

## Verification

Run the smallest relevant check after editing, then the project's configured
lint, typecheck, test, and build commands. Use the repository's wrappers when
they exist. Run a production build for routing, environment, or build-system
changes.

Review the diff after auto-fix. Do not commit generated output, `.env` files,
tokens, or unrelated formatting churn. Add one focused test or runnable check
for non-trivial parsing, permissions, validation, or state-transition logic.
