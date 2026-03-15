# ARCHITECTURE_NOTES.md

## Required Application Shape

The app should remain a server-rendered FastAPI application. Do not introduce a separate SPA frontend in v1.

## Domain Model

The core entity is `FeedbackItem`.

Suggested fields:

- `id`
- `title`
- `description`
- `category`
- `priority_hint`
- `reporter_email`
- `status`
- `owner`
- `created_at`
- `updated_at`
