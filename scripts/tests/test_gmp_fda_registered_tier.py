"""H1 — an FDA-registered facility is not full GMP certification.

The v3 B4b GMP tier credited the full "certified" 4.0 whenever ``gmp.claimed``
was truthy, and the enricher folds fda_registered into ``gmp.claimed``
(``claimed = gmp_found or nsf_gmp or fda_registered``). So "manufactured in an
FDA-registered facility" — a common label phrase with no product GMP
certification — scored 4.0, and the fda_registered → 2.0 tier was unreachable.

The v3 scorer now uses the SAME precise signal as the v4 scorer
(generic_trust.py): full GMP requires ``nsf_gmp``,
``gmp_certified_or_compliant``, or a claim that is NOT merely fda_registered.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from score_supplements import SupplementScorer


@pytest.fixture(scope="module")
def scorer() -> SupplementScorer:
    return SupplementScorer()


def _b4b(scorer, gmp):
    product = {"certification_data": {"gmp": gmp}, "supp_type": "general_supplement"}
    return scorer._compute_certifications_bonus(product, "general_supplement")["B4b"]


class TestGmpTierRespectsFdaRegistered:
    def test_fda_registered_only_scores_2_not_4(self, scorer) -> None:
        assert _b4b(scorer, {
            "claimed": True, "fda_registered": True,
            "nsf_gmp": False, "gmp_certified_or_compliant": False,
        }) == 2.0

    def test_cgmp_certified_scores_4(self, scorer) -> None:
        assert _b4b(scorer, {
            "claimed": True, "fda_registered": False,
            "nsf_gmp": False, "gmp_certified_or_compliant": True,
        }) == 4.0

    def test_nsf_gmp_scores_4(self, scorer) -> None:
        assert _b4b(scorer, {
            "claimed": True, "fda_registered": False,
            "nsf_gmp": True, "gmp_certified_or_compliant": False,
        }) == 4.0

    def test_cgmp_and_fda_registered_keeps_full_credit(self, scorer) -> None:
        # A genuinely cGMP-certified product that also notes FDA registration
        # must keep full credit (gmp_certified_or_compliant wins).
        assert _b4b(scorer, {
            "claimed": True, "fda_registered": True,
            "nsf_gmp": False, "gmp_certified_or_compliant": True,
        }) == 4.0

    def test_no_gmp_scores_0(self, scorer) -> None:
        assert _b4b(scorer, {
            "claimed": False, "fda_registered": False,
            "nsf_gmp": False, "gmp_certified_or_compliant": False,
        }) == 0.0
