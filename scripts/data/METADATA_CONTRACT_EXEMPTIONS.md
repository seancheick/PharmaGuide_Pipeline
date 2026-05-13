# Data-file metadata contract — exemptions reference

> **Where this file lives:** `scripts/data/METADATA_CONTRACT_EXEMPTIONS.md` (next to the data files it documents).
>
> **Why it exists:** The universal metadata-contract test ([scripts/tests/test_data_file_metadata_contract.py](../tests/test_data_file_metadata_contract.py)) catches off-by-N drift between `_metadata.total_entries` and actual entry count across all 73 `scripts/data/*.json` files. Some files have file-specific semantics the universal classifier can't enforce — those are marked `INTENTIONAL_EXCEPTIONS` and live behind a **bespoke per-file contract test**.
>
> **For devs reading a data file:** if you see a file in this table, its `_metadata.total_entries` does NOT follow the simple `len(payload)` rule. Read the linked bespoke test (or its docstring) to understand what's pinned and why before adding/removing entries.
>
> **Single source of truth:** `INTENTIONAL_EXCEPTIONS` dict in [test_data_file_metadata_contract.py](../tests/test_data_file_metadata_contract.py). This doc is a human-readable mirror — if you update either, update the other.

---

## Exemption table

| File | Why exempted | Bespoke contract test | What it pins |
|---|---|---|---|
| [`banned_match_allowlist.json`](banned_match_allowlist.json) | 2 top-level arrays (allowlist + denylist); `total_entries` tracks `allowlist` only | [test_banned_match_allowlist_contract.py](../tests/test_banned_match_allowlist_contract.py) | `total_entries == len(allowlist)`; both arrays must be present |
| [`cert_claim_rules.json`](cert_claim_rules.json) | Nested-dict shape; `total_entries` = Σ non-`_`-prefixed rule keys across `rules.*` (excludes per-category `_metadata` config) | [test_cert_claim_rules_contract.py](../tests/test_cert_claim_rules_contract.py) | Custom count rule + each rule category carries its own `_metadata` block |
| [`clinical_risk_taxonomy.json`](clinical_risk_taxonomy.json) | 7 top-level arrays — UNIQUE convention where `total_entries` = SUM of all 7 | [test_clinical_risk_taxonomy_contract.py](../tests/test_clinical_risk_taxonomy_contract.py) | Sum invariant + all 7 taxonomy arrays present and non-empty |
| [`color_indicators.json`](color_indicators.json) | 4 top-level arrays; `total_entries` tracks `natural_indicators` only (the other 3 are auxiliary) | [test_color_indicators_contract.py](../tests/test_color_indicators_contract.py) | `total_entries == len(natural_indicators)` + all 4 arrays present |
| [`fda_unii_cache.json`](fda_unii_cache.json) | Runtime cache (170K+ entries each in `name_to_unii` + `unii_to_name`) populated by `scripts/api_audit/fda_weekly_sync.py`. Static count would be forced to bump every sync — not meaningful. | *(no bespoke test — intentionally fluid)* | Freshness tracked by `_metadata.last_updated` instead of `total_entries` |
| [`functional_ingredient_groupings.json`](functional_ingredient_groupings.json) | 3 top-level arrays; `total_entries` tracks `functional_groupings` only | [test_functional_ingredient_groupings_contract.py](../tests/test_functional_ingredient_groupings_contract.py) | Primary array count + all 3 arrays present |
| [`ingredient_weights.json`](ingredient_weights.json) | Multi-section payload; `total_entries=4` tracks `dosage_weights` tier count (therapeutic / optimal / maintenance / trace), not categories or priorities | [test_ingredient_weights_contract.py](../tests/test_ingredient_weights_contract.py) | `total_entries == len(dosage_weights)` + structural config present |
| [`manufacture_deduction_expl.json`](manufacture_deduction_expl.json) | Hybrid runtime-config + documentation; mixed top-level (1 scalar + 4 dicts); `total_entries` tracks top-level section count. **Also runtime-validated** for code/base_deduction completeness. | [test_manufacture_deduction_expl_contract.py](../tests/test_manufacture_deduction_expl_contract.py) | 7 invariants — section count, 4 severity tiers, code+base_deduction on every subcategory, unique codes, 4 modifiers with expected shapes, total_deduction_cap is negative |
| [`migration_report.json`](migration_report.json) | Append-only audit log of a specific migration; `total_entries` tracks `alias_collisions_resolved` (headline count) only | [test_migration_report_contract.py](../tests/test_migration_report_contract.py) | `total_entries == len(alias_collisions_resolved)` |
| [`percentile_categories.json`](percentile_categories.json) | Mixed: `categories` (9) + `classification_rules` (4) at top level; `total_entries` tracks `categories` only — the 9 cohort definitions | [test_percentile_categories_contract.py](../tests/test_percentile_categories_contract.py) | Count + each non-fallback cohort has required schema (label, priority, evidence, min_evidence_score) |
| [`unit_conversions.json`](unit_conversions.json) | Multi-section payload; `total_entries=20` tracks `vitamin_conversions` only — other sub-dicts are static rule/alias config | [test_unit_conversions_contract.py](../tests/test_unit_conversions_contract.py) | `total_entries == len(vitamin_conversions)` + all 4 sections present |

---

## How to add a new exempted file

If you're adding a data file with a non-standard shape:

1. **Try to fit one of the 3 universal shapes first** (`single_array`, `single_payload_dict`, `top_level_dict_of_dicts` — see [test_data_file_metadata_contract.py:_classify_shape](../tests/test_data_file_metadata_contract.py)). If your file fits, drop in `_metadata.total_entries` matching the count and the universal test covers it for free.

2. **If it can't fit:**
   - Add an entry to `INTENTIONAL_EXCEPTIONS` in `test_data_file_metadata_contract.py` with a rationale + pointer to the bespoke test you're about to write.
   - Add a row to the table above with the same rationale + test link.
   - Write the bespoke test (`scripts/tests/test_<filename_without_extension>_contract.py`) following the pattern of any existing one. At minimum, pin the count invariant (whatever "count" means for this file) + structural defensive checks.
   - Add the `_metadata.contract_test` cross-reference field to the data file's `_metadata` pointing at the bespoke test file path (relative to repo root). This makes the cross-ref discoverable from the data file itself.

3. **Verify drift detection:** temporarily bump `_metadata.total_entries` by any non-zero delta and run the bespoke test. It must fail with a clear "Bump total_entries to N" message naming the detected shape.

## How to remove an exemption

If a file's shape changes such that it now fits the universal classifier, **remove it from `INTENTIONAL_EXCEPTIONS`** in the same commit that changes the shape — leaving stale exemptions hides drift.

## Related

- [Test remediation plan (2026-05-13)](../../docs/handoff/2026-05-13_test_remediation_plan.md) — full history of how this exemption system was designed and shipped (Phases 5-8).
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) — master schema reference for all 73 data files.
- [test_data_file_metadata_contract.py](../tests/test_data_file_metadata_contract.py) — the universal contract test.
