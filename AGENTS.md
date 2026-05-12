# AGENTS.md

## Architecture

Two-system football data analysis platform, fully Dockerized:

| System | Stack | Port | Purpose |
|--------|-------|------|---------|
| A (`system_a/`) | FastAPI + PostgreSQL + Playwright | 8000 | Data layer: crawling, normalization, REST API |
| B (`system_b/`) | Streamlit (no FastAPI) | 8501 | Analysis layer: X-value calc, ETL, dashboards |

System B pulls data from System A via REST API (`SYSTEM_A_API_URL`). Both share the same PostgreSQL database for raw data; System B uses its own SQLite DB (`db/quant.db`) for derived analysis state.

## Start / Stop / Status

```bash
./start.sh    # build images + docker compose up (Linux/Mac, uses sudo)
./stop.sh     # docker compose down
./status.sh   # service health checks
```

On Linux, `start.sh` uses `sudo` for both `docker compose build` and `docker compose up`. If Docker is configured for rootless access, you may need to modify the script.

## Project Layout

```
system_a/
  api/main.py        # FastAPI app entrypoint (uvicorn api.main:app)
  api/routes/        # leagues, matches, odds, crawl, x_values, settlement
  admin/routes.py    # HTML admin panel (separate router)
  config/            # settings.py (pydantic-settings), database.py, models.py
  scraper/           # odds_crawler, league_crawler, team_normalizer, handicap_normalizer
  modules/           # settlement_calculator
  tests/             # pytest (3 test files)
  test_app.py        # standalone smoke test (python test_app.py)

system_b/
  app.py             # Streamlit entrypoint (streamlit run app.py)
  core/              # Main ETL/analysis — IMPORT: `from core import ...` always
  modules/           # data_connector, follow_list, auto_sync, x_calculator, settlement
  views/             # Streamlit page wrappers (imported by app.py via st.Page)
  app_pages/         # Extra Streamlit pages (system_sync, task_list)
  original_pages/    # Full page implementations (the actual page logic)
  config/            # settings.py, default_params.json, report_templates/
  utils/             # excel_io, migration, default_params, system_a_mapper
  tests/             # pytest (30+ test files)
  db/                # SQLite DB files (gitignored, .gitkeep present)
  core.1/            # EMPTY — stale directory, do not use
  pages_backup/      # EMPTY — stale directory, do not use
```

**Important**: `src/` at the repo root is empty (vestige). All code lives in `system_a/` and `system_b/`.

## System B Import Rules (CRITICAL)

System B uses **absolute imports from the project root** (`system_b/`). The entrypoint `app.py` adds the project root to `sys.path`:

```python
from core import ETLPipeline          # ✅ correct
from core.pipeline import ETLPipeline # ✅ also works
from modules.data_connector import get_connector  # ✅ correct
from config.settings import get_settings          # ✅ correct
from views.home import ...            # ✅ correct
```

**Never** use relative imports like `from .core import` inside System B.

**Do not** use `from etl import` — the ETL code was migrated to `core/`. Anything referencing `etl/` is stale.

## Commands

```bash
# System A tests
cd system_a && pytest

# System B tests (skips tests/tests/ subdir — those are duplicates)
cd system_b && pytest tests/ --ignore=tests/tests

# Or with the script
cd system_b && bash run_tests.sh

# Start single service (without full docker compose)
cd system_a && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
cd system_b && streamlit run app.py --server.port 8501

# Docker logs
docker compose logs -f system_a system_b
```

## Testing

- No CI/CD configured (no `.github/workflows/`)
- No tox, `pyproject.toml`, or `pytest.ini`
- System B tests use **property-based testing** with `hypothesis` (files with `_properties` suffix)
- `system_b/tests/tests/` contains duplicate test files — the `run_tests.sh` explicitly ignores it
- System A test files live in both `system_a/tests/` and `system_a/test_app.py` (standalone smoke test)

## Dependencies & Environment

- `.env` is gitignored. Use `.env.example` as template.
- System B Dockerfile extends System A's image (`FROM football_system-system_a:latest`)
- No linter or formatter config (no `.flake8`, `.ruff.toml`, `pyproject.toml`)
- No type checking config (`mypy`, `pyright`)

## File Name Convention

- Chinese filenames are used throughout (pages, views, docs)
- Streamlit page files in `original_pages/` used to follow `数字_功能.py` naming (e.g., `5_ETL執行.py`). Modern pages are in `views/` with English names (e.g., `dashboard.py`).
- Streamlit navigation is defined in `app.py` via `st.Page()` — do NOT rely on folder-based auto-navigation.

## Data Flow Gotchas

- System A scrapes data from `titan007.com` using `requests` (not Playwright — the `CLAUDE.md` is wrong; check `odds_crawler.py` — it uses `requests` with retry adapters)
- System B ETL pipeline operates on `match_records` table (preprocessed, settled matches), not raw scraped data
- Both systems have auto-sync via `apscheduler`, but System B only starts the scheduler when `IS_DOCKER` env var is NOT set
- Settlement calculation exists in both systems: `system_a/modules/settlement_calculator.py` and `system_b/modules/settlement_calculator.py` — they may differ

## Anti-Patterns

- **Do not use `as any`, `@ts-ignore`**, or similar type-suppression — this is Python, not TypeScript
- **Do not** create files in `system_b/core.1/` or `system_b/pages_backup/` — both are stale/empty
- **Do not** use relative imports in System B
- **Do not** modify `system_b/tests/tests/` — those are duplicate tests