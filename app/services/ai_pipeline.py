import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.core.schemas import DataSignal, Insight, Stage1Summary, Stage2Trends, Stage3TradeView
from app.utils.sentiment import score_sentiment

logger = get_logger(__name__)


class AIPipelineService:
    """Run a four-stage analysis workflow over collected sector signals."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run_pipeline(self, sector: str, signals: list[DataSignal]) -> tuple[Stage1Summary, Stage2Trends, Stage3TradeView, list[str]]:
        warnings: list[str] = []

        stage1 = await self._stage1_summary(sector, signals, warnings)
        stage2 = await self._stage2_trends(sector, signals, stage1, warnings)
        stage3 = await self._stage3_trade_view(sector, stage1, stage2, warnings)

        # Stage 4 is an additional LLM synthesis pass that can refine recommendation wording.
        stage3 = await self._stage4_synthesis(sector, stage1, stage2, stage3, warnings)

        return stage1, stage2, stage3, warnings

    async def _stage1_summary(self, sector: str, signals: list[DataSignal], warnings: list[str]) -> Stage1Summary:
        prompt = {
            "task": "Summarize sector signals into concise market context.",
            "sector": sector,
            "signals": [signal.model_dump(mode="json") for signal in signals],
            "output_schema": {
                "market_summary": "string",
                "notable_events": ["string"],
            },
        }

        raw = await self._generate_json(prompt)
        if raw is None:
            warnings.append("Stage 1 AI summary unavailable; fallback summary used.")
            return self._fallback_stage1(signals)

        try:
            return Stage1Summary.model_validate(raw)
        except ValidationError:
            warnings.append("Stage 1 output schema mismatch; fallback summary used.")
            return self._fallback_stage1(signals)

    async def _stage2_trends(
        self,
        sector: str,
        signals: list[DataSignal],
        stage1: Stage1Summary,
        warnings: list[str],
    ) -> Stage2Trends:
        baseline_sentiment = score_sentiment(signals)
        prompt = {
            "task": "Extract key trends with explainability and sentiment.",
            "sector": sector,
            "stage1_summary": stage1.model_dump(mode="json"),
            "baseline_sentiment": baseline_sentiment,
            "output_schema": {
                "trends": [
                    {
                        "title": "string",
                        "reasoning": "string",
                        "confidence": "number 0-100",
                        "source_reference": "string",
                    }
                ],
                "sentiment": "bullish|neutral|bearish",
                "sentiment_score": "number between -1 and 1",
            },
        }

        raw = await self._generate_json(prompt)
        if raw is None:
            warnings.append("Stage 2 trend extraction unavailable; heuristic trends used.")
            return self._fallback_stage2(signals, baseline_sentiment)

        try:
            parsed = Stage2Trends.model_validate(raw)
            return parsed
        except ValidationError:
            warnings.append("Stage 2 output schema mismatch; heuristic trends used.")
            return self._fallback_stage2(signals, baseline_sentiment)

    async def _stage3_trade_view(
        self,
        sector: str,
        stage1: Stage1Summary,
        stage2: Stage2Trends,
        warnings: list[str],
    ) -> Stage3TradeView:
        prompt = {
            "task": "Generate trade opportunities and risk factors with explainability.",
            "sector": sector,
            "market_summary": stage1.model_dump(mode="json"),
            "trends": stage2.model_dump(mode="json"),
            "constraints": [
                "At least 2 opportunities and 2 risks when possible",
                "Keep confidence realistic and bounded",
                "Each item must include title, reasoning, confidence, source_reference",
            ],
            "output_schema": {
                "opportunities": [
                    {
                        "title": "string",
                        "reasoning": "string",
                        "confidence": "number 0-100",
                        "source_reference": "string",
                    }
                ],
                "risks": [
                    {
                        "title": "string",
                        "reasoning": "string",
                        "confidence": "number 0-100",
                        "source_reference": "string",
                    }
                ],
                "recommendation": "string",
            },
        }

        raw = await self._generate_json(prompt)
        if raw is None:
            warnings.append("Stage 3 opportunity analysis unavailable; fallback portfolio view used.")
            return self._fallback_stage3(stage2)

        try:
            return Stage3TradeView.model_validate(raw)
        except ValidationError:
            warnings.append("Stage 3 output schema mismatch; fallback portfolio view used.")
            return self._fallback_stage3(stage2)

    async def _stage4_synthesis(
        self,
        sector: str,
        stage1: Stage1Summary,
        stage2: Stage2Trends,
        stage3: Stage3TradeView,
        warnings: list[str],
    ) -> Stage3TradeView:
        """Final synthesis stage to tighten recommendation quality and consistency."""

        prompt = {
            "task": "Refine final recommendation and ensure opportunities/risks are coherent with trend context.",
            "sector": sector,
            "stage1": stage1.model_dump(mode="json"),
            "stage2": stage2.model_dump(mode="json"),
            "stage3": stage3.model_dump(mode="json"),
            "output_schema": stage3.model_dump(mode="json"),
        }

        raw = await self._generate_json(prompt)
        if raw is None:
            warnings.append("Stage 4 synthesis unavailable; using Stage 3 output.")
            return stage3

        try:
            return Stage3TradeView.model_validate(raw)
        except ValidationError:
            warnings.append("Stage 4 schema mismatch; using Stage 3 output.")
            return stage3

    async def _generate_json(self, prompt_payload: dict[str, Any]) -> dict[str, Any] | None:
        """Invoke Gemini if configured; otherwise return None to trigger deterministic fallback."""

        if not self.settings.gemini_api_key:
            return None

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )

        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are a quant research assistant. Return valid JSON only, no markdown, no prose. "
                                "Keep confidence values between 0 and 100.\n"
                                f"INPUT:\n{json.dumps(prompt_payload, ensure_ascii=True)}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    endpoint,
                    params={"key": self.settings.gemini_api_key},
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning("gemini_call_failed", extra={"extra_data": {"error": str(exc)}})
            return None

        text = self._extract_text(payload)
        if not text:
            return None

        return self._safe_json_loads(text)

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        try:
            return payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return ""

    @staticmethod
    def _safe_json_loads(text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
            return None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _fallback_stage1(signals: list[DataSignal]) -> Stage1Summary:
        top = signals[:3]
        summary_bits = [f"{item.title}: {item.summary}" for item in top]
        return Stage1Summary(
            market_summary=" ".join(summary_bits) if summary_bits else "Insufficient data for detailed summary.",
            notable_events=[item.title for item in top],
        )

    @staticmethod
    def _fallback_stage2(signals: list[DataSignal], sentiment: float) -> Stage2Trends:
        mapped_sentiment = "neutral"
        if sentiment > 0.2:
            mapped_sentiment = "bullish"
        elif sentiment < -0.2:
            mapped_sentiment = "bearish"

        trends: list[Insight] = []
        for signal in signals[:3]:
            trends.append(
                Insight(
                    title=signal.title,
                    reasoning=signal.summary,
                    confidence=65.0,
                    source_reference=signal.source,
                )
            )

        return Stage2Trends(trends=trends, sentiment=mapped_sentiment, sentiment_score=sentiment)

    @staticmethod
    def _fallback_stage3(stage2: Stage2Trends) -> Stage3TradeView:
        opportunities: list[Insight] = []
        risks: list[Insight] = []

        if stage2.trends:
            opportunities.append(
                Insight(
                    title="Momentum-aligned long basket",
                    reasoning="Leading names with recurring positive catalysts may sustain relative strength.",
                    confidence=68.0,
                    source_reference=stage2.trends[0].source_reference,
                )
            )
            risks.append(
                Insight(
                    title="Valuation compression risk",
                    reasoning="Premium multiples can unwind quickly if earnings delivery softens.",
                    confidence=71.0,
                    source_reference=stage2.trends[0].source_reference,
                )
            )

        recommendation = (
            "Neutral-to-positive stance with selective deployment, strict position sizing, "
            "and event-driven risk controls."
        )

        return Stage3TradeView(opportunities=opportunities, risks=risks, recommendation=recommendation)
