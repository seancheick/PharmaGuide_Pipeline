#!/usr/bin/env python3
"""
DSLD Supplement Scoring System v3.1.0
======================================
Calculates product scores from enriched data using best-practice algorithms.

SCORING STRUCTURE (100 POINTS TOTAL):
- Section A: Ingredient Quality (0-30 pts)
- Section B: Safety & Purity (0-45 pts)
- Section C: Evidence & Research (0-15 pts)
- Section D: Brand Trust (0-10 pts)
- Section E: User Profile (0-20 pts) - Calculated on device, NOT here

This script calculates 80 points (Sections A-D).
Display format: "65/80" with "/100 equivalent" shown underneath.

ALGORITHM FEATURES:
- Uses combined 'score' field (bio_score + natural bonus)
- Deduplication by additive_id to prevent double penalties
- Category caps to prevent over-penalization
- Diminishing returns on stacking penalties
- Floor/ceiling protection

Usage:
    python score_supplements.py
    python score_supplements.py --config config/scoring_config.json
    python score_supplements.py --input-dir enriched_data --output-dir scored_output
    python score_supplements.py --dry-run

Author: PharmaGuide Team
Version: 3.1.0
"""

import json
import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set, Optional
from collections import defaultdict

# Optional tqdm import for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = None

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from constants import LOG_FORMAT, LOG_DATE_FORMAT


class SupplementScorer:
    """
    Scoring system for enriched supplement data.

    Design Principles:
    1. Uses 'score' field (bio_score + natural) instead of raw bio_score
    2. Deduplicates penalties by additive_id to prevent double-counting
    3. Implements category caps per MCDM best practices
    4. Provides transparent scoring notes for every calculation
    """

    VERSION = "3.3.1"
    COMPATIBLE_ENRICHMENT_VERSIONS = ["3.0.0", "3.0.1", "3.1.0", "3.2.0"]

    # Required fields for enriched product validation
    REQUIRED_ENRICHED_FIELDS = ['dsld_id', 'product_name', 'enrichment_version']
    REQUIRED_ENRICHMENT_SECTIONS = [
        'ingredient_quality_data', 'contaminant_data', 'compliance_data',
        'certification_data', 'proprietary_data', 'evidence_data', 'manufacturer_data'
    ]

    @staticmethod
    def validate_enriched_product(product: Dict) -> Tuple[bool, List[str]]:
        """
        Validate enriched product structure before scoring.
        Returns: (is_valid, list of issues)
        """
        issues = []

        if not isinstance(product, dict):
            return False, ["Product must be a dictionary"]

        # Check required fields
        for field in SupplementScorer.REQUIRED_ENRICHED_FIELDS:
            if field not in product:
                issues.append(f"Missing required field: {field}")

        # Check enrichment sections exist (warning only, don't fail)
        for section in SupplementScorer.REQUIRED_ENRICHMENT_SECTIONS:
            if section not in product:
                issues.append(f"Missing enrichment section: {section} (will use defaults)")

        # Check enrichment version compatibility
        enrichment_version = product.get('enrichment_version', '')
        if enrichment_version and enrichment_version not in SupplementScorer.COMPATIBLE_ENRICHMENT_VERSIONS:
            issues.append(f"Enrichment version {enrichment_version} may not be compatible")

        # Only fail on truly critical missing fields (accept alternative field names)
        has_id = 'dsld_id' in product or 'id' in product
        has_name = 'product_name' in product or 'fullName' in product

        critical_issues = []
        if not has_id:
            critical_issues.append("Missing product ID (dsld_id or id)")
        if not has_name:
            critical_issues.append("Missing product name (product_name or fullName)")

        return len(critical_issues) == 0, issues + critical_issues

    def __init__(self, config_path: str = "config/scoring_config.json"):
        """Initialize scoring system with configuration"""
        self.logger = self._setup_logging()
        self.config = self._load_config(config_path)

        # Extract scoring parameters from config
        self.section_max = self.config.get('section_maximums', {})
        self.section_a_config = self.config.get('section_A_ingredient_quality', {})
        self.section_b_config = self.config.get('section_B_safety_purity', {})
        self.section_c_config = self.config.get('section_C_evidence_research', {})
        self.section_d_config = self.config.get('section_D_brand_trust', {})
        self.probiotic_config = self.config.get('probiotic_bonus', {})
        self.floors_ceilings = self.config.get('score_floors_and_ceilings', {})

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        return logging.getLogger(__name__)

    def _load_config(self, config_path: str) -> Dict:
        """Load scoring configuration"""
        try:
            if not os.path.isabs(config_path):
                script_dir = Path(__file__).parent
                config_path = script_dir / config_path

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info(f"Scoring config loaded from {config_path}")
            return config
        except FileNotFoundError:
            self.logger.warning(f"Config not found at {config_path}, using defaults")
            return self._default_config()
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in scoring config {config_path}: {e}")
            return self._default_config()
        except PermissionError as e:
            self.logger.error(f"Permission denied reading config {config_path}: {e}")
            return self._default_config()
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to read config file {config_path}: {e}")
            return self._default_config()

    def _default_config(self) -> Dict:
        """Return sensible defaults if config not found"""
        return {
            "section_maximums": {
                "A_ingredient_quality": 30,
                "B_safety_purity": 45,
                "C_evidence_research": 15,
                "D_brand_trust": 8,  # Was 10, now 8 after removing full_disclosure (+2 double-counting)
                "total_without_E": 80
            },
            "score_floors_and_ceilings": {
                "total_floor": 10,
                "total_ceiling": 80
            },
            "paths": {
                "input_directory": "output_Lozenges_enriched/enriched",
                "output_directory": "output_Lozenges_scored"
            }
        }

    # =========================================================================
    # SECTION A: INGREDIENT QUALITY (0-30 POINTS)
    # =========================================================================

    def _score_a1_bioavailability(self, ingredients: List[Dict], supplement_type: str, a1_config: Dict) -> Tuple[float, List[str]]:
        """Score A1: Bioavailability & Form Quality (max 15)"""
        a1_max = a1_config.get('max', 15)
        notes = []

        if not ingredients:
            return 0, ["A1: No ingredients found"]

        total_weighted = 0
        total_importance = 0
        skipped_count = 0

        for ing in ingredients:
            # Skip summaries and sources to prevent double-counting (score only components)
            hierarchy = ing.get('hierarchyType') or {}
            hierarchy_type = hierarchy.get('type') if isinstance(hierarchy, dict) else None
            scoring_rule = hierarchy.get('scoring_rule') if isinstance(hierarchy, dict) else None

            if hierarchy_type in ['summary', 'source']:
                skipped_count += 1
                continue
            if scoring_rule == 'skip_all':
                skipped_count += 1
                continue

            score = ing.get('score')
            if score is None:
                bio_score = ing.get('bio_score', 5) or 5
                natural = ing.get('natural', False)
                score = bio_score + (3 if natural else 0)

            importance = ing.get('dosage_importance', 1.0)
            total_weighted += score * importance
            total_importance += importance

        if skipped_count > 0:
            notes.append(f"A1: Skipped {skipped_count} summary/source ingredients (scoring components only)")

        if total_importance > 0:
            weighted_avg = total_weighted / total_importance

            if supplement_type == 'multivitamin':
                floor_mult = a1_config.get('floor_multiplier_for_multis', 0.7)
                weighted_avg = max(weighted_avg, a1_max * floor_mult)
                notes.append(f"A1: Multivitamin floor applied (min {a1_max * floor_mult:.1f})")

            a1_score = min(weighted_avg, a1_max)
            notes.append(f"A1: Weighted avg score = {weighted_avg:.1f} (capped at {a1_max})")
            return a1_score, notes

        return 0, notes

    def _score_a2_premium_forms(self, ingredients: List[Dict], a2_config: Dict) -> Tuple[float, List[str], int]:
        """Score A2: Multiple Premium Forms (max 3)"""
        a2_max = a2_config.get('max', 3)
        threshold = a2_config.get('threshold_bio_score', 12)
        points_per = a2_config.get('points_per_form', 0.5)

        premium_count = 0
        for ing in ingredients:
            # Skip summaries and sources to prevent double-counting
            hierarchy = ing.get('hierarchyType') or {}
            hierarchy_type = hierarchy.get('type') if isinstance(hierarchy, dict) else None
            scoring_rule = hierarchy.get('scoring_rule') if isinstance(hierarchy, dict) else None

            if hierarchy_type in ['summary', 'source'] or scoring_rule == 'skip_all':
                continue

            if (ing.get('bio_score') or 0) > threshold:
                premium_count += 1

        if premium_count > 0:
            score = min(premium_count * points_per, a2_max)
            return score, [f"A2: {premium_count} premium forms (bio_score > {threshold}) = +{score:.1f}"], premium_count

        return 0, [], 0

    def _score_a3_delivery(self, delivery_data: Dict, a3_config: Dict) -> Tuple[float, List[str]]:
        """Score A3: Enhanced Delivery (max 3)"""
        a3_max = a3_config.get('max', 3)

        if not delivery_data.get('matched', False):
            return 0, ["A3: No enhanced delivery detected"]

        highest_tier = delivery_data.get('highest_tier', 4)
        tier_points = a3_config.get('tiers', {}).get(f'tier_{highest_tier}', {}).get('points', 0)
        score = min(tier_points, a3_max)

        systems = delivery_data.get('systems', [])
        system_name = systems[0].get('name', 'unknown') if systems else 'unknown'
        return score, [f"A3: {system_name} (Tier {highest_tier}) = +{score}"]

    def _score_a4_absorption(self, absorption_data: Dict, a4_config: Dict) -> Tuple[float, List[str]]:
        """Score A4: Absorption Enhancer (max 3, once only)"""
        a4_max = a4_config.get('max', 3)

        if not absorption_data.get('qualifies_for_bonus', False):
            return 0, ["A4: No qualifying absorption enhancer"]

        score = min(a4_config.get('points_if_qualifies', 3), a4_max)
        enhancers = absorption_data.get('enhancers', [])
        enhancer_name = enhancers[0].get('name', 'unknown') if enhancers else 'unknown'
        nutrients = absorption_data.get('enhanced_nutrients_present', [])
        return score, [f"A4: {enhancer_name} enhances {nutrients} = +{score}"]

    def _score_a5_formulation(self, formulation_data: Dict, a5_config: Dict) -> Tuple[float, List[str], Dict]:
        """Score A5: Formulation Excellence (max 9) - organic, botanicals, synergy"""
        a5_max = a5_config.get('max', 9)
        score = 0
        notes = []
        details = {'organic_claimed': False, 'qualifying_botanicals': [], 'synergy_pts': 0, 'synergy_note': 'N/A'}

        # Organic (+2)
        organic = formulation_data.get('organic', {})
        if organic.get('claimed', False) and organic.get('usda_verified', False):
            organic_pts = a5_config.get('usda_organic', {}).get('points', 2)
            score += organic_pts
            notes.append(f"A5: USDA Organic = +{organic_pts}")
            details['organic_claimed'] = True

        # Standardized Botanicals (+2)
        botanicals = formulation_data.get('standardized_botanicals', [])
        qualifying_botanicals = [b for b in botanicals if b.get('meets_threshold', False)]
        if qualifying_botanicals:
            botanical_pts = a5_config.get('standardized_botanicals', {}).get('points', 2)
            score += botanical_pts
            notes.append(f"A5: {len(qualifying_botanicals)} standardized botanicals = +{botanical_pts}")
        details['qualifying_botanicals'] = qualifying_botanicals

        # Synergy Clusters
        clusters = formulation_data.get('synergy_clusters', [])
        synergy_config = a5_config.get('synergy_clusters', {})
        synergy_max = synergy_config.get('max', 5)
        synergy_pts = 0
        synergy_note = "N/A"

        if clusters:
            best_cluster = max(clusters, key=lambda c: c.get('match_count', 0))
            match_count = best_cluster.get('match_count', 0)
            cluster_name = best_cluster.get('cluster_name', 'unknown')

            tier_thresholds = [(5, 'tier_5_plus', 5), (4, 'tier_4', 3), (3, 'tier_3', 2), (2, 'tier_2', 1)]
            for threshold, key, default in tier_thresholds:
                if match_count >= threshold:
                    synergy_pts = synergy_config.get(key, default)
                    synergy_note = f"{cluster_name} ({match_count} ingredients)"
                    break

            if synergy_pts > 0:
                synergy_pts = min(synergy_pts, synergy_max)
                score += synergy_pts
                notes.append(f"A5: Synergy cluster {synergy_note} = +{synergy_pts}")

        details['synergy_pts'] = synergy_pts
        details['synergy_note'] = synergy_note

        return min(score, a5_max), notes, details

    def _score_section_a(self, product: Dict) -> Dict:
        """
        Score Section A: Ingredient Quality

        Sub-sections:
        - A1: Bioavailability & Form Quality (0-15) - weighted avg of score × importance
        - A2: Multiple Premium Forms (0-3) - +0.5 per form with bio_score > 12
        - A3: Enhanced Delivery (0-3) - tier-based points
        - A4: Absorption Enhancer (0-3) - once only if qualifies
        - A5: Formulation Excellence (0-9) - organic, botanicals, synergy
        """
        # Load configs
        a1_config = self.section_a_config.get('A1_bioavailability_form', {})
        a2_config = self.section_a_config.get('A2_premium_forms', {})
        a3_config = self.section_a_config.get('A3_delivery_system', {})
        a4_config = self.section_a_config.get('A4_absorption_enhancer', {})
        a5_config = self.section_a_config.get('A5_formulation_excellence', {})

        # Extract product data
        quality_data = product.get('ingredient_quality_data', {})
        delivery_data = product.get('delivery_data', {})
        absorption_data = product.get('absorption_data', {})
        formulation_data = product.get('formulation_data', {})
        supplement_type = product.get('supplement_type', {}).get('type', 'unknown')
        ingredients = quality_data.get('ingredients', [])

        # Score each sub-section using helper methods
        a1_score, a1_notes = self._score_a1_bioavailability(ingredients, supplement_type, a1_config)
        a2_score, a2_notes, premium_count = self._score_a2_premium_forms(ingredients, a2_config)
        a3_score, a3_notes = self._score_a3_delivery(delivery_data, a3_config)
        a4_score, a4_notes = self._score_a4_absorption(absorption_data, a4_config)
        a5_score, a5_notes, a5_details = self._score_a5_formulation(formulation_data, a5_config)

        # Combine notes
        notes = a1_notes + a2_notes + a3_notes + a4_notes + a5_notes

        # Total Section A
        total_a = a1_score + a2_score + a3_score + a4_score + a5_score
        max_a = self.section_max.get('A_ingredient_quality', 30)
        total_a = min(total_a, max_a)

        # Get config values for output
        a1_max = a1_config.get('max', 15)
        a2_max = a2_config.get('max', 3)
        a3_max = a3_config.get('max', 3)
        a4_max = a4_config.get('max', 3)
        threshold = a2_config.get('threshold_bio_score', 12)
        synergy_config = a5_config.get('synergy_clusters', {})
        synergy_max = synergy_config.get('max', 5)
        organic_pts = a5_config.get('usda_organic', {}).get('points', 2)
        botanical_pts = a5_config.get('standardized_botanicals', {}).get('points', 2)

        # Build consumer-facing output
        return {
            "score": round(total_a, 1),
            "max": max_a,
            "subcategories": [
                {"name": a1_config.get('name', 'Bioavailability & Form Quality'),
                 "score": round(a1_score, 1), "max": a1_max,
                 "note": f"Weighted avg of {len(ingredients)} ingredients" if ingredients else "No ingredients found"},
                {"name": a2_config.get('name', 'Multiple Premium Forms'),
                 "score": round(a2_score, 1), "max": a2_max,
                 "note": f"{premium_count} premium forms (bio_score > {threshold})" if premium_count > 0 else "None"},
                {"name": a3_config.get('name', 'Enhanced Delivery System'),
                 "score": round(a3_score, 1), "max": a3_max,
                 "note": self._get_delivery_note(delivery_data)},
                {"name": a4_config.get('name', 'Absorption Enhancer Present'),
                 "score": round(a4_score, 1), "max": a4_max,
                 "note": self._get_absorption_note(absorption_data)},
                {"name": a5_config.get('usda_organic', {}).get('name', 'USDA Organic Certified'),
                 "score": organic_pts if a5_details['organic_claimed'] else 0, "max": organic_pts,
                 "note": "Verified seal" if a5_details['organic_claimed'] else "N/A"},
                {"name": a5_config.get('standardized_botanicals', {}).get('name', 'Standardized Botanicals'),
                 "score": botanical_pts if a5_details['qualifying_botanicals'] else 0, "max": botanical_pts,
                 "note": f"{len(a5_details['qualifying_botanicals'])} found" if a5_details['qualifying_botanicals'] else "N/A"},
                {"name": synergy_config.get('name', 'Synergy Clusters'),
                 "score": round(a5_details['synergy_pts'], 1), "max": synergy_max,
                 "note": a5_details['synergy_note']}
            ],
            "details": {
                "supplement_type": supplement_type,
                "ingredients_count": len(ingredients),
                "premium_forms_count": premium_count,
                "notes": notes
            }
        }

    def _get_delivery_note(self, delivery_data: Dict) -> str:
        """Generate consumer-facing note for delivery system."""
        if not delivery_data.get('matched'):
            return "N/A"
        systems = delivery_data.get('systems', [])
        system_name = systems[0].get('name', 'N/A') if systems else 'N/A'
        tier = delivery_data.get('highest_tier', 'N/A')
        return f"{system_name} (Tier {tier})"

    def _get_absorption_note(self, absorption_data: Dict) -> str:
        """Generate consumer-facing note for absorption enhancer."""
        if not absorption_data.get('qualifies_for_bonus'):
            return "N/A"
        enhancers = absorption_data.get('enhancers', [])
        enhancer_name = enhancers[0].get('name', 'N/A') if enhancers else 'N/A'
        nutrients = absorption_data.get('enhanced_nutrients_present', [])
        return f"{enhancer_name} enhances {nutrients}"

    # =========================================================================
    # SECTION B: SAFETY & PURITY (0-45 POINTS)
    # =========================================================================

    def _score_b1_contaminants(self, contaminant_data: Dict, b1_config: Dict) -> Tuple[float, List[str], bool, Dict]:
        """
        Score B1: Contaminants & Additives (deductions only)
        Returns: (penalty, notes, immediate_fail, details)
        """
        penalty = 0
        notes = []
        immediate_fail = False
        additive_penalty = 0
        allergen_penalty = 0
        additive_penalties_list = []
        allergen_penalties_list = []

        # B1a: Banned/Recalled Substances
        banned = contaminant_data.get('banned_substances', {})
        banned_config = b1_config.get('banned_recalled', {})

        if banned.get('found', False):
            for substance in banned.get('substances', []):
                severity = substance.get('severity_level', 'moderate')
                pen = banned_config.get(severity, -10)
                penalty += pen
                notes.append(f"B1: Banned substance ({substance.get('banned_name', 'unknown')}, {severity}): {pen}")
                if severity == 'critical':
                    immediate_fail = True
                    notes.append("⚠️ CRITICAL: Product flagged as immediate fail")

        # B1b: Harmful Additives (with deduplication and cap)
        additives = contaminant_data.get('harmful_additives', {})
        additive_config = b1_config.get('harmful_additives', {})
        additive_cap = additive_config.get('cap_total', -5)

        if additives.get('found', False):
            additive_list = additives.get('additives', [])
            seen_ids: Set[str] = set()
            unique_additives = []

            for additive in additive_list:
                additive_id = additive.get('additive_id', '')
                if additive_id and additive_id not in seen_ids:
                    seen_ids.add(additive_id)
                    unique_additives.append(additive)
                elif not additive_id:
                    unique_additives.append(additive)

            if len(additive_list) != len(unique_additives):
                notes.append(f"B1: Deduplicated {len(additive_list)} → {len(unique_additives)} additives")

            for additive in unique_additives:
                risk = additive.get('risk_level', 'low')
                pen = additive_config.get(risk, -0.5)
                additive_penalty += pen
                name = additive.get('matched_name', 'Unknown')
                additive_penalties_list.append(f"{name} → {pen}")

            additive_penalty = max(additive_penalty, additive_cap)
            penalty += additive_penalty
            notes.append(f"B1: Harmful additives ({len(unique_additives)}): {additive_penalty} (cap: {additive_cap})")

        # B1c: Allergens (with cap)
        allergens = contaminant_data.get('allergens', {})
        allergen_config = b1_config.get('undeclared_allergens', {})
        allergen_cap = allergen_config.get('cap_total', -2)

        if allergens.get('found', False):
            for allergen in allergens.get('allergens', []):
                sev = allergen.get('severity_level', 'low')
                pen = allergen_config.get(sev, -1)
                allergen_penalty += pen
                name = allergen.get('allergen_name', 'Unknown')
                allergen_penalties_list.append(f"{name} → {pen}")

            allergen_penalty = max(allergen_penalty, allergen_cap)
            penalty += allergen_penalty
            notes.append(f"B1: Allergens: {allergen_penalty} (cap: {allergen_cap})")

        details = {
            'banned': banned,
            'additive_penalty': additive_penalty,
            'allergen_penalty': allergen_penalty,
            'additive_penalties_list': additive_penalties_list,
            'allergen_penalties_list': allergen_penalties_list,
            'additive_cap': additive_cap,
            'allergen_cap': allergen_cap
        }
        return penalty, notes, immediate_fail, details

    def _score_b2_compliance(self, compliance_data: Dict, b2_config: Dict) -> Tuple[float, List[str]]:
        """
        Score B2: Allergen & Dietary Compliance (bonuses)
        Returns: (score, notes)
        """
        b2_max = b2_config.get('max', 4)
        score = 0
        notes = []

        allergen_free_claims = compliance_data.get('allergen_free_claims', [])
        if allergen_free_claims:
            pts = b2_config.get('allergen_free_claim', {}).get('points', 2)
            score += pts
            notes.append(f"B2: Allergen-free claims ({len(allergen_free_claims)}): +{pts}")

        if compliance_data.get('gluten_free', False):
            pts = b2_config.get('gluten_free', {}).get('points', 1)
            score += pts
            notes.append(f"B2: Gluten-free: +{pts}")

        if compliance_data.get('vegan', False) or compliance_data.get('vegetarian', False):
            pts = b2_config.get('vegan_vegetarian', {}).get('points', 1)
            score += pts
            notes.append(f"B2: Vegan/Vegetarian: +{pts}")

        if compliance_data.get('has_may_contain_warning', False):
            pen = b2_config.get('may_contain_warning', {}).get('penalty', -2)
            score += pen
            notes.append(f"B2: 'May contain' warning: {pen}")

        return max(min(score, b2_max), 0), notes

    def _score_b3_certifications(self, certification_data: Dict, b3_config: Dict) -> Tuple[float, List[str], List]:
        """
        Score B3: Quality Certifications (bonuses)
        Returns: (score, notes, tp_programs)
        """
        b3_max = b3_config.get('max', 16)
        score = 0
        notes = []

        # Third-party testing
        third_party = certification_data.get('third_party_programs', {})
        tp_config = b3_config.get('third_party_testing', {})
        tp_programs = third_party.get('programs', [])

        if third_party.get('count', 0) > 0:
            num_programs = min(len(tp_programs), tp_config.get('max_programs', 2))
            tp_bonus = num_programs * tp_config.get('per_program', 5)
            tp_bonus = min(tp_bonus, tp_config.get('max_total', 10))
            score += tp_bonus
            program_names = [p.get('name', 'unknown') for p in tp_programs[:num_programs]]
            notes.append(f"B3: Third-party ({', '.join(program_names)}): +{tp_bonus}")

        # GMP
        if certification_data.get('gmp', {}).get('claimed', False):
            pts = b3_config.get('gmp_certified', {}).get('points', 4)
            score += pts
            notes.append(f"B3: GMP certified: +{pts}")

        # Batch traceability
        if certification_data.get('batch_traceability', {}).get('qualifies', False):
            pts = b3_config.get('batch_traceability', {}).get('points', 2)
            score += pts
            notes.append(f"B3: Batch traceability: +{pts}")

        return min(score, b3_max), notes, tp_programs

    def _score_b4_proprietary(self, product: Dict, proprietary_data: Dict, b4_config: Dict) -> Tuple[float, List[str], str]:
        """
        Score B4: Proprietary Blend Penalties
        Returns: (penalty, notes, note_suffix)
        """
        b4_cap = b4_config.get('cap_total', -15)
        penalty = 0
        notes = []
        note_suffix = ""

        if not proprietary_data.get('has_proprietary_blends', False):
            return 0, notes, note_suffix

        total_active = proprietary_data.get('total_active_ingredients', 1)
        blends = proprietary_data.get('blends', [])
        blend_count = len(blends)

        if total_active <= 0:
            return 0, notes, note_suffix

        ratio = blend_count / total_active
        scaling = b4_config.get('scaling', {})

        if ratio >= 0.75:
            penalty = scaling.get('ratio_75_plus', -15)
        elif ratio >= 0.50:
            penalty = scaling.get('ratio_50_to_74', -10)
        elif ratio >= 0.25:
            penalty = scaling.get('ratio_25_to_49', -5)
        else:
            penalty = scaling.get('ratio_under_25', -2)

        # Clinical evidence mitigation
        mitigation_config = b4_config.get('clinical_evidence_mitigation', {})
        original_penalty = penalty
        mitigation_applied = False

        # 1. Probiotic blends with clinically documented strains
        probiotic_data = product.get('probiotic_data', {})
        clinical_strain_count = probiotic_data.get('clinical_strain_count', 0)
        if clinical_strain_count > 0:
            reduction = mitigation_config.get('probiotic_clinical_strains', 0.5)
            penalty = penalty * reduction
            note_suffix = f" (reduced from {original_penalty} → {penalty:.1f}: {clinical_strain_count} clinical probiotic strain(s))"
            mitigation_applied = True

        # 2. Herbal/botanical blends with clinical evidence
        if not mitigation_applied:
            evidence_data = product.get('evidence_data', {})
            clinical_matches = evidence_data.get('clinical_matches', [])
            blend_has_evidence = any(
                m.get('evidence_level') in ['product-human', 'tier_1', 'tier_2', 'systematic_review', 'rct_multiple']
                for m in clinical_matches
            )
            if blend_has_evidence and len(clinical_matches) > 0:
                reduction = mitigation_config.get('herbal_clinical_evidence', 0.6)
                penalty = penalty * reduction
                note_suffix = f" (reduced from {original_penalty} → {penalty:.1f}: {len(clinical_matches)} clinically-backed ingredient(s))"
                mitigation_applied = True

        # 3. Standardized botanical extracts
        if not mitigation_applied:
            formulation_data = product.get('formulation_data', {})
            standardized_botanicals = formulation_data.get('standardized_botanicals', [])
            std_count = len(standardized_botanicals) if isinstance(standardized_botanicals, list) else standardized_botanicals.get('count', 0)
            if std_count > 0:
                reduction = mitigation_config.get('standardized_extracts', 0.7)
                penalty = penalty * reduction
                note_suffix = f" (reduced from {original_penalty} → {penalty:.1f}: {std_count} standardized extract(s))"

        penalty = max(penalty, b4_cap)
        notes.append(f"B4: Proprietary blend ({blend_count}/{total_active} = {ratio:.0%}): {penalty}{note_suffix}")

        return penalty, notes, note_suffix

    def _score_section_b(self, product: Dict) -> Dict:
        """
        Score Section B: Safety & Purity

        CRITICAL: Implements deduplication and caps to prevent over-penalization.

        Sub-sections:
        - B1: Contaminants & Additives (deductions with caps)
        - B2: Allergen & Dietary Compliance (+4 max)
        - B3: Quality Certifications (+16 max)
        - B4: Proprietary Blend Penalties (-15 max)
        """
        # Get configs
        b1_config = self.section_b_config.get('B1_contaminants_additives', {})
        b2_config = self.section_b_config.get('B2_allergen_compliance', {})
        b3_config = self.section_b_config.get('B3_quality_certifications', {})
        b4_config = self.section_b_config.get('B4_proprietary_blends', {})

        # Get product data
        contaminant_data = product.get('contaminant_data', {})
        compliance_data = product.get('compliance_data', {})
        certification_data = product.get('certification_data', {})
        proprietary_data = product.get('proprietary_data', {})

        max_b = self.section_max.get('B_safety_purity', 45)
        score = max_b  # Start at max, subtract penalties, add bonuses
        notes = []

        # B1: Contaminants & Additives (deductions)
        b1_penalty, b1_notes, immediate_fail, b1_details = self._score_b1_contaminants(contaminant_data, b1_config)
        score += b1_penalty
        notes.extend(b1_notes)

        # B2: Allergen & Dietary Compliance (bonuses)
        b2_score, b2_notes = self._score_b2_compliance(compliance_data, b2_config)
        score += b2_score
        notes.extend(b2_notes)

        # B3: Quality Certifications (bonuses)
        b3_score, b3_notes, tp_programs = self._score_b3_certifications(certification_data, b3_config)
        score += b3_score
        notes.extend(b3_notes)

        # B4: Proprietary Blend Penalties
        b4_penalty, b4_notes, b4_note_suffix = self._score_b4_proprietary(product, proprietary_data, b4_config)
        score += b4_penalty
        notes.extend(b4_notes)

        # Apply floor (cannot go below 0) and ceiling (cannot exceed max_b)
        score = max(min(score, max_b), 0)

        # Extract details from b1 helper for breakdown
        additive_penalties_list = b1_details.get('additive_penalties_list', [])
        allergen_penalties_list = b1_details.get('allergen_penalties_list', [])
        additive_penalty = b1_details.get('additive_penalty', 0)
        allergen_penalty = b1_details.get('allergen_penalty', 0)
        additive_cap = b1_details.get('additive_cap', -5)
        allergen_cap = b1_details.get('allergen_cap', -2)
        banned = b1_details.get('banned', {})
        allergen_free_claims = compliance_data.get('allergen_free_claims', [])

        # Get config names for detailed breakdown
        banned_name = b1_config.get('banned_recalled', {}).get('name', 'Banned/Recalled Substances')
        additive_name = b1_config.get('harmful_additives', {}).get('name', 'Harmful Additives')
        allergen_name = b1_config.get('undeclared_allergens', {}).get('name', 'Undeclared Allergens')
        b2_allergen_name = b2_config.get('allergen_free_claim', {}).get('name', 'Allergen-Free Claim (Bonus)')
        b2_gluten_name = b2_config.get('gluten_free', {}).get('name', 'Gluten-Free Certified')
        b2_vegan_name = b2_config.get('vegan_vegetarian', {}).get('name', 'Vegan/Vegetarian')
        b3_tp_name = b3_config.get('third_party_testing', {}).get('name', 'Third-Party Testing')
        b3_gmp_name = b3_config.get('gmp_certified', {}).get('name', 'GMP Certified Facility')
        b3_trace_name = b3_config.get('batch_traceability', {}).get('name', 'Batch Traceability / COA')
        b4_name = b4_config.get('name', 'Proprietary Blend Penalty')
        tp_program_names = ', '.join([p.get('name', 'Unknown') for p in tp_programs[:2]]) if tp_programs else "None"

        return {
            "score": round(score, 1),
            "max": max_b,
            "subcategories": [
                {"name": banned_name, "score": 0, "max": 0, "note": f"{len(banned.get('substances', []))} found" if banned.get('found') else "None found"},
                {"name": additive_name, "score": round(additive_penalty, 1) if 'additive_penalty' in dir() else 0, "max": 0,
                 "penalties": additive_penalties_list if additive_penalties_list else None,
                 "note": f"capped at {additive_cap}" if additive_penalties_list else "None found"},
                {"name": allergen_name, "score": round(allergen_penalty, 1) if 'allergen_penalty' in dir() else 0, "max": 0,
                 "penalties": allergen_penalties_list if allergen_penalties_list else None,
                 "note": f"capped at {allergen_cap}" if allergen_penalties_list else "None found"},
                {"name": b2_allergen_name, "score": b2_config.get('allergen_free_claim', {}).get('points', 2) if allergen_free_claims else 0,
                 "max": b2_config.get('allergen_free_claim', {}).get('points', 2),
                 "note": f"Verified {len(allergen_free_claims)}-free" if allergen_free_claims else "N/A"},
                {"name": b2_gluten_name, "score": b2_config.get('gluten_free', {}).get('points', 1) if compliance_data.get('gluten_free') else 0,
                 "max": b2_config.get('gluten_free', {}).get('points', 1),
                 "note": "Yes" if compliance_data.get('gluten_free') else "N/A"},
                {"name": b2_vegan_name, "score": b2_config.get('vegan_vegetarian', {}).get('points', 1) if (compliance_data.get('vegan') or compliance_data.get('vegetarian')) else 0,
                 "max": b2_config.get('vegan_vegetarian', {}).get('points', 1),
                 "note": "Yes" if (compliance_data.get('vegan') or compliance_data.get('vegetarian')) else "N/A"},
                {"name": b3_tp_name, "score": min(len(tp_programs) * b3_config.get('third_party_testing', {}).get('per_program', 5), b3_config.get('third_party_testing', {}).get('max_total', 10)) if tp_programs else 0,
                 "max": b3_config.get('third_party_testing', {}).get('max_total', 10),
                 "note": tp_program_names},
                {"name": b3_gmp_name, "score": b3_config.get('gmp_certified', {}).get('points', 4) if certification_data.get('gmp', {}).get('claimed') else 0,
                 "max": b3_config.get('gmp_certified', {}).get('points', 4),
                 "note": "Yes" if certification_data.get('gmp', {}).get('claimed') else "N/A"},
                {"name": b3_trace_name, "score": b3_config.get('batch_traceability', {}).get('points', 2) if certification_data.get('batch_traceability', {}).get('qualifies') else 0,
                 "max": b3_config.get('batch_traceability', {}).get('points', 2),
                 "note": "Publicly available" if certification_data.get('batch_traceability', {}).get('qualifies') else "N/A"},
                {"name": b4_name, "score": round(b4_penalty, 1), "max": 0,
                 "note": f"{proprietary_data.get('blend_count', 0)}/{proprietary_data.get('total_active_ingredients', 1)} ingredients hidden{b4_note_suffix}" if proprietary_data.get('has_proprietary_blends') else "Full disclosure — no blends"}
            ],
            "details": {
                "immediate_fail": immediate_fail,
                "additive_penalty_capped": additive_penalty if 'additive_penalty' in dir() else 0,
                "allergen_penalty_capped": allergen_penalty if 'allergen_penalty' in dir() else 0,
                "third_party_pts": min(len(tp_programs) * b3_config.get('third_party_testing', {}).get('per_program', 5), b3_config.get('third_party_testing', {}).get('max_total', 10)) if tp_programs else 0,
                "notes": notes
            }
        }

    # =========================================================================
    # SECTION C: EVIDENCE & RESEARCH (0-15 POINTS)
    # =========================================================================

    def _get_evidence_hierarchy_config(self) -> Dict:
        """Get evidence hierarchy config with defaults."""
        return self.section_c_config.get('evidence_hierarchy', {
            'product_level': {'multiplier': 1.0, 'bonus_for_product_trial': 2},
            'branded_ingredient': {'multiplier': 0.8},
            'ingredient_human': {'multiplier': 0.65},
            'strain_level_probiotic': {'multiplier': 0.6},
            'preclinical': {'multiplier': 0.3}
        })

    def _get_legacy_tier_mapping(self) -> Dict:
        """Get mapping from legacy evidence levels to new hierarchy."""
        return self.section_c_config.get('legacy_tier_mapping', {
            'product-human': 'product_level',
            'product-rct': 'product_level',
            'branded-rct': 'branded_ingredient',
            'ingredient-human': 'ingredient_human',
            'strain-clinical': 'strain_level_probiotic',
            'preclinical': 'preclinical',
            'ingredient-preclinical': 'preclinical',
            'tier_1': 'product_level',
            'tier_2': 'branded_ingredient',
            'tier_3': 'ingredient_human'
        })

    def _get_base_points_for_study_type(self, hierarchy_level: str, study_type: str) -> float:
        """Get base points for a study type within a hierarchy level."""
        hierarchy_config = self._get_evidence_hierarchy_config()
        level_config = hierarchy_config.get(hierarchy_level, {})
        base_points = level_config.get('base_points', {})

        # Default base points if not specified
        defaults = {
            'systematic_review_meta': 6,
            'rct_multiple': 5,
            'rct_single': 4,
            'observational': 2,
            'clinical_strain': 4,
            'animal_study': 2,
            'in_vitro': 1
        }

        return base_points.get(study_type, defaults.get(study_type, 3))

    def _calculate_evidence_score(self, evidence_level: str, study_type: str = 'rct_single') -> Tuple[float, str]:
        """
        Calculate evidence score using hierarchy multipliers.

        Returns: (score, hierarchy_level_used)
        """
        hierarchy_config = self._get_evidence_hierarchy_config()
        legacy_mapping = self._get_legacy_tier_mapping()

        # Map legacy evidence level to hierarchy
        hierarchy_level = legacy_mapping.get(evidence_level, 'ingredient_human')

        # Get multiplier for this hierarchy level
        level_config = hierarchy_config.get(hierarchy_level, {})
        multiplier = level_config.get('multiplier', 0.65)

        # Get base points for study type
        base_points = self._get_base_points_for_study_type(hierarchy_level, study_type)

        # Calculate final score
        score = base_points * multiplier

        return score, hierarchy_level

    def _score_section_c(self, product: Dict) -> Dict:
        """
        Score Section C: Evidence & Research (v3.4.0 - Enhanced Hierarchy)

        Uses evidence hierarchy aligned with EFSA, Natural Medicines, GRADE, Examine:
        - product_level: 1.0x multiplier + bonus for product trials
        - branded_ingredient: 0.8x multiplier
        - ingredient_human: 0.65x multiplier
        - strain_level_probiotic: 0.6x multiplier
        - preclinical: 0.3x multiplier

        Includes:
        - Per-ingredient cap (5 pts max per ingredient)
        - Product trial bonus (+2 for actual product RCTs)
        - Consistency penalty (-1 for mixed evidence)
        """
        evidence_data = product.get('evidence_data', {})
        max_c = self.section_max.get('C_evidence_research', 15)
        scoring_rules = self.section_c_config.get('scoring_rules', {})
        hierarchy_config = self._get_evidence_hierarchy_config()

        cap_per_ingredient = scoring_rules.get('cap_per_ingredient', 5)
        consistency_penalty = scoring_rules.get('consistency_penalty', -1)

        score = 0
        notes = []
        evidence_details = []
        ingredient_scores = {}  # Track per-ingredient to apply cap
        has_product_trial = False
        has_inconsistent_evidence = False

        # Clinical evidence - use hierarchy multipliers
        clinical_matches = evidence_data.get('clinical_matches', [])

        for match in clinical_matches:
            ingredient = match.get('ingredient', 'Unknown')
            evidence_level = match.get('evidence_level', 'preclinical')
            study_type = match.get('study_type', 'rct_single')
            is_inconsistent = match.get('inconsistent_evidence', False)

            # Track inconsistency
            if is_inconsistent:
                has_inconsistent_evidence = True

            # Check for product-level evidence
            if evidence_level in ['product-human', 'product-rct']:
                has_product_trial = True

            # Calculate score using hierarchy
            match_score, hierarchy_level = self._calculate_evidence_score(evidence_level, study_type)

            # Apply per-ingredient cap
            current_ingredient_score = ingredient_scores.get(ingredient, 0)
            capped_contribution = min(match_score, cap_per_ingredient - current_ingredient_score)
            capped_contribution = max(0, capped_contribution)  # Ensure non-negative

            ingredient_scores[ingredient] = current_ingredient_score + capped_contribution
            score += capped_contribution

            # Build detail string
            effective_score = round(capped_contribution, 2)
            detail = f"{ingredient} → {hierarchy_level} ({evidence_level}) → +{effective_score}"
            if capped_contribution < match_score:
                detail += f" (capped from {round(match_score, 2)})"
            evidence_details.append(detail)

        # Apply product trial bonus
        product_bonus = 0
        product_level_config = hierarchy_config.get('product_level', {})
        if has_product_trial:
            product_bonus = product_level_config.get('bonus_for_product_trial', 2)
            score += product_bonus
            notes.append(f"C: Product-level trial bonus: +{product_bonus}")

        # Apply consistency penalty
        consistency_deduction = 0
        if has_inconsistent_evidence:
            consistency_deduction = consistency_penalty
            score += consistency_deduction  # penalty is negative
            notes.append(f"C: Inconsistent evidence penalty: {consistency_deduction}")

        # Summary note
        if clinical_matches:
            notes.insert(0, f"C: Clinical evidence ({len(clinical_matches)} matches, hierarchy-weighted): +{round(score - product_bonus - consistency_deduction, 1)}")

        # Cap at max
        raw_score = score
        score = min(max(score, 0), max_c)

        return {
            "score": round(score, 1),
            "max": max_c,
            "subcategories": [
                {
                    "name": "Clinical Evidence (Hierarchy-Weighted)",
                    "score": round(score, 1),
                    "max": max_c,
                    "details": evidence_details if evidence_details else None,
                    "note": f"{len(clinical_matches)} ingredients with evidence" if clinical_matches else "No clinical evidence found"
                }
            ],
            "details": {
                "clinical_matches": len(clinical_matches),
                "evidence_breakdown": evidence_details,
                "ingredient_scores": ingredient_scores,
                "has_product_trial": has_product_trial,
                "product_trial_bonus": product_bonus,
                "has_inconsistent_evidence": has_inconsistent_evidence,
                "consistency_penalty_applied": consistency_deduction if has_inconsistent_evidence else 0,
                "raw_score_before_cap": round(raw_score, 1),
                "notes": notes
            }
        }

    # =========================================================================
    # SECTION D: BRAND TRUST (0-10 POINTS)
    # =========================================================================

    def _score_d_top_manufacturer(self, top_mfr: Dict) -> Tuple[int, List[str]]:
        """Score top manufacturer bonus (+3 for exact/high-confidence match)."""
        top_pts = self.section_d_config.get('top_manufacturer', {}).get('points', 3)
        notes = []

        if not top_mfr.get('found', False):
            return 0, notes

        match_type = top_mfr.get('match_type', 'exact')
        confidence = top_mfr.get('match_confidence', 1.0)

        if match_type == 'exact' or confidence >= 0.85:
            notes.append(f"D: Top manufacturer ({top_mfr.get('name', 'unknown')}): +{top_pts}")
            return top_pts, notes

        return 0, notes

    def _score_d_country(self, country_data: Dict) -> Tuple[int, List[str]]:
        """Score high-regulation country bonus (+1)."""
        if not country_data.get('found', False):
            return 0, []

        country = country_data.get('country', '')
        high_reg_countries = self.section_d_config.get('high_regulation_country', {}).get(
            'countries', ['USA', 'EU', 'Canada', 'Australia', 'Japan']
        )

        if any(c.lower() in country.lower() for c in high_reg_countries):
            country_pts = self.section_d_config.get('high_regulation_country', {}).get('points', 1)
            return country_pts, [f"D: High-regulation country ({country}): +{country_pts}"]

        return 0, []

    def _score_d_bonus_features(self, bonus_features: Dict) -> Tuple[int, List[str], Dict]:
        """Score bonus features: physician-formulated (+1), sustainable packaging (+1)."""
        score = 0
        notes = []
        details = {'physician': False, 'sustainable': False}

        physician_pts = self.section_d_config.get('physician_formulated', {}).get('points', 1)
        if bonus_features.get('physician_formulated', False):
            score += physician_pts
            notes.append(f"D: Physician-formulated: +{physician_pts}")
            details['physician'] = True

        sustainable_pts = self.section_d_config.get('sustainable_packaging', {}).get('points', 1)
        if bonus_features.get('sustainability_claim', False):
            score += sustainable_pts
            notes.append(f"D: Sustainable packaging: +{sustainable_pts}")
            details['sustainable'] = True

        return score, notes, details

    def _score_d_violations(self, violations: Dict) -> Tuple[int, List[str]]:
        """Score manufacturer violations (negative, capped at -20)."""
        if not violations.get('found', False):
            return 0, []

        violation_list = violations.get('violations', [])
        total_deduction = sum(v.get('total_deduction', -3) for v in violation_list)
        violation_cap = self.section_d_config.get('manufacturer_violations', {}).get('cap_total', -20)
        total_deduction = max(total_deduction, violation_cap)

        return total_deduction, [f"D: Manufacturer violations ({len(violation_list)}): {total_deduction}"]

    def _score_section_d(self, product: Dict) -> Dict:
        """
        Score Section D: Brand Trust

        - Top manufacturer (+3)
        - Physician-formulated (+1)
        - High-regulation country (+1)
        - Sustainable packaging (+1)
        - Manufacturer violations (deductions, cap -20)
        """
        manufacturer_data = product.get('manufacturer_data', {})
        max_d = self.section_max.get('D_brand_trust', 8)

        # Extract data
        top_mfr = manufacturer_data.get('top_manufacturer', {})
        country_data = manufacturer_data.get('country_of_origin', {})
        bonus_features = manufacturer_data.get('bonus_features', {})
        violations = manufacturer_data.get('violations', {})

        # Score each component
        top_pts, top_notes = self._score_d_top_manufacturer(top_mfr)
        country_pts, country_notes = self._score_d_country(country_data)
        bonus_pts, bonus_notes, bonus_details = self._score_d_bonus_features(bonus_features)
        violation_pts, violation_notes = self._score_d_violations(violations)

        # Calculate total
        raw_score = top_pts + country_pts + bonus_pts + violation_pts
        score = max(min(raw_score, max_d), 0)
        notes = top_notes + country_notes + bonus_notes + violation_notes

        # Get config values for output
        top_pts_config = self.section_d_config.get('top_manufacturer', {}).get('points', 3)
        physician_pts_config = self.section_d_config.get('physician_formulated', {}).get('points', 1)
        country_pts_config = self.section_d_config.get('high_regulation_country', {}).get('points', 1)
        sustainable_pts_config = self.section_d_config.get('sustainable_packaging', {}).get('points', 1)

        return {
            "score": round(score, 1),
            "max": max_d,
            "subcategories": [
                {"name": self.section_d_config.get('top_manufacturer', {}).get('name', 'Top-Tier Manufacturer'),
                 "score": top_pts, "max": top_pts_config,
                 "note": f"Matched to {top_mfr.get('name', 'N/A')}" if top_mfr.get('found') else "N/A"},
                {"name": self.section_d_config.get('physician_formulated', {}).get('name', 'Physician/Formulator Credibility'),
                 "score": physician_pts_config if bonus_details['physician'] else 0, "max": physician_pts_config,
                 "note": "Yes" if bonus_details['physician'] else "N/A"},
                {"name": self.section_d_config.get('high_regulation_country', {}).get('name', 'Made in High-Regulation Country'),
                 "score": country_pts, "max": country_pts_config,
                 "note": country_data.get('country', 'N/A') if country_data.get('found') else "N/A"},
                {"name": self.section_d_config.get('sustainable_packaging', {}).get('name', 'Sustainable/Recyclable Packaging'),
                 "score": sustainable_pts_config if bonus_details['sustainable'] else 0, "max": sustainable_pts_config,
                 "note": bonus_features.get('sustainability_text', 'N/A') if bonus_details['sustainable'] else "N/A"},
                {"name": self.section_d_config.get('manufacturer_violations', {}).get('name', 'Manufacturer Violations (Last 10y)'),
                 "score": round(violation_pts, 1), "max": 0,
                 "note": f"{len(violations.get('violations', []))} violations" if violations.get('found') else "None found"}
            ],
            "details": {
                "top_manufacturer": top_mfr.get('found', False),
                "notes": notes
            }
        }

    # =========================================================================
    # PROBIOTIC BONUS (0-10 POINTS)
    # =========================================================================

    def _score_probiotic_cfu(self, probiotic_data: Dict) -> Tuple[int, List[str], Dict]:
        """Score probiotic CFU bonus (max +4 for ≥10B at expiration)."""
        cfu_config = self.probiotic_config.get('cfu_bonus', {})
        cfu_pts_config = cfu_config.get('threshold_10b', 4)
        max_cfu_billions = 0
        cfu_guarantee = None
        notes = []

        for blend in probiotic_data.get('probiotic_blends', []):
            blend_cfu = blend.get('cfu_data', {})
            if blend_cfu.get('has_cfu', False):
                billions = blend_cfu.get('billion_count', 0)
                if billions > max_cfu_billions:
                    max_cfu_billions = billions
                    cfu_guarantee = blend_cfu.get('guarantee_type')

        cfu_pts = 0
        if max_cfu_billions >= 10:
            if cfu_guarantee == 'expiration':
                cfu_pts = cfu_pts_config
                notes.append(f"Probiotic: {max_cfu_billions}B CFU at expiration: +{cfu_pts}")
            else:
                notes.append(f"Probiotic: {max_cfu_billions}B CFU (not guaranteed at expiration)")

        cfu_note = f"{max_cfu_billions}B CFU" if max_cfu_billions > 0 else "N/A"
        if cfu_guarantee:
            cfu_note += f" ({cfu_guarantee})"

        return cfu_pts, notes, {"max_billions": max_cfu_billions, "guarantee": cfu_guarantee, "note": cfu_note}

    def _score_probiotic_strain_diversity(self, probiotic_data: Dict) -> Tuple[int, List[str], str]:
        """Score probiotic strain diversity (tiered: +2 for ≥4, +4 for ≥8)."""
        strain_config = self.probiotic_config.get('strain_diversity', {})
        total_strain_count = probiotic_data.get('total_strain_count', 0)
        strain_pts = 0
        notes = []

        if total_strain_count >= 8:
            strain_pts = strain_config.get('threshold_8_strains', 4)
        elif total_strain_count >= 4:
            strain_pts = strain_config.get('threshold_4_strains', 2)

        if strain_pts > 0:
            notes.append(f"Probiotic: {total_strain_count} strains: +{strain_pts}")

        note = f"{total_strain_count} distinct strains" if total_strain_count > 0 else "N/A"
        return strain_pts, notes, note

    def _score_probiotic_clinical_strains(self, probiotic_data: Dict) -> Tuple[int, List[str], str]:
        """Score clinical strain presence (+2 if present)."""
        clinical_config = self.probiotic_config.get('clinical_strains', {})
        clinical_pts_config = clinical_config.get('points', 2)
        clinical_strains = probiotic_data.get('clinical_strains', [])
        notes = []
        clinical_pts = 0

        if clinical_strains:
            clinical_pts = clinical_pts_config
            notes.append(f"Probiotic: Clinical strains ({len(clinical_strains)}): +{clinical_pts}")

        # Extract strain names - handle both dict format and string format
        strain_names = []
        for s in clinical_strains[:3]:
            if isinstance(s, dict):
                name = s.get('strain_name') or s.get('name') or s.get('strain') or str(s)
                strain_names.append(name)
            else:
                strain_names.append(str(s))

        note = ', '.join(strain_names) if clinical_strains else "N/A"
        return clinical_pts, notes, note

    def _score_probiotic_prebiotic(self, probiotic_data: Dict) -> Tuple[int, List[str], str]:
        """Score prebiotic pairing bonus (+3 if present)."""
        prebiotic_config = self.probiotic_config.get('prebiotic_pairing', {})
        prebiotic_pts_config = prebiotic_config.get('points', 3)
        notes = []
        prebiotic_pts = 0

        if probiotic_data.get('prebiotic_present', False):
            prebiotic_pts = prebiotic_pts_config
            notes.append(f"Probiotic: Prebiotic pairing: +{prebiotic_pts}")

        note = "Yes" if probiotic_data.get('prebiotic_present') else "N/A"
        return prebiotic_pts, notes, note

    def _score_probiotic_survivability(self, probiotic_data: Dict) -> Tuple[int, List[str], str]:
        """Score survivability coating bonus (+2 if present)."""
        survivability_config = self.probiotic_config.get('survivability_coating', {})
        survivability_pts_config = survivability_config.get('points', 2)
        notes = []
        survivability_pts = 0

        if probiotic_data.get('has_survivability_coating', False):
            survivability_pts = survivability_pts_config
            reason = probiotic_data.get('survivability_reason', 'detected')
            notes.append(f"Probiotic: Survivability coating ({reason}): +{survivability_pts}")

        note = probiotic_data.get('survivability_reason', 'N/A') if probiotic_data.get('has_survivability_coating') else "N/A"
        return survivability_pts, notes, note

    def _score_probiotic_bonus(self, product: Dict) -> Dict:
        """
        Score Probiotic Bonus (only if is_probiotic_product = true)

        Enhanced probiotic scoring with tiered strain diversity and clinical strain detection.
        - CFU bonus (+4 if >= 10B at expiration)
        - Strain diversity (+2 if >= 4 strains, +4 if >= 8 strains)
        - Clinical strains (+3)
        - Prebiotic pairing (+3)
        - Survivability coating (+2)
        Total cap: 10 points max
        """
        probiotic_data = product.get('probiotic_data', {})
        max_probiotic = self.probiotic_config.get('_max', 10)

        # Get config names for subcategory output
        cfu_name = self.probiotic_config.get('cfu_bonus', {}).get('name', '≥10 Billion CFU at Expiration')
        strain_name = self.probiotic_config.get('strain_diversity', {}).get('name', '≥4 Clinically Studied Strains')
        clinical_name = self.probiotic_config.get('clinical_strains', {}).get('name', 'Contains Clinically Studied Strains')
        prebiotic_name = self.probiotic_config.get('prebiotic_pairing', {}).get('name', 'Prebiotic Pairing')
        survivability_name = self.probiotic_config.get('survivability_coating', {}).get('name', 'Survivability Coating/Technology')

        if not probiotic_data.get('is_probiotic_product', False):
            return {
                "score": 0, "max": max_probiotic, "applied": False,
                "subcategories": [
                    {"name": cfu_name, "score": 0, "note": "Not a probiotic"},
                    {"name": strain_name, "score": 0, "note": "Not a probiotic"},
                    {"name": clinical_name, "score": 0, "note": "Not a probiotic"},
                    {"name": prebiotic_name, "score": 0, "note": "Not a probiotic"},
                    {"name": survivability_name, "score": 0, "note": "Not a probiotic"}
                ],
                "details": {"is_probiotic": False, "notes": []}
            }

        # Score each probiotic bonus category
        cfu_pts, cfu_notes, cfu_details = self._score_probiotic_cfu(probiotic_data)
        strain_pts, strain_notes, strain_note = self._score_probiotic_strain_diversity(probiotic_data)
        clinical_pts, clinical_notes, clinical_note = self._score_probiotic_clinical_strains(probiotic_data)
        prebiotic_pts, prebiotic_notes, prebiotic_note = self._score_probiotic_prebiotic(probiotic_data)
        survivability_pts, survivability_notes, survivability_note = self._score_probiotic_survivability(probiotic_data)

        # Combine scores and notes (cap at max_probiotic = 10)
        uncapped_score = cfu_pts + strain_pts + clinical_pts + prebiotic_pts + survivability_pts
        score = min(uncapped_score, max_probiotic)
        notes = cfu_notes + strain_notes + clinical_notes + prebiotic_notes + survivability_notes

        return {
            "score": round(score, 1),
            "max": max_probiotic,
            "applied": True,
            "uncapped_score": round(uncapped_score, 1),
            "subcategories": [
                {"name": cfu_name, "score": cfu_pts, "note": cfu_details['note']},
                {"name": strain_name, "score": strain_pts, "note": strain_note},
                {"name": clinical_name, "score": clinical_pts, "note": clinical_note},
                {"name": prebiotic_name, "score": prebiotic_pts, "note": prebiotic_note},
                {"name": survivability_name, "score": survivability_pts, "note": survivability_note}
            ],
            "details": {
                "is_probiotic": True,
                "cfu_billions": cfu_details['max_billions'],
                "cfu_guarantee": cfu_details['guarantee'],
                "strain_count": probiotic_data.get('total_strain_count', 0),
                "clinical_strain_count": len(probiotic_data.get('clinical_strains', [])),
                "has_survivability_coating": probiotic_data.get('has_survivability_coating', False),
                "notes": notes
            }
        }

    # =========================================================================
    # MAIN SCORING METHOD
    # =========================================================================

    def score_product(self, product: Dict) -> Dict:
        """
        Calculate complete score for a product.
        Returns scored product with section breakdown.
        """
        product_id = product.get('dsld_id', product.get('id', 'unknown'))
        product_name = product.get('product_name', product.get('fullName', 'Unknown Product'))

        # Validate enriched product structure
        is_valid, validation_issues = self.validate_enriched_product(product)
        if not is_valid:
            self.logger.error(f"Product {product_id}: Validation failed - {validation_issues}")
            return self._create_failed_score(product_id, product_name, f"Validation failed: {'; '.join(validation_issues)}")

        # Log warnings for non-critical issues
        if validation_issues:
            for issue in validation_issues:
                self.logger.warning(f"Product {product_id}: {issue}")

        try:
            # Check enrichment version compatibility (already done in validation, but log here too)
            enrichment_version = product.get('enrichment_version', 'unknown')
            if enrichment_version not in self.COMPATIBLE_ENRICHMENT_VERSIONS:
                self.logger.warning(
                    f"Product {product_id}: Enrichment version {enrichment_version} "
                    f"may not be compatible with scorer {self.VERSION}"
                )

            # Score each section
            section_a = self._score_section_a(product)
            section_b = self._score_section_b(product)
            section_c = self._score_section_c(product)
            section_d = self._score_section_d(product)
            probiotic = self._score_probiotic_bonus(product)

            # Calculate total score (80 points max without Section E)
            # Base score from sections A-D
            base_score = sum([
                section_a['score'],
                section_b['score'],
                section_c['score'],
                section_d['score']
            ])

            # Probiotic bonus is ADDITIONAL - allows score to temporarily exceed 80
            # Then ceiling is applied. This ensures a 80/80 product + 10pt probiotic bonus
            # gets full credit shown in breakdown even if final score is capped at 80
            probiotic_score = probiotic.get('score', 0)
            raw_score_with_probiotic = base_score + probiotic_score

            # Apply floor and ceiling
            floor = self.floors_ceilings.get('total_floor', 10)
            ceiling = self.floors_ceilings.get('total_ceiling', 80)
            score_80 = max(min(raw_score_with_probiotic, ceiling), floor)

            # Calculate /100 equivalent
            score_100_equivalent = (score_80 / 80) * 100

            # Collect all notes
            all_notes = []
            for section in [section_a, section_b, section_c, section_d, probiotic]:
                all_notes.extend(section.get('details', {}).get('notes', []))

            # Build detailed_breakdown for consumer-facing output
            detailed_breakdown = {
                "A_Ingredient_Quality": {
                    "total": section_a['score'],
                    "max": section_a['max'],
                    "subcategories": section_a.get('subcategories', [])
                },
                "B_Safety_and_Purity": {
                    "total": section_b['score'],
                    "max": section_b['max'],
                    "subcategories": section_b.get('subcategories', [])
                },
                "C_Evidence_and_Research": {
                    "total": section_c['score'],
                    "max": section_c['max'],
                    "subcategories": section_c.get('subcategories', [])
                },
                "D_Brand_Trust": {
                    "total": section_d['score'],
                    "max": section_d['max'],
                    "subcategories": section_d.get('subcategories', [])
                },
                "Probiotic_Bonus": {
                    "total": probiotic['score'],
                    "max": probiotic['max'],
                    "applied": probiotic.get('applied', False),
                    "subcategories": probiotic.get('subcategories', [])
                }
            }

            # Build scored product with both formats for backward compatibility
            scored_product = {
                "dsld_id": product_id,
                "product_name": product_name,
                "brand_name": product.get('brandName', ''),
                "score_80": round(score_80, 1),
                "score_100_equivalent": round(score_100_equivalent, 1),
                "display": f"{round(score_80, 1)}/80",
                "display_100": f"{round(score_100_equivalent, 1)}/100",
                "grade": self._calculate_grade(score_100_equivalent),
                # New consumer-facing detailed breakdown
                "detailed_breakdown": detailed_breakdown,
                # Legacy format for backward compatibility
                "section_scores": {
                    "A_ingredient_quality": {"score": section_a['score'], "max": section_a['max'], "earned": section_a['score']},
                    "B_safety_purity": {"score": section_b['score'], "max": section_b['max'], "earned": section_b['score']},
                    "C_evidence_research": {"score": section_c['score'], "max": section_c['max'], "earned": section_c['score']},
                    "D_brand_trust": {"score": section_d['score'], "max": section_d['max'], "earned": section_d['score']},
                    "probiotic_bonus": {"score": probiotic['score'], "max": probiotic['max'], "earned": probiotic['score']}
                },
                "scoring_notes": all_notes,
                "scoring_metadata": {
                    "scoring_version": self.VERSION,
                    "scored_date": datetime.utcnow().isoformat() + "Z",
                    "enrichment_version": enrichment_version,
                    "supplement_type": product.get('supplement_type', {}).get('type', 'unknown'),
                    "base_score": round(base_score, 1),
                    "probiotic_bonus_added": round(probiotic_score, 1),
                    "raw_score_before_ceiling": round(raw_score_with_probiotic, 1),
                    "ceiling_applied": raw_score_with_probiotic > ceiling,
                    "floor_applied": raw_score_with_probiotic < floor,
                    "immediate_fail": section_b.get('details', {}).get('immediate_fail', False)
                }
            }

            return scored_product

        except (KeyError, TypeError) as e:
            # Data structure issues - return failed score
            self.logger.error(f"Product {product_id}: Data structure error during scoring: {e}")
            return self._create_failed_score(product_id, product_name, f"Data structure error: {e}")
        except (ValueError, AttributeError) as e:
            # Value/attribute issues
            self.logger.error(f"Product {product_id}: Value error during scoring: {e}")
            return self._create_failed_score(product_id, product_name, f"Value error: {e}")
        except Exception as e:
            # Unexpected error - log with traceback for debugging
            self.logger.error(f"Product {product_id}: Unexpected scoring error: {e}", exc_info=True)
            return self._create_failed_score(product_id, product_name, str(e))

    def _create_failed_score(self, product_id: str, product_name: str, error_msg: str) -> Dict:
        """Create a standardized failed score response"""
        return {
            "dsld_id": product_id,
            "product_name": product_name,
            "score_80": 10,  # Floor
            "score_100_equivalent": 12.5,
            "display": "10/80",
            "display_100": "12.5/100",
            "grade": "F",
            "error": error_msg,
            "scoring_metadata": {
                "scoring_version": self.VERSION,
                "scored_date": datetime.utcnow().isoformat() + "Z",
                "status": "failed"
            }
            }

    def _calculate_grade(self, score_100: float) -> str:
        """Calculate letter grade from /100 score"""
        grade_scale = self.config.get('grade_scale', {})

        if score_100 >= grade_scale.get('A_plus', {}).get('min', 90):
            return "A+"
        elif score_100 >= grade_scale.get('A', {}).get('min', 85):
            return "A"
        elif score_100 >= grade_scale.get('A_minus', {}).get('min', 80):
            return "A-"
        elif score_100 >= grade_scale.get('B_plus', {}).get('min', 77):
            return "B+"
        elif score_100 >= grade_scale.get('B', {}).get('min', 73):
            return "B"
        elif score_100 >= grade_scale.get('B_minus', {}).get('min', 70):
            return "B-"
        elif score_100 >= grade_scale.get('C_plus', {}).get('min', 67):
            return "C+"
        elif score_100 >= grade_scale.get('C', {}).get('min', 63):
            return "C"
        elif score_100 >= grade_scale.get('C_minus', {}).get('min', 60):
            return "C-"
        elif score_100 >= grade_scale.get('D', {}).get('min', 50):
            return "D"
        else:
            return "F"

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

    def process_batch(self, input_file: str, output_dir: str) -> Dict:
        """Process a batch of enriched products"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                products = json.load(f)

            if not isinstance(products, list):
                products = [products]

            self.logger.info(f"Scoring batch: {len(products)} products from {os.path.basename(input_file)}")

            scored_products = []
            score_distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
            fail_count = 0

            # Progress bar
            show_progress = self.config.get('processing', {}).get('show_progress_bar', True)
            iterator = products
            if show_progress and len(products) > 10 and TQDM_AVAILABLE:
                iterator = tqdm(products, desc="Scoring", unit="product")

            for product in iterator:
                scored = self.score_product(product)
                scored_products.append(scored)

                # Track distribution (with bounds check)
                grade = scored.get('grade', 'F')
                grade_letter = grade[0] if grade and len(grade) > 0 else 'F'
                score_distribution[grade_letter] = score_distribution.get(grade_letter, 0) + 1

                # Track fails
                if scored.get('scoring_metadata', {}).get('immediate_fail', False):
                    fail_count += 1

            # Save outputs
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            if base_name.startswith('enriched_'):
                base_name = base_name[9:]

            scored_dir = os.path.join(output_dir, "scored")
            os.makedirs(scored_dir, exist_ok=True)

            output_file = os.path.join(scored_dir, f"scored_{base_name}.json")

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(scored_products, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Saved {len(scored_products)} scored products to {output_file}")

            # Statistics
            scores = [p['score_80'] for p in scored_products if 'score_80' in p]
            avg_score = sum(scores) / len(scores) if scores else 0

            return {
                "total_products": len(products),
                "successful": len(scored_products),
                "immediate_fails": fail_count,
                "average_score_80": round(avg_score, 1),
                "average_score_100": round((avg_score / 80) * 100, 1),
                "score_distribution": score_distribution,
                "output_file": output_file
            }

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in batch {input_file}: {e}")
            raise
        except PermissionError as e:
            self.logger.error(f"Permission denied for batch {input_file}: {e}")
            raise
        except (IOError, OSError) as e:
            self.logger.error(f"I/O error processing batch {input_file}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error processing batch {input_file}: {e}", exc_info=True)
            raise

    def process_all(self, input_path: str, output_dir: str) -> Dict:
        """Process all files in input path"""
        script_dir = Path(__file__).parent

        if not os.path.isabs(input_path):
            input_path = script_dir / input_path
        if not os.path.isabs(output_dir):
            output_dir = script_dir / output_dir

        # Get input files
        input_files = []
        if os.path.isfile(input_path):
            input_files = [str(input_path)]
        elif os.path.isdir(input_path):
            input_files = [
                os.path.join(input_path, f)
                for f in os.listdir(input_path)
                if f.endswith('.json') and not f.startswith('.')
            ]
        else:
            raise FileNotFoundError(f"Input path not found: {input_path}")

        if not input_files:
            raise ValueError(f"No JSON files found in: {input_path}")

        self.logger.info(f"Found {len(input_files)} files to score")

        # Process all files
        start_time = datetime.utcnow()
        all_scores = []
        all_distributions = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        total_products = 0
        total_fails = 0

        for input_file in input_files:
            self.logger.info(f"Processing: {os.path.basename(input_file)}")
            batch_stats = self.process_batch(input_file, str(output_dir))

            total_products += batch_stats.get("total_products", 0)
            total_fails += batch_stats.get("immediate_fails", 0)
            all_scores.append(batch_stats.get("average_score_80", 0))

            for grade, count in batch_stats.get("score_distribution", {}).items():
                all_distributions[grade] = all_distributions.get(grade, 0) + count

        # Calculate overall averages
        if all_scores:
            overall_avg_80 = sum(all_scores) / len(all_scores)
            overall_avg_100 = (overall_avg_80 / 80) * 100
        else:
            overall_avg_80 = 0
            overall_avg_100 = 0

        # Generate summary
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        summary = {
            "processing_info": {
                "scoring_version": self.VERSION,
                "files_processed": len(input_files),
                "duration_seconds": round(duration, 2),
                "timestamp": end_time.isoformat() + "Z"
            },
            "stats": {
                "total_products": total_products,
                "immediate_fails": total_fails,
                "average_score_80": round(overall_avg_80, 1),
                "average_score_100": round(overall_avg_100, 1),
                "score_distribution": all_distributions
            },
            "scoring_rules": {
                "max_section_A": self.section_max.get('A_ingredient_quality', 30),
                "max_section_B": self.section_max.get('B_safety_purity', 45),
                "max_section_C": self.section_max.get('C_evidence_research', 15),
                "max_section_D": self.section_max.get('D_brand_trust', 10),
                "max_total": 80,
                "probiotic_bonus_max": 10,
                "note": "Section E (User Profile, +20 max) scored on device"
            }
        }

        # Save summary
        reports_dir = os.path.join(output_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        summary_file = os.path.join(
            reports_dir,
            f"scoring_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        self.logger.info("=" * 50)
        self.logger.info("SCORING COMPLETE")
        self.logger.info(f"Total products: {total_products}")
        self.logger.info(f"Immediate fails: {total_fails}")
        self.logger.info(f"Average score: {overall_avg_80:.1f}/80 ({overall_avg_100:.1f}/100)")
        self.logger.info(f"Distribution: {all_distributions}")
        self.logger.info(f"Duration: {duration:.2f}s")
        self.logger.info(f"Summary saved: {summary_file}")
        self.logger.info("=" * 50)

        return summary


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='DSLD Supplement Scoring System v3.1.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python score_supplements.py
    python score_supplements.py --config config/scoring_config.json
    python score_supplements.py --input-dir enriched_data --output-dir scored_output
    python score_supplements.py --dry-run
        """
    )

    parser.add_argument('--config', default='config/scoring_config.json',
                        help='Scoring configuration file path')
    parser.add_argument('--input-dir', help='Input directory (overrides config)')
    parser.add_argument('--output-dir', help='Output directory (overrides config)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Test run without writing files')

    args = parser.parse_args()

    try:
        scorer = SupplementScorer(args.config)

        # Determine paths
        if args.input_dir and args.output_dir:
            input_path = args.input_dir
            output_dir = args.output_dir
        else:
            paths = scorer.config.get('paths', {})
            input_path = paths.get('input_directory', 'output_Lozenges_enriched/enriched')
            output_dir = paths.get('output_directory', 'output_Lozenges_scored')

        if args.dry_run:
            scorer.logger.info("DRY RUN MODE")
            scorer.logger.info(f"Would score files from: {input_path}")
            scorer.logger.info(f"Would output to: {output_dir}")
            return

        scorer.process_all(input_path, output_dir)

    except FileNotFoundError as e:
        logging.error(f"File or directory not found: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON file: {e}")
        sys.exit(1)
    except PermissionError as e:
        logging.error(f"Permission denied: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Scoring interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
