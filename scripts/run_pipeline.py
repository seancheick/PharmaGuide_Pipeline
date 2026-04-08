#!/usr/bin/env python3
"""
DSLD Supplement Pipeline Runner
================================
Runs the complete data processing pipeline: Clean → Enrich → Score

This script orchestrates all three stages of data processing in sequence,
with proper error handling and progress reporting.

PIPELINE STAGES:
1. CLEAN   - clean_dsld_data.py: Raw DSLD data → Cleaned JSON
2. ENRICH  - enrich_supplements_v3.py: Cleaned data → Enriched data with quality metadata
3. SCORE   - score_supplements.py: Enriched data → Final scores

Usage:
    # Run complete pipeline
    python run_pipeline.py

    # Run specific stages only
    python run_pipeline.py --stages enrich,score
    python run_pipeline.py --stages score

    # Custom paths
    python run_pipeline.py --raw-dir raw_data --output-prefix my_dataset

    # Dry run (show what would be executed)
    python run_pipeline.py --dry-run

Author: PharmaGuide Team
Version: 1.0.0
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class PipelineRunner:
    """
    Orchestrates the complete DSLD data processing pipeline.
    """

    VERSION = "1.1.0"

    def __init__(self, config: Dict = None):
        """Initialize pipeline with configuration"""
        self.script_dir = Path(__file__).parent.resolve()  # Absolute path to scripts/
        self.config = config or self._default_config()
        self._check_cwd()

    def _check_cwd(self):
        """Warn if running from unexpected directory"""
        cwd = Path.cwd().resolve()
        expected_locations = [
            self.script_dir,  # scripts/
            self.script_dir.parent,  # repo root
        ]
        if cwd not in expected_locations:
            logger.warning(
                f"Running from unexpected directory: {cwd}\n"
                f"Expected: {self.script_dir} or {self.script_dir.parent}\n"
                f"Paths will be resolved relative to scripts/ directory."
            )

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to script_dir if not absolute"""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.script_dir / p

    def _validate_input_dir(self, input_dir: str, stage: str) -> bool:
        """
        Validate that input directory exists and contains expected files.

        Args:
            input_dir: Directory path to validate
            stage: Name of the stage for error messages

        Returns:
            True if valid, False otherwise
        """
        resolved = self._resolve_path(input_dir)
        if not resolved.exists():
            logger.error(f"[{stage}] Input directory not found: {resolved}")
            return False
        if not resolved.is_dir():
            logger.error(f"[{stage}] Input path is not a directory: {resolved}")
            return False

        # Check for JSON files
        json_files = list(resolved.glob("*.json"))
        if not json_files:
            logger.warning(f"[{stage}] No JSON files found in: {resolved}")

        logger.info(f"[{stage}] Validated input: {resolved} ({len(json_files)} JSON files)")
        return True

    def _validate_data_dir(self) -> bool:
        """Validate that required reference data files exist"""
        data_dir = self.script_dir / "data"
        critical_files = [
            "ingredient_quality_map.json",
            "banned_recalled_ingredients.json",
            "harmful_additives.json",
            "allergens.json",
        ]

        missing = []
        for f in critical_files:
            if not (data_dir / f).exists():
                missing.append(f)

        if missing:
            logger.error(f"Missing critical data files in {data_dir}: {missing}")
            return False

        logger.info(f"Validated data directory: {data_dir}")
        return True

    def _default_config(self) -> Dict:
        """Default pipeline configuration"""
        return {
            "stages": ["clean", "enrich", "score"],
            "paths": {
                "raw_directory": "raw_data",
                "output_prefix": "output_Lozenges",
                "cleaned_suffix": "cleaned",
                "enriched_suffix": "enriched",
                "scored_suffix": "scored"
            },
            "scripts": {
                "clean": "clean_dsld_data.py",
                "enrich": "enrich_supplements_v3.py",
                "score": "score_supplements.py"
            },
            "configs": {
                "clean": "config/cleaning_config.json",
                "enrich": "config/enrichment_config.json",
                "score": "config/scoring_config.json"
            }
        }

    def _run_script(self, script_name: str, args: List[str], dry_run: bool = False) -> bool:
        """Run a Python script with arguments"""
        script_path = self.script_dir / script_name

        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return False

        cmd = [sys.executable, str(script_path)] + args

        if dry_run:
            logger.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return True

        logger.info(f"Executing: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.script_dir),
                capture_output=False,  # Let output flow through
                text=True
            )

            if result.returncode != 0:
                logger.error(f"Script {script_name} failed with return code {result.returncode}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to run {script_name}: {e}")
            return False

    def run_clean(self, raw_dir: str, output_dir: str, dry_run: bool = False) -> bool:
        """
        Stage 1: Clean raw DSLD data

        Input: Raw JSON files from DSLD
        Output: Cleaned, normalized JSON files
        """
        logger.info("=" * 60)
        logger.info("STAGE 1: CLEANING")
        logger.info("=" * 60)

        script = self.config["scripts"]["clean"]
        config_file = self.config["configs"]["clean"]

        args = [
            "--input-dir", raw_dir,
            "--output-dir", output_dir
        ]

        # Add config if exists
        config_path = self.script_dir / config_file
        if config_path.exists():
            args.extend(["--config", str(config_path)])

        return self._run_script(script, args, dry_run)

    def run_enrich(self, cleaned_dir: str, output_dir: str, dry_run: bool = False) -> bool:
        """
        Stage 2: Enrich cleaned data

        Input: Cleaned JSON files
        Output: Enriched JSON files with quality metadata
        """
        logger.info("=" * 60)
        logger.info("STAGE 2: ENRICHMENT")
        logger.info("=" * 60)

        script = self.config["scripts"]["enrich"]
        config_file = self.config["configs"]["enrich"]

        args = [
            "--input-dir", cleaned_dir,
            "--output-dir", output_dir
        ]

        # Add config if exists
        config_path = self.script_dir / config_file
        if config_path.exists():
            args.extend(["--config", str(config_path)])

        return self._run_script(script, args, dry_run)

    def run_coverage_gate(
        self,
        enriched_dir: str,
        output_dir: str,
        block_on_failure: bool = True,
        dry_run: bool = False
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Stage 2.5: Coverage gate check (AC5 compliance)

        Validates enriched data meets coverage thresholds and correctness checks.

        Input: Enriched JSON files
        Output: Coverage report (JSON + Markdown)

        Returns:
            Tuple of (can_proceed, report_summary)
        """
        if dry_run:
            logger.info("[DRY RUN] Would run coverage gate on %s", enriched_dir)
            return True, None

        logger.info("=" * 60)
        logger.info("STAGE 2.5: COVERAGE GATE")
        logger.info("=" * 60)

        try:
            from coverage_gate import CoverageGate

            # Load enriched products
            enriched_path = self._resolve_path(enriched_dir)
            products = []

            for json_file in enriched_path.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            products.extend(data)
                        else:
                            products.append(data)
                except Exception as e:
                    logger.warning(f"Failed to load {json_file}: {e}")

            if not products:
                logger.warning("No enriched products found for coverage check")
                return True, None

            logger.info(f"Checking coverage for {len(products)} products...")

            # Run coverage gate
            gate = CoverageGate()
            result = gate.check_batch(products)

            # Generate reports
            report_dir = self._resolve_path(output_dir) / "reports"
            json_path, md_path = gate.generate_report(result, report_dir)

            # Log summary
            logger.info(f"Coverage Gate Results:")
            logger.info(f"  Total products: {result.total_products}")
            logger.info(f"  Can score: {result.products_can_score}")
            logger.info(f"  Blocked: {result.products_blocked}")
            logger.info(f"  Average coverage: {result.average_coverage:.1f}%")

            if result.issues_by_type:
                logger.info(f"  Correctness issues: {result.issues_by_type}")

            if result.blocked_product_ids:
                logger.warning(f"  Blocked products: {result.blocked_product_ids[:10]}...")

            logger.info(f"Reports generated: {json_path}, {md_path}")

            # Determine if we can proceed
            can_proceed = (result.products_blocked == 0) if block_on_failure else True

            if not can_proceed:
                logger.error(
                    f"Coverage gate FAILED: {result.products_blocked} products blocked. "
                    "See coverage report for details."
                )

            return can_proceed, {
                "total_products": result.total_products,
                "products_blocked": result.products_blocked,
                "average_coverage": result.average_coverage,
                "issues": result.issues_by_type
            }

        except ImportError:
            logger.warning("coverage_gate module not available, skipping coverage check")
            return True, None
        except Exception as e:
            logger.error(f"Coverage gate failed: {e}")
            return not block_on_failure, None

    def run_score(self, enriched_dir: str, output_dir: str, dry_run: bool = False) -> bool:
        """
        Stage 3: Score enriched data

        Input: Enriched JSON files
        Output: Scored JSON files with final ratings
        """
        logger.info("=" * 60)
        logger.info("STAGE 3: SCORING")
        logger.info("=" * 60)

        script = self.config["scripts"]["score"]
        config_file = self.config["configs"]["score"]

        args = [
            "--input-dir", enriched_dir,
            "--output-dir", output_dir
        ]

        # Add config if exists
        config_path = self.script_dir / config_file
        if config_path.exists():
            args.extend(["--config", str(config_path)])

        return self._run_script(script, args, dry_run)

    def run_pipeline(
        self,
        stages: List[str] = None,
        raw_dir: str = None,
        output_prefix: str = None,
        dry_run: bool = False,
        skip_coverage_gate: bool = False,
        coverage_gate_warn_only: bool = False
    ) -> Dict:
        """
        Run the complete pipeline or specified stages.

        Args:
            stages: List of stages to run ["clean", "enrich", "score"]
            raw_dir: Directory containing raw data
            output_prefix: Prefix for output directories
            dry_run: If True, show what would be executed without running

        Returns:
            Summary dict with timing and status
        """
        start_time = datetime.now(UTC)

        # Use defaults if not provided
        stages = stages or self.config["stages"]
        paths = self.config["paths"]

        raw_dir = raw_dir or paths.get("raw_directory", "raw_data")
        output_prefix = output_prefix or paths.get("output_prefix", "products/output")

        # Build paths
        cleaned_dir = f"{output_prefix}/{paths['cleaned_suffix']}"
        enriched_dir = f"{output_prefix}_enriched/{paths['enriched_suffix']}"
        scored_dir = f"{output_prefix}_scored"

        logger.info("=" * 60)
        logger.info("DSLD SUPPLEMENT PIPELINE")
        logger.info("=" * 60)
        logger.info(f"Script directory: {self.script_dir}")
        logger.info(f"Stages to run: {', '.join(stages)}")
        logger.info(f"Raw data: {raw_dir}")
        logger.info(f"Cleaned output: {cleaned_dir}")
        logger.info(f"Enriched output: {enriched_dir}")
        logger.info(f"Scored output: {scored_dir}")
        logger.info("=" * 60)

        results = {
            "stages_requested": stages,
            "stages_completed": [],
            "stages_failed": [],
            "dry_run": dry_run,
            "success": False
        }

        # Preflight validation: Check data directory
        if not dry_run:
            if not self._validate_data_dir():
                logger.error("Preflight failed: Missing critical data files")
                results["stages_failed"].append("preflight")
                return results

        # Stage 1: Clean
        if "clean" in stages:
            success = self.run_clean(raw_dir, f"{output_prefix}", dry_run)
            if success:
                results["stages_completed"].append("clean")
            else:
                results["stages_failed"].append("clean")
                if not dry_run:
                    logger.error("Pipeline stopped due to cleaning failure")
                    return results

        # Stage 2: Enrich
        if "enrich" in stages:
            # Use cleaned output from stage 1 as input
            enrich_input = cleaned_dir
            # Validate input directory exists (skip if clean just ran or dry_run)
            if not dry_run and "clean" not in results["stages_completed"]:
                if not self._validate_input_dir(enrich_input, "ENRICH"):
                    results["stages_failed"].append("enrich")
                    logger.error("Pipeline stopped: Enrichment input not found")
                    return results
            success = self.run_enrich(enrich_input, f"{output_prefix}_enriched", dry_run)
            if success:
                results["stages_completed"].append("enrich")
            else:
                results["stages_failed"].append("enrich")
                if not dry_run:
                    logger.error("Pipeline stopped due to enrichment failure")
                    return results

        # Stage 2.5: Coverage Gate (AC5)
        if "score" in stages and not dry_run and not skip_coverage_gate:
            # Run coverage gate before scoring
            block_on_failure = not coverage_gate_warn_only
            can_proceed, coverage_summary = self.run_coverage_gate(
                enriched_dir,
                f"{output_prefix}_enriched",
                block_on_failure=block_on_failure,
                dry_run=dry_run
            )
            results["coverage_gate"] = coverage_summary

            if not can_proceed:
                results["stages_failed"].append("coverage_gate")
                logger.error("Pipeline stopped: Coverage gate failed")
                return results
        elif skip_coverage_gate:
            logger.info("Coverage gate skipped (--skip-coverage-gate)")
            results["coverage_gate"] = {"skipped": True}

        # Stage 3: Score
        if "score" in stages:
            # Use enriched output from stage 2 as input
            score_input = enriched_dir
            # Validate input directory exists (skip if enrich just ran or dry_run)
            if not dry_run and "enrich" not in results["stages_completed"]:
                if not self._validate_input_dir(score_input, "SCORE"):
                    results["stages_failed"].append("score")
                    logger.error("Pipeline stopped: Scoring input not found")
                    return results
            success = self.run_score(score_input, scored_dir, dry_run)
            if success:
                results["stages_completed"].append("score")
            else:
                results["stages_failed"].append("score")

        # Summary
        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        results["duration_seconds"] = round(duration, 2)
        results["timestamp"] = end_time.isoformat().replace("+00:00", "Z")
        results["success"] = len(results["stages_failed"]) == 0

        logger.info("")
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Stages completed: {', '.join(results['stages_completed']) or 'none'}")
        if results["stages_failed"]:
            logger.warning(f"Stages failed: {', '.join(results['stages_failed'])}")
        logger.info(f"Total duration: {duration:.2f}s")
        logger.info(f"Success: {results['success']}")
        logger.info("=" * 60)

        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='DSLD Supplement Pipeline Runner - Clean → Enrich → Score',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run complete pipeline
    python run_pipeline.py

    # Run only enrichment and scoring
    python run_pipeline.py --stages enrich,score

    # Run only scoring
    python run_pipeline.py --stages score

    # Custom output prefix
    python run_pipeline.py --output-prefix output_Vitamins

    # Dry run (show commands without executing)
    python run_pipeline.py --dry-run

Pipeline Flow:
    raw_data/ → [CLEAN] → output_*/cleaned/ → [ENRICH] → output_*_enriched/enriched/ → [SCORE] → output_*_scored/
        """
    )

    parser.add_argument(
        '--stages',
        default='clean,enrich,score',
        help='Comma-separated list of stages to run (clean,enrich,score)'
    )
    parser.add_argument(
        '--raw-dir',
        help='Directory containing raw DSLD data'
    )
    parser.add_argument(
        '--output-prefix',
        default='output_Lozenges',
        help='Prefix for output directories (default: output_Lozenges)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without running'
    )
    parser.add_argument(
        '--config',
        help='Pipeline configuration file (JSON)'
    )
    parser.add_argument(
        '--skip-coverage-gate',
        action='store_true',
        help='Skip coverage gate checks (AC5) before scoring'
    )
    parser.add_argument(
        '--coverage-gate-warn-only',
        action='store_true',
        help='Run coverage gate but only warn, do not block scoring'
    )

    args = parser.parse_args()

    # Load config if provided
    config = None
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded config from {args.config}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")

    # Parse stages
    stages = [s.strip() for s in args.stages.split(',')]
    valid_stages = {'clean', 'enrich', 'score'}
    invalid = set(stages) - valid_stages
    if invalid:
        logger.error(f"Invalid stages: {invalid}. Valid: {valid_stages}")
        sys.exit(1)

    # Run pipeline
    runner = PipelineRunner(config)
    results = runner.run_pipeline(
        stages=stages,
        raw_dir=args.raw_dir,
        output_prefix=args.output_prefix,
        dry_run=args.dry_run,
        skip_coverage_gate=args.skip_coverage_gate,
        coverage_gate_warn_only=args.coverage_gate_warn_only
    )

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
