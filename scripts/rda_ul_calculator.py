#!/usr/bin/env python3
"""
RDA/UL Adequacy Calculator Module

Computes nutrient adequacy scores based on RDA/AI, optimal ranges, and UL values.
Outputs structured evidence for scoring consumption.

Key features:
- RDA/AI percentage calculation
- UL comparison with safety flags
- Adequacy band classification
- "No UL" policy handling
- Full evidence tracking

Usage:
    from rda_ul_calculator import RDAULCalculator

    calculator = RDAULCalculator()
    result = calculator.compute_nutrient_adequacy(
        nutrient="Vitamin D3",
        amount=50,
        unit="mcg"
    )
"""

import json
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


# Adequacy bands per spec
ADEQUACY_BANDS = {
    "deficient": {"min_pct": 0, "max_pct": 25, "points": 0},
    "suboptimal": {"min_pct": 25, "max_pct": 75, "points": 1},
    "optimal": {"min_pct": 75, "max_pct": 150, "points": 3},
    "high": {"min_pct": 150, "max_pct": 300, "points": 2},
    "excessive": {"min_pct": 300, "max_pct": float('inf'), "points": 0}
}


@dataclass
class NutrientAdequacyResult:
    """Result of nutrient adequacy calculation."""
    nutrient: str
    amount: float
    unit: str
    rda_ai: Optional[float]
    rda_ai_source: str  # "rda" or "ai" (adequate intake)
    ul: Optional[float]
    ul_status: str  # "established", "not_determined", "not_applicable"
    optimal_min: Optional[float]
    optimal_max: Optional[float]
    pct_rda: Optional[float]
    pct_ul: Optional[float]
    adequacy_band: str
    over_ul: bool
    over_ul_amount: Optional[float]
    scoring_eligible: bool
    point_recommendation: int  # What scoring COULD award
    notes: List[str]
    warnings: List[str]
    age_group: str
    sex_group: str

    def to_dict(self) -> Dict:
        return {
            "nutrient": self.nutrient,
            "amount": self.amount,
            "unit": self.unit,
            "rda_ai": self.rda_ai,
            "rda_ai_source": self.rda_ai_source,
            "ul": self.ul,
            "ul_status": self.ul_status,
            "optimal_min": self.optimal_min,
            "optimal_max": self.optimal_max,
            "pct_rda": self.pct_rda,
            "pct_ul": self.pct_ul,
            "adequacy_band": self.adequacy_band,
            "over_ul": self.over_ul,
            "over_ul_amount": self.over_ul_amount,
            "scoring_eligible": self.scoring_eligible,
            "point_recommendation": self.point_recommendation,
            "notes": self.notes,
            "warnings": self.warnings,
            "age_group": self.age_group,
            "sex_group": self.sex_group
        }


@dataclass
class SafetyFlag:
    """Safety flag for over-UL nutrients."""
    nutrient: str
    amount: float
    unit: str
    ul: float
    pct_ul: float
    over_amount: float
    warning: str
    severity: str  # "caution", "warning", "critical"

    def to_dict(self) -> Dict:
        return {
            "nutrient": self.nutrient,
            "amount": self.amount,
            "unit": self.unit,
            "ul": self.ul,
            "pct_ul": self.pct_ul,
            "over_amount": self.over_amount,
            "warning": self.warning,
            "severity": self.severity
        }


class RDAULCalculator:
    """
    Calculates nutrient adequacy based on RDA/AI and UL values.

    Outputs evidence data for scoring consumption - does NOT compute
    final scores (that's the scorer's job).
    """

    # Age group normalization
    AGE_NORMALIZATION = {
        "14-18": "14-18",
        "19-30": "19-30",
        "31-50": "31-50",
        "51-70": "51-70",
        "71+": "71+",
        "adult": "19-30",  # Default adult
        "default": "19-30"
    }

    # Sex group normalization
    SEX_NORMALIZATION = {
        "male": "Male",
        "m": "Male",
        "female": "Female",
        "f": "Female",
        "both": "Male",  # Use male as default when both
        "default": "Male"
    }

    def __init__(self, rda_db_path: Optional[Path] = None):
        """
        Initialize the calculator.

        Args:
            rda_db_path: Path to rda_optimal_uls.json.
                        If None, uses default location.
        """
        if rda_db_path is None:
            rda_db_path = Path(__file__).parent / "data" / "rda_optimal_uls.json"

        self.rda_db = self._load_rda_db(rda_db_path)
        self._build_nutrient_lookup()

    def _load_rda_db(self, path: Path) -> Dict:
        """Load the RDA/UL database."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load RDA database: {e}")
            return {"nutrient_recommendations": [], "_metadata": {}}

    def _build_nutrient_lookup(self):
        """Build fast lookup for nutrients by name."""
        self.nutrient_lookup = {}
        self.nutrient_aliases = {}

        for nutrient in self.rda_db.get("nutrient_recommendations", []):
            std_name = nutrient.get("standard_name", "")
            nutrient_id = nutrient.get("id", "")

            # Index by standard name
            key = self._normalize_nutrient_name(std_name)
            self.nutrient_lookup[key] = nutrient

            # Index by id
            if nutrient_id:
                self.nutrient_lookup[nutrient_id.lower()] = nutrient

            # Add common aliases
            aliases = nutrient.get("aliases", [])
            for alias in aliases:
                alias_key = self._normalize_nutrient_name(alias)
                self.nutrient_aliases[alias_key] = key

    def _normalize_nutrient_name(self, name: str) -> str:
        """Normalize nutrient name for lookup."""
        if not name:
            return ""
        # Lowercase, remove special chars, normalize spaces
        normalized = name.lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', '_', normalized.strip())
        return normalized

    def compute_nutrient_adequacy(
        self,
        nutrient: str,
        amount: float,
        unit: str,
        age_group: str = "19-30",
        sex: str = "both"
    ) -> NutrientAdequacyResult:
        """
        Compute nutrient adequacy with full evidence.

        Args:
            nutrient: Nutrient name (will be normalized)
            amount: Amount per serving (already unit-converted)
            unit: Unit of amount
            age_group: Age range (e.g., "19-30", "51-70")
            sex: "male", "female", or "both"

        Returns:
            NutrientAdequacyResult with all evidence
        """
        notes = []
        warnings = []

        # Normalize inputs
        norm_age = self.AGE_NORMALIZATION.get(age_group, self.AGE_NORMALIZATION["default"])
        norm_sex = self.SEX_NORMALIZATION.get(sex.lower() if sex else "both", self.SEX_NORMALIZATION["default"])

        # Find nutrient data
        nutrient_data = self._find_nutrient(nutrient)

        if not nutrient_data:
            return NutrientAdequacyResult(
                nutrient=nutrient,
                amount=amount,
                unit=unit,
                rda_ai=None,
                rda_ai_source="unknown",
                ul=None,
                ul_status="unknown",
                optimal_min=None,
                optimal_max=None,
                pct_rda=None,
                pct_ul=None,
                adequacy_band="unknown",
                over_ul=False,
                over_ul_amount=None,
                scoring_eligible=False,
                point_recommendation=0,
                notes=[f"Nutrient '{nutrient}' not found in RDA database"],
                warnings=[],
                age_group=norm_age,
                sex_group=norm_sex
            )

        # Get age/sex specific values
        rda_ai, ul = self._get_age_sex_values(nutrient_data, norm_age, norm_sex)

        # Determine RDA source
        rda_source = "rda"
        if rda_ai is None:
            # Check for AI value
            ai_data = self._get_ai_value(nutrient_data, norm_age, norm_sex)
            if ai_data:
                rda_ai = ai_data
                rda_source = "ai"

        # Check UL status
        ul_status = self._determine_ul_status(nutrient_data, ul)

        # Get optimal range
        optimal_min, optimal_max = self._parse_optimal_range(nutrient_data.get("optimal_range", ""))

        # Calculate percentages
        pct_rda = None
        if rda_ai and rda_ai > 0:
            pct_rda = (amount / rda_ai) * 100
            notes.append(f"{pct_rda:.1f}% of RDA/AI ({rda_ai} {nutrient_data.get('unit', unit)})")

        pct_ul = None
        over_ul = False
        over_ul_amount = None
        if ul and ul > 0 and ul_status == "established":
            pct_ul = (amount / ul) * 100
            if amount > ul:
                over_ul = True
                over_ul_amount = amount - ul
                warnings.append(f"Exceeds UL by {over_ul_amount:.1f} {unit}")

        # Determine adequacy band. Magnesium is a special case because the UL
        # applies to supplemental intake only while the RDA is total intake.
        uses_supplement_only_ul = self._uses_supplement_only_ul_policy(nutrient_data)
        if over_ul and uses_supplement_only_ul:
            notes.append("Supplemental magnesium has a separate UL from the total-intake RDA.")
            warnings.append(
                f"Supplemental magnesium exceeds the adult supplemental UL by {over_ul_amount:.1f} {unit}"
            )
        adequacy_band = self._determine_adequacy_band(
            pct_rda,
            over_ul and not uses_supplement_only_ul
        )

        # Handle "no UL" policy
        if ul_status == "not_determined":
            notes.append("No UL established for this nutrient")
            # Flag extreme doses (>10x RDA) for information only
            if pct_rda and pct_rda > 1000:
                notes.append(f"Note: Amount is {pct_rda/100:.1f}x RDA (informational only, no UL applies)")

        # Get point recommendation from band
        point_recommendation = ADEQUACY_BANDS.get(adequacy_band, {}).get("points", 0)

        # Determine scoring eligibility
        scoring_eligible = True
        if pct_rda is None:
            scoring_eligible = False
            notes.append("No RDA/AI found - not scored")
        elif adequacy_band == "excessive" or over_ul:
            # Still eligible but points may be 0 or negative
            pass

        return NutrientAdequacyResult(
            nutrient=nutrient,
            amount=amount,
            unit=unit,
            rda_ai=rda_ai,
            rda_ai_source=rda_source,
            ul=ul if ul_status == "established" else None,
            ul_status=ul_status,
            optimal_min=optimal_min,
            optimal_max=optimal_max,
            pct_rda=pct_rda,
            pct_ul=pct_ul,
            adequacy_band=adequacy_band,
            over_ul=over_ul,
            over_ul_amount=over_ul_amount,
            scoring_eligible=scoring_eligible,
            point_recommendation=point_recommendation,
            notes=notes,
            warnings=warnings,
            age_group=norm_age,
            sex_group=norm_sex
        )

    def get_safety_flags(self, adequacy_results: List[NutrientAdequacyResult]) -> List[SafetyFlag]:
        """
        Get safety flags for any nutrients exceeding UL.

        Args:
            adequacy_results: List of computed adequacy results

        Returns:
            List of SafetyFlag objects
        """
        flags = []

        for result in adequacy_results:
            if result.over_ul and result.over_ul_amount:
                # Determine severity
                if result.pct_ul and result.pct_ul >= 200:
                    severity = "critical"
                elif result.pct_ul and result.pct_ul >= 150:
                    severity = "warning"
                else:
                    severity = "caution"

                flags.append(SafetyFlag(
                    nutrient=result.nutrient,
                    amount=result.amount,
                    unit=result.unit,
                    ul=result.ul,
                    pct_ul=result.pct_ul,
                    over_amount=result.over_ul_amount,
                    warning=f"Exceeds Tolerable Upper Intake Level by {result.over_ul_amount:.1f} {result.unit}",
                    severity=severity
                ))

        return flags

    def _find_nutrient(self, name: str) -> Optional[Dict]:
        """Find nutrient in database by name or alias."""
        key = self._normalize_nutrient_name(name)

        # Direct lookup
        if key in self.nutrient_lookup:
            return self.nutrient_lookup[key]

        # Check aliases
        if key in self.nutrient_aliases:
            actual_key = self.nutrient_aliases[key]
            return self.nutrient_lookup.get(actual_key)

        # Try partial matching for common variations
        for db_key, data in self.nutrient_lookup.items():
            if key in db_key or db_key in key:
                return data

        return None

    def _get_age_sex_values(
        self,
        nutrient_data: Dict,
        age_group: str,
        sex: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """Get RDA/AI and UL for specific age/sex group."""
        data_list = nutrient_data.get("data", [])

        for entry in data_list:
            if entry.get("group") == sex and entry.get("age_range") == age_group:
                rda = entry.get("rda_ai")
                ul = entry.get("ul")

                # UL and RDA are now numeric or null (no more "ND" strings)
                if not isinstance(ul, (int, float)):
                    ul = None
                if not isinstance(rda, (int, float)):
                    rda = None

                return rda, ul

        # Fallback to highest_ul if specific value not found
        fallback_ul = nutrient_data.get("highest_ul")
        if isinstance(fallback_ul, str):
            try:
                fallback_ul = float(fallback_ul)
            except ValueError:
                fallback_ul = None
        return None, fallback_ul

    def _get_ai_value(
        self,
        nutrient_data: Dict,
        age_group: str,
        sex: str
    ) -> Optional[float]:
        """Get AI (Adequate Intake) if RDA not available."""
        # Check if this nutrient uses AI instead of RDA
        data_list = nutrient_data.get("data", [])

        for entry in data_list:
            if entry.get("group") == sex and entry.get("age_range") == age_group:
                ai_value = entry.get("rda_ai")  # AI is stored in same field
                if ai_value is None:
                    return None
                if isinstance(ai_value, (int, float)):
                    return float(ai_value)
                if isinstance(ai_value, str):
                    try:
                        return float(ai_value)
                    except ValueError:
                        return None
                return None

        return None

    def _determine_ul_status(self, nutrient_data: Dict, ul: Optional[float]) -> str:
        """Determine UL status."""
        if ul is not None and ul > 0:
            return "established"

        # Check ul_status field (set during Phase 2 normalization)
        ul_status = nutrient_data.get("ul_status")
        if ul_status == "not_determined":
            return "not_determined"

        # Check highest_ul
        highest = nutrient_data.get("highest_ul")
        if highest is None:
            return "not_determined"

        return "not_applicable"

    def _parse_optimal_range(self, range_str: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse optimal range string like '200-2000'."""
        if not range_str:
            return None, None

        match = re.match(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', str(range_str))
        if match:
            return float(match.group(1)), float(match.group(2))

        return None, None

    def _uses_supplement_only_ul_policy(self, nutrient_data: Dict) -> bool:
        """Return True for nutrients whose UL applies only to supplemental intake."""
        return nutrient_data.get("id") == "magnesium"

    def _determine_adequacy_band(
        self,
        pct_rda: Optional[float],
        over_ul: bool
    ) -> str:
        """Determine adequacy band based on percentage of RDA."""
        if pct_rda is None:
            return "unknown"

        if over_ul:
            return "excessive"

        for band_name, band_info in ADEQUACY_BANDS.items():
            if band_info["min_pct"] <= pct_rda < band_info["max_pct"]:
                return band_name

        return "unknown"


# Convenience functions
def compute_nutrient_adequacy(
    nutrient: str,
    amount: float,
    unit: str,
    age_group: str = "19-30",
    sex: str = "both",
    rda_db_path: Optional[Path] = None
) -> Dict:
    """
    Convenience function to compute nutrient adequacy.

    Returns dictionary suitable for adding to enriched product data.
    """
    calculator = RDAULCalculator(rda_db_path)
    result = calculator.compute_nutrient_adequacy(nutrient, amount, unit, age_group, sex)
    return result.to_dict()


def get_safety_flags(adequacy_results: List[Dict], rda_db_path: Optional[Path] = None) -> List[Dict]:
    """
    Convenience function to get safety flags from adequacy results.

    Args:
        adequacy_results: List of adequacy result dictionaries

    Returns:
        List of safety flag dictionaries
    """
    # Convert dicts back to dataclass for processing
    results = []
    for r in adequacy_results:
        results.append(NutrientAdequacyResult(
            nutrient=r["nutrient"],
            amount=r["amount"],
            unit=r["unit"],
            rda_ai=r.get("rda_ai"),
            rda_ai_source=r.get("rda_ai_source", "unknown"),
            ul=r.get("ul"),
            ul_status=r.get("ul_status", "unknown"),
            optimal_min=r.get("optimal_min"),
            optimal_max=r.get("optimal_max"),
            pct_rda=r.get("pct_rda"),
            pct_ul=r.get("pct_ul"),
            adequacy_band=r.get("adequacy_band", "unknown"),
            over_ul=r.get("over_ul", False),
            over_ul_amount=r.get("over_ul_amount"),
            scoring_eligible=r.get("scoring_eligible", False),
            point_recommendation=r.get("point_recommendation", 0),
            notes=r.get("notes", []),
            warnings=r.get("warnings", []),
            age_group=r.get("age_group", "19-30"),
            sex_group=r.get("sex_group", "Male")
        ))

    calculator = RDAULCalculator(rda_db_path)
    flags = calculator.get_safety_flags(results)
    return [f.to_dict() for f in flags]
