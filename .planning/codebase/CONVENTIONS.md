# Coding Conventions

**Analysis Date:** 2026-03-16

## Naming Patterns

**Files:**
- Snake case with descriptive names: `batch_processor.py`, `enhanced_normalizer.py`, `dsld_validator.py`
- Test files use pattern: `test_<feature>_<type>.py` (e.g., `test_pipeline_regressions.py`, `test_clean_unmapped_alias_regressions.py`)
- Config/constant files: `constants.py`, `preflight.py`
- Scripts grouped by function: `batch_processor.py`, `unmapped_ingredient_tracker.py`, `claims_audit.py`

**Functions:**
- Snake case throughout: `_should_skip_ingredient()`, `_check_data_quality()`, `validate_product()`, `process_unmapped_ingredients()`
- Private methods prefixed with single underscore: `_enhanced_ingredient_mapping()`, `_is_label_header()`
- Public methods without prefix: `validate()`, `match()`, `save_tracking_files()`
- Multi-word action verbs: `preprocess_text()`, `normalize_for_fuzzy()`, `convert_nutrient()`

**Variables:**
- Snake case for all variables: `max_workers`, `batch_size`, `missing_fields`, `quality_issues`
- Constants in UPPER_CASE with underscores: `STATUS_SUCCESS`, `STATUS_NEEDS_REVIEW`, `EXCLUDED_NUTRITION_FACTS`, `FUZZY_MATCHING_THRESHOLDS`
- Boolean prefixes common: `is_nutrition_fact`, `has_added_sugar`, `contains_sugar`, `needs_review`, `enable_case_insensitive_skip`
- Collection variables with plural suffix: `unmapped_active`, `needs_verification_active`, `missing_fields`, `validation_details`

**Types:**
- Type hints used extensively with `typing` module: `Dict`, `List`, `Tuple`, `Optional`, `Set`, `Any`, `Union`
- Return types in function signatures: `-> Tuple[str, List[str], Dict[str, Any]]`
- Class definitions use type hints in `__init__`: `def __init__(self, output_path: Path)`
- Dataclass usage: `@dataclass` decorators for data containers like `PerformanceTracker`

## Code Style

**Formatting:**
- 4-space indentation (Python standard)
- No apparent enforcement tool configured at project root (no `.pylintrc`, `ruff.toml`, or `pyproject.toml` found)
- Max line length appears to be flexible (lines range from 80-120+ characters)
- Module docstrings at top of file using triple quotes

**Linting:**
- No `.eslintrc`, `.pylintrc`, or `ruff.toml` detected at root or scripts directory
- Code follows PEP 8 conventions informally
- Type hints present throughout but not enforced by static checker

## Import Organization

**Order:**
1. Standard library imports: `json`, `logging`, `time`, `os`, `sys`, `re`, `string`
2. Third-party library imports: `tqdm`, `psutil`, `pytest`, `requests`, `fuzzywuzzy`
3. Local imports: `from enhanced_normalizer import`, `from constants import`, `from pathlib import Path`

**Path Aliases:**
- No path aliases or `PYTHONPATH` remapping detected
- Relative imports used: `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`
- Absolute path imports from constants: `from pathlib import Path`
- Local modules imported directly: `from batch_processor import`, `from dsld_validator import`

## Error Handling

**Patterns:**
- Try-except blocks with specific exception types: `except json.JSONDecodeError as e`, `except requests.RequestException as e`, `except Exception as e`
- Fallback patterns for optional dependencies: `try: from fuzzywuzzy import fuzz; except ImportError: from difflib import SequenceMatcher`
- Logging errors with context: `logger.error(f"Validation error: {str(e)}")`
- Exception re-raising minimal - mostly caught and logged
- Status enums used to signal processing state rather than exceptions: `STATUS_SUCCESS`, `STATUS_NEEDS_REVIEW`, `STATUS_INCOMPLETE`, `STATUS_ERROR`

**Exception Handling Locations:**
- `batch_processor.py`: Catches JSON decode errors, general exceptions during file processing
- `dsld_validator.py`: Catches validation errors and returns status tuple
- `fda_weekly_sync.py`: Catches request exceptions and XML parse errors
- Test files catch specific assertion failures with pytest mechanisms

## Logging

**Framework:** Python's standard `logging` module

**Configuration:**
- Logger created per module: `logger = logging.getLogger(__name__)`
- No centralized logging config file detected; loggers created ad-hoc

**Patterns:**
- Debug level for detailed processing: `logger.debug("Wrote quarantine record: %s", quarantine_file)`
- Info level for major operations: `logger.info(f"Processing {len(batch_files)} files")`
- Warning level for non-fatal issues: `logger.warning(f"Failed to write quarantine file: {e}")`
- Error level for failures: `logger.error(f"Failed to load state: {str(e)}")`
- Formatted logging with % placeholders and f-strings intermixed: both styles used
- Context logged alongside messages: file paths, counts, state information

**Example from `batch_processor.py`:**
```python
logger = logging.getLogger(__name__)
logger.info(f"Processing {len(files)} files in {state.total_batches} batches")
logger.warning(f"Pausing for 5 seconds due to high memory usage ({memory_usage:.1f}MB)")
```

## Comments

**When to Comment:**
- Module docstrings describe purpose and main classes: `"""DSLD Batch Processor Module\nHandles batch processing, multiprocessing, and state management"""`
- Class docstrings explain responsibility: `"""Tracks unmapped ingredients during the cleaning process"""`
- Docstrings include Args and Returns sections: `Args:\n    product_data: Raw product data from DSLD\n    \nReturns:\n    Tuple of (status, missing_fields, validation_details)`
- In-line comments minimal - code is self-documenting through naming
- Complex logic commented inline (e.g., in validation decision trees)

**JSDoc/TSDoc:**
- Not applicable (Python codebase)
- Module and function docstrings follow Google/Sphinx style: triple-quoted strings with Args/Returns sections

## Function Design

**Size:** Functions typically 10-50 lines; some larger processing functions 100+ lines for batch operations
- Validation functions: ~20 lines (e.g., `_check_fields`)
- Processing functions: 50-100 lines (e.g., `process_unmapped_ingredients`)
- Complex enrichment functions: 100-200+ lines (e.g., `_enhanced_ingredient_mapping`)

**Parameters:**
- Functions use explicit parameters, not *args or **kwargs
- Type hints on all parameters: `def validate_product(self, product_data: Dict[str, Any])`
- Default parameters used sparingly: `def __init__(self, output_path: Path)` requires explicit path
- Optional parameters use `Optional[Type]`: `details_by_name: Optional[Dict[str, Dict[str, Any]]] = None`

**Return Values:**
- Tuples for multiple related returns: `Tuple[str, List[str], Dict[str, Any]]` (status, missing_fields, details)
- Dictionary for complex structured returns: `Dict[str, Any]` for validation results
- Boolean for success/failure: `is_valid: bool`
- Classes used for strongly-typed returns: `ConversionResult`, `NutrientAdequacyResult`
- Lists for collections: `List[Dict[str, Any]]` for verification records

**Example from `dsld_validator.py`:**
```python
def validate_product(self, product_data: Dict[str, Any]) -> Tuple[str, List[str], Dict[str, Any]]:
    """
    Validate a product and determine its processing status

    Args:
        product_data: Raw product data from DSLD

    Returns:
        Tuple of (status, missing_fields, validation_details)
    """
```

## Module Design

**Exports:**
- Classes exported implicitly through `from module_name import ClassName`
- Modules typically export one main class: `EnhancedDSLDNormalizer`, `DSLDValidator`, `UnmappedIngredientTracker`
- Utility functions exported at module level: `fuzzy_match_ingredient()`, `convert_nutrient()`
- No `__all__` declarations detected - all public names implicitly exported

**Barrel Files:**
- No barrel/index files detected
- Direct imports used: `from enhanced_normalizer import EnhancedDSLDNormalizer`
- Scripts import from scripts directory siblings: `sys.path.insert(0, os.path.dirname(...))`

## Database Schema Conventions

**JSON Data Files:**
- Located in `scripts/data/` directory
- File naming: snake_case with descriptive names: `ingredient_quality_map.json`, `banned_recalled_ingredients.json`, `harmful_additives.json`
- Schema validation tests check for consistency: `test_db_integrity.py` validates all JSON files

**Field Naming:**
- camelCase for JSON object keys: `"standardName"`, `"ingredientGroup"`, `"ingredientId"`, `"contains_sugar"`, `"is_trusted_manufacturer"`
- Consistency enforced by validation: duplicate case errors flagged as camelCase leaks
- Singular/plural patterns: `"ingredients"` (plural for arrays), `"sugar"` (singular for object properties)

**Example from Data Files:**
- `ingredient_quality_map.json`: Keys like `"standardName"`, `"taxonomyId"`, `"efficacy_category"`
- `banned_recalled_ingredients.json`: Schema validates `"match_type"`, `"similarity_score"`, `"found"`
- Nested structure: products have `"dietary_sensitivity_data"` with nested objects like `"sugar": { "amount_g", "contains_sugar", "level" }`

**Validation Patterns:**
- Type checking in validators: `if missing_critical:`, `if quality_issues:`
- Required field tracking: `critical_fields`, `important_fields`, `optional_fields` defined in `DSLDValidator`
- Completeness scoring: `(present_critical_important / critical_important_fields) * 100`
- Status-based validation: Returns enum status strings rather than raising exceptions

---

*Convention analysis: 2026-03-16*
