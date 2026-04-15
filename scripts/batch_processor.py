"""
DSLD Batch Processor Module
Handles batch processing, multiprocessing, and state management
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set
from datetime import datetime, timezone
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
from dataclasses import dataclass, asdict
from tqdm import tqdm
try:
    import psutil
except ImportError:
    psutil = None

from enhanced_normalizer import EnhancedDSLDNormalizer
from dsld_validator import DSLDValidator
from constants import (
    STATUS_SUCCESS,
    STATUS_NEEDS_REVIEW,
    STATUS_INCOMPLETE,
    STATUS_ERROR,
    VALID_INPUT_EXTENSIONS,
    VALIDATION_THRESHOLDS
)
import traceback
import os
import hashlib

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Track performance metrics during batch processing"""

    def __init__(self):
        self.start_time = time.time()
        self.file_times = []
        self.batch_times = []
        self.memory_samples = []

    def record_file(self, duration: float):
        """Record processing time for a single file"""
        self.file_times.append(duration)

    def record_batch(self, duration: float):
        """Record processing time for a batch"""
        self.batch_times.append(duration)

    def record_memory(self):
        """Record current memory usage"""
        if psutil is None:
            return 0
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            self.memory_samples.append(memory_mb)
            return memory_mb
        except Exception:
            # Return high value so memory throttling triggers conservatively
            # rather than assuming unlimited memory is available.
            # Do NOT append to memory_samples — inf would corrupt stats.
            return 8192.0

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        import statistics

        stats = {
            "total_runtime_seconds": time.time() - self.start_time,
            "total_files": len(self.file_times)
        }

        if self.file_times:
            stats["avg_time_per_file"] = statistics.mean(self.file_times)
            stats["median_time"] = statistics.median(self.file_times)
            stats["slowest_file"] = max(self.file_times)
            stats["fastest_file"] = min(self.file_times)
            stats["files_per_minute"] = 60 / statistics.mean(self.file_times)

        if self.batch_times:
            stats["avg_batch_time"] = statistics.mean(self.batch_times)

        if self.memory_samples:
            stats["avg_memory_mb"] = statistics.mean(self.memory_samples)
            stats["peak_memory_mb"] = max(self.memory_samples)

        return stats


@dataclass
class ProcessingResult:
    """Result of processing a single file"""
    success: bool
    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    file_path: Optional[str] = None
    processing_time: float = 0.0
    unmapped_ingredients: Optional[List[str]] = None
    unmapped_active: Optional[Set[str]] = None  # Track which unmapped ingredients are active
    unmapped_details: Optional[Dict[str, Dict[str, Any]]] = None
    validation_errors: Optional[List[str]] = None  # Cleaned data structural validation errors
    raw_id: Optional[Any] = None  # Original ID from raw data for verify_output comparison
    error_stage: Optional[str] = None  # P2: Stage where error occurred (load, normalize, validate_cleaned, etc.)


@dataclass
class StructuredError:
    """D2: Structured error for better debugging and triage"""
    file_path: str
    exception_type: str
    message: str
    stage: str  # load, normalize, validate, write
    traceback: Optional[str] = None


@dataclass
class BatchState:
    """State tracking for batch processing"""
    started: str
    last_updated: str
    last_completed_batch: int
    total_batches: int
    processed_files: int
    total_files: int
    errors: List[str]
    can_resume: bool
    config_checksum: str
    # A7: File manifest for robust resume
    file_manifest_checksum: str = ""  # Hash of sorted file list
    first_file: str = ""  # First file in manifest
    last_file: str = ""   # Last file in manifest
    processed_file_paths: List[str] = None  # List of processed file paths
    # D1: Run metadata for reproducibility
    pipeline_version: str = "1.0.0"
    python_version: str = ""
    host_info: str = ""
    input_directory: str = ""

    def __post_init__(self):
        """Initialize mutable defaults and system info"""
        if self.processed_file_paths is None:
            self.processed_file_paths = []
        # D1: Capture system info
        if not self.python_version:
            import sys
            self.python_version = sys.version.split()[0]
        if not self.host_info:
            import platform
            self.host_info = f"{platform.node()}/{platform.system()}-{platform.release()}"


class BatchProcessor:
    """Manages batch processing of DSLD files"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.batch_size = config["processing"]["batch_size"]
        self.max_workers = config["processing"]["max_workers"]
        self.output_dir = Path(config["paths"]["output_directory"])
        self.log_dir = Path(config["paths"]["log_directory"])

        # Create output directories
        self._create_directories()

        # Initialize state
        self.state_file = self.log_dir / "processing_state.json"

        # Global counters for unmapped and mapped ingredients
        self.global_unmapped = Counter()
        self.global_unmapped_active = set()  # Track which unmapped ingredients are active
        self.global_unmapped_details: Dict[str, Dict[str, Any]] = {}
        self.global_mapped = Counter()

        # Track seen dsld_ids to detect duplicates across input files
        self.seen_dsld_ids: Dict[str, str] = {}  # dsld_id -> first file_path

        # Initialize performance tracker
        self.performance_tracker = PerformanceTracker()

        # Startup guardrail: estimate duplicated reference-data payload per worker.
        self.reference_data_memory = self._estimate_reference_data_memory()
        self._log_worker_memory_guardrail()

        # Remove shared normalizer instance for thread safety
        # Each process will create its own normalizer instance
        
    def _create_directories(self):
        """Create necessary output directories"""
        dirs = [
            self.output_dir / "cleaned",
            self.output_dir / "needs_review",
            self.output_dir / "incomplete",
            self.output_dir / "unmapped",
            self.output_dir / "errors",  # D4: Quarantine directory for failed files
            self.output_dir / "quarantine",  # Validation quarantine directory
            self.log_dir,
            Path(self.config["paths"]["output_directory"]) / "reports"
        ]

        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)

    def _write_quarantine_file(self, file_path: str, error: StructuredError):
        """
        D4: Write failed file metadata to quarantine directory for reprocessing.
        """
        quarantine_dir = self.output_dir / "errors"
        quarantine_file = quarantine_dir / f"{Path(file_path).stem}_error.json"

        error_record = {
            "original_file": file_path,
            "error_type": error.exception_type,
            "error_message": error.message,
            "processing_stage": error.stage,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "traceback": error.traceback
        }

        try:
            with open(quarantine_file, 'w', encoding='utf-8') as f:
                json.dump(error_record, f, indent=2, ensure_ascii=False)
            logger.debug("Wrote quarantine record: %s", quarantine_file)
        except Exception as e:
            logger.warning("Failed to write quarantine file: %s", e)

    def _write_validation_quarantine(self, result: ProcessingResult):
        """
        Write validation error quarantine artifact for debugging/triage.
        Only called when validation_errors exist in the result.
        """
        quarantine_dir = self.output_dir / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        # Extract product_id from data or filename
        product_id = None
        if result.data:
            product_id = result.data.get("id")
        if not product_id and result.file_path:
            product_id = Path(result.file_path).stem

        quarantine_file = quarantine_dir / f"{product_id}_validation.json"

        # Build quarantine artifact with debugging context
        quarantine_record = {
            "file_path": result.file_path,
            "product_id": product_id,
            "validation_errors": result.validation_errors,
            "top_level_keys": list(result.data.keys()) if result.data else [],
            "pipeline_version": self.config.get("pipeline_version", "unknown"),
            "config_checksum": self.config.get("config_checksum"),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        try:
            with open(quarantine_file, 'w', encoding='utf-8') as f:
                json.dump(quarantine_record, f, indent=2, ensure_ascii=False)
            logger.info("Wrote validation quarantine: %s", quarantine_file)
        except Exception as e:
            logger.warning("Failed to write validation quarantine: %s", e)

    @staticmethod
    def _sort_counter_deterministic(counter: Counter, limit: int = None) -> List[Tuple[str, int]]:
        """
        D3: Sort Counter items deterministically for stable CI diffing.
        Orders by count descending, then by name ascending.
        """
        items = list(counter.items())
        # Sort by count desc, then name asc for deterministic ordering
        items.sort(key=lambda x: (-x[1], x[0]))
        if limit:
            return items[:limit]
        return items

    def check_memory(self) -> Tuple[bool, float]:
        """
        B4: Monitor memory usage and warn if high.
        Returns: (is_ok, usage_mb) - all memory values in MB for consistency
        """
        if psutil is None:
            return True, 0
        try:
            # B4: Check both process and system memory for more accurate monitoring
            process = psutil.Process()
            process_memory_mb = process.memory_info().rss / (1024 * 1024)  # MB

            # Also check system-wide memory (helpful when running multiple workers)
            system_memory = psutil.virtual_memory()
            system_used_percent = system_memory.percent

            # Record for performance tracking (already in MB)
            self.performance_tracker.record_memory()

            # Config is in GB, convert to MB for comparison
            memory_limit_gb = self.config.get("processing", {}).get("memory_limit_gb", 8)
            memory_limit_mb = memory_limit_gb * 1024

            # Warn if process memory is high OR system memory is critically low
            if process_memory_mb > memory_limit_mb:
                logger.warning(
                    "High process memory: %.1fMB (limit: %.1fMB), System: %.1f%% used",
                    process_memory_mb, memory_limit_mb, system_used_percent
                )
                return False, process_memory_mb
            elif system_used_percent > 90:
                logger.warning(
                    "System memory critically high: %.1f%% used (process: %.1fMB)",
                    system_used_percent, process_memory_mb
                )
                return False, process_memory_mb

            return True, process_memory_mb
        except Exception as e:
            logger.warning("Memory check failed (assuming pressure): %s", e)
            # Conservative: assume memory pressure so batch slows down rather than OOM
            return False, 0

    def validate_input_file(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate JSON file before processing
        Returns: (is_valid, error_message)
        """
        if not self.config.get("validation", {}).get("check_input_integrity", False):
            return True, None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check required fields
            required = ['id']  # Minimal requirement
            missing = [f for f in required if f not in data]

            if missing:
                return False, f"Missing required fields: {missing}"

            # C3: Check if it's a valid DSLD structure - handle case variations
            # Accept: ingredientRows, otherIngredients, otheringredients
            has_ingredient_rows = 'ingredientRows' in data
            has_other_ingredients = (
                'otherIngredients' in data or
                'otheringredients' in data  # C3: Handle lowercase variant
            )

            if not has_ingredient_rows and not has_other_ingredients:
                return False, "No ingredient data found"

            return True, None

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def verify_output(
        self, cleaned_data: Dict, raw_data: Dict = None
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        B3: Verify cleaned data meets requirements with strengthened checks.
        Returns: (all_checks_passed, individual_checks)
        """
        if not self.config.get("validation", {}).get("verify_output", False):
            return True, {}

        checks = {
            "has_id": "id" in cleaned_data,
            "has_metadata": "metadata" in cleaned_data,
            "has_labelText": "labelText" in cleaned_data,
        }

        # B3: Strengthen id preservation check - compare with raw if available
        if raw_data:
            raw_id = raw_data.get("id")
            cleaned_id = cleaned_data.get("id")
            # Handle both string and int comparisons
            checks["preserved_original_id"] = (
                cleaned_id is not None and
                str(cleaned_id) == str(raw_id)
            )
        else:
            checks["preserved_original_id"] = cleaned_data.get("id") is not None

        # B3: Check for disallowed enrichment fields structurally (not string search)
        disallowed_fields = ["clinicalDosing", "industryBenchmark", "efficacyScore"]
        checks["no_enrichment_fields"] = self._check_no_disallowed_keys(
            cleaned_data, disallowed_fields
        )

        # B3: Validate ingredient arrays are actually arrays
        checks["valid_ingredients_structure"] = (
            isinstance(cleaned_data.get("activeIngredients", []), list) and
            isinstance(cleaned_data.get("inactiveIngredients", []), list)
        )

        return all(checks.values()), checks

    def _check_no_disallowed_keys(
        self, data: Dict, disallowed: List[str], path: str = ""
    ) -> bool:
        """
        B3: Recursively check that no disallowed keys exist in the data structure.
        This is safer than string-searching the entire dict.
        """
        if not isinstance(data, dict):
            return True

        for key, value in data.items():
            if key in disallowed:
                logger.warning(f"Found disallowed key '{key}' at path: {path}.{key}")
                return False
            if isinstance(value, dict):
                if not self._check_no_disallowed_keys(value, disallowed, f"{path}.{key}"):
                    return False
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        if not self._check_no_disallowed_keys(
                            item, disallowed, f"{path}.{key}[{i}]"
                        ):
                            return False
        return True

    def get_input_files(self, input_directory: str) -> List[Path]:
        """Get list of input DSLD JSON files"""
        input_path = Path(input_directory)
        if not input_path.exists():
            raise FileNotFoundError(f"Input directory not found: {input_directory}")
        
        files = []
        for ext in VALID_INPUT_EXTENSIONS:
            files.extend(input_path.glob(f"*{ext}"))
        
        # Sort for consistent processing order
        files.sort()
        
        logger.info(f"Found {len(files)} input files")
        return files
    
    def load_state(self) -> Optional[BatchState]:
        """Load processing state if exists"""
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            return BatchState(**state_data)
        except Exception as e:
            logger.warning(
                "Corrupt resume state file %s: %s — reprocessing from scratch",
                self.state_file, e,
            )
            return None
    
    def save_state(self, state: BatchState):
        """Save processing state (atomic write: tmp + fsync + replace)"""
        try:
            tmp_path = self.state_file.with_suffix('.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(state), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.state_file)
        except Exception as e:
            logger.error(f"Failed to save state: {str(e)}")
    
    def create_initial_state(self, files: List[Path]) -> BatchState:
        """Create initial processing state with file manifest for robust resume"""
        total_files = len(files)
        total_batches = (total_files + self.batch_size - 1) // self.batch_size

        # A7: Store file manifest info for resume validation
        sorted_files = sorted(str(f) for f in files)
        first_file = sorted_files[0] if sorted_files else ""
        last_file = sorted_files[-1] if sorted_files else ""

        return BatchState(
            started=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            last_updated=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            last_completed_batch=-1,  # -1 means no batches completed yet
            total_batches=total_batches,
            processed_files=0,
            total_files=total_files,
            errors=[],
            can_resume=True,
            config_checksum=self._get_config_checksum(),
            file_manifest_checksum=self._get_file_manifest_checksum(files),
            first_file=first_file,
            last_file=last_file,
            processed_file_paths=[]
        )
    
    def _get_config_checksum(self) -> str:
        """Get checksum of config for validation"""
        config_str = json.dumps(self.config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _get_file_manifest_checksum(self, files: List[Path]) -> str:
        """
        A7: Get checksum of file manifest for resume validation.
        This ensures resume won't skip/reprocess wrong files if file list changes.

        Includes: path, size, and a fast content fingerprint (head/tail chunks)
        This is a best-effort integrity check, not cryptographic.
        """
        manifest_entries = []
        for f in sorted(files, key=str):
            try:
                stat_info = os.stat(f)
                entry = f"{f}|{stat_info.st_size}|{self._fast_file_fingerprint(Path(f))}"
                manifest_entries.append(entry)
            except OSError as e:
                # File doesn't exist or is inaccessible - include error marker
                logger.warning("Cannot stat file for manifest: %s - %s", f, e)
                manifest_entries.append(f"{f}|ERROR")

        manifest_str = "\n".join(manifest_entries)
        return hashlib.md5(manifest_str.encode()).hexdigest()

    def _fast_file_fingerprint(self, path: Path, sample_size: int = 4096) -> str:
        """Cheap content fingerprint for resume safety without hashing whole files."""
        digest = hashlib.md5()
        with open(path, "rb") as handle:
            head = handle.read(sample_size)
            digest.update(head)

            file_size = path.stat().st_size
            if file_size > sample_size:
                tail_offset = max(file_size - sample_size, 0)
                handle.seek(tail_offset)
                tail = handle.read(sample_size)
                digest.update(tail)

        return digest.hexdigest()

    def _estimate_reference_data_memory(self, data_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Estimate on-disk JSON payload duplicated across worker processes."""
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"

        json_files = []
        total_bytes = 0
        if data_dir.exists():
            for path in sorted(data_dir.glob("*.json")):
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                json_files.append(path)
                total_bytes += size

        return {
            "reference_data_dir": str(data_dir),
            "reference_json_count": len(json_files),
            "reference_payload_bytes": total_bytes,
            "reference_payload_mb": round(total_bytes / (1024 * 1024), 2),
            "estimated_worker_payload_bytes": total_bytes,
            "estimated_worker_payload_mb": round(total_bytes / (1024 * 1024), 2),
            "estimated_total_worker_payload_bytes": total_bytes * max(self.max_workers, 1),
            "estimated_total_worker_payload_mb": round((total_bytes * max(self.max_workers, 1)) / (1024 * 1024), 2),
        }

    def _log_worker_memory_guardrail(self) -> None:
        diagnostics = self.reference_data_memory
        if diagnostics["reference_json_count"] == 0:
            logger.info("Reference data footprint estimate unavailable: no JSON files found in %s", diagnostics["reference_data_dir"])
            return

        logger.info(
            "Reference data footprint: %d JSON files, %.2fMB on disk; estimated duplicated worker payload %.2fMB at max_workers=%d",
            diagnostics["reference_json_count"],
            diagnostics["reference_payload_mb"],
            diagnostics["estimated_total_worker_payload_mb"],
            self.max_workers,
        )
        if self.max_workers > 4 or diagnostics["estimated_total_worker_payload_mb"] >= 128:
            logger.warning(
                "Worker memory guardrail: max_workers=%d with %.2fMB duplicated reference payload estimate. "
                "Reduce workers on low-memory hosts before scaling batch size.",
                self.max_workers,
                diagnostics["estimated_total_worker_payload_mb"],
            )
    
    def process_all_files(self, files: List[Path], resume: bool = False) -> Dict[str, Any]:
        """Process all files in batches"""
        start_time = time.time()
        logger.info("Preparing processing state for %d files", len(files))

        # Load or create state
        state = None
        if resume:
            state = self.load_state()
            if state:
                # FAIL-FAST: Check all files exist before resuming
                missing_files = [f for f in files if not f.exists()]
                if missing_files:
                    error_msg = (
                        f"Resume aborted: {len(missing_files)} file(s) from manifest "
                        f"no longer exist. First missing: '{missing_files[0]}'"
                    )
                    logger.error(error_msg)
                    raise FileNotFoundError(error_msg)

                # A7: Validate config hasn't changed
                if state.config_checksum != self._get_config_checksum():
                    logger.warning("Config changed since last run, starting fresh")
                    state = None
                # A7: Validate file manifest hasn't changed (now includes size+mtime)
                elif state.file_manifest_checksum:
                    logger.info("Validating file manifest fingerprint for resume safety...")
                    manifest_check_start = time.time()
                    current_manifest = self._get_file_manifest_checksum(files)
                    logger.info(
                        "Resume file manifest fingerprint completed in %.2fs",
                        time.time() - manifest_check_start,
                    )
                    if state.file_manifest_checksum != current_manifest:
                        logger.warning(
                            "File manifest changed since last run (files added/removed/modified). "
                            "Starting fresh to avoid skipping or reprocessing wrong files."
                        )
                        state = None
                    else:
                        logger.info("File manifest validated - safe to resume")

        if not state:
            logger.info("Building file manifest fingerprint for fresh run...")
            manifest_build_start = time.time()
            state = self.create_initial_state(files)
            logger.info(
                "Initial processing state ready in %.2fs",
                time.time() - manifest_build_start,
            )

        # FIX 1+2: Skip already-processed files on resume
        processed_set = set(state.processed_file_paths or [])
        using_per_file_resume = False
        if resume and processed_set:
            original_count = len(files)
            files = [f for f in files if str(f) not in processed_set]
            skipped_count = original_count - len(files)
            if skipped_count > 0:
                logger.info(f"Skipping {skipped_count} already-processed files on resume")
            # Recompute batches for remaining files
            state.total_batches = (len(files) + self.batch_size - 1) // self.batch_size
            using_per_file_resume = True

        # FIX C6: On per-file resume, batch_num resets to 0, which would overwrite
        # previously-written output files (cleaned_batch_1.json, etc.).
        # Count existing batch output files and use that as the naming offset so
        # new batches are appended (batch_N+1, batch_N+2, ...) instead of overwriting.
        output_batch_offset = 0
        if using_per_file_resume:
            existing_outputs = list((self.output_dir / "cleaned").glob("cleaned_batch_*.json"))
            output_batch_offset = len(existing_outputs)
            if output_batch_offset > 0:
                logger.info(
                    "Resume: %d existing batch output files found, new batches will start at batch_%d",
                    output_batch_offset, output_batch_offset + 1
                )

        logger.info(f"Processing {len(files)} files in {state.total_batches} batches")
        logger.info(f"Batch size: {self.batch_size}, Max workers: {self.max_workers}")

        if resume and state.last_completed_batch >= 0:
            if using_per_file_resume:
                logger.info(
                    "Resuming with per-file state: %d remaining files across %d batches",
                    len(files),
                    state.total_batches,
                )
            else:
                logger.info(f"Resuming from batch {state.last_completed_batch + 1}")

        # Process batches
        batch_results = []
        start_batch = 0 if using_per_file_resume else state.last_completed_batch + 1

        for batch_num in range(start_batch, state.total_batches):
            batch_start = batch_num * self.batch_size
            batch_end = min(batch_start + self.batch_size, len(files))
            batch_files = files[batch_start:batch_end]

            # FIX C6: Use output_batch_offset to produce non-colliding file names on resume
            output_batch_num = output_batch_offset + (batch_num - start_batch)

            logger.info(f"Processing batch {batch_num + 1}/{state.total_batches} ({len(batch_files)} files)")

            # Process batch
            batch_result = self.process_batch(batch_num, batch_files, output_batch_num=output_batch_num)
            batch_results.append(batch_result)
            
            # Update state — only advance last_completed_batch if outputs were written successfully
            if batch_result.get("write_success", True):
                state.last_completed_batch = batch_num
            state.processed_files += len(batch_result.get("processed_files", []))
            state.last_updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            state.errors.extend(batch_result.get("errors", []))
            # FIX 1+2: Track processed file paths for per-file resume
            state.processed_file_paths.extend(batch_result.get("processed_files", []))
            self.save_state(state)
            
            # Log batch completion
            logger.info(f"Batch {batch_num + 1} complete: {batch_result['summary']}")
        
        # Generate final summary
        total_time = time.time() - start_time
        summary = self._generate_final_summary(batch_results, total_time)
        
        # Save unmapped ingredients
        self._save_unmapped_ingredients(processed_count_override=state.processed_files)
        
        # Generate processing report
        self._generate_processing_report(summary, batch_results)
        
        # Generate detailed review report
        self._generate_detailed_review_report()
        
        logger.info(f"Processing complete! Total time: {total_time:.2f}s")
        
        return summary
    
    def process_batch(self, batch_num: int, files: List[Path], output_batch_num: Optional[int] = None) -> Dict[str, Any]:
        """Process a single batch of files"""
        batch_start_time = time.time()

        # Check memory before processing (now in MB)
        memory_ok, memory_usage = self.check_memory()
        if not memory_ok and self.config.get("processing", {}).get("pause_on_high_memory", False):
            logger.warning(f"Pausing for 5 seconds due to high memory usage ({memory_usage:.1f}MB)")
            time.sleep(5)

        # Create batch logger
        batch_log_file = self.log_dir / f"batch_{batch_num + 1}_log.txt"
        batch_logger = self._create_batch_logger(batch_log_file)

        batch_logger.info(f"=== Batch {batch_num + 1} Processing Log ===")
        batch_logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        batch_logger.info(f"Memory usage: {memory_usage:.1f}MB")
        batch_logger.info(f"Files: {files[0].name} to {files[-1].name}")

        # Containers for results
        cleaned_products = []
        needs_review_products = []
        incomplete_products = []
        errors = []
        batch_unmapped = Counter()
        batch_mapped = Counter()
        processed_files = []  # FIX 1+2: Track processed file paths
        
        # Process files
        if self.max_workers == 1:
            # Single-threaded processing
            # PERFORMANCE FIX: Initialize worker once before processing files
            init_worker(str(self.output_dir))
            for file_path in files:
                # FIX 7: Validate input file before processing
                is_valid, validation_error = self.validate_input_file(file_path)
                if not is_valid:
                    error_msg = f"Input validation failed for {file_path}: {validation_error}"
                    errors.append(error_msg)
                    batch_logger.error(error_msg)
                    # FIX 4: Write structured quarantine for validation failures
                    self._write_quarantine_file(
                        str(file_path),
                        StructuredError(
                            file_path=str(file_path),
                            exception_type="InputValidationError",
                            message=validation_error,
                            stage="validate"
                        )
                    )
                    continue

                result = process_single_file(str(file_path), str(self.output_dir))
                try:
                    self._categorize_result(
                        result,
                        cleaned_products,
                        needs_review_products,
                        incomplete_products,
                        errors,
                        batch_unmapped,
                        batch_mapped
                    )
                    processed_files.append(str(file_path))  # Track AFTER successful categorization
                except Exception as e:
                    error_msg = f"Failed to categorize result for {file_path}: {str(e)}"
                    errors.append(error_msg)
                    batch_logger.error(error_msg)
                    self._write_quarantine_file(
                        str(file_path),
                        StructuredError(
                            file_path=str(file_path),
                            exception_type=type(e).__name__,
                            message=str(e),
                            stage="categorize",
                            traceback=traceback.format_exc()
                        )
                    )
        else:
            # Multi-threaded processing with worker initialization
            # PERFORMANCE FIX: Initialize normalizer once per worker, not per file

            # FIX 7: Pre-validate all files before submitting to executor
            valid_files = []
            for file_path in files:
                is_valid, validation_error = self.validate_input_file(file_path)
                if not is_valid:
                    error_msg = f"Input validation failed: {file_path}: {validation_error}"
                    errors.append(error_msg)
                    batch_logger.error(error_msg)
                    # FIX 4: Write structured quarantine for validation failures
                    self._write_quarantine_file(
                        str(file_path),
                        StructuredError(
                            file_path=str(file_path),
                            exception_type="InputValidationError",
                            message=validation_error,
                            stage="validate"
                        )
                    )
                else:
                    valid_files.append(file_path)

            with ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=init_worker,
                initargs=(str(self.output_dir),)
            ) as executor:
                # Submit only validated files
                future_to_file = {
                    executor.submit(process_single_file, str(f), str(self.output_dir)): f
                    for f in valid_files
                }

                # Check if progress bar should be shown
                show_progress = self.config.get("ui", {}).get("show_progress_bar", False)

                # Wrap iterator with tqdm if progress bar is enabled
                futures_iterator = as_completed(future_to_file)
                if show_progress:
                    futures_iterator = tqdm(
                        futures_iterator,
                        total=len(valid_files),
                        desc=f"Processing Batch {batch_num + 1}",
                        unit="file"
                    )

                # Collect results
                completed_results = {}
                for future in futures_iterator:
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        completed_results[str(file_path)] = result
                    except Exception as e:
                        error_msg = f"Failed to process {file_path}: {str(e)}"
                        errors.append(error_msg)
                        batch_logger.error(error_msg)
                        # FIX 4: Write quarantine for processing exceptions
                        self._write_quarantine_file(
                            str(file_path),
                            StructuredError(
                                file_path=str(file_path),
                                exception_type=type(e).__name__,
                                message=str(e),
                                stage="process",
                                traceback=traceback.format_exc()
                            )
                        )

                # Deterministic post-processing order: always follow input file order
                for file_path in valid_files:
                    result = completed_results.get(str(file_path))
                    if result is None:
                        continue
                    try:
                        self._categorize_result(
                            result,
                            cleaned_products,
                            needs_review_products,
                            incomplete_products,
                            errors,
                            batch_unmapped,
                            batch_mapped
                        )
                        processed_files.append(str(file_path))  # Track AFTER successful categorization
                    except Exception as e:
                        error_msg = f"Failed to categorize result for {file_path}: {str(e)}"
                        errors.append(error_msg)
                        batch_logger.error(error_msg)
                        self._write_quarantine_file(
                            str(file_path),
                            StructuredError(
                                file_path=str(file_path),
                                exception_type=type(e).__name__,
                                message=str(e),
                                stage="categorize",
                                traceback=traceback.format_exc()
                            )
                        )
        
        # Update global counters
        self.global_unmapped.update(batch_unmapped)
        self.global_mapped.update(batch_mapped)
        
        # Write batch outputs — use output_batch_num if provided (resume offset), else batch_num
        effective_output_num = output_batch_num if output_batch_num is not None else batch_num
        write_ok = self._write_batch_outputs(effective_output_num, cleaned_products, needs_review_products, incomplete_products)
        if not write_ok:
            logger.error("Batch %d: one or more output files failed to write — batch will NOT be marked complete", batch_num + 1)
        
        # Log batch summary
        batch_time = time.time() - batch_start_time

        # Record performance metrics
        self.performance_tracker.record_batch(batch_time)

        # Final memory check
        _, final_memory = self.check_memory()

        summary = {
            "batch_num": batch_num + 1,
            "processed": len(processed_files),
            "cleaned": len(cleaned_products),
            "needs_review": len(needs_review_products),
            "incomplete": len(incomplete_products),
            "errors": len(errors),
            "processing_time": batch_time,
            "avg_time_per_file": batch_time / len(processed_files) if processed_files else 0,
            "memory_mb": final_memory  # FIX 6: Already in MB from check_memory()
        }

        batch_logger.info("Ended: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        batch_logger.info("Summary: %s", summary)
        batch_logger.info("Unmapped ingredients: %d", len(batch_unmapped))
        batch_logger.info("Final memory usage: %.1fMB", final_memory)  # FIX 6: MB not GB

        if errors:
            batch_logger.info("Errors:")
            for error in errors:
                batch_logger.error("  - %s", error)

        # FIX 1+2: Return processed_files for per-file resume tracking
        return {
            "summary": summary,
            "errors": errors,
            "unmapped_count": len(batch_unmapped),
            "processed_files": processed_files,
            "write_success": write_ok,
        }
    
    def _categorize_result(self, result: ProcessingResult, cleaned: List,
                          needs_review: List, incomplete: List, errors: List,
                          batch_unmapped: Counter, batch_mapped: Counter = None):
        """Categorize processing result into appropriate list"""
        # FIX 5: Record per-file processing time for performance tracking
        if result.processing_time > 0:
            self.performance_tracker.record_file(result.processing_time)

        if not result.success:
            errors.append(f"{result.file_path}: {result.error}")
            # P2: Write quarantine with stage context for debugging
            self._write_quarantine_file(
                str(result.file_path),
                StructuredError(
                    file_path=str(result.file_path),
                    exception_type="ProcessingError",
                    message=result.error or "Unknown error",
                    stage=result.error_stage or "unknown",
                    traceback=None  # Traceback not available from ProcessingResult
                )
            )
            return

        # Update unmapped ingredients
        if result.unmapped_ingredients:
            batch_unmapped.update(result.unmapped_ingredients)

        # Track which unmapped ingredients are active
        if result.unmapped_active:
            self.global_unmapped_active.update(result.unmapped_active)
        if result.unmapped_details:
            self.global_unmapped_details.update(result.unmapped_details)

        # Extract and count mapped ingredients from the processed data
        if batch_mapped is not None and result.data:
            self._extract_mapped_ingredients(result.data, batch_mapped)

        # FIX 7: Verify output structure before categorizing
        if result.data:
            # Pass raw_id for ID preservation check (wrapped in dict for verify_output)
            raw_data_for_check = {"id": result.raw_id} if result.raw_id else None
            output_ok, output_checks = self.verify_output(result.data, raw_data_for_check)
            if not output_ok:
                failed_checks = [k for k, v in output_checks.items() if not v]
                logger.warning(
                    "Output verification failed for %s: %s",
                    result.file_path, failed_checks
                )
                # Add to validation_errors for tracking
                if result.validation_errors is None:
                    result.validation_errors = []
                result.validation_errors.append(
                    f"Output verification failed: {failed_checks}"
                )

        # VALIDATION QUARANTINE: Write quarantine artifact if validation errors exist
        if result.validation_errors:
            self._write_validation_quarantine(result)

        # Dedup check: skip products with dsld_ids we've already seen.
        # Empty-string or None dsld_id is treated as a hard validation error —
        # without a canonical id we cannot dedup safely, and two empty-id
        # records would otherwise both slip through.
        if result.data:
            raw_id = result.data.get('id')
            if raw_id is None or (isinstance(raw_id, str) and raw_id.strip() == ''):
                raw_id = result.data.get('dsld_id')
            dsld_id = (
                str(raw_id).strip()
                if raw_id is not None and (not isinstance(raw_id, str) or raw_id.strip() != '')
                else ''
            )

            if not dsld_id:
                logger.error(
                    "Missing/empty dsld_id in %s — rejecting (dedup requires a canonical id)",
                    result.file_path,
                )
                errors.append(
                    f"{result.file_path}: missing or empty dsld_id (dedup requires canonical id)"
                )
                return

            if dsld_id in self.seen_dsld_ids:
                first_file = self.seen_dsld_ids[dsld_id]
                logger.warning(
                    "Duplicate dsld_id %s from %s (first seen in %s) — skipping duplicate",
                    dsld_id, result.file_path, first_file,
                )
                return
            self.seen_dsld_ids[dsld_id] = str(result.file_path)

        # Categorize by status
        if result.status == STATUS_SUCCESS:
            cleaned.append(result.data)
        elif result.status == STATUS_NEEDS_REVIEW:
            needs_review.append(result.data)
        elif result.status == STATUS_INCOMPLETE:
            incomplete.append(result.data)
        else:
            errors.append(f"{result.file_path}: Unknown status {result.status}")
    
    def _extract_mapped_ingredients(self, product_data: Dict, batch_mapped: Counter):
        """Extract mapped ingredients from processed product data"""
        # Count active ingredients
        active_ingredients = product_data.get('activeIngredients', [])
        for ingredient in active_ingredients:
            ingredient_name = ingredient.get('name', '').strip()
            if ingredient_name and ingredient.get('mapped', False):
                batch_mapped[ingredient_name] += 1
        
        # Count inactive ingredients  
        inactive_ingredients = product_data.get('inactiveIngredients', [])
        for ingredient in inactive_ingredients:
            ingredient_name = ingredient.get('name', '').strip()
            if ingredient_name and ingredient.get('mapped', False):
                batch_mapped[ingredient_name] += 1
    
    def _write_batch_outputs(self, batch_num: int, cleaned: List,
                           needs_review: List, incomplete: List) -> bool:
        """Write batch outputs to JSON files. Returns True if all writes succeeded."""
        batch_suffix = f"_batch_{batch_num + 1}"
        use_jsonl = self.config.get("output_format", {}).get("use_jsonl", False)
        file_extension = ".jsonl" if use_jsonl else ".json"

        all_ok = True

        # Write cleaned products
        if cleaned:
            output_file = self.output_dir / "cleaned" / f"cleaned{batch_suffix}{file_extension}"
            if not self._write_json_output(output_file, cleaned, use_jsonl):
                all_ok = False

        # Write needs review
        if needs_review:
            output_file = self.output_dir / "needs_review" / f"needs_review{batch_suffix}{file_extension}"
            if not self._write_json_output(output_file, needs_review, use_jsonl):
                all_ok = False

        # Write incomplete
        if incomplete:
            output_file = self.output_dir / "incomplete" / f"incomplete{batch_suffix}{file_extension}"
            if not self._write_json_output(output_file, incomplete, use_jsonl):
                all_ok = False

        return all_ok
    
    def _write_json_output(self, file_path: Path, data: List[Dict], use_jsonl: bool = False):
        """
        Write data to JSON or JSONL file using atomic write pattern.
        FIX 8: Write to .tmp file first, then atomically rename to prevent
        partial writes on crash/interrupt.
        """
        tmp_path = file_path.with_suffix(file_path.suffix + '.tmp')
        try:
            pretty_print = self.config.get("output_format", {}).get("pretty_print", False)

            with open(tmp_path, 'w', encoding='utf-8') as f:
                if use_jsonl:
                    # JSONL format: one JSON object per line
                    for item in data:
                        f.write(json.dumps(item, ensure_ascii=False) + '\n')
                else:
                    # Standard JSON array format
                    if pretty_print:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    else:
                        json.dump(data, f, ensure_ascii=False)

            # FIX 8: Atomic rename - if this fails, original file is untouched
            os.replace(tmp_path, file_path)
            logger.debug("Wrote %d items to %s", len(data), file_path)
            return True
        except Exception as e:
            logger.error("Failed to write %s: %s", file_path, str(e))
            # Clean up temp file if it exists
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            return False
    
    def _save_unmapped_ingredients(self, processed_count_override: Optional[int] = None):
        """Save cumulative unmapped ingredients using enhanced tracking"""
        # Create a temporary normalizer to process the global unmapped ingredients
        temp_normalizer = EnhancedDSLDNormalizer()
        temp_normalizer.set_output_directory(self.output_dir)
        
        # Transfer global unmapped data to the normalizer
        temp_normalizer.unmapped_ingredients = self.global_unmapped.copy()

        # Preserve per-label details from worker normalization so reporting can
        # distinguish ordinary unmapped rows from needs-verification cases.
        temp_normalizer.unmapped_details = {}
        for name, count in self.global_unmapped.items():
            detail = dict(self.global_unmapped_details.get(name, {}))
            if not detail:
                detail = {
                    "processed_name": name.lower(),
                    "forms": [],
                    "variations_tried": [],
                }
            detail["is_active"] = name in self.global_unmapped_active
            temp_normalizer.unmapped_details[name] = detail
        
        # Process and save with enhanced tracking
        try:
            result = temp_normalizer.process_and_save_unmapped_tracking(
                processed_count_override=processed_count_override
            )
            logger.info(f"Saved enhanced unmapped tracking files: {result['total_count']} total ingredients")
            logger.info(f"  Active: {result['active_count']}, Inactive: {result['inactive_count']}")
        except Exception as e:
            logger.error(f"Failed to save enhanced unmapped ingredients: {str(e)}")
            
            # Fallback to original method
            # D3: Use deterministic ordering
            unmapped_data = {
                "unmapped": [
                    {
                        "name": name,
                        "occurrences": count,
                        "firstSeen": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    }
                    for name, count in self._sort_counter_deterministic(self.global_unmapped)
                ],
                "stats": {
                    "totalUnmapped": len(self.global_unmapped),
                    "totalOccurrences": sum(self.global_unmapped.values()),
                    "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                }
            }
            
            output_file = self.output_dir / "unmapped" / "unmapped_ingredients.json"
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(unmapped_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved fallback unmapped ingredients: {len(self.global_unmapped)}")
            except Exception as fallback_error:
                logger.error(f"Failed to save fallback unmapped ingredients: {str(fallback_error)}")
    
    def _generate_final_summary(self, batch_results: List[Dict], total_time: float) -> Dict[str, Any]:
        """Generate final processing summary with performance metrics"""
        total_processed = sum(r["summary"]["processed"] for r in batch_results)
        total_cleaned = sum(r["summary"]["cleaned"] for r in batch_results)
        total_needs_review = sum(r["summary"]["needs_review"] for r in batch_results)
        total_incomplete = sum(r["summary"]["incomplete"] for r in batch_results)
        total_errors = sum(r["summary"]["errors"] for r in batch_results)

        # Get performance stats
        perf_stats = self.performance_tracker.get_stats()

        summary = {
            "processing_complete": True,
            "total_files": total_processed,
            "results": {
                "cleaned": total_cleaned,
                "needs_review": total_needs_review,
                "incomplete": total_incomplete,
                "errors": total_errors
            },
            "processing_time": {
                "total_seconds": total_time,
                "total_minutes": total_time / 60,
                "avg_per_file": total_time / total_processed if total_processed else 0
            },
            "unmapped_ingredients": len(self.global_unmapped),
            "mapped_ingredients": len(self.global_mapped),
            "success_rate": (total_cleaned / total_processed * 100) if total_processed else 0
        }

        # Add performance metrics if tracking is enabled
        if self.config.get("monitoring", {}).get("track_performance", False):
            summary["performance"] = perf_stats

        return summary
    
    def _generate_processing_report(self, summary: Dict, batch_results: List[Dict]):
        """Generate detailed processing report"""
        report_file = Path(self.config["paths"]["output_directory"]) / "reports" / "processing_summary.txt"
        
        try:
            with open(report_file, 'w') as f:
                f.write("DSLD Data Cleaning Processing Report\n")
                f.write("=" * 50 + "\n\n")
                
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Files Processed: {summary['total_files']}\n")
                f.write(f"Processing Time: {summary['processing_time']['total_minutes']:.2f} minutes\n\n")
                
                f.write("Results Summary:\n")
                f.write(f"  - Successfully cleaned: {summary['results']['cleaned']}\n")
                f.write(f"  - Needs review: {summary['results']['needs_review']}\n") 
                f.write(f"  - Incomplete: {summary['results']['incomplete']}\n")
                f.write(f"  - Errors: {summary['results']['errors']}\n")
                f.write(f"  - Success rate: {summary['success_rate']:.1f}%\n\n")
                
                f.write(f"Mapped ingredients found: {summary['mapped_ingredients']}\n")
                f.write(f"Unmapped ingredients found: {summary['unmapped_ingredients']}\n\n")

                # Add performance metrics if available
                if "performance" in summary:
                    perf = summary["performance"]
                    f.write("Performance Metrics:\n")
                    f.write(f"  - Files per minute: {perf.get('files_per_minute', 0):.1f}\n")
                    f.write(f"  - Average time per file: {perf.get('avg_time_per_file', 0):.2f}s\n")
                    f.write(f"  - Median time: {perf.get('median_time', 0):.2f}s\n")
                    if 'peak_memory_mb' in perf:
                        f.write(f"  - Peak memory usage: {perf['peak_memory_mb']:.1f}MB\n")
                    f.write("\n")

                # D3: Add top mapped ingredients with deterministic ordering
                if self.global_mapped:
                    f.write("Top 15 Mapped Ingredients (data insights):\n")
                    for ingredient, count in self._sort_counter_deterministic(
                        self.global_mapped, 15
                    ):
                        f.write(f"  {count:>3}x {ingredient}\n")
                    f.write("\nThese are the most frequently appearing mapped ingredients\n\n")

                # D3: Add top unmapped ingredients with deterministic ordering
                if self.global_unmapped:
                    f.write("Top 10 Unmapped Ingredients (for enrichment planning):\n")
                    for ingredient, count in self._sort_counter_deterministic(
                        self.global_unmapped, 10
                    ):
                        f.write(f"  {count:>3}x {ingredient}\n")
                    f.write("\nThese ingredients should be prioritized for database enrichment\n\n")

                f.write("Batch Details:\n")
                for i, batch in enumerate(batch_results):
                    s = batch["summary"]
                    f.write(f"  Batch {s['batch_num']}: {s['cleaned']} cleaned, "
                           f"{s['needs_review']} review, {s['incomplete']} incomplete, "
                           f"{s['errors']} errors ({s['processing_time']:.1f}s)\n")
                
            logger.info(f"Processing report saved to {report_file}")
        except Exception as e:
            logger.error(f"Failed to generate report: {str(e)}")
    
    def _generate_detailed_review_report(self):
        """Generate detailed review report for products needing manual attention"""
        needs_review_dir = self.output_dir / "needs_review"
        report_file = Path(self.config["paths"]["output_directory"]) / "reports" / "detailed_review_report.md"
        
        try:
            # Find all needs_review files (both .json and .jsonl)
            review_files = list(needs_review_dir.glob("*.json*"))
            if not review_files:
                logger.info("No products need review - skipping detailed review report")
                return
            
            # Load all products needing review
            review_products = []
            for file_path in review_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content.startswith('['):
                            # JSON array format
                            products = json.loads(content)
                            review_products.extend(products)
                        else:
                            # JSONL format
                            for line in content.split('\n'):
                                if line.strip():
                                    product = json.loads(line.strip())
                                    review_products.append(product)
                except Exception as e:
                    logger.warning(f"Could not read review file {file_path}: {str(e)}")
            
            if not review_products:
                logger.info("No products found in review files")
                return
            
            # Generate the report
            self._write_detailed_review_report(report_file, review_products)
            logger.info(f"Detailed review report saved to {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate detailed review report: {str(e)}")
    
    def _write_detailed_review_report(self, report_file: Path, review_products: List[Dict]):
        """Write the detailed review report in markdown format"""
        with open(report_file, 'w', encoding='utf-8') as f:
            # Header
            f.write("# DSLD Products Requiring Manual Review\n")
            f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n")
            f.write(f"**Total Products Needing Review:** {len(review_products)}\n\n")
            
            # Summary
            f.write("## Summary\n")
            f.write("Products are flagged for review when they have:\n")
            f.write("- **Low ingredient mapping rates** (below 75% mapped ingredients)\n")
            f.write("- **Missing important fields** (like UPC codes, contact info)\n")
            f.write("- **High numbers of unmapped ingredients** requiring manual curation\n\n")
            f.write("---\n\n")
            
            # Process each product
            for i, product in enumerate(review_products, 1):
                self._write_product_review_section(f, product, i)
            
            # Action items summary
            self._write_action_items_summary(f, review_products)
            
            # Files location
            f.write("---\n\n")
            f.write("## Files Location:\n")
            f.write("- **Detailed products:** `output/needs_review/needs_review_batch_*.jsonl`\n")
            f.write("- **Full unmapped ingredients list:** `output/unmapped/unmapped_ingredients.json`\n")
            f.write("- **This report:** `output/reports/detailed_review_report.md`\n")
    
    def _write_product_review_section(self, f, product: Dict, product_num: int):
        """Write individual product review section"""
        # Basic info
        f.write(f"## Product {product_num}: {product.get('fullName', 'Unknown Product')}\n")
        f.write(f"**Product ID:** {product.get('id', 'Unknown')}\n")
        f.write(f"**Brand:** {product.get('brandName', 'Unknown')}\n")
        
        # Status
        status = product.get('status', 'unknown')
        if status == 'discontinued':
            f.write(f"**Status:** ⚠️ **DISCONTINUED**")
            if product.get('discontinuedDate'):
                f.write(f" (Off market as of {product.get('discontinuedDate')[:10]})")
            f.write("\n\n")
        else:
            f.write(f"**Status:** ✅ **ACTIVE**\n\n")
        
        # Completeness and mapping info
        completeness = product.get('metadata', {}).get('completeness', {})
        mapping_stats = product.get('metadata', {}).get('mappingStats', {})
        
        f.write("### Why It Needs Review:\n")
        f.write(f"- **Completeness score:** {completeness.get('score', 0):.1f}%")
        if completeness.get('score', 0) >= VALIDATION_THRESHOLDS["excellent_completeness"]:
            f.write(" ✅\n")
        else:
            f.write(" ⚠️\n")
        
        f.write(f"- **Critical fields complete:** ")
        if completeness.get('criticalFieldsComplete', False):
            f.write("✅\n")
        else:
            f.write("❌\n")
        
        mapping_rate = mapping_stats.get('mappingRate', 0)
        f.write(f"- **Ingredient mapping:** {mapping_rate:.1f}% ")
        f.write(f"({mapping_stats.get('mappedIngredients', 0)} out of {mapping_stats.get('totalIngredients', 0)} ingredients mapped)")
        if mapping_rate >= 75:
            f.write(" ✅\n\n")
        else:
            f.write(" ⚠️\n\n")
        
        # Issues to address
        f.write("### Issues to Address:\n\n")
        
        # Missing fields
        missing_fields = completeness.get('missingFields', [])
        if missing_fields:
            # Import constants to check field categorization
            from constants import REQUIRED_FIELDS

            # Categorize missing fields
            missing_critical = [f for f in missing_fields if f in REQUIRED_FIELDS["critical"]]
            missing_important = [f for f in missing_fields if f in REQUIRED_FIELDS["important"]]
            missing_optional = [f for f in missing_fields if f in REQUIRED_FIELDS["optional"]]

            if missing_critical or missing_important:
                f.write("#### 1. Missing Critical Information:\n")

                # Handle critical fields
                for field in missing_critical:
                    f.write(f"- **{field}:** Missing critical field\n")

                # Handle important fields
                for field in missing_important:
                    if field == 'upcSku':
                        f.write("- **UPC/SKU Code:** Product has no barcode information\n")
                        f.write("  - **Impact:** Cannot be properly tracked in retail systems\n")
                        f.write("  - **Action:** Contact manufacturer to obtain UPC code\n")
                    else:
                        f.write(f"- **{field}:** Missing important field\n")

                f.write("\n")

            # Handle optional fields separately (informational only)
            if missing_optional:
                f.write("#### Additional Information (Optional Fields):\n")
                for field in missing_optional:
                    f.write(f"- **{field}:** Optional field not present\n")
                f.write("\n")
        
        # Unmapped ingredients
        unmapped_count = mapping_stats.get('unmappedIngredients', 0)
        if unmapped_count > 0:
            if missing_fields:
                f.write("#### 2. ")
            else:
                f.write("#### 1. ")
            
            if unmapped_count <= 5:
                f.write(f"Unmapped Ingredients Need Manual Review ({unmapped_count} total):\n")
            else:
                f.write(f"Many Unmapped Ingredients ({unmapped_count} total):\n")
            
            # Get unmapped ingredient names from the product data
            unmapped_ingredients = self._extract_unmapped_ingredients_from_product(product)
            
            if unmapped_count <= 10:
                for ingredient in unmapped_ingredients[:10]:
                    f.write(f"   - **{ingredient}** - Should be added to ingredient database\n")
            else:
                # Group by category for complex products
                f.write("\n**Key Missing Ingredients:**\n")
                for ingredient in unmapped_ingredients[:15]:
                    f.write(f"   - {ingredient}\n")
                if len(unmapped_ingredients) > 15:
                    f.write(f"   - ... and {len(unmapped_ingredients) - 15} more\n")
            f.write("\n")
        
        # Recommendation
        f.write("### Recommendation:\n")
        if status == 'discontinued':
            f.write("- **Priority:** Medium (product is discontinued)\n")
        elif mapping_rate < 60:
            f.write("- **Priority:** HIGH (active product with many missing ingredients)\n")
        else:
            f.write("- **Priority:** Medium (active product with some missing ingredients)\n")
        
        if unmapped_count > 0:
            f.write(f"- **Action:** Add the {unmapped_count} missing ingredients to your reference database\n")
        if missing_fields:
            f.write(f"- **Action:** Obtain missing information: {', '.join(missing_fields)}\n")
        f.write("- **Impact:** Will improve mapping for future similar products\n\n")
        f.write("---\n\n")
    
    def _extract_unmapped_ingredients_from_product(self, product: Dict) -> List[str]:
        """Extract names of unmapped ingredients from a product"""
        unmapped = []
        
        # Check active ingredients
        for ingredient in product.get('activeIngredients', []):
            if not ingredient.get('mapped', True):
                unmapped.append(ingredient.get('name', 'Unknown'))
        
        # Check inactive ingredients  
        for ingredient in product.get('inactiveIngredients', []):
            if not ingredient.get('mapped', True):
                unmapped.append(ingredient.get('name', 'Unknown'))
        
        return unmapped
    
    def _write_action_items_summary(self, f, review_products: List[Dict]):
        """Write action items summary section"""
        f.write("## Action Items Summary\n\n")
        
        high_priority = []
        medium_priority = []
        low_priority = []
        
        total_unmapped = 0
        missing_upc_count = 0
        
        for product in review_products:
            completeness = product.get('metadata', {}).get('completeness', {})
            mapping_stats = product.get('metadata', {}).get('mappingStats', {})
            
            unmapped_count = mapping_stats.get('unmappedIngredients', 0)
            total_unmapped += unmapped_count
            
            missing_fields = completeness.get('missingFields', [])
            if 'upcSku' in missing_fields:
                missing_upc_count += 1
            
            mapping_rate = mapping_stats.get('mappingRate', 0)
            is_active = product.get('status', 'active') == 'active'
            
            product_name = product.get('fullName', 'Unknown')
            product_id = product.get('id', 'Unknown')
            
            if is_active and mapping_rate < 60:
                high_priority.append(f"**{product_name}** (ID: {product_id}) - {unmapped_count} ingredients to add")
            elif is_active and unmapped_count > 0:
                medium_priority.append(f"**{product_name}** (ID: {product_id}) - {unmapped_count} ingredients to add")
            elif unmapped_count > 0:
                low_priority.append(f"**{product_name}** (ID: {product_id}) - {unmapped_count} ingredients to add")
        
        if high_priority:
            f.write("### High Priority:\n")
            for item in high_priority:
                f.write(f"1. {item}\n")
            f.write("\n")
        
        if medium_priority:
            f.write("### Medium Priority:\n")
            for item in medium_priority:
                f.write(f"1. {item}\n")
            f.write("\n")
        
        if low_priority:
            f.write("### Low Priority:\n")
            for item in low_priority:
                f.write(f"1. {item}\n")
            f.write("\n")
        
        if missing_upc_count > 0:
            f.write("### Additional Actions:\n")
            f.write(f"- **Obtain UPC codes** for {missing_upc_count} products\n\n")
        
        # Impact summary
        f.write("### Expected Impact:\n")
        total_ingredients = sum(p.get('metadata', {}).get('mappingStats', {}).get('totalIngredients', 0) for p in review_products)
        total_mapped = sum(p.get('metadata', {}).get('mappingStats', {}).get('mappedIngredients', 0) for p in review_products)
        
        if total_ingredients > 0:
            current_rate = (total_mapped / total_ingredients) * 100
            potential_rate = ((total_mapped + total_unmapped) / total_ingredients) * 100
            f.write(f"- **Current mapping rate:** {current_rate:.1f}% ({total_mapped} mapped out of {total_ingredients} total ingredients)\n")
            f.write(f"- **After improvements:** ~{potential_rate:.1f}% ({total_unmapped} more ingredients would be mapped)\n")
            f.write("- **Benefit:** Much better data quality for future similar products\n\n")
    
    def _create_batch_logger(self, log_file: Path) -> logging.Logger:
        """
        B5: Create batch-specific logger with proper handler management.
        Prevents handler leaks and duplicate log entries.
        """
        logger_name = f"batch_{log_file.stem}"
        batch_logger = logging.getLogger(logger_name)

        # B5: Prevent log propagation to root logger (avoid duplicates)
        batch_logger.propagate = False

        # Remove existing handlers and close them properly
        for handler in batch_logger.handlers[:]:
            try:
                handler.close()
            except Exception:
                pass
            batch_logger.removeHandler(handler)

        # Add file handler
        handler = logging.FileHandler(log_file, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        batch_logger.addHandler(handler)
        batch_logger.setLevel(logging.INFO)

        return batch_logger


# Global variables for worker processes (initialized once per worker)
_worker_normalizer = None
_worker_validator = None
_worker_output_dir = None


def init_worker(output_dir: str = None, from_defensive_init: bool = False):
    """
    Initialize worker process with shared normalizer and validator instances.
    This is called ONCE per worker process, not per file.
    PERFORMANCE FIX: Avoids reloading databases for every single file.

    Args:
        output_dir: Output directory for unmapped tracking
        from_defensive_init: True if called from defensive fallback (for logging)

    Raises:
        RuntimeError: If critical reference files fail to load
    """
    global _worker_normalizer, _worker_validator, _worker_output_dir
    # FIX 11: os is already imported at module level, no need to reimport

    # Log warning if this is a defensive initialization
    if from_defensive_init:
        logger.warning(
            "Defensive worker init triggered (PID: %s, output_dir: %s) - "
            "this may indicate init_worker() was not called properly",
            os.getpid(), output_dir
        )

    # Initialize normalizer ONCE per worker (loads all databases once)
    _worker_normalizer = EnhancedDSLDNormalizer()
    if output_dir:
        _worker_normalizer.set_output_directory(Path(output_dir))
        _worker_output_dir = output_dir

    # Initialize validator ONCE per worker
    _worker_validator = DSLDValidator()

    # POST-INIT VERIFICATION: Fail fast if critical datasets are missing
    # Critical datasets (required for safety/correctness):
    # - These are required by core safety logic (banned/harmful detection)
    # - Without these, outputs would be unsafe/inconsistent
    critical_datasets = {
        "ingredient_quality_map": _worker_normalizer.ingredient_map,
        "harmful_additives": _worker_normalizer.harmful_additives,
        "allergens_db": _worker_normalizer.allergens_db,
        "banned_recalled": _worker_normalizer.banned_recalled,
        "ingredient_classification": _worker_normalizer.ingredient_classification,
    }

    missing_critical = []
    for name, data in critical_datasets.items():
        if not data or (isinstance(data, dict) and len(data) == 0):
            missing_critical.append(name)

    if missing_critical:
        error_msg = (
            f"CRITICAL: Worker init failed - required datasets missing or empty: "
            f"{', '.join(missing_critical)}. Cannot continue with partial mappings. "
            f"Ensure these files exist in data/ directory."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Strongly recommended datasets (warn if missing, but don't fail)
    # - These improve parsing/coverage and reduce false "unmapped"
    # - Pipeline can still run, but with degraded results
    recommended_datasets = {
        "standardized_botanicals": _worker_normalizer.standardized_botanicals,
        "absorption_enhancers": _worker_normalizer.absorption_enhancers,
        "other_ingredients": _worker_normalizer.other_ingredients,
        "botanical_ingredients": _worker_normalizer.botanical_ingredients,
        "proprietary_blends": _worker_normalizer.proprietary_blends,
    }

    skipped_recommended = []
    for name, data in recommended_datasets.items():
        if not data or (isinstance(data, dict) and len(data) == 0):
            skipped_recommended.append(name)

    if skipped_recommended:
        logger.warning(
            "RECOMMENDED datasets not loaded (PID: %s): %s. "
            "Results may have more unmapped ingredients, weaker blend/botanical handling.",
            os.getpid(), ', '.join(skipped_recommended)
        )

    # Optional datasets (info-level log if skipped)
    optional_datasets = {
        "enhanced_delivery": _worker_normalizer.enhanced_delivery,
    }

    skipped_optional = []
    for name, data in optional_datasets.items():
        if not data or (isinstance(data, dict) and len(data) == 0):
            skipped_optional.append(name)

    if skipped_optional:
        logger.info(
            "Optional datasets not loaded (PID: %s): %s",
            os.getpid(), ', '.join(skipped_optional)
        )

    logger.debug(
        "Worker initialized (PID: %s): critical datasets verified",
        os.getpid()
    )


def process_single_file(file_path: str, output_dir: str = None) -> ProcessingResult:
    """
    Process a single DSLD file using pre-initialized worker instances.
    This function is designed to be used with multiprocessing.
    PERFORMANCE: Now uses global worker instances instead of creating new ones each time.
    """
    global _worker_normalizer, _worker_validator

    start_time = time.time()
    stage = "init"  # P2: Track stage for structured error context

    try:
        # A8: Defensive initialization - if globals are None, initialize them
        # This protects against direct calls without init_worker() being called first
        if _worker_normalizer is None or _worker_validator is None:
            init_worker(output_dir, from_defensive_init=True)

        # Load JSON data
        stage = "load"
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        # Use pre-initialized worker instances (MUCH faster than creating new ones)
        normalizer = _worker_normalizer
        validator = _worker_validator

        # DELTA TRACKING: Snapshot unmapped ingredients BEFORE processing this file
        # This prevents shared state accumulation from affecting per-file stats
        unmapped_before = normalizer.get_unmapped_snapshot()

        # Normalize the data
        stage = "normalize"
        cleaned_data = normalizer.normalize_product(raw_data)

        # B2: Validate CLEANED data structure (not just raw data)
        # SINGLE SOURCE OF TRUTH: If validation errors exist, attach to metadata and force status
        stage = "validate_cleaned"
        cleaned_errors = validator.validate_cleaned_product(cleaned_data)
        validation_forced_review = False
        if cleaned_errors:
            # Attach errors to metadata for debugging/triage
            cleaned_data["metadata"]["validationErrors"] = cleaned_errors
            cleaned_data["metadata"]["validationErrorCount"] = len(cleaned_errors)
            # Log at WARN level (not DEBUG) for visibility
            product_id = cleaned_data.get("id", Path(file_path).stem)
            logger.warning(
                "Cleaned data validation errors for product %s: %s",
                product_id,
                cleaned_errors
            )
            validation_forced_review = True

        # Validate raw data for completeness/status determination
        stage = "validate_raw"
        status, missing_fields, validation_details = validator.validate_product(raw_data)

        # DELTA TRACKING: Get only NEW unmapped ingredients for THIS file
        unmapped_delta = normalizer.get_unmapped_delta(unmapped_before)
        unmapped_list = [item["name"] for item in unmapped_delta["unmapped"]]
        # Extract which unmapped ingredients are active (from ingredientRows, not otherIngredients)
        unmapped_active_set = {item["name"] for item in unmapped_delta["unmapped"] if item.get("isActive", False)}
        unmapped_details = {
            item["name"]: normalizer.unmapped_details.get(item["name"], {})
            for item in unmapped_delta["unmapped"]
        }

        # B1: Calculate mapping statistics from CLEANED ingredient objects directly
        # This ensures consistency - count mapped:true from actual cleaned data
        active_ings = cleaned_data.get("activeIngredients", [])
        inactive_ings = cleaned_data.get("inactiveIngredients", [])
        total_ingredients = len(active_ings) + len(inactive_ings)

        # Count ingredients that have mapped:true in the cleaned data
        mapped_count = sum(
            1 for ing in active_ings + inactive_ings if ing.get("mapped", False)
        )
        unmapped_count = total_ingredients - mapped_count
        mapping_rate = (mapped_count / total_ingredients * 100) if total_ingredients > 0 else 100

        # Update metadata with validation results AND mapping stats
        cleaned_data["metadata"]["completeness"] = {
            "score": validation_details.get("completeness_score", 0),
            "missingFields": missing_fields,
            "criticalFieldsComplete": validation_details.get("critical_fields_complete", False)
        }

        cleaned_data["metadata"]["mappingStats"] = {
            "totalIngredients": total_ingredients,
            "mappedIngredients": mapped_count,  # Now guaranteed non-negative
            "unmappedIngredients": unmapped_count,
            "mappingRate": mapping_rate
        }

        # IMPROVED: Adjust status based on actual mapping performance
        if status == STATUS_NEEDS_REVIEW:
            # If product has excellent mapping (90%+) and only missing UPC, promote to success
            if (mapping_rate >= VALIDATION_THRESHOLDS["excellent_mapping"] and
                len(missing_fields) == 1 and
                missing_fields[0] == "upcSku" and
                validation_details.get("critical_fields_complete", False)):
                status = STATUS_SUCCESS

        # VALIDATION ROUTING: Force NEEDS_REVIEW if cleaned data has structural errors
        # This OVERRIDES any status promotion above - validation errors are serious
        if validation_forced_review:
            status = STATUS_NEEDS_REVIEW

        stage = "finalize"
        processing_time = time.time() - start_time

        return ProcessingResult(
            success=True,
            status=status,
            data=cleaned_data,
            file_path=file_path,
            processing_time=processing_time,
            unmapped_ingredients=unmapped_list,
            unmapped_active=unmapped_active_set,  # Track which unmapped are active ingredients
            unmapped_details=unmapped_details,
            validation_errors=cleaned_errors if cleaned_errors else None,
            raw_id=raw_data.get("id")  # For verify_output ID preservation check
        )

    except Exception as e:
        processing_time = time.time() - start_time
        return ProcessingResult(
            success=False,
            status=STATUS_ERROR,
            error=str(e),
            file_path=file_path,
            processing_time=processing_time,
            error_stage=stage  # P2: Include stage context for debugging
        )
