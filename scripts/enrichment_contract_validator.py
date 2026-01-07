"""
Enrichment Contract Validator

Enforces minimum contract rules for enriched product consistency.
These invariants must hold for any valid enriched product output.

Contract Rules:
A. Sugar Consistency - sugar flags must be internally consistent
B. Allergen Precedence - no duplicate allergens with weaker presence_type
C. Colors Consistency - natural colors must not be flagged as artificial
D. Serving Basis Integrity - form_factor and basis_unit must be consistent

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
        product_id = product.get("id", product.get("productId", "unknown"))

        # Run all contract validations
        violations.extend(self._validate_sugar_consistency(product, product_id))
        violations.extend(self._validate_allergen_precedence(product, product_id))
        violations.extend(self._validate_colors_consistency(product, product_id))
        violations.extend(self._validate_serving_basis_integrity(product, product_id))

        return violations

    def validate_batch(self, products: List[Dict]) -> Dict[str, List[ContractViolation]]:
        """
        Validate a batch of products.

        Returns:
            Dict mapping product_id to list of violations
        """
        results = {}
        for product in products:
            product_id = product.get("id", product.get("productId", "unknown"))
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
