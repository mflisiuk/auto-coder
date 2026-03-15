# PROJECT.md

## Tech Stack

- Python 3.12
- FastAPI
- Jinja2 templates
- SQLAlchemy
- Alembic
- pytest
- Ruff

## Repo Structure

```text
app/
  main.py
  db.py
  models.py
  routes/
  services/
  templates/
  static/
migrations/
tests/
scripts/
```

## Commands

### Install

```bash
uv sync
```

### Run App

```bash
uv run uvicorn app.main:app --reload
```

### Run Tests

```bash
uv run pytest tests/
```

### Run Lint

```bash
uv run ruff check .
```

## Editable Paths

- `app/`
- `tests/`
- `migrations/`
- `scripts/`

## Protected Paths

- `.github/`
- `infra/`
- `deploy/`
- `secrets/`
- `.env`

## Environment Assumptions

- local development uses SQLite
- database URL is provided through `DATABASE_URL`
- no external queue or cache exists in v1
