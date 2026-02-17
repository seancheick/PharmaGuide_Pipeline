#!/usr/bin/env python3
"""
Proprietary Blend Detector Module

Detects proprietary blends in supplement products and classifies their
disclosure level for scoring purposes.

Key features:
- Pattern-based blend detection
- Disclosure level classification (full/partial/none)
- Risk category identification
- Full evidence tracking

Usage:
    from proprietary_blend_detector import ProprietaryBlendDetector

    detector = ProprietaryBlendDetector()
    result = detector.analyze_product(product)
"""

import json
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DetectedBlend:
    """A detected proprietary blend with evidence."""
    blend_name: str
    blend_id: str
    matched_text: str
    source_field: str
    blend_total_declared: bool
    blend_total_amount: Optional[float]
    blend_total_unit: Optional[str]
    blend_ingredients_listed: bool
    blend_ingredient_count: int
    blend_amounts_present: str  # "none" | "partial" | "full"
    ingredients_with_amounts: List[Dict]
    ingredients_without_amounts: List[str]
    risk_category: str
    severity_level: str
    disclosure_level: str  # "full" | "partial" | "none"
    penalty_applicable: int  # What scoring COULD apply (not computed here)
    penalty_reason: str

    @property
    def dedupe_key(self) -> Tuple[str, str, Optional[int], int]:
        """
        Generate a dedupe key for this blend.

        Key components:
        - normalized_name: lowercase, stripped blend name
        - disclosure_level: none/partial/full
        - mg_bucket: 5mg bucket (to tolerate parsing variance like 33.9 vs 34.1)
        - ingredient_count: distinguishes same-named blends with different structures

        This prevents:
        - Double-penalizing same blend detected from multiple fields
        - Under-penalizing distinct same-named blends (e.g., inner vs outer capsule)
        """
        normalized = self.blend_name.lower().strip()
        if self.blend_total_amount is not None:
            # 5mg bucket to tolerate parsing variance
            mg_bucket = int(round(self.blend_total_amount / 5.0) * 5)
        else:
            mg_bucket = None
        return (normalized, self.disclosure_level, mg_bucket, self.blend_ingredient_count)

    def to_dict(self) -> Dict:
        return {
            "blend_name": self.blend_name,
            "blend_id": self.blend_id,
            "matched_text": self.matched_text,
            "source_field": self.source_field,
            "blend_total_declared": self.blend_total_declared,
            "blend_total_amount": self.blend_total_amount,
            "blend_total_unit": self.blend_total_unit,
            "blend_ingredients_listed": self.blend_ingredients_listed,
            "blend_ingredient_count": self.blend_ingredient_count,
            "blend_amounts_present": self.blend_amounts_present,
            "ingredients_with_amounts": self.ingredients_with_amounts,
            "ingredients_without_amounts": self.ingredients_without_amounts,
            "risk_category": self.risk_category,
            "severity_level": self.severity_level,
            "disclosure_level": self.disclosure_level,
            "penalty_applicable": self.penalty_applicable,
            "penalty_reason": self.penalty_reason,
            "dedupe_key": self.dedupe_key
        }


@dataclass
class BlendAnalysisResult:
    """Complete blend analysis result for a product."""
    blends_detected: List[DetectedBlend]
    total_penalty_applicable: int  # Sum of applicable penalties (for scoring to use)
    penalty_cap: int
    penalty_cap_would_apply: bool  # If total exceeds cap
    has_high_risk_blend: bool
    warnings: List[str]

    def to_dict(self) -> Dict:
        return {
            "blends_detected": [b.to_dict() for b in self.blends_detected],
            "total_penalty_applicable": self.total_penalty_applicable,
            "penalty_cap": self.penalty_cap,
            "penalty_cap_would_apply": self.penalty_cap_would_apply,
            "has_high_risk_blend": self.has_high_risk_blend,
            "warnings": self.warnings
        }


class ProprietaryBlendDetector:
    """
    Detects and analyzes proprietary blends in supplement products.

    Outputs evidence data for scoring consumption - does NOT compute
    final scores (that's the scorer's job).
    """

    # Additional patterns for blend detection beyond database terms
    BLEND_INDICATOR_PATTERNS = [
        r'proprietary\s+(?:blend|complex|formula|matrix)',
        r'\b(?:blend|complex|matrix|formula)\b.*\d+\s*(?:mg|g|mcg)',
        r'\d+\s*(?:mg|g|mcg)\s*(?:blend|complex|matrix|formula)',
    ]

    # Patterns to detect total amount declaration
    TOTAL_AMOUNT_PATTERN = re.compile(
        r'(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|μg|iu|billion\s*cfu|cfu)',
        re.IGNORECASE
    )

    def __init__(self, blend_db_path: Optional[Path] = None):
        """
        Initialize the detector.

        Args:
            blend_db_path: Path to proprietary_blends_penalty.json.
                          If None, uses default location.
        """
        if blend_db_path is None:
            blend_db_path = Path(__file__).parent / "data" / "proprietary_blends_penalty.json"

        self.blend_db = self._load_blend_db(blend_db_path)
        self.penalty_cap = self.blend_db.get("_metadata", {}).get("max_penalty_points", 10)
        self._compile_patterns()

    def _load_blend_db(self, path: Path) -> Dict:
        """Load the proprietary blends penalty database."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load blend database: {e}")
            return {"proprietary_blend_concerns": [], "_metadata": {"max_penalty_points": 10}}

    def _compile_patterns(self):
        """Compile all detection patterns for efficiency."""
        self.compiled_patterns = []

        for blend_def in self.blend_db.get("proprietary_blend_concerns", []):
            blend_id = blend_def.get("id", "UNKNOWN")
            standard_name = blend_def.get("standard_name", "Unknown Blend")
            severity = blend_def.get("severity_level", "moderate")

            # Get penalties
            penalties = blend_def.get("penalties") or blend_def.get("penalty_levels") or []
            no_disclosure_penalty = -10
            partial_disclosure_penalty = -5
            no_disclosure_reason = "No ingredient amounts disclosed"
            partial_disclosure_reason = "Some ingredient amounts disclosed"

            for p in penalties:
                if p.get("type") == "no_disclosure":
                    no_disclosure_penalty = p.get("penalty", -10)
                    no_disclosure_reason = p.get("penalty_reason", no_disclosure_reason)
                elif p.get("type") == "partial_disclosure":
                    partial_disclosure_penalty = p.get("penalty", -5)
                    partial_disclosure_reason = p.get("penalty_reason", partial_disclosure_reason)

            # Compile patterns from red_flag_terms
            terms = blend_def.get("red_flag_terms") or []
            aliases = blend_def.get("aliases") or []
            all_terms = terms + aliases

            for term in all_terms:
                # Escape special regex chars but allow matching
                escaped = re.escape(term)
                # Make matching case-insensitive and allow some flexibility
                pattern = re.compile(escaped, re.IGNORECASE)

                self.compiled_patterns.append({
                    "pattern": pattern,
                    "term": term,
                    "blend_id": blend_id,
                    "standard_name": standard_name,
                    "severity": severity,
                    "risk_category": self._infer_risk_category(blend_id, standard_name),
                    "no_disclosure_penalty": no_disclosure_penalty,
                    "partial_disclosure_penalty": partial_disclosure_penalty,
                    "no_disclosure_reason": no_disclosure_reason,
                    "partial_disclosure_reason": partial_disclosure_reason
                })

    def _infer_risk_category(self, blend_id: str, name: str) -> str:
        """Infer risk category from blend ID or name."""
        id_lower = blend_id.lower()
        name_lower = name.lower()

        if 'stimulant' in id_lower or 'energy' in name_lower:
            return "stimulant"
        elif 'testosterone' in id_lower or 'anabolic' in name_lower or 'hormone' in name_lower:
            return "testosterone"
        elif 'weight' in id_lower or 'fat' in name_lower or 'thermogenic' in name_lower:
            return "weight_loss"
        elif 'nootropic' in id_lower or 'cognitive' in name_lower or 'brain' in name_lower:
            return "nootropic"
        elif 'adaptogen' in id_lower or 'stress' in name_lower:
            return "adaptogen"
        elif 'probiotic' in id_lower or 'probiotic' in name_lower:
            return "probiotic"
        elif 'superfood' in id_lower or 'immune' in name_lower:
            return "superfood"
        elif 'beauty' in id_lower or 'collagen' in name_lower:
            return "beauty"
        elif 'enzyme' in id_lower or 'enzyme' in name_lower:
            return "enzyme"
        else:
            return "general"

    def analyze_product(self, product: Dict) -> BlendAnalysisResult:
        """
        Analyze a product for proprietary blends.

        Args:
            product: Product dictionary with supplement facts and ingredients

        Returns:
            BlendAnalysisResult with all detected blends and evidence
        """
        detected_blends = []
        warnings = []

        # Fields to search for blend patterns
        search_fields = [
            ("supplementFacts", product.get("supplementFacts", [])),
            ("activeIngredients", product.get("activeIngredients", [])),
            ("inactiveIngredients", product.get("inactiveIngredients", [])),
            ("otherIngredients", product.get("otherIngredients", [])),
            ("ingredients", product.get("ingredients", [])),
        ]

        # Also search statements and claims
        for stmt in product.get("statements", []):
            if isinstance(stmt, dict):
                text = stmt.get("text", "") or stmt.get("notes", "")
                if text:
                    search_fields.append(("statements", [{"name": text}]))
            elif isinstance(stmt, str):
                search_fields.append(("statements", [{"name": stmt}]))

        seen_blends = set()  # Avoid duplicate detection

        for field_name, field_data in search_fields:
            if not field_data:
                continue

            if isinstance(field_data, list):
                for i, item in enumerate(field_data):
                    source_field = f"{field_name}[{i}]"
                    blend = self._analyze_ingredient_for_blend(item, source_field, seen_blends)
                    if blend:
                        detected_blends.append(blend)
                        seen_blends.add(blend.blend_name.lower())

        # Calculate totals
        total_penalty = sum(b.penalty_applicable for b in detected_blends)
        cap_would_apply = abs(total_penalty) > self.penalty_cap
        has_high_risk = any(b.severity_level in ["high", "critical"] for b in detected_blends)

        if cap_would_apply:
            warnings.append(f"Penalty cap of -{self.penalty_cap} would apply (raw: {total_penalty})")

        if has_high_risk:
            warnings.append("High-risk blend category detected")

        return BlendAnalysisResult(
            blends_detected=detected_blends,
            total_penalty_applicable=total_penalty,
            penalty_cap=self.penalty_cap,
            penalty_cap_would_apply=cap_would_apply,
            has_high_risk_blend=has_high_risk,
            warnings=warnings
        )

    def _analyze_ingredient_for_blend(
        self,
        ingredient: Any,
        source_field: str,
        seen_blends: set
    ) -> Optional[DetectedBlend]:
        """Analyze a single ingredient/field for blend patterns."""

        # Get text to search
        if isinstance(ingredient, dict):
            name = ingredient.get("name", "") or ingredient.get("ingredient", "")
            description = ingredient.get("description", "") or ingredient.get("notes", "")
            text_to_search = f"{name} {description}".strip()

            # Check for sub-ingredients (indicates a blend)
            sub_ingredients = ingredient.get("ingredients", []) or ingredient.get("subIngredients", [])
        elif isinstance(ingredient, str):
            text_to_search = ingredient
            sub_ingredients = []
        else:
            return None

        if not text_to_search:
            return None

        # Check against all patterns
        for pattern_info in self.compiled_patterns:
            match = pattern_info["pattern"].search(text_to_search)
            if match:
                matched_text = match.group(0)

                # Skip if already seen
                if matched_text.lower() in seen_blends:
                    continue

                # Analyze disclosure level
                disclosure_info = self._analyze_disclosure(
                    ingredient if isinstance(ingredient, dict) else {"name": ingredient},
                    sub_ingredients
                )

                # Determine penalty based on disclosure
                if disclosure_info["level"] == "full":
                    penalty = 0  # No penalty for full disclosure
                    reason = "Full ingredient disclosure"
                elif disclosure_info["level"] == "partial":
                    penalty = pattern_info["partial_disclosure_penalty"]
                    reason = pattern_info["partial_disclosure_reason"]
                else:  # none
                    penalty = pattern_info["no_disclosure_penalty"]
                    reason = pattern_info["no_disclosure_reason"]

                return DetectedBlend(
                    blend_name=pattern_info["standard_name"],
                    blend_id=pattern_info["blend_id"],
                    matched_text=matched_text,
                    source_field=source_field,
                    blend_total_declared=disclosure_info["total_declared"],
                    blend_total_amount=disclosure_info["total_amount"],
                    blend_total_unit=disclosure_info["total_unit"],
                    blend_ingredients_listed=disclosure_info["ingredients_listed"],
                    blend_ingredient_count=disclosure_info["ingredient_count"],
                    blend_amounts_present=disclosure_info["amounts_present"],
                    ingredients_with_amounts=disclosure_info["with_amounts"],
                    ingredients_without_amounts=disclosure_info["without_amounts"],
                    risk_category=pattern_info["risk_category"],
                    severity_level=pattern_info["severity"],
                    disclosure_level=disclosure_info["level"],
                    penalty_applicable=penalty,
                    penalty_reason=reason
                )

        return None

    def _analyze_disclosure(
        self,
        blend_data: Dict,
        sub_ingredients: List
    ) -> Dict:
        """
        Analyze the disclosure level of a blend.

        Returns dict with:
        - level: "full" | "partial" | "none"
        - total_declared: bool
        - total_amount: float or None
        - total_unit: str or None
        - ingredients_listed: bool
        - ingredient_count: int
        - amounts_present: "full" | "partial" | "none"
        - with_amounts: list of ingredient dicts with amounts
        - without_amounts: list of ingredient names without amounts
        """
        result = {
            "level": "none",
            "total_declared": False,
            "total_amount": None,
            "total_unit": None,
            "ingredients_listed": False,
            "ingredient_count": 0,
            "amounts_present": "none",
            "with_amounts": [],
            "without_amounts": []
        }

        # Check for total amount in blend
        name = blend_data.get("name", "") or ""
        amount = blend_data.get("amount")
        unit = blend_data.get("unit", "")

        if amount is not None:
            result["total_declared"] = True
            result["total_amount"] = self._parse_amount(amount)
            result["total_unit"] = unit
        else:
            # Try to extract from name
            match = self.TOTAL_AMOUNT_PATTERN.search(name)
            if match:
                result["total_declared"] = True
                result["total_amount"] = float(match.group(1).replace(",", ""))
                result["total_unit"] = match.group(2)

        # Analyze sub-ingredients
        if not sub_ingredients:
            # Check if blend_data has nested ingredients
            sub_ingredients = blend_data.get("ingredients", []) or \
                             blend_data.get("subIngredients", []) or \
                             blend_data.get("components", [])

        if sub_ingredients:
            result["ingredients_listed"] = True
            result["ingredient_count"] = len(sub_ingredients)

            for sub in sub_ingredients:
                if isinstance(sub, dict):
                    sub_name = sub.get("name", "") or sub.get("ingredient", "")
                    sub_amount = sub.get("amount") or sub.get("quantity")

                    if sub_amount is not None and sub_amount != "" and sub_amount != 0:
                        result["with_amounts"].append({
                            "name": sub_name,
                            "amount": sub_amount,
                            "unit": sub.get("unit", "")
                        })
                    else:
                        result["without_amounts"].append(sub_name)
                elif isinstance(sub, str):
                    # Check if amount is embedded in string
                    amount_match = self.TOTAL_AMOUNT_PATTERN.search(sub)
                    if amount_match:
                        result["with_amounts"].append({
                            "name": sub,
                            "amount": float(amount_match.group(1)),
                            "unit": amount_match.group(2)
                        })
                    else:
                        result["without_amounts"].append(sub)

        # Determine disclosure level
        total_subs = len(result["with_amounts"]) + len(result["without_amounts"])

        if total_subs == 0:
            # No sub-ingredients listed = no disclosure
            result["level"] = "none"
            result["amounts_present"] = "none"
        elif len(result["without_amounts"]) == 0 and len(result["with_amounts"]) > 0:
            # All sub-ingredients have amounts = full disclosure
            result["level"] = "full"
            result["amounts_present"] = "full"
        elif len(result["with_amounts"]) > 0:
            # Some have amounts, some don't = partial
            result["level"] = "partial"
            result["amounts_present"] = "partial"
        else:
            # Listed but no amounts = none
            result["level"] = "none"
            result["amounts_present"] = "none"

        return result

    def _parse_amount(self, amount: Any) -> Optional[float]:
        """Parse amount to float."""
        if amount is None:
            return None
        if isinstance(amount, (int, float)):
            return float(amount)
        if isinstance(amount, str):
            try:
                # Remove commas and parse
                clean = amount.replace(",", "").strip()
                # Handle ranges - take lower bound
                if "-" in clean and not clean.startswith("-"):
                    clean = clean.split("-")[0].strip()
                return float(clean)
            except ValueError:
                return None
        return None


# Convenience function
def analyze_product_blends(product: Dict, blend_db_path: Optional[Path] = None) -> Dict:
    """
    Convenience function to analyze a product's proprietary blends.

    Returns dictionary suitable for adding to enriched product data.
    """
    detector = ProprietaryBlendDetector(blend_db_path)
    result = detector.analyze_product(product)
    return result.to_dict()
