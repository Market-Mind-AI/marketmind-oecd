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
- Exposes all data via a REST API with full traceability (ingestion_run_id, oecd_request_id)

## What This Service Does NOT Do

- Does NOT calculate MOS (Market Opportunity Score)
- Does NOT calculate Entropy Weight
- Does NOT calculate TOPSIS
- Does NOT use LLMs
- Does NOT know about Semantic Layer
- Does NOT know about MarketMind final rules or dimensions

It exclusively collects, normalizes, stores, and delivers OECD economic data.

## Architecture

```
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
- SQLAlchemy 2.x (async), Alembic
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

### Environment Variables

```bash
cp .env.example .env
# Edit .env if needed
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
- **marketmind-oecd-api** on port 8000
- **PostgreSQL 16** on port 5432
- **pgAdmin 4** on port 5050

### Run Migrations in Docker

```bash
docker compose exec marketmind-oecd-api alembic upgrade head
```

## Access Points

| Service | URL |
|---------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

pgAdmin was consolidated into `marketmind-core` (single instance pointing at
all 5 services' databases). See `marketmind-core/README.md`.

## Endpoints

### Health & Info

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check with DB connectivity |
| GET | `/version` | Service version info |

### OECD Data

| Method | Path | Description |
|--------|------|-------------|
| POST | `/dataflows` | Discover available OECD dataflows |
| POST | `/datastructure` | Get structure of a dataflow |
| POST | `/observations` | Collect observations from a dataflow |
| POST | `/indicators/catalog` | Create/update indicator catalog |
| GET | `/indicators/catalog` | List indicator catalog |
| POST | `/indicators/collect` | Collect data for cataloged indicators |
| GET | `/requests/{id}` | Get stored request with data |
| GET | `/runs/{id}` | Get ingestion run status |

## Examples

### Discover Dataflows

```bash
curl -X POST http://localhost:8000/dataflows \
  -H "Content-Type: application/json" \
  -d '{"agency_id": "OECD", "detail": "allstubs"}'
```

### Get Dataflow Structure

```bash
curl -X POST http://localhost:8000/datastructure \
  -H "Content-Type: application/json" \
  -d '{"agency_id": "OECD", "dataflow_id": "DF_CCI"}'
```

### Collect Observations

```bash
curl -X POST http://localhost:8000/observations \
  -H "Content-Type: application/json" \
  -d '{
    "dataflow_id": "DF_CCI",
    "country": "ES",
    "indicator_code": "CCI",
    "start_period": "2020",
    "end_period": "2026"
  }'
```

### Register Indicators in Catalog

```bash
curl -X POST http://localhost:8000/indicators/catalog \
  -H "Content-Type: application/json" \
  -d '{
    "indicators": [
      {
        "indicator_code": "CCI",
        "indicator_name": "Consumer Confidence Indicator",
        "category": "consumer_confidence",
        "expected_unit": "index",
        "marketmind_dimension": "economic_readiness",
        "dataflow_id": "DF_CCI"
      }
    ]
  }'
```

### Collect Cataloged Indicators

```bash
curl -X POST http://localhost:8000/indicators/collect \
  -H "Content-Type: application/json" \
  -d '{
    "country": "ES",
    "start_period": "2020",
    "end_period": "2026",
    "indicator_codes": ["CCI"]
  }'
```

## How to Discover OECD Dataflows

1. Call `POST /dataflows` to list all available dataflows
2. Search the results for relevant indicators (CCI, unemployment, inflation, etc.)
3. Call `POST /datastructure` with the `dataflow_id` to understand dimensions and codes
4. Use the dimension values (REF_AREA codes, INDICATOR codes) to build your `POST /observations` request

## How to Run Tests

```bash
pytest
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

### Key Indicators for MarketMind

| Indicator | Category | MarketMind Dimension |
|-----------|----------|---------------------|
| Consumer Confidence | consumer_confidence | economic_readiness |
| Household Disposable Income | disposable_income | purchasing_power |
| Household Consumption | household_consumption | consumption_capacity |
| Inflation (CPI) | inflation | macroeconomic_risk |
| Unemployment Rate | unemployment | macroeconomic_risk |
| Retail Sales | retail_sales | consumption_capacity |

### SDMX Limitations

- Response format varies across datasets (series vs flat observations)
- Some datasets have complex dimension structures
- Time period formats vary (2026, 2026-Q1, 2026-01)
- Not all datasets support all query parameters
- Rate limits apply; the client implements retry with exponential backoff

### Rate Limit Best Practices

- Avoid bursting many requests simultaneously
- Use `startPeriod` and `endPeriod` to limit data volume
- The client automatically retries on 429 with Retry-After header
- Default: 3 retries with exponential backoff (factor=2)
- Cache dataflow/structure responses when possible

## Database

PostgreSQL 16 with 7 tables:

- `ingestion_runs` — tracks each ingestion job
- `oecd_requests` — tracks each API call
- `raw_api_responses` — stores raw SDMX JSON (JSONB)
- `oecd_dataflows` — discovered dataflows
- `oecd_datastructures` — dataset dimensions and codes
- `oecd_observations` — normalized time series data
- `oecd_indicators_catalog` — internal indicator registry

All tables use UUID primary keys and UTC timestamps. Raw responses are never overwritten; each call generates new history.
