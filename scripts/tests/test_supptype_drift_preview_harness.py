"""Phase -1 contract tests for the TEMPORARY supp-type drift-preview harness.

TEMPORARY — delete this file together with
``scripts/audits/supptype_drift_preview.py`` at consolidation cutover
(Phase 5).

WHY THIS EXISTS
    The harness output is used as *evidence* for classifier changes. An
    untrustworthy harness silently launders a wrong classifier into a
    release, which is worse than having no harness at all: it converts
    "unknown" into "falsely confirmed". These tests pin the §8 harness
    contract from SUPP_TYPE_CONSOLIDATION_PLAN.md.

The five required RED-first cases from §8:
    1. A recomputed taxonomy change alters the v4 preview even when the
       enriched blob contains stale taxonomy.
    2. A change only to ``is_single_scorable_active`` is included and
       rescored even when ``primary_type`` is unchanged.
    3. A multi-active amino-acid product is not reported as single from its
       type name.
    4. Duplicate IDs, unreadable JSON, missing IDs, added IDs, and scoring
       errors each produce a non-zero exit.
    5. Frozen fixtures match the production final-build projection for every
       captured field.  (Case 5 needs the real corpus + the shipped DB and
       lives in ``test_supptype_preview_exact_path_canary.py``, which is
       registered in the slow profile.)
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
HARNESS_PATH = SCRIPTS_DIR / "audits" / "supptype_drift_preview.py"

# The harness lives in scripts/audits/ (not a package, not on sys.path), so it
# is loaded by path — same pattern as test_migrate_to_profile_gate.py.
_spec = importlib.util.spec_from_file_location("supptype_drift_preview", HARNESS_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["supptype_drift_preview"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

harness = _mod


# ---------------------------------------------------------------------------
# Fixtures — synthetic products only. These tests must not need the corpus.
# ---------------------------------------------------------------------------


def _row(name, canonical_id, category, qty=100.0, unit="mg", **extra):
    row = {
        "name": name,
        "canonical_id": canonical_id,
        "standard_name": name,
        "category": category,
        "quantity": qty,
        "unit": unit,
        "mapped": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "score_eligible_by_cleaner": True,
    }
    row.update(extra)
    return row


def _product(dsld_id, name, rows):
    """A minimally-valid enriched product the taxonomy + scorer will accept."""
    return {
        "dsld_id": dsld_id,
        "product_name": name,
        "fullName": name,
        "brand_name": "TestBrand",
        "enrichment_version": "3.1.0",
        "ingredient_quality_data": {
            "ingredients": copy.deepcopy(rows),
            "ingredients_scorable": copy.deepcopy(rows),
        },
        "probiotic_data": {"is_probiotic_product": False, "total_cfu": 0},
    }


@pytest.fixture(scope="module")
def enricher():
    return harness.make_enricher()


@pytest.fixture(scope="module")
def scorer():
    return harness.make_scorer()


@pytest.fixture
def amino_multi():
    """Amino-acid product with TWO distinct scorable actives."""
    return _product(
        900001,
        "Test BCAA Blend",
        [
            _row("L-Leucine", "l_leucine", "amino_acid", 2500.0),
            _row("L-Valine", "l_valine", "amino_acid", 1250.0),
        ],
    )


@pytest.fixture
def mineral_single():
    return _product(
        900002,
        "Test Magnesium Glycinate",
        [_row("Magnesium Glycinate", "magnesium", "mineral", 200.0)],
    )


# A product whose v4 ROUTE genuinely hangs on the taxonomy's primary_type.
# Deliberately calibrated: the title carries no probiotic name token, and total
# CFU sits below scoring_v4/router.py's 1B `_PROBIOTIC_HIGH_CFU_BILLIONS`
# bypass. Above that threshold, or with "probiotic" in the title, the router
# reaches the probiotic module on row evidence alone and the taxonomy stops
# being load-bearing — which would make this test vacuous.
_PROBIOTIC_CFU_BELOW_HIGH_BYPASS = 500_000_000


@pytest.fixture
def taxonomy_routed_probiotic():
    product = _product(
        900003,
        "Test Daily Formula",  # no probiotic name signal, by design
        [
            _row(
                "Lactobacillus acidophilus",
                "lactobacillus_acidophilus",
                "probiotic",
                _PROBIOTIC_CFU_BELOW_HIGH_BYPASS,
                unit="CFU",
            )
        ],
    )
    product["probiotic_data"] = {
        "is_probiotic_product": True,
        "total_cfu": _PROBIOTIC_CFU_BELOW_HIGH_BYPASS,
        "total_strain_count": 1,
        "probiotic_blends": [
            {"name": "Lactobacillus acidophilus", "cfu": _PROBIOTIC_CFU_BELOW_HIGH_BYPASS}
        ],
        "cfu_raw_source_path": "activeIngredients[0]",
        "cfu_linked_rows": ["activeIngredients[0]"],
    }
    return product


# ---------------------------------------------------------------------------
# The production projection seam
# ---------------------------------------------------------------------------


def test_projection_seam_is_owned_by_production_not_the_harness():
    """§8: 'Use one production projection seam shared by enrichment and the
    harness; do not maintain a harness-only mirror algorithm.'"""
    from enrich_supplements_v3 import SupplementEnricherV3

    assert hasattr(SupplementEnricherV3, "apply_taxonomy_projection"), (
        "enrichment must expose the taxonomy projection as a production seam "
        "so the harness cannot drift from the pipeline"
    )


def test_enrich_product_uses_the_seam():
    """The seam is only trustworthy if the pipeline itself goes through it."""
    source = (SCRIPTS_DIR / "enrich_supplements_v3.py").read_text()
    assert "self.apply_taxonomy_projection(enriched)" in source, (
        "enrich_product must call the shared seam; otherwise the harness "
        "preview and the pipeline can diverge silently"
    )


# ---------------------------------------------------------------------------
# §8 case 1 — stale embedded taxonomy must not reach the preview
# ---------------------------------------------------------------------------


def test_the_scorer_receives_the_recomputed_taxonomy_not_the_stale_blob(
    enricher, scorer, mineral_single, monkeypatch
):
    """Baseline defect #1, pinned at the seam: classify_row() recomputed the
    taxonomy but score_products() scored the ORIGINAL product, so scoring could
    still read a stale embedded taxonomy.

    Asserted on what the production scorer is actually handed, so the guarantee
    does not depend on which fields v4 happens to route on today.
    """
    stale = copy.deepcopy(mineral_single)
    stale["supplement_taxonomy"] = {
        "primary_type": "omega_3",
        "secondary_type": "epa_dha",
        "percentile_category": "omega_3",
        "classification_confidence": 0.99,
        "classification_reasons": ["STALE FIXTURE VALUE"],
    }
    stale["primary_type"] = "omega_3"

    seen: dict = {}

    import scoring_v4.export_adapter as adapter

    original = adapter.overlay_v4_scored

    def spy(enriched, scored_v3):
        seen["primary_type"] = enriched.get("primary_type")
        seen["taxonomy_primary"] = (enriched.get("supplement_taxonomy") or {}).get(
            "primary_type"
        )
        return original(enriched, scored_v3)

    monkeypatch.setattr(adapter, "overlay_v4_scored", spy)

    harness.preview_scored(harness.project_current_taxonomy(stale, enricher), scorer)

    assert seen["primary_type"] == "single_mineral", (
        f"the production scorer was handed primary_type={seen['primary_type']!r} — "
        "a stale embedded taxonomy reached the score preview"
    )
    assert seen["taxonomy_primary"] == "single_mineral"


def test_a_recomputed_taxonomy_change_alters_the_v4_preview(
    enricher, scorer, taxonomy_routed_probiotic, monkeypatch
):
    """§8 case 1, end to end: the blob carries a stale taxonomy, current code
    classifies it differently, and the v4 preview must follow CURRENT code.

    The old harness scored the original product, so it would have reported the
    stale blob's score and silently hidden the classifier change.
    """
    stale = copy.deepcopy(taxonomy_routed_probiotic)
    stale["supplement_taxonomy"] = {"primary_type": "probiotic", "secondary_type": None}
    stale["primary_type"] = "probiotic"

    # Current code now classifies this product as something else entirely.
    import enrich_supplements_v3 as enrich_mod

    real_classify = enrich_mod.classify_supplement
    monkeypatch.setattr(
        enrich_mod,
        "classify_supplement",
        lambda product: {**real_classify(product),
                         "primary_type": "fiber_digestive",
                         "secondary_type": None},
    )

    preview = harness.score_facts(
        harness.preview_scored(harness.project_current_taxonomy(stale, enricher), scorer)
    )

    monkeypatch.undo()
    stale_preview = harness.score_facts(harness.preview_scored(stale, scorer))

    assert preview["_v4_module"] == "generic", (
        "the preview must follow the recomputed taxonomy"
    )
    assert stale_preview["_v4_module"] == "probiotic", (
        "test is vacuous: the stale taxonomy did not drive routing"
    )
    assert preview["_v4_quality_score_100"] != stale_preview["_v4_quality_score_100"], (
        "a recomputed taxonomy change must move the v4 preview"
    )


# ---------------------------------------------------------------------------
# §8 case 2 — selection must not be primary_type-only
# ---------------------------------------------------------------------------


def test_single_fact_only_change_is_selected_when_primary_type_is_stable():
    """Baseline defect #3: the affected set only included primary_type changes,
    missing score-driving changes like is_single_scorable_active."""
    base = {
        "111": {"primary_type": "amino_acid", "is_single_scorable_active": True},
        "222": {"primary_type": "single_mineral", "is_single_scorable_active": True},
    }
    new = copy.deepcopy(base)
    new["111"]["is_single_scorable_active"] = False  # primary_type UNCHANGED

    affected = harness.select_affected(base, new)

    assert "111" in affected, (
        "a change to a score-driving fact must be selected even when "
        "primary_type is unchanged"
    )
    assert "222" not in affected


def test_selection_covers_every_declared_classification_fact():
    """Each declared fact key must independently trigger selection — no key may
    be captured for the ledger but silently ignored by the comparison."""
    for key in harness.CLASSIFICATION_FACT_KEYS:
        base = {"1": {k: None for k in harness.CLASSIFICATION_FACT_KEYS}}
        new = copy.deepcopy(base)
        new["1"][key] = "CHANGED"
        assert "1" in harness.select_affected(base, new), (
            f"fact '{key}' is captured but does not drive selection"
        )


def test_derived_projection_change_is_selected(enricher, amino_multi):
    """product_scoring_evidence is taxonomy-derived AND score-driving (it gates
    probiotic CFU evidence on primary_type). A change there must be selected
    even if every scalar taxonomy fact is unchanged."""
    projected = harness.project_current_taxonomy(amino_multi, enricher)
    facts = harness.classification_facts(projected)

    mutated = copy.deepcopy(facts)
    mutated["derived_digest"] = "different-digest"

    assert "1" in harness.select_affected({"1": facts}, {"1": mutated})


# ---------------------------------------------------------------------------
# §8 case 3 — no independent single-ness inference
# ---------------------------------------------------------------------------


def test_harness_has_no_independent_single_family_inference():
    """§8: 'The static SINGLE_FAMILY set is also duplicate classification
    logic... Remove it and consume the canonical single-active fact.'"""
    assert not hasattr(harness, "SINGLE_FAMILY"), (
        "SINGLE_FAMILY is duplicate classification logic — the harness must "
        "consume the canonical fact, not re-derive single-ness from a type name"
    )
    source = HARNESS_PATH.read_text()
    assert "SINGLE_FAMILY" not in source


def test_multi_active_amino_acid_is_not_reported_single_from_its_type_name(
    enricher, amino_multi
):
    """An amino_acid product can contain multiple scorable actives; the type
    name must never be used to infer single-ness."""
    projected = harness.project_current_taxonomy(amino_multi, enricher)
    facts = harness.classification_facts(projected)

    assert facts["primary_type"] == "amino_acid"
    # The harness reports the canonical fact verbatim. Until the classifier
    # emits it (Phase 0d) it is truthfully absent — never inferred as True.
    assert facts["is_single_scorable_active"] in (False, None), (
        "harness inferred single-ness for a multi-active amino_acid product"
    )


# ---------------------------------------------------------------------------
# §8 case 4 — fail closed
# ---------------------------------------------------------------------------


def test_unreadable_json_fails_closed(tmp_path):
    """Baseline defect #4: unreadable JSON was skipped with a stderr note."""
    brand = tmp_path / "output_Test_enriched" / "enriched"
    brand.mkdir(parents=True)
    (brand / "batch_1.json").write_text("{not valid json")

    with pytest.raises(harness.HarnessError, match="unreadable"):
        harness.load_corpus(tmp_path)


def test_duplicate_product_ids_fail_closed(tmp_path):
    """Baseline defect #4: duplicate DSLD IDs overwrote each other silently."""
    brand = tmp_path / "output_Test_enriched" / "enriched"
    brand.mkdir(parents=True)
    (brand / "batch_1.json").write_text(json.dumps([_product(1, "A", [])]))
    (brand / "batch_2.json").write_text(json.dumps([_product(1, "A again", [])]))

    with pytest.raises(harness.HarnessError, match="duplicate"):
        harness.load_corpus(tmp_path)


def test_malformed_batch_shape_fails_closed(tmp_path):
    brand = tmp_path / "output_Test_enriched" / "enriched"
    brand.mkdir(parents=True)
    (brand / "batch_1.json").write_text(json.dumps("a bare string"))

    with pytest.raises(harness.HarnessError):
        harness.load_corpus(tmp_path)


def test_missing_baseline_product_fails_closed():
    with pytest.raises(harness.HarnessError, match="missing"):
        harness.reconcile_ids({"1", "2"}, {"1"})


def test_added_product_fails_closed():
    with pytest.raises(harness.HarnessError, match="added"):
        harness.reconcile_ids({"1"}, {"1", "2"})


def test_reconcile_ids_accepts_exact_parity():
    harness.reconcile_ids({"1", "2"}, {"2", "1"})  # must not raise


def test_scoring_error_is_not_swallowed(scorer):
    """Baseline: score_products() caught every exception into a string field.
    A crash must surface, not become a row in the report."""
    with pytest.raises(Exception):
        harness.preview_scored({"this": "is not a product"}, scorer, strict=True)


def test_baseline_schema_mismatch_fails_closed(tmp_path):
    stale = tmp_path / "baseline.json"
    stale.write_text(json.dumps({"schema_version": "0-ancient", "types": {}}))

    with pytest.raises(harness.HarnessError, match="schema"):
        harness.load_baseline(stale)


# ---------------------------------------------------------------------------
# Deterministic baseline
# ---------------------------------------------------------------------------


def test_baseline_is_deterministic_and_self_describing(enricher, scorer, mineral_single):
    rows = {"900002": harness.classification_facts(
        harness.project_current_taxonomy(mineral_single, enricher)
    )}
    a = harness.build_baseline_payload(rows, scores={})
    b = harness.build_baseline_payload(rows, scores={})

    for key in ("schema_version", "baseline_commit", "corpus_count", "product_ids",
                "content_hash"):
        assert key in a, f"baseline must declare {key}"

    assert a["content_hash"] == b["content_hash"], "content hash must be stable"
    assert a["product_ids"] == sorted(a["product_ids"]), "product ids must be sorted"
    assert a["corpus_count"] == 1

    # The hash must exclude the timestamp, else it can never match.
    assert "generated_at" in a
    stamped = copy.deepcopy(a)
    stamped["generated_at"] = "1999-01-01T00:00:00Z"
    assert harness.content_hash_of(stamped) == harness.content_hash_of(a)


def test_content_hash_changes_when_a_fact_changes():
    a = harness.build_baseline_payload({"1": {"primary_type": "amino_acid"}}, scores={})
    b = harness.build_baseline_payload({"1": {"primary_type": "collagen"}}, scores={})
    assert a["content_hash"] != b["content_hash"]


# ---------------------------------------------------------------------------
# Ledger completeness
# ---------------------------------------------------------------------------


def test_ledger_is_not_truncated():
    """§8: 'Do not truncate the machine-readable ledger even when console
    output is summarized.'"""
    base = {str(i): {"primary_type": "general_supplement"} for i in range(200)}
    new = {str(i): {"primary_type": "collagen"} for i in range(200)}

    ledger = harness.build_ledger(base, new, harness.select_affected(base, new),
                                  base_scores={}, new_scores={})

    assert len(ledger) == 200, "every changed product must remain in the ledger"
    for entry in ledger.values():
        assert "old" in entry and "new" in entry
