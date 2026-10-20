# Cleaner safety-classification equivalence — PR #176 fuzzy removal (2026-10-19)

Question: did removing the cleaner's fuzzy fallback (PR #176) change any banned, harmful or
allergen classification? `probe.py` runs
`EnhancedDSLDNormalizer._priority_based_classification` from one checkout and records
`banned_info`, `harmful_info` and `allergen_info` per name.

Name set (6,851): every distinct ingredient row name in the 2,221-label frozen raw cohort from
PR #176's replay (`~/pg_quality/clean_fuzzy_20261019/frozen_raw`, 37 brands), plus each
`allergens.json` standard name and alias with prefix (`organic`, `natural`, `hydrolyzed`),
suffix (`powder`, `extract`, `oil`, `(non-gmo)`, plural `s`) and one-letter typo variants.

| Checkout | Commit | Names | Banned | Harmful | Allergen |
|---|---|---|---|---|---|
| base (merge-base of #176) | 6aaa9e874 | 6,851 | 38 | 174 | 1,389 |
| head (#176 tip) | 528989f5d | 6,851 | 38 | 174 | 1,389 |

`receipt.json`: 0 changed names; both outputs byte-identical
(sha256 `d4276c36…c86def`). Outputs: `~/pg_quality/clean_allergen_equivalence_20261019/`.

Sensitivity: the same harness over `non_harmful_info` (excluded from the probe because PR #176
deliberately removed those fuzzy matches) shows 936 changed names, e.g. "Acacia catechu wood and
bark extract" was fuzzy-matched to the filler "natural fiber" on base. So the probe does detect
matcher changes.

Pre-existing, unchanged by #176 (same on base and head): every exact name and alias is detected
(229/229), but "hydrolyzed X" (227), "X oil" (219) and plural "Xs" (223) variants are not
flagged by the cleaner allergen check. The enricher's ingredient-list allergen match
(`enrich_supplements_v3.py::_check_allergens`) is also exact, so such rows rely on a label
"Contains" statement. Logged as a follow-up, not fixed here.

CI floor: `scripts/tests/test_allergen_alias_detection.py` (every name and alias classifies as
its own allergen).

Rerun:

```bash
source scripts/python_env.sh
git worktree add --detach /tmp/base <base>; git worktree add --detach /tmp/head <head>
$PG_PYTHON scripts/audits/clean_allergen_equivalence_20261019/probe.py run --scripts-dir /tmp/base/scripts --raw-dir <frozen_raw> --out base.json
$PG_PYTHON scripts/audits/clean_allergen_equivalence_20261019/probe.py run --scripts-dir /tmp/head/scripts --raw-dir <frozen_raw> --out head.json
$PG_PYTHON scripts/audits/clean_allergen_equivalence_20261019/probe.py compare base.json head.json
```
