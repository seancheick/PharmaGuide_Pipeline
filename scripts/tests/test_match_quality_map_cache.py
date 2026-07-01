"""TDD + adversarial regression suite for the `_match_quality_map` memoization cache.

The matcher is the pipeline's hot path (exact → alias → token → fuzzy cascade,
run per ingredient occurrence with no caching). `_match_quality_map` is wrapped
by a memoizing layer over `_match_quality_map_impl`.

CONTRACT (clinical):
  cached_wrapper(args) == impl(args)   for EVERY argument tuple.

The cache key MUST include every result-affecting argument — in particular
`cleaner_canonical_id`, which HARD-CONSTRAINS the matched parent (the
Silybin / "phospholipid complex" milk_thistle-vs-lecithin medical-accuracy fix
documented on `_match_quality_map`). A cache keyed on a subset (e.g. only
ing_name/std_name/cleaned_forms) would collide two clinically distinct
ingredients and silently mis-score one of them. `test_cleaner_canonical_id_*`
fails on exactly that bug.

Empirically (probe, IQM v-current), the label "Phospholipid Complex" resolves to
THREE distinct results purely via cleaner_canonical_id:
  cci=None        -> None  (no match)
  cci=milk_thistle-> bio 7.0
  cci=phosphorus  -> bio 8.0
so it is a sensitive collision fixture.
"""
import copy

import pytest

from enrich_supplements_v3 import SupplementEnricherV3


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3()


@pytest.fixture
def qmap(enricher):
    return enricher.databases["ingredient_quality_map"]


def _ref(enricher, **kw):
    """Uncached reference value: call the impl directly (never the wrapper)."""
    return enricher._match_quality_map_impl(**kw)


# --- structure -------------------------------------------------------------

def test_wrapper_impl_and_cache_exist(enricher):
    assert callable(getattr(enricher, "_match_quality_map", None))
    assert callable(getattr(enricher, "_match_quality_map_impl", None))
    assert isinstance(getattr(enricher, "_match_quality_cache", None), dict)


# --- the cache is actually used --------------------------------------------

def test_second_identical_call_hits_cache(enricher, qmap):
    enricher._match_quality_cache.clear()
    calls = {"n": 0}
    orig = enricher._match_quality_map_impl

    def spy(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    enricher._match_quality_map_impl = spy
    try:
        r1 = enricher._match_quality_map("Vitamin D3", "Vitamin D3", qmap)
        r2 = enricher._match_quality_map("Vitamin D3", "Vitamin D3", qmap)
    finally:
        enricher._match_quality_map_impl = orig

    assert calls["n"] == 1, "second identical call must be served from cache"
    assert r1 == r2


# --- CLINICAL: cache key must include cleaner_canonical_id ------------------

def test_cleaner_canonical_id_not_collided(enricher, qmap):
    name = "Phospholipid Complex"
    enricher._match_quality_cache.clear()

    # Call through the wrapper in sequence sharing ONE cache.
    got_none = enricher._match_quality_map(name, name, qmap, cleaner_canonical_id=None)
    got_mt = enricher._match_quality_map(name, name, qmap, cleaner_canonical_id="milk_thistle")
    got_phos = enricher._match_quality_map(name, name, qmap, cleaner_canonical_id="phosphorus")

    # Each must equal its OWN uncached reference (a subset-key cache fails here).
    assert got_none == _ref(enricher, ing_name=name, std_name=name, quality_map=qmap,
                            cleaner_canonical_id=None)
    assert got_mt == _ref(enricher, ing_name=name, std_name=name, quality_map=qmap,
                          cleaner_canonical_id="milk_thistle")
    assert got_phos == _ref(enricher, ing_name=name, std_name=name, quality_map=qmap,
                            cleaner_canonical_id="phosphorus")

    # Sensitivity guard: the three results must genuinely differ, otherwise this
    # test could not detect a collision. If the IQM changes such that they no
    # longer differ, pick a new fixture rather than weakening the assertion.
    assert got_none != got_mt != got_phos and got_none != got_phos, (
        "collision fixture no longer differentiates by cleaner_canonical_id"
    )


# --- None results are cached (the *expensive* unmapped path) ----------------

def test_none_result_is_cached_and_correct(enricher, qmap):
    name = "Phospholipid Complex"
    enricher._match_quality_cache.clear()
    calls = {"n": 0}
    orig = enricher._match_quality_map_impl

    def spy(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    enricher._match_quality_map_impl = spy
    try:
        r1 = enricher._match_quality_map(name, name, qmap, cleaner_canonical_id=None)
        r2 = enricher._match_quality_map(name, name, qmap, cleaner_canonical_id=None)
    finally:
        enricher._match_quality_map_impl = orig

    assert r1 is None and r2 is None
    assert calls["n"] == 1, "cached None must not re-run the impl"


# --- callers may mutate results without poisoning the cache -----------------

def test_returned_value_is_isolated_from_cache(enricher, qmap):
    enricher._match_quality_cache.clear()
    r1 = enricher._match_quality_map("Vitamin D3", "Vitamin D3", qmap)
    assert isinstance(r1, dict), "fixture must match for this test to be meaningful"
    r1["__poison__"] = "MUTATED"
    r1["bio_score"] = -999
    r2 = enricher._match_quality_map("Vitamin D3", "Vitamin D3", qmap)
    assert "__poison__" not in r2
    assert r2.get("bio_score") != -999


# --- equivalence over a matrix that varies every key argument --------------

def test_cached_equals_uncached_across_argument_matrix(enricher, qmap):
    enricher._match_quality_cache.clear()
    forms_a = [{"name": "Retinyl Palmitate", "percent": None}]
    matrix = [
        dict(ing_name="Magnesium Glycinate", std_name="Magnesium Glycinate", quality_map=qmap),
        dict(ing_name="Vitamin D3", std_name="Cholecalciferol", quality_map=qmap),
        dict(ing_name="Vitamin A", std_name="Vitamin A", quality_map=qmap, cleaned_forms=forms_a),
        dict(ing_name="Phospholipid Complex", std_name="Phospholipid Complex",
             quality_map=qmap, cleaner_canonical_id="milk_thistle"),
        dict(ing_name="Phospholipid Complex", std_name="Phospholipid Complex",
             quality_map=qmap, cleaner_canonical_id="phosphorus"),
        dict(ing_name="Curcumin", std_name="Curcumin", quality_map=qmap,
             preferred_parent="curcumin"),
        dict(ing_name="KSM-66", std_name="Ashwagandha", quality_map=qmap,
             branded_token="KSM-66"),
        dict(ing_name="Totally Unknown Junk XYZ", std_name="Totally Unknown Junk XYZ",
             quality_map=qmap),
    ]
    # Reference (uncached) computed first so the wrapper cache can't influence it.
    refs = [copy.deepcopy(_ref(enricher, **args)) for args in matrix]
    # Run wrapper twice over the matrix (second pass = all cache hits).
    for _ in range(2):
        for args, ref in zip(matrix, refs):
            assert enricher._match_quality_map(**args) == ref
