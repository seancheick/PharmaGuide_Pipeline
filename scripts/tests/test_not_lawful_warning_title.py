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

import json
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
        ("WADA_CANNABIS", "Not lawful as a supplement"),
        ("WADA_TRAMADOL", "Controlled substance"),
        ("NOOTROPIC_PIRACETAM", "Unverified ingredient"),
        ("BANNED_ACONITE", "Unverified ingredient"),
        ("BANNED_ARISTOLOCHIC_ACID", "Unsafe ingredient"),
        ("BANNED_BVO_2024", "Banned substance"),
        ("SCHED_AMANITA_MUSCARIA", "Unverified ingredient"),
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

    assert entry["legal_status_enum"] == "under_review"  # LEDGER Q58 Category 1
    assert entry.get("regulatory_date_label") != "DEA scheduling effective"
    assert entry.get("regulatory_date") is None
    assert entry["source_category"] != "schedule_I_psychoactives"


def _registry():
    import json
    return json.loads(
        (ROOT / "scripts/data/banned_recalled_ingredients.json").read_text()
    )


# LEDGER Q56 (2026-10-02): two DEA dates looked like placeholders. Checked
# against the Federal Register and 21 CFR 1308.11 as published 2026-09-30.
@pytest.mark.parametrize(
    "rule_id, expected_prefix",
    [
        # Schedule I, DEA code 7544: temporary 84 FR 34291, permanent 87 FR 32996.
        ("STIM_ALPHA_PHP", "Controlled substance"),
        # Not named in 21 CFR 1308.11 and outside the paragraph (g)
        # cannabimimetic structural classes; no US document names it.
        ("SYNTH_CUMYL_PICA", "Unverified ingredient"),
    ],
)
def test_q56_dea_titles(rule_id, expected_prefix):
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [{
        "ingredient": "X", "id": rule_id, "status": "banned", "match_type": "exact",
    }]

    assert _ban_titles(build_top_warnings(enriched)) == [f"{expected_prefix}: X"]


def test_alpha_php_dates_its_dea_scheduling_from_the_federal_register():
    entry = _entry("STIM_ALPHA_PHP")
    urls = {r.get("url") for r in entry["references_structured"]}

    assert entry["legal_status_enum"] == "controlled_substance"
    assert entry["regulatory_date"] == "2019-07-18"
    assert entry["regulatory_date_label"] == "DEA scheduling effective"
    assert entry["policy_verification_status"] == "verified"
    assert any("2019-15184" in (u or "") for u in urls)  # 84 FR 34291
    assert any("2022-11740" in (u or "") for u in urls)  # 87 FR 32996
    assert "emergency Schedule I" not in entry["reason"]


def test_cumyl_pica_claims_no_dea_scheduling():
    entry = _entry("SYNTH_CUMYL_PICA")

    assert entry["legal_status_enum"] == "under_review"
    assert entry.get("regulatory_date") is None
    assert entry.get("regulatory_date_label") is None
    assert entry.get("policy_verification_status") is None
    text = json.dumps(
        [entry["reason"], entry["jurisdictions"], entry["references_structured"],
         entry["safety_warning"]]
    )
    for false_claim in (
        "DEA Schedule I controlled substance analogs",
        "DEA Schedule I (controlled substance)",
        "Synthetic cannabinoids Schedule I",
        "constitutes an adulterated controlled substance",
        "Not a lawful supplement ingredient",
        "no approved use",
    ):
        assert false_claim not in text
    assert "not named in the federal schedules" in entry["reason"]


@pytest.mark.parametrize(
    "rule_id, ghost_doi",
    [
        # Resolve to a face-recognition paper and a lathe toolmark paper.
        ("STIM_ALPHA_PHP", "10.1016/j.forsciint.2015.09.002"),
        ("SYNTH_CUMYL_PICA", "10.1016/j.forsciint.2017.03.004"),
    ],
)
def test_q56_wrong_topic_dois_are_gone(rule_id, ghost_doi):
    assert ghost_doi not in json.dumps(_entry(rule_id))


def _entry(rule_id):
    return next(e for e in _registry()["ingredients"] if e["id"] == rule_id)
