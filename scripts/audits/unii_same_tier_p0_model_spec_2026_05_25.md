# UNII Same-Tier P0 Model Spec

Generated: 2026-05-25

Source reports:

- `scripts/audits/unii_same_tier_conflicts_2026_05_25.json`
- `scripts/audits/unii_same_tier_high_review_triage_2026_05_25.md`

Scope: P0 model decisions for the three highest-risk high-review groups. This
is a planning/spec artifact only. No data or runtime behavior was changed.

## Verification Summary

Live GSRS verification was run with:

```bash
python3 scripts/api_audit/verify_unii.py --search "Fumaric Acid"
python3 scripts/api_audit/verify_unii.py --search "Vanadyl Sulfate"
python3 scripts/api_audit/verify_unii.py --search "Dicalcium Phosphate"
python3 scripts/api_audit/verify_unii.py --search "Calcium"
python3 scripts/api_audit/verify_unii.py --search "Vanadium"
```

Verified identities:

| Substance | GSRS name | UNII | CAS | RxCUI | Notes |
|---|---|---|---|---|---|
| Fumaric Acid | Fumaric acid | `88XHZ13131` | `110-17-8` | `70598` | Exact compound identity. |
| Vanadyl Sulfate | VANADYL SULFATE | `6DU9Y533FA` | `27774-13-6` | `39364` | Exact compound identity. |
| Dicalcium Phosphate | Anhydrous dibasic calcium phosphate | `L11K75P92J` | `7757-93-9` | `253163` | Exact compound identity; active moiety is calcium cation. |
| Calcium | Calcium | `SY7Q814VUP` | `7440-70-2` | `1895` | Mineral parent, distinct from dicalcium phosphate salt. |
| Vanadium | VANADIUM | `00J9J9XKDE` | `7440-62-2` | `11121` | Element parent, distinct from vanadyl sulfate salt. |

Runtime lookup spot-check:

```python
EnhancedDSLDNormalizer()._unii_to_payload_lookup["88XHZ13131"]
EnhancedDSLDNormalizer()._unii_to_payload_lookup["6DU9Y533FA"]
EnhancedDSLDNormalizer()._unii_to_payload_lookup["L11K75P92J"]
```

Current runtime first-write results:

| UNII | Current runtime payload | Why this matters |
|---|---|---|
| `88XHZ13131` | `Policy Watchlist: Synthetic Food Acids` tier 1 | Concrete fumaric-acid UNII resolves to a broad policy umbrella. |
| `6DU9Y533FA` | `Vanadyl Sulfate` tier 4 | Same identity exists as both a standalone IQM parent and a form under `vanadium`. |
| `L11K75P92J` | `Calcium` tier 4 | Dicalcium phosphate UNII resolves to calcium parent/form path, while standalone and inactive-filler entries also exist. |

## P0-1: `88XHZ13131` synthetic-food-acid policy vs fumaric acid

Records:

- `banned_recalled_ingredients.json` → `BANNED_ADD_SYNTHETIC_FOOD_ACIDS`
  (`Policy Watchlist: Synthetic Food Acids`)
- `other_ingredients.json` → `OI_FUMARIC_ACID` (`Fumaric Acid`)

### Observed Facts

- GSRS verifies `88XHZ13131` as **Fumaric acid**, not a synthetic-food-acid
  class.
- The policy entry is explicitly modeled as a class:
  - `entity_type: "class"`
  - `cui_status: "no_single_umls_concept"`
  - `match_mode: "disabled"`
  - `inactive_policy: "excipient_acceptable"`
- Despite `match_mode: "disabled"`, `EnhancedDSLDNormalizer._build_fast_lookups_impl`
  still indexes the policy standard name and aliases into `_fast_exact_lookup`.
- Because the policy aliases include exact compounds (`fumaric acid`, `e297`,
  `adipic acid`, `e355`, `synthetic citric acid`), `OI_FUMARIC_ACID` inherits
  the tier-1 policy payload during UNII index construction.

### Model Decision

`BANNED_ADD_SYNTHETIC_FOOD_ACIDS` must not own an exact compound UNII. The UNII
belongs to `OI_FUMARIC_ACID`.

### Recommended Fix

This is a two-part root fix:

1. **Data cleanup**
   - Remove `external_ids.unii = "88XHZ13131"` from
     `BANNED_ADD_SYNTHETIC_FOOD_ACIDS`.
   - Add a reviewer note explaining that the policy entry is a multi-compound
     umbrella with no exact UNII.

2. **Runtime-contract hardening**
   - Make `_build_fast_lookups_impl` honor `match_mode in {"disabled",
     "historical"}` for banned/watchlist entries, or explicitly document and
     test any exception.
   - Without this runtime fix, removing the policy UNII alone is insufficient:
     the `fumaric acid` alias still causes the other-ingredient record to
     inherit the tier-1 policy payload.

### Regression Tests

- `BANNED_ADD_SYNTHETIC_FOOD_ACIDS` has no exact UNII.
- `_fast_exact_lookup["fumaric acid"]` does not resolve to the disabled policy
  watchlist entry.
- UNII `88XHZ13131` resolves to `Fumaric Acid` as an other ingredient, not the
  synthetic-food-acid policy umbrella.
- Existing enrichment safety checks still skip disabled/historical policy
  entries.

## P0-2: `6DU9Y533FA` vanadium / vanadyl sulfate structural duplicate

Records:

- `ingredient_quality_map.json` → `vanadium.forms[vanadyl sulfate]`
- `ingredient_quality_map.json` → `vanadyl_sulfate`

### Observed Facts

- GSRS verifies `6DU9Y533FA` as **VANADYL SULFATE**, exact compound identity.
- `vanadium` parent has UNII `00J9J9XKDE`.
- `vanadium.forms[vanadyl sulfate]` has bio_score `4` and notes warning about
  poor oral bioavailability and toxicity.
- Standalone parent `vanadyl_sulfate` also carries `6DU9Y533FA` and has its own
  richer form set, including `vanadyl sulfate (VOSO4)` with bio_score `9`.
- Current runtime UNII lookup maps `6DU9Y533FA` to standalone `Vanadyl Sulfate`,
  not the lower-scored form under `vanadium`.

### Model Decision Needed

Choose one canonical model:

1. **Preferred**: `vanadyl_sulfate` is the canonical IQM parent for vanadyl
   products, and `vanadium.forms[vanadyl sulfate]` should stop carrying the
   same UNII/form identity.
2. Alternative: `vanadium` remains the canonical parent, and the standalone
   `vanadyl_sulfate` parent should be retired/redirected.

Given the standalone parent has multiple vanadium salt/chelate forms, the
preferred model is to keep `vanadyl_sulfate` as canonical for these supplement
labels and remove or de-identify the duplicate form-level UNII under `vanadium`.

### Recommended Fix

- Test-first decide and lock canonical routing for labels/UNIIs:
  - `Vanadium` / UNII `00J9J9XKDE` → `vanadium`
  - `Vanadyl Sulfate` / UNII `6DU9Y533FA` → `vanadyl_sulfate`
- Remove `external_ids.unii` from `vanadium.forms[vanadyl sulfate]` or replace
  it with a note that the exact identity is represented by `vanadyl_sulfate`.
- Reconcile score divergence between the old `vanadium.forms[vanadyl sulfate]`
  bio_score `4` and standalone `vanadyl_sulfate` forms before shipping a data
  edit. This is clinical-scoring data, not just identifier plumbing.

### Regression Tests

- UNII `6DU9Y533FA` resolves deterministically to the chosen parent.
- No same-tier conflict remains for `6DU9Y533FA`.
- A label with generic `Vanadium` does not accidentally route to vanadyl
  sulfate.
- A label with explicit `Vanadyl Sulfate` routes to the chosen vanadyl form.

## P0-3: `L11K75P92J` calcium / dicalcium phosphate active-vs-filler model

Records:

- `ingredient_quality_map.json` → `calcium.forms[dicalcium phosphate]`
- `ingredient_quality_map.json` → `dicalcium_phosphate`
- `other_ingredients.json` → `PII_DICALCIUM_PHOSPHATE`

### Observed Facts

- GSRS verifies `L11K75P92J` as **Anhydrous dibasic calcium phosphate**.
- Calcium parent has UNII `SY7Q814VUP`; dicalcium phosphate is a calcium salt,
  not the calcium element.
- Current runtime UNII lookup maps `L11K75P92J` to the `Calcium` payload because
  the calcium form is indexed before the standalone parent/filler entry.
- The same exact substance legitimately appears in two label roles:
  - active mineral source
  - inactive filler/binder/excipient
- Existing entries reflect that split but do not make the context rule explicit.

### Model Decision

Do not collapse this to one global identity. Dicalcium phosphate needs
context-aware routing:

- Active-ingredient row / mineral context → calcium-source form or dedicated
  active parent, depending on final IQM model.
- Inactive-ingredient row / filler context → `PII_DICALCIUM_PHOSPHATE`.

### Recommended Fix

Two defensible options:

1. **Preferred**: keep `calcium.forms[dicalcium phosphate]` as the active
   mineral-source model, keep `PII_DICALCIUM_PHOSPHATE` as inactive filler,
   and remove/retire standalone `dicalcium_phosphate` as duplicate unless
   there is a distinct scoring need.
2. Alternative: keep standalone `dicalcium_phosphate` as the active model and
   remove the duplicate calcium form UNII. This is less aligned with calcium
   dose scoring because labels usually disclose dicalcium phosphate as a form
   of calcium.

### Regression Tests

- Active row `Dicalcium Phosphate` with mineral context routes to the intended
  active calcium/dicalcium model.
- Inactive row `Dicalcium Phosphate` routes to `PII_DICALCIUM_PHOSPHATE` and
  remains non-scorable.
- UNII `L11K75P92J` does not silently resolve to a misleading parent in both
  contexts.
- No same-tier conflict remains unless explicitly exonerated with a context
  reason.

## Implementation Sequence

Do not batch these into one data edit. Recommended sequence:

1. `P0-1` runtime-contract + data cleanup for disabled policy watchlist entries.
   This removes the highest-risk safety-tier false ownership.
2. `P0-2` vanadyl model decision + score reconciliation. This needs clinical
   review because current forms disagree materially on bio_score.
3. `P0-3` dicalcium context-routing decision. This is an identity/context
   problem, not a simple duplicate deletion.

Each implementation commit should be test-first and should re-run:

```bash
python3 -m pytest scripts/tests/test_unii_same_tier_conflict_audit.py scripts/tests/test_unii_match_path.py -q
python3 scripts/api_audit/audit_unii_same_tier_conflicts.py --output-dir /tmp --timestamp p0_check --fail-on-high-review
```

For `--fail-on-high-review`, expect failure until all high-review groups are
resolved or explicitly exonerated. For per-P0 commits, inspect the specific UNII
group in the generated JSON rather than requiring global zero high-review.
