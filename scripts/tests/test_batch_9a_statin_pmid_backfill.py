"""Batch 9.A regression locks — PubMed citation backfill for 3 statin entries
in scripts/data/curated_interactions/curated_interactions_v1.json.

Per the clinician guardrails (2026-05-27):
  - Scope is evidence hardening only: add verified PMIDs to entries that
    already exist and already have correct mechanism/management/source_urls.
  - The PMID list for each entry was content-verified via live PubMed
    efetch — the article title/abstract must directly address the
    drug-supplement interaction mechanism, not a "related topic".
  - DSI_STATINS_COQ10 is explicitly EXCLUDED — it is a Minor-severity
    background insight, not a user-facing alert, and belongs in the
    separate background-policy cleanup batch.
  - DSI_STATINS_RYR.agent2_canonical_id is realigned from the orphan
    "red_yeast_rice" to the existing safety canonical
    "BANNED_RED_YEAST_RICE" (from banned_recalled_ingredients.json).
    The CUI C0763533 already resolves to that canonical via
    build_iqm_cui_index's banned_recalled fallback; this just makes the
    stored agent2_canonical_id field match the resolved value.

The PMIDs locked here have been individually fetched, with title and
abstract reviewed, before they were added to the entries. A future agent
that wants to swap them out must re-verify with PubMed efetch — do not
"clean up" these IDs based on superficial searches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CURATED_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curated_interactions"
    / "curated_interactions_v1.json"
)


@pytest.fixture(scope="module")
def curated() -> dict:
    return json.loads(CURATED_PATH.read_text())


def _find(curated: dict, entry_id: str) -> dict:
    for e in curated["interactions"]:
        if e["id"] == entry_id:
            return e
    raise AssertionError(f"curated_interactions_v1.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# DSI_STATINS_RYR — Statins ↔ Red Yeast Rice (monacolin K = lovastatin)
# --------------------------------------------------------------------------- #

# PMID 36779111: "Rhabdomyolysis Related to Red Yeast Rice Ingestion." Direct
#   case report of RYR-induced rhabdo, the exact mechanism the entry warns about.
# PMID 40909457: "Red yeast rice-induced severe rhabdomyolysis complicated by
#   acute kidney injury and respiratory failure: a case report." Documents the
#   severity tail (AKI + respiratory failure) that justifies the Major rating.
# PMID 33538260: "Red Yeast Rice for Hypercholesterolemia: JACC Focus Seminar."
#   Authoritative cardiology review of monacolin K mechanism and the
#   monacolin-K = lovastatin equivalence the mechanism text relies on.
DSI_STATINS_RYR_PMIDS = ["36779111", "40909457", "33538260"]


def test_dsi_statins_ryr_has_verified_pmids(curated):
    e = _find(curated, "DSI_STATINS_RYR")
    pmids = e.get("source_pmids") or []
    for required in DSI_STATINS_RYR_PMIDS:
        assert required in pmids, (
            f"DSI_STATINS_RYR.source_pmids must include {required} "
            f"(Batch 9.A content-verified anchor)."
        )


def test_dsi_statins_ryr_canonical_aligned_with_banned_recalled(curated):
    """The agent2_canonical_id must match the existing safety canonical
    `BANNED_RED_YEAST_RICE` from banned_recalled_ingredients.json. The
    legacy value "red_yeast_rice" was an orphan and only resolved
    silently via the CUI→canonical_id index path."""
    e = _find(curated, "DSI_STATINS_RYR")
    assert e.get("agent2_canonical_id") == "BANNED_RED_YEAST_RICE", (
        "DSI_STATINS_RYR.agent2_canonical_id must be 'BANNED_RED_YEAST_RICE' "
        "(aligned with the safety entry in banned_recalled_ingredients.json), "
        "not the orphan 'red_yeast_rice'."
    )


# --------------------------------------------------------------------------- #
# DSI_STATINS_SJW — Statins ↔ St. John's Wort (CYP3A4 induction)
# --------------------------------------------------------------------------- #

# PMID 17701167: "Interaction between a commercially available St. John's wort
#   product (Movina) and atorvastatin in patients with hypercholesterolemia."
#   Direct human PK study on SJW + atorvastatin — anchors the CYP3A4-statin
#   mechanism with patient-level evidence.
# PMID 31742659: "Clinical relevance of St. John's wort drug interactions
#   revisited." Updated review confirming the clinically relevant induction
#   profile that drove the original SJW labeling guidance.
# PMID 15260917: "Pharmacokinetic interactions of drugs with St John's wort."
#   PK mechanism review — documents the CYP3A4 + P-gp induction that the
#   entry's mechanism text describes.
DSI_STATINS_SJW_PMIDS = ["17701167", "31742659", "15260917"]


def test_dsi_statins_sjw_has_verified_pmids(curated):
    e = _find(curated, "DSI_STATINS_SJW")
    pmids = e.get("source_pmids") or []
    for required in DSI_STATINS_SJW_PMIDS:
        assert required in pmids, (
            f"DSI_STATINS_SJW.source_pmids must include {required} "
            f"(Batch 9.A content-verified anchor)."
        )


# --------------------------------------------------------------------------- #
# DSI_STATINS_NIACIN — Statins ↔ High-dose Niacin (additive myopathy)
# --------------------------------------------------------------------------- #

# PMID 22085343: AIM-HIGH (Boden 2011 NEJM). "Niacin in patients with low HDL
#   cholesterol levels receiving intensive statin therapy." Landmark RCT
#   showing no incremental benefit of adding niacin to statin therapy and
#   the adverse-event signal that supports caution.
# PMID 25014686: HPS2-THRIVE primary outcomes (Landray 2014 NEJM). "Effects of
#   extended-release niacin with laropiprant in high-risk patients." Largest
#   trial of niacin + statin with the myopathy signal documented.
# PMID 23444397: HPS2-THRIVE design + pre-specified muscle and liver outcomes.
#   Documents the elevated myopathy/hepatotoxicity rates that anchor the
#   "monitor for muscle pain, weakness, or brown urine" management text.
DSI_STATINS_NIACIN_PMIDS = ["22085343", "25014686", "23444397"]


def test_dsi_statins_niacin_has_verified_pmids(curated):
    e = _find(curated, "DSI_STATINS_NIACIN")
    pmids = e.get("source_pmids") or []
    for required in DSI_STATINS_NIACIN_PMIDS:
        assert required in pmids, (
            f"DSI_STATINS_NIACIN.source_pmids must include {required} "
            f"(Batch 9.A content-verified anchor)."
        )


# --------------------------------------------------------------------------- #
# Negative lock: DSI_STATINS_COQ10 is NOT in this batch
# --------------------------------------------------------------------------- #


def test_dsi_statins_coq10_is_not_part_of_batch_9a(curated):
    """Per clinician guardrail (2026-05-27): DSI_STATINS_COQ10 is a Minor-
    severity background insight, not a user-facing alert. It does not
    receive PMID backfill in Batch 9.A. That entry belongs in the separate
    Minor-entry / two-lane policy cleanup, when those are reclassified."""
    e = _find(curated, "DSI_STATINS_COQ10")
    # If this still has empty source_pmids, the batch boundary was respected.
    # If a future batch adds PMIDs here as part of an alert promotion, this
    # assertion will fail loudly — the maintainer must update the test
    # consciously and document the severity / two-lane decision.
    assert (e.get("source_pmids") or []) == [], (
        "DSI_STATINS_COQ10.source_pmids unexpectedly non-empty. "
        "Batch 9.A explicitly excluded this entry. If you are promoting "
        "the CoQ10 interaction to a user-facing alert, do it through the "
        "two-lane policy cleanup batch and update this test consciously."
    )
    assert e.get("severity") == "Minor", (
        "DSI_STATINS_COQ10.severity unexpectedly changed. Batch 9.A is "
        "evidence-hardening only and must not alter severity."
    )
