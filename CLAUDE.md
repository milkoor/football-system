# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a football data analysis system with two main components:

- **System A**: Data infrastructure (crawlers, data normalization, PostgreSQL DB, FastAPI backend)
- **System B**: Quantitative analysis platform (X-value calculation, ETL pipeline, Streamlit frontend)

## Architecture

```
┌─────────────────────────────────────────┐
│           System A (Data Layer)         │
│  FastAPI + PostgreSQL + Playwright      │
│  (Port 8000)                            │
└────────────────┬────────────────────────┘
                 │ REST API
                 ▼
┌─────────────────────────────────────────┐
│         System B (Analysis Layer)       │
│  Streamlit + X-value Calculation + ETL  │
│  (Port 8501)                            │
└─────────────────────────────────────────┘
```

## System B Module Structure
- **`system_b/core/`**: Main ETL and analysis logic (previously in `etl/` or `core/core/`; use `from core import ...` for all imports)
- **`system_b/modules/`**: Additional modules like `data_connector`, `follow_list`, `auto_sync`
- **`system_b/views/`**: Streamlit page wrappers
- **`system_b/app_pages/` & `original_pages/`**: Actual Streamlit page implementations
- **`system_b/tests/`**: Pytest tests for System B

## Commands

### Build & Run
```bash
# Start all services
./start.sh          # Linux/Mac
start.bat           # Windows

# Check service status
./status.sh         # Linux/Mac
status.bat          # Windows

# Stop services
./stop.sh           # Linux/Mac
stop.bat            # Windows

# View logs
docker-compose logs -f
```

### Tests
```bash
# System A tests (pytest)
cd system_a && pytest

# System B tests (pytest)
cd system_b && ./run_tests.sh  # Or: pytest tests/ --ignore=tests/tests
```

## Key Directories
- `system_a/`: FastAPI backend, data crawlers, PostgreSQL models
- `system_b/`: Streamlit frontend, X-value calculation, ETL pipeline
- `docs/`: Project documentation (API docs, DB schema, user manual)
