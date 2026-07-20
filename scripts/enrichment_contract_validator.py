"""
Enrichment Contract Validator

Enforces minimum contract rules for enriched product consistency.
These invariants must hold for any valid enriched product output.

Contract Rules:
A. Sugar Consistency - sugar flags must be internally consistent
B. Allergen Precedence - no duplicate allergens with weaker presence_type
C. Colors Consistency - natural colors must not be flagged as artificial
D. Serving Basis Integrity - form_factor and basis_unit must be consistent
E. Claims Consistency - claims must have valid evidence and no scoring conflicts
F. Provenance Integrity - raw_source_text and normalized_key must be present and immutable
G. Match Ledger Consistency - match_ledger must be present and consistent with unmatched lists
H. Label Ledger Release Contract - display, form, identity, omission, and completeness integrity

Usage:
    validator = EnrichmentContractValidator()
    violations = validator.validate(enriched_product)

    if violations:
        for v in violations:
            print(f"[{v['severity']}] {v['rule']}: {v['message']}")
"""

import logging
import re
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

from constants import DISPLAY_LEDGER_SOURCE_SECTIONS
from scoring_input_contract import SCORING_ROUTE_MODULES

logger = logging.getLogger(__name__)


# =============================================================================
# PIPELINE CONTRACT VERSION
# =============================================================================
# Bump this version when:
# - Match ledger schema changes (new fields, renamed fields, removed fields)
# - Invariant rules change (new rules, changed thresholds, removed rules)
# - Provenance field semantics change
# - Coverage gate thresholds change in breaking ways
#
# This version should be checked by consumers (scoring, reports, downstream tools)
# to ensure compatibility with the enriched data format.
#
# Version history:
# - 1.0.0: Initial hardened pipeline with match_ledger, provenance fields,
#          coverage gates, and invariant validation
# - 1.1.0: Label-ledger form, identity, omission, and completeness release gates
# =============================================================================
PIPELINE_CONTRACT_VERSION = "1.1.0"


@dataclass
class ContractViolation:
    """Represents a contract violation"""
    rule: str  # Rule ID (e.g., "A.1", "B.2")
    rule_name: str  # Human-readable rule name
    severity: str  # "error" or "warning"
    message: str  # Detailed violation message
    product_id: str  # Product identifier
    field_path: str  # JSON path to the violating field
    expected: Any = None  # Expected value
    actual: Any = None  # Actual value
    evidence: Dict = field(default_factory=dict)  # Supporting evidence


class EnrichmentContractValidator:
    """
    Validates enriched products against minimum contract rules.

    Can be used:
    - As a post-enrichment validation step
    - In regression tests
    - For batch auditing
    """

    # =========================================================================
    # CANONICAL_ID MONOTONICITY SCOPE
    # =========================================================================
    # canonical_id monotonicity (cannot downgrade to null) applies ONLY to
    # these domains. Other domains (manufacturer, delivery, claims) may have
    # null canonical_id as expected behavior (e.g., unmatched manufacturer).
    #
    # Rationale:
    # - ingredients/additives/allergens: Core scoring domains, must be matched
    # - manufacturer: Bonus-only, unmatched is acceptable
    # - delivery: Detected from form, not always matchable
    # - claims: Optional, many products have no claims
    # =========================================================================
    CANONICAL_ID_MONOTONICITY_DOMAINS = frozenset({
        "ingredients",
        "additives",
        "allergens",
    })

    # Domains where unmatched canonical_id is acceptable (bonus/optional)
    CANONICAL_ID_OPTIONAL_DOMAINS = frozenset({
        "manufacturer",
        "delivery",
        "claims",
    })

    # Allergen presence type precedence (higher = stronger)
    ALLERGEN_PRESENCE_PRIORITY = {
        "contains": 5,
        "may_contain": 4,
        "facility_warning": 3,
        "ingredient_list": 2,
        "unknown": 1
    }

    # Artificial color additive IDs
    ARTIFICIAL_COLOR_IDS = {
        "ADD_ARTIFICIAL_COLORS",
        "ADD_SYNTHETIC_COLORS",
        "ADD_RED40",
        "ADD_YELLOW5",
        "ADD_YELLOW6",
        "ADD_BLUE1",
        "ADD_BLUE2",
        "ADD_GREEN3"
    }

    # Gummy form factor normalized variants
    # basis_unit is LABEL-FAITHFUL (the unit the label declares); form_factor is
    # the canonical form. DSLD gummy labels legitimately declare servings by
    # shape/marketing name ("1 Jelly Bean", "Nordic Berries") and sometimes by
    # mass ("2.2 Gram(s)" for 2 gummies, servingQuantitySource="label"). None of
    # those are normalization failures, so they must not warn. D.1a still fails
    # closed on genuinely truncated/garbled units.
    GUMMY_UNIT_VARIANTS = {
        "gummy", "gummies", "gummy(ies)", "gummie", "gummie(s)",
        # Shape / marketing count units observed on real DSLD labels. Kept
        # evidence-based: add a term only when the corpus shows it, so the rule
        # still flags genuinely unnormalized units (e.g. "piece").
        "jelly bean", "jelly beans",   # CVS 239580, Natures_Bounty 308199
        "swirly bear",                 # CVS 25945 "Gummy Swirls"
        "chewable bear",               # Garden_of_life 321386
        "chew", "chews",               # GNC 228076
        "nordic berry", "nordic berries",  # nordic-naturals 221659
        # Label-declared mass servings (Pure_Encapsulations 278384: the label
        # declares 2.2 Gram(s) == 2 gummies @ 1.1 g, servingQuantitySource="label")
        "gram", "grams",
    }

    DISPLAY_LEDGER_REQUIRED_FIELDS = frozenset({
        "raw_source_path",
        "raw_source_text",
        "display_name",
        "label_display_name",
        "label_order",
        "nested_depth",
        "source_section",
        "display_type",
        "resolution_type",
        "score_included",
        "display_disposition",
        "form_display_state",
        "identity_integrity_state",
        "ledger_fingerprint",
    })

    DISPLAY_LEDGER_ALLOWED_SOURCE_SECTIONS = DISPLAY_LEDGER_SOURCE_SECTIONS

    DISPLAY_LEDGER_FORM_STATES = frozenset({
        "assessed",
        "not_disclosed",
        "listed_not_assessed",
        "not_applicable",
        "needs_review",
    })

    DISPLAY_LEDGER_IDENTITY_STATES = frozenset({
        "clean",
        "repaired",
        "taxonomy_only",
        "identity_conflict",
        "missing_display_label",
    })

    DISPLAY_LEDGER_ACTIVE_SECTIONS = frozenset({"active", "activeIngredients"})

    LABEL_LEDGER_OMISSION_REASONS = frozenset({
        "nutrition_fact_not_applicable",
        "decorative_or_header_text",
        "duplicate_source_line",
        "empty_source_text",
        "unsupported_source_structure",
    })

    LABEL_LEDGER_AUDIT_REQUIRED_FIELDS = frozenset({
        "support_status",
        "source_structure",
        "meaningful_source_rows",
        "displayed_rows",
        "omitted_rows",
        "completeness_percentage",
        "completeness_status",
    })

    LABEL_LEDGER_SUPPORT_STATES = frozenset({"supported", "unsupported"})
    LABEL_LEDGER_SUPPORTED_EMPTY_STRUCTURES = frozenset({"empty_panel"})
    LABEL_LEDGER_COMPLETENESS_STATES = frozenset({
        "complete",
        "incomplete",
        "unavailable",
    })

    NEEDS_REVIEW_CLAIM_PATHS = (
        ("exact_dose_text",),
        ("display_dose_label",),
        ("dose_claim",),
        ("form_quality_claim",),
        ("form_quality",),
        ("form_quality_rating",),
        ("bio_score",),
        ("safety_claim",),
        ("safety_status",),
        ("safety_rating",),
        ("safety_verdict",),
        ("is_safe",),
        ("analysis", "display_dose_label"),
        ("analysis", "dose_claim"),
        ("analysis", "form_quality_claim"),
        ("analysis", "form_quality"),
        ("analysis", "form_quality_rating"),
        ("analysis", "bio_score"),
        ("analysis", "safety_claim"),
        ("analysis", "safety_status"),
        ("analysis", "safety_rating"),
        ("analysis", "safety_verdict"),
        ("analysis", "is_safe"),
    )

    CLEANER_ALLOWED_SOURCE_SECTIONS = frozenset({
        "active",
        "inactive",
        "nutrition",
        "label",
        "unknown",
    })

    CLEANER_NON_SCORABLE_ROLES = frozenset({
        "blend_header_total",
        "nested_display_only",
        "composition_leaf",
        "source_descriptor",
        "nutrition_rollup",
        "excipient",
        "inactive",
        "label_header",
        "review_required",
    })

    CLEANER_SCORABLE_ROLES = frozenset({
        "active_scorable",
        "active_misfiled_in_inactive",
    })

    VALID_IQD_DOSE_CLASSES = frozenset({
        "therapeutic_mass",
        "enzyme_activity",
        "probiotic_cfu",
        "percent_dv_only",
    })

    VALID_SCORING_CLASSIFICATION_ROUTES = SCORING_ROUTE_MODULES

    VALID_SCORING_CLASSIFICATION_ORIGINS = frozenset({
        "compatibility_derived",
        "native_enrichment",
    })

    VALID_SCORING_ROUTE_CONFIDENCE = frozenset({
        "high",
        "medium",
        "low",
        "failed",
    })

    REQUIRED_SCORING_CLASSIFICATION_FIELDS = frozenset({
        "classification_schema_version",
        "classification_origin",
        "classification_failed",
        "route_module",
        "route_reason",
        "route_confidence",
        "route_evidence",
        "ingredients",
        "profile_eligibility",
    })

    SAFETY_IDENTITY_SOURCES = frozenset({
        "banned_recalled",
        "banned_recalled_ingredients",
        "harmful_additives",
        "allergens",
        "contaminants",
        "recalls",
    })

    SAFETY_FLAG_REQUIRED_FIELDS = frozenset({
        "entry_id",
        "source_db",
        "status",
        "severity",
        "match_type",
        "matched_variant",
        "evidence_text",
        "confidence",
    })

    NEGATIVE_MATCH_MODES = frozenset({"exact", "substring"})

    QUALIFIED_SAFETY_NAME_RE = re.compile(
        r"\b(?:high\s+dose|e\d+|extract|asbestos|monacolin|hexavalent|chromate|dichromate|vi|6\+)\b",
        re.IGNORECASE,
    )

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: If True, warnings are treated as errors
        """
        self.strict_mode = strict_mode

    def validate(self, product: Dict) -> List[ContractViolation]:
        """
        Validate an enriched product against all contract rules.

        Args:
            product: Enriched product dictionary

        Returns:
            List of ContractViolation objects (empty if all rules pass)
        """
        violations = []
        product_id = product.get("dsld_id", product.get("id", product.get("productId", "unknown")))

        # Run all contract validations
        violations.extend(self._validate_sugar_consistency(product, product_id))
        violations.extend(self._validate_allergen_precedence(product, product_id))
        violations.extend(self._validate_colors_consistency(product, product_id))
        violations.extend(self._validate_serving_basis_integrity(product, product_id))
        violations.extend(self._validate_claims_consistency(product, product_id))
        violations.extend(self._validate_provenance_integrity(product, product_id))
        violations.extend(self._validate_match_ledger_consistency(product, product_id))
        violations.extend(self._validate_display_ledger_contract(product, product_id))
        violations.extend(self._validate_identity_safety_separation(product, product_id))
        violations.extend(self._validate_scoring_classification_contract(product, product_id))

        return violations

    def validate_release_integrity(self, product: Dict) -> List[ContractViolation]:
        """Return the label-ledger failures consumed by release audits.

        This is validation-only: it never repairs identity, rewrites form state,
        or mutates score publication fields.
        """
        product_id = product.get(
            "dsld_id", product.get("id", product.get("productId", "unknown"))
        )
        return self._validate_display_ledger_contract(product, product_id)

    def validate_batch(self, products: List[Dict]) -> Dict[str, List[ContractViolation]]:
        """
        Validate a batch of products.

        Returns:
            Dict mapping product_id to list of violations
        """
        results = {}
        for product in products:
            product_id = product.get("dsld_id", product.get("id", product.get("productId", "unknown")))
            violations = self.validate(product)
            if violations:
                results[product_id] = violations
        return results

    def get_summary(self, violations: List[ContractViolation]) -> Dict[str, Any]:
        """
        Generate a summary of violations by rule.
        """
        summary = {
            "total_violations": len(violations),
            "errors": sum(1 for v in violations if v.severity == "error"),
            "warnings": sum(1 for v in violations if v.severity == "warning"),
            "by_rule": {}
        }

        for v in violations:
            if v.rule not in summary["by_rule"]:
                summary["by_rule"][v.rule] = {
                    "rule_name": v.rule_name,
                    "count": 0,
                    "severity": v.severity
                }
            summary["by_rule"][v.rule]["count"] += 1

        return summary

    # =========================================================================
    # RULE A: Sugar Consistency
    # =========================================================================

    def _validate_sugar_consistency(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule A: Sugar consistency validation.

        A.1: If sugar_g > 0 OR has_added_sugar == true:
             - contains_sugar must be true
             - level must not be "sugar_free"

        A.2: If sugar_sources is non-empty:
             - contains_sugar must be true
        """
        violations = []

        dietary = product.get("dietary_sensitivity_data", {})
        sugar_data = dietary.get("sugar", {})

        amount_g = sugar_data.get("amount_g", 0) or 0
        has_added_sugar = sugar_data.get("has_added_sugar", False)
        contains_sugar = sugar_data.get("contains_sugar", False)
        level = sugar_data.get("level", "")
        sugar_sources = sugar_data.get("sugar_sources", []) or []

        # A.1: amount_g > 0 OR has_added_sugar implies contains_sugar and not sugar_free
        if amount_g > 0 or has_added_sugar:
            if not contains_sugar:
                violations.append(ContractViolation(
                    rule="A.1a",
                    rule_name="Sugar Consistency - contains_sugar flag",
                    severity="error",
                    message=f"contains_sugar is false but amount_g={amount_g} or has_added_sugar={has_added_sugar}",
                    product_id=product_id,
                    field_path="dietary_sensitivity_data.sugar.contains_sugar",
                    expected=True,
                    actual=contains_sugar,
                    evidence={"amount_g": amount_g, "has_added_sugar": has_added_sugar}
                ))

            if level == "sugar_free":
                violations.append(ContractViolation(
                    rule="A.1b",
                    rule_name="Sugar Consistency - level cannot be sugar_free",
                    severity="error",
                    message=f"level is 'sugar_free' but amount_g={amount_g} or has_added_sugar={has_added_sugar}",
                    product_id=product_id,
                    field_path="dietary_sensitivity_data.sugar.level",
                    expected="not 'sugar_free'",
                    actual=level,
                    evidence={"amount_g": amount_g, "has_added_sugar": has_added_sugar}
                ))

        # A.2: sugar_sources non-empty implies contains_sugar
        if sugar_sources and not contains_sugar:
            violations.append(ContractViolation(
                rule="A.2",
                rule_name="Sugar Consistency - sugar_sources implies contains_sugar",
                severity="error",
                message=f"contains_sugar is false but sugar_sources has {len(sugar_sources)} entries",
                product_id=product_id,
                field_path="dietary_sensitivity_data.sugar.contains_sugar",
                expected=True,
                actual=contains_sugar,
                evidence={"sugar_sources": sugar_sources[:3]}  # First 3 for brevity
            ))

        return violations

    # =========================================================================
    # RULE B: Allergen Precedence
    # =========================================================================

    def _validate_allergen_precedence(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule B: Allergen precedence validation.

        B.1: If any allergen has presence_type == "contains":
             - No duplicate records for same allergen with weaker presence_type

        B.2: If has_may_contain_warning == true:
             - Must exist at least one allergen with presence_type in {may_contain, facility_warning}
        """
        violations = []

        dietary = product.get("dietary_sensitivity_data", {})
        allergens = dietary.get("allergens", []) or []
        has_may_contain_warning = dietary.get("has_may_contain_warning", False)

        # Build allergen presence map
        allergen_presence: Dict[str, List[Dict]] = {}
        for allergen in allergens:
            allergen_id = allergen.get("allergen_id", allergen.get("allergen_name", "unknown"))
            if allergen_id not in allergen_presence:
                allergen_presence[allergen_id] = []
            allergen_presence[allergen_id].append(allergen)

        # B.1: Check for duplicate allergens with conflicting presence_types
        for allergen_id, records in allergen_presence.items():
            if len(records) > 1:
                presence_types = [r.get("presence_type", "unknown") for r in records]
                priorities = [self.ALLERGEN_PRESENCE_PRIORITY.get(pt, 0) for pt in presence_types]

                max_priority = max(priorities)
                has_contains = "contains" in presence_types

                # If "contains" is present, there should be only one record
                if has_contains and len(records) > 1:
                    weaker_types = [pt for pt in presence_types if pt != "contains"]
                    if weaker_types:
                        violations.append(ContractViolation(
                            rule="B.1",
                            rule_name="Allergen Precedence - no duplicates with weaker type",
                            severity="error",
                            message=f"Allergen '{allergen_id}' has 'contains' but also weaker types: {weaker_types}",
                            product_id=product_id,
                            field_path="dietary_sensitivity_data.allergens",
                            expected="single record with 'contains'",
                            actual=f"{len(records)} records with types {presence_types}",
                            evidence={"allergen_id": allergen_id, "records": records}
                        ))

        # B.2: has_may_contain_warning implies at least one may_contain/facility_warning allergen
        if has_may_contain_warning:
            may_contain_types = {"may_contain", "facility_warning"}
            has_may_contain_allergen = any(
                a.get("presence_type") in may_contain_types
                for a in allergens
            )

            if not has_may_contain_allergen:
                violations.append(ContractViolation(
                    rule="B.2",
                    rule_name="Allergen Precedence - may_contain_warning requires allergen",
                    severity="error",
                    message="has_may_contain_warning is true but no allergen has may_contain/facility_warning presence_type",
                    product_id=product_id,
                    field_path="dietary_sensitivity_data.has_may_contain_warning",
                    expected="at least one allergen with may_contain or facility_warning",
                    actual=f"{len(allergens)} allergens, none with may_contain/facility_warning",
                    evidence={"allergen_presence_types": [a.get("presence_type") for a in allergens]}
                ))

        return violations

    # =========================================================================
    # RULE C: Colors Consistency
    # =========================================================================

    def _validate_colors_consistency(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule C: Colors consistency validation.

        C.1: If cleaned standardName == "natural colors":
             - enriched must not include ADD_ARTIFICIAL_COLORS

        C.2: If enriched flags an artificial dye:
             - cleaned should be "artificial colors" OR ingredient has explicit dye token
        """
        violations = []

        # Get all ingredients (active + inactive)
        all_ingredients = (
            (product.get("activeIngredients", []) or []) +
            (product.get("inactiveIngredients", []) or [])
        )

        # Get harmful additives from enrichment
        contaminant_data = product.get("contaminant_data", {})
        harmful_additives = contaminant_data.get("harmful_additives", {})
        flagged_additives = harmful_additives.get("additives", []) or []

        # Build set of flagged artificial color IDs
        flagged_artificial_colors = {
            a.get("additive_id") for a in flagged_additives
            if a.get("additive_id") in self.ARTIFICIAL_COLOR_IDS
        }

        # Build map of ingredients by name
        ingredient_map = {
            ing.get("name", "").lower(): ing
            for ing in all_ingredients if ing
        }

        # C.1: Natural colors should not be flagged as artificial
        for ing in all_ingredients:
            if not ing:
                continue

            std_name = (ing.get("standardName", "") or "").lower()
            ing_name = (ing.get("name", "") or "").lower()

            if std_name == "natural colors":
                # Check if this ingredient is flagged as artificial color
                flagged_for_this = [
                    a for a in flagged_additives
                    if a.get("ingredient", "").lower() == ing_name
                    and a.get("additive_id") in self.ARTIFICIAL_COLOR_IDS
                ]

                if flagged_for_this:
                    violations.append(ContractViolation(
                        rule="C.1",
                        rule_name="Colors Consistency - natural colors not flagged as artificial",
                        severity="error",
                        message=f"Ingredient '{ing.get('name')}' has standardName='natural colors' but is flagged as artificial",
                        product_id=product_id,
                        field_path="contaminant_data.harmful_additives",
                        expected="no artificial color flag",
                        actual=f"flagged with {[a.get('additive_id') for a in flagged_for_this]}",
                        evidence={
                            "ingredient": ing.get("name"),
                            "standardName": std_name,
                            "forms": ing.get("forms", [])
                        }
                    ))

        # C.2: Artificial dye flag should have evidence (explicit dye name or artificial standardName)
        explicit_dye_tokens = {
            "red 40", "yellow 5", "yellow 6", "blue 1", "blue 2", "green 3",
            "fd&c", "fdc", "lake"
        }

        for additive in flagged_additives:
            if additive.get("additive_id") not in self.ARTIFICIAL_COLOR_IDS:
                continue

            flagged_ing_name = (additive.get("ingredient", "") or "").lower()
            ing = ingredient_map.get(flagged_ing_name, {})
            std_name = (ing.get("standardName", "") or "").lower()

            # Check if there's evidence for the artificial color flag
            has_artificial_standardname = std_name == "artificial colors"
            # Labels write dyes as "Red #40" / "Blue #1"; the tokens are stored
            # unhashed ("red 40"), so a raw substring test never matched and a
            # literal FD&C dye was reported as lacking evidence that it is a dye.
            normalized_ing_name = re.sub(
                r"\s+", " ", flagged_ing_name.replace("#", " ")
            ).strip()
            has_explicit_dye = any(
                token in normalized_ing_name
                for token in explicit_dye_tokens
            )

            if not has_artificial_standardname and not has_explicit_dye:
                # This is a warning, not an error - might be valid based on context
                violations.append(ContractViolation(
                    rule="C.2",
                    rule_name="Colors Consistency - artificial flag should have evidence",
                    severity="warning",
                    message=f"Artificial color flag for '{flagged_ing_name}' lacks evidence (no 'artificial colors' standardName or explicit dye token)",
                    product_id=product_id,
                    field_path="contaminant_data.harmful_additives",
                    expected="standardName='artificial colors' OR explicit dye token in name",
                    actual=f"standardName='{std_name}'",
                    evidence={
                        "ingredient": flagged_ing_name,
                        "additive_id": additive.get("additive_id")
                    }
                ))

        return violations

    # =========================================================================
    # RULE D: Serving Basis Integrity
    # =========================================================================

    def _validate_serving_basis_integrity(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule D: Serving basis integrity validation.

        D.1: If form_factor == "gummy":
             - basis_unit must normalize to "gummy" (not truncated)

        D.2: If canonical_serving_size_quantity is null:
             - Log warning with product_id and reason
        """
        violations = []

        serving_basis = product.get("serving_basis", {}) or {}
        # Enricher owns form factor at the product level. Keep the legacy
        # nested lookup only as a compatibility fallback.
        form_factor = str(
            product.get("form_factor_canonical")
            or product.get("form_factor")
            or serving_basis.get("form_factor")
            or ""
        ).lower()
        basis_unit = (serving_basis.get("basis_unit", "") or "").lower()
        canonical_qty = serving_basis.get("canonical_serving_size_quantity")

        # D.1: Gummy form_factor requires proper basis_unit
        if form_factor == "gummy":
            # Check for truncated variants like "gummy(ie" or incomplete parens
            is_truncated = (
                basis_unit.endswith("(") or
                basis_unit.endswith("(ie") or
                "(" in basis_unit and ")" not in basis_unit
            )

            is_valid_gummy_unit = basis_unit in self.GUMMY_UNIT_VARIANTS

            if is_truncated:
                violations.append(ContractViolation(
                    rule="D.1a",
                    rule_name="Serving Basis - gummy unit not truncated",
                    severity="error",
                    message=f"basis_unit '{basis_unit}' appears truncated for form_factor='gummy'",
                    product_id=product_id,
                    field_path="serving_basis.basis_unit",
                    expected="complete unit like 'gummy' or 'gummy(ies)'",
                    actual=basis_unit,
                    evidence={"form_factor": form_factor}
                ))
            elif basis_unit and not is_valid_gummy_unit:
                violations.append(ContractViolation(
                    rule="D.1b",
                    rule_name="Serving Basis - gummy unit normalized",
                    severity="warning",
                    message=f"basis_unit '{basis_unit}' may not match form_factor='gummy'",
                    product_id=product_id,
                    field_path="serving_basis.basis_unit",
                    expected=f"one of {self.GUMMY_UNIT_VARIANTS}",
                    actual=basis_unit,
                    evidence={"form_factor": form_factor}
                ))

        # D.2: canonical_serving_size_quantity should not be null
        if canonical_qty is None:
            # Determine the reason
            serving_sizes = product.get("servingSizes", []) or []
            reason = "unknown"

            if not serving_sizes:
                reason = "missing servingSizes array"
            elif all(not ss.get("servingSizeQuantity") for ss in serving_sizes):
                reason = "all servingSizeQuantity values are null/empty"
            else:
                reason = "parse failure or selection policy issue"

            violations.append(ContractViolation(
                rule="D.2",
                rule_name="Serving Basis - canonical quantity present",
                severity="warning",
                message=f"canonical_serving_size_quantity is null: {reason}",
                product_id=product_id,
                field_path="serving_basis.canonical_serving_size_quantity",
                expected="numeric value",
                actual=None,
                evidence={"reason": reason, "serving_sizes_count": len(serving_sizes)}
            ))

        return violations

    # =========================================================================
    # RULE E: Claims Consistency
    # =========================================================================

    def _validate_claims_consistency(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule E: Claims consistency validation.

        E.1: USP Verified cannot be score_eligible unless evidence_strength == "strong"
        E.2: If allergen_free claim has score_eligible=true, no allergen conflict can exist
        E.3: If batch_traceability is score_eligible, must have actionable evidence
        E.4: Organic scoring requires scope=product_level (not ingredient_level)
        E.5: Evidence objects must have valid rule_id from cert_claim_rules.json
        """
        violations = []

        certification_data = product.get("certification_data", {})
        compliance_data = product.get("compliance_data", {})
        organic_data = product.get("organic", {})

        # E.1: USP Verified strength validation
        evidence_based = certification_data.get("evidence_based", {})
        third_party_evidence = evidence_based.get("third_party_programs", []) or []

        for evidence in third_party_evidence:
            rule_id = evidence.get("rule_id", "")
            if "USP" in rule_id.upper() and "VERIFIED" in rule_id.upper():
                if evidence.get("score_eligible", False):
                    strength = evidence.get("evidence_strength", "")
                    if strength != "strong":
                        violations.append(ContractViolation(
                            rule="E.1",
                            rule_name="Claims Consistency - USP Verified strength",
                            severity="error",
                            message=f"USP Verified claim is score_eligible but evidence_strength is '{strength}' (must be 'strong')",
                            product_id=product_id,
                            field_path="certification_data.evidence_based.third_party_programs",
                            expected="evidence_strength='strong'",
                            actual=strength,
                            evidence={
                                "rule_id": rule_id,
                                "matched_text": evidence.get("matched_text"),
                                "score_eligible": evidence.get("score_eligible")
                            }
                        ))

        # E.2: Allergen-free claims cannot be score_eligible with allergen conflicts
        compliance_evidence = compliance_data.get("evidence_based", {})
        allergen_evidence = compliance_evidence.get("allergen_free_claims", []) or []

        for evidence in allergen_evidence:
            if evidence.get("score_eligible", False):
                conflicts = evidence.get("proximity_conflicts", [])
                if conflicts:
                    violations.append(ContractViolation(
                        rule="E.2",
                        rule_name="Claims Consistency - allergen conflict blocks scoring",
                        severity="error",
                        message=f"Allergen-free claim '{evidence.get('display_name')}' is score_eligible but has conflicts: {conflicts}",
                        product_id=product_id,
                        field_path="compliance_data.evidence_based.allergen_free_claims",
                        expected="score_eligible=false when proximity_conflicts exist",
                        actual=f"score_eligible=true with conflicts={conflicts}",
                        evidence={
                            "rule_id": evidence.get("rule_id"),
                            "matched_text": evidence.get("matched_text"),
                            "proximity_conflicts": conflicts
                        }
                    ))

        # E.3: Batch traceability with score_eligible must have actionable evidence
        batch_evidence = evidence_based.get("batch_traceability", []) or []
        actionable_keywords = ["available", "request", "download", "scan", "qr", "url", "website"]

        for evidence in batch_evidence:
            if evidence.get("score_eligible", False):
                evidence_strength = evidence.get("evidence_strength", "")
                matched_text = (evidence.get("matched_text", "") or "").lower()

                # Only weak evidence needs actionable keywords
                if evidence_strength == "weak":
                    has_actionable = any(kw in matched_text for kw in actionable_keywords)
                    if not has_actionable:
                        violations.append(ContractViolation(
                            rule="E.3",
                            rule_name="Claims Consistency - batch traceability actionable",
                            severity="warning",
                            message=f"Batch traceability claim with weak evidence is score_eligible without actionable keywords",
                            product_id=product_id,
                            field_path="certification_data.evidence_based.batch_traceability",
                            expected="actionable evidence (available, request, QR, etc.)",
                            actual=evidence.get("matched_text"),
                            evidence={
                                "rule_id": evidence.get("rule_id"),
                                "evidence_strength": evidence_strength
                            }
                        ))

        # E.4: Organic scoring requires product-level scope
        organic_evidence_based = organic_data.get("evidence_based", {})
        organic_evidence = organic_evidence_based.get("organic_certifications", []) or []

        for evidence in organic_evidence:
            if evidence.get("score_eligible", False):
                scope_violation = evidence.get("scope_violation", False)
                scope_rule = evidence.get("scope_rule", "")

                if scope_violation:
                    violations.append(ContractViolation(
                        rule="E.4",
                        rule_name="Claims Consistency - organic scope",
                        severity="error",
                        message=f"Organic claim is score_eligible but has scope_violation=true",
                        product_id=product_id,
                        field_path="organic.evidence_based.organic_certifications",
                        expected="scope_violation=false for scoring",
                        actual=f"scope_violation={scope_violation}, scope_rule={scope_rule}",
                        evidence={
                            "rule_id": evidence.get("rule_id"),
                            "source_field": evidence.get("source_field")
                        }
                    ))

        # E.5: All evidence objects must have valid rule_id
        all_evidence = (
            third_party_evidence +
            evidence_based.get("gmp_certifications", []) +
            batch_evidence +
            allergen_evidence +
            organic_evidence
        )

        for evidence in all_evidence:
            rule_id = evidence.get("rule_id", "")
            if not rule_id or rule_id == "UNKNOWN":
                violations.append(ContractViolation(
                    rule="E.5",
                    rule_name="Claims Consistency - valid rule_id",
                    severity="warning",
                    message=f"Evidence object missing valid rule_id",
                    product_id=product_id,
                    field_path="certification_data.evidence_based",
                    expected="valid rule_id from cert_claim_rules.json",
                    actual=rule_id or "(empty)",
                    evidence={
                        "display_name": evidence.get("display_name"),
                        "matched_text": evidence.get("matched_text")
                    }
                ))

        return violations

    # =========================================================================
    # RULE F: Provenance Integrity
    # =========================================================================

    def _validate_provenance_integrity(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule F: Provenance integrity validation.

        F.1: All matched ingredients must have raw_source_text (never null/empty after cleaning)
        F.2: All matched ingredients must have normalized_key (computed once, never regenerated)
        F.3: canonical_id monotonicity - items with canonical_id must maintain provenance chain
        """
        violations = []

        # Get all ingredients (active + inactive)
        active_ingredients = product.get("activeIngredients", []) or []
        inactive_ingredients = product.get("inactiveIngredients", []) or []
        all_ingredients = active_ingredients + inactive_ingredients

        # F.1 & F.2: Check provenance fields on ingredients
        for i, ing in enumerate(active_ingredients):
            if not ing:
                continue
            violations.extend(self._check_ingredient_provenance(
                ing, product_id, "activeIngredients", i
            ))

        for i, ing in enumerate(inactive_ingredients):
            if not ing:
                continue
            violations.extend(self._check_ingredient_provenance(
                ing, product_id, "inactiveIngredients", i
            ))

        violations.extend(self._validate_cleaner_iqd_contract(product, product_id))

        # F.3: Check canonical_id monotonicity in match_ledger entries
        # NOTE: Monotonicity only applies to core scoring domains (ingredients,
        # additives, allergens). Bonus/optional domains (manufacturer, delivery,
        # claims) may have null canonical_id as expected behavior.
        match_ledger = product.get("match_ledger", {})
        domains = match_ledger.get("domains", {})

        for domain_name, domain_data in domains.items():
            # Skip monotonicity check for optional domains
            if domain_name not in self.CANONICAL_ID_MONOTONICITY_DOMAINS:
                continue

            entries = domain_data.get("entries", []) or []
            for entry in entries:
                canonical_id = entry.get("canonical_id")
                decision = entry.get("decision", "")

                # If matched in a monotonicity domain, must have canonical_id
                if decision == "matched" and not canonical_id:
                    violations.append(ContractViolation(
                        rule="F.3",
                        rule_name="Provenance Integrity - canonical_id monotonicity",
                        severity="error",
                        message=f"Ledger entry in '{domain_name}' is 'matched' but has no canonical_id",
                        product_id=product_id,
                        field_path=f"match_ledger.domains.{domain_name}.entries",
                        expected="canonical_id present for matched entries in monotonicity domains",
                        actual=f"decision=matched, canonical_id={canonical_id}",
                        evidence={
                            "raw_source_text": entry.get("raw_source_text"),
                            "domain": domain_name,
                            "monotonicity_scope": list(self.CANONICAL_ID_MONOTONICITY_DOMAINS)
                        }
                    ))

        return violations

    def _validate_cleaner_iqd_contract(
        self, product: Dict, product_id: str
    ) -> List[ContractViolation]:
        """Validate cleaner-owned row role and IQD scorable eligibility."""
        violations = []
        iqd = product.get("ingredient_quality_data") or {}
        if not isinstance(iqd, dict):
            return violations

        all_rows = iqd.get("ingredients") or []
        if isinstance(all_rows, list):
            for i, row in enumerate(all_rows):
                if not isinstance(row, dict):
                    continue
                violations.extend(
                    self._check_cleaner_contract_fields(
                        row, product_id, f"ingredient_quality_data.ingredients[{i}]"
                    )
                )

        scorable_rows = iqd.get("ingredients_scorable") or []
        if not isinstance(scorable_rows, list):
            return violations

        for i, row in enumerate(scorable_rows):
            if not isinstance(row, dict):
                continue
            field_path = f"ingredient_quality_data.ingredients_scorable[{i}]"
            violations.extend(
                self._check_cleaner_contract_fields(row, product_id, field_path)
            )

            role = self._norm_contract_value(row.get("cleaner_row_role"))
            source_section = self._norm_contract_value(row.get("source_section"))
            eligible = row.get("score_eligible_by_cleaner")
            role_classification = self._norm_contract_value(row.get("role_classification"))

            if eligible is not True:
                violations.append(ContractViolation(
                    rule="F.4",
                    rule_name="Cleaner IQD Contract - scorable eligibility",
                    severity="error",
                    message="IQD scorable row is not cleaner-eligible",
                    product_id=product_id,
                    field_path=f"{field_path}.score_eligible_by_cleaner",
                    expected=True,
                    actual=eligible,
                    evidence={
                        "name": row.get("name"),
                        "cleaner_row_role": row.get("cleaner_row_role"),
                    },
                ))

            if role in self.CLEANER_NON_SCORABLE_ROLES:
                violations.append(ContractViolation(
                    rule="F.5",
                    rule_name="Cleaner IQD Contract - non-scorable role excluded",
                    severity="error",
                    message=f"Non-scorable cleaner role '{role}' appears in IQD scorable rows",
                    product_id=product_id,
                    field_path=f"{field_path}.cleaner_row_role",
                    expected=f"one of {sorted(self.CLEANER_SCORABLE_ROLES)}",
                    actual=role,
                    evidence={"name": row.get("name")},
                ))

            if source_section == "inactive" and role != "active_misfiled_in_inactive":
                violations.append(ContractViolation(
                    rule="F.6",
                    rule_name="Cleaner IQD Contract - inactive promotion gate",
                    severity="error",
                    message="Inactive-source row appears in IQD scorable rows without cleaner promotion role",
                    product_id=product_id,
                    field_path=f"{field_path}.source_section",
                    expected="active source or cleaner_row_role=active_misfiled_in_inactive",
                    actual=source_section,
                    evidence={
                        "name": row.get("name"),
                        "cleaner_row_role": row.get("cleaner_row_role"),
                    },
                ))

            if row.get("recognized_non_scorable") or role_classification == "recognized_non_scorable":
                violations.append(ContractViolation(
                    rule="F.10",
                    rule_name="Enrichment IQD Contract - recognized rows excluded from scorable",
                    severity="error",
                    message="Recognized-but-non-scorable row appears in ingredients_scorable",
                    product_id=product_id,
                    field_path=field_path,
                    expected="ingredients_recognized_non_scorable or ingredients_skipped",
                    actual=role_classification or row.get("recognized_non_scorable"),
                    evidence={"name": row.get("name")},
                ))

            if row.get("scoreable_identity") is not True:
                violations.append(ContractViolation(
                    rule="F.11",
                    rule_name="Enrichment IQD Contract - scoreable identity required",
                    severity="error",
                    message="IQD scorable row lacks scoreable_identity=true",
                    product_id=product_id,
                    field_path=f"{field_path}.scoreable_identity",
                    expected=True,
                    actual=row.get("scoreable_identity"),
                    evidence={"name": row.get("name")},
                ))

            if role_classification != "active_scorable":
                violations.append(ContractViolation(
                    rule="F.12",
                    rule_name="Enrichment IQD Contract - active_scorable role required",
                    severity="error",
                    message="IQD scorable row is not classified active_scorable",
                    product_id=product_id,
                    field_path=f"{field_path}.role_classification",
                    expected="active_scorable",
                    actual=row.get("role_classification"),
                    evidence={"name": row.get("name")},
                ))

            if not self._has_iqd_dose_evidence(row):
                violations.append(ContractViolation(
                    rule="F.13",
                    rule_name="Enrichment IQD Contract - dose evidence required",
                    severity="error",
                    message="IQD scorable row lacks usable dose evidence",
                    product_id=product_id,
                    field_path=field_path,
                    expected=f"dose_class in {sorted(self.VALID_IQD_DOSE_CLASSES)} or positive quantity/activity",
                    actual={
                        "dose_class": row.get("dose_class"),
                        "quantity": row.get("quantity"),
                        "unit": row.get("unit"),
                    },
                    evidence={"name": row.get("name")},
                ))

            if self._is_fallback_derived_row(row) and (
                not row.get("fallback_class") or not row.get("fallback_reason")
            ):
                violations.append(ContractViolation(
                    rule="F.14",
                    rule_name="Enrichment IQD Contract - fallback diagnostics required",
                    severity="error",
                    message="Fallback-derived IQD decision lacks fallback_class/fallback_reason",
                    product_id=product_id,
                    field_path=field_path,
                    expected=["fallback_class", "fallback_reason"],
                    actual={
                        "fallback_class": row.get("fallback_class"),
                        "fallback_reason": row.get("fallback_reason"),
                    },
                    evidence={"name": row.get("name")},
                ))

        return violations

    def _check_cleaner_contract_fields(
        self, row: Dict, product_id: str, field_path: str
    ) -> List[ContractViolation]:
        violations = []
        required_fields = (
            "raw_source_path",
            "source_section",
            "cleaner_row_role",
            "score_eligible_by_cleaner",
        )
        missing = [
            field
            for field in required_fields
            if field not in row or row.get(field) in (None, "")
        ]
        if missing:
            violations.append(ContractViolation(
                rule="F.7",
                rule_name="Cleaner IQD Contract - required provenance",
                severity="error",
                message=f"IQD row missing cleaner provenance fields: {missing}",
                product_id=product_id,
                field_path=field_path,
                expected=list(required_fields),
                actual={field: row.get(field) for field in required_fields},
                evidence={"name": row.get("name")},
            ))
            return violations

        source_section = self._norm_contract_value(row.get("source_section"))
        if source_section not in self.CLEANER_ALLOWED_SOURCE_SECTIONS:
            violations.append(ContractViolation(
                rule="F.8",
                rule_name="Cleaner IQD Contract - source_section enum",
                severity="error",
                message=f"Invalid cleaner source_section '{source_section}'",
                product_id=product_id,
                field_path=f"{field_path}.source_section",
                expected=sorted(self.CLEANER_ALLOWED_SOURCE_SECTIONS),
                actual=row.get("source_section"),
                evidence={"name": row.get("name")},
            ))

        role = self._norm_contract_value(row.get("cleaner_row_role"))
        allowed_roles = self.CLEANER_NON_SCORABLE_ROLES | self.CLEANER_SCORABLE_ROLES
        if role not in allowed_roles:
            violations.append(ContractViolation(
                rule="F.9",
                rule_name="Cleaner IQD Contract - cleaner_row_role enum",
                severity="error",
                message=f"Invalid cleaner_row_role '{role}'",
                product_id=product_id,
                field_path=f"{field_path}.cleaner_row_role",
                expected=sorted(allowed_roles),
                actual=row.get("cleaner_row_role"),
                evidence={"name": row.get("name")},
            ))

        return violations

    @staticmethod
    def _norm_contract_value(value: Any) -> str:
        return str(value or "").strip().lower()

    def _validate_scoring_classification_contract(
        self,
        product: Dict,
        product_id: str,
    ) -> List[ContractViolation]:
        """Validate native ScoringClassification v1 when emitted.

        Missing classification is allowed during compatibility migration.
        Release/P5 gates can require native classification once fresh
        enrichment artifacts have been generated.
        """
        classification = product.get("product_scoring_classification")
        if classification is None:
            return []
        if not isinstance(classification, dict):
            return [ContractViolation(
                rule="J.1",
                rule_name="Scoring Classification Contract - object shape",
                severity="error",
                message="product_scoring_classification must be an object when present",
                product_id=product_id,
                field_path="product_scoring_classification",
                expected="dict",
                actual=type(classification).__name__,
            )]

        violations: List[ContractViolation] = []
        missing = sorted(
            field for field in self.REQUIRED_SCORING_CLASSIFICATION_FIELDS
            if field not in classification
        )
        if missing:
            violations.append(ContractViolation(
                rule="J.2",
                rule_name="Scoring Classification Contract - required fields",
                severity="error",
                message=f"product_scoring_classification missing fields: {missing}",
                product_id=product_id,
                field_path="product_scoring_classification",
                expected=sorted(self.REQUIRED_SCORING_CLASSIFICATION_FIELDS),
                actual=sorted(classification.keys()),
            ))

        route = self._norm_contract_value(classification.get("route_module"))
        if route not in self.VALID_SCORING_CLASSIFICATION_ROUTES:
            violations.append(ContractViolation(
                rule="J.3",
                rule_name="Scoring Classification Contract - route enum",
                severity="error",
                message=f"Invalid scoring route '{route}'",
                product_id=product_id,
                field_path="product_scoring_classification.route_module",
                expected=sorted(self.VALID_SCORING_CLASSIFICATION_ROUTES),
                actual=classification.get("route_module"),
            ))

        origin = self._norm_contract_value(classification.get("classification_origin"))
        if origin not in self.VALID_SCORING_CLASSIFICATION_ORIGINS:
            violations.append(ContractViolation(
                rule="J.4",
                rule_name="Scoring Classification Contract - origin enum",
                severity="error",
                message=f"Invalid scoring classification origin '{origin}'",
                product_id=product_id,
                field_path="product_scoring_classification.classification_origin",
                expected=sorted(self.VALID_SCORING_CLASSIFICATION_ORIGINS),
                actual=classification.get("classification_origin"),
            ))

        confidence = self._norm_contract_value(classification.get("route_confidence"))
        if confidence not in self.VALID_SCORING_ROUTE_CONFIDENCE:
            violations.append(ContractViolation(
                rule="J.5",
                rule_name="Scoring Classification Contract - confidence enum",
                severity="error",
                message=f"Invalid route confidence '{confidence}'",
                product_id=product_id,
                field_path="product_scoring_classification.route_confidence",
                expected=sorted(self.VALID_SCORING_ROUTE_CONFIDENCE),
                actual=classification.get("route_confidence"),
            ))

        if classification.get("classification_failed") is True and route != "generic":
            violations.append(ContractViolation(
                rule="J.6",
                rule_name="Scoring Classification Contract - failed route default",
                severity="error",
                message="classification_failed=true must route generic",
                product_id=product_id,
                field_path="product_scoring_classification.route_module",
                expected="generic",
                actual=classification.get("route_module"),
            ))

        ingredients = classification.get("ingredients")
        if not isinstance(ingredients, list):
            violations.append(ContractViolation(
                rule="J.7",
                rule_name="Scoring Classification Contract - ingredient list",
                severity="error",
                message="classification ingredients must be a list",
                product_id=product_id,
                field_path="product_scoring_classification.ingredients",
                expected="list",
                actual=type(ingredients).__name__,
            ))
            return violations

        for index, ingredient in enumerate(ingredients):
            if not isinstance(ingredient, dict):
                violations.append(ContractViolation(
                    rule="J.8",
                    rule_name="Scoring Classification Contract - ingredient object",
                    severity="error",
                    message="classification ingredient entries must be objects",
                    product_id=product_id,
                    field_path=f"product_scoring_classification.ingredients[{index}]",
                    expected="dict",
                    actual=type(ingredient).__name__,
                ))
                continue
            for field in ("ingredient_domain", "botanical_source", "role", "profile_eligibility"):
                if field not in ingredient:
                    violations.append(ContractViolation(
                        rule="J.9",
                        rule_name="Scoring Classification Contract - ingredient fields",
                        severity="error",
                        message=f"classification ingredient missing {field}",
                        product_id=product_id,
                        field_path=f"product_scoring_classification.ingredients[{index}]",
                        expected=field,
                        actual=sorted(ingredient.keys()),
                    ))

        return violations

    def _has_iqd_dose_evidence(self, row: Dict) -> bool:
        dose_class = self._norm_contract_value(row.get("dose_class"))
        if dose_class in self.VALID_IQD_DOSE_CLASSES:
            return True
        if row.get("activity_quantity") not in (None, "") and row.get("activity_unit"):
            return True
        if row.get("has_dose") is True:
            return True
        quantity = row.get("quantity")
        unit = self._norm_contract_value(row.get("unit"))
        if not unit:
            return False
        try:
            return float(str(quantity).replace(",", "")) > 0
        except (TypeError, ValueError):
            return False

    def _is_fallback_derived_row(self, row: Dict) -> bool:
        reason = self._norm_contract_value(row.get("identity_decision_reason"))
        return bool(
            row.get("fallback_class")
            or row.get("fallback_reason")
            or row.get("recognized_non_scorable")
            or reason in {
                "form_unmapped_fallback",
                "proprietary_blend_member",
                "source_descriptor_child_row",
                "recognized_non_scorable",
                "no_dose_evidence",
            }
        )

    def _check_ingredient_provenance(
        self, ing: Dict, product_id: str, array_name: str, index: int
    ) -> List[ContractViolation]:
        """Helper to check provenance fields on an ingredient."""
        violations = []
        ing_name = ing.get("name", ing.get("ingredient", "unknown"))

        # F.1: raw_source_text must be present
        raw_source_text = ing.get("raw_source_text")
        if not raw_source_text:
            # Only flag if this is a matched ingredient (has canonical info)
            has_canonical = (
                ing.get("canonical_id") or
                ing.get("db_id") or
                ing.get("ingredient_id")
            )
            if has_canonical:
                violations.append(ContractViolation(
                    rule="F.1",
                    rule_name="Provenance Integrity - raw_source_text required",
                    severity="error",
                    message=f"Matched ingredient '{ing_name}' missing raw_source_text",
                    product_id=product_id,
                    field_path=f"{array_name}[{index}].raw_source_text",
                    expected="non-empty string",
                    actual=raw_source_text,
                    evidence={
                        "ingredient_name": ing_name,
                        "canonical_id": ing.get("canonical_id") or ing.get("db_id")
                    }
                ))

        # F.2: normalized_key must be present for matched ingredients
        normalized_key = ing.get("normalized_key")
        if not normalized_key:
            has_canonical = (
                ing.get("canonical_id") or
                ing.get("db_id") or
                ing.get("ingredient_id")
            )
            if has_canonical:
                violations.append(ContractViolation(
                    rule="F.2",
                    rule_name="Provenance Integrity - normalized_key required",
                    severity="error",
                    message=f"Matched ingredient '{ing_name}' missing normalized_key",
                    product_id=product_id,
                    field_path=f"{array_name}[{index}].normalized_key",
                    expected="non-empty string",
                    actual=normalized_key,
                    evidence={
                        "ingredient_name": ing_name,
                        "canonical_id": ing.get("canonical_id") or ing.get("db_id")
                    }
                ))

        return violations

    # =========================================================================
    # RULE G: Match Ledger Consistency
    # =========================================================================

    def _validate_match_ledger_consistency(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule G: Match ledger consistency validation.

        G.1: match_ledger must be present in enriched products
        G.2: Ledger summary totals must equal sum of domain totals
        G.3: unmatched_* lists must match ledger unmatched counts
        G.4: coverage_percent must be mathematically correct
        """
        violations = []

        match_ledger = product.get("match_ledger")

        # G.1: match_ledger must be present
        if match_ledger is None:
            violations.append(ContractViolation(
                rule="G.1",
                rule_name="Match Ledger Consistency - ledger present",
                severity="warning",
                message="match_ledger not present in enriched product",
                product_id=product_id,
                field_path="match_ledger",
                expected="match_ledger object",
                actual=None
            ))
            return violations  # Can't validate further without ledger

        if not isinstance(match_ledger, dict):
            violations.append(ContractViolation(
                rule="G.1",
                rule_name="Match Ledger Consistency - ledger is object",
                severity="error",
                message=f"match_ledger is not a dictionary: {type(match_ledger).__name__}",
                product_id=product_id,
                field_path="match_ledger",
                expected="dict",
                actual=type(match_ledger).__name__
            ))
            return violations

        domains = match_ledger.get("domains", {})
        summary = match_ledger.get("summary", {})

        # G.2: Summary totals must equal sum of domain totals
        expected_total = 0
        expected_matched = 0
        domain_breakdown = {}

        for domain_name, domain_data in domains.items():
            total_raw = domain_data.get("total_raw", 0) or 0
            matched = domain_data.get("matched", 0) or 0
            expected_total += total_raw
            expected_matched += matched
            domain_breakdown[domain_name] = {"total": total_raw, "matched": matched}

        summary_total = summary.get("total_entities", 0)
        summary_matched = summary.get("total_matched", 0)

        if expected_total != summary_total:
            violations.append(ContractViolation(
                rule="G.2a",
                rule_name="Match Ledger Consistency - total entities",
                severity="error",
                message=f"summary.total_entities ({summary_total}) != sum of domain totals ({expected_total})",
                product_id=product_id,
                field_path="match_ledger.summary.total_entities",
                expected=expected_total,
                actual=summary_total,
                evidence={"domain_breakdown": domain_breakdown}
            ))

        if expected_matched != summary_matched:
            violations.append(ContractViolation(
                rule="G.2b",
                rule_name="Match Ledger Consistency - matched entities",
                severity="error",
                message=f"summary.total_matched ({summary_matched}) != sum of domain matched ({expected_matched})",
                product_id=product_id,
                field_path="match_ledger.summary.total_matched",
                expected=expected_matched,
                actual=summary_matched,
                evidence={"domain_breakdown": domain_breakdown}
            ))

        # G.3: unmatched_* lists must match ledger unmatched counts
        unmatched_lists = {
            "ingredients": product.get("unmatched_ingredients", []) or [],
            "additives": product.get("unmatched_additives", []) or [],
            "allergens": product.get("unmatched_allergens", []) or []
        }

        for domain_name, unmatched_list in unmatched_lists.items():
            if domain_name not in domains:
                continue

            domain_data = domains[domain_name]
            ledger_unmatched = domain_data.get("unmatched", 0) or 0
            list_count = len(unmatched_list)

            if ledger_unmatched != list_count:
                violations.append(ContractViolation(
                    rule="G.3",
                    rule_name="Match Ledger Consistency - unmatched list count",
                    severity="error",
                    message=f"unmatched_{domain_name} list ({list_count}) != ledger unmatched count ({ledger_unmatched})",
                    product_id=product_id,
                    field_path=f"unmatched_{domain_name}",
                    expected=ledger_unmatched,
                    actual=list_count,
                    evidence={
                        "domain": domain_name,
                        "ledger_unmatched": ledger_unmatched
                    }
                ))

        # G.4: coverage_percent must be mathematically correct
        #
        # Legacy semantics:
        #   coverage_percent = total_matched / total_entities * 100
        #
        # Current hardened semantics:
        #   coverage_percent = total_matched / scorable_total * 100
        #
        # Accept both, preferring scorable_total when provided.
        reported_coverage = summary.get("coverage_percent", 0)
        scorable_total = summary.get("scorable_total", 0) or 0
        if scorable_total > 0:
            expected_coverage = round((summary_matched / scorable_total) * 100, 2)
            tolerance = 0.11
            evidence = {
                "coverage_mode": "scorable_total",
                "total_matched": summary_matched,
                "scorable_total": scorable_total,
            }
        elif summary_total > 0:
            expected_coverage = round((summary_matched / summary_total) * 100, 1)
            tolerance = 0.1
            evidence = {
                "coverage_mode": "total_entities",
                "total_matched": summary_matched,
                "total_entities": summary_total,
            }
        else:
            expected_coverage = None
            tolerance = None
            evidence = {}

        if expected_coverage is not None and abs(reported_coverage - expected_coverage) > tolerance:
            violations.append(ContractViolation(
                rule="G.4",
                rule_name="Match Ledger Consistency - coverage percent",
                severity="error",
                message=f"coverage_percent ({reported_coverage}) != calculated ({expected_coverage})",
                product_id=product_id,
                field_path="match_ledger.summary.coverage_percent",
                expected=expected_coverage,
                actual=reported_coverage,
                evidence=evidence
            ))

        return violations

    # =========================================================================
    # RULE H: Display Ledger Contract
    # =========================================================================

    def _validate_display_ledger_contract(self, product: Dict, product_id: str) -> List[ContractViolation]:
        """
        Rule H: display_ingredients is optional but must be valid when present.

        H.1: Each display row must include the required display-ledger fields.
        H.2: mapped_to, when present, must include standard_name and source_section.
        H.3: Form and identity states use their exact closed enums.
        H.4: Disclosed source form text cannot be marked not_disclosed.
        H.5: Score-included conflicts and active missing labels block release.
        H.6: needs_review rows cannot carry dose, form-quality, or safety claims.
        H.7: Source omissions require evidence with a closed omission reason.
        H.8: Ledger fields require label_ledger_audit; completeness is
             unavailable for unsupported source structures and must be 100%
             for supported archetypes.
        H.9: Identity-blocked products cannot publish a v4 quality score.
        """
        violations = []
        identity_blocking_paths = []
        display_rows = product.get("display_ingredients")
        ledger_fields_present = any(
            field_name in product
            for field_name in (
                "display_ingredients",
                "label_ledger_omissions",
                "label_source_rows",
            )
        )

        if not ledger_fields_present and "label_ledger_audit" not in product:
            return violations

        if ledger_fields_present and product.get("label_ledger_audit") is None:
            violations.append(ContractViolation(
                rule="H.8",
                rule_name="Label Ledger Audit Contract - required audit",
                severity="error",
                message=(
                    "label_ledger_audit is required when display_ingredients, "
                    "label_ledger_omissions, or label_source_rows is present"
                ),
                product_id=product_id,
                field_path="label_ledger_audit",
                expected="label-ledger audit object",
                actual=product.get("label_ledger_audit"),
                evidence={"audit_code": "missing_label_ledger_audit"},
            ))

        if display_rows is None:
            display_rows = []

        if not isinstance(display_rows, list):
            violations.append(ContractViolation(
                rule="H.1",
                rule_name="Display Ledger Contract - structure",
                severity="error",
                message="display_ingredients must be a list when present",
                product_id=product_id,
                field_path="display_ingredients",
                expected="list",
                actual=type(display_rows).__name__,
            ))
            return violations

        for index, row in enumerate(display_rows):
            field_path = f"display_ingredients[{index}]"
            if not isinstance(row, dict):
                violations.append(ContractViolation(
                    rule="H.1",
                    rule_name="Display Ledger Contract - structure",
                    severity="error",
                    message=f"Display ledger row at index {index} must be an object",
                    product_id=product_id,
                    field_path=field_path,
                    expected="object",
                    actual=type(row).__name__,
                ))
                continue

            missing_fields = [
                field for field in self.DISPLAY_LEDGER_REQUIRED_FIELDS
                if field not in row
            ]
            if missing_fields:
                violations.append(ContractViolation(
                    rule="H.1",
                    rule_name="Display Ledger Contract - required fields",
                    severity="error",
                    message=f"Display ledger row missing required fields: {', '.join(sorted(missing_fields))}",
                    product_id=product_id,
                    field_path=field_path,
                    expected=sorted(self.DISPLAY_LEDGER_REQUIRED_FIELDS),
                    actual=sorted(row.keys()),
                    evidence={"raw_source_text": row.get("raw_source_text")},
                ))
                continue

            if row.get("source_section") not in self.DISPLAY_LEDGER_ALLOWED_SOURCE_SECTIONS:
                violations.append(ContractViolation(
                    rule="H.1",
                    rule_name="Display Ledger Contract - source section",
                    severity="error",
                    message=f"Display ledger row has invalid source_section: {row.get('source_section')}",
                    product_id=product_id,
                    field_path=f"{field_path}.source_section",
                    expected=sorted(self.DISPLAY_LEDGER_ALLOWED_SOURCE_SECTIONS),
                    actual=row.get("source_section"),
                    evidence={"raw_source_text": row.get("raw_source_text")},
                ))

            form_state = row.get("form_display_state")
            if (
                "form_display_state" in row
                and form_state not in self.DISPLAY_LEDGER_FORM_STATES
            ):
                violations.append(ContractViolation(
                    rule="H.3",
                    rule_name="Display Ledger Contract - form state enum",
                    severity="error",
                    message=(
                        "form_display_state must be one of the closed label-ledger "
                        f"states; got {form_state!r}"
                    ),
                    product_id=product_id,
                    field_path=f"{field_path}.form_display_state",
                    expected=sorted(self.DISPLAY_LEDGER_FORM_STATES),
                    actual=form_state,
                    evidence={
                        "audit_code": "invalid_form_display_state",
                        "raw_source_path": row.get("raw_source_path"),
                    },
                ))

            identity_state = row.get("identity_integrity_state")
            if (
                "identity_integrity_state" in row
                and identity_state not in self.DISPLAY_LEDGER_IDENTITY_STATES
            ):
                violations.append(ContractViolation(
                    rule="H.3",
                    rule_name="Display Ledger Contract - identity state enum",
                    severity="error",
                    message=(
                        "identity_integrity_state must be one of the closed "
                        f"label-ledger states; got {identity_state!r}"
                    ),
                    product_id=product_id,
                    field_path=f"{field_path}.identity_integrity_state",
                    expected=sorted(self.DISPLAY_LEDGER_IDENTITY_STATES),
                    actual=identity_state,
                    evidence={
                        "audit_code": "invalid_identity_integrity_state",
                        "raw_source_path": row.get("raw_source_path"),
                    },
                ))

            disclosed_form = self._first_nonempty_string(
                row.get("label_display_form"),
                row.get("source_label_form"),
            )
            if disclosed_form and form_state == "not_disclosed":
                violations.append(ContractViolation(
                    rule="H.4",
                    rule_name="Display Ledger Contract - form disclosure truth",
                    severity="error",
                    message=(
                        "A source-label form is present but form_display_state is "
                        "not_disclosed"
                    ),
                    product_id=product_id,
                    field_path=f"{field_path}.form_display_state",
                    expected="assessed, listed_not_assessed, or needs_review",
                    actual=form_state,
                    evidence={
                        "audit_code": "disclosed_form_marked_not_disclosed",
                        "disclosed_form": disclosed_form,
                        "raw_source_path": row.get("raw_source_path"),
                    },
                ))

            score_included_conflict = (
                row.get("score_included") is True
                and identity_state == "identity_conflict"
            )
            active_missing_label = (
                row.get("source_section") in self.DISPLAY_LEDGER_ACTIVE_SECTIONS
                and identity_state == "missing_display_label"
            )
            if score_included_conflict:
                identity_blocking_paths.append(field_path)
                violations.append(ContractViolation(
                    rule="H.5",
                    rule_name="Display Ledger Contract - score identity integrity",
                    severity="error",
                    message=(
                        "A score-included row cannot carry "
                        "identity_integrity_state=identity_conflict"
                    ),
                    product_id=product_id,
                    field_path=f"{field_path}.identity_integrity_state",
                    expected="clean, repaired, or taxonomy_only",
                    actual=identity_state,
                    evidence={
                        "audit_code": "score_included_identity_conflict",
                        "raw_source_path": row.get("raw_source_path"),
                    },
                ))
            if active_missing_label:
                identity_blocking_paths.append(field_path)
                violations.append(ContractViolation(
                    rule="H.5",
                    rule_name="Display Ledger Contract - active display identity",
                    severity="error",
                    message=(
                        "An active label row cannot carry "
                        "identity_integrity_state=missing_display_label"
                    ),
                    product_id=product_id,
                    field_path=f"{field_path}.identity_integrity_state",
                    expected="a resolved label display identity",
                    actual=identity_state,
                    evidence={
                        "audit_code": "active_missing_display_label",
                        "raw_source_path": row.get("raw_source_path"),
                    },
                ))

            if (
                form_state == "needs_review"
                or row.get("display_disposition") == "needs_review"
            ):
                for claim_path in self.NEEDS_REVIEW_CLAIM_PATHS:
                    present, claim_value = self._claim_value(row, claim_path)
                    if not present:
                        continue
                    dotted_path = ".".join(claim_path)
                    violations.append(ContractViolation(
                        rule="H.6",
                        rule_name="Display Ledger Contract - review claim suppression",
                        severity="error",
                        message=(
                            "needs_review row cannot ship a dose, form-quality, "
                            f"or safety claim at {dotted_path}"
                        ),
                        product_id=product_id,
                        field_path=f"{field_path}.{dotted_path}",
                        expected="claim absent while row needs review",
                        actual=claim_value,
                        evidence={
                            "audit_code": f"needs_review_claim_present:{dotted_path}",
                            "raw_source_path": row.get("raw_source_path"),
                        },
                    ))

            mapped_to = row.get("mapped_to")
            if mapped_to is None:
                continue

            if not isinstance(mapped_to, dict):
                violations.append(ContractViolation(
                    rule="H.2",
                    rule_name="Display Ledger Contract - mapped_to structure",
                    severity="error",
                    message="Display ledger mapped_to must be an object when present",
                    product_id=product_id,
                    field_path=f"{field_path}.mapped_to",
                    expected="object",
                    actual=type(mapped_to).__name__,
                    evidence={"raw_source_text": row.get("raw_source_text")},
                ))
                continue

            if not mapped_to.get("standard_name"):
                violations.append(ContractViolation(
                    rule="H.2",
                    rule_name="Display Ledger Contract - mapped_to fields",
                    severity="error",
                    message="Display ledger mapped_to missing standard_name",
                    product_id=product_id,
                    field_path=f"{field_path}.mapped_to.standard_name",
                    expected="non-empty string",
                    actual=mapped_to.get("standard_name"),
                    evidence={"raw_source_text": row.get("raw_source_text")},
                ))

            if not mapped_to.get("source_section"):
                violations.append(ContractViolation(
                    rule="H.2",
                    rule_name="Display Ledger Contract - mapped_to fields",
                    severity="error",
                    message="Display ledger mapped_to missing source_section",
                    product_id=product_id,
                    field_path=f"{field_path}.mapped_to.source_section",
                    expected="non-empty string",
                    actual=mapped_to.get("source_section"),
                    evidence={"raw_source_text": row.get("raw_source_text")},
                ))

        if identity_blocking_paths and self._score_is_published(product):
            violations.append(ContractViolation(
                rule="H.9",
                rule_name="Display Ledger Contract - score publication",
                severity="error",
                message=(
                    "quality_score_v4_100 cannot be published while label-ledger "
                    "identity integrity is blocked"
                ),
                product_id=product_id,
                field_path="quality_score_status",
                expected="not_scored or suppressed_safety with no published score",
                actual={
                    "quality_score_status": product.get("quality_score_status"),
                    "quality_score_v4_100": product.get("quality_score_v4_100"),
                },
                evidence={
                    "audit_code": "score_publication_blocked_by_identity_integrity",
                    "blocking_rows": identity_blocking_paths,
                },
            ))

        violations.extend(
            self._validate_label_ledger_omissions(
                product,
                product_id,
                display_rows,
            )
        )
        violations.extend(self._validate_label_ledger_audit(product, product_id))
        return violations

    def _validate_label_ledger_omissions(
        self,
        product: Dict,
        product_id: str,
        display_rows: List[Dict],
    ) -> List[ContractViolation]:
        violations = []
        omissions_value = product.get("label_ledger_omissions", [])
        if not isinstance(omissions_value, list):
            return [ContractViolation(
                rule="H.7",
                rule_name="Label Ledger Omission Contract - structure",
                severity="error",
                message="label_ledger_omissions must be a list when present",
                product_id=product_id,
                field_path="label_ledger_omissions",
                expected="list",
                actual=type(omissions_value).__name__,
                evidence={"audit_code": "invalid_label_ledger_omissions"},
            )]

        omission_paths = set()
        omission_path_counts = {}
        omission_reasons = {}
        unsupported_omission = False
        for index, omission in enumerate(omissions_value):
            field_path = f"label_ledger_omissions[{index}]"
            if not isinstance(omission, dict):
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Ledger Omission Contract - structure",
                    severity="error",
                    message=f"Label-ledger omission at index {index} must be an object",
                    product_id=product_id,
                    field_path=field_path,
                    expected="object",
                    actual=type(omission).__name__,
                    evidence={"audit_code": "invalid_label_ledger_omission"},
                ))
                continue

            source_path = self._nonempty_string(omission.get("raw_source_path"))
            reason = omission.get("omission_reason")
            missing_fields = [
                key
                for key in ("raw_source_path", "raw_source_text", "omission_reason")
                if key not in omission
            ]
            if missing_fields or not source_path:
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Ledger Omission Contract - required evidence",
                    severity="error",
                    message=(
                        "Label-ledger omission requires raw_source_path, "
                        "raw_source_text, and omission_reason"
                    ),
                    product_id=product_id,
                    field_path=field_path,
                    expected=[
                        "raw_source_path",
                        "raw_source_text",
                        "omission_reason",
                    ],
                    actual=sorted(omission.keys()),
                    evidence={"audit_code": "invalid_label_ledger_omission"},
                ))
            if source_path:
                omission_paths.add(source_path)
                omission_path_counts[source_path] = (
                    omission_path_counts.get(source_path, 0) + 1
                )
                omission_reasons.setdefault(source_path, set()).add(reason)
            if reason not in self.LABEL_LEDGER_OMISSION_REASONS:
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Ledger Omission Contract - reason enum",
                    severity="error",
                    message=(
                        "omission_reason must be one of the exact closed-set "
                        f"values; got {reason!r}"
                    ),
                    product_id=product_id,
                    field_path=f"{field_path}.omission_reason",
                    expected=sorted(self.LABEL_LEDGER_OMISSION_REASONS),
                    actual=reason,
                    evidence={
                        "audit_code": "invalid_label_ledger_omission_reason",
                        "raw_source_path": source_path,
                    },
                ))
            elif reason == "unsupported_source_structure":
                unsupported_omission = True

        for source_path, count in omission_path_counts.items():
            if count <= 1:
                continue
            violations.append(ContractViolation(
                rule="H.7",
                rule_name="Label Ledger Omission Contract - unique path",
                severity="error",
                message=(
                    "A canonical source path may appear only once in "
                    "label_ledger_omissions"
                ),
                product_id=product_id,
                field_path="label_ledger_omissions",
                expected="unique raw_source_path values",
                actual=source_path,
                evidence={
                    "audit_code": "duplicate_omission_source_path",
                    "raw_source_path": source_path,
                    "occurrences": count,
                },
            ))

        display_path_counts = {}
        folded_path_counts = {}
        for row_index, row in enumerate(display_rows):
            if not isinstance(row, dict):
                continue
            source_path = self._nonempty_string(row.get("raw_source_path"))
            if source_path:
                display_path_counts[source_path] = (
                    display_path_counts.get(source_path, 0) + 1
                )
            folded_components = row.get("folded_label_components", [])
            if folded_components is None:
                folded_components = []
            if not isinstance(folded_components, list):
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Display Ledger Contract - folded components",
                    severity="error",
                    message="folded_label_components must be a list when present",
                    product_id=product_id,
                    field_path=(
                        f"display_ingredients[{row_index}].folded_label_components"
                    ),
                    expected="list",
                    actual=type(folded_components).__name__,
                    evidence={"audit_code": "invalid_folded_label_components"},
                ))
                continue
            for folded_index, component in enumerate(folded_components):
                component_path = (
                    self._nonempty_string(component.get("raw_source_path"))
                    if isinstance(component, dict)
                    else ""
                )
                if not component_path:
                    violations.append(ContractViolation(
                        rule="H.7",
                        rule_name="Display Ledger Contract - folded source path",
                        severity="error",
                        message=(
                            "Each folded label component requires a non-empty "
                            "raw_source_path"
                        ),
                        product_id=product_id,
                        field_path=(
                            f"display_ingredients[{row_index}]."
                            f"folded_label_components[{folded_index}]"
                        ),
                        expected="non-empty raw_source_path",
                        actual=component,
                        evidence={"audit_code": "invalid_folded_source_path"},
                    ))
                    continue
                folded_path_counts[component_path] = (
                    folded_path_counts.get(component_path, 0) + 1
                )

        for source_path, count in display_path_counts.items():
            if count <= 1:
                continue
            violations.append(ContractViolation(
                rule="H.7",
                rule_name="Display Ledger Contract - unique source path",
                severity="error",
                message=(
                    "A canonical source path may resolve to only one primary "
                    "display row"
                ),
                product_id=product_id,
                field_path="display_ingredients",
                expected="unique raw_source_path values",
                actual=source_path,
                evidence={
                    "audit_code": "duplicate_display_source_path",
                    "raw_source_path": source_path,
                    "occurrences": count,
                },
            ))
        for source_path, count in folded_path_counts.items():
            if count <= 1:
                continue
            violations.append(ContractViolation(
                rule="H.7",
                rule_name="Display Ledger Contract - unique folded source path",
                severity="error",
                message=(
                    "A source path may appear in only one folded label component"
                ),
                product_id=product_id,
                field_path="display_ingredients",
                expected="unique folded raw_source_path values",
                actual=source_path,
                evidence={
                    "audit_code": "duplicate_folded_source_path",
                    "raw_source_path": source_path,
                    "occurrences": count,
                },
            ))

        display_paths = set(display_path_counts)
        for source_path in sorted(display_paths & omission_paths):
            violations.append(ContractViolation(
                rule="H.7",
                rule_name="Label Ledger Contract - exclusive resolution",
                severity="error",
                message=(
                    "A source path cannot be both a primary display row and an "
                    "omission"
                ),
                product_id=product_id,
                field_path="display_ingredients",
                expected="display or omission, never both",
                actual=source_path,
                evidence={
                    "audit_code": "display_omission_source_path_overlap",
                    "raw_source_path": source_path,
                },
            ))

        canonical_sources_present = "label_source_rows" in product
        canonical_source_paths = set()
        canonical_source_path_counts = {}
        if canonical_sources_present:
            canonical_source_rows = product.get("label_source_rows")
            if not isinstance(canonical_source_rows, list):
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Source Row Contract - structure",
                    severity="error",
                    message="label_source_rows must be a list when present",
                    product_id=product_id,
                    field_path="label_source_rows",
                    expected="list",
                    actual=type(canonical_source_rows).__name__,
                    evidence={"audit_code": "invalid_label_source_rows"},
                ))
                source_collections = []
            else:
                source_collections = [("label_source_rows", canonical_source_rows)]
        else:
            source_collections = [
                (source_section, product.get(source_section, []))
                for source_section in ("activeIngredients", "inactiveIngredients")
            ]

        for source_section, source_rows in source_collections:
            if not isinstance(source_rows, list):
                continue
            for index, source_row in enumerate(source_rows):
                if not isinstance(source_row, dict):
                    if canonical_sources_present:
                        violations.append(ContractViolation(
                            rule="H.7",
                            rule_name="Label Source Row Contract - structure",
                            severity="error",
                            message=f"label_source_rows[{index}] must be an object",
                            product_id=product_id,
                            field_path=f"label_source_rows[{index}]",
                            expected="object",
                            actual=type(source_row).__name__,
                            evidence={"audit_code": "invalid_label_source_row"},
                        ))
                    continue
                source_text = self._source_row_text(source_row)
                source_path = self._nonempty_string(source_row.get("raw_source_path"))
                if canonical_sources_present:
                    missing_fields = [
                        field_name
                        for field_name in (
                            "raw_source_path",
                            "raw_source_text",
                            "source_section",
                        )
                        if field_name not in source_row
                    ]
                    if (
                        missing_fields
                        or not source_path
                        or not self._nonempty_string(source_row.get("source_section"))
                    ):
                        violations.append(ContractViolation(
                            rule="H.7",
                            rule_name="Label Source Row Contract - required fields",
                            severity="error",
                            message=(
                                "Each label_source_rows entry requires "
                                "raw_source_path, raw_source_text, and source_section"
                            ),
                            product_id=product_id,
                            field_path=f"label_source_rows[{index}]",
                            expected=[
                                "raw_source_path",
                                "raw_source_text",
                                "source_section",
                            ],
                            actual=sorted(source_row.keys()),
                            evidence={"audit_code": "invalid_label_source_row"},
                        ))
                        continue
                    canonical_source_paths.add(source_path)
                    canonical_source_path_counts[source_path] = (
                        canonical_source_path_counts.get(source_path, 0) + 1
                    )
                if (
                    (not canonical_sources_present and not source_text)
                    or not source_path
                    or source_path in display_paths
                    or source_path in omission_paths
                ):
                    continue
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Ledger Omission Contract - source reconciliation",
                    severity="error",
                    message=(
                        "Source row is absent from display_ingredients "
                        "without label_ledger_omissions evidence"
                    ),
                    product_id=product_id,
                    field_path=f"{source_section}[{index}].raw_source_path",
                    expected="display ledger row or allowed omission evidence",
                    actual=source_path,
                    evidence={
                        "audit_code": "missing_label_ledger_omission",
                        "raw_source_path": source_path,
                        "raw_source_text": source_text,
                    },
                ))

        if canonical_sources_present:
            for source_path, count in canonical_source_path_counts.items():
                if count <= 1:
                    continue
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Source Row Contract - unique source path",
                    severity="error",
                    message=(
                        "label_source_rows must contain one row per canonical "
                        "source path"
                    ),
                    product_id=product_id,
                    field_path="label_source_rows",
                    expected="unique raw_source_path values",
                    actual=source_path,
                    evidence={
                        "audit_code": "duplicate_label_source_path",
                        "raw_source_path": source_path,
                        "occurrences": count,
                    },
                ))

            for source_path in sorted(display_paths - canonical_source_paths):
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Ledger Contract - canonical inventory",
                    severity="error",
                    message=(
                        "A primary display path must exist in label_source_rows"
                    ),
                    product_id=product_id,
                    field_path="display_ingredients",
                    expected="path registered in label_source_rows",
                    actual=source_path,
                    evidence={
                        "audit_code": "unregistered_display_source_path",
                        "raw_source_path": source_path,
                    },
                ))
            for source_path in sorted(omission_paths - canonical_source_paths):
                violations.append(ContractViolation(
                    rule="H.7",
                    rule_name="Label Ledger Contract - canonical inventory",
                    severity="error",
                    message=(
                        "An omission path must exist in label_source_rows"
                    ),
                    product_id=product_id,
                    field_path="label_ledger_omissions",
                    expected="path registered in label_source_rows",
                    actual=source_path,
                    evidence={
                        "audit_code": "unregistered_omission_source_path",
                        "raw_source_path": source_path,
                    },
                ))
            for source_path in sorted(folded_path_counts):
                if source_path not in canonical_source_paths:
                    violations.append(ContractViolation(
                        rule="H.7",
                        rule_name="Display Ledger Contract - folded inventory",
                        severity="error",
                        message=(
                            "A folded component path must exist in "
                            "label_source_rows"
                        ),
                        product_id=product_id,
                        field_path="display_ingredients",
                        expected="path registered in label_source_rows",
                        actual=source_path,
                        evidence={
                            "audit_code": "unregistered_folded_source_path",
                            "raw_source_path": source_path,
                        },
                    ))
                elif (
                    source_path not in omission_paths
                    or "duplicate_source_line"
                    not in omission_reasons.get(source_path, set())
                ):
                    violations.append(ContractViolation(
                        rule="H.7",
                        rule_name="Display Ledger Contract - folded resolution",
                        severity="error",
                        message=(
                            "A folded component must be reconciled as a "
                            "duplicate_source_line omission"
                        ),
                        product_id=product_id,
                        field_path="display_ingredients",
                        expected="duplicate_source_line omission evidence",
                        actual=source_path,
                        evidence={
                            "audit_code": "folded_source_path_not_reconciled",
                            "raw_source_path": source_path,
                        },
                    ))

        audit = product.get("label_ledger_audit")
        if unsupported_omission and isinstance(audit, dict):
            audit_declares_unsupported = (
                audit.get("support_status") == "unsupported"
                or audit.get("source_structure") == "unsupported_source_structure"
            )
            if not audit_declares_unsupported and (
                audit.get("support_status") != "unsupported"
                or audit.get("completeness_status") != "unavailable"
                or audit.get("completeness_percentage") is not None
            ):
                violations.append(self._unsupported_completeness_violation(
                    product_id,
                    audit,
                    "label_ledger_omissions",
                ))
        return violations

    def _validate_label_ledger_audit(
        self,
        product: Dict,
        product_id: str,
    ) -> List[ContractViolation]:
        audit = product.get("label_ledger_audit")
        if audit is None:
            return []
        if not isinstance(audit, dict):
            return [ContractViolation(
                rule="H.8",
                rule_name="Label Ledger Audit Contract - structure",
                severity="error",
                message="label_ledger_audit must be an object when present",
                product_id=product_id,
                field_path="label_ledger_audit",
                expected="object",
                actual=type(audit).__name__,
                evidence={"audit_code": "invalid_label_ledger_audit"},
            )]

        violations = []
        missing_fields = sorted(
            field
            for field in self.LABEL_LEDGER_AUDIT_REQUIRED_FIELDS
            if field not in audit
        )
        if missing_fields:
            violations.append(ContractViolation(
                rule="H.8",
                rule_name="Label Ledger Audit Contract - required fields",
                severity="error",
                message=(
                    "label_ledger_audit missing required fields: "
                    f"{', '.join(missing_fields)}"
                ),
                product_id=product_id,
                field_path="label_ledger_audit",
                expected=sorted(self.LABEL_LEDGER_AUDIT_REQUIRED_FIELDS),
                actual=sorted(audit.keys()),
                evidence={"audit_code": "invalid_label_ledger_audit"},
            ))

        support_status = audit.get("support_status")
        completeness_status = audit.get("completeness_status")
        if support_status not in self.LABEL_LEDGER_SUPPORT_STATES:
            violations.append(ContractViolation(
                rule="H.8",
                rule_name="Label Ledger Audit Contract - support state enum",
                severity="error",
                message=(
                    "label_ledger_audit.support_status must be supported or "
                    f"unsupported; got {support_status!r}"
                ),
                product_id=product_id,
                field_path="label_ledger_audit.support_status",
                expected=sorted(self.LABEL_LEDGER_SUPPORT_STATES),
                actual=support_status,
                evidence={"audit_code": "invalid_label_ledger_audit"},
            ))
        if completeness_status not in self.LABEL_LEDGER_COMPLETENESS_STATES:
            violations.append(ContractViolation(
                rule="H.8",
                rule_name="Label Ledger Audit Contract - completeness state enum",
                severity="error",
                message=(
                    "label_ledger_audit.completeness_status must be one of the "
                    f"closed states; got {completeness_status!r}"
                ),
                product_id=product_id,
                field_path="label_ledger_audit.completeness_status",
                expected=sorted(self.LABEL_LEDGER_COMPLETENESS_STATES),
                actual=completeness_status,
                evidence={"audit_code": "invalid_label_ledger_audit"},
            ))

        count_values = {}
        for field_name in (
            "meaningful_source_rows",
            "displayed_rows",
            "omitted_rows",
        ):
            value = audit.get(field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                violations.append(ContractViolation(
                    rule="H.8",
                    rule_name="Label Ledger Audit Contract - counts",
                    severity="error",
                    message=f"label_ledger_audit.{field_name} must be a non-negative integer",
                    product_id=product_id,
                    field_path=f"label_ledger_audit.{field_name}",
                    expected="non-negative integer",
                    actual=value,
                    evidence={"audit_code": "invalid_label_ledger_audit"},
                ))
            else:
                count_values[field_name] = value

        actual_display_mismatch = False
        display_rows = product.get("display_ingredients")
        if (
            "displayed_rows" in count_values
            and "display_ingredients" in product
            and isinstance(display_rows, list)
            and count_values["displayed_rows"] != len(display_rows)
        ):
            actual_display_mismatch = True
            violations.append(ContractViolation(
                rule="H.8",
                rule_name="Label Ledger Audit Contract - display count",
                severity="error",
                message=(
                    "label_ledger_audit.displayed_rows must equal the actual "
                    "display_ingredients length"
                ),
                product_id=product_id,
                field_path="label_ledger_audit.displayed_rows",
                expected=len(display_rows),
                actual=count_values["displayed_rows"],
                evidence={"audit_code": "displayed_rows_count_mismatch"},
            ))

        omissions = product.get("label_ledger_omissions")
        if (
            "omitted_rows" in count_values
            and "label_ledger_omissions" in product
            and isinstance(omissions, list)
            and count_values["omitted_rows"] != len(omissions)
        ):
            violations.append(ContractViolation(
                rule="H.8",
                rule_name="Label Ledger Audit Contract - omission count",
                severity="error",
                message=(
                    "label_ledger_audit.omitted_rows must equal the actual "
                    "label_ledger_omissions length"
                ),
                product_id=product_id,
                field_path="label_ledger_audit.omitted_rows",
                expected=len(omissions),
                actual=count_values["omitted_rows"],
                evidence={"audit_code": "omitted_rows_count_mismatch"},
            ))

        canonical_source_rows = product.get("label_source_rows")
        if isinstance(canonical_source_rows, list):
            canonical_source_paths = {
                self._nonempty_string(row.get("raw_source_path"))
                for row in canonical_source_rows
                if isinstance(row, dict)
                and self._nonempty_string(row.get("raw_source_path"))
            }
            omission_paths = {
                self._nonempty_string(row.get("raw_source_path"))
                for row in (omissions if isinstance(omissions, list) else [])
                if isinstance(row, dict)
                and self._nonempty_string(row.get("raw_source_path"))
            }
            expected_meaningful_rows = len(
                canonical_source_paths - omission_paths
            )
            expected_displayed_rows = expected_meaningful_rows
            if (
                "meaningful_source_rows" in count_values
                and count_values["meaningful_source_rows"]
                != expected_meaningful_rows
            ):
                violations.append(ContractViolation(
                    rule="H.8",
                    rule_name="Label Ledger Audit Contract - source inventory",
                    severity="error",
                    message=(
                        "meaningful_source_rows must be derived from unique "
                        "label_source_rows paths minus allowed omission paths"
                    ),
                    product_id=product_id,
                    field_path="label_ledger_audit.meaningful_source_rows",
                    expected=expected_meaningful_rows,
                    actual=count_values["meaningful_source_rows"],
                    evidence={
                        "audit_code":
                        "meaningful_source_rows_inventory_mismatch"
                    },
                ))
            if (
                "displayed_rows" in count_values
                and count_values["displayed_rows"] != expected_displayed_rows
            ):
                violations.append(ContractViolation(
                    rule="H.8",
                    rule_name="Label Ledger Audit Contract - source inventory",
                    severity="error",
                    message=(
                        "displayed_rows must equal the canonical source paths "
                        "remaining after allowed omissions"
                    ),
                    product_id=product_id,
                    field_path="label_ledger_audit.displayed_rows",
                    expected=expected_displayed_rows,
                    actual=count_values["displayed_rows"],
                    evidence={
                        "audit_code": "displayed_rows_inventory_mismatch"
                    },
                ))

        source_structure = self._nonempty_string(audit.get("source_structure"))
        percentage = audit.get("completeness_percentage")
        is_unsupported = (
            support_status == "unsupported"
            or source_structure == "unsupported_source_structure"
        )
        if is_unsupported:
            if completeness_status != "unavailable" or percentage is not None:
                violations.append(self._unsupported_completeness_violation(
                    product_id,
                    audit,
                    "label_ledger_audit",
                ))
        elif support_status == "supported":
            supported_contract_error = actual_display_mismatch
            meaningful_rows = count_values.get("meaningful_source_rows")
            displayed_count = count_values.get("displayed_rows")
            expected_percentage = None

            if meaningful_rows is not None and displayed_count is not None:
                if meaningful_rows != displayed_count:
                    supported_contract_error = True
                    violations.append(ContractViolation(
                        rule="H.8",
                        rule_name="Label Ledger Audit Contract - supported counts",
                        severity="error",
                        message=(
                            "Supported structures require meaningful_source_rows "
                            "to equal displayed_rows; omissions track only "
                            "non-meaningful source rows"
                        ),
                        product_id=product_id,
                        field_path="label_ledger_audit.meaningful_source_rows",
                        expected=displayed_count,
                        actual=meaningful_rows,
                        evidence={
                            "audit_code":
                            "supported_meaningful_display_count_mismatch"
                        },
                    ))

                if meaningful_rows > 0:
                    expected_percentage = round(
                        displayed_count / meaningful_rows * 100.0,
                        2,
                    )
                elif displayed_count == 0:
                    if (
                        source_structure
                        in self.LABEL_LEDGER_SUPPORTED_EMPTY_STRUCTURES
                    ):
                        expected_percentage = 100.0
                    else:
                        supported_contract_error = True
                        violations.append(ContractViolation(
                            rule="H.8",
                            rule_name=(
                                "Label Ledger Audit Contract - supported empty panel"
                            ),
                            severity="error",
                            message=(
                                "A zero-row supported ledger may claim 100% only "
                                "when source_structure explicitly identifies an "
                                "empty panel"
                            ),
                            product_id=product_id,
                            field_path="label_ledger_audit.source_structure",
                            expected=sorted(
                                self.LABEL_LEDGER_SUPPORTED_EMPTY_STRUCTURES
                            ),
                            actual=source_structure,
                            evidence={
                                "audit_code":
                                "supported_empty_panel_not_declared"
                            },
                        ))

            percentage_is_number = (
                not isinstance(percentage, bool)
                and isinstance(percentage, (int, float))
            )
            if expected_percentage is not None and (
                not percentage_is_number
                or round(float(percentage), 2) != expected_percentage
            ):
                supported_contract_error = True
                violations.append(ContractViolation(
                    rule="H.8",
                    rule_name="Label Ledger Audit Contract - completeness math",
                    severity="error",
                    message=(
                        "completeness_percentage must equal displayed_rows / "
                        "meaningful_source_rows * 100"
                    ),
                    product_id=product_id,
                    field_path="label_ledger_audit.completeness_percentage",
                    expected=expected_percentage,
                    actual=percentage,
                    evidence={
                        "audit_code": "label_completeness_percentage_mismatch"
                    },
                ))

            if (
                completeness_status != "complete"
                or not percentage_is_number
                or float(percentage) != 100.0
                or supported_contract_error
            ):
                violations.append(ContractViolation(
                    rule="H.8",
                    rule_name="Label Ledger Audit Contract - supported completeness",
                    severity="error",
                    message=(
                        "Supported label archetypes must be internally consistent "
                        "and 100% complete before release"
                    ),
                    product_id=product_id,
                    field_path="label_ledger_audit.completeness_percentage",
                    expected=100.0,
                    actual=percentage,
                    evidence={"audit_code": "supported_archetype_incomplete"},
                ))
        return violations

    @staticmethod
    def _unsupported_completeness_violation(
        product_id: str,
        audit: Dict,
        field_path: str,
    ) -> ContractViolation:
        return ContractViolation(
            rule="H.8",
            rule_name="Label Ledger Audit Contract - unsupported completeness",
            severity="error",
            message=(
                "unsupported_source_structure makes completeness unavailable; "
                "a completeness percentage or complete claim cannot ship"
            ),
            product_id=product_id,
            field_path=field_path,
            expected={
                "support_status": "unsupported",
                "completeness_percentage": None,
                "completeness_status": "unavailable",
            },
            actual={
                "support_status": audit.get("support_status"),
                "source_structure": audit.get("source_structure"),
                "completeness_percentage": audit.get("completeness_percentage"),
                "completeness_status": audit.get("completeness_status"),
            },
            evidence={"audit_code": "unsupported_structure_completeness_claim"},
        )

    @staticmethod
    def _nonempty_string(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @classmethod
    def _first_nonempty_string(cls, *values: Any) -> str:
        for value in values:
            text = cls._nonempty_string(value)
            if text:
                return text
        return ""

    @classmethod
    def _source_row_text(cls, row: Dict) -> str:
        if "raw_source_text" in row:
            return cls._nonempty_string(row.get("raw_source_text"))
        return cls._nonempty_string(row.get("name"))

    @staticmethod
    def _claim_value(row: Dict, path: tuple) -> tuple:
        current: Any = row
        for segment in path:
            if not isinstance(current, dict) or segment not in current:
                return False, None
            current = current[segment]
        if current is None or current == "" or current == [] or current == {}:
            return False, current
        return True, current

    @staticmethod
    def _score_is_published(product: Dict) -> bool:
        return (
            product.get("quality_score_status") == "scored"
            or product.get("quality_score_v4_100") is not None
        )

    # =========================================================================
    # RULE I: Identity / Safety Separation
    # =========================================================================

    def _validate_identity_safety_separation(
        self, product: Dict, product_id: str
    ) -> List[ContractViolation]:
        """Validate that safety sources do not own identity fields."""
        violations = []
        all_ingredients = (
            (product.get("activeIngredients", []) or []) +
            (product.get("inactiveIngredients", []) or []) +
            (product.get("ingredients", []) or []) +
            (product.get("inactive_ingredients", []) or [])
        )

        for index, ing in enumerate(all_ingredients):
            if not isinstance(ing, dict):
                continue
            field_path = f"ingredients[{index}]"
            standard_name = ing.get("standard_name")
            standard_name_alias = ing.get("standardName")
            if standard_name and standard_name_alias and standard_name != standard_name_alias:
                violations.append(ContractViolation(
                    rule="I.1",
                    rule_name="Identity/Safety Separation - standard name alias",
                    severity="error",
                    message="standardName and standard_name must be identical identity aliases",
                    product_id=product_id,
                    field_path=field_path,
                    expected=standard_name,
                    actual=standard_name_alias,
                    evidence={"name": ing.get("name")},
                ))

            source = self._norm_source(ing.get("canonical_source_db") or ing.get("source_db"))
            if source in self.SAFETY_IDENTITY_SOURCES:
                violations.append(ContractViolation(
                    rule="I.2",
                    rule_name="Identity/Safety Separation - identity source",
                    severity="error",
                    message=f"Ingredient identity is sourced from safety database '{source}'",
                    product_id=product_id,
                    field_path=f"{field_path}.canonical_source_db",
                    expected="identity source database",
                    actual=source,
                    evidence={"name": ing.get("name"), "standardName": standard_name_alias},
                ))

            safety_flags = [
                flag for flag in (ing.get("safety_flags") or [])
                if isinstance(flag, dict)
            ]
            matched_source = self._norm_source(ing.get("matched_source"))
            matched_rule_id = ing.get("matched_rule_id")
            if matched_source in self.SAFETY_IDENTITY_SOURCES and matched_rule_id:
                if not safety_flags:
                    violations.append(ContractViolation(
                        rule="I.3",
                        rule_name="Identity/Safety Separation - legacy safety projection",
                        severity="error",
                        message="Legacy safety fields must be projected from safety_flags",
                        product_id=product_id,
                        field_path=field_path,
                        expected="matching safety_flags[] entry",
                        actual={"matched_source": ing.get("matched_source"), "matched_rule_id": matched_rule_id},
                        evidence={"name": ing.get("name")},
                    ))
                elif not any(
                    self._safety_flag_matches_legacy_fields(
                        flag,
                        matched_source=matched_source,
                        matched_rule_id=str(matched_rule_id),
                    )
                    for flag in safety_flags
                ):
                    violations.append(ContractViolation(
                        rule="I.3",
                        rule_name="Identity/Safety Separation - legacy safety projection",
                        severity="error",
                        message="Legacy safety fields must have a matching safety_flags[] entry",
                        product_id=product_id,
                        field_path=field_path,
                        expected={"source_db": matched_source, "entry_id": matched_rule_id},
                        actual=[
                            {
                                "source_db": flag.get("source_db") or flag.get("matched_source"),
                                "entry_id": flag.get("entry_id") or flag.get("rule_id"),
                            }
                            for flag in safety_flags
                        ],
                        evidence={"name": ing.get("name")},
                    ))

            for flag_index, flag in enumerate(safety_flags):
                missing = sorted(
                    field for field in self.SAFETY_FLAG_REQUIRED_FIELDS
                    if flag.get(field) in (None, "")
                )
                if missing:
                    violations.append(ContractViolation(
                        rule="I.4",
                        rule_name="Identity/Safety Separation - safety flag shape",
                        severity="error",
                        message=f"safety_flags[{flag_index}] missing required fields: {missing}",
                        product_id=product_id,
                        field_path=f"{field_path}.safety_flags[{flag_index}]",
                        expected=sorted(self.SAFETY_FLAG_REQUIRED_FIELDS),
                        actual=sorted(flag.keys()),
                        evidence={"name": ing.get("name")},
                    ))

        return violations

    def validate_banned_recalled_reference(self, doc: Dict) -> List[ContractViolation]:
        """Validate banned/recalled matching policy fields.

        This is intentionally separate from product validation because the
        reference database is reviewed in smaller clinical-policy batches.
        """
        violations: List[ContractViolation] = []
        entries = doc.get("ingredients") or doc.get("banned_recalled_ingredients") or []
        if not isinstance(entries, list):
            return violations

        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id") or f"entry_{index}"
            field_path = f"ingredients[{index}]"
            match_rules = entry.get("match_rules") or {}
            negative_terms = (
                entry.get("negative_match_terms")
                if "negative_match_terms" in entry
                else match_rules.get("negative_match_terms", [])
            )

            violations.extend(self._validate_negative_match_terms(
                negative_terms,
                product_id=str(entry_id),
                field_path=f"{field_path}.match_rules.negative_match_terms",
            ))

            requires_evidence = bool(entry.get("requires_explicit_form_evidence"))
            patterns = entry.get("form_evidence_patterns") or []
            if requires_evidence and not patterns:
                violations.append(ContractViolation(
                    rule="I.6",
                    rule_name="Reference Safety Policy - explicit evidence patterns",
                    severity="error",
                    message="requires_explicit_form_evidence=true requires form_evidence_patterns",
                    product_id=str(entry_id),
                    field_path=f"{field_path}.form_evidence_patterns",
                    expected="non-empty list[str]",
                    actual=patterns,
                    evidence={"standard_name": entry.get("standard_name")},
                ))

            if (
                self._is_qualified_safety_name(entry.get("standard_name"))
                and not requires_evidence
                and not negative_terms
            ):
                violations.append(ContractViolation(
                    rule="I.7",
                    rule_name="Reference Safety Policy - qualified entry guard",
                    severity="warning",
                    message="Qualified banned/recalled entry lacks negative_match_terms or explicit evidence policy",
                    product_id=str(entry_id),
                    field_path=field_path,
                    expected="negative_match_terms or requires_explicit_form_evidence=true",
                    actual={
                        "negative_match_terms": negative_terms,
                        "requires_explicit_form_evidence": requires_evidence,
                    },
                    evidence={"standard_name": entry.get("standard_name")},
                ))

        return violations

    def _validate_negative_match_terms(
        self, terms: Any, *, product_id: str, field_path: str
    ) -> List[ContractViolation]:
        violations = []
        if terms in (None, ""):
            return violations
        if not isinstance(terms, list):
            return [ContractViolation(
                rule="I.5",
                rule_name="Reference Safety Policy - negative match terms",
                severity="error",
                message="negative_match_terms must be a list",
                product_id=product_id,
                field_path=field_path,
                expected="list[str | {term, match_mode}]",
                actual=type(terms).__name__,
            )]

        for index, term in enumerate(terms):
            term_path = f"{field_path}[{index}]"
            if isinstance(term, str):
                continue
            if not isinstance(term, dict):
                violations.append(ContractViolation(
                    rule="I.5",
                    rule_name="Reference Safety Policy - negative match terms",
                    severity="error",
                    message="negative_match_terms entries must be strings or objects",
                    product_id=product_id,
                    field_path=term_path,
                    expected="str | {term: str, match_mode: exact|substring}",
                    actual=type(term).__name__,
                ))
                continue
            match_term = term.get("term")
            match_mode = term.get("match_mode", "substring")
            if not isinstance(match_term, str) or not match_term.strip():
                violations.append(ContractViolation(
                    rule="I.5",
                    rule_name="Reference Safety Policy - negative match terms",
                    severity="error",
                    message="negative_match_terms object entries require a non-empty term",
                    product_id=product_id,
                    field_path=f"{term_path}.term",
                    expected="non-empty string",
                    actual=match_term,
                ))
            if match_mode not in self.NEGATIVE_MATCH_MODES:
                violations.append(ContractViolation(
                    rule="I.5",
                    rule_name="Reference Safety Policy - negative match terms",
                    severity="error",
                    message=f"negative_match_terms match_mode must be one of {sorted(self.NEGATIVE_MATCH_MODES)}",
                    product_id=product_id,
                    field_path=f"{term_path}.match_mode",
                    expected=sorted(self.NEGATIVE_MATCH_MODES),
                    actual=match_mode,
                ))
        return violations

    @classmethod
    def _is_qualified_safety_name(cls, value: Any) -> bool:
        return bool(cls.QUALIFIED_SAFETY_NAME_RE.search(str(value or "")))

    @staticmethod
    def _norm_source(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if normalized == "banned_recalled":
            return "banned_recalled_ingredients"
        return normalized

    @classmethod
    def _safety_flag_matches_legacy_fields(
        cls,
        flag: Dict[str, Any],
        *,
        matched_source: str,
        matched_rule_id: str,
    ) -> bool:
        flag_source = cls._norm_source(flag.get("source_db") or flag.get("matched_source"))
        flag_rule_id = str(flag.get("entry_id") or flag.get("rule_id") or "")
        return bool(flag_rule_id and flag_rule_id == matched_rule_id and flag_source == matched_source)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def log_violations(self, violations: List[ContractViolation], level: str = "warning"):
        """Log violations using the logger"""
        for v in violations:
            log_level = logging.ERROR if v.severity == "error" else logging.WARNING
            if level == "error":
                log_level = logging.ERROR

            logger.log(
                log_level,
                f"[{v.rule}] {v.rule_name} - Product {v.product_id}: {v.message}"
            )

    def to_dict(self, violation: ContractViolation) -> Dict:
        """Convert a violation to a dictionary for JSON serialization"""
        return {
            "rule": violation.rule,
            "rule_name": violation.rule_name,
            "severity": violation.severity,
            "message": violation.message,
            "product_id": violation.product_id,
            "field_path": violation.field_path,
            "expected": violation.expected,
            "actual": violation.actual,
            "evidence": violation.evidence
        }


# Convenience function for quick validation
def validate_enriched_product(product: Dict) -> List[Dict]:
    """
    Convenience function to validate an enriched product.

    Returns list of violation dictionaries.
    """
    validator = EnrichmentContractValidator()
    violations = validator.validate(product)
    return [validator.to_dict(v) for v in violations]


def validate_enriched_payload(payload: Any) -> tuple[List[ContractViolation], int]:
    """Validate one enriched product or an operational batch payload."""
    validator = EnrichmentContractValidator()
    if isinstance(payload, list):
        violations: List[ContractViolation] = []
        product_count = 0
        for index, product in enumerate(payload):
            if not isinstance(product, dict):
                violations.append(ContractViolation(
                    rule="CLI.1",
                    rule_name="Enriched batch payload shape",
                    severity="error",
                    message="Batch entries must be enriched product objects",
                    product_id=f"batch[{index}]",
                    field_path=f"$[{index}]",
                    expected="object",
                    actual=type(product).__name__,
                ))
                continue
            product_count += 1
            violations.extend(validator.validate(product))
        return violations, product_count
    if isinstance(payload, dict):
        return validator.validate(payload), 1
    return [
        ContractViolation(
            rule="CLI.1",
            rule_name="Enriched payload shape",
            severity="error",
            message="Payload must be an enriched product object or a batch list",
            product_id="unknown",
            field_path="$",
            expected="object or list",
            actual=type(payload).__name__,
        )
    ], 0


def main(argv: Optional[List[str]] = None) -> int:
    import json
    import sys

    argv = argv or sys.argv[1:]

    if argv:
        path_arg = argv[0]
        with open(path_arg) as f:
            payload = json.load(f)

        validator = EnrichmentContractValidator()
        if path_arg.endswith("banned_recalled_ingredients.json"):
            violations = validator.validate_banned_recalled_reference(payload)
            product_count = 1
        else:
            violations, product_count = validate_enriched_payload(payload)

        if violations:
            print(f"Validated {product_count} product(s).")
            print(f"Found {len(violations)} contract violations:")
            for v in violations:
                print(f"  [{v.severity.upper()}] {v.rule}: {v.message}")
            return 1 if any(v.severity == "error" for v in violations) else 0
        else:
            print(f"Validated {product_count} product(s).")
            print("All contract rules passed!")
            return 0
    else:
        print("Usage: python enrichment_contract_validator.py <enriched_product.json>")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
