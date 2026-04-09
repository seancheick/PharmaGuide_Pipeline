#!/usr/bin/env python3
"""
Functional Ingredient Grouping Handler
Preserves context for ingredients with functional declarations (Natural Colors:, Natural Flavors:, etc.)
Implements FDA labeling best practices and transparency scoring
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class FunctionalGroupingHandler:
    """Handle functional ingredient groupings and transparency scoring"""

    def __init__(self):
        """Initialize with functional grouping patterns"""
        self.load_patterns()

    def load_patterns(self):
        """Load functional grouping patterns from database. Raises on failure."""
        config_path = Path(__file__).parent / 'data' / 'functional_ingredient_groupings.json'
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"FATAL: Failed to load functional grouping patterns from {config_path}: {e}. "
                f"Transparency scoring will be completely disabled without this file."
            ) from e

        self.groupings = data.get('functional_groupings', [])
        self.vague_terms = data.get('vague_terms_to_flag', [])
        self.bonuses = data.get('transparency_bonuses', [])

        # Build pattern matchers
        self.grouping_patterns = []
        for group in self.groupings:
            pattern = group.get('pattern', '')
            compiled = re.compile(pattern, re.IGNORECASE)
            self.grouping_patterns.append({
                'compiled': compiled,
                'config': group
            })
        logger.info("Loaded %d functional grouping patterns", len(self.grouping_patterns))

    def detect_functional_grouping(self, ingredient_text: str) -> Optional[Dict]:
        """
        Detect if ingredient has functional grouping
        Returns: {'type': str, 'prefix': str, 'ingredients': list, 'has_details': bool}
        """

        for pattern_info in self.grouping_patterns:
            match = pattern_info['compiled'].search(ingredient_text)

            if match:
                # Extract the prefix (e.g., "Natural Colors:")
                prefix = match.group(0)

                # Extract everything after the colon
                after_colon = ingredient_text[match.end():].strip()

                # Check if there are actual ingredient details
                has_details = bool(after_colon) and after_colon.lower() != 'not specified'

                # Split by commas to get individual ingredients
                ingredients = []
                if has_details:
                    ingredients = [ing.strip() for ing in after_colon.split(',') if ing.strip()]

                return {
                    'type': pattern_info['config']['type'],
                    'prefix': prefix,
                    'ingredients': ingredients,
                    'has_details': has_details,
                    'original_text': ingredient_text,
                    'config': pattern_info['config']
                }

        return None

    def check_for_vague_terms(self, ingredient_text: str) -> List[Dict]:
        """Check if ingredient uses vague terms without details"""
        flags = []

        for vague_term in self.vague_terms:
            term = vague_term['term']

            # Exact match for vague term (case insensitive)
            if re.search(rf'\b{re.escape(term)}\b', ingredient_text, re.IGNORECASE):
                # Check if it's just the vague term alone (no specifics after)
                # Look for pattern like "Natural Flavors" or "Natural Flavors." but not "Natural Flavors: Vanilla"
                is_vague = not re.search(rf'{re.escape(term)}\s*:', ingredient_text, re.IGNORECASE)

                if is_vague:
                    flags.append({
                        'term': term,
                        'severity': vague_term['severity'],
                        'penalty': vague_term['penalty'],
                        'flag': vague_term['flag'],
                        'message': vague_term['message']
                    })

        return flags

    def process_ingredient_for_cleaning(self, ingredient_text: str) -> Dict:
        """
        Process ingredient for cleaning script
        Returns structured data preserving functional context
        """

        # Check for functional grouping
        grouping = self.detect_functional_grouping(ingredient_text)

        if grouping:
            # Has functional grouping (e.g., "Natural Colors: Beet Root Powder")
            if grouping['has_details']:
                # Good transparency - preserve with context
                return {
                    'type': 'functional_group_with_details',
                    'functional_type': grouping['type'],
                    'prefix': grouping['prefix'],
                    'ingredients': grouping['ingredients'],
                    'original': ingredient_text,
                    'transparency': 'good',
                    'preserve_as_group': True
                }
            else:
                # Vague declaration (e.g., just "Natural Colors")
                return {
                    'type': 'functional_group_vague',
                    'functional_type': grouping['type'],
                    'prefix': grouping['prefix'],
                    'ingredients': [],
                    'original': ingredient_text,
                    'transparency': 'poor',
                    'flag_for_review': True
                }

        # Check for standalone vague terms
        vague_flags = self.check_for_vague_terms(ingredient_text)
        if vague_flags:
            return {
                'type': 'vague_declaration',
                'original': ingredient_text,
                'vague_flags': vague_flags,
                'transparency': 'poor',
                'flag_for_review': True
            }

        # Regular ingredient
        return {
            'type': 'regular',
            'original': ingredient_text,
            'transparency': 'standard'
        }

    def score_transparency_for_enrichment(self, ingredient_data: Dict) -> Dict:
        """
        Calculate transparency score for enrichment
        Returns: {'score': float, 'flags': list, 'bonuses': list}
        """

        result = {
            'transparency_score': 0,
            'flags': [],
            'bonuses': [],
            'penalties': []
        }

        ingredient_type = ingredient_data.get('type', 'regular')

        if ingredient_type == 'functional_group_with_details':
            # Good transparency - specific disclosure
            config = ingredient_data.get('config', {})
            score = config.get('transparency_score_with_details', 8)
            result['transparency_score'] = score
            result['bonuses'].append({
                'type': 'specific_functional_disclosure',
                'bonus': 1.0,
                'reason': f"Specific {ingredient_data['functional_type']} sources disclosed"
            })

        elif ingredient_type == 'functional_group_vague':
            # Poor transparency - vague declaration
            config = ingredient_data.get('config', {})
            score = config.get('transparency_score_without_details', 2)
            penalty = config.get('penalty_without_details', -1.5)

            result['transparency_score'] = score
            result['penalties'].append({
                'type': 'vague_functional_disclosure',
                'penalty': penalty,
                'reason': f"Generic {ingredient_data['functional_type']} declaration without specifics"
            })

            result['flags'].append({
                'severity': 'moderate',
                'flag': f"vague_{ingredient_data['functional_type']}_disclosure",
                'message': f"Uses vague declaration without listing specific ingredients"
            })

        elif ingredient_type == 'vague_declaration':
            # Standalone vague term
            for vague_flag in ingredient_data.get('vague_flags', []):
                result['flags'].append(vague_flag)
                result['penalties'].append({
                    'type': vague_flag['flag'],
                    'penalty': vague_flag['penalty'],
                    'reason': vague_flag['message']
                })

        return result
