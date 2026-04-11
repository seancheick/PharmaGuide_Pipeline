"""Golden fixture smoke + pin tests for curated_interactions_golden.json.

This 20-row fixture is the anchor for the entire interaction DB build pipeline
(verify_interactions → build_interaction_db → release_interaction_artifact). If
the fixture drifts, downstream byte-identity tests (T8) and schema tests will
fail by design.

Guards:
- Schema loads, 20 entries, expected ID set
- verify_interactions runs offline with 0 errors / 0 warnings
- Every Major+ entry has ≥1 source_url (evidence gate §6.2 check 9)
- Every agent_id is verified-shape (RXCUI / CUI / class:X)
- Severity distribution stays stable (catches accidental severity drift)
- Direction normalization is deterministic (drug-first, Sup-Sup sorted)
- Every class: agent_id references a class that exists in drug_classes.json
- Every CUI agent_id exists in ingredient_quality_map.json
- Every RXCUI agent_id exists in drug_classes.json

Live PubMed + RxNorm + UMLS verification of these rows happens in
test_verify_interactions_live.py under PHARMAGUIDE_LIVE_TESTS=1.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "curated_interactions_golden.json"
IQM = ROOT / "data" / "ingredient_quality_map.json"
DRUG_CLASSES = ROOT / "data" / "drug_classes.json"

sys.path.insert(0, str(ROOT / "api_audit"))
import verify_interactions as vi  # noqa: E402

EXPECTED_IDS = {
    "DDI_WAR_VITK",
    "DDI_WAR_GINKGO",
    "DDI_WAR_GARLIC",
    "DDI_WAR_FISHOIL",
    "DDI_WAR_STJOHNS",
    "DDI_WAR_COQ10",
    "DDI_NSAID_FISHOIL",
    "DDI_NSAID_GINKGO",
    "DDI_ACE_POTASSIUM",
    "DDI_DIURETIC_POTASSIUM",
    "DDI_STATIN_STJOHNS",
    "DDI_SSRI_STJOHNS",
    "DDI_SSRI_5HTP",
    "DDI_MAOI_STJOHNS",
    "DDI_MAOI_5HTP",
    "DDI_IRON_CALCIUM",
    "DDI_IRON_ZINC",
    "DDI_CALCIUM_ZINC",
    "DDI_WARF_NSAID",
    "DDI_LITHIUM_NSAID",
}

RXCUI_RE = re.compile(r"^\d+$")
CUI_RE = re.compile(r"^C\d{7}$")
CLASS_RE = re.compile(r"^class:[a-z][a-z0-9_]*$")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def payload() -> dict:
    assert FIXTURE.exists(), f"golden fixture missing: {FIXTURE}"
    with FIXTURE.open() as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def entries(payload) -> list[dict]:
    return payload["interactions"]


@pytest.fixture(scope="module")
def iqm() -> dict:
    with IQM.open() as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def drug_classes() -> dict:
    with DRUG_CLASSES.open() as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Shape + coverage
# --------------------------------------------------------------------------- #


def test_metadata_block(payload):
    assert "_metadata" in payload
    meta = payload["_metadata"]
    assert meta["schema_version"] == "1.0.0"
    assert meta["total_entries"] == 20
    assert "NIH" in " ".join(meta["sources"])


def test_fixture_has_exactly_20_entries(entries):
    assert len(entries) == 20


def test_all_expected_ids_present(entries):
    got = {e["id"] for e in entries}
    missing = EXPECTED_IDS - got
    extra = got - EXPECTED_IDS
    assert not missing, f"missing: {missing}"
    assert not extra, f"unexpected: {extra}"


def test_no_duplicate_ids(entries):
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "type",
        "agent1_name",
        "agent1_id",
        "agent2_name",
        "agent2_id",
        "severity",
        "interaction_effect_type",
        "mechanism",
        "management",
        "source_urls",
    ],
)
def test_every_entry_has_required_field(entries, field):
    for e in entries:
        assert field in e, f"{e.get('id')} missing {field}"
        assert e[field] not in (None, "", [], {}), f"{e['id']}.{field} is empty"


def test_all_agent_ids_have_valid_shape(entries):
    for e in entries:
        for side in ("agent1_id", "agent2_id"):
            aid = e[side]
            assert (
                RXCUI_RE.match(aid) or CUI_RE.match(aid) or CLASS_RE.match(aid)
            ), f"{e['id']}.{side}={aid!r} has invalid shape"


def test_all_types_are_allowed(entries):
    allowed = {"Med-Sup", "Sup-Med", "Sup-Sup", "Med-Med"}
    for e in entries:
        assert e["type"] in allowed, f"{e['id']}: disallowed type {e['type']}"


def test_all_severities_are_draft_vocab(entries):
    allowed = {"Contraindicated", "Major", "Moderate", "Minor"}
    for e in entries:
        assert e["severity"] in allowed, f"{e['id']}: {e['severity']}"


def test_all_effect_types_are_allowed(entries):
    allowed = {"Inhibitor", "Enhancer", "Additive", "Neutral"}
    for e in entries:
        assert e["interaction_effect_type"] in allowed, (
            f"{e['id']}: {e['interaction_effect_type']}"
        )


# --------------------------------------------------------------------------- #
# Evidence gate — Major+ must carry source URLs
# --------------------------------------------------------------------------- #


def test_major_plus_entries_have_source_urls(entries):
    for e in entries:
        if e["severity"] in ("Major", "Contraindicated"):
            assert e["source_urls"], (
                f"{e['id']} is {e['severity']} but has no source_urls — "
                "evidence gate will block the build"
            )


def test_source_urls_are_authoritative(entries):
    """Every URL must be from NIH/NCBI/NCCIH/DailyMed — no arbitrary web pages."""
    allowed_hosts = (
        "ods.od.nih.gov",
        "nccih.nih.gov",
        "ncbi.nlm.nih.gov",
        "dailymed.nlm.nih.gov",
        "pubmed.ncbi.nlm.nih.gov",
    )
    for e in entries:
        for url in e["source_urls"]:
            assert any(host in url for host in allowed_hosts), (
                f"{e['id']}: non-authoritative URL {url!r}"
            )


# --------------------------------------------------------------------------- #
# Cross-reference with IQM + drug_classes
# --------------------------------------------------------------------------- #


def test_every_class_agent_id_exists_in_drug_classes(entries, drug_classes):
    classes = drug_classes["classes"]
    for e in entries:
        for side in ("agent1_id", "agent2_id"):
            aid = e[side]
            if CLASS_RE.match(aid):
                assert aid in classes, f"{e['id']}: unknown class {aid}"


def test_every_cui_agent_id_maps_in_iqm(entries, iqm):
    """Every supplement CUI in the fixture must be present in IQM, proving the
    fixture uses canonical IDs rather than invented strings."""
    cui_to_canonical = {
        v["cui"]: canonical
        for canonical, v in iqm.items()
        if not canonical.startswith("_") and isinstance(v, dict) and v.get("cui")
    }
    for e in entries:
        for side in ("agent1_id", "agent2_id"):
            aid = e[side]
            if CUI_RE.match(aid):
                assert aid in cui_to_canonical, (
                    f"{e['id']}.{side}={aid} not found in IQM — "
                    "either wrong CUI or missing supplement"
                )


def test_every_rxcui_agent_id_exists_in_drug_classes(entries, drug_classes):
    """Every drug RXCUI must be verifiable via drug_classes.json (our ground
    truth for bundled pipeline data)."""
    known_rxcuis = set()
    for cls in drug_classes["classes"].values():
        known_rxcuis.update(cls["member_rxcuis"])
    for e in entries:
        for side in ("agent1_id", "agent2_id"):
            aid = e[side]
            if RXCUI_RE.match(aid):
                assert aid in known_rxcuis, (
                    f"{e['id']}.{side}={aid} is not a member of any curated drug class"
                )


# --------------------------------------------------------------------------- #
# verify_interactions.py offline pass — the gate itself
# --------------------------------------------------------------------------- #


def test_verify_interactions_offline_pass(tmp_path):
    report = tmp_path / "report.json"
    normalized = tmp_path / "normalized.json"
    corrections = tmp_path / "corrections.json"

    rc = vi.main(
        [
            "--drafts",
            str(FIXTURE),
            "--iqm",
            str(IQM),
            "--drug-classes",
            str(DRUG_CLASSES),
            "--report",
            str(report),
            "--normalized-out",
            str(normalized),
            "--corrections-out",
            str(corrections),
            "--offline",
        ]
    )
    assert rc == 0, f"verify_interactions exited {rc}"

    r = json.loads(report.read_text())
    assert r["total_entries"] == 20
    assert r["valid"] == 20
    assert r["errors"] == 0
    assert r["warnings"] == 0
    assert not r["blocked_by"]
    assert not r["rxcui_mismatches"]
    assert not r["unknown_classes"]
    assert not r["unmapped_supplements"]


def test_verify_interactions_normalized_shape(tmp_path):
    report = tmp_path / "report.json"
    normalized = tmp_path / "normalized.json"

    rc = vi.main(
        [
            "--drafts",
            str(FIXTURE),
            "--iqm",
            str(IQM),
            "--drug-classes",
            str(DRUG_CLASSES),
            "--report",
            str(report),
            "--normalized-out",
            str(normalized),
            "--offline",
        ]
    )
    assert rc == 0
    payload = json.loads(normalized.read_text())
    out = payload["interactions"]

    # Severity distribution is frozen — any drift in the fixture fails loudly.
    from collections import Counter

    sev = Counter(e["severity"] for e in out)
    assert sev == Counter(
        {"avoid": 9, "caution": 8, "contraindicated": 2, "monitor": 1}
    ), f"severity distribution drifted: {sev}"

    # Med-Sup entries must have the drug on agent1 side.
    for e in out:
        if e["type_authored"] in ("Med-Sup", "Sup-Med"):
            a1_kind = vi.classify_agent(e["agent1_id"])
            assert a1_kind in ("drug", "class"), (
                f"{e['id']}: agent1 is not drug-side after normalization "
                f"({e['agent1_id']} → {a1_kind})"
            )

    # Sup-Sup entries must be sorted by agent_id for determinism.
    for e in out:
        if e["type_authored"] == "Sup-Sup":
            assert e["agent1_id"] < e["agent2_id"], (
                f"{e['id']}: Sup-Sup pair not stable-sorted"
            )


def test_verify_interactions_no_corrections_needed(tmp_path):
    """Offline run must produce an empty corrections file. This proves the
    fixture is already clean and future live runs can detect drift precisely."""
    report = tmp_path / "report.json"
    normalized = tmp_path / "normalized.json"
    corrections = tmp_path / "corrections.json"

    rc = vi.main(
        [
            "--drafts",
            str(FIXTURE),
            "--iqm",
            str(IQM),
            "--drug-classes",
            str(DRUG_CLASSES),
            "--report",
            str(report),
            "--normalized-out",
            str(normalized),
            "--corrections-out",
            str(corrections),
            "--offline",
        ]
    )
    assert rc == 0
    c = json.loads(corrections.read_text())
    assert not c.get("cui_corrections"), c
    assert not c.get("rxcui_mismatches"), c
    assert not c.get("unmapped_supplements"), c
