# Technology Stack

**Analysis Date:** 2026-03-16

## Languages

**Primary:**
- Python 3.13.3 - All core processing scripts, data pipelines, and utilities
- Bash - Shell scripts for batch processing and orchestration (`batch_run_all_datasets.sh`, `run_pipeline.py`)

**Secondary:**
- JSON - Data storage format for all reference databases and configuration

## Runtime

**Environment:**
- Python 3.13.3 (from Clang 15.0.0)
- Virtual environment via venv at `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/.venv`

**Package Manager:**
- pip 25.0.1
- Lockfile: Not present (dependencies managed via individual imports)

## Frameworks

**Core:**
- None (standard library focused) - Custom data processing architecture with manual module integration

**Testing:**
- pytest 9.0.2 - Test runner and framework for all regression and unit tests
  - Config: Standard pytest discovery (tests/ directory with `test_*.py` naming)

**Build/Dev:**
- tqdm 4.67.3 - Progress bar visualization for batch operations
- pygments 2.19.2 - Syntax highlighting for output
- iniconfig 2.3.0 - INI file parsing (pytest dependency)
- pluggy 1.6.0 - Plugin system (pytest dependency)
- packaging 26.0 - Version parsing utilities

## Key Dependencies

**Critical:**
- tqdm 4.67.3 - Progress bar display in batch processing (`batch_processor.py`, `enrich_supplements_v3.py`, `score_supplements.py`)
- pytest 9.0.2 - Test execution (47+ test files in `scripts/tests/`)
- psutil - Optional system monitoring for memory tracking during batch processing (graceful import with fallback)
- fuzzywuzzy - Fuzzy string matching for ingredient name normalization (optional with difflib fallback)
- rapidfuzz - High-performance fuzzy matching for better pattern matching accuracy (optional replacement for fuzzywuzzy)

**Data Processing:**
- json (stdlib) - All data serialization and loading (`batch_processor.py`, `constants.py`)
- pathlib (stdlib) - Cross-platform file path handling
- concurrent.futures (stdlib) - Multiprocessing and threading for batch operations
- logging (stdlib) - Structured logging throughout pipeline

## Configuration

**Environment:**
- No external environment files required (pipeline is data-driven from JSON reference files)
- Configuration passed via CLI arguments to pipeline stages
- State persisted to `scripts/logs/processing_state.json`

**Build:**
- `.venv` - Python virtual environment (committed to git, contains installed dependencies)
- `pyvenv.cfg` - Virtual environment configuration pointing to Python 3.13.3

## Platform Requirements

**Development:**
- macOS (Darwin 25.3.0) - Current development environment
- Python 3.13.3 - Must match venv Python version
- Bash shell for pipeline orchestration

**Production:**
- Any Unix-like system (macOS, Linux) with Python 3.13.3+
- Data sources: Local filesystem (JSON files in `scripts/data/`)
- External dependency: NIH DSLD API for image PDFs (referenced via template `https://api.ods.od.nih.gov/dsld/s3/pdf/{}.pdf`)

---

*Stack analysis: 2026-03-16*
