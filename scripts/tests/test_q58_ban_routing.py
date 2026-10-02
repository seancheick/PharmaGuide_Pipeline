"""LEDGER Q58: every banned/recalled record that was not policy-verified has one route.

Sean 2026-10-02. A confirmed match on an unverified record is quarantined
(NOT_SCORED, out of the catalog, so a scan answers "not found"). The 84 such
records were verified one by one (q58_verification_20261002.json) and each now
has exactly one deterministic route:

- verified US regulatory block (FDA notice, recall, statute, DEA schedule);
- Category 1 "Unverified ingredient": identity confident, human harm evidence,
  no US determination (``legal_status_enum: under_review``, verified);
- ended recall or retired record: ``match_mode`` historical/disabled, so the
  product name never blocks (a DMAA label still blocks through DMAA);
- quarantine: neither a regulatory nor a harm basis is verified.

Regulatory uncertainty alone never becomes a safety recommendation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from identity.safety import SafetySignal  # noqa: E402
from scoring_v4.gate_safety import _hard_policy_missing_requirements  # noqa: E402

DATA = ROOT / "scripts" / "data" / "banned_recalled_ingredients.json"
CLASSIFICATION = (
    ROOT / "scripts" / "audits" / "pending_items_20260926" / "q58_classification_20261002.json"
)

REGULATORY_BLOCK = (
    # Hidden drugs named in FDA laboratory notices or recalls.
    "SPIKE_SILDENAFIL", "SPIKE_TADALAFIL", "PHARMA_DAPOXETINE", "ADULTERANT_METFORMIN",
    "ADULTERANT_RIMONABANT", "PHARMA_LORCASERIN", "SPIKE_DEXAMETHASONE", "SPIKE_DICLOFENAC",
    "SPIKE_CHLOROPRETADALAFIL", "SPIKE_PROPOXYPHENYLSILDENAFIL", "ADULTERANT_MELOXICAM",
    "SPIKE_FLUOXETINE", "SPIKE_PHENOLPHTHALEIN", "SPIKE_METHOCARBAMOL", "SPIKE_AMINOTADALAFIL",
    "ADULTERANT_TESTOSTERONE_PROPIONATE", "BANNED_DNP",
    # Statute, regulation, DEA schedule or FDA warning letter.
    "ADD_THYROGEN", "BANNED_DMSA_SUCCIMER", "ADD_HEXADRONE", "ADD_HORDENINE",
    "BANNED_CALAMUS_ACORUS_CALAMUS", "SCHED_PSILOCYBIN", "SCHED_PSILOCIN", "WADA_TRAMADOL",
    # Products named in FDA laboratory notices.
    "RECALLED_DEEP", "RECALLED_BEAUTY_911", "RECALLED_BIG_DICK_ENERGY",
    "RECALLED_CANDY_POWER_FOR_MAN", "RECALLED_ERECTUS_PLUS", "RECALLED_LUZE_FIT_INTENSITY",
    "RECALLED_MAXMAN_COFFEE", "RECALLED_MIRACLE_POWER_OF_KING_KONG_HONEY",
    "RECALLED_SENSUAL_MIRACLE_HONEY", "RECALLED_ZUBB", "RECALLED_GE_LABS_YKARINE",
    # Explicit THC only (FDA drug exclusion); WADA is information.
    "WADA_CANNABIS",
)
ACTIVE_RECALL = (  # rule A: openFDA status Ongoing or a current FDA recall notice
    "RECALLED_BIQ_FEL", "RECALLED_X10_NATURAL_ENHANCEMENT", "RECALLED_BLUE_BULL_EXTREME",
    "RECALLED_BONER_BEARS_HONEY", "RECALLED_RED_BULL_EXTREME", "RECALLED_GREEN_LUMBER",
    "RECALLED_MODERN_WARRIOR", "RECALLED_MR7_SUPER_700000",
    "RECALLED_REBOOST_CLEARLIFE_NASAL_SPRAY", "RECALLED_RHEUMACARE_CAPSULES",
    "RECALLED_SILINTAN", "RECALLED_SILUETAYA_TEJOCOTE",
)
UNVERIFIED_INGREDIENT = (  # Category 1
    "BANNED_ACONITE", "BANNED_CLENBUTEROL",
    "BANNED_IBOTENIC_ACID", "BANNED_IGF1", "BANNED_MUSCIMOL",
    "BANNED_USNIC_ACID", "PEPTIDE_BPC157", "PEPTIDE_TB500", "SCHED_AMANITA_MUSCARIA",
)
ENDED_RECALL = (  # rule C (Jack3D: rule D, DMAA blocks on its own)
    "RECALLED_ROSABELLA_MORINGA", "RECALLED_AONIC_COMPLETE_HERS", "RECALLED_AONIC_COMPLETE_HIS",
    "RECALLED_IMU_TEK_COLOSTRUM_5_CAPSULES", "RECALLED_IMU_TEK_COLOSTRUM_5_POWDER",
    "RECALLED_DIVIDED_SUNSET_COLLAGEN_PEPTIDES", "RECALLED_LIVE_IT_UP_SUPER_GREENS",
    "RECALLED_PURITY_PRODUCTS_MY_BLADDER", "RECALLED_HYDROXYCUT", "RECALLED_OXYELITE_PRO",
    "RECALLED_JACK3D", "RECALLED_GOLD_STAR_DISTRIBUTION",
)
RETIRED = ("SPIKE_METHYL7K",)
QUARANTINE = (  # Category 3: neither a verified regulatory nor a verified harm basis
    "NOOTROPIC_PIRACETAM", "ADD_N_PHENETHYL_DIMETHYLAMINE", "RC_CARDARINE_ANALOGS",
    "SPIKE_TIANEPTINE_ANALOGUES", "BANNED_FASORACETAM", "BANNED_IGF1_LR3", "BANNED_SUNIFIRAM",
    "NOOTROPIC_9MEBC", "NOOTROPIC_BROMANTANE", "NOOTROPIC_FLMODAFINIL", "SYNTH_CUMYL_PICA",
    # Multi-stimulant exposure only; a single case report (Sean 2026-10-02).
    "BANNED_DETERENOL_ISOPROPYLNORSYNEPHRINE", "BANNED_SR9009",
)


@pytest.fixture(scope="module")
def entries() -> dict:
    return {e["id"]: e for e in json.loads(DATA.read_text())["ingredients"]}


def _signal(entry: dict) -> SafetySignal:
    return SafetySignal(
        entry_id=entry["id"], source_db="banned_recalled_ingredients", status=entry["status"],
        severity="critical", subject_role="active", match_resolution="confirmed",
        match_confidence=1.0, policy_eligible=True, review_required=False,
        inactive_policy="", evidence_text=entry["standard_name"],
    )


def test_every_q58_record_has_exactly_one_route():
    q58 = {r["id"] for r in json.loads(CLASSIFICATION.read_text())["records"]}
    routes = [REGULATORY_BLOCK, ACTIVE_RECALL, UNVERIFIED_INGREDIENT, ENDED_RECALL, RETIRED, QUARANTINE]
    listed = [rid for route in routes for rid in route]
    assert len(listed) == len(set(listed))
    assert set(listed) == q58


@pytest.mark.parametrize("rule_id", REGULATORY_BLOCK + ACTIVE_RECALL)
def test_verified_regulatory_records_pass_the_hard_policy_gate(entries, rule_id):
    entry = entries[rule_id]
    assert entry["match_mode"] == "active"
    assert entry["legal_status_enum"] != "under_review"
    assert _hard_policy_missing_requirements(entry, _signal(entry)) == []


@pytest.mark.parametrize("rule_id", UNVERIFIED_INGREDIENT)
def test_category_1_records_block_on_harm_evidence_without_a_us_determination(entries, rule_id):
    entry = entries[rule_id]
    assert entry["status"] == "banned" and entry["match_mode"] == "active"
    assert entry["legal_status_enum"] == "under_review"
    assert entry["ban_context"] != "adulterant_in_supplements"
    assert _hard_policy_missing_requirements(entry, _signal(entry)) == []
    copy = " ".join(entry.get(k) or "" for k in ("reason", "safety_warning", "safety_warning_one_liner")).lower()
    for claim in ("not lawful", "not a lawful", "unlawful", "illegal", "fda banned", "fda-banned"):
        assert claim not in copy, (rule_id, claim)


def test_category_1_without_harm_evidence_is_quarantined(entries):
    entry = json.loads(json.dumps(entries["PEPTIDE_BPC157"]))
    for ref in entry["references_structured"]:
        ref["supports_claims"] = [c for c in ref.get("supports_claims") or []
                                  if c not in ("clinical_outcomes", "clinical_risk")]
    assert "verified_harm_evidence" in _hard_policy_missing_requirements(entry, _signal(entry))


def test_an_outcomes_tag_alone_is_not_harm_evidence(entries):
    """``clinical_outcomes`` also tags efficacy and product-analysis papers
    (fasoracetam's trial found no adverse-event difference from placebo)."""
    entry = json.loads(json.dumps(entries["BANNED_FASORACETAM"]))
    entry["policy_verification_status"] = "verified"
    assert "verified_harm_evidence" in _hard_policy_missing_requirements(entry, _signal(entry))


def test_amanita_muscaria_aliases_name_only_amanita_muscaria(entries):
    aliases = {a.lower() for a in entries["SCHED_AMANITA_MUSCARIA"]["aliases"]}
    assert not aliases & {"amanita pantherina", "panther cap", "legal shrooms"}


def test_regulatory_uncertainty_alone_never_blocks(entries):
    """Piracetam: under review, no harm evidence, not verified -> quarantine."""
    entry = entries["NOOTROPIC_PIRACETAM"]
    missing = _hard_policy_missing_requirements(entry, _signal(entry))
    assert "policy_verification_status" in missing


@pytest.mark.parametrize("rule_id", ENDED_RECALL)
def test_ended_recalls_never_block_by_product_name(entries, rule_id):
    assert entries[rule_id]["match_mode"] == "historical"


def test_retired_record_never_matches(entries):
    assert entries["SPIKE_METHYL7K"]["match_mode"] == "disabled"


@pytest.mark.parametrize("rule_id", QUARANTINE)
def test_category_3_records_stay_quarantined(entries, rule_id):
    entry = entries[rule_id]
    assert entry["match_mode"] == "active"
    assert entry.get("policy_verification_status") != "verified"


# --- defects found by the verification, fixed before routing ----------------

def _text(entry: dict) -> str:
    """The record's data, without its review log (which quotes what changed)."""
    return json.dumps({k: v for k, v in entry.items() if k != "review"}, ensure_ascii=False)


@pytest.mark.parametrize(
    "rule_id, gone",
    [
        ("BANNED_CALAMUS_ACORUS_CALAMUS", "189.140"),
        ("ADD_HEXADRONE", "Schedule III"),
        ("BANNED_DETERENOL_ISOPROPYLNORSYNEPHRINE", "32927348"),
        ("BANNED_CLENBUTEROL", "31887249"),
        ("PHARMA_LORCASERIN", "FDA voluntarily withdrew"),
        ("PHARMA_LORCASERIN", "FDA pulled it"),
        ("RECALLED_GOLD_STAR_DISTRIBUTION", "contaminated with Salmonella"),
        ("RECALLED_GOLD_STAR_DISTRIBUTION", "linked to Salmonella contamination"),
        ("RECALLED_HYDROXYCUT", "23 reports of severe liver injury"),
        ("SCHED_PSILOCYBIN", "DEA scheduling effective"),
        ("SCHED_PSILOCIN", "DEA scheduling effective"),
        ("PEPTIDE_BPC157", "trendione"),
        ("BANNED_IBOTENIC_ACID", "excitotoxic brain injury"),
        ("BANNED_IGF1", "acromegaly"),
        ("BANNED_SR9009", "bioavailability"),
        ("BANNED_CLENBUTEROL", "illicitly"),
        ("ADD_THYROGEN", "BLA 125104"),
        ("SPIKE_CHLOROPRETADALAFIL", "health-fixer-and-health-fixer-plus"),
        ("SPIKE_PROPOXYPHENYLSILDENAFIL", "health-fixer-and-health-fixer-plus"),
    ],
)
def test_verification_defect_is_gone(entries, rule_id, gone):
    assert gone not in _text(entries[rule_id])


def test_bpc157_carries_no_recall_scope(entries):
    assert entries["PEPTIDE_BPC157"].get("recall_scope") is None


def test_hexadrone_is_not_a_scheduled_steroid(entries):
    assert entries["ADD_HEXADRONE"]["legal_status_enum"] == "not_lawful_as_supplement"


def test_tramadol_blocks_for_its_us_schedule_not_for_wada(entries):
    entry = entries["WADA_TRAMADOL"]
    assert entry["legal_status_enum"] == "controlled_substance"
    assert "WADA" not in entry["safety_warning_one_liner"]


# --- the reader's label -------------------------------------------------------

@pytest.mark.parametrize(
    "rule_id, status, expected_prefix",
    [
        ("PEPTIDE_BPC157", "banned", "Unverified ingredient"),
        ("BANNED_CLENBUTEROL", "banned", "Unverified ingredient"),
        ("ADD_HORDENINE", "banned", "Not lawful as a supplement"),
        ("ADD_HEXADRONE", "banned", "Not lawful as a supplement"),
        ("WADA_TRAMADOL", "banned", "Controlled substance"),
        ("SPIKE_SILDENAFIL", "banned", "Hidden drug"),
        ("WADA_CANNABIS", "banned", "Not lawful as a supplement"),
        ("RECALLED_BIQ_FEL", "recalled", "Recalled product"),
    ],
)
def test_core_row_title_states_the_route(rule_id, status, expected_prefix):
    from build_final_db import build_top_warnings
    from test_build_final_db import make_enriched

    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [{
        "ingredient": "X", "id": rule_id, "status": status, "match_type": "exact",
    }]
    titles = [w["title"] for w in build_top_warnings(enriched)
              if w.get("type") in ("banned_substance", "recalled_ingredient")]
    assert titles == [f"{expected_prefix}: X"]


# --- THC: explicit identity only; ordinary hemp never inherits the block ------
# Corpus hemp strings measured 2026-10-02 (0 labels declared THC).
HEMP_LABEL_STRINGS = (
    "Hemp Seed Oil", "Hemp seed Protein", "Hemp Protein", "organic Hemp Protein", "Hemp Hearts",
    "Hemp Extract", "Broad Spectrum Hemp extract blend", "Broad Spectrum Hemp Oil extract",
    "Broad Spectrum Hemp Whole Plant Oil Extract", "Hemp Oil (aerial plant parts) extract",
    "Full Spectrum Hemp Extract", "Full Spectrum Hemp Extract (<0.3% THC)", "Hemp extract, THC-free",
    "Broad Spectrum Phytocannabinoids", "Cannabidiol",
)
THC_LABEL_STRINGS = ("THC", "Delta-9-Tetrahydrocannabinol", "delta 9 thc", "Tetrahydrocannabinol")


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def _banned_ids(enricher, name):
    result = enricher._check_banned_substances([{"name": name, "standardName": name}])
    return {s.get("banned_id") for s in result.get("substances", [])}


@pytest.mark.parametrize("label", HEMP_LABEL_STRINGS)
def test_hemp_labels_never_match_the_thc_rule(enricher, label):
    assert "WADA_CANNABIS" not in _banned_ids(enricher, label)


@pytest.mark.parametrize("label", THC_LABEL_STRINGS)
def test_explicit_thc_matches_the_thc_rule(enricher, label):
    assert "WADA_CANNABIS" in _banned_ids(enricher, label)
