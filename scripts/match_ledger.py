"""
Match Ledger Module

Provides centralized tracking of all match decisions during enrichment.
Ensures every entity match is auditable with full provenance.

CRITICAL: This module is the single source of truth for match tracking.
All domains (ingredients, additives, allergens, manufacturer, delivery, claims)
must record their matches through this ledger.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import normalization as norm_module


SCHEMA_VERSION = "1.1.0"

# Domain names for ledger entries
DOMAIN_INGREDIENTS = "ingredients"
DOMAIN_ADDITIVES = "additives"
DOMAIN_ALLERGENS = "allergens"
DOMAIN_MANUFACTURER = "manufacturer"
DOMAIN_DELIVERY = "delivery"
DOMAIN_CLAIMS = "claims"

ALL_DOMAINS = [
    DOMAIN_INGREDIENTS,
    DOMAIN_ADDITIVES,
    DOMAIN_ALLERGENS,
    DOMAIN_MANUFACTURER,
    DOMAIN_DELIVERY,
    DOMAIN_CLAIMS,
]

# Match decision types
DECISION_MATCHED = "matched"
DECISION_UNMATCHED = "unmatched"
DECISION_REJECTED = "rejected"
DECISION_SKIPPED = "skipped"
DECISION_RECOGNIZED_NON_SCORABLE = "recognized_non_scorable"  # Recognized but not therapeutic
DECISION_RECOGNIZED_BOTANICAL_UNSCORED = "recognized_botanical_unscored"  # Botanical recognized, not yet modeled for scoring

# Match method types
METHOD_EXACT = "exact"
METHOD_NORMALIZED = "normalized"
METHOD_PATTERN = "pattern"
METHOD_CONTAINS = "contains"
METHOD_TOKEN_BOUNDED = "token_bounded"
METHOD_FUZZY = "fuzzy"
METHOD_MANUAL = "manual"

# =============================================================================
# SCORING STATUS CONSTANTS
# =============================================================================
# Three distinct output states for API/UI consistency:
#
# 1. SCORED - Product was scored normally
#    - score != None, scored_ingredients_count > 0
#    - score_basis: "bioactives_scored"
#
# 2. NOT_APPLICABLE - Product has no scorable ingredients (botanical-only, etc.)
#    - score == None, scoring_status = "not_applicable"
#    - recognized_* counts populated for transparency
#    - UI: "No scorable bioactives; recognized botanicals only"
#    - score_basis: "no_scorable_ingredients"
#    - NOTE: Data completeness issues NEVER block - they produce not_applicable
#
# 3. BLOCKED - SAFETY BLOCK ONLY (banned/recalled ingredients detected)
#    - score == None, scoring_status = "blocked"
#    - RESERVED FOR: banned substances, recalled ingredients, critical safety issues
#    - UI: "Safety Block: contains banned/recall ingredient(s)"
#    - score_basis: "safety_block"
#    - NOTE: Coverage/data gaps must NEVER produce "blocked" status
# =============================================================================
SCORING_STATUS_SCORED = "scored"
SCORING_STATUS_NOT_APPLICABLE = "not_applicable"
SCORING_STATUS_BLOCKED = "blocked"  # SAFETY BLOCKS ONLY

# Score basis values for explainability
SCORE_BASIS_BIOACTIVES = "bioactives_scored"
SCORE_BASIS_NO_SCORABLE = "no_scorable_ingredients"
SCORE_BASIS_SAFETY_BLOCK = "safety_block"
SCORE_BASIS_SCORING_ERROR = "scoring_error"

# Evaluation stage values - indicates where in the pipeline the status was determined
# This helps debugging and user messaging:
# - "safety" = blocked due to safety scan (banned/recalled)
# - "scoring" = determined during scoring (scored, not_applicable, or error)
# - "postprocessing" = determined after scoring (future use: recall feed updates)
# - "unknown" = edge case / error state
EVALUATION_STAGE_SAFETY = "safety"
EVALUATION_STAGE_SCORING = "scoring"
EVALUATION_STAGE_POSTPROCESSING = "postprocessing"
EVALUATION_STAGE_UNKNOWN = "unknown"

# =============================================================================
# CENTRALIZED ROLLUP RULES (Single Source of Truth)
# =============================================================================
# These constants define which decision types are included in each metric.
# ALL coverage calculations MUST use these lists to prevent drift.
#
# CRITICAL: If you modify these, update:
# - build() method in MatchLedgerBuilder
# - regression_snapshot.py
# - coverage_gate.py report generation
# - Any UI components that display coverage
# =============================================================================

# Decisions that count as "recognized" (we know what it is)
RECOGNIZED_DECISIONS = frozenset([
    DECISION_MATCHED,
    DECISION_SKIPPED,
    DECISION_RECOGNIZED_NON_SCORABLE,
    DECISION_RECOGNIZED_BOTANICAL_UNSCORED,
])

# Decisions EXCLUDED from scorable_total (denominator for gate)
# These are recognized but should NOT affect the coverage gate
EXCLUDED_FROM_SCORABLE = frozenset([
    DECISION_SKIPPED,
    DECISION_RECOGNIZED_NON_SCORABLE,
    DECISION_RECOGNIZED_BOTANICAL_UNSCORED,
])


@dataclass
class LedgerEntry:
    """A single match decision entry in the ledger."""

    domain: str
    raw_source_text: str
    raw_source_path: str
    normalized_key: str
    canonical_id: Optional[str] = None
    match_method: Optional[str] = None
    confidence: float = 0.0
    matched_to_name: Optional[str] = None
    decision: str = DECISION_UNMATCHED
    decision_reason: Optional[str] = None
    candidates_top3: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        return {
            "domain": self.domain,
            "raw_source_text": self.raw_source_text,
            "raw_source_path": self.raw_source_path,
            "normalized_key": self.normalized_key,
            "canonical_id": self.canonical_id,
            "match_method": self.match_method,
            "confidence": self.confidence,
            "matched_to_name": self.matched_to_name,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "candidates_top3": self.candidates_top3,
        }


class MatchLedgerBuilder:
    """
    Builder for match ledger during enrichment.

    Usage:
        ledger = MatchLedgerBuilder()

        # Record ingredient matches
        ledger.record_match(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Vitamin B12",
            raw_source_path="activeIngredients[0].name",
            canonical_id="vitamin_b12",
            match_method=METHOD_EXACT,
            matched_to_name="Vitamin B12",
            confidence=1.0
        )

        # Record unmatched items
        ledger.record_unmatched(
            domain=DOMAIN_INGREDIENTS,
            raw_source_text="Novel Ingredient XYZ",
            raw_source_path="activeIngredients[1].name",
            reason="no_match_found",
            candidates=[{"canonical_id": "vitamin_x", "confidence": 0.5}, ...]
        )

        # Build final ledger
        final = ledger.build()
    """

    def __init__(self):
        """Initialize empty ledger."""
        self.entries: List[LedgerEntry] = []
        self._domain_counts: Dict[str, Dict[str, int]] = {
            domain: {
                "total": 0,
                "matched": 0,
                "unmatched": 0,
                "rejected": 0,
                "skipped": 0,
                "recognized_non_scorable": 0,  # Recognized but not therapeutic
                "recognized_botanical_unscored": 0,  # Botanical recognized but not modeled
            }
            for domain in ALL_DOMAINS
        }

    def record_match(
        self,
        domain: str,
        raw_source_text: str,
        raw_source_path: str,
        canonical_id: str,
        match_method: str,
        matched_to_name: str,
        confidence: float = 1.0,
        normalized_key: Optional[str] = None,
    ) -> None:
        """
        Record a successful match.

        Args:
            domain: Domain category (ingredients, additives, etc.)
            raw_source_text: Original text from DSLD
            raw_source_path: Source field path
            canonical_id: ID from reference database
            match_method: How the match was made (exact, normalized, etc.)
            matched_to_name: Canonical name from database
            confidence: Match confidence 0.0-1.0
            normalized_key: Pre-computed normalized key (auto-computed if None)
        """
        if not normalized_key:
            normalized_key = norm_module.make_normalized_key(raw_source_text)

        entry = LedgerEntry(
            domain=domain,
            raw_source_text=raw_source_text,
            raw_source_path=raw_source_path,
            normalized_key=normalized_key,
            canonical_id=canonical_id,
            match_method=match_method,
            confidence=confidence,
            matched_to_name=matched_to_name,
            decision=DECISION_MATCHED,
            decision_reason=None,
            candidates_top3=[],
        )

        self.entries.append(entry)
        self._domain_counts[domain]["total"] += 1
        self._domain_counts[domain]["matched"] += 1

    def record_unmatched(
        self,
        domain: str,
        raw_source_text: str,
        raw_source_path: str,
        reason: str = "no_match_found",
        candidates: Optional[List[Dict[str, Any]]] = None,
        normalized_key: Optional[str] = None,
    ) -> None:
        """
        Record an unmatched item.

        Args:
            domain: Domain category
            raw_source_text: Original text from DSLD
            raw_source_path: Source field path
            reason: Why no match was found
            candidates: Top candidate matches that were considered
            normalized_key: Pre-computed normalized key (auto-computed if None)
        """
        if not normalized_key:
            normalized_key = norm_module.make_normalized_key(raw_source_text)

        candidates_top3 = (candidates or [])[:3]

        entry = LedgerEntry(
            domain=domain,
            raw_source_text=raw_source_text,
            raw_source_path=raw_source_path,
            normalized_key=normalized_key,
            canonical_id=None,
            match_method=None,
            confidence=0.0,
            matched_to_name=None,
            decision=DECISION_UNMATCHED,
            decision_reason=reason,
            candidates_top3=candidates_top3,
        )

        self.entries.append(entry)
        self._domain_counts[domain]["total"] += 1
        self._domain_counts[domain]["unmatched"] += 1

    def record_rejected(
        self,
        domain: str,
        raw_source_text: str,
        raw_source_path: str,
        best_match_id: str,
        best_match_name: str,
        match_method: str,
        confidence: float,
        rejection_reason: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
        normalized_key: Optional[str] = None,
    ) -> None:
        """
        Record a rejected match (match found but rejected due to threshold or rule).

        Args:
            domain: Domain category
            raw_source_text: Original text from DSLD
            raw_source_path: Source field path
            best_match_id: ID of best candidate
            best_match_name: Name of best candidate
            match_method: Method used
            confidence: Confidence score (below threshold)
            rejection_reason: Why the match was rejected
            candidates: Other candidates considered
            normalized_key: Pre-computed normalized key
        """
        if not normalized_key:
            normalized_key = norm_module.make_normalized_key(raw_source_text)

        candidates_top3 = (candidates or [])[:3]
        # Include the rejected best match in candidates if not already there
        if best_match_id and not any(c.get("canonical_id") == best_match_id for c in candidates_top3):
            candidates_top3.insert(0, {
                "canonical_id": best_match_id,
                "matched_name": best_match_name,
                "confidence": confidence,
                "method": match_method,
            })
            candidates_top3 = candidates_top3[:3]

        entry = LedgerEntry(
            domain=domain,
            raw_source_text=raw_source_text,
            raw_source_path=raw_source_path,
            normalized_key=normalized_key,
            canonical_id=None,  # Rejected, so no canonical_id assigned
            match_method=match_method,
            confidence=confidence,
            matched_to_name=best_match_name,
            decision=DECISION_REJECTED,
            decision_reason=rejection_reason,
            candidates_top3=candidates_top3,
        )

        self.entries.append(entry)
        self._domain_counts[domain]["total"] += 1
        self._domain_counts[domain]["rejected"] += 1

    def record_skipped(
        self,
        domain: str,
        raw_source_text: str,
        raw_source_path: str,
        skip_reason: str,
        normalized_key: Optional[str] = None,
    ) -> None:
        """
        Record a skipped item (intentionally not matched).

        Args:
            domain: Domain category
            raw_source_text: Original text from DSLD
            raw_source_path: Source field path
            skip_reason: Why the item was skipped
            normalized_key: Pre-computed normalized key
        """
        if not normalized_key:
            normalized_key = norm_module.make_normalized_key(raw_source_text)

        entry = LedgerEntry(
            domain=domain,
            raw_source_text=raw_source_text,
            raw_source_path=raw_source_path,
            normalized_key=normalized_key,
            canonical_id=None,
            match_method=None,
            confidence=0.0,
            matched_to_name=None,
            decision=DECISION_SKIPPED,
            decision_reason=skip_reason,
            candidates_top3=[],
        )

        self.entries.append(entry)
        self._domain_counts[domain]["total"] += 1
        self._domain_counts[domain]["skipped"] += 1

    def record_recognized_non_scorable(
        self,
        domain: str,
        raw_source_text: str,
        raw_source_path: str,
        recognition_source: str,
        recognition_reason: str,
        normalized_key: Optional[str] = None,
    ) -> None:
        """
        Record a recognized but non-scorable item.

        These are ingredients that are RECOGNIZED (not unmapped) but should
        NOT be quality-scored because they are not therapeutic actives.

        Examples:
        - Oils (sunflower oil, coconut oil) - carriers, not bioactives
        - Food powders (apple cider vinegar, beet juice powder)
        - Fibers used as excipients

        Args:
            domain: Domain category
            raw_source_text: Original text from DSLD
            raw_source_path: Source field path
            recognition_source: Which database recognized it (e.g., "other_ingredients", "excipient_list")
            recognition_reason: Why it's non-scorable (e.g., "carrier_oil", "food_powder")
            normalized_key: Pre-computed normalized key
        """
        if not normalized_key:
            normalized_key = norm_module.make_normalized_key(raw_source_text)

        entry = LedgerEntry(
            domain=domain,
            raw_source_text=raw_source_text,
            raw_source_path=raw_source_path,
            normalized_key=normalized_key,
            canonical_id=None,
            match_method=recognition_source,  # Reuse field to track source
            confidence=1.0,  # High confidence we recognized it
            matched_to_name=None,
            decision=DECISION_RECOGNIZED_NON_SCORABLE,
            decision_reason=recognition_reason,
            candidates_top3=[],
        )

        self.entries.append(entry)
        self._domain_counts[domain]["total"] += 1
        self._domain_counts[domain]["recognized_non_scorable"] += 1

    def record_recognized_botanical_unscored(
        self,
        domain: str,
        raw_source_text: str,
        raw_source_path: str,
        botanical_db_match: str,
        reason: str = "botanical_not_scored",
        normalized_key: Optional[str] = None,
    ) -> None:
        """
        Record a botanical ingredient recognized but NOT scored in core scoring.

        BOTANICAL POLICY:
        - Botanicals are NOT scored in the core scoring system
        - They are EXCLUDED from scorable_total (and gate denominators)
        - They are INCLUDED in recognition_coverage (tracks mapping progress)
        - standardized_botanicals.json is bonus-only: award capped bonus ONLY when
          label contains standardization evidence (marker %, mg, branded extract)

        These are botanicals that:
        - Exist in standardized_botanicals DB (recognized)
        - Do NOT contribute to quality score calculations
        - MAY award bonus points if standardization evidence is present

        This is SIMILAR to recognized_non_scorable in gate behavior:
        - Both are excluded from scorable_total
        - Both count toward recognition_coverage
        - Difference: botanicals can earn bonus points with standardization evidence

        Implications for coverage:
        - Recognition coverage: counts as recognized
        - Scorable coverage: EXCLUDED from scorable_total
          This prevents gate failures due to botanical coverage gaps.

        Args:
            domain: Domain category
            raw_source_text: Original text from DSLD
            raw_source_path: Source field path
            botanical_db_match: Which botanical entry matched
            reason: Why it's unscored (default: botanical_not_scored)
            normalized_key: Pre-computed normalized key
        """
        if not normalized_key:
            normalized_key = norm_module.make_normalized_key(raw_source_text)

        entry = LedgerEntry(
            domain=domain,
            raw_source_text=raw_source_text,
            raw_source_path=raw_source_path,
            normalized_key=normalized_key,
            canonical_id=None,
            match_method="standardized_botanicals",  # Track which DB recognized it
            confidence=0.8,  # High recognition confidence, but not full scoring
            matched_to_name=botanical_db_match,
            decision=DECISION_RECOGNIZED_BOTANICAL_UNSCORED,
            decision_reason=reason,
            candidates_top3=[],
        )

        self.entries.append(entry)
        self._domain_counts[domain]["total"] += 1
        self._domain_counts[domain]["recognized_botanical_unscored"] += 1

    def get_unmatched_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all unmatched entries for a domain."""
        return [
            entry.to_dict()
            for entry in self.entries
            if entry.domain == domain and entry.decision == DECISION_UNMATCHED
        ]

    def get_rejected_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all rejected entries for a domain."""
        return [
            entry.to_dict()
            for entry in self.entries
            if entry.domain == domain and entry.decision == DECISION_REJECTED
        ]

    def get_entries_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all entries for a domain."""
        return [entry.to_dict() for entry in self.entries if entry.domain == domain]

    def build(self) -> Dict[str, Any]:
        """
        Build the final match ledger structure.

        Returns:
            Dict with schema_version, domains, and summary.

        Coverage Metrics (per botanical policy):
        - recognition_coverage: % of items we can identify
          (matched + skipped + recognized_non_scorable + recognized_botanical_unscored)
        - scorable_coverage: % of scorable items we can quality-score (matched / scorable_total)
          where scorable_total = total - skipped - recognized_non_scorable - recognized_botanical_unscored

        BOTANICAL POLICY:
        - Botanicals are NOT scored in the core scoring system
        - They are EXCLUDED from scorable_total (and gate denominators)
        - They are INCLUDED in recognition_coverage (tracks mapping progress)
        - Bonus points awarded only when standardization evidence present (marker %, mg, etc.)

        The GATE should use scorable_coverage, not recognition_coverage.
        This prevents botanicals/oils/carriers from inflating the denominator.
        """
        domains = {}
        for domain in ALL_DOMAINS:
            counts = self._domain_counts[domain]
            domain_entries = self.get_entries_for_domain(domain)

            # RECOGNITION coverage: Do we know what this is?
            # Numerator: matched + skipped + recognized_non_scorable + recognized_botanical_unscored
            # Denominator: total
            recognition_coverage = 0.0
            if counts["total"] > 0:
                recognized = (
                    counts["matched"] +
                    counts["skipped"] +
                    counts["recognized_non_scorable"] +
                    counts["recognized_botanical_unscored"]  # Botanicals ARE recognized
                )
                recognition_coverage = round((recognized / counts["total"]) * 100, 2)

            # SCORABLE coverage: Of things that SHOULD be scored, did we score them?
            # Numerator: matched (successfully scored)
            # Denominator: total - skipped - recognized_non_scorable - recognized_botanical_unscored
            # NOTE: Botanicals are EXCLUDED from scorable_total per policy:
            #   - Botanicals do not contribute to core quality score
            #   - They are bonus-only (standardization evidence awards capped bonus)
            #   - Excluding them prevents gate failures due to botanical coverage gaps
            scorable_total = (
                counts["total"] -
                counts["skipped"] -
                counts["recognized_non_scorable"] -
                counts["recognized_botanical_unscored"]  # Botanicals excluded from scoring
            )
            # SCORABLE_TOTAL=0 CONTRACT:
            # If scorable_total == 0: scorable_coverage = 100% (vacuous; no scorable items missed)
            # This ensures botanical-only products don't fail gate with "0% coverage"
            if scorable_total == 0:
                scorable_coverage = 100.0  # Vacuously covered - nothing TO score
            elif scorable_total > 0:
                scorable_coverage = round((counts["matched"] / scorable_total) * 100, 2)
            else:
                scorable_coverage = 0.0  # Edge case: negative (shouldn't happen)

            # Legacy coverage (for backward compat) - same as old formula
            legacy_coverage = 0.0
            if counts["total"] > 0:
                covered = counts["matched"] + counts["skipped"]
                legacy_coverage = round((covered / counts["total"]) * 100, 2)

            domains[domain] = {
                "total_raw": counts["total"],
                "matched": counts["matched"],
                "unmatched": counts["unmatched"],
                "rejected": counts["rejected"],
                "skipped": counts["skipped"],
                "recognized_non_scorable": counts["recognized_non_scorable"],
                "recognized_botanical_unscored": counts["recognized_botanical_unscored"],
                # Dual coverage metrics
                "recognition_coverage_percent": recognition_coverage,
                "scorable_coverage_percent": scorable_coverage,
                "scorable_total": scorable_total,
                # Legacy (use scorable_coverage for gates)
                "coverage_percent": scorable_coverage,
                "entries": domain_entries,
            }

        # Calculate overall summary
        total_entities = sum(self._domain_counts[d]["total"] for d in ALL_DOMAINS)
        total_matched = sum(self._domain_counts[d]["matched"] for d in ALL_DOMAINS)
        total_skipped = sum(self._domain_counts[d]["skipped"] for d in ALL_DOMAINS)
        total_recognized_non_scorable = sum(
            self._domain_counts[d]["recognized_non_scorable"] for d in ALL_DOMAINS
        )
        total_recognized_botanical_unscored = sum(
            self._domain_counts[d]["recognized_botanical_unscored"] for d in ALL_DOMAINS
        )

        # Overall recognition coverage (includes botanicals)
        total_recognized = (
            total_matched +
            total_skipped +
            total_recognized_non_scorable +
            total_recognized_botanical_unscored
        )
        overall_recognition_coverage = 0.0
        if total_entities > 0:
            overall_recognition_coverage = round((total_recognized / total_entities) * 100, 2)

        # Overall scorable coverage (botanicals EXCLUDED from denominator per policy)
        total_scorable = (
            total_entities -
            total_skipped -
            total_recognized_non_scorable -
            total_recognized_botanical_unscored  # Botanicals excluded from scoring
        )
        # SCORABLE_TOTAL=0 CONTRACT (overall):
        # If total_scorable == 0: coverage = 100% (vacuous; nothing to score)
        if total_scorable == 0:
            overall_scorable_coverage = 100.0  # Vacuously covered
        elif total_scorable > 0:
            overall_scorable_coverage = round((total_matched / total_scorable) * 100, 2)
        else:
            overall_scorable_coverage = 0.0  # Edge case

        coverage_by_domain = {
            domain: domains[domain]["scorable_coverage_percent"]
            for domain in ALL_DOMAINS
        }

        recognition_by_domain = {
            domain: domains[domain]["recognition_coverage_percent"]
            for domain in ALL_DOMAINS
        }

        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "domains": domains,
            "summary": {
                "total_entities": total_entities,
                "total_matched": total_matched,
                "total_skipped": total_skipped,
                "total_recognized_non_scorable": total_recognized_non_scorable,
                "total_recognized_botanical_unscored": total_recognized_botanical_unscored,
                "total_unmatched": sum(self._domain_counts[d]["unmatched"] for d in ALL_DOMAINS),
                "total_rejected": sum(self._domain_counts[d]["rejected"] for d in ALL_DOMAINS),
                # Dual coverage metrics
                "recognition_coverage_percent": overall_recognition_coverage,
                "scorable_coverage_percent": overall_scorable_coverage,
                "scorable_total": total_scorable,
                # Legacy (gates should use scorable_coverage)
                "coverage_percent": overall_scorable_coverage,
                "coverage_by_domain": coverage_by_domain,
                "recognition_by_domain": recognition_by_domain,
            }
        }

    def build_unmatched_lists(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build structured unmatched lists for each domain.

        Returns:
            Dict with unmatched_* keys for each domain.
        """
        return {
            "unmatched_ingredients": self.get_unmatched_for_domain(DOMAIN_INGREDIENTS),
            "unmatched_additives": self.get_unmatched_for_domain(DOMAIN_ADDITIVES),
            "unmatched_allergens": self.get_unmatched_for_domain(DOMAIN_ALLERGENS),
            "unmatched_delivery_systems": self.get_unmatched_for_domain(DOMAIN_DELIVERY),
            "rejected_manufacturer_matches": self.get_rejected_for_domain(DOMAIN_MANUFACTURER),
            "rejected_claim_matches": self.get_rejected_for_domain(DOMAIN_CLAIMS),
        }


# =============================================================================
# HELPER FUNCTIONS FOR SCORING STATUS DETERMINATION
# =============================================================================

def _extract_botanical_evidence(ledger: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract botanical standardization evidence from a match ledger.

    This provides clean explainability data for:
    - NOT_APPLICABLE scores (botanical-only products)
    - Bonus point decisions (standardization evidence)

    PAYLOAD CAPS (for API performance):
    - Max 25 botanicals returned in list
    - raw_source_text truncated to 150 chars
    - Full details available in logs, not app payload

    Returns:
        Dict with:
        - recognized_count: int (total count, may exceed list length)
        - botanicals: list of {name, raw_source_text, decision_reason} (capped at 25)
        - truncated: bool (True if list was capped)
        - note: str (explains standardization rules)
    """
    MAX_BOTANICALS_IN_PAYLOAD = 25
    MAX_RAW_TEXT_LENGTH = 150

    domains = ledger.get("domains", {})
    ing_domain = domains.get(DOMAIN_INGREDIENTS, {})
    entries = ing_domain.get("entries", [])

    all_botanical_entries = []
    for entry in entries:
        if entry.get("decision") == DECISION_RECOGNIZED_BOTANICAL_UNSCORED:
            raw_text = entry.get("raw_source_text", "")
            # Truncate raw_source_text to keep payload size reasonable
            if len(raw_text) > MAX_RAW_TEXT_LENGTH:
                raw_text = raw_text[:MAX_RAW_TEXT_LENGTH] + "..."

            all_botanical_entries.append({
                "name": entry.get("matched_to_name", entry.get("raw_source_text", "unknown")),
                "raw_source_text": raw_text,
                "decision_reason": entry.get("decision_reason", "botanical_not_scored"),
                "match_method": entry.get("match_method", "standardized_botanicals"),
            })

    total_count = len(all_botanical_entries)
    truncated = total_count > MAX_BOTANICALS_IN_PAYLOAD
    capped_entries = all_botanical_entries[:MAX_BOTANICALS_IN_PAYLOAD]

    return {
        "recognized_count": total_count,
        "botanicals": capped_entries,
        "truncated": truncated,
        # Standardization evidence is determined during enrichment/scoring
        # by checking for % markers, mg standardization, branded extracts
        # This field documents what was recognized; standardization bonus is separate
        "note": "Standardization bonus awarded only if label contains explicit standardization evidence (%, mg, branded extract names)",
    }


def compute_scoring_eligibility(ledger: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine scoring eligibility from a built match ledger.

    This is the SINGLE SOURCE OF TRUTH for determining whether a product
    should be scored, marked not_applicable, or blocked.

    Args:
        ledger: Built match ledger from MatchLedgerBuilder.build()

    Returns:
        Dict with:
        - scoring_status: SCORING_STATUS_SCORED | NOT_APPLICABLE | BLOCKED
        - can_score: bool (True if scoring should proceed)
        - reason: str (human-readable explanation)
        - scorable_total: int (number of scorable items)
        - recognized_botanicals: int (botanical count for UI)
        - recognized_excipients: int (excipient count for UI)
        - ui_message: str (display message for product pages)

    SCORABLE_TOTAL=0 CONTRACT:
    - If scorable_total == 0:
      - scoring_status = "not_applicable"
      - can_score = False (do NOT produce numeric score)
      - Gate: PASS (do not block)
      - UI: "No scorable bioactives; recognized botanicals only"
    """
    domains = ledger.get("domains", {})
    summary = ledger.get("summary", {})

    # Get ingredients domain (primary for scoring decisions)
    ing_domain = domains.get(DOMAIN_INGREDIENTS, {})
    scorable_total = ing_domain.get("scorable_total", 0)
    recognized_botanicals = ing_domain.get("recognized_botanical_unscored", 0)
    recognized_excipients = ing_domain.get("recognized_non_scorable", 0)
    matched = ing_domain.get("matched", 0)
    unmatched = ing_domain.get("unmatched", 0)
    total_raw = ing_domain.get("total_raw", 0)

    # SCORABLE_TOTAL=0 CONTRACT: No scorable items = not_applicable
    if scorable_total == 0:
        # Determine if it's botanical-only, excipient-only, or empty
        if recognized_botanicals > 0 and recognized_excipients == 0:
            reason = "botanical_only"
            ui_message = "No scorable bioactives; recognized botanicals only"
        elif recognized_excipients > 0 and recognized_botanicals == 0:
            reason = "excipient_only"
            ui_message = "No scorable bioactives; recognized excipients only"
        elif recognized_botanicals > 0 and recognized_excipients > 0:
            reason = "botanical_and_excipient_only"
            ui_message = "No scorable bioactives; recognized botanicals and excipients only"
        elif total_raw == 0:
            reason = "no_ingredients"
            ui_message = "No ingredients found to evaluate"
        else:
            reason = "all_non_scorable"
            ui_message = "No scorable bioactives found"

        # Extract botanical details for standardization evidence
        botanical_evidence = _extract_botanical_evidence(ledger)

        return {
            "scoring_status": SCORING_STATUS_NOT_APPLICABLE,
            "can_score": False,
            "reason": reason,
            "scorable_total": 0,
            "matched": matched,
            "unmatched": unmatched,
            "recognized_botanicals": recognized_botanicals,
            "recognized_excipients": recognized_excipients,
            "total_raw": total_raw,
            "ui_message": ui_message,
            # Standardization evidence for botanicals - clean explainability field
            "botanical_evidence": botanical_evidence,
        }

    # Has scorable items - check if coverage is sufficient
    scorable_coverage = ing_domain.get("scorable_coverage_percent", 0.0)

    # If there are unmatched scorable items, check if it should be blocked
    # Note: The actual blocking threshold is applied in coverage_gate.py
    # Here we just report the status
    if matched > 0 or scorable_total > 0:
        return {
            "scoring_status": SCORING_STATUS_SCORED,
            "can_score": True,
            "reason": "scorable_ingredients_present",
            "scorable_total": scorable_total,
            "matched": matched,
            "unmatched": unmatched,
            "recognized_botanicals": recognized_botanicals,
            "recognized_excipients": recognized_excipients,
            "total_raw": total_raw,
            "ui_message": None,  # Normal scoring - no special message
        }

    # Fallback (shouldn't reach here)
    return {
        "scoring_status": SCORING_STATUS_SCORED,
        "can_score": True,
        "reason": "default",
        "scorable_total": scorable_total,
        "matched": matched,
        "unmatched": unmatched,
        "recognized_botanicals": recognized_botanicals,
        "recognized_excipients": recognized_excipients,
        "total_raw": total_raw,
        "ui_message": None,
    }
