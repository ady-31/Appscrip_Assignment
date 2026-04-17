from app.core.schemas import DataSignal


POSITIVE_TERMS = {
    "growth",
    "expansion",
    "beat",
    "strong",
    "upside",
    "rally",
    "approval",
    "outperform",
}

NEGATIVE_TERMS = {
    "slowdown",
    "miss",
    "weak",
    "downside",
    "decline",
    "regulatory",
    "delay",
    "downgrade",
}


def score_sentiment(signals: list[DataSignal]) -> float:
    """Compute a simple lexicon-based sentiment score in [-1, 1]."""

    positive = 0
    negative = 0

    for signal in signals:
        text = f"{signal.title} {signal.summary}".lower()
        positive += sum(1 for term in POSITIVE_TERMS if term in text)
        negative += sum(1 for term in NEGATIVE_TERMS if term in text)

    total = positive + negative
    if total == 0:
        return 0.0
    return (positive - negative) / total
