from fastapi.testclient import TestClient

from app.main import app
from app.services.data_collection import DataCollectionService


def test_cache_hit_returns_from_cache() -> None:
    client = TestClient(app)

    first = client.get("/analyze/tech", headers={"X-API-Key": "cache-user"})
    second = client.get("/analyze/tech", headers={"X-API-Key": "cache-user"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["from_cache"] is False
    assert second.json()["from_cache"] is True


def test_rate_limit_blocks_after_five_requests() -> None:
    client = TestClient(app)
    headers = {"X-API-Key": "limit-user"}

    status_codes = [client.get("/analyze/banking", headers=headers).status_code for _ in range(6)]

    assert status_codes[:5] == [200, 200, 200, 200, 200]
    assert status_codes[5] == 429


def test_partial_analysis_warning_when_data_collection_fails(monkeypatch) -> None:
    client = TestClient(app)

    async def fail_collection(self: DataCollectionService, sector: str):
        raise RuntimeError("simulated upstream outage")

    monkeypatch.setattr(DataCollectionService, "collect_signals", fail_collection)

    response = client.get("/analyze/automobile", headers={"X-API-Key": "partial-user"})
    body = response.json()

    assert response.status_code == 200
    assert body["from_cache"] is False
    assert any("partial fallback" in warning.lower() for warning in body["warnings"])
