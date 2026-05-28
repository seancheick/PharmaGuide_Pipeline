"""Per-entry identifier integrity tests for other_ingredients.json.

Pattern mirrors the IQM / banned_recalled / harmful_additives integrity
tests: one assertion per Wave 9.E correction, content-verified against
UMLS / RxNav / FDA GSRS / PubChem before the entry is written.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OI_PATH = REPO_ROOT / "scripts" / "data" / "other_ingredients.json"


@pytest.fixture(scope="module")
def other_ingredients() -> list[dict]:
    payload = json.loads(OI_PATH.read_text())
    return payload["other_ingredients"]


def _find(entries: list[dict], entry_id: str) -> dict:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    raise AssertionError(f"other_ingredients.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# Wave 9.E.2 — Disease-CUI hallucinations → substance CUI (3 entries)
# --------------------------------------------------------------------------- #


def test_pii_lactose_monohydrate_cui_is_substance(other_ingredients):
    """C0022951 resolved to 'Lactose Intolerance' (Disease or Syndrome).
    C1658042 'lactose monohydrate' (Organic Chemical / Pharmacologic
    Substance) is the exact substance match. Verified via live UMLS
    exact-search 2026-05-28."""
    e = _find(other_ingredients, "PII_LACTOSE_MONOHYDRATE")
    assert e["cui"] == "C1658042", (
        "PII_LACTOSE_MONOHYDRATE.cui must be C1658042 (lactose monohydrate "
        "substance), not C0022951 (Lactose Intolerance, a disease)."
    )


def test_pii_mica_colorant_cui_is_substance(other_ingredients):
    """C0700319 resolved to 'Mentally ill chemical abuse' (Mental or
    Behavioral Dysfunction). C0066503 'mica' (Pharmacologic Substance /
    Inorganic Chemical) is the correct mineral-colorant substance.
    Verified via live UMLS exact-search 2026-05-28."""
    e = _find(other_ingredients, "PII_MICA_COLORANT")
    assert e["cui"] == "C0066503", (
        "PII_MICA_COLORANT.cui must be C0066503 (mica, the mineral "
        "substance), not C0700319 ('Mentally ill chemical abuse')."
    )


def test_pii_pituitary_tissue_cui_is_organ(other_ingredients):
    """C0032002 resolved to 'Pituitary Diseases' (Disease or Syndrome).
    C0032005 'Pituitary Gland' (Body Part, Organ, or Organ Component) is
    the correct concept for a glandular-tissue source ingredient.
    Verified via live UMLS exact-search 2026-05-28."""
    e = _find(other_ingredients, "PII_PITUITARY_TISSUE")
    assert e["cui"] == "C0032005", (
        "PII_PITUITARY_TISSUE.cui must be C0032005 (Pituitary Gland organ/"
        "tissue), not C0032002 (Pituitary Diseases)."
    )


# --------------------------------------------------------------------------- #
# Wave 9.E.2 — Wrong-concept class/proprietary CUIs → null (4 entries)
# --------------------------------------------------------------------------- #


def test_nha_lactotripeptides_cui_nulled(other_ingredients):
    """C0063506 resolved to 'indolepropanol phosphate' — unrelated. The
    entry is a two-peptide class (IPP C1505879 + VPP C1505878); UMLS has
    no single 'lactotripeptides' concept. Nulled with cui_note pointing at
    the two component CUIs. Verified via live UMLS 2026-05-28."""
    e = _find(other_ingredients, "NHA_LACTOTRIPEPTIDES")
    assert e["cui"] is None, "NHA_LACTOTRIPEPTIDES.cui must be null (no single UMLS concept)."
    assert e.get("cui_note")


def test_nha_fruit_veg_powders_cui_nulled(other_ingredients):
    """C1145672 resolved to 'Bixa orellana (plant)' (annatto) — unrelated.
    The entry is a multi-source powder class (berry/carrot/cherry); UMLS
    has no single concept. Nulled with cui_note."""
    e = _find(other_ingredients, "NHA_FRUIT_VEG_POWDERS")
    assert e["cui"] is None, "NHA_FRUIT_VEG_POWDERS.cui must be null (class entry)."
    assert e.get("cui_note")


def test_nha_vegetable_fruit_juice_colors_cui_nulled(other_ingredients):
    """C4042943 resolved to 'Fruit and Vegetable Juices' (multi-compound
    combo). The entry is a natural-colorant class; no single UMLS concept.
    Nulled with cui_note."""
    e = _find(other_ingredients, "NHA_VEGETABLE_FRUIT_JUICE_COLORS")
    assert e["cui"] is None, "NHA_VEGETABLE_FRUIT_JUICE_COLORS.cui must be null."
    assert e.get("cui_note")


def test_pii_brand_complex_descriptor_cui_nulled(other_ingredients):
    """C1269100 resolved to 'Eosinophilic major basic protein' — unrelated.
    The entry is a proprietary brand-blend descriptor (ap-bio, Brain
    Shield, graminex g60, etc.); no single UMLS concept exists for a
    brand-complex placeholder. Nulled with cui_note."""
    e = _find(other_ingredients, "PII_BRAND_COMPLEX_DESCRIPTOR")
    assert e["cui"] is None, "PII_BRAND_COMPLEX_DESCRIPTOR.cui must be null (proprietary)."
    assert e.get("cui_note")


# --------------------------------------------------------------------------- #
# Wave 9.E.2 — Deprecated RxCUI → null (1 entry)
# --------------------------------------------------------------------------- #


def test_pii_polyvinyl_alcohol_rxcui_nulled(other_ingredients):
    """rxcui 8570 returns no record from RxNav (404 on 2026-05-28).
    Cleared to null with rxcui_note. cui and unii remain valid."""
    e = _find(other_ingredients, "PII_POLYVINYL_ALCOHOL")
    assert e.get("rxcui") is None, "PII_POLYVINYL_ALCOHOL.rxcui must be null (RxNav 404)."
    assert e.get("rxcui_note")


# --------------------------------------------------------------------------- #
# Wave 9.E.3 — Policy locks: flagged-but-correct CUIs (6 entries)
# --------------------------------------------------------------------------- #
#
# These 6 fired the strict-mode no_token_overlap / combo guard but the
# stored CUI is actually correct on review: singular/plural variance,
# naming variance, the principal-protein concept, or a correct
# species/genus mapping. Locked so a future sweep agent doesn't "fix"
# a correct mapping. Same pattern as IQM Wave 6.Y Batches 4 & 5 and
# banned_recalled Wave 9.C.4.

_WAVE_9E3_POLICY_LOCKS = [
    ("NHA_FLAVANOLS", "C2348678", "Flavanol",
     "Singular/plural variance: IQM 'Flavanols' ↔ UMLS 'Flavanol'. Same concept."),
    ("NHA_GLYCOSAPONINS", "C0036189", "Saponins",
     "Glycosaponins are the glycosidic saponins; C0036189 'Saponins' is the "
     "accepted parent-class concept for this class entry."),
    ("NHA_POLYGLYCERYL_ESTER", "C0982350", "POLYGLYCEROL ESTERS OF FATTY ACIDS",
     "Naming variance: 'Polyglyceryl Ester' ↔ 'Polyglycerol esters of fatty "
     "acids'. Same emulsifier substance."),
    ("OI_CORN_PROTEIN", "C0043458", "zein",
     "Zein IS the principal corn storage protein. Correct substance mapping; "
     "the common name 'corn protein' has no separate UMLS concept."),
    ("PII_CANOLA_SOURCE_DESCRIPTOR", "C5703431", "Brassica napus var. napus",
     "Canola IS Brassica napus (var. napus). Correct botanical species/variety "
     "mapping for the source descriptor."),
    ("PII_SUNFLOWER_SOURCE_DESCRIPTOR", "C0018874", "Helianthus",
     "Sunflower IS the Helianthus genus. Genus-level mapping is acceptable for "
     "a source descriptor (species C0947381 Helianthus annuus also valid)."),
]


@pytest.mark.parametrize("canonical_id,locked_cui,umls_name,rationale", _WAVE_9E3_POLICY_LOCKS)
def test_wave_9e3_flagged_but_correct_cui_locked(
    other_ingredients, canonical_id, locked_cui, umls_name, rationale
):
    """Each of these 6 CUIs fired a strict-mode guard but is correct on
    review. Locked with the UMLS target name + rationale so a future agent
    escalates rather than auto-rewriting a correct mapping."""
    e = _find(other_ingredients, canonical_id)
    assert e.get("cui") == locked_cui, (
        f"{canonical_id}.cui must remain {locked_cui} (UMLS '{umls_name}'; "
        f"policy-accepted: {rationale})."
    )
