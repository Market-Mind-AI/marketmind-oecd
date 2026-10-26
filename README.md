# MarketMind OECD

Microservice for consuming OECD public data via the SDMX API.

## What This Service Does

- Discovers OECD datasets/dataflows via the SDMX REST API
- Queries the structure (dimensions, codelists) of datasets
- Collects economic observations (time series data)
- Manages an internal catalog of relevant OECD indicators
- Normalizes SDMX responses into clean, flat records
- Persists raw API responses (JSONB) for auditability
- Persists normalized data for downstream consumption
- Exposes stored series, freshness and a stale-refresh pass over REST, with full traceability (ingestion_run_id, oecd_request_id)

## What This Service Does NOT Do

- Does NOT calculate MOS (Market Opportunity Score)
- Does NOT calculate Rank Order Centroid weights or TOPSIS
- Does NOT use LLMs
- Does NOT know about Semantic Layer
- Does NOT know about MarketMind final rules or dimensions

It exclusively collects, normalizes, stores, and delivers OECD economic data.

## Architecture

```text
app/
  api/routes/          # FastAPI route handlers (no business logic)
  core/                # Config, logging, exceptions
  domain/              # Enums and domain entities
  clients/             # OECD SDMX API client (httpx)
  services/            # Orchestration: client + normalization + persistence
  repositories/        # Database access layer
  db/models/           # SQLAlchemy models
  schemas/             # Pydantic request/response schemas
  utils/               # SDMX parsing, normalization, time utilities
tests/                 # Pytest test suite
alembic/               # Database migrations
```

## Stack

- Python 3.12, FastAPI, Pydantic v2
- httpx (async HTTP client with retry/backoff)
- SQLAlchemy 2.0 (async, asyncpg), Alembic
- PostgreSQL 16
- Docker, Docker Compose
- Poetry

## How to Run Locally

### Prerequisites

- Python 3.12+
- Poetry
- PostgreSQL 16 (or use Docker)

### Install Dependencies

```bash
poetry install
```

### Configure Environment

```bash
cp .env.example .env
# Edit .env if needed (DATABASE_HOST=localhost when Postgres runs on the host)
```

### Run Migrations

```bash
alembic upgrade head
```

### Start the Server

```bash
uvicorn app.main:app --reload
```

## How to Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts:

- **marketmind-oecd-api** on host port `${APP_PORT}` (8001 in `.env.example`; the container listens on 8000)
- **PostgreSQL 16** on host port 5432

Migrations run automatically when the container starts (`alembic upgrade head`).

pgAdmin was consolidated into `marketmind-scoring` (single instance pointing at
all 5 services' databases). See `marketmind-scoring/README.md`.

## Access Points

| Service | URL |
|---------|-----|
| Swagger UI | `http://localhost:8001/docs` |
| ReDoc | `http://localhost:8001/redoc` |
| OpenAPI JSON | `http://localhost:8001/openapi.json` |

## Environment Variables

| Variable | Default in code | Description |
|----------|-----------------|-------------|
| `APP_NAME` | marketmind-oecd | Service name |
| `APP_ENV` | local | Environment |
| `APP_PORT` | — | Host port mapped by `docker-compose.yml` only (8001 in `.env.example`); the app itself does not read it |
| `DATABASE_HOST` | localhost | PostgreSQL host (`postgres` in `.env.example`) |
| `DATABASE_PORT` | 5432 | PostgreSQL port |
| `DATABASE_NAME` | marketmind_oecd | Database name |
| `DATABASE_USER` | marketmind | Database user |
| `DATABASE_PASSWORD` | marketmind_password | Database password |
| `DATABASE_SSL_MODE` | disable | `disable`, `require` or `verify-full` (Azure needs at least `require`) |
| `OECD_BASE_URL` | https://sdmx.oecd.org/public/rest/v1 | OECD SDMX base URL |
| `DEFAULT_TIMEOUT` | 60 | HTTP timeout (seconds), same in every collector |
| `DEFAULT_RETRIES` | 5 | Attempts per call, same in every collector |
| `DEFAULT_BACKOFF` | 2 | First wait (seconds); doubles per attempt, with jitter, capped at 60 s |
| `LOG_LEVEL` | INFO | Log level |

## Endpoints

### Health & Info

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Liveness: is the process up (no DB access) |
| GET | `/health` | Readiness: health check with DB connectivity |
| GET | `/version` | Service version info |

### OECD Data

| Method | Path | Description |
|--------|------|-------------|
| POST | `/dataflows` | Discover available OECD dataflows |
| POST | `/datastructure` | Get structure of a dataflow |
| POST | `/observations` | Collect observations from a dataflow |
| POST | `/indicators/catalog` | Create/update indicator catalog |
| GET | `/indicators/catalog` | List indicator catalog |
| POST | `/indicators/catalog/seed` | Seed the 4 default MarketMind indicators |
| POST | `/indicators/collect` | Collect data for cataloged indicators |
| GET | `/observations/series` | Read one stored series for one country (`country`, `measure` or `indicator_code`, optional `frequency`, `limit`) |
| GET | `/freshness` | What is stored and when it was last checked (`country`, `indicator`, `stale_after_days`, `only_stale`) |
| POST | `/maintenance/refresh-stale` | Collect again every country whose last check is older than `stale_after_days` (default 90); `limit`, `fail_if_incomplete`, `years_back` (default 10) |
| GET | `/requests/{id}` | Get stored request with data |
| GET | `/runs/{id}` | Get ingestion run status |

Consumers (e.g. `marketmind-scoring`) read this service over HTTP (`/observations/series`,
`/freshness`); they do not connect to its database.

## Indicator Catalog

`POST /indicators/catalog/seed` registers the four entries of `SEED_INDICATORS`
(`app/services/oecd_service.py`). Only the two with a `dataflow_id` can be collected;
`POST /indicators/collect` rejects the other two with "missing dataflow_id" until someone
maps them to a real dataflow.

| Code | Name | Dimension | Dataflow | Collectable |
|------|------|-----------|----------|-------------|
| `CPI` | Consumer Price Index | macroeconomic_risk | `DSD_PRICES@DF_PRICES_ALL` | yes |
| `RHP` | Real House Price Index | economic_readiness | `DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES` | yes |
| `UNEMP` | Unemployment Rate | macroeconomic_risk | none (`dataflow_id` None) | no |
| `CCI` | Consumer Confidence Indicator | economic_readiness | none (`dataflow_id` None) | no |

For `CPI` and `RHP` the service builds a scoped SDMX key (REF_AREA=country, MEASURE=code,
every other dimension wildcarded) instead of downloading the whole dataflow. OECD REF_AREA
codes are ISO-3 (`ESP`, not `ES`).

## Examples

### Discover Dataflows

```bash
curl -X POST http://localhost:8001/dataflows \
  -H "Content-Type: application/json" \
  -d '{"agency_id": "OECD", "detail": "allstubs"}'
```

### Get Dataflow Structure

```bash
curl -X POST http://localhost:8001/datastructure \
  -H "Content-Type: application/json" \
  -d '{"agency_id": "OECD", "dataflow_id": "DSD_PRICES@DF_PRICES_ALL"}'
```

### Seed the Catalog, then Collect

```bash
curl -X POST http://localhost:8001/indicators/catalog/seed

curl -X POST http://localhost:8001/indicators/collect \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ESP",
    "start_period": "2020",
    "end_period": "2026",
    "indicator_codes": ["CPI", "RHP"]
  }'
```

### Collect Observations Directly from a Dataflow

```bash
curl -X POST http://localhost:8001/observations \
  -H "Content-Type: application/json" \
  -d '{
    "dataflow_id": "DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES",
    "country": "ESP",
    "indicator_code": "RHP",
    "start_period": "2020",
    "end_period": "2026",
    "query_key": "ESP.Q.RHP."
  }'
```

### Register or Update a Catalog Entry

```bash
curl -X POST http://localhost:8001/indicators/catalog \
  -H "Content-Type: application/json" \
  -d '{
    "indicators": [
      {
        "indicator_code": "CPI",
        "indicator_name": "Consumer Price Index",
        "category": "inflation",
        "expected_unit": "percentage",
        "marketmind_dimension": "macroeconomic_risk",
        "dataflow_id": "DSD_PRICES@DF_PRICES_ALL"
      }
    ]
  }'
```

### Read a Stored Series

```bash
curl "http://localhost:8001/observations/series?country=ESP&measure=RHP&frequency=Q&limit=8"
```

### Check Freshness and Refresh What Is Stale

```bash
curl "http://localhost:8001/freshness?country=ESP&stale_after_days=90&only_stale=true"

curl -X POST http://localhost:8001/maintenance/refresh-stale \
  -H "Content-Type: application/json" \
  -d '{"stale_after_days": 90, "fail_if_incomplete": true}'
```

## How to Discover OECD Dataflows

1. Call `POST /dataflows` to list all available dataflows
2. Search the results for the indicator you need (prices, house prices, unemployment, ...)
3. Call `POST /datastructure` with the `dataflow_id` to understand dimensions and codes
4. Use the dimension values (REF_AREA codes, MEASURE codes) to build your `POST /observations` request, or add the dataflow to the catalog with its `dataflow_id`

## How to Run Tests

```bash
pytest                 # unit tests, all external calls mocked
pytest -v              # verbose
pytest --cov=app       # with coverage
```

## Linting & Type Checking

```bash
ruff check .
black .
mypy .
```

## OECD SDMX API

Base URL: `https://sdmx.oecd.org/public/rest/v1`

The OECD Data Explorer provides free programmatic access using the SDMX standard.

### SDMX Limitations

- Response format varies across datasets (series vs flat observations)
- Some datasets have complex dimension structures
- Time period formats vary (2026, 2026-Q1, 2026-01)
- Not all datasets support all query parameters
- Rate limits apply; see the collection rules below

## Collection rules (the same in every MarketMind collector)

- **Retries** (`app/utils/retry.py`): 408, 429, any 5xx, timeouts and network errors are retried, up to
  `DEFAULT_RETRIES` attempts, waiting `DEFAULT_BACKOFF` seconds doubled per attempt, with jitter, capped at
  60 s; a `Retry-After` header is honoured up to the same cap. Other 4xx are never retried.
- **HTTP status**: `422` when the request names an indicator the catalog does not have, or one without a
  `dataflow_id` (the only caller error); `503` when the source stayed down through every attempt; `502`
  when the source answered with something unusable; `404` when it has no data (direct endpoints only).
- **A collection that got nothing raises**: if no requested indicator got an answer, `/indicators/collect`
  answers `503` (every failure transient) or `502`, and the run is `failed` -- never a `200` with a failed run.
- **What counts as a check**: one `oecd_requests` row per (country, indicator) that got an answer from the
  source -- data, or a definitive "no data" (a 404). Failed indicators are not checks. Run statuses are
  `running`, `success` and `failed`; there is no `partial`.
- **One value per period**: a new collection replaces the periods it brings, and `/observations/series`
  returns one row per period -- the latest collection's; within one collection, the largest value.
- **Timestamps**: timezone-aware UTC everywhere (`app/utils/time.py`).
- **Refresh**: each stale country is replayed with every indicator from all of its successful runs, over
  the Core's window (`years_back` = 10: from ten years ago to this year); it counts as refreshed only when
  every indicator got an answer.

### Rate Limit Best Practices

- Avoid bursting many requests simultaneously
- Use `start_period`/`end_period` to limit data volume
- Prefer `/indicators/collect` (scoped SDMX key) over `/observations` with `query_key` omitted, which fetches the entire dataflow
- Use `/freshness` and `/maintenance/refresh-stale` instead of re-collecting everything on a schedule

## Database

PostgreSQL 16 with 7 tables:

- `ingestion_runs` — tracks each ingestion job
- `oecd_requests` — tracks each API call; one row per (country, indicator) the source answered is a check
- `raw_api_responses` — stores raw SDMX JSON (JSONB)
- `oecd_dataflows` — discovered dataflows
- `oecd_datastructures` — dataset dimensions and codes
- `oecd_observations` — normalized time series data
- `oecd_indicators_catalog` — internal indicator registry

All tables use UUID primary keys and UTC timestamps. Raw responses are never overwritten; each call generates new history.

Migration `002_create_readonly_role` creates a `marketmind_readonly` Postgres role. It is
legacy: it dates from when `marketmind-scoring` read this database directly. Collectors are
now read over HTTP, so nothing uses the role; the migration is kept only so existing
databases keep a linear revision history (technical debt).

## Team

Final project (TFM) for the *Máster en Ingeniería y Desarrollo de Soluciones de IA Generativa* — **EBIS Business Techschool**. The whole system and how to run it: [marketmind-ai](https://github.com/Market-Mind-AI/marketmind-ai).

- **Miguel Antonio Blanco Salcedo** — [@mikews93](https://github.com/mikews93)
- **Álvaro Augusto De Marco Neto** — [@ironeto](https://github.com/ironeto)
