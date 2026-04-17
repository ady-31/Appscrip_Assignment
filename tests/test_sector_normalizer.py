from app.utils.sector_normalizer import normalize_sector


def test_sector_aliases_normalize_to_single_key() -> None:
    assert normalize_sector("tech") == "information_technology"
    assert normalize_sector("Technology") == "information_technology"
    assert normalize_sector("IT") == "information_technology"


def test_unknown_sector_returns_none() -> None:
    assert normalize_sector("aviation") is None
