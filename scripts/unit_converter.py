#!/usr/bin/env python3
"""
Unit Conversion Module for Dosage Normalization

Provides functions to convert nutrient amounts between units (IU, mcg, mg, etc.)
with full evidence tracking for audit purposes.

Key features:
- Nutrient + form specific conversions (e.g., Vitamin A retinol vs beta-carotene)
- Pattern-based form detection from ingredient names
- Full evidence output for every conversion
- Mass unit normalization (g, mg, mcg)
- CFU normalization for probiotics

Usage:
    from unit_converter import UnitConverter

    converter = UnitConverter()
    result = converter.convert_nutrient(
        nutrient="Vitamin D3",
        amount=2000,
        from_unit="IU",
        to_unit="mcg"
    )
    # result.converted_value = 50
    # result.evidence = {...}
"""

import json
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of a unit conversion with full evidence."""
    success: bool
    original_value: float
    original_unit: str
    converted_value: Optional[float]
    converted_unit: Optional[str]
    conversion_rule_id: Optional[str]
    conversion_factor: Optional[float]
    nutrient_detected: Optional[str]
    form_detected: Optional[str]
    form_detection_source: Optional[str]
    confidence: str  # "high", "medium", "low", "failed"
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "original_value": self.original_value,
            "original_unit": self.original_unit,
            "converted_value": self.converted_value,
            "converted_unit": self.converted_unit,
            "conversion_rule_id": self.conversion_rule_id,
            "conversion_factor": self.conversion_factor,
            "nutrient_detected": self.nutrient_detected,
            "form_detected": self.form_detected,
            "form_detection_source": self.form_detection_source,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "notes": self.notes,
            "error": self.error
        }


@dataclass
class CFUResult:
    """Result of CFU normalization."""
    success: bool
    original_value: float
    original_unit: str
    normalized_cfu: Optional[float]
    display_value: Optional[str]  # e.g., "50 billion CFU"
    qualifier: Optional[str]  # "at_expiration", "at_manufacture", "unqualified"
    confidence: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "original_value": self.original_value,
            "original_unit": self.original_unit,
            "normalized_cfu": self.normalized_cfu,
            "display_value": self.display_value,
            "qualifier": self.qualifier,
            "confidence": self.confidence,
            "notes": self.notes
        }


class UnitConverter:
    """
    Unit conversion engine with evidence tracking.

    Loads conversion rules from data/unit_conversions.json and provides
    methods to convert between units with full audit trail.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the unit converter.

        Args:
            db_path: Path to unit_conversions.json. If None, uses default.
        """
        if db_path is None:
            db_path = Path(__file__).parent / "data" / "unit_conversions.json"

        self.db_path = db_path
        self.db = None
        self.vitamin_conversions = {}
        self.mass_rules = {}
        self.probiotic_rules = {}
        self.form_patterns = {}
        self.version = "unknown"

        self._load_database()

    def _load_database(self) -> bool:
        """Load the unit conversions database."""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                self.db = json.load(f)

            self.version = self.db.get('_metadata', {}).get('version', 'unknown')
            self.vitamin_conversions = self.db.get('vitamin_conversions', {})
            self.mass_rules = self.db.get('mass_conversions', {}).get('rules', {})
            self.probiotic_rules = self.db.get('probiotic_conversions', {})
            self.form_patterns = self.db.get('form_detection_patterns', {})

            logger.info("Loaded unit_conversions.json v%s with %d vitamin rules",
                       self.version, len(self.vitamin_conversions))
            return True

        except FileNotFoundError:
            logger.error("Unit conversions database not found: %s", self.db_path)
            return False
        except json.JSONDecodeError as e:
            logger.error("Failed to parse unit conversions database: %s", e)
            return False

    def get_version(self) -> str:
        """Get database version."""
        return self.version

    # =========================================================================
    # NUTRIENT CONVERSION
    # =========================================================================

    def convert_nutrient(
        self,
        nutrient: str,
        amount: float,
        from_unit: str,
        to_unit: Optional[str] = None,
        ingredient_name: Optional[str] = None
    ) -> ConversionResult:
        """
        Convert a nutrient amount from one unit to another.

        Args:
            nutrient: Nutrient name (e.g., "Vitamin D3", "Vitamin A")
            amount: Amount in original units
            from_unit: Original unit (e.g., "IU", "mg", "mcg")
            to_unit: Target unit. If None, converts to canonical unit.
            ingredient_name: Full ingredient name for form detection

        Returns:
            ConversionResult with converted value and evidence
        """
        # Normalize inputs
        nutrient_lower = nutrient.lower().strip()
        from_unit_lower = from_unit.lower().strip()
        ingredient_text = ingredient_name or nutrient

        # Find matching conversion rule
        rule_id, rule_data = self._find_conversion_rule(
            nutrient_lower, ingredient_text
        )

        if rule_id is None:
            return ConversionResult(
                success=False,
                original_value=amount,
                original_unit=from_unit,
                converted_value=None,
                converted_unit=None,
                conversion_rule_id=None,
                conversion_factor=None,
                nutrient_detected=nutrient,
                form_detected=None,
                form_detection_source=None,
                confidence="failed",
                error=f"No conversion rule found for nutrient: {nutrient}"
            )

        # Get target unit
        canonical_unit = rule_data.get('canonical_unit', 'mcg')
        target_unit = to_unit or canonical_unit

        # Get conversion factor
        conversions = rule_data.get('conversions', {})
        if conversions is None:
            warnings = []
            if rule_data.get('warnings'):
                warnings.extend(rule_data['warnings'])

            handling = rule_data.get('handling', '')
            from_normalized = from_unit_lower.replace('µg', 'mcg').replace(' ', '_').strip()
            target_normalized = target_unit.lower().replace('µg', 'mcg').replace(' ', '_').strip()

            if handling == "flag_for_review":
                return ConversionResult(
                    success=True,
                    original_value=amount,
                    original_unit=from_unit,
                    converted_value=amount,
                    converted_unit=from_unit,
                    conversion_rule_id=rule_id,
                    conversion_factor=1.0,
                    nutrient_detected=nutrient,
                    form_detected=rule_data.get('standard_name'),
                    form_detection_source="no_conversion_possible",
                    confidence="low",
                    warnings=warnings,
                    notes=[rule_data.get('notes', '')] if rule_data.get('notes') else []
                )

            if from_normalized == target_normalized:
                # Some nutrients (like Vitamin K) don't need conversion if already canonical
                return ConversionResult(
                    success=True,
                    original_value=amount,
                    original_unit=from_unit,
                    converted_value=amount,
                    converted_unit=target_unit,
                    conversion_rule_id=rule_id,
                    conversion_factor=1.0,
                    nutrient_detected=nutrient,
                    form_detected=rule_data.get('standard_name'),
                    form_detection_source="no_conversion_needed",
                    confidence="high",
                    warnings=warnings,
                    notes=["No unit conversion needed for this nutrient"]
                )

            # Try mass conversion for nutrients expressed in mass units
            mass_result = self.convert_mass(amount, from_unit, target_unit)
            if mass_result.success:
                return ConversionResult(
                    success=True,
                    original_value=amount,
                    original_unit=from_unit,
                    converted_value=mass_result.converted_value,
                    converted_unit=mass_result.converted_unit,
                    conversion_rule_id="mass_conversion",
                    conversion_factor=mass_result.conversion_factor,
                    nutrient_detected=nutrient,
                    form_detected=rule_data.get('standard_name'),
                    form_detection_source="mass_conversion_fallback",
                    confidence="high",
                    warnings=warnings,
                    notes=["Used mass conversion (no IU conversion defined)"]
                )

            return ConversionResult(
                success=False,
                original_value=amount,
                original_unit=from_unit,
                converted_value=None,
                converted_unit=None,
                conversion_rule_id=rule_id,
                conversion_factor=None,
                nutrient_detected=nutrient,
                form_detected=rule_data.get('standard_name'),
                form_detection_source="conversion_missing",
                confidence="failed",
                warnings=warnings,
                error=f"No conversion available for {from_unit} -> {target_unit}"
            )

        # Determine conversion key
        conversion_key = self._get_conversion_key(from_unit_lower, target_unit.lower())
        factor = conversions.get(conversion_key)

        if factor is None:
            # Try mass conversion as fallback
            mass_result = self.convert_mass(amount, from_unit, target_unit)
            if mass_result.success:
                return ConversionResult(
                    success=True,
                    original_value=amount,
                    original_unit=from_unit,
                    converted_value=mass_result.converted_value,
                    converted_unit=mass_result.converted_unit,
                    conversion_rule_id="mass_conversion",
                    conversion_factor=mass_result.conversion_factor,
                    nutrient_detected=nutrient,
                    form_detected=None,
                    form_detection_source="mass_conversion_fallback",
                    confidence="high",
                    notes=["Used mass conversion (not IU-specific)"]
                )

            return ConversionResult(
                success=False,
                original_value=amount,
                original_unit=from_unit,
                converted_value=None,
                converted_unit=None,
                conversion_rule_id=rule_id,
                conversion_factor=None,
                nutrient_detected=nutrient,
                form_detected=rule_data.get('standard_name'),
                form_detection_source=None,
                confidence="failed",
                error=f"No conversion factor for {from_unit} -> {target_unit}"
            )

        # Perform conversion
        converted_value = amount * factor

        # Build result
        warnings = []
        if rule_data.get('warnings'):
            warnings.extend(rule_data['warnings'])

        # Check for Vitamin A unknown form
        if rule_id == 'vitamin_a_unknown':
            warnings.append("Vitamin A form unknown - flagged for review")

        # Determine form detection source
        form_source = "alias_match"
        if ingredient_name and ingredient_name.lower() != nutrient_lower:
            form_source = "ingredient_name_analysis"

        return ConversionResult(
            success=True,
            original_value=amount,
            original_unit=from_unit,
            converted_value=converted_value,
            converted_unit=target_unit,
            conversion_rule_id=rule_id,
            conversion_factor=factor,
            nutrient_detected=nutrient,
            form_detected=rule_data.get('standard_name'),
            form_detection_source=form_source,
            confidence="high" if rule_id != 'vitamin_a_unknown' else "low",
            warnings=warnings,
            notes=[rule_data.get('notes', '')] if rule_data.get('notes') else []
        )

    def _find_conversion_rule(
        self,
        nutrient: str,
        ingredient_text: str
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Find the appropriate conversion rule for a nutrient.

        IMPORTANT: For vitamins with form-dependent conversions (A, E, Folate),
        form detection runs FIRST before generic matching to ensure correct
        conversion factors are applied.
        """
        nutrient_lower = nutrient.lower()
        ingredient_lower = ingredient_text.lower()

        # CRITICAL: Form detection MUST run FIRST for form-dependent vitamins
        # Vitamin A: retinol (0.3) vs beta-carotene (0.1) - different UL implications
        if 'vitamin a' in nutrient_lower or 'retinol' in nutrient_lower or \
           'beta-carotene' in nutrient_lower or 'beta carotene' in nutrient_lower:
            return self._detect_vitamin_a_form(ingredient_lower)

        # Vitamin E: natural d-alpha (0.67) vs synthetic dl-alpha (0.45)
        if 'vitamin e' in nutrient_lower or 'tocopherol' in nutrient_lower:
            return self._detect_vitamin_e_form(ingredient_lower)

        # Folate: folic acid vs methylfolate
        if 'folate' in nutrient_lower or 'folic' in nutrient_lower:
            return self._detect_folate_form(ingredient_lower)

        # For non-form-dependent vitamins (D, K, B-vitamins, etc.), use direct match
        for rule_id, rule_data in self.vitamin_conversions.items():
            # Check standard name
            std_name = rule_data.get('standard_name', '').lower()
            if nutrient_lower in std_name or std_name in nutrient_lower:
                return rule_id, rule_data

            # Check aliases
            aliases = rule_data.get('aliases', [])
            for alias in aliases:
                if alias.lower() == nutrient_lower:
                    return rule_id, rule_data

        return None, None

    def _detect_vitamin_a_form(
        self,
        ingredient_text: str
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """Detect Vitamin A form from ingredient text."""
        patterns = self.form_patterns.get('vitamin_a', {})

        # Check retinol patterns
        for pattern in patterns.get('retinol_patterns', []):
            if re.search(pattern, ingredient_text, re.IGNORECASE):
                return 'vitamin_a_retinol', self.vitamin_conversions.get('vitamin_a_retinol', {})

        # Check beta-carotene patterns
        for pattern in patterns.get('beta_carotene_patterns', []):
            if re.search(pattern, ingredient_text, re.IGNORECASE):
                # Default to supplement form (more common in supplements)
                return 'vitamin_a_beta_carotene_supplement', \
                       self.vitamin_conversions.get('vitamin_a_beta_carotene_supplement', {})

        # Unknown form is expected on many raw labels; keep logs at debug to avoid noise.
        logger.debug("Vitamin A form not detected from: %s", ingredient_text)
        return 'vitamin_a_unknown', self.vitamin_conversions.get('vitamin_a_unknown', {})

    def _detect_vitamin_e_form(
        self,
        ingredient_text: str
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """Detect Vitamin E form (natural vs synthetic)."""
        patterns = self.form_patterns.get('vitamin_e', {})

        # Check natural patterns first
        for pattern in patterns.get('natural_patterns', []):
            if re.search(pattern, ingredient_text, re.IGNORECASE):
                return 'vitamin_e_d_alpha_tocopherol', \
                       self.vitamin_conversions.get('vitamin_e_d_alpha_tocopherol', {})

        # Check synthetic patterns
        for pattern in patterns.get('synthetic_patterns', []):
            if re.search(pattern, ingredient_text, re.IGNORECASE):
                return 'vitamin_e_dl_alpha_tocopherol', \
                       self.vitamin_conversions.get('vitamin_e_dl_alpha_tocopherol', {})

        # Default to synthetic (conservative)
        default = patterns.get('default_if_unknown', 'synthetic')
        if default == 'synthetic':
            return 'vitamin_e_dl_alpha_tocopherol', \
                   self.vitamin_conversions.get('vitamin_e_dl_alpha_tocopherol', {})
        else:
            return 'vitamin_e_d_alpha_tocopherol', \
                   self.vitamin_conversions.get('vitamin_e_d_alpha_tocopherol', {})

    def _detect_folate_form(
        self,
        ingredient_text: str
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """Detect Folate form."""
        text_lower = ingredient_text.lower()

        # Methylfolate
        if any(x in text_lower for x in ['methylfolate', '5-mthf', 'metafolin', 'quatrefolic']):
            return 'folate_methylfolate', self.vitamin_conversions.get('folate_methylfolate', {})

        # Folic acid
        if 'folic acid' in text_lower:
            return 'folate_folic_acid', self.vitamin_conversions.get('folate_folic_acid', {})

        # Default to folic acid
        return 'folate_folic_acid', self.vitamin_conversions.get('folate_folic_acid', {})

    def _get_conversion_key(self, from_unit: str, to_unit: str) -> str:
        """Get the conversion key for the database lookup."""
        from_normalized = from_unit.lower().replace('µg', 'mcg').replace(' ', '_').strip()
        to_normalized = to_unit.lower().replace('µg', 'mcg').replace(' ', '_').strip()

        return f"{from_normalized}_to_{to_normalized}"

    # =========================================================================
    # MASS CONVERSION
    # =========================================================================

    def convert_mass(
        self,
        amount: float,
        from_unit: str,
        to_unit: str
    ) -> ConversionResult:
        """
        Convert between mass units (g, mg, mcg).

        Args:
            amount: Amount in original units
            from_unit: Original unit
            to_unit: Target unit

        Returns:
            ConversionResult with converted value
        """
        from_lower = from_unit.lower().replace('µg', 'mcg').strip()
        to_lower = to_unit.lower().replace('µg', 'mcg').strip()

        # Same unit - no conversion needed
        if from_lower == to_lower:
            return ConversionResult(
                success=True,
                original_value=amount,
                original_unit=from_unit,
                converted_value=amount,
                converted_unit=to_unit,
                conversion_rule_id="same_unit",
                conversion_factor=1.0,
                nutrient_detected=None,
                form_detected=None,
                form_detection_source=None,
                confidence="high"
            )

        # Build conversion key
        conversion_key = f"{from_lower}_to_{to_lower}"
        factor = self.mass_rules.get(conversion_key)

        if factor is None:
            # Try computing from chain
            factor = self._compute_mass_factor(from_lower, to_lower)

        if factor is None:
            return ConversionResult(
                success=False,
                original_value=amount,
                original_unit=from_unit,
                converted_value=None,
                converted_unit=None,
                conversion_rule_id=None,
                conversion_factor=None,
                nutrient_detected=None,
                form_detected=None,
                form_detection_source=None,
                confidence="failed",
                error=f"No mass conversion for {from_unit} -> {to_unit}"
            )

        return ConversionResult(
            success=True,
            original_value=amount,
            original_unit=from_unit,
            converted_value=amount * factor,
            converted_unit=to_unit,
            conversion_rule_id="mass_conversion",
            conversion_factor=factor,
            nutrient_detected=None,
            form_detected=None,
            form_detection_source=None,
            confidence="high"
        )

    def _compute_mass_factor(self, from_unit: str, to_unit: str) -> Optional[float]:
        """Compute mass conversion factor by chaining."""
        # Define unit hierarchy: g > mg > mcg
        unit_to_mcg = {
            'g': 1_000_000,
            'mg': 1_000,
            'mcg': 1
        }

        if from_unit not in unit_to_mcg or to_unit not in unit_to_mcg:
            return None

        from_mcg = unit_to_mcg[from_unit]
        to_mcg = unit_to_mcg[to_unit]

        return from_mcg / to_mcg

    # =========================================================================
    # CFU CONVERSION
    # =========================================================================

    def normalize_cfu(
        self,
        amount: float,
        unit: str,
        qualifier_text: Optional[str] = None
    ) -> CFUResult:
        """
        Normalize probiotic CFU values.

        Args:
            amount: CFU amount
            unit: Unit string (e.g., "billion CFU", "CFU", "million CFU")
            qualifier_text: Text to check for "at expiration" etc.

        Returns:
            CFUResult with normalized value
        """
        unit_lower = unit.lower().strip()
        rules = self.probiotic_rules.get('rules', {})

        # Determine multiplier
        multiplier = 1
        if 'billion' in unit_lower:
            multiplier = rules.get('billion_cfu_to_cfu', 1_000_000_000)
        elif 'million' in unit_lower:
            multiplier = rules.get('million_cfu_to_cfu', 1_000_000)
        elif 'trillion' in unit_lower:
            multiplier = rules.get('trillion_cfu_to_cfu', 1_000_000_000_000)

        # Handle "viable cells" as CFU
        if 'viable' in unit_lower or 'live' in unit_lower:
            # Keep same multiplier
            pass

        normalized = amount * multiplier

        # Determine qualifier
        qualifier = "unqualified"
        confidence = "medium"
        notes = []

        if qualifier_text:
            qt_lower = qualifier_text.lower()
            if 'expir' in qt_lower or 'through expir' in qt_lower or 'at time of expir' in qt_lower:
                qualifier = "at_expiration"
                confidence = "high"
                notes.append("CFU guaranteed at expiration - highest confidence")
            elif 'manufactur' in qt_lower or 'at time of manufactur' in qt_lower:
                qualifier = "at_manufacture"
                confidence = "medium"
                notes.append("CFU at manufacture - expect some die-off")
        else:
            notes.append("No qualifier found - assume conservative estimate")

        # Format display value
        if normalized >= 1_000_000_000_000:
            display = f"{normalized / 1_000_000_000_000:.1f} trillion CFU"
        elif normalized >= 1_000_000_000:
            display = f"{normalized / 1_000_000_000:.1f} billion CFU"
        elif normalized >= 1_000_000:
            display = f"{normalized / 1_000_000:.1f} million CFU"
        else:
            display = f"{normalized:,.0f} CFU"

        return CFUResult(
            success=True,
            original_value=amount,
            original_unit=unit,
            normalized_cfu=normalized,
            display_value=display,
            qualifier=qualifier,
            confidence=confidence,
            notes=notes
        )

    # =========================================================================
    # BATCH CONVERSION
    # =========================================================================

    def convert_ingredient_list(
        self,
        ingredients: List[Dict]
    ) -> List[Dict]:
        """
        Convert all ingredients in a list to canonical units.

        Args:
            ingredients: List of ingredient dicts with 'name', 'amount', 'unit'

        Returns:
            List of ingredient dicts with added conversion evidence
        """
        results = []

        for ing in ingredients:
            name = ing.get('name', '')
            amount = ing.get('amount')
            unit = ing.get('unit', '')

            # Skip if no amount
            if amount is None:
                results.append({
                    **ing,
                    'conversion_evidence': {
                        'success': False,
                        'reason': 'No amount specified'
                    }
                })
                continue

            # Try to parse amount if string
            if isinstance(amount, str):
                try:
                    amount = float(amount.replace(',', ''))
                except ValueError:
                    results.append({
                        **ing,
                        'conversion_evidence': {
                            'success': False,
                            'reason': f'Cannot parse amount: {amount}'
                        }
                    })
                    continue

            # Check if this is a probiotic
            if any(x in name.lower() for x in ['probiotic', 'lactobacillus', 'bifidobacterium', 'cfu']):
                if 'cfu' in unit.lower() or 'viable' in unit.lower():
                    cfu_result = self.normalize_cfu(amount, unit, name)
                    results.append({
                        **ing,
                        'normalized_amount': cfu_result.normalized_cfu,
                        'normalized_unit': 'CFU',
                        'conversion_evidence': cfu_result.to_dict()
                    })
                    continue

            # Standard nutrient conversion
            result = self.convert_nutrient(
                nutrient=name,
                amount=amount,
                from_unit=unit,
                ingredient_name=name
            )

            results.append({
                **ing,
                'normalized_amount': result.converted_value,
                'normalized_unit': result.converted_unit,
                'conversion_evidence': result.to_dict()
            })

        return results


# Module-level convenience functions
_converter_instance = None


def get_converter() -> UnitConverter:
    """Get or create the singleton converter instance."""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = UnitConverter()
    return _converter_instance


def convert_nutrient(
    nutrient: str,
    amount: float,
    from_unit: str,
    to_unit: Optional[str] = None,
    ingredient_name: Optional[str] = None
) -> ConversionResult:
    """Convenience function for nutrient conversion."""
    return get_converter().convert_nutrient(
        nutrient, amount, from_unit, to_unit, ingredient_name
    )


def convert_mass(amount: float, from_unit: str, to_unit: str) -> ConversionResult:
    """Convenience function for mass conversion."""
    return get_converter().convert_mass(amount, from_unit, to_unit)


def normalize_cfu(
    amount: float,
    unit: str,
    qualifier_text: Optional[str] = None
) -> CFUResult:
    """Convenience function for CFU normalization."""
    return get_converter().normalize_cfu(amount, unit, qualifier_text)
