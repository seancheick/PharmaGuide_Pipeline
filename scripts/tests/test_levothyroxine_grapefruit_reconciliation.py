"""D27 regression lock: one severity per supplement-levothyroxine pair, and the
sourced facts behind the levothyroxine and grapefruit-statin entries.

Decided by Sean on 2026-10-01 from the evidence packet
`scripts/audits/levo_grapefruit_severity_20261001/research.md`:

- Calcium, iron and magnesium with levothyroxine carry ONE severity (caution)
  in both owners: the profile rules (product page) and the curated drug pairs
  (stack check). The SYNTHROID label manages these by separating doses by at
  least 4 hours, not by avoiding the combination.
- The magnesium entries cite the 2025 ThyroMag crossover trial and case
  reports, not the ODS fact sheet, which never mentions levothyroxine.
- The grapefruit-statin text follows each statin's label: atorvastatin is
  limited to large quantities of juice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api_audit.verify_interactions import SEVERITY_MAP

DATA = Path(__file__).resolve().parents[1] / "data"
RULES = DATA / "ingredient_interaction_rules.json"
CURATED = DATA / "curated_interactions" / "curated_interactions_v1.json"
TIMING = DATA / "timing_rules.json"

ODS_MAGNESIUM = "ods.od.nih.gov/factsheets/Magnesium-HealthProfessional"
THYROMAG = "41221788"
MAGNESIUM_CASES = "10193669"
SIMVASTATIN_LABEL = "3f6fad0b-0278-433f-86db-761b673a5803"
ATORVASTATIN_LABEL = "d57720ab-9f83-4da9-a57f-0d55e00a605c"
LOVASTATIN_LABEL = "9438d8a0-ca5b-4676-aab9-d0241ccff6c9"

# curated pair id -> profile rule id whose thyroid_medications sub-rule must agree
LEVOTHYROXINE_PAIRS = {
    "DSI_LEVOTHYROXINE_CALCIUM": "RULE_IQM_CALCIUM",
    "DSI_LEVOTHYROXINE_IRON": "RULE_IQM_IRON_HYPERTENSION",
    "DSI_LEVOTHYROXINE_MAGNESIUM": "RULE_IQM_MAGNESIUM_HYPERTENSION",
}


@pytest.fixture(scope="module")
def curated() -> dict:
    data = json.loads(CURATED.read_text())
    return {entry["id"]: entry for entry in data["interactions"]}


@pytest.fixture(scope="module")
def thyroid_sub_rules() -> dict:
    data = json.loads(RULES.read_text())
    out = {}
    for rule in data["interaction_rules"]:
        for sub in rule.get("drug_class_rules", []):
            if sub.get("drug_class_id") == "thyroid_medications":
                out[rule["id"]] = sub
    return out


@pytest.fixture(scope="module")
def timing() -> dict:
    data = json.loads(TIMING.read_text())
    return {rule["id"]: rule for rule in data["timing_rules"]}


@pytest.mark.parametrize("pair_id,rule_id", sorted(LEVOTHYROXINE_PAIRS.items()))
def test_one_severity_per_levothyroxine_pair(curated, thyroid_sub_rules, pair_id, rule_id):
    """A user on levothyroxine must not see "Not recommended" in the stack and
    "Use caution" on the product page for the same pair."""
    pair_severity = SEVERITY_MAP[curated[pair_id]["severity"].lower()]
    rule_severity = thyroid_sub_rules[rule_id]["severity"]
    assert pair_severity == rule_severity == "caution", (pair_id, pair_severity, rule_id, rule_severity)


@pytest.mark.parametrize("rule_id", ["RULE_IQM_CALCIUM", "RULE_IQM_IRON_HYPERTENSION"])
def test_label_backed_thyroid_rules_are_established(thyroid_sub_rules, rule_id):
    """Calcium carbonate and ferrous sulfate are named in the SYNTHROID label."""
    sub = thyroid_sub_rules[rule_id]
    assert sub["evidence_level"] == "established"
    assert any("1e11ad30-1041-4520-10b0-8f9d30d30fcc" in s for s in sub["sources"])


def test_calcium_absorption_figure_matches_its_source(curated):
    """Zamfirescu 2011 (PMID 21595516) reports about 20-25%, not 'up to 40%'."""
    mechanism = curated["DSI_LEVOTHYROXINE_CALCIUM"]["mechanism"]
    assert "40%" not in mechanism
    assert "20" in mechanism and "25%" in mechanism


def test_magnesium_entries_cite_magnesium_evidence(curated, thyroid_sub_rules, timing):
    pair = curated["DSI_LEVOTHYROXINE_MAGNESIUM"]
    rule = thyroid_sub_rules["RULE_IQM_MAGNESIUM_HYPERTENSION"]
    timing_rule = timing["timing_thyroid_med_magnesium_separate"]
    cited = {
        "pair": " ".join(pair["source_urls"]),
        "rule": " ".join(rule["sources"]),
        "timing": " ".join(s["url"] for s in timing_rule["sources"]),
    }
    for owner, text in cited.items():
        assert ODS_MAGNESIUM not in text, owner
        assert THYROMAG in text, owner
    assert set(pair["source_pmids"]) == {THYROMAG, MAGNESIUM_CASES}


def test_magnesium_interval_and_grade_agree(curated, thyroid_sub_rules, timing):
    pair = curated["DSI_LEVOTHYROXINE_MAGNESIUM"]
    assert "2–4" not in pair["management"] and "2-4" not in pair["management"]
    assert "at least 4 hours" in pair["management"]
    assert "at least 4 hours" in thyroid_sub_rules["RULE_IQM_MAGNESIUM_HYPERTENSION"]["action"]
    timing_rule = timing["timing_thyroid_med_magnesium_separate"]
    assert timing_rule["timing_relation"]["minimum_hours"] == 4
    assert timing_rule["evidence_level"] == "probable"
    assert thyroid_sub_rules["RULE_IQM_MAGNESIUM_HYPERTENSION"]["evidence_level"] == "probable"


def test_magnesium_timing_rule_stays_unpublished_until_interval_is_sourced(timing):
    """ThyroMag resolves the citation blocker; no study sets a magnesium-specific
    interval, so the timing card is not published by this batch."""
    rule = timing["timing_thyroid_med_magnesium_separate"]
    assert rule["review_status"] == "needs_revision"
    assert rule["review_blockers"] == ["interval_not_supported_by_cited_source"]


def test_grapefruit_text_follows_each_statin_label(curated):
    entry = curated["DSI_STATINS_GRAPEFRUIT"]
    for field in ("management", "note_body", "practical_guidance"):
        text = entry[field]
        if "atorvastatin" in text.lower():
            assert "1.2" in text, field
    urls = " ".join(entry["source_urls"])
    for setid in (SIMVASTATIN_LABEL, ATORVASTATIN_LABEL, LOVASTATIN_LABEL):
        assert setid in urls
    # Class-level food note: severity is unchanged by this batch.
    assert entry["severity"] == "Moderate"
    assert entry["alert_style"] == "food_advisory_note"
