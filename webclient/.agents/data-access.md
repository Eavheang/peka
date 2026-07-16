---
title: Data Access and State
description: Request clients, data-access hooks, server-state conventions, validation, and cache behavior.
read_when:

* Adding or changing an API call, query, mutation, upload, or download
* Handling request errors, auth refresh, caching, or invalidation
* Choosing between local state, the project's server-state solution, and a utility
---

# Data Access and State

## Layers

* A dedicated data-access layer owns domain API calls. Components do not
  construct requests inline.
* Separate authenticated and unauthenticated request paths when the project
  needs both. Keep token attachment and refresh behavior in the request layer.
* Utilities contain pure transformations only. Do not hide network calls in a
  utility function.
* Use the project's server-state solution for remote data and local state for
  ephemeral UI state such as dialogs, input text, or selected tabs.

## Query rules

* Query/cache keys are stable and include every input that changes the response
  when the selected data library uses query keys.
* Do not run a request until required identifiers or prerequisites exist.
* Pass cancellation signals when the data library and transport support them.
* Return typed domain data; do not leak transport response objects to UI code.
* Set explicit stale/refetch behavior for expensive or user-specific data.

## Mutation rules

* Type mutation variables and responses separately from form UI state.
* Invalidate the smallest affected query keys in `onSuccess`.
* Keep optimistic updates only when rollback behavior is defined; otherwise
  invalidate and refetch.
* Disable duplicate submissions while a mutation is pending.
* Show user-safe feedback for expected failures. Log diagnostic details without
  exposing tokens, credentials, or private response payloads.

## Trust boundaries

* Validate user input at the form boundary with the project's schema/tooling.
* Treat URL params, query params, file metadata, API responses, and decoded
  tokens as untrusted data.
* Validate response shapes when an invalid response could break rendering or
  security decisions.
* Uploads and downloads must enforce size/type rules and release object URLs.
