# Test Suite Consolidation Plan (Phase 2)

**Document version:** 1.0.0
**Date:** 2026-04-26
**Status:** Phase 1 shipped (markers + conftest); Phase 2 deferred deliberately.

---

## TL;DR for the next session

The test suite has 18 batch-style integrity files (`test_b18_*` through
`test_b35_*`) created during the IQM audit. Each one codifies a specific
batch's clinical decisions as regression guards. They're all green and
fast — the question is whether to consolidate them into 3 canonical files.

**Phase 1 is done** (this session, 2026-04-26): pytest.ini with markers,
shared conftest.py for sys.path, slow markers on the 2 actually-heavy
files. Full suite stays at 5800 tests; fast subset (`-m "not slow"`)
runs in 2:01 vs 4:20 default.

**Phase 2** (this doc): collapse the 18 batch files into 3 canonical
parametrized files. Mechanical work, ~3 hours, low risk if done right.
Skipped this session because the runtime savings are zero — the files
are already fast. The value is maintainability.

---

## Why Phase 2 is worth doing eventually (but not urgent)

**Current:**
- 18 files, each ~150-300 lines, each with module fixture + parametrize tables + 5-15 specific tests
- Total: ~3000 lines of mostly-mechanical assertions
- Each file repeats the same imports, fixture, IQM load, identical assertion shapes

**After consolidation:**
- 3 files, ~600 lines total, single source of truth for IQM form data
- One canonical `IQM_FORM_QUALITY_TABLE` lists every (parent, form, expected_bio, expected_natural)
- One canonical `IQM_CLASS_AUTHORITY_PMIDS` lists every required citation
- One canonical `IQM_CATEGORY_ERROR_PARENTS` lists every category-error mechanism

**Cost-benefit:**
- LoC: 3000 → 600 (~80% reduction in test code)
- Runtime: unchanged (already fast)
- Discovery: a future session asking "where is chromium picolinate's bio_score asserted?" finds ONE place, not 3 scattered files
- Risk during migration: medium — each migration step needs to verify parity (assertions still fire on regression)

**Why not now:**
- 0 runtime benefit (the speed wins are in pipeline_regressions/enrichment_regressions, already marked slow)
- All 18 files currently pass — there's no breakage forcing a rewrite
- A bad migration could silently drop coverage. Better to do it deliberately, not under pressure.

---

## What Phase 1 already achieved

### `pytest.ini`
Project-level config. Markers registered with `--strict-markers` so typos fail the build. Default runs everything (accuracy-first); explicit opt-in for fast iteration:

```bash
pytest                       # full suite, 5800 tests, ~4:20
pytest -m "not slow"         # fast subset, 5408 tests, ~2:01
pytest -m "slow"             # only the heavy integration tests
pytest -n auto               # parallel (needs pytest-xdist installed)
```

### `scripts/tests/conftest.py`
Sets `sys.path` once for the whole suite. Eliminates the per-file
`sys.path.insert(...)` hack and makes individual test files runnable
standalone (e.g., `pytest scripts/tests/test_provenance_invariants.py`
now works — it didn't before).

### Slow markers
Two files marked `pytestmark = pytest.mark.slow`:
- `test_pipeline_regressions.py` (73s, 197 tests)
- `test_enrichment_regressions.py` (19s, 195 tests)

Together: 92s of the 260s total. Other "big" files were checked and
turned out to be fast (test_score_supplements is 1.3s; test_clean_unmapped_alias_regressions is 2.1s — fixtures are properly cached `scope='module'`).

---

## Phase 2 design — 3 canonical IQM tests

### `scripts/tests/test_iqm_form_quality.py`
Single parametrized test covering every form's `bio_score` + `natural` + derived `score`.

```python
"""Canonical IQM form-quality regression guards.

Replaces the 18 batch-style files (test_b18_*, test_b21_* … test_b35_*).
One source of truth for "what bio_score does this form have?" across the
entire IQM. Adding a new form: add one row. Modifying a Dr Pham
sign-off: edit one row.
"""
import json
from pathlib import Path
import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)

# Format: (parent_id, form_name, expected_bio, expected_natural, basis)
# Sourced from B18-B35 batch files. Each row's basis comments back to the
# original audit decision so reviewers can trace clinical rationale.
IQM_FORM_QUALITY = [
    # ── Iron / calcium (B27) ──────────────────────────────────────────────
    ('iron', 'iron picolinate',                 8, False, 'B27 Sabatier 2020 = ferrous sulfate, NOT premium'),
    ('iron', 'iron bisglycinate',              12, False, 'B27 retained per stable-isotope evidence'),
    # ── B12 / Dr Pham C2 (B35) ────────────────────────────────────────────
    ('vitamin_b12_cobalamin', 'methylcobalamin sublingual', 12, True,  'B35 Dr Pham C2: only sublingual retains premium'),
    ('vitamin_b12_cobalamin', 'methylcobalamin',            8,  True,  'B35 Dr Pham C2: plain form downgraded 14→8'),
    ('vitamin_b12_cobalamin', 'adenosylcobalamin',          8,  True,  'B35 Dr Pham C2'),
    # ── Chromium / Dr Pham C7 (B35) ───────────────────────────────────────
    ('chromium', 'chromium picolinate',         7, False, 'B35 Dr Pham C7: form-independent class F'),
    ('chromium', 'chromium nicotinate glycinate',7, False, 'B35 Dr Pham C7'),
    # ── Brown rice chelates / Dr Pham C4 ──────────────────────────────────
    ('chromium',   'chromium brown rice chelate',  6, False, 'B35 Dr Pham C4'),
    ('iron',       'iron brown rice chelate',      6, False, 'B35 Dr Pham C4'),
    ('molybdenum', 'molybdenum brown rice chelate',11, False, 'B35 Dr Pham C4'),
    # … plus ~200 more rows from the b18-b35 series
]

@pytest.mark.parametrize('parent_id,form_name,expected_bio,expected_natural,basis', IQM_FORM_QUALITY)
def test_form_quality(iqm, parent_id, form_name, expected_bio, expected_natural, basis):
    form = iqm[parent_id]['forms'].get(form_name)
    assert form is not None, f'{parent_id}::{form_name} missing — {basis}'
    assert form['bio_score'] == expected_bio, f'{parent_id}::{form_name} bio_score drift — {basis}'
    assert form['natural'] == expected_natural, f'{parent_id}::{form_name} natural flag drift — {basis}'
    expected_score = expected_bio + (3 if expected_natural else 0)
    assert form['score'] == expected_score, f'{parent_id}::{form_name} score recompute drift'
```

### `scripts/tests/test_iqm_class_authority_pmids.py`
Each verified class-authority PMID must be referenced somewhere in IQM notes (regression guard against accidental note rewrites that drop citations).

```python
"""Verify every class-authority PMID still appears in IQM notes."""

# Sourced from b21-b35 PMID assertions. One canonical map.
CLASS_AUTHORITY_PMIDS = {
    'PMID:2507689':  'Hallberg 1989 Fe3+ reduction',
    'PMID:24408120': 'Yokoyama 2014 ferric citrate (Auryxia)',
    'PMID:31187261': 'Sabatier 2020 iron picolinate',
    'PMID:11444420': 'Heaney 2001 CaCO3',
    'PMID:9001835':  'Talent 1996 NAG → glucosamine',
    'PMID:19847319': 'Crowley 2009 UC-II oral tolerance',
    # … (~25 more)
}

def test_all_class_authority_pmids_in_notes(iqm):
    full_text = ''
    for parent in iqm.values():
        if not isinstance(parent, dict) or 'forms' not in parent: continue
        for form in parent['forms'].values():
            full_text += (form.get('notes') or '') + ' '
    missing = [p for p in CLASS_AUTHORITY_PMIDS if p not in full_text]
    assert not missing, f'PMID drift: {missing}'
```

### `scripts/tests/test_iqm_category_errors.py`
Every category-error parent must have its mechanism documented in form.notes.

```python
"""Each of the 8+ category-error parents must document its mechanism."""

CATEGORY_ERRORS = [
    ('manuka_honey',         'umf 15+ / mgo 514+',                ['local action', 'topical', 'wound']),
    ('organ_extracts',       'grass-fed desiccated',              ['composite', 'protein digestion']),
    ('inulin',               'inulin (unspecified)',              ['colonic fermentation', 'scfa']),
    ('slippery_elm',         'standardized extract (mucilage)',   ['mucilage', 'viscous fiber']),
    ('psyllium',             'psyllium seed',                     ['viscous fiber']),
    ('superoxide_dismutase', 'sod supplement',                    ['protein digestion', 'amino acid']),
    ('fiber',                'konjac glucomannan',                ['viscous fiber']),
    ('collagen',             'undenatured collagen',              ['oral tolerance', 'peyer', 'galt']),
    # ── B28 spirulina / digestive enzymes (Dr Pham E2/E3) ──
    ('spirulina',            'spirulina powder',                  ['composite food']),
    ('digestive_enzymes',    'plant-based enzyme complex',        ['local action']),
    # … etc
]

@pytest.mark.parametrize('parent_id,form_name,required_phrases', CATEGORY_ERRORS)
def test_category_error_documented(iqm, parent_id, form_name, required_phrases):
    form = iqm[parent_id]['forms'].get(form_name)
    if form is None: pytest.skip(f'{parent_id}::{form_name} not present (intentional in some configs)')
    assert (form.get('absorption_structured') or {}).get('value') is None, (
        f'{parent_id}::{form_name} should be null per category-error pattern'
    )
    text = ((form.get('notes') or '') + ' ' + (form.get('absorption') or '')).lower()
    assert any(p.lower() in text for p in required_phrases), (
        f'{parent_id}::{form_name} must document one of: {required_phrases}'
    )
```

---

## Migration steps (next session)

### Step 1 — Build the new files alongside the old
Create the 3 canonical files. Populate the parametrize tables by reading
each `test_b*_integrity.py` and lifting the assertions. Keep old files
untouched.

### Step 2 — Run both
```bash
pytest scripts/tests/test_iqm_form_quality.py \
       scripts/tests/test_iqm_class_authority_pmids.py \
       scripts/tests/test_iqm_category_errors.py \
       scripts/tests/test_b*.py
```

If both old and new pass: parity confirmed.

### Step 3 — Cross-check: would any future regression be caught by both?

Pick 5 random rows from `IQM_FORM_QUALITY`. Temporarily flip the
`expected_bio` to a wrong value. Run pytest. Both the new file AND the
old `test_b*` file that originally tested that pair should fire.
If they both fire on the same row, that row is double-covered — safe to
delete from the old file. If only the new fires, the old file had less
coverage than thought — note it but proceed.

### Step 4 — Delete the redundant old files
File-by-file. Commit each deletion atomically:
```bash
git rm scripts/tests/test_b21_class_application_integrity.py
git commit -m "tests: remove b21 — coverage migrated to test_iqm_form_quality.py"
```

### Step 5 — Keep the unique tests
Some `test_b*` files have semantically-unique assertions that don't fit
the canonical tables. Keep those. Examples:
- B31's "8th category-error UC-II" test asserts a *count* (8 parents
  fit the pattern) — that's a meta-check, not a per-row assertion. Keep.
- B27's `test_iron_picolinate_below_bisglycinate` is a *cross-form*
  comparison, not a per-row check. Keep.

Anything that's pure (parent, form, expected_bio) data → delete.
Anything with comparative or count-based logic → keep.

### Step 6 — Verify no regression
```bash
pytest scripts/tests/ --ignore=scripts/tests/test_verify_interactions_live.py
# Should still be 5800 passed (or a few less if dedup'd assertions removed)
```

---

## What NOT to do

- **Don't migrate b18-b35 in one mega-commit.** Each `test_b*` file's
  migration should be its own commit, easy to revert if parity fails.
- **Don't delete test files without running BOTH suites.** Parity must
  be empirically verified, not assumed.
- **Don't fold semantically-distinct assertions into the canonical
  tables.** "iron picolinate < iron bisglycinate" is a relation; it
  belongs in its own test, not a parametrized data row.
- **Don't touch `test_b35_dr_pham_signoff_integrity.py` blindly.**
  Dr Pham reviewed those exact assertions for clinical sign-off. If you
  migrate, the canonical file is the source of truth and `test_b35_*`
  should be deleted *after* parity is confirmed — not before.

---

## Estimated effort

- Build the 3 canonical files with full data: 90 min (mostly transcribing parametrize tables)
- Verify parity: 15 min
- Delete old files: 15 min (one git rm per file)
- Final test run + commit: 15 min

**Total: ~2.5 hours of focused work.** Save it for a session where
you're not interrupted by clinical reviews — this is mechanical, but
mistakes silently drop coverage.
