"""Q40: botanical plant part has one owner, the cleaner, and only label text discloses it.

21 CFR 101.36(d)(1) puts the plant part on the Supplement Facts row. The cleaner records it from
DSLD's PlantPart note, else from the label row's name or its label forms; the enricher carries
it onto the quality row and the botanical Formulation credit reads only that. Before, the scorer
re-derived it with a private word list over text that included IQM form and standard names, so a
"Licorice" row earned the credit from IQM's "licorice root extract" while DSLD's own PlantPart
note (60306, root) earned nothing.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def scored():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.CRITICAL)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    out = {}
    for dsld_id in ("60306", "330145", "251625"):
        raw = json.loads((FIXTURES / f"plant_part_{dsld_id}_raw.json").read_text())
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        out[dsld_id] = build_scored_artifact(enriched)
    logging.disable(logging.NOTSET)
    return out


def _botanical_components(artifact):
    formulation = artifact["_v4_module_breakdown"]["dimensions"]["formulation"]
    return (formulation.get("metadata") or {}).get("botanical_formulation") or {}


@pytest.mark.parametrize("dsld_id", ["60306", "330145"])
def test_label_disclosed_plant_part_earns_the_credit(scored, dsld_id):
    # 60306: DSLD note "PlantPart: root". 330145: label row "Okra Pods Extract, Fresh".
    assert _botanical_components(scored[dsld_id]).get("plant_part_disclosed") == 2.0


def test_database_form_name_is_not_label_disclosure(scored):
    # 251625: the Supplement Facts row is "Licorice"; only IQM's form name says root.
    assert "plant_part_disclosed" not in _botanical_components(scored["251625"])
