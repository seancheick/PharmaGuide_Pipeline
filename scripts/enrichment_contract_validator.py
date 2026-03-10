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
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

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
    GUMMY_UNIT_VARIANTS = {
        "gummy", "gummies", "gummy(ies)", "gummie", "gummie(s)"
    }

    DISPLAY_LEDGER_REQUIRED_FIELDS = frozenset({
        "raw_source_text",
        "display_name",
        "source_section",
        "display_type",
        "resolution_type",
        "score_included",
    })

    DISPLAY_LEDGER_ALLOWED_SOURCE_SECTIONS = frozenset({
        "activeIngredients",
        "inactiveIngredients",
    })

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
            has_explicit_dye = any(
                token in flagged_ing_name
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
        form_factor = (serving_basis.get("form_factor", "") or "").lower()
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


if __name__ == "__main__":
    # Example usage
    import json
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            product = json.load(f)

        validator = EnrichmentContractValidator()
        violations = validator.validate(product)

        if violations:
            print(f"Found {len(violations)} contract violations:")
            for v in violations:
                print(f"  [{v.severity.upper()}] {v.rule}: {v.message}")
        else:
            print("All contract rules passed!")
    else:
        print("Usage: python enrichment_contract_validator.py <enriched_product.json>")
