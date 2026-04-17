from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DataSignal(BaseModel):
    source: str
    signal_type: str
    title: str
    summary: str
    published_at: datetime | None = None
    score: float | None = None


class Stage1Summary(BaseModel):
    market_summary: str
    notable_events: list[str] = Field(default_factory=list)


class Insight(BaseModel):
    title: str
    reasoning: str
    confidence: float = Field(ge=0, le=100)
    source_reference: str


class Stage2Trends(BaseModel):
    trends: list[Insight] = Field(default_factory=list)
    sentiment: Literal["bullish", "neutral", "bearish"]
    sentiment_score: float = Field(ge=-1.0, le=1.0)


class Stage3TradeView(BaseModel):
    opportunities: list[Insight] = Field(default_factory=list)
    risks: list[Insight] = Field(default_factory=list)
    recommendation: str


class AnalysisEnvelope(BaseModel):
    sector: str
    normalized_sector: str
    generated_at: datetime
    markdown_report: str
    from_cache: bool = False
    warnings: list[str] = Field(default_factory=list)
