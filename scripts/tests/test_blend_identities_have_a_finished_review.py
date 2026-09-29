"""Every evidence owner of these 8 labels has a finished literature review.

Each product scored Evidence 0 with the pillar saying `not_yet_reviewed`:
its purpose-owning identity was a proprietary blend (or branded blend) that
nobody had searched. Sean asked on 2026-09-28 for all of them to be reviewed
(scripts/audits/rr_correctness_20260928/CALIBRATION_PACKET.md item 3). A blend
with no published human trial gets a reproducible search record that
concludes so; a branded blend with trials (Tesnor, Sytrinol) gets its reviewed
clinical entry. The answer then depends on the evidence, never on a missing
review.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PRODUCTS = ["1179", "14168", "315089", "243271", "282638", "299755", "54775", "275464"]


@pytest.fixture(scope="module")
def enriched():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    out = {}
    for pid in PRODUCTS:
        raw = json.loads((FIXTURES / f"evidence_review_{pid}_raw.json").read_text())
        out[pid], _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return out


@pytest.mark.parametrize("pid", PRODUCTS)
def test_the_owner_review_is_finished(enriched, pid):
    from evidence_resolver import resolve_product_evidence

    resolution = resolve_product_evidence(enriched[pid], owner_scoped=True)
    assert resolution.is_assessment_complete, [
        (r.canonical_id, r.disposition) for r in resolution.resolutions
    ]


@pytest.mark.parametrize("pid", PRODUCTS)
def test_the_evidence_pillar_no_longer_says_not_yet_reviewed(enriched, pid):
    from scoring_v4.scored_artifact import build_scored_artifact

    evidence = build_scored_artifact(enriched[pid])["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] != "not_yet_reviewed"


def test_tesnor_and_sytrinol_resolve_to_their_reviewed_trials(enriched):
    from evidence_resolver import resolve_product_evidence

    for pid, canonical in (("315089", "tesnor_pomegranate_cocoa_blend"), ("54775", "sytrinol")):
        resolution = resolve_product_evidence(enriched[pid], owner_scoped=True)
        owner = next(r for r in resolution.resolutions if r.canonical_id == canonical)
        assert "backed_clinical_studies" in owner.matched_owners
