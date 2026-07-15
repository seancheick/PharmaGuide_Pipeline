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
H. Display Ledger Contract - display_ingredients is optional, but must be well-formed when present

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
# =============================================================================
PIPELINE_CONTRACT_VERSION = "1.0.0"


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
        "raw_source_text",
        "display_name",
        "source_section",
        "display_type",
        "resolution_type",
        "score_included",
    })

    DISPLAY_LEDGER_ALLOWED_SOURCE_SECTIONS = DISPLAY_LEDGER_SOURCE_SECTIONS

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
        """
        violations = []
        display_rows = product.get("display_ingredients")

        if display_rows is None:
            return violations

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

        return violations

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
