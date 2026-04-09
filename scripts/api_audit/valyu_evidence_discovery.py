#!/usr/bin/env python3
"""
Valyu Clinical Evidence Discovery & Audit Tool
==============================================
Uses the Valyu API to find 2025-2026 clinical evidence for ingredients,
auditing existing records for staleness and discovering new high-tier evidence.

Outputs:
    - scripts/reports/valyu_discovery_report.json (Human-readable audit)
    - scripts/data/quarantine/valyu_pending_updates.json (Ready to merge)
"""

import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root and scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import env_loader  # noqa: F401 - Loads .env
try:
    from valyu import Valyu
except ImportError:
    print("[ERROR] Valyu SDK not found. Install with: pip install valyu")
    sys.exit(1)

# Config
VALYU_API_KEY = os.environ.get("VALYU_API_KEY")
CLINICAL_DB_PATH = PROJECT_ROOT / "scripts/data/backed_clinical_studies.json"
REPORT_OUTPUT = PROJECT_ROOT / "scripts/reports/valyu_discovery_report.json"
QUARANTINE_PATH = PROJECT_ROOT / "scripts/data/quarantine/valyu_pending_updates.json"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("valyu_audit")

class ValyuEvidenceAuditor:
    def __init__(self):
        if not VALYU_API_KEY:
            logger.error("VALYU_API_KEY not found in environment.")
            sys.exit(1)
        self.client = Valyu(api_key=VALYU_API_KEY)
        self.clinical_db = self._load_db()
        self.results = {
            "metadata": {
                "audit_date": datetime.now().isoformat(),
                "valyu_sources": ["valyu/valyu-pubmed", "valyu/valyu-clinical-trials", "valyu/valyu-chembl"]
            },
            "new_discoveries": [],
            "stale_audits": [],
            "errors": []
        }

    def _load_db(self) -> Dict:
        with open(CLINICAL_DB_PATH, 'r') as f:
            return json.load(f)

    def audit_ingredient(self, ingredient_name: str, current_record: Optional[Dict] = None):
        """
        Search for 2025-2026 evidence for an ingredient.
        """
        logger.info(f"Auditing: {ingredient_name}...")
        
        # 1. Construct Targeted Query
        # We look for Systematic Reviews or RCTs in the last 18 months (2025-2026)
        query = f"latest 2025 2026 clinical trials systematic review meta-analysis for {ingredient_name} supplement"
        
        try:
            # Use Answer API for a grounded, cited response
            answer_response = self.client.answer(
                query=query,
                search_type="proprietary",
                included_sources=["valyu/valyu-pubmed", "valyu/valyu-clinical-trials"]
            )
            
            # Extract content and references
            answer_text = str(getattr(answer_response, 'contents', ""))
            search_results = getattr(answer_response, 'search_results', [])
            
            # 2. Extract structured citations for DB merging
            extracted_refs = []
            for res in search_results:
                # Only pull from PubMed/ClinicalTrials sources
                url = str(getattr(res, 'url', ""))
                if "pubmed" in url or "clinicaltrials.gov" in url:
                    ref = {
                        "type": "pubmed" if "pubmed" in url else "clinical_trials_gov",
                        "title": getattr(res, 'title', ""),
                        "url": url,
                        "published_date": getattr(res, 'publication_date', ""),
                        "doi": getattr(res, 'doi', None)
                    }
                    # Extract PMID from URL if possible
                    if "pubmed.ncbi.nlm.nih.gov/" in url:
                        ref["pmid"] = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
                    extracted_refs.append(ref)

            # 2. Analyze the result
            audit_entry = {
                "name": ingredient_name,
                "timestamp": datetime.now().isoformat(),
                "valyu_summary": answer_text,
                "top_citations": extracted_refs[:3],  # Keep top 3 for review
                "status": "reviewed",
                "current_tier": current_record.get("score_contribution") if current_record else "none"
            }

            # Simple logic to flag staleness/discovery
            text = answer_text.lower()
            if "contradicts" in text or "no effect" in text or "null results" in text:
                audit_entry["status"] = "STALE_CONTRADICTION"
                audit_entry["recommendation"] = "Review for evidence downgrade"
            elif "2026" in text or "2025" in text:
                if current_record:
                    audit_entry["status"] = "STALE_UPGRADE"
                    audit_entry["recommendation"] = "New 2025/2026 evidence found - Update record"
                else:
                    audit_entry["status"] = "NEW_DISCOVERY"
                    audit_entry["recommendation"] = "Add new ingredient to clinical DB"

            if current_record:
                self.results["stale_audits"].append(audit_entry)
            else:
                self.results["new_discoveries"].append(audit_entry)

        except Exception as e:
            logger.error(f"Valyu API error for {ingredient_name}: {e}")
            self.results["errors"].append({"name": ingredient_name, "error": str(e)})

    def run_batch_audit(self, limit: int = 5, discovery_limit: int = 5):
        """
        Audit existing DB + discover new high-priority ingredients.
        """
        # 1. Audit high-tier existing items for staleness/upgrades
        top_existing = [
            item for item in self.clinical_db.get("backed_clinical_studies", [])
            if item.get("score_contribution") == "tier_1"
        ][:limit]
        
        for item in top_existing:
            self.audit_ingredient(item["standard_name"], item)

        # 2. Discovery: Scan unmapped ingredients from high-volume brands (e.g. GNC)
        # This acts as the 'discovery layer' for ingredients not yet in your DB
        gnc_unmapped = PROJECT_ROOT / "scripts/output_GNC/unmapped/unmapped_inactive_ingredients.json"
        if gnc_unmapped.exists():
            with open(gnc_unmapped, 'r') as f:
                data = json.load(f)
                unmapped_list = data.get("unmapped_ingredients", {})
                # Sort by occurrence (high-impact first)
                sorted_unmapped = sorted(unmapped_list.items(), key=lambda x: x[1], reverse=True)
                
                # Check top N unmapped for clinical significance
                for name, count in sorted_unmapped[:discovery_limit]:
                    # Skip if already in clinical DB
                    if any(item["standard_name"].lower() == name.lower() for item in self.clinical_db.get("backed_clinical_studies", [])):
                        continue
                    self.audit_ingredient(name, None)

        # 3. Save Report
        self._save_results()

    def _save_results(self):
        # Create directories if missing
        REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(REPORT_OUTPUT, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Audit report saved to {REPORT_OUTPUT}")

if __name__ == "__main__":
    # Ensure VALYU_API_KEY is available or prompt user
    if not os.environ.get("VALYU_API_KEY"):
        print("\n[!] VALYU_API_KEY not found in .env")
        print("Please add VALYU_API_KEY=your_key to your .env file or export it.")
        sys.exit(1)

    auditor = ValyuEvidenceAuditor()
    # For demo, we audit the first 5 Tier-1 ingredients
    auditor.run_batch_audit(limit=5)
