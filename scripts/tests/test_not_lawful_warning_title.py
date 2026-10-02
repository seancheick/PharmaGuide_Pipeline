"""Ban warning titles say what the registry's legal status says.

Extended 2026-10-02 (Sean): every banned legal status gets its own title, and
the three Amanita entries lose a DEA scheduling the DEA list does not have.

Simulator walkthrough 2026-10-01: a CBD product read "Banned substance:
organic Hemp Oil extract" offline, but the registry records CBD as
``legal_status_enum: not_lawful_as_supplement`` (excluded from the
supplement definition), not a federal ban. 67 of the 73 blocked products in
that catalog had this status. A ``status: banned`` entry whose legal status
is ``not_lawful_as_supplement`` is titled "Not lawful as a supplement: <name>";
a real federal ban (BVO, PHO) keeps "Banned substance: <name>".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_final_db import build_detail_blob, build_top_warnings  # noqa: E402
from test_build_final_db import make_enriched, make_scored  # noqa: E402


def _enriched_with_inactive(name: str) -> dict:
    enriched = make_enriched()
    enriched["inactiveIngredients"] = [
        {"name": name, "raw_source_text": name, "standardName": name},
    ]
    return enriched


def _ban_titles(warnings: list) -> list:
    return [w["title"] for w in warnings if w.get("type") == "banned_substance"]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Cannabidiol", "Not lawful as a supplement: CBD (Cannabidiol)"),
        ("Brominated Vegetable Oil", "Banned substance: Brominated Vegetable Oil"),
    ],
)
def test_detail_blob_ban_title_follows_legal_status(name, expected):
    blob = build_detail_blob(_enriched_with_inactive(name), make_scored("BLOCKED"))

    assert _ban_titles(blob["warnings"]) == [expected]


@pytest.mark.parametrize(
    "rule_id, name, expected",
    [
        ("BANNED_CBD_US", "Cannabidiol", "Not lawful as a supplement: Cannabidiol"),
        (
            "BANNED_BVO_2024",
            "Brominated Vegetable Oil",
            "Banned substance: Brominated Vegetable Oil",
        ),
    ],
)
def test_top_warnings_fallback_title_follows_legal_status(rule_id, name, expected):
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [{
        "ingredient": name, "id": rule_id, "status": "banned", "match_type": "exact",
    }]

    assert _ban_titles(build_top_warnings(enriched)) == [expected]


def test_not_lawful_title_still_yields_the_substance_name():
    blob = build_detail_blob(
        _enriched_with_inactive("Cannabidiol"), make_scored("BLOCKED"),
    )

    assert blob["banned_substance_detail"]["substance_name"] == "CBD (Cannabidiol)"


@pytest.mark.parametrize(
    "rule_id, expected_prefix",
    [
        ("SPIKE_SILDENAFIL", "Hidden drug"),
        ("BANNED_CBD_US", "Not lawful as a supplement"),
        ("NOOTROPIC_MODAFINIL", "Controlled substance"),
        ("WADA_TRAMADOL", "Prohibited in sport"),
        ("NOOTROPIC_PIRACETAM", "Unapproved ingredient"),
        ("BANNED_ACONITE", "High-risk ingredient"),
        ("BANNED_ARISTOLOCHIC_ACID", "Unsafe ingredient"),
        ("BANNED_BVO_2024", "Banned substance"),
        ("SCHED_AMANITA_MUSCARIA", "High-risk ingredient"),
    ],
)
def test_each_legal_status_gets_its_own_title(rule_id, expected_prefix):
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [{
        "ingredient": "X", "id": rule_id, "status": "banned", "match_type": "exact",
    }]

    assert _ban_titles(build_top_warnings(enriched)) == [f"{expected_prefix}: X"]


@pytest.mark.parametrize(
    "rule_id", ["SCHED_AMANITA_MUSCARIA", "BANNED_MUSCIMOL", "BANNED_IBOTENIC_ACID"],
)
def test_amanita_entries_claim_no_dea_scheduling(rule_id):
    # Not on the DEA controlled-substances list (orange book, checked
    # 2026-10-02); the records had a 2024-01-01 "DEA scheduling effective" date.
    entry = next(e for e in _registry()["ingredients"] if e["id"] == rule_id)

    assert entry["legal_status_enum"] == "high_risk"
    assert entry.get("regulatory_date_label") != "DEA scheduling effective"
    assert entry.get("regulatory_date") is None
    assert entry["source_category"] != "schedule_I_psychoactives"


def _registry():
    import json
    return json.loads(
        (ROOT / "scripts/data/banned_recalled_ingredients.json").read_text()
    )
