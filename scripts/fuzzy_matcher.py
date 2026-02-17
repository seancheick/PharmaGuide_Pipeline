"""
Fuzzy matching fallback layer for ingredient matching.

This module provides fuzzy string matching as a secondary matching strategy
for ingredients that don't match via exact token-bounded matching. It uses
rapidfuzz for efficient fuzzy matching with configurable confidence thresholds.

Usage:
    from fuzzy_matcher import FuzzyMatcher

    matcher = FuzzyMatcher(threshold=85)
    result = matcher.match("Vitamin B-12", ["Vitamin B12", "Cyanocobalamin"])
    # Returns: {"match": "Vitamin B12", "score": 95, "method": "fuzzy_ratio"}

Design Principles:
    - Only used as fallback when exact/token matching fails
    - High default threshold (85) to minimize false positives
    - Returns confidence score for auditability
    - Flags low-confidence matches for human review
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class FuzzyMatcher:
    """
    Fuzzy string matcher with configurable thresholds and multiple algorithms.

    Attributes:
        threshold: Minimum score (0-100) to consider a match valid
        review_threshold: Score below which matches are flagged for human review
        max_candidates: Maximum number of candidates to consider
    """

    # Default thresholds optimized for safety-critical matching
    DEFAULT_THRESHOLD = 85  # High threshold for precision
    REVIEW_THRESHOLD = 90   # Flag for review if below this
    MAX_CANDIDATES = 5      # Limit candidate processing

    def __init__(
        self,
        threshold: int = DEFAULT_THRESHOLD,
        review_threshold: int = REVIEW_THRESHOLD,
        max_candidates: int = MAX_CANDIDATES
    ):
        self.threshold = threshold
        self.review_threshold = review_threshold
        self.max_candidates = max_candidates

    def normalize_for_fuzzy(self, text: str) -> str:
        """
        Normalize text for fuzzy matching.

        - Lowercase
        - Remove extra whitespace
        - Normalize hyphens/dashes to single hyphen
        - Keep alphanumeric and hyphens only
        """
        if not text:
            return ""
        text = text.lower().strip()
        # Normalize various dash characters to hyphen
        text = re.sub(r'[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]', '-', text)
        # Collapse multiple spaces/hyphens
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'-+', '-', text)
        return text

    def match(
        self,
        query: str,
        candidates: List[str],
        scorer: str = "ratio"
    ) -> Optional[Dict]:
        """
        Find the best fuzzy match for a query against candidates.

        Args:
            query: The string to match
            candidates: List of candidate strings to match against
            scorer: Scoring algorithm - "ratio", "partial_ratio", "token_sort_ratio"

        Returns:
            Dict with keys: match, score, method, needs_review
            None if no match above threshold
        """
        if not query or not candidates:
            return None

        query_norm = self.normalize_for_fuzzy(query)
        if not query_norm:
            return None

        # Filter empty candidates
        valid_candidates = [c for c in candidates if c and c.strip()]
        if not valid_candidates:
            return None

        # Select scoring function
        scorer_func = self._get_scorer(scorer)

        # Use process.extractOne for efficiency
        result = process.extractOne(
            query_norm,
            valid_candidates,
            scorer=scorer_func,
            processor=self.normalize_for_fuzzy
        )

        if result is None:
            return None

        match_text, score, _ = result

        if score < self.threshold:
            return None

        return {
            "match": match_text,
            "score": score,
            "method": f"fuzzy_{scorer}",
            "needs_review": score < self.review_threshold
        }

    def match_multi_algorithm(
        self,
        query: str,
        candidates: List[str]
    ) -> Optional[Dict]:
        """
        Try multiple fuzzy algorithms and return the best result.

        Order of algorithms (by reliability for ingredient names):
        1. token_sort_ratio - handles word order differences ("Vitamin B12" vs "B12 Vitamin")
        2. ratio - standard Levenshtein ratio
        3. partial_ratio - substring matching (for abbreviated names)

        Returns the highest scoring match that exceeds threshold.
        """
        algorithms = ["token_sort_ratio", "ratio", "partial_ratio"]
        best_result = None

        for algo in algorithms:
            result = self.match(query, candidates, scorer=algo)
            if result:
                if best_result is None or result["score"] > best_result["score"]:
                    best_result = result

        return best_result

    def batch_match(
        self,
        queries: List[str],
        candidates: List[str],
        scorer: str = "ratio"
    ) -> Dict[str, Optional[Dict]]:
        """
        Match multiple queries against the same candidate list.

        More efficient than calling match() repeatedly for large batches.

        Returns:
            Dict mapping query -> match result (or None)
        """
        results = {}
        for query in queries:
            results[query] = self.match(query, candidates, scorer)
        return results

    def _get_scorer(self, scorer_name: str):
        """Get the scoring function by name."""
        scorers = {
            "ratio": fuzz.ratio,
            "partial_ratio": fuzz.partial_ratio,
            "token_sort_ratio": fuzz.token_sort_ratio,
            "token_set_ratio": fuzz.token_set_ratio,
            "WRatio": fuzz.WRatio,
        }
        return scorers.get(scorer_name, fuzz.ratio)

    def explain_match(
        self,
        query: str,
        candidate: str,
        show_all_scores: bool = False
    ) -> Dict:
        """
        Provide detailed explanation of how two strings match.

        Useful for debugging and auditing match decisions.

        Returns:
            Dict with detailed scoring breakdown
        """
        query_norm = self.normalize_for_fuzzy(query)
        cand_norm = self.normalize_for_fuzzy(candidate)

        result = {
            "query_original": query,
            "query_normalized": query_norm,
            "candidate_original": candidate,
            "candidate_normalized": cand_norm,
            "scores": {
                "ratio": fuzz.ratio(query_norm, cand_norm),
                "partial_ratio": fuzz.partial_ratio(query_norm, cand_norm),
                "token_sort_ratio": fuzz.token_sort_ratio(query_norm, cand_norm),
                "token_set_ratio": fuzz.token_set_ratio(query_norm, cand_norm),
            },
            "threshold": self.threshold,
            "review_threshold": self.review_threshold,
        }

        # Determine best match
        best_score = max(result["scores"].values())
        best_algo = max(result["scores"], key=result["scores"].get)

        result["best_score"] = best_score
        result["best_algorithm"] = best_algo
        result["would_match"] = best_score >= self.threshold
        result["needs_review"] = self.threshold <= best_score < self.review_threshold

        return result


# Convenience functions for common use cases

def fuzzy_match_ingredient(
    ingredient_name: str,
    candidate_names: List[str],
    threshold: int = 85
) -> Optional[Dict]:
    """
    Match an ingredient name against candidates with default settings.

    This is the recommended entry point for ingredient matching.
    Uses multi-algorithm matching for best results.

    Args:
        ingredient_name: Name to match
        candidate_names: List of known ingredient names
        threshold: Minimum score (default 85 for high precision)

    Returns:
        Match result dict or None if no match
    """
    matcher = FuzzyMatcher(threshold=threshold)
    return matcher.match_multi_algorithm(ingredient_name, candidate_names)


def build_alias_index(ingredients: List[Dict]) -> Dict[str, str]:
    """
    Build an index mapping all aliases to their canonical names.

    Args:
        ingredients: List of ingredient dicts with 'standard_name' and 'aliases' keys

    Returns:
        Dict mapping alias -> standard_name
    """
    index = {}
    for ing in ingredients:
        std_name = ing.get("standard_name", "")
        if not std_name:
            continue

        # Add standard name itself
        index[std_name.lower()] = std_name

        # Add all aliases
        for alias in ing.get("aliases", []):
            if alias:
                index[alias.lower()] = std_name

    return index


if __name__ == "__main__":
    # Demo usage
    print("=== Fuzzy Matcher Demo ===\n")

    candidates = [
        "Vitamin B12",
        "Cyanocobalamin",
        "Methylcobalamin",
        "Vitamin D3",
        "Cholecalciferol",
        "Magnesium Glycinate",
        "Magnesium Citrate",
    ]

    test_queries = [
        "Vitamin B-12",      # Hyphen variant
        "B12 Vitamin",       # Word order
        "Vit B12",           # Abbreviation
        "Cyancobalamin",     # Typo
        "Mag Glycinate",     # Abbreviation
        "Calcium Citrate",   # No match expected
    ]

    matcher = FuzzyMatcher(threshold=80)

    for query in test_queries:
        result = matcher.match_multi_algorithm(query, candidates)
        if result:
            review_flag = " [REVIEW]" if result["needs_review"] else ""
            print(f"'{query}' -> '{result['match']}' "
                  f"(score: {result['score']}, method: {result['method']}){review_flag}")
        else:
            print(f"'{query}' -> No match")
