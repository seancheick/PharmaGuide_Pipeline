# Ingredient-row twins — classification and retirement (2026-09-25)

Follow-up to the row-key census on `harness/ownership`
(`scripts/audits/ingredient_row_key_census_20260925/`). That census found 51 active and 27
inactive row keys outside `audit_contract_sync.ACTIVE_CONTRACT` / `INACTIVE_CONTRACT` on the
shipped build (`scripts/dist`, db_version 2026.09.22.201915, 15,310 blobs, 78,877 active and
83,130 inactive rows).

## Classification

"Readers" covers Flutter `lib/` (current and git history), the reviewer console
(`scripts/submission_review`), the dashboard, `core_export_model.py`, Supabase functions and
SQL, `build_final_db.py` readers of the built rows, the release and manual audits, and tests.
Equality comes from a probe over every shipped row.

| Key(s) | Values on the shipped corpus | Shape | Readers | Outcome |
|---|---|---|---|---|
| `standardName` / `standard_name` (both lists) | identical on 78,877 / 83,130 rows | false dual brain | every `standardName` reader was a fallback beside `standard_name` | `standardName` retired |
| `normalized_value` / `normalized_amount` | identical on 78,877 rows | false dual brain | `_anchor_amount` fallback, `audit_raw_to_final` | `normalized_value` retired |
| `mapped` / `is_mapped` | identical on 78,877 rows | false dual brain | dashboard `ingredients_mapped` read `mapped`; `audit_raw_to_final` read both | `mapped` retired, `is_mapped` kept |
| inactive `label_display` / `display_label` | identical on 83,130 rows (both added in eaeb6f47) | false dual brain | app `inactiveFromMap` and `_inactiveRowDisplayLabel`, `catalog_gold` | `label_display` retired |
| `safety_hits` / `safety_flags` | different shapes | two policies, one topic | `safety_hits`: only the schema-3 pop and its payload report | `safety_hits` retired |
| `harmful_notes` (both lists) | different from `notes` / `mechanism_of_harm` | single owner | none, in any app version | retired |
| `forms` / `extracted_forms` | differ on 49,761 rows | two policies, one topic | `forms`: `audit_raw_to_final` branded-token and plant-part checks, label-fidelity and form-note reports | both kept |
| `matched_form` / `matched_forms` / `extracted_forms` | differ (best match vs candidate lists) | one policy, layered data | app `profile_gate_summary_filter` reads all three in order | kept |

Every other emitted key has one name. The rest of the row shape is now declared in the two
contracts, and a row key they do not declare fails `audit_contract_sync` (exit 1), as an
undeclared top-level key already did.

## Left for a follow-up

- Declared twins, identical on every shipped row: `dosage`/`quantity`,
  `dosage_unit`/`unit`, `score`/`bio_score`. The app reads `dosage` in 3 files.
- Single-owner keys with no reader found, marked in the contracts:
  active `natural`, `is_allergen`, `source_label_key`, `identity_resolution_rationale`,
  `canonical_id_before`, `adequacy_tier`, `cfu_confidence`, `dose_basis`, `ui_copy_hint`,
  `jurisdiction_scope`; inactive `mechanism_of_harm`, `common_uses`,
  `resolved_display_label`, `label_row_disposition`, `jurisdiction_scope`.

## Evidence

```bash
# The gate on the shipped build flags exactly the retired twins (exit 1):
python3 scripts/audit_contract_sync.py --build-dir scripts/dist --out /tmp/cs.json
#   active row keys undeclared:   5 ['harmful_notes', 'mapped', 'normalized_value', 'safety_hits', 'standardName']
#   inactive row keys undeclared: 3 ['harmful_notes', 'label_display', 'standardName']

# A fresh build_final_db run on this branch (same enriched/scored inputs as the
# snapshot script; 15,310 products, 0 errors) passes the gate (exit 0):
#   active row keys undeclared:   0 []
#   inactive row keys undeclared: 0 []

# Behaviour check: with the 8 retired keys dropped from the shipped blobs, all
# 15,310 fresh blobs are JSON-equal to the shipped ones; products_core differs
# only in detail_blob_sha256, exported_at and the release-step thumbnail URL.
```
