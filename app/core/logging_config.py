import json
import logging
import time
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Render logs as JSON lines to simplify ingestion by log systems."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            payload.update(record.extra_data)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """Allow passing arbitrary context fields without manual string formatting."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        extra_data = extra.setdefault("extra_data", {})
        extra_data.update(self.extra)
        return msg, kwargs


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())


def get_logger(name: str, **extra: Any) -> StructuredLoggerAdapter:
    return StructuredLoggerAdapter(logging.getLogger(name), extra)


def now_ms() -> float:
    return time.perf_counter() * 1000
