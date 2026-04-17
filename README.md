# Trade Opportunity Intelligence API

Production-oriented FastAPI backend for sector-level trade intelligence focused on Indian markets.

## Why This Architecture

This project intentionally avoids a single prompt endpoint. Instead, it uses a modular pipeline with clear separation of concerns:

- `routes/`: API contract and request orchestration
- `services/`: data collection, AI pipeline, report rendering
- `core/`: settings, schemas, caching, rate limiting, dependencies, logging
- `utils/`: sector normalization and deterministic sentiment scoring

## Core Endpoint

- `GET /analyze/{sector}`

Example:

```bash
curl -X GET "http://127.0.0.1:8000/analyze/tech" -H "X-API-Key: demo-user-1"
```

## Pipeline Design

1. Stage 1: summarize normalized multi-source signals.
2. Stage 2: extract trends and sentiment with explainability.
3. Stage 3: produce opportunities and risk factors.
4. Stage 4: synthesis pass to refine final recommendation consistency.

Each insight includes:

- reasoning
- confidence score (0-100)
- source reference

## Advanced Capabilities Included

- Async parallel data fetching (`asyncio.gather`)
- Config-driven design with `.env` support (`pydantic-settings`)
- Redis-backed sector cache with resilient in-memory fallback
- Redis-backed per-identity rate limiting (5 req/min) with resilient in-memory fallback
- Structured JSON logging with latency/error fields
- OpenTelemetry tracing (OTLP HTTP exporter)
- Input intelligence with synonym normalization and strict validation
- Resilient fallback behavior for external API failure
- Unit + integration tests

## Setup

1. Create and activate a virtual environment.
2. Install deps:

```bash
pip install -r requirements.txt
```

3. Configure environment:

```bash
copy .env.example .env
```

4. Add API keys if available:

- `GEMINI_API_KEY` for multi-stage AI execution
- `NEWS_API_KEY` for live news ingestion

Without keys, the service still runs using deterministic fallback and mock signals.

5. Optional: run with Redis + tracing by setting in `.env`:

```env
USE_REDIS=true
REDIS_URL=redis://localhost:6379/0
ENABLE_TRACING=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

## Run

```bash
uvicorn app.main:app --reload
```

Windows PowerShell using this repo venv:

```powershell
Set-Location "g:\Drive Assignment"
& "g:/Drive Assignment/.venv/Scripts/python.exe" -m uvicorn app.main:app --reload
```

Optional Redis (Docker):

```bash
docker run --name trade-intel-redis -p 6379:6379 -d redis:7
```

## Render Deploy Note

This repository includes `runtime.txt` pinned to Python 3.11.9 to ensure binary wheel compatibility for `pydantic-core` and avoid Rust source builds on restricted build environments.
If your Render service still shows Python 3.14 in logs, set environment variable `PYTHON_VERSION=3.11.9` and redeploy with cleared build cache.

## Test

```bash
pytest
```

Run only integration tests:

```bash
pytest tests/test_integration_api.py -q
```

## Example Response Shape

```json
{
  "sector": "tech",
  "normalized_sector": "information_technology",
  "generated_at": "2026-04-17T14:22:11.482967+00:00",
  "markdown_report": "# Sector Intelligence Report\\n...",
  "from_cache": false,
  "warnings": []
}
```

## Observability

- Structured logs include request path, sector, identity, latency, warning count, and error details.
- If `ENABLE_TRACING=true`, spans are exported through OTLP HTTP to `${OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces`.

## Notes on Production Hardening

For multi-instance deployment, keep Redis enabled and point tracing to your collector (for example: OpenTelemetry Collector, Jaeger, or Tempo).
