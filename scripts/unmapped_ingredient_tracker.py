"""
Unmapped Ingredient Tracker Module
==================================

Tracks and reports unmapped ingredients during the cleaning process
to help identify ingredients that need to be added to the reference databases.

Author: PharmaGuide Team
Version: 1.0.0
"""

import json
import logging
from pathlib import Path
from typing import Dict, Set, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class UnmappedIngredientTracker:
    """Tracks unmapped ingredients and generates reports for database enrichment"""
    
    def __init__(self, output_path: Path):
        """Initialize the tracker with output directory
        
        Args:
            output_path: Directory where tracking files will be saved
        """
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.unmapped_active = {}
        self.unmapped_inactive = {}
        self.needs_verification_active: List[Dict[str, Any]] = []
        self.needs_verification_inactive: List[Dict[str, Any]] = []
        self.processed_count = 0
        
        logger.info(f"Initialized UnmappedIngredientTracker with output: {self.output_path}")
    
    def process_unmapped_ingredients(
        self,
        unmapped_data: Dict[str, int],
        active_ingredients: Set[str],
        details_by_name: Optional[Dict[str, Dict[str, Any]]] = None,
        processed_count_override: Optional[int] = None,
    ):
        """Process and categorize unmapped ingredients
        
        Args:
            unmapped_data: Dictionary of ingredient names to occurrence counts
            active_ingredients: Set of active ingredient names
            details_by_name: Optional context/details keyed by ingredient name
        """
        details_by_name = details_by_name or {}
        if processed_count_override is not None:
            self.processed_count = processed_count_override
        else:
            self.processed_count += len(unmapped_data)
        
        for ingredient_name, count in unmapped_data.items():
            details = details_by_name.get(ingredient_name, {})
            if ingredient_name in active_ingredients:
                # This is an active ingredient
                if ingredient_name in self.unmapped_active:
                    self.unmapped_active[ingredient_name] += count
                else:
                    self.unmapped_active[ingredient_name] = count
            else:
                # This is an inactive ingredient
                if ingredient_name in self.unmapped_inactive:
                    self.unmapped_inactive[ingredient_name] += count
                else:
                    self.unmapped_inactive[ingredient_name] = count

            if details.get("needs_verification"):
                verification_row = {
                    "label_text": ingredient_name,
                    "occurrences": count,
                    "reason": details.get("verification_reason", "needs_verification"),
                    "raw_ingredient_group": details.get("raw_ingredient_group"),
                    "conflicting_candidates": details.get("conflicting_candidates", []),
                    "next_verification_step": details.get("next_verification_step"),
                }
                if ingredient_name in active_ingredients:
                    self.needs_verification_active.append(verification_row)
                else:
                    self.needs_verification_inactive.append(verification_row)
        
        logger.debug(f"Processed {len(unmapped_data)} unmapped ingredients")
    
    def save_tracking_files(self):
        """Save tracking data to JSON files"""
        try:
            # Sort ingredients by count (descending) for easier review
            sorted_active = dict(sorted(
                self.unmapped_active.items(), 
                key=lambda x: x[1], 
                reverse=True
            ))
            
            sorted_inactive = dict(sorted(
                self.unmapped_inactive.items(), 
                key=lambda x: x[1], 
                reverse=True
            ))
            
            if self.processed_count == 0:
                logger.warning(
                    "UnmappedIngredientTracker: saving with processed_count=0. "
                    "Output files reflect no products — data is likely from a partial or empty run."
                )

            # Save active ingredients
            active_file = self.output_path / "unmapped_active_ingredients.json"
            with open(active_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "products_processed": self.processed_count,
                        "total_unmapped": len(sorted_active),
                        "total_occurrences": sum(sorted_active.values())
                    },
                    "unmapped_ingredients": sorted_active
                }, f, indent=2, ensure_ascii=False)

            # Save inactive ingredients
            inactive_file = self.output_path / "unmapped_inactive_ingredients.json"
            with open(inactive_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "products_processed": self.processed_count,
                        "total_unmapped": len(sorted_inactive),
                        "total_occurrences": sum(sorted_inactive.values())
                    },
                    "unmapped_ingredients": sorted_inactive
                }, f, indent=2, ensure_ascii=False)

            needs_active_file = self.output_path / "needs_verification_active_ingredients.json"
            with open(needs_active_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "products_processed": self.processed_count,
                        "total_needs_verification": len(self.needs_verification_active),
                        "total_occurrences": sum(row["occurrences"] for row in self.needs_verification_active),
                    },
                    "ingredients": sorted(
                        self.needs_verification_active,
                        key=lambda row: (-row["occurrences"], row["label_text"]),
                    ),
                }, f, indent=2, ensure_ascii=False)

            needs_inactive_file = self.output_path / "needs_verification_inactive_ingredients.json"
            with open(needs_inactive_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "products_processed": self.processed_count,
                        "total_needs_verification": len(self.needs_verification_inactive),
                        "total_occurrences": sum(row["occurrences"] for row in self.needs_verification_inactive),
                    },
                    "ingredients": sorted(
                        self.needs_verification_inactive,
                        key=lambda row: (-row["occurrences"], row["label_text"]),
                    ),
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved unmapped tracking files:")
            logger.info(f"  - Active: {len(sorted_active)} ingredients -> {active_file}")
            logger.info(f"  - Inactive: {len(sorted_inactive)} ingredients -> {inactive_file}")
            logger.info(f"  - Needs verification active: {len(self.needs_verification_active)} ingredients -> {needs_active_file}")
            logger.info(f"  - Needs verification inactive: {len(self.needs_verification_inactive)} ingredients -> {needs_inactive_file}")
            
        except Exception as e:
            logger.error(f"Failed to save unmapped tracking files: {str(e)}")
            raise
