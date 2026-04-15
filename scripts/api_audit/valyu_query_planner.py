from __future__ import annotations

from datetime import datetime, timedelta, timezone


CLINICAL_SOURCES = [
    "valyu/valyu-pubmed",
    "valyu/valyu-clinical-trials",
    "valyu/valyu-chembl",
]

REGULATORY_SOURCES = [
    "fda.gov",
    "efsa.europa.eu",
    "ec.europa.eu",
]


def build_search_plan(domain: str, entity_name: str, months_back: int = 24) -> dict[str, object]:
    end_date = datetime.now(timezone.utc).date()
    start_date = (datetime.now(timezone.utc) - timedelta(days=months_back * 30)).date()

    if domain == "clinical_refresh":
        included_sources = CLINICAL_SOURCES
        query = f'latest clinical evidence for "{entity_name}" supplement'
    elif domain == "harmful_refresh":
        included_sources = REGULATORY_SOURCES
        query = f'latest regulatory safety update for "{entity_name}" supplement additive'
    elif domain == "recall_refresh":
        included_sources = REGULATORY_SOURCES
        query = f'latest recall or regulatory action for "{entity_name}" supplement ingredient'
    elif domain == "iqm_gap_scan":
        included_sources = CLINICAL_SOURCES
        query = f'latest clinical trials systematic review for "{entity_name}" supplement ingredient'
    else:
        raise ValueError(f"Unsupported domain: {domain}")

    return {
        "domain": domain,
        "entity_name": entity_name,
        "included_sources": included_sources,
        "query_used": query,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "months_back": months_back,
    }
