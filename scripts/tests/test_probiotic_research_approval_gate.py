"""An unreviewed probiotic evidence claim must never present as affirmative.

``_probiotic_research_presentation`` decides what the product card is allowed to
say about a strain's research. It assigned ``formula_only`` *before* it consulted
``dr_pham_signoff``, so a formula-level match rendered "Research applies to the
formula, not necessarily each strain" with no clinician review behind it.

The tell was arithmetic: on the 2026-08-22 candidate, ``exact_strain`` (242) plus
``species_level`` (787) summed to exactly the 1,029 clinician-verified rows, while
``formula_only`` (148) sat entirely outside that set.

Review status gates every affirmative status. Scope only chooses which affirmative
status a reviewed strain earns.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from enrich_supplements_v3 import _probiotic_research_presentation  # noqa: E402


AFFIRMATIVE = frozenset({"exact_strain", "species_level", "formula_only"})


def _entry(*, signoff, evidence_type="rct", strain_explicit="YES", human="YES"):
    validation = {}
    if strain_explicit is not None:
        validation["q1_strain_explicit"] = strain_explicit
    if human is not None:
        validation["q3_human_clinical"] = human
    thresholds = {
        "indication_primary": "test indication",
        "evidence": {
            "type": evidence_type,
            "clinical_validation": validation,
            "pmid": "12345678",
        },
    }
    if signoff is not None:
        thresholds["dr_pham_signoff"] = signoff
    return {"cfu_thresholds": thresholds}


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "evidence_type,strain_explicit,human",
    [
        ("product_formula_rct", "FORMULA_LEVEL", "YES"),  # the escaping case
        ("product_formula_rct", "FORMULA_LEVEL", "NO"),
        ("strain_specific_rct", "YES", "YES"),
        ("strain_specific_rct", "YES", "NO"),
        ("observational", "NO", "NO"),
        ("rct", None, None),
    ],
)
@pytest.mark.parametrize("signoff", [False, None])
def test_unreviewed_strain_never_gets_an_affirmative_status(
    signoff, evidence_type, strain_explicit, human
) -> None:
    out = _probiotic_research_presentation(
        _entry(
            signoff=signoff,
            evidence_type=evidence_type,
            strain_explicit=strain_explicit,
            human=human,
        )
    )
    assert out["review_status"] != "clinician_verified"
    assert out["research_match_status"] not in AFFIRMATIVE, (
        f"scope={evidence_type}/{strain_explicit} signoff={signoff!r} produced "
        f"{out['research_match_status']!r} without clinician review"
    )
    assert out["research_match_status"] == "pending_review"


@pytest.mark.parametrize(
    "evidence_type,strain_explicit,human,expected",
    [
        ("product_formula_rct", "FORMULA_LEVEL", "YES", "formula_only"),
        ("strain_specific_rct", "YES", "YES", "exact_strain"),
        ("strain_specific_rct", "YES", "NO", "species_level"),
        ("observational", "NO", "NO", "species_level"),
    ],
)
def test_reviewed_strain_earns_the_status_its_scope_supports(
    evidence_type, strain_explicit, human, expected
) -> None:
    out = _probiotic_research_presentation(
        _entry(
            signoff=True,
            evidence_type=evidence_type,
            strain_explicit=strain_explicit,
            human=human,
        )
    )
    assert out["review_status"] == "clinician_verified"
    assert out["research_match_status"] == expected


def test_blocked_strain_is_rejected_regardless_of_review() -> None:
    for signoff in (True, False, None):
        out = _probiotic_research_presentation(
            _entry(signoff=signoff, evidence_type="product_formula_rct",
                   strain_explicit="FORMULA_LEVEL"),
            is_blocked=True,
        )
        assert out["research_match_status"] == "rejected"


def test_evidence_scope_still_reports_the_underlying_scope() -> None:
    """The gate changes what is claimed, not what was measured.

    ``evidence_scope`` remains the honest description of the study so the
    backlog stays visible; only ``research_match_status`` is gated.
    """
    out = _probiotic_research_presentation(
        _entry(signoff=False, evidence_type="product_formula_rct",
               strain_explicit="FORMULA_LEVEL")
    )
    assert out["evidence_scope"] == "formula_specific"
    assert out["research_match_status"] == "pending_review"


# --------------------------------------------------------------------------- #
# Curated source: every strain the vocabulary defines
# --------------------------------------------------------------------------- #


def test_no_curated_strain_claims_more_than_its_review_allows() -> None:
    import json

    from constants import DATA_DIR

    path = Path(DATA_DIR) / "clinically_relevant_strains.json"
    payload = json.loads(path.read_text())
    entries = payload["clinically_relevant_strains"]
    if isinstance(entries, dict):
        entries = list(entries.values())

    offenders = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        out = _probiotic_research_presentation(entry)
        verified = out["review_status"] == "clinician_verified"
        if out["research_match_status"] in AFFIRMATIVE and not verified:
            offenders.append(
                (entry.get("strain_id"), out["research_match_status"])
            )
    assert not offenders, (
        f"{len(offenders)} curated strain(s) claim research without clinician "
        f"sign-off: {offenders[:10]}"
    )
