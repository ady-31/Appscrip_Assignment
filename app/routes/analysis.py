from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.dependencies import enforce_rate_limit, resolve_identity
from app.core.logging_config import get_logger, now_ms
from app.core.runtime import get_runtime
from app.core.schemas import AnalysisEnvelope
from app.services.ai_pipeline import AIPipelineService
from app.services.data_collection import DataCollectionService
from app.services.report_generation import ReportGenerationService
from app.utils.sector_normalizer import SUPPORTED_SECTORS, normalize_sector

router = APIRouter(prefix="/analyze", tags=["analysis"])
logger = get_logger(__name__)

settings = get_settings()
runtime = get_runtime()
cache = runtime.cache
rate_limiter = runtime.rate_limiter


def _build_cache_key(sector: str) -> str:
    return f"sector:{sector}"


@router.get("/{sector}", response_model=AnalysisEnvelope)
async def analyze_sector(sector: str, request: Request, identity: str = Depends(resolve_identity)) -> AnalysisEnvelope:
    """Analyze an Indian sector and return a markdown intelligence report."""

    start_ms = now_ms()
    normalized = normalize_sector(sector)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Unknown sector.",
                "supported_sectors": sorted(SUPPORTED_SECTORS),
            },
        )

    await enforce_rate_limit(identity, rate_limiter)

    cache_key = _build_cache_key(normalized)
    cached = await cache.get(cache_key)
    if cached:
        cached["from_cache"] = True
        logger.info(
            "analysis_cache_hit",
            extra={
                "extra_data": {
                    "sector": normalized,
                    "identity": identity,
                    "latency_ms": round(now_ms() - start_ms, 2),
                    "path": request.url.path,
                }
            },
        )
        return AnalysisEnvelope.model_validate(cached)

    warnings: list[str] = []

    data_service = DataCollectionService(settings)
    ai_service = AIPipelineService(settings)
    report_service = ReportGenerationService()

    try:
        signals = await data_service.collect_signals(normalized)
    except Exception as exc:
        cached_fallback = await cache.get(cache_key)
        if cached_fallback:
            cached_fallback["from_cache"] = True
            cached_fallback.setdefault("warnings", []).append(
                "Live data collection failed; served recent cached analysis."
            )
            logger.warning(
                "analysis_data_failed_cache_fallback",
                extra={
                    "extra_data": {
                        "sector": normalized,
                        "identity": identity,
                        "error": str(exc),
                    }
                },
            )
            return AnalysisEnvelope.model_validate(cached_fallback)

        warnings.append("Live data collection failed; analysis uses partial fallback signals.")
        logger.error(
            "analysis_data_failed_partial",
            extra={
                "extra_data": {
                    "sector": normalized,
                    "identity": identity,
                    "error": str(exc),
                }
            },
        )
        signals = data_service._fallback_signals(normalized)

    stage1, stage2, stage3, pipeline_warnings = await ai_service.run_pipeline(normalized, signals)
    warnings.extend(pipeline_warnings)

    markdown = report_service.build_markdown(normalized, stage1, stage2, stage3, warnings)

    response_payload = AnalysisEnvelope(
        sector=sector,
        normalized_sector=normalized,
        generated_at=datetime.now(timezone.utc),
        markdown_report=markdown,
        from_cache=False,
        warnings=warnings,
    )

    await cache.set(cache_key, response_payload.model_dump(mode="json"))

    latency_ms = round(now_ms() - start_ms, 2)
    logger.info(
        "analysis_completed",
        extra={
            "extra_data": {
                "sector": normalized,
                "identity": identity,
                "latency_ms": latency_ms,
                "path": request.url.path,
                "warning_count": len(warnings),
            }
        },
    )

    return response_payload
