"""Per-entry CUI integrity tests — one assertion per Wave-6.Y correction.

Each test:
  1. Locks the IQM parent's `cui` to the clinician-authorized value.
  2. Locks `scripts/data/curated_interactions/curated_interactions_v1.json` to
     not reference the prior (wrong) CUI as `agent2_id`.

Pattern (per CLAUDE.md "small batches, decomposed problems" and
"write the failing regression assertion … BEFORE the fix"):

  - Failing tests land in this file before the IQM / curated_interactions
    edits are applied for that entry.
  - When the edit is applied, the assertion flips green.
  - Each correction is its own atomic commit.

Source of authority for the corrections: clinician review of
`reports/iqm_identifier_sweep/reviewed_queue.csv` produced by
`scripts/api_audit/iqm_identifier_sweep.py`. The wrong-CUI evidence for each
test is content-verified via UMLS REST API (see per_parent/<id>.json snapshot
for the cached response).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IQM_PATH = REPO_ROOT / "scripts" / "data" / "ingredient_quality_map.json"
CI_PATH = REPO_ROOT / "scripts" / "data" / "curated_interactions" / "curated_interactions_v1.json"


@pytest.fixture(scope="module")
def iqm():
    return json.loads(IQM_PATH.read_text())


@pytest.fixture(scope="module")
def curated_interactions():
    return json.loads(CI_PATH.read_text())


def _agent2_ids(curated: dict) -> list[str]:
    """Collect every agent2_id value across all entries in curated_interactions_v1.json."""
    out: list[str] = []
    # Schema: top-level object with 'entries' or array of rules; iterate generously.
    if isinstance(curated, dict):
        for v in curated.values():
            if isinstance(v, list):
                for row in v:
                    if isinstance(row, dict) and "agent2_id" in row:
                        out.append(str(row["agent2_id"]))
    return out


# --------------------------------------------------------------------------- #
# Batch 1 — Seed fixes from reviewed_queue.csv (status=fix_cui)
# --------------------------------------------------------------------------- #


def test_coq10_cui_is_canonical_ubidecarenone(iqm):
    """coq10 must use UMLS C0041536 (ubidecarenone) — the Organic Chemical /
    Pharmacologic Substance CUI for the actual compound. C1843920 was the
    'COENZYME Q10 DEFICIENCY' Disease-or-Syndrome CUI (hallucination caught
    by the 2026-05-27 IQM identifier sweep, strict-mode Disease guard)."""
    assert iqm["coq10"]["cui"] == "C0041536", (
        "coq10.cui must be the substance CUI (C0041536, ubidecarenone), "
        "not the disease CUI (C1843920, 'COENZYME Q10 DEFICIENCY')."
    )


def test_no_curated_interaction_uses_coq10_disease_cui(curated_interactions):
    """No row in curated_interactions_v1.json may have agent2_id=C1843920
    (the 'COENZYME Q10 DEFICIENCY' disease CUI). Any such row would resolve
    to the wrong concept through `verify_interactions.build_iqm_cui_index`.
    """
    bad = "C1843920"
    matches = [a for a in _agent2_ids(curated_interactions) if a == bad]
    assert not matches, (
        f"Found {len(matches)} curated_interactions rows still using the "
        f"disease CUI {bad}. They must be updated to C0041536 (ubidecarenone)."
    )

def test_5_htp_cui_is_canonical_5_hydroxytryptophan(iqm):
    """5_htp must use UMLS C0000578 (5-hydroxytryptophan) — the Organic
    Chemical CUI for the compound. C5815882 was the 'Natrol Melatonin + 5-HTP'
    combo product CUI (hallucination caught by the 2026-05-27 sweep, strict-
    mode multi-compound combo guard via the ' + ' marker in the candidate name)."""
    assert iqm["5_htp"]["cui"] == "C0000578", (
        "5_htp.cui must be the generic compound CUI (C0000578, "
        "5-hydroxytryptophan), not the branded combo CUI (C5815882, "
        "'Natrol Melatonin + 5-HTP')."
    )


def test_no_curated_interaction_uses_5_htp_combo_cui(curated_interactions):
    """No row may reference C5815882, the branded combo product CUI for 5-HTP.
    """
    bad = "C5815882"
    matches = [a for a in _agent2_ids(curated_interactions) if a == bad]
    assert not matches, (
        f"Found {len(matches)} curated_interactions rows still using the "
        f"branded combo CUI {bad}. They must be updated to C0000578."
    )


# --------------------------------------------------------------------------- #
# Batch 2A — Wrong-concept CUI corrections (no curated_interactions impact)
# --------------------------------------------------------------------------- #


def test_acacia_catechu_cui_is_canonical_plant(iqm):
    """acacia_catechu must use C1135823 (Acacia catechu, Plant semantic type).
    C0949533 resolved to 'Australian bat lyssavirus' — a virus, not the plant.
    Caught by no-token-overlap guard."""
    assert iqm["acacia_catechu"]["cui"] == "C1135823", (
        "acacia_catechu.cui must be C1135823 (Acacia catechu, Plant), not "
        "C0949533 ('Australian bat lyssavirus')."
    )


def test_cayenne_pepper_cui_is_canonical_food_concept(iqm):
    """cayenne_pepper must use C0007480 (Cayenne Pepper, Food semantic type).
    C0006909 resolved to 'Capital' — no overlap. Caught by no-token-overlap
    guard. The old wrong CUI must also no longer appear in the entry's
    aliases array (it was previously stored there as a 'hint')."""
    entry = iqm["cayenne_pepper"]
    assert entry["cui"] == "C0007480", (
        "cayenne_pepper.cui must be C0007480 ('Cayenne Pepper', Food), not "
        "C0006909 ('Capital')."
    )
    assert "C0006909" not in (entry.get("aliases") or []), (
        "cayenne_pepper.aliases must no longer contain the wrong CUI C0006909."
    )


def test_cla_cui_is_canonical_conjugated_linoleic_acid(iqm):
    """cla must use C0050156 ('Conjugated Linoleic Acid', Organic Chemical).
    C0055856 resolved to 'clarithromycin' — an antibiotic, completely
    unrelated. Caught by no_token_overlap guard. The correct CUI C0050156
    was previously stored as a hint in aliases; we promote it to the
    canonical `cui` field and remove the now-redundant alias entry."""
    entry = iqm["cla"]
    assert entry["cui"] == "C0050156", (
        "cla.cui must be C0050156 ('Conjugated Linoleic Acid'), not "
        "C0055856 (clarithromycin, the macrolide antibiotic)."
    )
    assert "C0050156" not in (entry.get("aliases") or []), (
        "cla.aliases must no longer contain C0050156 as a hint — it is now "
        "the canonical cui field."
    )


def test_english_ivy_cui_is_canonical_hedera_helix(iqm):
    """english_ivy must use C0331030 ('Hedera helix', Plant). C0949841
    resolved to 'Phosphate Carriers' — biochemistry concept, completely
    unrelated to the plant species. Caught by no_token_overlap guard. The
    old wrong CUI was stored as a hint in aliases; it has been removed."""
    entry = iqm["english_ivy"]
    assert entry["cui"] == "C0331030", (
        "english_ivy.cui must be C0331030 ('Hedera helix', Plant), not "
        "C0949841 ('Phosphate Carriers')."
    )
    assert "C0949841" not in (entry.get("aliases") or []), (
        "english_ivy.aliases must no longer contain the wrong CUI C0949841."
    )


def test_horse_chestnut_seed_cui_is_canonical(iqm):
    """horse_chestnut_seed must use C0874047 ('horse chestnut seed', Organic
    Chemical / Pharmacologic Substance). C0001443 resolved to 'adenosine'
    (the nucleoside) — likely a copy/paste from the IQM 'adenosine' entry
    (which legitimately uses C0001443). Caught by no_token_overlap guard.
    Adenosine's own use of C0001443 is correct and untouched."""
    entry = iqm["horse_chestnut_seed"]
    assert entry["cui"] == "C0874047", (
        "horse_chestnut_seed.cui must be C0874047 ('horse chestnut seed'), "
        "not C0001443 (adenosine, the nucleoside)."
    )
    assert "C0001443" not in (entry.get("aliases") or []), (
        "horse_chestnut_seed.aliases must no longer contain the wrong CUI "
        "C0001443 (which is the canonical CUI for adenosine, not horse chestnut)."
    )
    # Sanity: adenosine itself should still have C0001443.
    assert iqm.get("adenosine", {}).get("cui") == "C0001443", (
        "Sanity check failed — adenosine.cui must remain C0001443 (the "
        "correct CUI for the nucleoside). Only horse_chestnut_seed was fixed."
    )


def test_silicon_cui_is_canonical_element(iqm):
    """silicon must use C0037107 ('silicon', semantic type 'Element, Ion,
    or Isotope') — the canonical elemental-silicon concept. C0037114 had
    no token overlap with 'silicon' (resolves to an unrelated concept).
    The correct CUI C0037107 was previously stored as a hint in aliases;
    we promote it to the canonical `cui` field and clean up the alias."""
    entry = iqm["silicon"]
    assert entry["cui"] == "C0037107", (
        "silicon.cui must be C0037107 ('silicon', Element/Ion/Isotope), "
        "not C0037114."
    )
    assert "C0037107" not in (entry.get("aliases") or []), (
        "silicon.aliases must no longer contain C0037107 — it is now the "
        "canonical cui field."
    )


# --------------------------------------------------------------------------- #
# Batch 2B — Branded clinical-drug CUI corrections (mostly IQM-only)
# --------------------------------------------------------------------------- #


def test_alpha_gpc_cui_is_canonical_glycerylphosphorylcholine(iqm):
    """alpha_gpc must use C0017889 ('glycerylphosphorylcholine', Organic
    Chemical / Biologically Active Substance). C5762292 was a branded
    'Jarrow Formulas Alpha GPC Capsules' (Clinical Drug). Caught by
    branded-drug guard."""
    assert iqm["alpha_gpc"]["cui"] == "C0017889", (
        "alpha_gpc.cui must be C0017889 (glycerylphosphorylcholine, the "
        "generic substance), not C5762292 (Jarrow Formulas branded capsule)."
    )


def test_borage_seed_oil_cui_is_canonical(iqm):
    """C5982013 was a branded 'borage seed oil 1300 MG Oral Capsule' (Clinical
    Drug). C0212750 'borage oil' (Organic Chemical / Pharmacologic Substance
    / Food) is the canonical generic concept — accepted via reverse-check on
    'Borage Seed Oil'."""
    assert iqm["borage_seed_oil"]["cui"] == "C0212750", (
        "borage_seed_oil.cui must be C0212750 (borage oil), not C5982013 "
        "(branded oral capsule)."
    )


def test_citrus_bergamot_cui_is_canonical(iqm):
    """C5762301 was a branded 'Jarrow Formulas Citrus Bergamot Capsules'
    (Clinical Drug). C0725330 'Bergamot' (Food) is the canonical concept
    and was already stored as a hint in aliases; promoted to canonical."""
    entry = iqm["citrus_bergamot"]
    assert entry["cui"] == "C0725330", (
        "citrus_bergamot.cui must be C0725330 (Bergamot, Food), not "
        "C5762301 (Jarrow branded capsule)."
    )
    assert "C0725330" not in (entry.get("aliases") or []), (
        "citrus_bergamot.aliases must no longer contain C0725330 hint."
    )


def test_gamma_oryzanol_cui_is_canonical(iqm):
    """C5979108 was a branded multi-ingredient capsule. C0061081
    'gamma-oryzanol' (Organic Chemical) is the canonical generic substance."""
    assert iqm["gamma_oryzanol"]["cui"] == "C0061081", (
        "gamma_oryzanol.cui must be C0061081 (gamma-oryzanol)."
    )


def test_hemp_seed_oil_cui_is_canonical(iqm):
    """C5777771 was a branded topical cream containing hemp seed oil
    (Clinical Drug). C4489800 'hempseed oil' (Organic Chemical) is the
    canonical generic substance — accepted via reverse-check on 'Hemp Seed Oil'."""
    assert iqm["hemp_seed_oil"]["cui"] == "C4489800", (
        "hemp_seed_oil.cui must be C4489800 (hempseed oil)."
    )


def test_lions_mane_cui_is_canonical_mushroom_not_jellyfish(iqm):
    """C6011652 was a branded 'Black Pepper Extract/Lion's Mane Mushroom'
    capsule (Clinical Drug). C6049163 'Lion's Mane Mushroom' (Organic
    Chemical / Pharmacologic Substance) is the canonical mushroom concept.

    Note: UMLS exact-search for 'Lion's Mane' also returns C1001731 (the
    jellyfish Cyanea capillata) — explicitly NOT the supplement context.
    The strict-mode guards don't differentiate jellyfish vs mushroom for
    the common name, so the correct mushroom CUI was picked by clinician
    judgment, not by automated guards alone."""
    assert iqm["lions_mane"]["cui"] == "C6049163", (
        "lions_mane.cui must be C6049163 (Lion's Mane Mushroom), not "
        "C6011652 (branded capsule) and NOT C1001731 (Cyanea capillata, the "
        "lion's mane JELLYFISH — entirely different organism)."
    )


def test_mastic_gum_cui_is_canonical(iqm):
    """C5709624 was 'Mastic Gum 500 MG Oral Capsule' (Clinical Drug).
    C0164196 'GUM MASTIC PREPARATION' (Pharmacologic Substance) is the
    canonical generic concept."""
    assert iqm["mastic_gum"]["cui"] == "C0164196", (
        "mastic_gum.cui must be C0164196 (GUM MASTIC PREPARATION)."
    )


def test_neem_cui_is_canonical_azadirachta_indica(iqm):
    """C5670607 was a branded Neem capsule (Clinical Drug). C1095052
    'Azadirachta indica' (Plant) is the canonical species concept —
    accepted via reverse-check on 'Neem'."""
    assert iqm["neem"]["cui"] == "C1095052", (
        "neem.cui must be C1095052 (Azadirachta indica)."
    )


def test_noni_cui_is_canonical_morinda_citrifolia(iqm):
    """C1814348 was 'MORINDA (NONI) CAP/TAB' (Clinical Drug). C1010822
    'Morinda citrifolia' (Plant) is the canonical species concept —
    accepted via reverse-check on 'Noni'."""
    assert iqm["noni"]["cui"] == "C1010822", (
        "noni.cui must be C1010822 (Morinda citrifolia)."
    )


def test_shilajit_cui_is_canonical_mumie(iqm):
    """C3709449 was a branded 'Shilajit 250 MG Oral Capsule' (Clinical Drug).
    C0066936 'mumie' (Organic Chemical / Pharmacologic Substance) — mumie /
    mumiyo is the alternate name for shilajit (Russian transliteration of
    the same mineral-pitch resin) — is the canonical generic concept,
    accepted via UMLS reverse-check on 'Shilajit'."""
    assert iqm["shilajit"]["cui"] == "C0066936", (
        "shilajit.cui must be C0066936 (mumie)."
    )


def test_theacrine_cui_is_canonical_tetramethyluric_acid(iqm):
    """C5778236 was a branded multi-ingredient capsule containing theacrine
    (Clinical Drug). C0654300 '1,3,7,9-tetramethyluric acid' (Organic
    Chemical / Pharmacologic Substance) — the IUPAC name for theacrine —
    is the canonical generic substance."""
    assert iqm["theacrine"]["cui"] == "C0654300", (
        "theacrine.cui must be C0654300 (1,3,7,9-tetramethyluric acid)."
    )


def test_turkey_tail_cui_cleared_to_null_with_note(iqm):
    """C6011676 was a branded multi-mushroom capsule (Clinical Drug). No
    clean single-CUI candidate exists for 'Turkey Tail' under strict-mode
    guards — UMLS does not link the common name to the species CUI
    (Coriolus/Trametes versicolor). Per the null-CUI policy, cleared to
    null with cui_status='no_confirmed_umls_match' and cui_note documenting
    the deferred ontology question."""
    entry = iqm["turkey_tail"]
    assert entry["cui"] is None, (
        "turkey_tail.cui must be null (no confirmed UMLS match)."
    )
    assert entry.get("cui_status") == "no_confirmed_umls_match"
    assert entry.get("cui_note"), "turkey_tail must have a cui_note explaining the null"


def test_white_willow_bark_cui_is_canonical(iqm):
    """C0936557 had no token overlap with 'White Willow Bark' under strict
    guards. C2349151 'Salix alba bark extract' (Organic Chemical /
    Pharmacologic Substance) is the canonical concept, accepted via
    reverse-check on 'White Willow Bark'."""
    assert iqm["white_willow_bark"]["cui"] == "C2349151", (
        "white_willow_bark.cui must be C2349151 (Salix alba bark extract)."
    )


def test_no_curated_interaction_uses_white_willow_bark_old_cui(curated_interactions):
    """Propagation check: no row may still reference C0936557 — it must
    have been updated to C2349151."""
    matches = [a for a in _agent2_ids(curated_interactions) if a == "C0936557"]
    assert not matches, (
        f"Found {len(matches)} curated_interactions rows still using the "
        "old white_willow_bark CUI C0936557; must be C2349151."
    )


# --------------------------------------------------------------------------- #
# Batch 2C — Class/extract/mixture CUI corrections (or nulls)
# --------------------------------------------------------------------------- #


def test_branched_chain_amino_acids_cui_is_canonical(iqm):
    """C0359316 was 'Branched chain amino acids infusion' (Clinical Drug —
    the IV-infusion product). C0002521 'Amino Acids, Branched-Chain' (Amino
    Acid/Peptide/Protein / Biologically Active Substance) is the canonical
    class-level concept for the supplement context."""
    assert iqm["branched_chain_amino_acids"]["cui"] == "C0002521", (
        "branched_chain_amino_acids.cui must be C0002521 (the class concept), "
        "not C0359316 (the IV infusion clinical drug)."
    )


def test_flower_pollen_cui_is_canonical_source(iqm):
    """C4073752 was 'Quercetin/Rye Flower Pollen Extract 250 MG-500 MG Oral
    Tablet' (Clinical Drug, combo). C1328880 'flower pollen' (Plant) is the
    canonical source-substance concept — UMLS has no exact match for
    'Flower Pollen Extract' (the extract form), so the parent-source
    concept is the closest defensible substance."""
    assert iqm["flower_pollen"]["cui"] == "C1328880", (
        "flower_pollen.cui must be C1328880 (flower pollen, Plant)."
    )


def test_olive_fruit_extract_cui_is_canonical(iqm):
    """C6017333 was a branded combo capsule containing olive extract among
    other ingredients (Clinical Drug). C1365464 'Olive extract' (Organic
    Chemical / Pharmacologic Substance) is the canonical generic concept.
    The narrower 'Olea europaea whole extract' (C3539016) would include
    leaves; the IQM entry is fruit-extract specifically, so the generic
    'Olive extract' concept is the best defensible match."""
    assert iqm["olive_fruit_extract"]["cui"] == "C1365464", (
        "olive_fruit_extract.cui must be C1365464 (Olive extract)."
    )


def test_omega_6_fatty_acids_cui_is_canonical(iqm):
    """C5918245 was a branded clinical-drug CUI. C0133860 'fatty acids,
    omega-6' (Organic Chemical / Biologically Active Substance) is the
    canonical class concept — was already stored as a hint in aliases;
    promoted to canonical and stale alias removed."""
    entry = iqm["omega_6_fatty_acids"]
    assert entry["cui"] == "C0133860", (
        "omega_6_fatty_acids.cui must be C0133860 (fatty acids, omega-6)."
    )
    assert "C0133860" not in (entry.get("aliases") or []), (
        "omega_6_fatty_acids.aliases must no longer contain C0133860 as a hint."
    )


def test_purple_corn_extract_cui_cleared_to_null(iqm):
    """C1446590 had no token overlap and no UMLS exact-match candidate
    survives strict-mode guards. Class-broader (Anthocyanins) and
    narrower-specific (cyanidin) markers exist but neither IS the extract
    concept. Per null-CUI policy, cleared to null with cui_status and
    cui_note documenting the deferral."""
    entry = iqm["purple_corn_extract"]
    assert entry["cui"] is None, "purple_corn_extract.cui must be null."
    assert entry.get("cui_status") == "no_confirmed_umls_match"
    assert entry.get("cui_note"), "purple_corn_extract must have a cui_note"
    assert "C1446590" not in (entry.get("aliases") or []), (
        "purple_corn_extract.aliases must no longer contain the wrong CUI."
    )


# --------------------------------------------------------------------------- #
# Stale cui_note / cui_status guard (Task #13, Wave 6.Y cleanup pass)
# --------------------------------------------------------------------------- #


_STALE_NOTE_TOKENS = (
    "no umls entry for",
    "no umls cui for",
    "no umls cui established",
    "no umls cui assigned",
    "no umls cui confirmed",
    "no confirmed umls concept",
    "no confirmed exact umls concept",
    "no umls concept linked",
)


# --------------------------------------------------------------------------- #
# Batch 3 — Cleared deprecated RxCUIs (no record in RxNav)
# --------------------------------------------------------------------------- #


def test_bilberry_rxcui_replayed_to_verified_extract_concept(iqm):
    """Prior rxcui '11155' returned no record in RxNav and was cleared.
    The 2026-06-06 replay found a live bilberry-extract RxCUI."""
    entry = iqm["bilberry"]
    assert entry["rxcui"] == "125929", "bilberry.rxcui must be RxCUI 125929 (bilberry extract)."


def test_cryptoxanthin_rxcui_cleared_to_null(iqm):
    """Prior rxcui '1116063' returns no record in RxNav."""
    entry = iqm["cryptoxanthin"]
    assert entry["rxcui"] is None, "cryptoxanthin.rxcui must be null."
    assert entry.get("rxcui_note")


def test_goldenseal_rxcui_cleared_to_null(iqm):
    """Prior rxcui '253171' returns no record in RxNav."""
    entry = iqm["goldenseal"]
    assert entry["rxcui"] is None, "goldenseal.rxcui must be null."
    assert entry.get("rxcui_note")


def test_sulforaphane_rxcui_cleared_to_null(iqm):
    """Prior rxcui '1116060' returns no record in RxNav."""
    entry = iqm["sulforaphane"]
    assert entry["rxcui"] is None, "sulforaphane.rxcui must be null."
    assert entry.get("rxcui_note")


# --------------------------------------------------------------------------- #
# Batch 4 — defer_clinician_review adjudication (2026-05-27)
# --------------------------------------------------------------------------- #


def test_deferred_cas_findings_are_gsrs_confirmed_not_pubchem_compounds(iqm):
    """These CAS values are valid GSRS substance identifiers for botanicals,
    proteins, enzymes, or mixtures. PubChem has no single compound CID for
    them, so the fix is explicit documentation rather than deletion."""
    expected = {
        "black_cherry": "84604-07-9",
        "black_seed_oil": "90064-32-7",
        "bromelain": "9001-00-7",
        "cascara_sagrada": "8015-89-2",
        "casein": "9000-71-9",
        "goji_berry": "85085-46-7",
        "pepsin": "9001-75-6",
        "whey_protein": "91082-88-1",
    }
    for canonical_id, cas in expected.items():
        external_ids = iqm[canonical_id]["external_ids"]
        assert external_ids["cas"] == cas
        note = external_ids.get("cas_note", "")
        assert "GSRS" in note and "PubChem" in note, canonical_id


def test_deferred_unii_proxy_mappings_are_cleared(iqm):
    """Reject UNIIs that resolve to a component, source organism/plant, or
    narrower subtype rather than the IQM parent ingredient."""
    cleared = {
        "chitosan": "8SH93A7QWW",
        "gypenosides": "CHC1JS541R",
        "organ_extracts": "W8N8R55022",
        "phytosterols": "S347WMO6M4",
        "shilajit": "XII14C5FXV",
        "vitamin_e": "KP2MW85SSQ",
        "wheatgrass": "3C3Y389JBU",
    }
    for canonical_id, old_unii in cleared.items():
        external_ids = iqm[canonical_id]["external_ids"]
        assert external_ids.get("unii") is None, canonical_id
        note = external_ids.get("unii_note", "")
        assert old_unii in note and "Cleared 2026-05-27" in note, canonical_id


def test_deferred_cui_semantic_findings_are_resolved(iqm):
    """Wrong functional/object CUIs are corrected to exact substance CUIs;
    deer antler velvet keeps the exact source-material concept because no
    better ingredient-level UMLS concept exists."""
    assert iqm["cape"]["cui"] == "C0054434"
    assert "C0453952" in iqm["cape"].get("cui_note", "")

    assert iqm["diamine_oxidase"]["cui"] == "C0019587"
    assert "C3155423" in iqm["diamine_oxidase"].get("cui_note", "")

    assert iqm["nmn"]["cui"] == "C0597067"
    assert "C1159803" in iqm["nmn"].get("cui_note", "")

    same = iqm["same"]
    assert same["cui"] == "C0036002"
    assert "C0445247" in same.get("cui_note", "")
    assert "C0036002" not in (same.get("aliases") or [])

    deer = iqm["deer_antler_velvet"]
    assert deer["cui"] == "C0222040"
    assert "Clinician-adjudicated keep 2026-05-27" in deer.get("cui_note", "")


def test_same_curated_interactions_use_promoted_substance_cui(curated_interactions):
    agent2_ids = _agent2_ids(curated_interactions)
    assert "C0445247" not in agent2_ids
    assert agent2_ids.count("C0036002") == 2


def test_no_entry_with_valid_cui_carries_stale_no_umls_note(iqm):
    """Regression: when `cui` is non-null, neither cui_note nor cui_status
    may still claim that UMLS has no entry / no confirmed match. Such notes
    are semantically stale once a valid CUI has been chosen and confuse
    future reviewers and agents.

    Legitimate notes (e.g. 'Corrected from X to Y', 'UMLS CUI: ...',
    'Class entry spans multiple ...') are preserved — only the documented
    'No UMLS ...' / 'No confirmed UMLS ...' phrasings are forbidden when
    cui is set.
    """
    offenders = []
    for cid, entry in iqm.items():
        if cid.startswith("_") or not isinstance(entry, dict):
            continue
        if not entry.get("cui"):
            continue
        note = (entry.get("cui_note") or "").strip().lower()
        status = (entry.get("cui_status") or "").strip().lower()
        if status == "no_confirmed_umls_match":
            offenders.append((cid, "cui_status='no_confirmed_umls_match'"))
            continue
        if note and any(tok in note for tok in _STALE_NOTE_TOKENS):
            offenders.append((cid, f"cui_note=<{note[:60]}…>"))
    assert not offenders, (
        f"{len(offenders)} IQM entries have valid `cui` but still carry "
        f"stale 'No UMLS ...' notes / 'no_confirmed_umls_match' status. "
        f"Examples: {offenders[:5]}"
    )


def test_no_entry_with_valid_rxcui_carries_stale_no_rxnorm_note(iqm):
    """If an RxCUI is present, notes may document verification, but they must
    not still claim that no RxNorm concept was found."""
    offenders = []
    for cid, entry in iqm.items():
        if cid.startswith("_") or not isinstance(entry, dict):
            continue
        if not entry.get("rxcui"):
            continue
        note = (entry.get("rxcui_note") or "").strip().lower()
        if "no rxnorm concept found" in note or "no rxnorm concept" in note:
            offenders.append((cid, entry.get("rxcui"), note[:80]))
    assert not offenders, (
        f"{len(offenders)} IQM entries have valid `rxcui` but stale no-RxNorm "
        f"notes. Examples: {offenders[:5]}"
    )


# --------------------------------------------------------------------------- #
# Batch 4 — Clinician-adjudicated species/taxonomy mappings (defer_ambiguous)
# --------------------------------------------------------------------------- #
#
# These 5 entries fail strict-mode no_token_overlap because UMLS preferred
# names are Latin species while IQM names are common names. UMLS has no
# atom linking the common name to the species CUI, so the orchestrator's
# reverse-check cannot rescue them. The species CUIs are nonetheless
# correct under modern taxonomy, so each is documented as a clinician-
# adjudicated exception with a cui_note explaining why.

_BATCH_4_DEFER_AMBIGUOUS = [
    ("french_oak",            "C0330306"),  # Quercus robur, Plant
    ("lychee_polyphenol",     "C1072272"),  # Litchi chinensis, Plant — source species; IQM entry is the polyphenol fraction
    ("maqui_berry",           "C1067051"),  # Aristotelia chilensis, Plant
    ("saccharomyces_exiguus", "C1940772"),  # Kazachstania exigua, Fungus — taxonomy reclassification
    ("split_gill_polypore",   "C0319679"),  # Schizophyllum commune, Fungus
]


@pytest.mark.parametrize("canonical_id,expected_cui", _BATCH_4_DEFER_AMBIGUOUS)
def test_batch_4_defer_ambiguous_cui_locked_with_note(iqm, canonical_id, expected_cui):
    """Regression-lock: each defer_ambiguous entry retains its
    clinician-adjudicated species/taxonomy CUI AND has a non-empty cui_note
    documenting the species/common-name (or taxonomy synonym) mapping.

    Future agents that "fix" these via the strict-mode guard alone would
    break the species mapping — the cui_note is the load-bearing context."""
    entry = iqm[canonical_id]
    assert entry["cui"] == expected_cui, (
        f"{canonical_id}.cui must remain {expected_cui} (clinician-adjudicated "
        f"species/taxonomy mapping per Wave 6.Y Batch 4)."
    )
    note = (entry.get("cui_note") or "").strip()
    assert note, (
        f"{canonical_id} must carry a cui_note explaining the species/"
        f"taxonomy mapping (strict-mode guard cannot rescue these; the note "
        f"is the load-bearing documentation)."
    )


# --------------------------------------------------------------------------- #
# Batch 5 — Policy-lock for keep_verified_alias entries
# --------------------------------------------------------------------------- #
#
# These 6 entries fail the orchestrator's strict-mode no_token_overlap guard
# because of a near-identity spelling/plural/class variance with the UMLS
# preferred name (cynarin/cynarine, fluoride/Fluorides, etc.). The clinician
# (review 2026-05-27) explicitly classified all 6 as 'keep_verified_alias' —
# accept the current CUI as a verified spelling/plural variant of the same
# concept. A future agent that mechanically follows the strict-mode guard
# could "fix" these and break the mapping; this test locks them in place.

_BATCH_5_KEEP_VERIFIED_ALIAS = [
    # canonical_id, locked cui, UMLS preferred name, why it's accepted
    ("cynarin",              "C0056848", "cynarine",              "spelling variant — same compound"),
    ("ecdysterones",         "C0013495", "Ecdysterone",           "plural vs singular — same class"),
    ("fluoride",             "C0016327", "Fluorides",             "class/plural — clinically acceptable identity"),
    ("gypenosides",          "C0905527", "gypenoside",            "plural vs singular — same class"),
    ("phosphatidylinositol", "C0031621", "phosphatidylinositols", "singular vs plural — same compound family"),
    ("protein",              "C0033684", "Proteins",              "class-level — acceptable as a class identity"),
]


@pytest.mark.parametrize(
    "canonical_id,locked_cui,umls_preferred_name,rationale",
    _BATCH_5_KEEP_VERIFIED_ALIAS,
)
def test_batch_5_keep_verified_alias_cui_locked(
    iqm, canonical_id, locked_cui, umls_preferred_name, rationale
):
    """Policy lock: each keep_verified_alias entry retains its
    clinician-approved CUI despite the strict-mode no_token_overlap
    guard intentionally flagging it (the variance is plural/spelling,
    not a wrong concept).

    Why this test exists: in commits Wave 6.Y Batches 1, 2A, 2B, 2C the
    same strict-mode guard caught real hallucinations and was used to
    drive 27 atomic IQM corrections. The same guard would also "fix"
    these 6 — but doing so would break the mapping rather than improve
    it. The clinician walked the report on 2026-05-27 and marked these
    as keep_verified_alias; this assertion makes that decision durable.
    """
    entry = iqm[canonical_id]
    assert entry["cui"] == locked_cui, (
        f"{canonical_id}.cui must remain {locked_cui} (UMLS preferred name "
        f"'{umls_preferred_name}'; clinician-approved {rationale}). If a "
        f"sweep agent wants to change this, escalate to clinician review — "
        f"do not rely on the strict-mode guard."
    )


# --------------------------------------------------------------------------- #
# Batch 6 — 2026-06-06 Claude-branch identifier replay onto current main
# --------------------------------------------------------------------------- #
#
# Source: scripts/audit/iqm_cui_changes.csv and iqm_rxcui_changes.csv from
# claude/eloquent-ride-Bq8cO, replayed selectively after live UMLS/RxNav
# verification on current main. This intentionally does NOT replay stale null
# recommendations where current RxNav resolves a broad ingredient concept.

_BATCH_6_CUI_REPLAY = [
    ("alpha_lipoic_acid", "C0023791", "thioctic acid", "replaces meglumine-specific C5763195"),
    ("brown_kelp", "C0022980", "Laminaria", "fills missing kelp parent concept"),
    ("common_bean_extract", "C4321296", "Phaseolus vulgaris whole extract", "fills missing extract concept"),
    ("cryptoxanthin", "C0896117", "Beta-Cryptoxanthin", "replaces broad cryptoxanthins plural class"),
    ("d_limonene", "C0064992", "limonene", "replaces D-limonene shampoo concept"),
    ("dandelion", "C0877851", "Taraxacum officinale", "locks the plant parent rather than extract-only concept"),
    ("horsetail", "C0331746", "Equisetum arvense", "locks the plant parent rather than herb-only concept"),
    ("l_carnitine", "C0087163", "levocarnitine", "replaces L-carnitine dehydratase enzyme"),
    ("l_ornithine", "C0029277", "ornithine", "replaces L-ornithine L-aspartate combination"),
    ("milk_thistle", "C0331428", "Milk Thistle", "locks the plant parent rather than extract-only concept"),
]


@pytest.mark.parametrize("canonical_id,expected_cui,umls_name,rationale", _BATCH_6_CUI_REPLAY)
def test_batch_6_replayed_cui_corrections_are_locked(
    iqm, canonical_id, expected_cui, umls_name, rationale
):
    entry = iqm[canonical_id]
    assert entry["cui"] == expected_cui, (
        f"{canonical_id}.cui must be {expected_cui} ({umls_name}); {rationale}."
    )
    assert expected_cui not in (entry.get("aliases") or []), (
        f"{canonical_id}.aliases must not keep promoted canonical CUI {expected_cui}."
    )


_BATCH_6_RXCUI_REPLAY = [
    ("5_htp", "94", "5-hydroxytryptophan"),
    ("alpha_lipoic_acid", "6417", "thioctic acid"),
    ("bilberry", "125929", "bilberry extract"),
    ("chondroitin", "2473", "chondroitin sulfates"),
    ("gaba", "4617", "gamma-aminobutyric acid"),
    ("garlic", "265647", "garlic preparation"),
    ("ginkgo", "236809", "Ginkgo biloba extract"),
    ("ginseng", "325526", "ginseng preparation"),
    ("milk_thistle", "259274", "milk thistle seed extract"),
    ("phosphatidylserine", "89959", "phosphatidylserine"),
    ("policosanol", "69440", "policosanol"),
    ("psyllium", "8928", "psyllium"),
    ("saw_palmetto", "236344", "saw palmetto extract"),
    ("superoxide_dismutase", "10245", "superoxide dismutase"),
    ("taurine", "10337", "taurine"),
    ("vitamin_e", "11256", "vitamin E"),
    ("vitamin_k1", "8308", "vitamin K1"),
    ("zinc", "11416", "zinc"),
]


@pytest.mark.parametrize("canonical_id,expected_rxcui,rxnorm_name", _BATCH_6_RXCUI_REPLAY)
def test_batch_6_replayed_rxcui_corrections_are_locked(
    iqm, canonical_id, expected_rxcui, rxnorm_name
):
    assert iqm[canonical_id]["rxcui"] == expected_rxcui, (
        f"{canonical_id}.rxcui must be {expected_rxcui} ({rxnorm_name}), "
        "verified via live RxNav during the 2026-06-06 replay."
    )


_BATCH_6_RETAINED_BROAD_RXCUIS = [
    ("choline", "2449", "choline"),
    ("glucosamine", "4845", "glucosamine"),
    ("l_carnitine", "42955", "levocarnitine"),
    ("l_lysine", "6536", "lysine"),
    ("selenium", "9641", "selenium"),
    ("vitamin_b6_pyridoxine", "42954", "vitamin B6"),
]


@pytest.mark.parametrize("canonical_id,expected_rxcui,rxnorm_name", _BATCH_6_RETAINED_BROAD_RXCUIS)
def test_batch_6_rejects_stale_null_recommendations_for_current_broad_rxcuis(
    iqm, canonical_id, expected_rxcui, rxnorm_name
):
    assert iqm[canonical_id]["rxcui"] == expected_rxcui, (
        f"{canonical_id}.rxcui must remain {expected_rxcui} ({rxnorm_name}); "
        "Claude's stale branch recommended null, but live RxNav on current main "
        "confirmed a valid broad ingredient concept."
    )
