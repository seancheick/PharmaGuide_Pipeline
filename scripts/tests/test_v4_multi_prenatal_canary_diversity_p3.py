"""v4 multi_or_prenatal canary diversity — real-catalog routing guards.

Mirror of test_v4_omega_canary_diversity_p161.py for the multi/prenatal class.
Locks the v4 router against two classes of regression that surfaced during
Codex-P3 end-to-end verification (2026-05-20):

  Bug B (medium): GoL MyKind Multi misroutes to `generic` because the
                  enricher emitted supp_type=specialty AND primary_category=None
                  for clearly multivitamin products (13 vitamins + 4 minerals).

  Bug C (severe): The enricher's supp_type=multivitamin signal is over-eager
                  for targeted/specialty products (Collagen Love, Hum Mighty
                  Night sleep aid, Vitafusion Omega-3 EPA/DHA, etc.). The
                  v4 router previously trusted supp_type=multivitamin
                  absolutely, sending these to multi_or_prenatal where they
                  scored poorly against a panel-coverage rubric.

The fix wires the router to read `primary_type` from the new supplement
taxonomy (scripts/supplement_taxonomy.py, 2026-05-20) as the primary signal.
The taxonomy uses canonical-ID based panel composition analysis instead of
trusting the enricher's heuristic supp_type field.

If the enriched catalog in this checkout was generated before the taxonomy
landed (so blobs lack a `primary_type` field), the tests compute the
taxonomy inline via classify_supplement() — exactly how the live enricher
will populate it going forward.

If a canary ID isn't in scripts/products/ at all, those tests skip.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# --- Canary set 1: TRUE POSITIVES (real multivitamins / prenatals) ----
# Format: dsld_id → (expected_route, expected_primary_type, label)
TRUE_POSITIVE_TARGETS = {
    # Mainstream gummy/tablet multivitamins — supp_type=multivitamin already
    # routes them today. Lock against regression.
    "12933":  ("multi_or_prenatal", "multivitamin",
               "Vitafusion Women's Complete MultiVitamin"),
    "177200": ("multi_or_prenatal", "multivitamin",
               "Vitafusion Complete Multivitamin Natural Blackberry"),
    "177046": ("multi_or_prenatal", "multivitamin",
               "Vitafusion Platinum 50+ Natural Peach"),
    "26583":  ("multi_or_prenatal", "multivitamin",
               "Spring Valley Women's Daily Multivitamin Formula"),
    "26587":  ("multi_or_prenatal", "multivitamin",
               "Spring Valley Men's Daily MultiVitamin Formula"),
    "178361": ("multi_or_prenatal", "multivitamin",
               "Spring Valley Women's Multivitamin"),
    # Prenatals with DHA must stay multivitamin-class. Earlier taxonomy
    # builds classified these as omega_3; TAXONOMY-BUG-1 locks the corrected
    # decision tree where broad prenatal vitamin/mineral panels beat the
    # omega signal.
    "246067": ("multi_or_prenatal", "multivitamin",
               "Vitafusion PreNatal Gummy (prenatal multi with DHA)"),
    "267507": ("multi_or_prenatal", "multivitamin",
               "SmartyPants PreNatal (prenatal multi with DHA)"),

    # Bug B fix: GoL MyKind Multi — enricher emits supp_type=specialty AND
    # primary_category=None, but the canonical-ID panel (13 V + 4 M) makes
    # primary_type=multivitamin under the new taxonomy. Must route to
    # multi_or_prenatal, NOT generic.
    "173888": ("multi_or_prenatal", "multivitamin",
               "Garden of Life MyKind Organics Men's Multi 40+ Berry "
               "(supp_type=specialty in enriched blob)"),
    "173918": ("multi_or_prenatal", "multivitamin",
               "Garden of Life MyKind Organics Women's Multi 40+ Berry "
               "(supp_type=specialty in enriched blob)"),
    "246201": ("multi_or_prenatal", "multivitamin",
               "Garden of Life MyKind Organics Women's Multi Cherry "
               "(supp_type=specialty in enriched blob)"),
}


# --- Canary set 2: FALSE POSITIVES (Bug C — must NOT route to multi) -----
# These products have supp_type=multivitamin in the OLD enricher output,
# which sent them to multi_or_prenatal incorrectly. The new taxonomy
# classifies them correctly based on actual panel composition. Expected
# primary_types below reflect what classify_supplement() actually returns
# today; any drift in the taxonomy classifier is a separate concern from
# the v4 router fix this file locks.
#   - Vitafusion Omega-3 EPA/DHA → omega_3 (route omega)
#   - Hum Collagen Love (single ing) → general_supplement (route generic)
#   - Hum Counter Cravings (herbs + minerals) → herbal_botanical
#     (TAXONOMY-NOTE: route generic either way)
    #   - Hum Mighty Night (sleep aid w/ herbs) → sleep_support
    #     (TAXONOMY-BUG-2 fixed: sleep name signal overrides herb plurality;
    #     route generic because there is no dedicated v4 sleep module)
#   - Hum Hair Sweet Hair → b_complex (3 B-vitamins + zinc/PABA/Fo-Ti adjuncts);
#     the b_complex route is generic, so it never hits the multivitamin rubric.
#     (Restored by the <=3 non-B-adjunct fix in supplement_taxonomy.py; the blob
#     re-bakes b_complex on the next enrichment.)
#   - Vitafusion Everyday Energy → general_supplement (caffeine/CoQ10 energy
#     product, disqualified from b_complex); routes generic, not multi.
# Format: dsld_id → (expected_route, expected_primary_type, label)
FALSE_POSITIVE_TARGETS = {
    "174772": ("omega", "single_vitamin",
               "Vitafusion Omega-3 EPA/DHA — CRITICAL: this is the bug "
               "that bypasses the entire omega module"),
    "241676": ("generic", None,
               "Hum Collagen Love (1 vitamin, 0 minerals — not a multi)"),
    "241681": ("generic", "herbal_botanical",
               "Hum Counter Cravings (herbs dominant — not multi)"),
    "241692": ("generic", "b_complex",
               "Hum Hair Sweet Hair (beauty name signal — not multi)"),
    "241699": ("generic", "sleep_support",
               "Hum Mighty Night (sleep aid — not multi)"),
    "176800": ("generic", "general_supplement",
               "Vitafusion Everyday Energy (energy/caffeine → general, not multi)"),
}


_canary_cache: dict | None = None
_ALL_CANARY_IDS = set(TRUE_POSITIVE_TARGETS.keys()) | set(FALSE_POSITIVE_TARGETS.keys())


def _load_canaries(ids: set[str]) -> dict:
    """One-shot loader scanning enriched batches for ALL canary dsld_ids
    on first call. Subsequent calls hit the cache. Mirrors omega canary
    loader pattern from test_v4_omega_canary_diversity_p161.py."""
    global _canary_cache
    if _canary_cache is not None:
        return {did: _canary_cache[did] for did in ids if did in _canary_cache}

    enriched_root = SCRIPTS_ROOT / "products"
    if not enriched_root.exists():
        _canary_cache = {}
        pytest.skip("no enriched products dir in this checkout")

    target_ids = _ALL_CANARY_IDS
    found: dict[str, dict] = {}
    for path in enriched_root.glob("output_*_enriched/enriched/*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else (
            data.get("products") or data.get("items") or []
        )
        for item in items:
            if not isinstance(item, dict):
                continue
            did = str(item.get("dsld_id") or item.get("id") or "")
            if did in target_ids:
                found[did] = item
        if len(found) == len(target_ids):
            break
    _canary_cache = found
    return {did: _canary_cache[did] for did in ids if did in _canary_cache}


def _ensure_taxonomy(product: dict) -> dict:
    """Return a product blob with `primary_type` populated.

    If the enriched batch already has the field (post-taxonomy enricher
    output), pass through unchanged. Otherwise compute it inline via
    classify_supplement() — exactly what the live enricher will write
    for products re-enriched after the taxonomy landed.
    """
    if product.get("primary_type"):
        return product
    from supplement_taxonomy import classify_supplement
    taxonomy = classify_supplement(product)
    # Mutate a copy so the cache stays clean across tests.
    augmented = dict(product)
    augmented["supplement_taxonomy"] = taxonomy
    augmented["primary_type"] = taxonomy["primary_type"]
    augmented["secondary_type"] = taxonomy.get("secondary_type")
    return augmented


# --- True positive routing tests ---------------------------------------


@pytest.mark.parametrize("dsld_id,expected", [(k, v) for k, v in TRUE_POSITIVE_TARGETS.items()])
def test_multi_canary_routes_to_multi_or_prenatal(dsld_id, expected):
    """Each real multivitamin/prenatal canary routes to multi_or_prenatal.

    Locks Bug B (MyKind misroute to generic) and the existing happy-path
    cases together so a router regression lights up immediately.
    """
    from scoring_v4.router import class_for_product

    expected_route, expected_primary, label = expected
    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"DSLD {dsld_id} ({label}) not in enriched catalog")

    product = _ensure_taxonomy(canaries[dsld_id])

    # Sanity: the new taxonomy classified this as multivitamin.
    actual_primary = product.get("primary_type")
    assert actual_primary == expected_primary, (
        f"DSLD {dsld_id} ({label}): taxonomy returned primary_type={actual_primary!r}, "
        f"expected {expected_primary!r}. If the taxonomy classification changed, "
        f"update CANARY_TARGETS rather than weakening this assertion."
    )

    route = class_for_product(product)
    assert route == expected_route, (
        f"DSLD {dsld_id} ({label}): routed to {route!r}, expected {expected_route!r}. "
        f"primary_type={actual_primary!r}, "
        f"supp_type={product.get('supplement_type', {}).get('type')!r}, "
        f"primary_category={product.get('primary_category')!r}."
    )


# --- False-positive routing guards -------------------------------------


@pytest.mark.parametrize("dsld_id,expected", [(k, v) for k, v in FALSE_POSITIVE_TARGETS.items()])
def test_multi_false_positive_does_not_route_to_multi(dsld_id, expected):
    """Targeted/specialty products mis-classified by the OLD enricher as
    supp_type=multivitamin must NOT route to multi_or_prenatal.

    Bug C (severe): pre-fix, six real catalog products were sent to
    multi_or_prenatal where they scored against a broad-panel RDA-coverage
    rubric. Vitafusion Omega-3 EPA/DHA was the most dangerous — it bypassed
    the entire omega module.
    """
    from scoring_v4.router import class_for_product

    expected_route, expected_primary, label = expected
    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"DSLD {dsld_id} ({label}) not in enriched catalog")

    product = _ensure_taxonomy(canaries[dsld_id])

    actual_primary = product.get("primary_type")
    if expected_primary is not None:
        assert actual_primary == expected_primary, (
            f"DSLD {dsld_id} ({label}): taxonomy returned primary_type={actual_primary!r}, "
            f"expected {expected_primary!r}. Routing test is meaningless if the "
            f"taxonomy classification drifts. Update the canary if intentional."
        )

    route = class_for_product(product)
    assert route != "multi_or_prenatal", (
        f"DSLD {dsld_id} ({label}): WRONG — routed to multi_or_prenatal "
        f"despite primary_type={actual_primary!r}. The router still trusts "
        f"the legacy supp_type=multivitamin signal. Fix: read primary_type "
        f"from supplement_taxonomy as the primary routing signal."
    )
    assert route == expected_route, (
        f"DSLD {dsld_id} ({label}): routed to {route!r}, expected {expected_route!r}."
    )


# --- Coverage diversity assertions -------------------------------------


def test_multi_canary_coverage_spans_required_diversity():
    """At least 8 true-positive canaries and 5 false-positive canaries.

    Locks the canary set against accidental shrinkage.
    """
    assert len(TRUE_POSITIVE_TARGETS) >= 8, (
        "Need at least 8 true-positive multi canaries for diversity. "
        f"Current: {len(TRUE_POSITIVE_TARGETS)}"
    )
    assert len(FALSE_POSITIVE_TARGETS) >= 5, (
        "Need at least 5 false-positive guards (per Bug C audit). "
        f"Current: {len(FALSE_POSITIVE_TARGETS)}"
    )


def test_multi_canary_covers_mykind_misroute():
    """MyKind Multi cases (Bug B) must be in the true-positive set.

    These are the products where supp_type=specialty AND primary_category=None
    cause the legacy router to send them to generic.
    """
    mykind_ids = {"173888", "173918", "246201"}
    missing = mykind_ids - set(TRUE_POSITIVE_TARGETS.keys())
    assert not missing, (
        f"MyKind Multi canaries missing from true-positive set: {missing}. "
        f"These are the Bug B regression guards."
    )


def test_multi_canary_covers_omega_misroute():
    """Vitafusion Omega-3 EPA/DHA (174772) must be in the false-positive
    set. This is the most severe Bug C case — an omega product mis-routed
    to multi bypasses the entire P1.6 omega module.
    """
    assert "174772" in FALSE_POSITIVE_TARGETS, (
        "Vitafusion Omega-3 EPA/DHA (174772) missing from false-positive set. "
        "This is the most dangerous Bug C case."
    )
    expected_route, _, _ = FALSE_POSITIVE_TARGETS["174772"]
    assert expected_route == "omega", (
        f"Vitafusion Omega-3 must route to omega, not {expected_route!r}."
    )
