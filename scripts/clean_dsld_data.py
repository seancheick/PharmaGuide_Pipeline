#!/usr/bin/env python3
"""
DSLD Data Cleaning Pipeline - Main Script
=========================================

Comprehensive batch processing system for cleaning and normalizing DSLD supplement data.
Processes thousands of files efficiently with resume capability, parallel processing,
and detailed logging.

Features:
- Batch processing with configurable size
- Multiprocessing support
- Resume capability after interruption
- Comprehensive ingredient mapping and normalization
- Allergen detection with severity levels
- Harmful additive flagging
- Certification extraction
- Quality assessment and completeness scoring

Usage:
    python clean_dsld_data.py --config scripts/config/cleaning_config.json
    python clean_dsld_data.py --resume
    python clean_dsld_data.py --dry-run

Author: PharmaGuide Team
Version: 1.0.0
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
sys.path.append(str(Path(__file__).parent))

from batch_processor import BatchProcessor
from enhanced_normalizer import EnhancedDSLDNormalizer
from constants import LOG_FORMAT, LOG_DATE_FORMAT


def verify_working_directory(config_path: str) -> None:
    """
    Verify that relative paths in config will resolve correctly from current working directory.
    Prevents accidental split logs/state when running from wrong directory.

    Args:
        config_path: Path to the configuration file

    Raises:
        SystemExit: If relative paths won't work from current directory
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Config loading errors will be handled later by DSLDCleaningPipeline
        return

    paths = config.get("paths", {})
    reference_data = paths.get("reference_data", "data")

    # If reference_data is relative and doesn't exist, we're in the wrong directory
    ref_path = Path(reference_data)
    if not ref_path.is_absolute() and not ref_path.exists():
        cwd = Path.cwd()
        print(f"\n❌ WORKING DIRECTORY ERROR", file=sys.stderr)
        print(f"   Current directory: {cwd}", file=sys.stderr)
        print(f"   Expected relative path '{reference_data}/' does not exist here.", file=sys.stderr)
        print(f"\n   This usually means you're running from the wrong directory.", file=sys.stderr)
        print(f"   Solution: cd to scripts/ directory and run again:", file=sys.stderr)
        print(f"      cd scripts/", file=sys.stderr)
        print(f"      python clean_dsld_data.py", file=sys.stderr)
        print(f"\n   Or use absolute paths in your config file.\n", file=sys.stderr)
        sys.exit(1)

    # Also check log_directory to prevent split state
    log_dir = paths.get("log_directory", "logs")
    log_path = Path(log_dir)
    if not log_path.is_absolute():
        # Don't fail, just warn if logs/ doesn't exist yet (it will be created)
        # But if there's a logs/ elsewhere and we're creating a new one, that's confusing
        pass  # Log creation is handled by the pipeline


class DSLDCleaningPipeline:
    """Main pipeline for DSLD data cleaning"""

    def __init__(self, config_path: str, cli_overrides: dict = None):
        self.config_path = Path(config_path)
        self.cli_overrides = cli_overrides or {}
        self.config = self._load_config()
        self._apply_cli_overrides()
        self.logger = self._setup_logging()
        self._log_resolved_paths()

    def _load_config(self) -> dict:
        """Load configuration file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Validate required sections (options is optional now)
            required_sections = ["processing", "paths"]
            for section in required_sections:
                if section not in config:
                    raise ValueError(f"Missing required config section: {section}")

            return config

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {str(e)}")

    def _apply_cli_overrides(self):
        """Apply CLI overrides to config (CLI takes precedence)"""
        if not self.cli_overrides:
            return

        paths = self.config.get("paths", {})

        if "input_directory" in self.cli_overrides:
            paths["input_directory"] = self.cli_overrides["input_directory"]
        if "output_directory" in self.cli_overrides:
            paths["output_directory"] = self.cli_overrides["output_directory"]
        if "reference_data" in self.cli_overrides:
            paths["reference_data"] = self.cli_overrides["reference_data"]

        self.config["paths"] = paths

    def _log_resolved_paths(self):
        """Log resolved paths for debugging and auditability"""
        paths = self.config.get("paths", {})
        reference_data = paths.get("reference_data", "data")
        ref_path = Path(reference_data)

        # Resolve to absolute path
        if not ref_path.is_absolute():
            ref_path = Path.cwd() / ref_path

        # Log resolved paths
        logging.info(f"Resolved paths:")
        logging.info(f"  input_directory: {paths.get('input_directory', 'N/A')}")
        logging.info(f"  output_directory: {paths.get('output_directory', 'N/A')}")
        logging.info(f"  reference_data: {ref_path}")

        # Validate reference_data directory exists
        if not ref_path.exists():
            raise FileNotFoundError(
                f"Reference data directory not found: {ref_path}\n"
                f"Ensure 'data/' directory exists with required database files."
            )

        # Log versions of critical databases if available
        self._log_database_versions(ref_path)

    def _log_database_versions(self, ref_path: Path):
        """Log versions of critical database files for auditability"""
        critical_dbs = [
            "color_indicators.json",
            "ingredient_quality_map.json",
            "harmful_additives.json",
            "allergens.json",
        ]

        for db_file in critical_dbs:
            db_path = ref_path / db_file
            if db_path.exists():
                try:
                    with open(db_path, 'r') as f:
                        db_data = json.load(f)

                    db_info = db_data.get('_metadata', {})
                    version = db_info.get('version', db_info.get('schema_version', 'unknown'))
                    last_updated = db_info.get('last_updated', 'unknown')

                    if version != 'unknown':
                        logging.info(f"  {db_file}: v{version} (updated: {last_updated})")
                except Exception as e:
                    logging.warning(f"  {db_file}: Failed to read version - {e}")
            else:
                logging.warning(f"  {db_file}: NOT FOUND at {db_path}")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        log_config = self.config.get("logging", {})
        log_level = getattr(logging, log_config.get("level", "INFO"))
        
        # Create logger
        logger = logging.getLogger("dsld_cleaner")
        logger.setLevel(log_level)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Create formatter
        formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
        
        # Console handler
        if log_config.get("log_to_console", True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # File handler
        if log_config.get("log_to_file", True):
            log_dir = Path(self.config["paths"]["log_directory"])
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"dsld_cleaning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def validate_config(self) -> bool:
        """Validate configuration and dependencies"""
        self.logger.info("Validating configuration...")
        
        # Check input directory
        input_dir = Path(self.config["paths"]["input_directory"])
        if not input_dir.exists():
            self.logger.error(f"Input directory does not exist: {input_dir}")
            return False
        
        # Check reference data directory
        ref_dir = Path(self.config["paths"]["reference_data"])
        if not ref_dir.exists():
            self.logger.error(f"Reference data directory does not exist: {ref_dir}")
            return False
        
        # Check CRITICAL reference files (fail if missing)
        # These are required for safety/correctness - cannot clean without them
        critical_files = [
            "ingredient_quality_map.json",
            "harmful_additives.json",
            "allergens.json",
            "banned_recalled_ingredients.json",
            "ingredient_classification.json",
        ]

        for filename in critical_files:
            file_path = ref_dir / filename
            if not file_path.exists():
                self.logger.error("CRITICAL reference file missing: %s", file_path)
                return False

        # Check RECOMMENDED reference files (warn if missing)
        # Pipeline can run without these, but with degraded results
        recommended_files = [
            "standardized_botanicals.json",
            "absorption_enhancers.json",
            "other_ingredients.json",
            "botanical_ingredients.json",
            "proprietary_blends.json",
        ]

        missing_recommended = []
        for filename in recommended_files:
            file_path = ref_dir / filename
            if not file_path.exists():
                missing_recommended.append(filename)

        if missing_recommended:
            self.logger.warning(
                "RECOMMENDED reference files missing (results may have more unmapped): %s",
                ", ".join(missing_recommended)
            )
        
        # Validate processing options
        batch_size = self.config["processing"]["batch_size"]
        if batch_size <= 0:
            self.logger.error(f"Invalid batch size: {batch_size}")
            return False
        
        max_workers = self.config["processing"]["max_workers"]
        if max_workers <= 0:
            self.logger.error(f"Invalid max workers: {max_workers}")
            return False
        
        self.logger.info("Configuration validation passed")
        return True
    
    def dry_run(self) -> bool:
        """Perform dry run to check setup without processing"""
        self.logger.info("=== DRY RUN MODE ===")
        
        if not self.validate_config():
            return False
        
        # Check input files
        processor = BatchProcessor(self.config)
        input_dir = self.config["paths"]["input_directory"]
        
        try:
            files = processor.get_input_files(input_dir)
            self.logger.info(f"Found {len(files)} input files")
            
            if len(files) == 0:
                self.logger.warning("No input files found!")
                return False
            
            # Calculate batch info
            batch_size = self.config["processing"]["batch_size"]
            total_batches = (len(files) + batch_size - 1) // batch_size
            
            self.logger.info(f"Would process {len(files)} files in {total_batches} batches")
            self.logger.info(f"Batch size: {batch_size}")
            self.logger.info(f"Max workers: {self.config['processing']['max_workers']}")
            
            # Test loading reference data
            try:
                normalizer = EnhancedDSLDNormalizer()
                self.logger.info("Reference data loaded successfully")
            except Exception as e:
                self.logger.error(f"Failed to load reference data: {str(e)}")
                return False
            
            # Test processing one file
            test_file = files[0]
            self.logger.info(f"Testing processing with: {test_file.name}")
            
            try:
                with open(test_file, 'r') as f:
                    test_data = json.load(f)
                
                cleaned = normalizer.normalize_product(test_data)
                self.logger.info(f"Test processing successful - product ID: {cleaned.get('id', 'unknown')}")
                
            except Exception as e:
                self.logger.error(f"Test processing failed: {str(e)}")
                return False
            
            self.logger.info("=== DRY RUN COMPLETE - READY TO PROCESS ===")
            return True
            
        except Exception as e:
            self.logger.error(f"Dry run failed: {str(e)}")
            return False
    
    def run(self, resume: bool = False) -> bool:
        """Run the main processing pipeline"""
        self.logger.info("=" * 60)
        self.logger.info("DSLD Data Cleaning Pipeline Starting")
        self.logger.info("=" * 60)
        
        start_time = datetime.now()
        self.logger.info(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Validate configuration
            if not self.validate_config():
                self.logger.error("Configuration validation failed")
                return False
            
            # Initialize processor
            processor = BatchProcessor(self.config)
            
            # Get input files
            input_dir = self.config["paths"]["input_directory"]
            files = processor.get_input_files(input_dir)
            
            if len(files) == 0:
                self.logger.error("No input files found!")
                return False
            
            # Process all files
            summary = processor.process_all_files(files, resume=resume)
            
            # Log final results
            end_time = datetime.now()
            duration = end_time - start_time
            
            self.logger.info("=" * 60)
            self.logger.info("PROCESSING COMPLETE")
            self.logger.info("=" * 60)
            self.logger.info(f"Ended at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Total duration: {duration}")
            self.logger.info(f"Files processed: {summary['total_files']}")
            self.logger.info(f"Success rate: {summary['success_rate']:.1f}%")
            self.logger.info("")
            self.logger.info("Results:")
            self.logger.info(f"  - Cleaned: {summary['results']['cleaned']}")
            self.logger.info(f"  - Needs review: {summary['results']['needs_review']}")
            self.logger.info(f"  - Incomplete: {summary['results']['incomplete']}")
            self.logger.info(f"  - Errors: {summary['results']['errors']}")
            self.logger.info(f"  - Unmapped ingredients: {summary['unmapped_ingredients']}")
            
            # Output file locations
            output_dir = Path(self.config["paths"]["output_directory"])
            self.logger.info("")
            self.logger.info("Output files saved to:")
            self.logger.info(f"  - Cleaned products: {output_dir / 'cleaned'}")
            self.logger.info(f"  - Needs review: {output_dir / 'needs_review'}")
            self.logger.info(f"  - Incomplete: {output_dir / 'incomplete'}")
            self.logger.info(f"  - Unmapped ingredients: {output_dir / 'unmapped'}")
            self.logger.info(f"  - Processing report: {output_dir / 'reports'}")
            
            return True
            
        except KeyboardInterrupt:
            self.logger.info("Processing interrupted by user")
            self.logger.info("You can resume processing using --resume flag")
            return False
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="DSLD Data Cleaning Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --config scripts/config/cleaning_config.json
  %(prog)s --input-dir raw_data --output-dir cleaned_output
  %(prog)s --resume
  %(prog)s --dry-run

CLI vs Config:
  CLI arguments (--input-dir, --output-dir) override config file values.
  Config file provides defaults; CLI provides per-run customization.
        """
    )

    # Determine default config path based on current directory
    if Path.cwd().name == "scripts":
        default_config = "config/cleaning_config.json"
        help_text = "Path to configuration file (default: config/cleaning_config.json)"
    else:
        default_config = "scripts/config/cleaning_config.json"
        help_text = "Path to configuration file (default: scripts/config/cleaning_config.json)"

    parser.add_argument(
        "--config",
        default=default_config,
        help=help_text
    )

    # CLI path overrides (take precedence over config)
    parser.add_argument(
        "--input-dir",
        help="Input directory containing raw DSLD JSON files (overrides config)"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for cleaned files (overrides config)"
    )
    parser.add_argument(
        "--reference-data",
        help="Directory containing reference databases (overrides config paths.reference_data)"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume processing from last completed batch"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and test processing without running full pipeline"
    )

    # NOTE: --start-batch was removed because resume is now file-level (processed_file_paths)
    # The old batch-based start was inconsistent with per-file tracking

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()

    # GUARD: Verify working directory before doing anything else
    # This prevents creating split logs/state in wrong directory
    verify_working_directory(args.config)

    # Set up basic logging for startup
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT
    )

    # Build CLI overrides dict
    cli_overrides = {}
    if args.input_dir:
        cli_overrides["input_directory"] = args.input_dir
    if args.output_dir:
        cli_overrides["output_directory"] = args.output_dir
    if args.reference_data:
        cli_overrides["reference_data"] = args.reference_data

    try:
        # Initialize pipeline with CLI overrides
        pipeline = DSLDCleaningPipeline(args.config, cli_overrides=cli_overrides)

        # Run pipeline
        if args.dry_run:
            success = pipeline.dry_run()
        else:
            success = pipeline.run(resume=args.resume)

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except Exception as e:
        logging.error(f"Pipeline initialization failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
