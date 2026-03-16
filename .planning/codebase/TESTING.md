# TESTING.md — Test Structure & Practices

## Framework

- **pytest** — primary test runner
- **No external mocking** — all tests use real reference DB data and real DSLD-sourced test fixtures
- **Real file I/O** — tests load actual JSON DBs from `scripts/data/`
- **No test database** — tests read production DBs directly (schema contract enforcement)

## Running Tests

```bash
cd scripts
pytest tests/                          # full suite
pytest tests/test_pipeline_regressions.py  # single file
pytest tests/ -k "banned"              # keyword filter
pytest tests/ -v --tb=short           # verbose with short tracebacks
```

## Test Organization

### File Structure
```
scripts/tests/
├── test_pipeline_regressions.py         # Core regression suite (highest priority)
├── test_clean_unmapped_alias_regressions.py  # Alias fix regressions
├── test_enrichment_regressions.py       # Enrichment stage regressions
├── test_db_integrity.py                 # DB schema + cross-DB consistency
├── test_banned_collision_corpus.py      # IQM ↔ BR collision prevention
├── test_blend_merge_pipeline.py         # Proprietary blend handling
├── test_coverage_gate.py                # Coverage gate logic
├── test_dosage_golden_fixtures.py       # Dosage golden tests
├── test_normalization_stability.py      # Determinism verification
├── test_scoring_invariants.py           # Score monotonicity
├── test_fuzzy_matching.py               # Fuzzy matcher accuracy
├── test_unit_conversions.py             # Unit conversion
├── test_allergen_negation.py            # Allergen negation parsing
├── test_cross_db_overlap_guard.py       # No entry in two DBs simultaneously
└── ... (47 files total)
```

### Class-Based Organization
Tests use `TestClass` grouping by domain:

```python
class TestBannedMatching:
    def test_propylparaben_exact(self): ...
    def test_propylparaben_alias_plural(self): ...

class TestBlendMerge:
    def test_proprietary_blend_children_surface(self): ...
    def test_dsld_group_blend_container_detection(self): ...
```

## Test Patterns

### Parametrized Tests
Used extensively for alias coverage:
```python
@pytest.mark.parametrize("alias,expected_key", [
    ("mono and diglycerides", "NHA_MONO_DIGLYCERIDES"),
    ("mono & diglycerides", "NHA_MONO_DIGLYCERIDES"),
    ("diglyceride", "NHA_MONO_DIGLYCERIDES"),
])
def test_mono_diglyceride_aliases(alias, expected_key): ...
```

### Golden Fixtures
Used for dosage and scoring output validation:
```python
# Loads from scripts/tests/fixtures/dosage_golden_*.json
def test_dosage_golden(fixture_path, expected): ...
```

### Regression Snapshots
Added whenever a bug is fixed — the bug case becomes a permanent test:
```python
# Regression: PIC was unmapped (should alias to polysaccharide-iron complex)
def test_pic_aliases_to_iron_polysaccharide_iron_complex(): ...
```

### DB Integrity Tests
Schema contract enforcement — tests fail if DB structure deviates:
```python
def test_iqm_all_entries_have_forms(): ...
def test_oi_all_entries_have_aliases_list(): ...
def test_no_entry_in_both_iqm_and_br(): ...
```

## Coverage Scope (~1085+ test cases)

| Domain | Approx. Tests | Key Files |
|--------|--------------|-----------|
| Pipeline regressions | 200+ | `test_pipeline_regressions.py` |
| Alias/unmapped | 150+ | `test_clean_unmapped_alias_regressions.py` |
| DB integrity | 100+ | `test_db_integrity.py`, `test_cross_db_overlap_guard.py` |
| Banned/harmful | 120+ | `test_banned_*`, `test_harmful_schema_v2.py` |
| Enrichment | 100+ | `test_enrichment_regressions.py` |
| Scoring | 80+ | `test_scoring_invariants.py`, `test_score_supplements.py` |
| Dosage | 80+ | `test_dosage_golden_fixtures.py`, `test_unit_conversions.py` |
| Blending | 60+ | `test_blend_merge_pipeline.py` |
| Coverage gate | 40+ | `test_coverage_gate.py` |
| Other | 155+ | Remaining 30 files |

## Key Testing Rules

1. **No mocks for DB data** — always load real `scripts/data/*.json`
2. **Every alias fix gets a regression test** — prevents alias regressions across pipeline runs
3. **Banned collision tests are sacred** — IQM ↔ BR collisions are safety-critical
4. **Normalizer stability** — same raw input must produce identical output across runs
5. **Coverage gate tests** must reflect actual gate thresholds (not hardcoded values)

## Known Test Gaps (as of 2026-03-16)

- No tests for `_is_dsld_group_blend_container()` (new method, not yet written)
- No tests for Vacha/Acorus calamus safety routing
- Krill Oil inactive routing not yet covered
- Titanium Dioxide alias variants not tested
- `Eicosatrienoic Acid` flat (non-nested) occurrence not tested
