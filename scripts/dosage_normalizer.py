#!/usr/bin/env python3
"""
Dosage Normalization Module

Handles serving basis detection, serving size selection, and dosage normalization
for supplement products. Outputs structured evidence for scoring.

Key features:
- Serving size parsing and selection policy
- Per-serving and per-day dosage calculation
- Unit conversion integration
- Full evidence tracking

Usage:
    from dosage_normalizer import DosageNormalizer

    normalizer = DosageNormalizer()
    result = normalizer.normalize_product_dosages(product)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from unit_converter import UnitConverter
from serving_frequency import resolve_daily_serving_range, select_canonical_serving

logger = logging.getLogger(__name__)


@dataclass
class ServingBasis:
    """Serving basis information with evidence."""
    quantity: float
    unit: str
    servings_per_container: Optional[float]
    servings_per_day_min: float
    servings_per_day_max: float
    servings_per_day_used: float  # Policy: use minimum
    source_field: str
    raw_text: str
    confidence: str  # "high", "medium", "low"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "quantity": self.quantity,
            "unit": self.unit,
            "servings_per_container": self.servings_per_container,
            "servings_per_day_min": self.servings_per_day_min,
            "servings_per_day_max": self.servings_per_day_max,
            "servings_per_day_used": self.servings_per_day_used,
            "source_field": self.source_field,
            "raw_text": self.raw_text,
            "confidence": self.confidence,
            "notes": self.notes
        }


@dataclass
class NormalizedIngredient:
    """A normalized ingredient with conversion evidence."""
    original_name: str
    standard_name: Optional[str]
    original_amount: Optional[float]
    original_unit: Optional[str]
    normalized_amount: Optional[float]
    normalized_unit: Optional[str]
    per_day_min: Optional[float]
    per_day_max: Optional[float]
    conversion_evidence: Dict
    source_field: str

    def to_dict(self) -> Dict:
        return {
            "original_name": self.original_name,
            "standard_name": self.standard_name,
            "original_amount": self.original_amount,
            "original_unit": self.original_unit,
            "normalized_amount": self.normalized_amount,
            "normalized_unit": self.normalized_unit,
            "per_day_min": self.per_day_min,
            "per_day_max": self.per_day_max,
            "conversion_evidence": self.conversion_evidence,
            "source_field": self.source_field
        }


@dataclass
class DosageNormalizationResult:
    """Complete dosage normalization result for a product."""
    success: bool
    serving_basis: Optional[ServingBasis]
    normalized_ingredients: List[NormalizedIngredient]
    warnings: List[str]
    errors: List[str]

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "serving_basis": self.serving_basis.to_dict() if self.serving_basis else None,
            "normalized_ingredients": [i.to_dict() for i in self.normalized_ingredients],
            "warnings": self.warnings,
            "errors": self.errors
        }


class DosageNormalizer:
    """
    Dosage normalization engine.

    Parses serving sizes, applies selection policy, and normalizes all
    ingredient amounts with unit conversions.
    """

    # Serving size patterns - ORDER MATTERS: most specific patterns first
    SERVING_PATTERNS = [
        # Pattern 0: "Take 1-2 capsules" - MOST SPECIFIC, check first
        r'take\s+(\d+)(?:\s*-\s*(\d+))?\s*(capsule|tablet|softgel|gummy|gummies)s?',
        # Pattern 1: "1/2 teaspoon", "1 tablespoon" - fractions
        r'(\d+(?:/\d+)?)\s*(teaspoon|tablespoon|tsp|tbsp)',
        # Pattern 2: "1 capsule", "2 softgels", "3 tablets" - simple quantity+unit
        r'(\d+(?:\.\d+)?)\s*(capsule|softgel|tablet|gummy|gummies|lozenge|drop|spray|scoop|packet|stick)s?',
    ]

    NO_RULE_ERROR_PREFIX = "No conversion rule found for nutrient:"

    def __init__(self, unit_converter: Optional[UnitConverter] = None):
        """
        Initialize dosage normalizer.

        Args:
            unit_converter: UnitConverter instance. Creates one if not provided.
        """
        self.unit_converter = unit_converter or UnitConverter()

    # Unicode fraction mappings
    UNICODE_FRACTIONS = {
        '½': 0.5, '⅓': 0.333, '⅔': 0.667, '¼': 0.25, '¾': 0.75,
        '⅕': 0.2, '⅖': 0.4, '⅗': 0.6, '⅘': 0.8,
        '⅙': 0.167, '⅚': 0.833, '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875,
    }

    def _parse_quantity(self, qty_str: str) -> float:
        """Parse quantity string, handling fractions, unicode, and mixed numbers.

        Supports:
        - Decimals: "2", "1.5", "0.5"
        - Fractions: "1/2", "3/4"
        - Unicode fractions: "½", "¼", "¾"
        - Mixed numbers: "1 1/2", "1½", "2 ½"

        Args:
            qty_str: Quantity string

        Returns:
            Parsed float value, or 1.0 on failure
        """
        if not qty_str:
            return 1.0

        qty_str = qty_str.strip()

        # Step 1: Replace unicode fractions with decimal values
        for unicode_frac, value in self.UNICODE_FRACTIONS.items():
            if unicode_frac in qty_str:
                # Handle mixed numbers like "1½" → "1" + 0.5 = 1.5
                parts = qty_str.split(unicode_frac)
                whole_part = parts[0].strip()
                if whole_part and whole_part.replace('.', '').isdigit():
                    return float(whole_part) + value
                return value

        # Step 2: Handle mixed fractions like "1 1/2"
        mixed_match = re.match(r'^(\d+)\s+(\d+)/(\d+)$', qty_str)
        if mixed_match:
            whole = float(mixed_match.group(1))
            numerator = float(mixed_match.group(2))
            denominator = float(mixed_match.group(3))
            if denominator != 0:
                return whole + (numerator / denominator)
            return whole

        # Step 3: Handle simple fractions like "1/2", "3/4"
        if '/' in qty_str:
            try:
                parts = qty_str.split('/')
                if len(parts) == 2:
                    numerator = float(parts[0].strip())
                    denominator = float(parts[1].strip())
                    if denominator != 0:
                        return numerator / denominator
            except (ValueError, ZeroDivisionError):
                pass
            logger.warning("Unparseable fraction quantity '%s', defaulting to 1.0", qty_str)
            return 1.0

        # Handle regular numbers
        try:
            return float(qty_str.replace(',', ''))
        except ValueError:
            logger.warning("Unparseable quantity '%s', defaulting to 1.0", qty_str)
            return 1.0

    def normalize_product_dosages(self, product: Dict) -> DosageNormalizationResult:
        """
        Normalize all dosages for a product.

        Args:
            product: Product dictionary with serving info and ingredients

        Returns:
            DosageNormalizationResult with all normalized data
        """
        warnings = []
        errors = []

        # Step 1: Extract serving basis
        serving_basis = self._extract_serving_basis(product)
        if serving_basis is None:
            errors.append("Could not determine serving basis")
            return DosageNormalizationResult(
                success=False,
                serving_basis=None,
                normalized_ingredients=[],
                warnings=warnings,
                errors=errors
            )

        # Step 2: Normalize all ingredients
        normalized_ingredients = []

        # Process supplement facts (or cleaned active ingredients)
        supp_facts = product.get('supplementFacts')
        supp_source = "supplementFacts"
        if not supp_facts:
            supp_facts = product.get('activeIngredients', [])
            supp_source = "activeIngredients"
        if not isinstance(supp_facts, list):
            supp_facts = []

        for i, ing in enumerate(supp_facts):
            normalized = self._normalize_ingredient(
                ing,
                serving_basis,
                f"{supp_source}[{i}]"
            )
            if normalized:
                normalized_ingredients.append(normalized)
                if normalized.conversion_evidence.get('warnings'):
                    warnings.extend(normalized.conversion_evidence['warnings'])

        # Process other ingredients that might have amounts
        other_ings = product.get('otherIngredients')
        other_source = "otherIngredients"
        if not other_ings:
            other_ings = product.get('inactiveIngredients', [])
            other_source = "inactiveIngredients"
        if not isinstance(other_ings, list):
            other_ings = []

        for i, ing in enumerate(other_ings):
            if isinstance(ing, dict) and (ing.get('amount') or ing.get('quantity')):
                normalized = self._normalize_ingredient(
                    ing,
                    serving_basis,
                    f"{other_source}[{i}]"
                )
                if normalized:
                    normalized_ingredients.append(normalized)

        if not normalized_ingredients:
            errors.append("No ingredients normalized")
            return DosageNormalizationResult(
                success=False,
                serving_basis=serving_basis,
                normalized_ingredients=[],
                warnings=warnings,
                errors=errors
            )

        return DosageNormalizationResult(
            success=True,
            serving_basis=serving_basis,
            normalized_ingredients=normalized_ingredients,
            warnings=warnings,
            errors=errors
        )

    def _extract_serving_basis(self, product: Dict) -> Optional[ServingBasis]:
        """Project the canonical serving selection and daily-frequency result."""
        sources = [
            ('servingSizes', product.get('servingSizes', [])),
            ('servingSize', [product.get('servingSize')] if product.get('servingSize') else []),
            ('labelText', self._extract_from_label_text(product.get('labelText', {}))),
        ]
        for source_name, serving_data in sources:
            if not isinstance(serving_data, list) or not serving_data:
                continue
            serving = select_canonical_serving(serving_data)
            if serving is None:
                # Legacy string carriers provide physical quantity only; they
                # cannot create a second daily-direction interpretation.
                serving = next((entry for entry in serving_data if isinstance(entry, str)), None)
            if isinstance(serving, dict):
                result = self._parse_serving_dict(serving, source_name)
            elif isinstance(serving, str):
                result = self._parse_serving_string(serving, source_name)
            else:
                continue
            if result is None:
                continue
            low, high, was_defaulted = resolve_daily_serving_range(product)
            result.servings_per_day_min = low
            result.servings_per_day_max = high
            result.servings_per_day_used = low
            result.notes.append('Daily frequency: serving_frequency owner')
            if was_defaulted:
                result.confidence = 'low'
                result.notes.append('Daily frequency defaulted or incompletely declared')
            return result
        return None

    def _extract_from_label_text(self, label_text: Dict) -> List[Dict]:
        """Extract serving info from label text."""
        parsed = label_text.get('parsed', {})
        serving_info = parsed.get('servingInfo', {})

        if serving_info:
            return [serving_info]

        # Try raw text
        raw = label_text.get('raw', '')
        if raw:
            # Look for serving size in raw text
            for pattern in self.SERVING_PATTERNS:
                match = re.search(pattern, raw, re.IGNORECASE)
                if match:
                    return [{'raw_text': match.group(0)}]

        return []

    def _parse_serving_dict(self, serving: Dict, source: str) -> Optional[ServingBasis]:
        """Parse serving size from dictionary."""
        quantity = next((serving.get(key) for key in (
            'quantity', 'servingSizeQuantity', 'maxQuantity', 'minQuantity',
            'normalizedServing', 'amount') if serving.get(key)), 1)
        unit = serving.get('unit') or serving.get('type') or 'serving'
        servings_per_container = serving.get('servingsPerContainer')
        raw_text = serving.get('description') or serving.get('raw_text') or ''

        # Try to parse quantity if string
        if isinstance(quantity, str):
            try:
                if '/' in quantity:  # Handle fractions like "1/2"
                    parts = quantity.split('/')
                    denom = float(parts[1])
                    quantity = float(parts[0]) / denom if denom != 0 else 1
                else:
                    quantity = float(quantity.replace(',', ''))
            except (ValueError, ZeroDivisionError):
                quantity = 1

        return ServingBasis(
            quantity=float(quantity),
            unit=str(unit),
            servings_per_container=float(servings_per_container) if servings_per_container else None,
            servings_per_day_min=1,
            servings_per_day_max=1,
            servings_per_day_used=1,  # Assigned by the canonical daily resolver
            source_field=source,
            raw_text=raw_text,
            confidence="high" if quantity and unit else "medium",
            notes=[f"Source: {source}"]
        )

    def _parse_serving_string(self, serving: str, source: str) -> Optional[ServingBasis]:
        """Parse serving size from string.

        Handles three pattern types with different capture group layouts:
        - Pattern 1: (quantity)(unit) - "1 capsule", "2 softgels"
        - Pattern 2: (fraction/decimal)(unit) - "1/2 teaspoon"
        - Pattern 3: take (min)(-max)?(unit) - "Take 1-2 capsules"
        """
        for i, pattern in enumerate(self.SERVING_PATTERNS):
            match = re.search(pattern, serving, re.IGNORECASE)
            if match:
                groups = match.groups()

                # Pattern-specific group extraction
                if i == 0:
                    # Pattern 0: "Take 1-2 capsules" - (min, max_or_None, unit)
                    quantity = self._parse_quantity(groups[0]) if groups[0] else 1
                    unit = groups[2] if len(groups) > 2 and groups[2] else 'serving'
                elif i == 1:
                    # Pattern 1: "1/2 tsp" - (quantity, unit)
                    quantity = self._parse_quantity(groups[0]) if groups[0] else 1
                    unit = groups[1] if len(groups) > 1 and groups[1] else 'serving'
                elif i == 2:
                    # Pattern 2: "1 capsule" - (quantity, unit)
                    quantity = self._parse_quantity(groups[0]) if groups[0] else 1
                    unit = groups[1] if len(groups) > 1 and groups[1] else 'serving'
                else:
                    # Fallback for any future patterns
                    quantity = self._parse_quantity(groups[0]) if groups[0] else 1
                    unit = groups[-1] if groups else 'serving'

                return ServingBasis(
                    quantity=quantity,
                    unit=unit,
                    servings_per_container=None,
                    servings_per_day_min=1,
                    servings_per_day_max=1,
                    servings_per_day_used=1,
                    source_field=source,
                    raw_text=serving,
                    confidence="medium",
                    notes=[f"Parsed from string (pattern {i+1})"]
                )

        # Fallback
        return ServingBasis(
            quantity=1,
            unit="serving",
            servings_per_container=None,
            servings_per_day_min=1,
            servings_per_day_max=1,
            servings_per_day_used=1,
            source_field=source,
            raw_text=serving,
            confidence="low",
            notes=["Could not parse - using defaults"]
        )

    def _normalize_ingredient(
        self,
        ingredient: Dict,
        serving_basis: ServingBasis,
        source_field: str
    ) -> Optional[NormalizedIngredient]:
        """Normalize a single ingredient."""
        name = ingredient.get('name') or ingredient.get('ingredient') or ''
        if not name:
            return None

        amount = ingredient.get('amount') or ingredient.get('quantity')
        unit = ingredient.get('unit') or ''

        # Parse amount if string
        if isinstance(amount, str):
            # Handle ranges like "50-100"
            if '-' in amount and not amount.startswith('-'):
                parts = amount.split('-')
                try:
                    amount = float(parts[0].replace(',', ''))  # Use lower bound
                except ValueError:
                    amount = None
            else:
                try:
                    amount = float(amount.replace(',', '').replace('<', '').replace('>', ''))
                except ValueError:
                    amount = None

        if amount is None:
            return NormalizedIngredient(
                original_name=name,
                standard_name=None,
                original_amount=None,
                original_unit=unit,
                normalized_amount=None,
                normalized_unit=None,
                per_day_min=None,
                per_day_max=None,
                conversion_evidence={"success": False, "reason": "No amount specified"},
                source_field=source_field
            )

        # Convert units. For form-dependent vitamins (A, E, folate) the
        # converter's form detection scans ``ingredient_name`` for tokens
        # like "beta-carotene" / "retinyl palmitate" / "d-alpha tocopherol"
        # / "methylfolate" — but the bare ``name`` (e.g. "Vitamin A") never
        # contains the form. The form is in ``ingredient['forms'][*].name``
        # (DSLD schema). Join name + form names so the converter can route
        # to the correct rule. Without this, Vitamin A in IU silently uses
        # factor 1.0 ("form unknown") instead of 0.1 (β-carotene supplement)
        # or 0.3 (retinol) — a BLOCKER for the pregnancy/UL gate.
        form_names = [
            f.get('name', '') for f in (ingredient.get('forms') or [])
            if isinstance(f, dict) and f.get('name')
        ]
        ingredient_name_for_form_detection = (
            ' '.join([name] + form_names) if form_names else name
        )
        conversion_result = self.unit_converter.convert_nutrient(
            nutrient=name,
            amount=float(amount),
            from_unit=unit,
            ingredient_name=ingredient_name_for_form_detection,
            measured_name=name,
        )

        # Calculate per-day amounts
        per_day_min = None
        per_day_max = None
        if conversion_result.success and conversion_result.converted_value is not None:
            per_day_min = conversion_result.converted_value * serving_basis.servings_per_day_min
            per_day_max = conversion_result.converted_value * serving_basis.servings_per_day_max

        conversion_evidence = self._sanitize_conversion_evidence_for_output(
            conversion_result.to_dict()
        )

        return NormalizedIngredient(
            original_name=name,
            standard_name=conversion_result.form_detected,
            original_amount=float(amount),
            original_unit=unit,
            normalized_amount=conversion_result.converted_value,
            normalized_unit=conversion_result.converted_unit,
            per_day_min=per_day_min,
            per_day_max=per_day_max,
            conversion_evidence=conversion_evidence,
            source_field=source_field
        )

    def _sanitize_conversion_evidence_for_output(self, evidence: Dict) -> Dict:
        """
        Downgrade expected "no conversion rule" outcomes from error semantics to
        informational semantics for cleaner audits.

        This preserves failure state (`success=False`) while avoiding noisy
        false-positive error interpretation in downstream audit views.
        """
        if not isinstance(evidence, dict):
            return evidence

        sanitized = dict(evidence)
        error_msg = sanitized.get("error")
        if not isinstance(error_msg, str):
            return sanitized

        if not error_msg.startswith(self.NO_RULE_ERROR_PREFIX):
            return sanitized

        warnings = list(sanitized.get("warnings") or [])
        notes = list(sanitized.get("notes") or [])
        nutrient = (sanitized.get("nutrient_detected") or "").strip()

        info_msg = (
            f"No unit conversion rule configured for nutrient: {nutrient or 'unknown'}; "
            "kept original amount/unit for reference."
        )
        if info_msg not in warnings:
            warnings.append(info_msg)
        notes_msg = "Expected non-converted nutrient path (informational, non-fatal)."
        if notes_msg not in notes:
            notes.append(notes_msg)

        sanitized["original_error"] = error_msg
        sanitized["error"] = None
        sanitized["conversion_status"] = "not_converted_expected"
        sanitized["nonfatal_reason"] = "no_conversion_rule"
        sanitized["severity"] = "informational"
        sanitized["warnings"] = warnings
        sanitized["notes"] = notes
        return sanitized
