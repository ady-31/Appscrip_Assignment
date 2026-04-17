from typing import Final


SECTOR_ALIASES: Final[dict[str, str]] = {
    "technology": "information_technology",
    "tech": "information_technology",
    "it": "information_technology",
    "information technology": "information_technology",
    "banking": "banking_financial_services",
    "bfsi": "banking_financial_services",
    "financial services": "banking_financial_services",
    "finance": "banking_financial_services",
    "pharma": "pharmaceuticals",
    "pharmaceutical": "pharmaceuticals",
    "pharmaceuticals": "pharmaceuticals",
    "healthcare": "healthcare",
    "auto": "automobile",
    "automobile": "automobile",
    "energy": "energy",
    "power": "energy",
    "fmcg": "fmcg",
    "consumer": "fmcg",
    "infrastructure": "infrastructure",
    "infra": "infrastructure",
    "metals": "metals_mining",
    "mining": "metals_mining",
    "real estate": "real_estate",
}

SUPPORTED_SECTORS: Final[set[str]] = set(SECTOR_ALIASES.values())


def normalize_sector(raw_sector: str) -> str | None:
    token = " ".join(raw_sector.strip().lower().replace("_", " ").split())
    return SECTOR_ALIASES.get(token)
