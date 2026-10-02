"""A dropped normalizer or matcher is freed, with all the data it loaded.

2026-10-02: one fast-suite shard held 43.8 million live allocations by the end
(15.6 GB on the CI runner) because class-level @lru_cache methods key on self,
so every instance a test ever built stayed alive with its reference indexes.
"""

from __future__ import annotations

import gc
import weakref

from enhanced_normalizer import EnhancedDSLDNormalizer, EnhancedIngredientMatcher


def _is_freed(ref: weakref.ref) -> bool:
    gc.collect()
    return ref() is None


def test_a_used_normalizer_is_freed():
    normalizer = EnhancedDSLDNormalizer()
    normalizer._enhanced_harmful_check_cached("titanium dioxide")
    normalizer._enhanced_non_harmful_check_cached("cellulose")
    normalizer._enhanced_allergen_check_cached("whey", ())
    ref = weakref.ref(normalizer)
    del normalizer

    assert _is_freed(ref)


def test_a_used_matcher_is_freed():
    matcher = EnhancedIngredientMatcher()
    matcher._safe_fuzzy_match_cached("vitamin c", ("vitamin c", "zinc"), None)
    ref = weakref.ref(matcher)
    del matcher

    assert _is_freed(ref)


def test_the_cache_still_answers_from_memory():
    normalizer = EnhancedDSLDNormalizer()
    first = normalizer._enhanced_harmful_check_cached("titanium dioxide")
    second = normalizer._enhanced_harmful_check_cached("titanium dioxide")

    assert second is first
    assert normalizer._enhanced_harmful_check_cached.cache_info().hits >= 1
