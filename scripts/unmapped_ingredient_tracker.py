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
from typing import Dict, Set, Any
from datetime import datetime

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
        self.processed_count = 0
        
        logger.info(f"Initialized UnmappedIngredientTracker with output: {self.output_path}")
    
    def process_unmapped_ingredients(self, unmapped_data: Dict[str, int], active_ingredients: Set[str]):
        """Process and categorize unmapped ingredients
        
        Args:
            unmapped_data: Dictionary of ingredient names to occurrence counts
            active_ingredients: Set of active ingredient names
        """
        self.processed_count += len(unmapped_data)
        
        for ingredient_name, count in unmapped_data.items():
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
            
            # Save active ingredients
            active_file = self.output_path / "unmapped_active_ingredients.json"
            with open(active_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "generated_at": datetime.utcnow().isoformat() + "Z",
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
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                        "total_unmapped": len(sorted_inactive),
                        "total_occurrences": sum(sorted_inactive.values())
                    },
                    "unmapped_ingredients": sorted_inactive
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved unmapped tracking files:")
            logger.info(f"  - Active: {len(sorted_active)} ingredients -> {active_file}")
            logger.info(f"  - Inactive: {len(sorted_inactive)} ingredients -> {inactive_file}")
            
        except Exception as e:
            logger.error(f"Failed to save unmapped tracking files: {str(e)}")
            raise
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for unmapped ingredients
        
        Returns:
            Dictionary containing summary statistics
        """
        return {
            "total_processed": self.processed_count,
            "unmapped_active_count": len(self.unmapped_active),
            "unmapped_inactive_count": len(self.unmapped_inactive),
            "total_unmapped": len(self.unmapped_active) + len(self.unmapped_inactive),
            "active_occurrences": sum(self.unmapped_active.values()),
            "inactive_occurrences": sum(self.unmapped_inactive.values()),
            "total_occurrences": sum(self.unmapped_active.values()) + sum(self.unmapped_inactive.values())
        }
    
    def reset(self):
        """Reset all tracking data"""
        self.unmapped_active.clear()
        self.unmapped_inactive.clear() 
        self.processed_count = 0
        logger.info("Reset unmapped ingredient tracker")