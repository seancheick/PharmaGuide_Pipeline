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
