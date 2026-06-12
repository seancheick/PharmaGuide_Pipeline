"""Regression guard: USP pharmacopeia references must NOT parse as the
USP Verified(TM) certification program.

Background (2026-06-09 audit): GNC prints "Conforms to USP <2091> for
weight." (the USP General Chapter on weight variation — a manufacturing
QC statement) on most SKUs. The legacy CERTIFICATION_PATTERNS entry

    "USP-Verified": r"USP\\s*(Verified|Grade|<\\d+>|\\s+standards)"

coined the literal string "USP-Verified" into labelText.parsed.certifications
for 858 GNC products. cert_claim_rules.json (CERT_USP_VERIFIED) then matched
its positive pattern against that *coined token* — its negative patterns
("USP <\\d+>", "USP grade", "USP standards") never saw the original context,
so the boilerplate laundered into a score-eligible label-asserted cert claim
(+2 verification pts each) the brand never made.

The fix tightens the cleaner pattern to actual program claims only. The
rules-db side was already correct; the cleaner must stop coining.

Truth check against raw labels (2026-06-09 cleaned artifacts):
    FALSE coins: GNC 858, Sports Research 4, Doctor's Best 1
    TRUE claims: Nature Made 416 (the flagship USP Verified brand),
                 Doctor's Best 27, Nature's Bounty 4, vitafusion 4, Ritual 1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.constants import CERTIFICATION_PATTERNS  # noqa: E402


USP_PATTERN = CERTIFICATION_PATTERNS["USP-Verified"]

# Pharmacopeia / grade / monograph language — NOT the certification program.
BOILERPLATE = [
    "Conforms to USP <2091> for weight.",
    "ACTUAL SIZE CODE 893122 AMG Conforms to USP <2091> for weight.",
    "Meets USP standards for quality.",
    "USP grade ascorbic acid.",
    "Tested per USP <711> dissolution.",
]

# Genuine program claims as printed on USP Verified participants' labels.
TRUE_CLAIMS = [
    "USP Verified",
    "USP-Verified",
    "Look for the USP Verified Mark.",
    "USP Dietary Supplement Verification Program",
    "USP Verification Program participant",
]


@pytest.mark.parametrize("text", BOILERPLATE)
def test_usp_pattern_rejects_pharmacopeia_boilerplate(text: str) -> None:
    assert not re.search(USP_PATTERN, text, re.IGNORECASE), (
        f"USP-Verified pattern must not match pharmacopeia/grade language: "
        f"{text!r} — this coined false cert claims on 858 GNC products."
    )


@pytest.mark.parametrize("text", TRUE_CLAIMS)
def test_usp_pattern_accepts_true_program_claims(text: str) -> None:
    assert re.search(USP_PATTERN, text, re.IGNORECASE), (
        f"USP-Verified pattern must still match a genuine program claim: {text!r}"
    )


# ---------------------------------------------------------------------------
# Integration: the statements→parsed.certifications path in the normalizer
# (the exact path that coined GNC's false certs).
# ---------------------------------------------------------------------------


def _minimal_raw(notes: str) -> dict:
    return {
        "id": 999001,
        "fullName": "Test Fish Oil",
        "brandName": "TestBrand",
        "ingredientRows": [],
        "otheringredients": {"ingredients": []},
        "statements": [{"type": "Other", "notes": notes}],
        "claims": [],
        "servingSizes": [],
        "netContents": [],
    }


@pytest.fixture(scope="module")
def normalizer():
    from scripts.enhanced_normalizer import EnhancedDSLDNormalizer
    return EnhancedDSLDNormalizer()


def _parsed_certs(out: dict) -> list:
    return ((out.get("labelText") or {}).get("parsed") or {}).get(
        "certifications"
    ) or []


def test_normalizer_does_not_coin_usp_verified_from_weight_conformance(
    normalizer,
) -> None:
    out = normalizer.normalize_product(
        _minimal_raw("Conforms to USP <2091> for weight. Controls fishy burps.")
    )
    assert "USP-Verified" not in _parsed_certs(out), (
        "Weight-variation conformance (USP <2091>) must not become a "
        "USP-Verified certification in labelText.parsed.certifications"
    )


def test_normalizer_still_parses_genuine_usp_verified_claim(normalizer) -> None:
    out = normalizer.normalize_product(
        _minimal_raw("This product is USP Verified. Look for the USP Verified Mark.")
    )
    assert "USP-Verified" in _parsed_certs(out), (
        "A genuine USP Verified label claim must still parse "
        "(Nature Made-class labels)"
    )
