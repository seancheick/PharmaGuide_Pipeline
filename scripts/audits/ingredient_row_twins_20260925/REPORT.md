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

## Follow-up (same day): declared twins and zero-reader keys

Same reader sweep, plus the website repo and the app's Supabase functions and migrations.
A same-named key at another blob path (`probiotic_detail.clinical_strains[]`, `warnings[]`,
`rda_ul_data`) is a different owner and was not counted as a row reader. Every key below was
retired.

| Key(s) | Shipped values | Shape | Readers | Why it goes |
|---|---|---|---|---|
| `dosage` / `quantity`, `dosage_unit` / `unit` | identical on 78,877 rows | false dual brain | app `readDoseAmount` / `readDoseUnit` and the profile-gate per-day reader, `_anchor_amount`, `audit_raw_to_final`, `audit_dv_plausibility`, dashboard inspector; every one also reads `quantity` / `unit`, in every app version | `quantity` / `unit` kept |
| `score` / `bio_score` | identical on 78,877 rows | false dual brain (v3.6.0 alias) | none on the row; scoring reads the IQD `score`, a different layer | `bio_score` kept |
| active `natural` | 18,297 true | single owner | none ever | sourcing unscored since v3.6.0 |
| active `is_allergen` | 1,026 true | single owner | none ever | allergens ship on blob-level `allergens`, which the app reads |
| active `source_label_key`, `identity_resolution_rationale`, `canonical_id_before` | populated | stated audit trail (47d70a39) | none on the blob | the trail's owner is the enriched IQD identity stamp; `audit_identity_integrity` (release gate) reads it there |
| active `adequacy_tier`, `cfu_confidence`, `dose_basis`, `ui_copy_hint` | non-null on ≤158 rows | copies of the matched `probiotic_detail.clinical_strains` entry | tests only | still ship on `clinical_strains` with `source_row_ref`; `display_badge` still derives from the tier |
| inactive `mechanism_of_harm`, `common_uses` | 25,887 / 45,236 non-empty | single owner | none ever (the app's `mechanism_of_harm` read was on `warnings[]`, dropped in 48379c1) | curated text stays in the data files and on harmful-additive warnings |
| `jurisdiction_scope` (both lists) | derivable on all 162,007 rows | restatement of `us_applicable` + `jurisdictions` | none | warnings keep their own |
| inactive `label_row_disposition` | derivable on all 83,130 rows | restatement of `is_label_descriptor` / `is_active_only` | none (app reads `is_label_descriptor`) | |
| inactive `resolved_display_label` | differs from `display_label` on 46,623 rows | single owner | none since 2026-06-15 | the resolver name `display_label` showed before it switched to label wording |

Not changed, recorded for later:

- Scoring modules keep tolerant amount-key lists that include `dosage`
  (`scoring_input_contract`, `gate_completeness`, `route_features`, `prebiotic_catalog`,
  `probiotic_dose`, `omega_dose` / `omega_formulation` / `omega_transparency`). They read
  enriched rows, where `dosage` never occurs (0 of 120 product files), so they are inert.
- The enriched IQD keeps `natural` and the `score` alias; `EXPORT_REQUIRED_IQD_FIELDS` (declared
  in both the enricher and `build_final_db`) still requires them. That is the enrichment contract,
  and scoring's `generic_helpers` reads IQD `score` as a fallback.
- `probiotic_detail.clinical_strains[]` confidence fields and `warnings[].mechanism_of_harm` have
  no Flutter reader either. They are top-level and warning shapes, outside this row pass.
- The local canary baseline (`reports/baseline_pre_e1_2_2/`, gitignored) predates both passes.
  Invariant 2a of `test_e1_2_2_preflight_invariant` will report the retired keys as mutated after
  the next canary rebuild; roll the baseline forward as that test's docstring prescribes.

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

# Follow-up: a fresh build_final_db --strict run with both passes (same 38+38
# enriched/scored dirs as the snapshot script; 15,310 products, 0 errors) passes
# the gate (exit 0):
#   active row keys undeclared:   0 []
#   inactive row keys undeclared: 0 []
# With all 26 retired row keys stripped from the shipped blobs, 15,310 of 15,310
# fresh blobs are JSON-equal to them. Every products_fts* table matches, and
# products_core differs only in detail_blob_sha256, exported_at and
# image_thumbnail_url. export_manifest and reference_data differ only in version
# and timestamp.
```
