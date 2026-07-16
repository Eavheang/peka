---
title: Authentication, Authorization, and Localization
description: Portable rules for identity, access control, optional localization, and environment variables.
read_when:

* Adding authentication, authorization, roles, protected routes, or sessions
* Adding localization, translation resources, locale selection, or formatting
* Changing environment variables or request boundaries
---

# Authentication, Authorization, and Localization

## Authentication and authorization

* Keep identity-provider configuration in one server-side boundary.
* Protect routes at the earliest server/request boundary available. Client-side
  guards improve UX; they are not authorization.
* Enforce permissions on the API/server too. Hidden navigation is not security.
* Centralize permission metadata when the same rules drive navigation and route
  protection. Keep role names, route names, and provider-specific claims in
  project configuration rather than these general rules.
* Keep credentials, signing keys, and private provider settings server-only.
* Expose only intentionally public environment variables to browser code.
* Preserve return URLs safely and allow redirects only to trusted destinations.
* Never log tokens, cookies, credentials, complete sessions, or sensitive user
  data. Fail closed when a protected identity check cannot be completed.

## Localization (optional)

Localization is optional. If a project supports multiple languages:

* Centralize supported locales, default locale, fallback locale, locale
  detection, and persistence strategy. The strategy may use URL segments,
  cookies, headers, user profile settings, or framework routing.
* Keep user-facing copy in translation resources. Components use stable intent-
  based keys rather than inline duplicated language strings.
* Keep translation setup in one integration boundary and avoid initializing the
  same global client repeatedly.
* Keep locale-specific formatting for dates, numbers, currency, pluralization,
  and direction in the localization layer or shared formatters.
* Do not translate identifiers, API enum values, route paths, or machine keys.
* Every supported locale must provide required keys or a deliberate fallback.
  Test long text, missing translations, interpolation, and right-to-left
  layout when relevant.
* Keep the document language and accessible labels synchronized with active
  locale.

## Environment

* Provide safe variable names and placeholders in the project's example env
  file; keep real values in local or deployment secret storage.
* Validate required variables at startup or at their server boundary.
* Do not hardcode environment-dependent URLs, provider settings, or credentials.
