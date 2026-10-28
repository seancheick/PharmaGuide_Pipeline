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
from typing import Dict, List, Optional, Tuple

from constants import UNIT_CONVERSIONS_DB
from normalization import (
    FOLATE_FORM_FOLIC_ACID,
    FOLATE_FORM_FOOD,
    FOLATE_FORM_METHYLFOLATE,
    canonicalize_mass_unit,
    classify_folate_form,
)

logger = logging.getLogger(__name__)

# Rules this module selects by name; a database without one would silently
# leave that form unconverted. test_reference_loaders_fail_closed keeps the
# set in step with every rule id written below.
REQUIRED_VITAMIN_RULES = frozenset({
    'choline_bitartrate_to_choline',
    'folate_folic_acid',
    'folate_food',
    'folate_methylfolate',
    'folate_unknown',
    'inositol_hexanicotinate_to_niacin_equivalents',
    'magnesium_hydroxide_to_magnesium',
    'niacin',
    'vitamin_a_beta_carotene_supplement',
    'vitamin_a_other_provitamin_a_carotenoid',
    'vitamin_a_retinol',
    'vitamin_a_unknown',
    'vitamin_d2',
    'vitamin_d3',
    'vitamin_e_d_alpha_tocopherol',
    'vitamin_e_dl_alpha_tocopherol',
    'vitamin_e_label_mg_alpha_tocopherol',
    'vitamin_e_unknown',
})
# Form-detection pattern lists read by _detect_vitamin_a_form / _detect_vitamin_e_form.
REQUIRED_FORM_PATTERNS = {
    'vitamin_a': ('retinol_patterns', 'beta_carotene_patterns',
                  'other_provitamin_a_carotenoid_patterns'),
    'vitamin_e': ('natural_patterns', 'synthetic_patterns'),
}


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

    @property
    def has_established_vitamin_e_activity(self) -> bool:
        """Known alpha-tocopherol activity, distinct from physical family mass.

        The converter owns form detection and FDA parent-label activity. An
        unknown-form physical mass or conservative UL bound cannot grant
        nutritional activity or meet an alpha-tocopherol threshold.
        """
        return bool(
            self.success
            and (self.conversion_rule_id or "").startswith("vitamin_e_")
            and self.conversion_rule_id != "vitamin_e_unknown"
        )

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
        self.db_path = UNIT_CONVERSIONS_DB if db_path is None else db_path
        self.db = None
        self.vitamin_conversions = {}
        self.mass_rules = {}
        self.form_patterns = {}
        self.version = "unknown"

        self._load_database()

    def _load_database(self) -> None:
        """Load the unit conversions database.

        Clean and Enrich both convert through this table, so a missing,
        unreadable or rule-less file stops the run instead of leaving every
        conversion to report "no rule".
        """
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                self.db = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"FATAL: Failed to load unit conversions database {self.db_path}: {e}"
            ) from e

        problems = self._structure_problems(self.db)
        if problems:
            raise RuntimeError(
                f"FATAL: unit conversions database {self.db_path} is incomplete: "
                + "; ".join(problems)
            )

        self.version = self.db.get('_metadata', {}).get('version', 'unknown')
        self.vitamin_conversions = self.db['vitamin_conversions']
        self.mass_rules = self.db['mass_conversions']['rules']
        self.form_patterns = self.db['form_detection_patterns']

        logger.info("Loaded unit_conversions.json v%s with %d vitamin rules",
                   self.version, len(self.vitamin_conversions))

    @staticmethod
    def _structure_problems(db) -> List[str]:
        """What a loaded database lacks for the conversions this module makes."""
        if not isinstance(db, dict):
            return ["top level is not an object"]
        problems = []
        rules = db.get('vitamin_conversions')
        if not isinstance(rules, dict) or not rules:
            problems.append("vitamin_conversions is not a non-empty object")
        else:
            missing = sorted(REQUIRED_VITAMIN_RULES - set(rules))
            if missing:
                problems.append(f"missing vitamin rules {missing}")
            # "conversions": null is authored ("no IU conversion", unknown form).
            malformed = sorted(
                rule_id for rule_id, rule in rules.items()
                if not isinstance(rule, dict) or 'conversions' not in rule
                or not isinstance(rule['conversions'], (dict, type(None)))
            )
            if malformed:
                problems.append(f"rules without a conversions object or null {malformed}")
        mass = db.get('mass_conversions')
        if not isinstance(mass, dict) or not isinstance(mass.get('rules'), dict) or not mass['rules']:
            problems.append("mass_conversions.rules is not a non-empty object")
        patterns = db.get('form_detection_patterns')
        if not isinstance(patterns, dict):
            problems.append("form_detection_patterns is not an object")
        else:
            for nutrient, keys in REQUIRED_FORM_PATTERNS.items():
                block = patterns.get(nutrient)
                bad = [k for k in keys if not isinstance(block, dict) or not isinstance(block.get(k), list)]
                if bad:
                    problems.append(f"form_detection_patterns.{nutrient} lacks {bad}")
        return problems

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
        ingredient_name: Optional[str] = None,
        measured_name: Optional[str] = None,
    ) -> ConversionResult:
        """
        Convert a nutrient amount from one unit to another.

        Args:
            nutrient: Nutrient name (e.g., "Vitamin D3", "Vitamin A")
            amount: Amount in original units
            from_unit: Original unit (e.g., "IU", "mg", "mcg")
            to_unit: Target unit. If None, converts to canonical unit.
            ingredient_name: Full ingredient name for form detection
            measured_name: The label row's own name, when known. Active-moiety
                conversions fire only when it names the compound: "Magnesium
                50 mg (as magnesium hydroxide)" declares 50 mg of magnesium
                (21 CFR 101.36); "Magnesium Hydroxide 2.6 g" measures the salt.

        Returns:
            ConversionResult with converted value and evidence
        """
        # Normalize inputs
        nutrient_lower = nutrient.lower().strip()
        from_unit_lower = canonicalize_mass_unit(from_unit)
        ingredient_text = ingredient_name or nutrient

        # Find matching conversion rule
        rule_id, rule_data = self._find_conversion_rule(
            nutrient_lower, ingredient_text, measured_name
        )

        # Since the 2020 Supplement Facts unit transition, a parent row headed
        # "Vitamin E" declares alpha-tocopherol activity. Plain mass aliases
        # change its scale, not that basis. Form is also needed to distinguish
        # nutritional activity from physical UL mass. Keep standalone ingredient
        # masses outside this rule by requiring the parent nutrient heading.
        if (
            rule_id == 'vitamin_e_unknown'
            and from_unit_lower in {'mg', 'mg at', 'g', 'mcg'}
            and re.match(r'^vitamin\s+e\b', measured_name or ingredient_text, re.IGNORECASE)
        ):
            rule_id = 'vitamin_e_label_mg_alpha_tocopherol'
            rule_data = self.vitamin_conversions.get(rule_id, {})

        if rule_id is None:
            # No specific vitamin/mineral conversion rule found.
            # Try mass conversion if a different target unit was requested
            # (e.g. mg → mcg for "Generic" nutrient).
            standard_mass_units = {'mg', 'mcg', 'g'}
            target_for_fallback = to_unit or from_unit
            if from_unit_lower in standard_mass_units:
                target_lower = canonicalize_mass_unit(target_for_fallback)
                # If from and to are the same unit (or to is unspecified),
                # this is an identity pass-through — nutrient is already in
                # its canonical unit (e.g. Vitamin C in mg, Calcium in mg).
                if target_lower == from_unit_lower or to_unit is None:
                    return ConversionResult(
                        success=True,
                        original_value=amount,
                        original_unit=from_unit,
                        converted_value=amount,
                        converted_unit=from_unit_lower,
                        conversion_rule_id="identity_mass_passthrough",
                        conversion_factor=1.0,
                        nutrient_detected=nutrient,
                        form_detected=None,
                        form_detection_source="no_conversion_needed",
                        confidence="high",
                        notes=[f"Nutrient already in standard mass unit ({from_unit_lower}); no conversion rule required"]
                    )
                # Different target unit — try mass conversion (e.g. mg → mcg)
                mass_result = self.convert_mass(amount, from_unit, target_for_fallback)
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
                        notes=["No specific rule; used mass conversion"]
                    )
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
        conversions = rule_data.get('conversions', {})

        # DSLD uses ``U`` and ``UI`` as label spellings of International Units.
        # Apply the alias only when the selected nutrient rule explicitly
        # declares an IU conversion. Enzyme rules such as lysozyme have no
        # ``iu_to_*`` conversion and therefore remain activity units.
        supports_iu = isinstance(conversions, dict) and any(
            str(key).startswith('iu_to_') for key in conversions
        )
        if supports_iu and from_unit_lower in {'u', 'ui'}:
            from_unit_lower = 'iu'

        # FDA Vitamin E reference amounts are expressed as milligrams of
        # alpha-tocopherol. DSLD's ``mg AT`` spelling is therefore the same
        # mass basis, but only after the form detector has selected a known
        # alpha-tocopherol rule.
        if (
            rule_id in {
                'vitamin_e_d_alpha_tocopherol',
                'vitamin_e_dl_alpha_tocopherol',
                'vitamin_e_label_mg_alpha_tocopherol',
            }
            and from_unit_lower == 'mg at'
        ):
            from_unit_lower = 'mg'

        # DSLD occasionally preserves the FDA Vitamin A quantity but drops the
        # ``RAE`` qualifier from the unit.  That shorthand is safe to interpret
        # only after the form detector has positively established preformed
        # retinol/retinyl ester; never apply it to generic Vitamin A or
        # beta-carotene.
        if rule_id == 'vitamin_a_retinol' and from_unit_lower == 'mcg':
            from_unit_lower = 'mcg rae'

        # A row headed "Vitamin A" declares vitamin-A activity in RAE even
        # when its source is beta-carotene. Only a standalone Beta-Carotene
        # mass receives the 0.5 supplemental conversion factor.
        if (
            rule_id == 'vitamin_a_beta_carotene_supplement'
            and from_unit_lower == 'mcg'
            and re.match(r'^vitamin\s+a\b', ingredient_text, re.IGNORECASE)
        ):
            from_unit_lower = 'mcg rae'

        # DSLD sometimes omits the RAE/DFE qualifier while retaining the
        # parent Supplement Facts heading.  The parent amount is already the
        # declared nutrient-equivalent amount; only its mass scale changes.
        # Keep standalone beta-carotene and identified folate forms on their
        # form-specific conversion rules.
        label_equivalent_target = None
        if (
            rule_id == 'vitamin_a_beta_carotene_supplement'
            and from_unit_lower in {'g', 'mg', 'mcg'}
            and re.match(r'^vitamin\s+a\b', ingredient_text, re.IGNORECASE)
        ):
            label_equivalent_target = 'mcg RAE'
        if label_equivalent_target is not None:
            mass_result = self.convert_mass(amount, from_unit, 'mcg')
            if mass_result.success:
                return ConversionResult(
                    success=True,
                    original_value=amount,
                    original_unit=from_unit,
                    converted_value=mass_result.converted_value,
                    converted_unit=label_equivalent_target,
                    conversion_rule_id=rule_id,
                    conversion_factor=mass_result.conversion_factor,
                    nutrient_detected=nutrient,
                    form_detected=rule_data.get('standard_name'),
                    form_detection_source='parent_label_equivalent_unit',
                    confidence='high',
                    notes=[
                        'Parent Supplement Facts nutrient amount retains its '
                        f'{label_equivalent_target.split()[-1]} basis.'
                    ],
                )

        # Get conversion factor
        if conversions is None:
            warnings = []
            if rule_data.get('warnings'):
                warnings.extend(rule_data['warnings'])

            handling = rule_data.get('handling', '')
            from_normalized = canonicalize_mass_unit(from_unit_lower).replace(' ', '_')
            target_normalized = canonicalize_mass_unit(target_unit).replace(' ', '_')

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

        from_key = canonicalize_mass_unit(from_unit_lower).replace(' ', '_')
        target_key = canonicalize_mass_unit(target_unit).replace(' ', '_')
        mass_scale_applied = False
        if factor is None and from_key == target_key:
            factor = 1.0
        if (
            factor is None
            and rule_id == 'vitamin_a_beta_carotene_supplement'
            and from_key == 'mcg'
            and target_key == 'mcg_rae'
        ):
            factor = conversions.get('mcg_beta_carotene_to_mcg_rae')
        if (
            factor is None
            and rule_id == 'vitamin_a_other_provitamin_a_carotenoid'
            and from_key == 'mcg'
            and target_key == 'mcg_rae'
        ):
            factor = conversions.get('mcg_carotenoid_to_mcg_rae')
        if factor is None and from_key in {'g', 'mg', 'mcg'}:
            # Compose physical mass scaling with an explicitly authored
            # nutrient conversion (e.g. g -> mg -> mg NE). Never invent a
            # nutrient-equivalence factor or use IU as a mass bridge.
            for bridge_unit in ('g', 'mg', 'mcg'):
                authored_factor = conversions.get(
                    self._get_conversion_key(bridge_unit, target_unit)
                )
                if authored_factor is None:
                    continue
                mass_result = self.convert_mass(amount, from_unit, bridge_unit)
                if mass_result.success:
                    factor = mass_result.conversion_factor * authored_factor
                    mass_scale_applied = True
                    break
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
                    # A scale conversion must not erase the selected Vitamin E
                    # form: its activity and UL mass can have different bases.
                    conversion_rule_id=(rule_id if rule_id.startswith('vitamin_e_') else "mass_conversion"),
                    conversion_factor=mass_result.conversion_factor,
                    nutrient_detected=nutrient,
                    form_detected=(rule_data.get('standard_name') if rule_id.startswith('vitamin_e_') else None),
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
            confidence=(
                "low"
                if rule_id in {'vitamin_a_unknown', 'vitamin_e_unknown', 'folate_unknown'}
                else "high"
            ),
            warnings=warnings,
            notes=(
                ([rule_data['notes']] if rule_data.get('notes') else [])
                + (['Scaled source mass before the authored nutrient conversion.']
                   if mass_scale_applied else [])
            )
        )

    def _ul_exposure_amount(
        self, conversion: ConversionResult, *, measured_name: str,
    ) -> Optional[float]:
        """Vitamin E UL mass, separate from label nutritional activity.

        Unknown IU/parent-mg forms return the conservative (upper) bound only;
        the caller must preserve indeterminate lineage unless that bound is low.
        """
        bounds = self._ul_exposure_bounds(conversion, measured_name=measured_name)
        return bounds[1] if bounds else None

    def _ul_exposure_bounds(
        self, conversion: ConversionResult, *, measured_name: str,
    ) -> Optional[Tuple[float, float]]:
        """Lowest and highest Vitamin E UL mass (mg) the label can mean.

        NIH ODS: the UL counts all eight synthetic stereoisomers, whereas
        nutritional activity counts half of all-rac alpha-tocopherol mass.
        A known form has one value; an undisclosed form spans natural (the
        activity mass) to synthetic (twice it). Standalone compound masses
        are not FDA parent nutrient declarations.
        https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/
        """
        rule = conversion.conversion_rule_id
        parent = bool(re.match(r"^vitamin\s+e\b", measured_name, re.I))
        iu = canonicalize_mass_unit(conversion.original_unit) in {"iu", "u", "ui"}
        if rule == "vitamin_e_unknown" and iu:
            natural, synthetic = (
                self.vitamin_conversions[form]["conversions"]["iu_to_mg"]
                for form in ("vitamin_e_d_alpha_tocopherol", "vitamin_e_dl_alpha_tocopherol")
            )
            return conversion.original_value * natural, conversion.original_value * synthetic * 2.0
        amount = conversion.converted_value
        if amount is None:
            return None
        mass = self.convert_mass(amount, conversion.converted_unit or "", "mg")
        if not mass.success or mass.converted_value is None:
            return None
        amount = mass.converted_value
        if rule == "vitamin_e_dl_alpha_tocopherol" and (parent or iu):
            return amount * 2.0, amount * 2.0
        if rule == "vitamin_e_label_mg_alpha_tocopherol" and parent:
            return amount, amount * 2.0
        return amount, amount

    def _find_conversion_rule(
        self,
        nutrient: str,
        ingredient_text: str,
        measured_name: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Find the appropriate conversion rule for a nutrient.

        IMPORTANT: For vitamins with form-dependent conversions (A, E, Folate),
        form detection runs FIRST before generic matching to ensure correct
        conversion factors are applied.
        """
        nutrient_lower = nutrient.lower()
        ingredient_lower = ingredient_text.lower()
        # A parenthetical in the row name names the source, not the measured compound.
        compound_lower = (
            measured_name.split('(')[0].lower() if measured_name else ingredient_lower
        )

        if (
            'choline' in nutrient_lower
            and re.search(r'\bcholine\s+(?:l[- ]|dl[- ])?bitartrate\b|\bcholine\s+tartrate\b', compound_lower)
        ):
            return 'choline_bitartrate_to_choline', self.vitamin_conversions.get(
                'choline_bitartrate_to_choline', {}
            )
        if (
            'magnesium' in nutrient_lower
            and re.search(r'\bmagnesium\s+hydroxide\b|\bmilk\s+of\s+magnesia\b', compound_lower)
        ):
            return (
                'magnesium_hydroxide_to_magnesium',
                self.vitamin_conversions.get(
                    'magnesium_hydroxide_to_magnesium', {}
                ),
            )
        if (
            ('niacin' in nutrient_lower or 'vitamin b3' in nutrient_lower)
            and re.search(
                r'\b(?:inositol\s+(?:hexa)?(?:nicotinate|niacinate)|hexanicotol)\b',
                compound_lower,
            )
        ):
            return (
                'inositol_hexanicotinate_to_niacin_equivalents',
                self.vitamin_conversions.get(
                    'inositol_hexanicotinate_to_niacin_equivalents', {}
                ),
            )

        # CRITICAL: Form detection MUST run FIRST for form-dependent vitamins
        # Vitamin A: retinol and supplemental beta-carotene both 0.3 mcg RAE/IU; only preformed retinol carries a UL
        if 'vitamin a' in nutrient_lower or 'retinol' in nutrient_lower or \
           'beta-carotene' in nutrient_lower or 'beta carotene' in nutrient_lower or \
           'alpha-carotene' in nutrient_lower or 'alpha carotene' in nutrient_lower or \
           'cryptoxanthin' in nutrient_lower:
            return self._detect_vitamin_a_form(ingredient_lower)

        # Vitamin E: natural d-alpha (0.67) vs synthetic dl-alpha (0.45)
        if 'vitamin e' in nutrient_lower or 'tocopherol' in nutrient_lower or 'tocotrienol' in nutrient_lower:
            return self._detect_vitamin_e_form(ingredient_lower)

        # Folate: folic acid vs methylfolate
        if 'folate' in nutrient_lower or 'folic' in nutrient_lower:
            return self._detect_folate_form(ingredient_lower)

        # Vitamin D2 and D3 share the same IU/mcg factor, but preserving a
        # label-confirmed form in the conversion trace is still clinically and
        # operationally important.  A generic parent name must not silently
        # report D3 when the label says ergocalciferol/D2.
        if 'vitamin d' in nutrient_lower:
            if re.search(r'\b(?:ergocalciferol|vitamin\s*d[- ]?2|d[- ]?2)\b', ingredient_lower):
                return 'vitamin_d2', self.vitamin_conversions.get('vitamin_d2', {})
            if re.search(r'\b(?:cholecalciferol|vitamin\s*d[- ]?3|d[- ]?3)\b', ingredient_lower):
                return 'vitamin_d3', self.vitamin_conversions.get('vitamin_d3', {})

        # For non-form-dependent vitamins (D, K, B-vitamins, etc.), use direct match
        nutrient_heading = nutrient_lower.split('(', 1)[0].strip()
        # A parent family label may use the shared conversion only when the
        # authored numbered forms all agree. This retains Vitamin D's common
        # D2/D3 IU factor without allowing arbitrary chemical-name substrings.
        family_rules = [
            data for data in self.vitamin_conversions.values()
            if nutrient_heading and re.fullmatch(
                re.escape(nutrient_heading) + r'\d+',
                data.get('standard_name', '').lower().split('(', 1)[0].strip(),
            )
        ]
        shared_family_conversion = len(family_rules) > 1 and len({
            (data.get('canonical_unit'), data.get('handling'),
             json.dumps(data.get('conversions'), sort_keys=True))
            for data in family_rules
        }) == 1
        for rule_id, rule_data in self.vitamin_conversions.items():
            if rule_id in {
                'choline_bitartrate_to_choline',
                'magnesium_hydroxide_to_magnesium',
                'inositol_hexanicotinate_to_niacin_equivalents',
            }:
                # Active-moiety conversions require the exact compound checks
                # above. Their parent nutrient names must never select them.
                continue
            # Match complete nutrient headings, including a parenthetical
            # label form. A chemical name containing an alias is not that
            # substance: nicotinamide mononucleotide is not nicotinamide.
            std_name = rule_data.get('standard_name', '').lower()
            standard_heading = std_name.split('(', 1)[0].strip()
            if nutrient_lower == std_name or (
                nutrient_heading and nutrient_heading == standard_heading
            ) or (
                shared_family_conversion and re.fullmatch(
                    re.escape(nutrient_heading) + r'\d+', standard_heading,
                )
            ):
                return rule_id, rule_data

            aliases = rule_data.get('aliases', [])
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in {nutrient_lower, nutrient_heading}:
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
                # DSLD is a dietary-supplement label source. A food-matrix
                # factor would require a separately typed source contract.
                return 'vitamin_a_beta_carotene_supplement', \
                       self.vitamin_conversions.get('vitamin_a_beta_carotene_supplement', {})

        for pattern in patterns.get('other_provitamin_a_carotenoid_patterns', []):
            if re.search(pattern, ingredient_text, re.IGNORECASE):
                return 'vitamin_a_other_provitamin_a_carotenoid', \
                       self.vitamin_conversions.get(
                           'vitamin_a_other_provitamin_a_carotenoid', {}
                       )

        # Unknown form is expected on many raw labels; keep logs at debug to avoid noise.
        logger.debug("Vitamin A form not detected from: %s", ingredient_text)
        return 'vitamin_a_unknown', self.vitamin_conversions.get('vitamin_a_unknown', {})

    def _detect_vitamin_e_form(
        self,
        ingredient_text: str
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """Detect Vitamin E form (natural vs synthetic)."""
        patterns = self.form_patterns.get('vitamin_e', {})

        # Alpha stereochemistry is not the alpha-tocopherol molecule. Explicit
        # tocotrienol material (including mixtures) cannot establish an exact
        # tocopherol activity amount through broad d-alpha/all-rac patterns.
        # Parent Vitamin E label activity is handled separately by the caller.
        if re.search(r'\btocotrienols?\b', ingredient_text, re.I):
            return 'vitamin_e_unknown', self.vitamin_conversions.get('vitamin_e_unknown', {})

        natural = any(re.search(p, ingredient_text, re.I)
                      for p in patterns.get('natural_patterns', []))
        synthetic = any(re.search(p, ingredient_text, re.I)
                        for p in patterns.get('synthetic_patterns', []))
        # A mixed declaration has no exact IU-to-activity conversion. Keep
        # that uncertainty in the existing unknown-form rule; the UL caller
        # can screen its conservative all-stereoisomer bound separately.
        if natural and not synthetic:
            rule = 'vitamin_e_d_alpha_tocopherol'
        elif synthetic and not natural:
            rule = 'vitamin_e_dl_alpha_tocopherol'
        else:
            rule = 'vitamin_e_unknown'
        return rule, self.vitamin_conversions.get(rule, {})

    def _detect_folate_form(
        self,
        ingredient_text: str
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """Detect Folate form."""
        form = classify_folate_form(ingredient_text)

        if form == FOLATE_FORM_FOOD:
            return 'folate_food', self.vitamin_conversions.get('folate_food', {})

        if form == FOLATE_FORM_METHYLFOLATE:
            return 'folate_methylfolate', self.vitamin_conversions.get('folate_methylfolate', {})

        if form == FOLATE_FORM_FOLIC_ACID:
            return 'folate_folic_acid', self.vitamin_conversions.get('folate_folic_acid', {})

        # Bare folate and recognized forms without an authorized conversion
        # factor (including folinic acid) stay conversion-unknown. Preserve an
        # explicit DFE declaration, but never borrow methylfolate's factor.
        return 'folate_unknown', self.vitamin_conversions.get('folate_unknown', {})

    def _get_conversion_key(self, from_unit: str, to_unit: str) -> str:
        """Get the conversion key for the database lookup."""
        from_normalized = canonicalize_mass_unit(from_unit).replace(' ', '_')
        to_normalized = canonicalize_mass_unit(to_unit).replace(' ', '_')

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
        from_lower = canonicalize_mass_unit(from_unit)
        to_lower = canonicalize_mass_unit(to_unit)

        # Same unit - no conversion needed
        if from_lower == to_lower:
            return ConversionResult(
                success=True,
                original_value=amount,
                original_unit=from_unit,
                converted_value=amount,
                converted_unit=to_lower,
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
            converted_unit=to_lower,
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
