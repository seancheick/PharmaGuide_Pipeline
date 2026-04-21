"""
Sprint D5.2 regression — enrichment_config must enable rda_ul_data collection.

**The medical-safety bug this guards**: the scorer's B7 dose-safety penalty
(OVER-150%-UL check, including the D4.3 canonical-sum aggregation for the
teratogenicity case) reads from ``enriched.rda_ul_data.safety_flags``. The
flags are generated inside ``_collect_rda_ul_data`` in the enricher.

``_collect_rda_ul_data`` is gated on
``processing_config.collect_rda_ul_data``. When false, the enricher emits
an empty payload with ``collection_reason="disabled_by_config"`` and the
scorer's B7 penalty silently returns 0 for every product.

If this flag drifts back to false, the D4.3 teratogenicity protection
goes completely dark in production. This test fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_collect_rda_ul_data_enabled() -> None:
    """``collect_rda_ul_data`` must be true so B7 safety flags populate."""
    cfg = json.loads(Path("scripts/config/enrichment_config.json").read_text())
    processing = cfg.get("processing_config", {})
    assert processing.get("collect_rda_ul_data") is True, (
        "D5.2 medical-safety regression: "
        "processing_config.collect_rda_ul_data must be true. When false, "
        "enriched.rda_ul_data is empty, the scorer's B7 dose-safety "
        "penalty silently returns 0, and the D4.3 teratogenicity fix "
        "(OVER-150%-UL aggregated across multiple forms) never fires "
        "in production."
    )


def test_scorer_b7_reads_rda_ul_data_safety_flags() -> None:
    """The scorer's source must still consume rda_ul_data.safety_flags so
    enabling the config actually flows to a B7 penalty."""
    source = Path("scripts/score_supplements.py").read_text()
    assert 'rda_ul.get("safety_flags")' in source, (
        "D5.2 regression: scorer's B7 dose-safety must read from "
        'rda_ul_data.safety_flags (the key the enricher populates).'
    )


def test_enricher_gate_preserved() -> None:
    """The enricher still honours the config gate (not hardcoded true)
    so the flag stays meaningful and reviewable."""
    source = Path("scripts/enrich_supplements_v3.py").read_text()
    assert 'self.config.get("processing_config", {}).get("collect_rda_ul_data"' in source, (
        "D5.2 regression: the enricher's collect_rda_ul_data gate must "
        "still be config-driven so operators retain the override."
    )
