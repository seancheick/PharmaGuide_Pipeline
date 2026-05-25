# UNII Same-Tier P0 Model Spec

Generated: 2026-05-25

Source reports:

- `scripts/audits/unii_same_tier_conflicts_2026_05_25.json`
- `scripts/audits/unii_same_tier_high_review_triage_2026_05_25.md`

Scope: P0 model decisions for the three highest-risk high-review groups. P0-1
and P0-2 have now shipped; P0-3 remains a pending context-routing decision.

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

Original runtime first-write results before the P0 cleanups:

| UNII | Original runtime payload | Why this matters |
|---|---|---|
| `88XHZ13131` | `Policy Watchlist: Synthetic Food Acids` tier 1 | Concrete fumaric-acid UNII resolved to a broad policy umbrella. |
| `6DU9Y533FA` | `Vanadyl Sulfate` tier 4 | Same identity existed as both a standalone IQM parent and a form under `vanadium`. |
| `L11K75P92J` | `Calcium` tier 4 | Dicalcium phosphate UNII resolves to calcium parent/form path, while standalone and inactive-filler entries also exist. |

## P0-1: `88XHZ13131` synthetic-food-acid policy vs fumaric acid

Status: resolved in the P0-1 cleanup. The policy entry no longer carries the
exact fumaric-acid UNII, and disabled/historical banned/watchlist entries no
longer populate `_fast_exact_lookup`.

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
  `adipic acid`, `e355`, `synthetic citric acid`), `OI_FUMARIC_ACID` originally
  inherited the tier-1 policy payload during UNII index construction.

### Model Decision

`BANNED_ADD_SYNTHETIC_FOOD_ACIDS` must not own an exact compound UNII. The UNII
belongs to `OI_FUMARIC_ACID`.

### Applied Fix

This was a two-part root fix:

1. **Data cleanup**
   - Removed `external_ids.unii = "88XHZ13131"` from
     `BANNED_ADD_SYNTHETIC_FOOD_ACIDS`.
   - Added a reviewer note explaining that the policy entry is a multi-compound
     umbrella with no exact UNII.

2. **Runtime-contract hardening**
   - Made `_build_fast_lookups_impl` honor `match_mode in {"disabled",
     "historical"}` for banned/watchlist entries.
   - Without this runtime fix, removing the policy UNII alone would have been insufficient:
     the `fumaric acid` alias still causes the other-ingredient record to
     inherit the tier-1 policy payload.

### Regression Tests

- `BANNED_ADD_SYNTHETIC_FOOD_ACIDS` has no exact UNII.
- `_fast_exact_lookup["fumaric acid"]` does not resolve to the disabled policy
  watchlist entry.
- UNII `88XHZ13131` resolves to a concrete `Fumaric Acid` record, not the
  synthetic-food-acid policy umbrella.
- Existing enrichment safety checks still skip disabled/historical policy
  entries.

## P0-2: `6DU9Y533FA` vanadium / vanadyl sulfate structural duplicate

Status: resolved in the P0-2 cleanup. The exact vanadyl sulfate UNII is now
owned only by the standalone `vanadyl_sulfate` IQM parent, while generic
`Vanadium` lookup routes to the elemental `vanadium` parent.

Records:

- `ingredient_quality_map.json` → `vanadium.forms[vanadium (unspecified)]`
- `ingredient_quality_map.json` → `vanadyl_sulfate`

### Observed Facts

- GSRS verifies `6DU9Y533FA` as **VANADYL SULFATE**, exact compound identity.
- `vanadium` parent has UNII `00J9J9XKDE`.
- `vanadium.forms[vanadium (unspecified)]` is the generic elemental-vanadium
  label bucket and no longer carries exact vanadyl sulfate UNII ownership.
- Standalone parent `vanadyl_sulfate` carries `6DU9Y533FA` and owns exact
  vanadyl sulfate / vanadium salt labels.
- Runtime exact lookup now routes `Vanadium` to `vanadium`, while explicit
  `Vanadyl Sulfate`, `Vanadium Sulfate`, `vanadyl`, and specific vanadium
  salt/chelate labels route to `vanadyl_sulfate`.
- `vanadyl_sulfate` forms now share the audited class-equivalence
  `bio_score=7` floor where old chelate-premium scores had remained.

### Model Decision

The chosen canonical model:

- `Vanadium` / UNII `00J9J9XKDE` → `vanadium`
- `Vanadyl Sulfate` / UNII `6DU9Y533FA` → `vanadyl_sulfate`
- `vanadium.forms[vanadium (unspecified)]` carries only a `unii_note`, not
  exact `external_ids.unii`.
- Generic aliases that preprocess to bare `vanadium` must not live on
  `vanadyl_sulfate` forms.

### Applied Fix

- Renamed the `vanadium` form from `vanadyl sulfate` to
  `vanadium (unspecified)`.
- Removed `external_ids.unii = "6DU9Y533FA"` from the `vanadium` form and added
  a `unii_note` pointing exact vanadyl sulfate identity to the standalone
  `vanadyl_sulfate` parent.
- Moved generic plain-vanadium aliases off `vanadyl_sulfate`.
- Removed BMOV aliases `organic vanadium` / `organic vanadium supplement`
  because the normalizer strips `organic`, making them implicit bare
  `vanadium` aliases.
- Collapsed old higher `vanadyl_sulfate` chelate/form scores to `bio_score=7`
  per B25 class-equivalence / Willsky 2013 (PMID:23982218).
- Regenerated the scanner report; `6DU9Y533FA` no longer appears.

### Regression Tests

- UNII ownership is not duplicated between `vanadium` and `vanadyl_sulfate`.
- No same-tier conflict remains for `6DU9Y533FA`.
- A label with generic `Vanadium` routes to `vanadium`.
- Labels with explicit `Vanadyl Sulfate` / vanadium salt terms route to
  `vanadyl_sulfate`.
- `vanadyl_sulfate` forms obey the class-equivalence `bio_score=7` floor.

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
   Complete.
2. `P0-2` vanadyl model decision + score reconciliation. Complete.
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
