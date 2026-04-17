import asyncio
from datetime import datetime, timezone

import httpx

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.core.schemas import DataSignal

logger = get_logger(__name__)


class DataCollectionService:
    """Collect sector-level signals from multiple async sources."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def collect_signals(self, sector: str) -> list[DataSignal]:
        tasks = [
            self._fetch_news_signals(sector),
            self._fetch_macro_signals(sector),
            self._fetch_market_snapshot(sector),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: list[DataSignal] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("data_source_failed", extra={"extra_data": {"error": str(result), "sector": sector}})
                continue
            merged.extend(result)

        if not merged:
            return self._fallback_signals(sector)
        return merged

    async def _fetch_news_signals(self, sector: str) -> list[DataSignal]:
        if not self.settings.news_api_key:
            return self._mock_news_signals(sector)

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f"India {sector.replace('_', ' ')} sector",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": self.settings.news_api_key,
        }

        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        items = payload.get("articles", [])
        signals: list[DataSignal] = []
        for article in items:
            signals.append(
                DataSignal(
                    source="newsapi",
                    signal_type="news",
                    title=article.get("title") or "Untitled",
                    summary=article.get("description") or "No description available.",
                    published_at=self._safe_parse_datetime(article.get("publishedAt")),
                )
            )
        return signals

    async def _fetch_macro_signals(self, sector: str) -> list[DataSignal]:
        # Placeholder macro feed for assignment scope.
        await asyncio.sleep(0)
        return [
            DataSignal(
                source="macro_synthetic",
                signal_type="macro",
                title=f"RBI liquidity commentary for {sector}",
                summary=(
                    "Latest policy communication suggests stable near-term liquidity with targeted support "
                    "for productive capex across major industrial and services segments."
                ),
                published_at=datetime.now(timezone.utc),
            ),
            DataSignal(
                source="macro_synthetic",
                signal_type="macro",
                title=f"Commodity and INR pass-through impact on {sector}",
                summary=(
                    "Input-cost volatility remains elevated; margin resilience depends on pricing power "
                    "and supply chain hedging discipline."
                ),
                published_at=datetime.now(timezone.utc),
            ),
        ]

    async def _fetch_market_snapshot(self, sector: str) -> list[DataSignal]:
        await asyncio.sleep(0)
        return [
            DataSignal(
                source="market_synthetic",
                signal_type="market",
                title=f"Valuation breadth update in {sector}",
                summary=(
                    "Large-cap leaders trade at premium multiples while mid-cap dispersion is widening, "
                    "creating selective entry opportunities with higher stock-specific risk."
                ),
                published_at=datetime.now(timezone.utc),
            )
        ]

    def _mock_news_signals(self, sector: str) -> list[DataSignal]:
        now = datetime.now(timezone.utc)
        return [
            DataSignal(
                source="mock_news",
                signal_type="news",
                title=f"Indian {sector} firms report mixed quarterly momentum",
                summary=(
                    "Revenue growth remained healthy for top names, though margin pressure persisted "
                    "for firms with elevated import dependency."
                ),
                published_at=now,
            ),
            DataSignal(
                source="mock_news",
                signal_type="news",
                title=f"Policy support announced for strategic {sector} investments",
                summary=(
                    "The government outlined incentives for domestic manufacturing and technology upgrades, "
                    "which could improve medium-term competitiveness."
                ),
                published_at=now,
            ),
        ]

    def _fallback_signals(self, sector: str) -> list[DataSignal]:
        logger.warning("all_data_sources_failed", extra={"extra_data": {"sector": sector}})
        return self._mock_news_signals(sector)

    @staticmethod
    def _safe_parse_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
