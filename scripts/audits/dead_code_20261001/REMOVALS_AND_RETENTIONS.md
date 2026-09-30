# Dead-code batch 1 — removals and retentions (2026-10-01)

Branch `cleanup/dead-code-20261001`. Proof tags are those of
`scripts/audits/closure_20260921/REMOVALS_AND_RETENTIONS_20260921.md` (ZERO, TRACE, FIELD,
SUPERSEDED, RETARGETED). Candidates came from `scripts/audit_dead_code.py functions` and its `keys`
census; every item was then checked by hand: git grep per name, shell, config and skill files,
lazy imports, the Flutter `lib/`, and the other lanes' worktrees.

The fast-rung ratchet `scripts/tests/test_no_unreferenced_production_code.py` now fails on any new
unreferenced or test-only production function, and on a stale `KEEP` entry.

## Removed

| File | Removed | Proof |
|---|---|---|
| `enrich_supplements_v3.py` | `_is_negated` | RETARGETED. Production negates label statements inside `_parse_allergen_statement`; ten tests pinned the unused helper. They now run through `statements[]` (probe: 8 negated statements detect nothing; 3 positive statements detect exactly their allergens). |
| `tests/test_allergen_negation.py` | `labelStatement` inputs | Test defect: the enricher never reads `labelStatement`, so the end-to-end negation tests passed without reading the statement. Now `statements[]`. |
| `enhanced_normalizer.py` | `_process_ingredient_for_other_parallel` (193 lines) | RETARGETED. Left from the old threshold-dependent path; the one cleaning path is `_process_ingredients_sequential`, where the same guarantee is pinned. |
| `enhanced_normalizer.py` | `EnhancedDSLDNormalizer.clear_caches`, matcher `clear_cache` | ZERO (the second by fixpoint). |
| `scoring_v4/modules/probiotic_{dose,evidence,transparency}.py` | `_as_int` ×2, `_probiotic_payload`, `_safe_dict`, `_as_float` | ZERO. Local copies nothing called. |
| `export_schema.py` | `_safe_dict` | ZERO |
| `enrich_supplements_v3.py` | nested `_as_float` in `build_form_match_data` | ZERO |
| `dosage_normalizer.py` | `normalize_product` | ZERO |
| `form_vocab.py` | `matches_premium_omega3_form` | ZERO (its scorer consumer is gone); docstring updated |
| `rda_ul_calculator.py` | module `get_safety_flags`, then `RDAULCalculator.get_safety_flags` and its `SafetyFlag` | ZERO, by fixpoint. UL flags ship from the enricher's `rda_ul_data`; `identity/safety.SafetyFlag` is a different, live class. |
| `sync_to_supabase.py` | `remote_blob_storage_path` | ZERO; an unused copy of `build_final_db`'s |
| `unii_cache.py` | `lookup_for_iqm_form` (ZERO); `bulk_lookup`, `is_loaded`, `lookup_for_iqm_entry` (RETARGETED, tests pinned only them) | |
| `api_audit/pubmed_client.py` | `elink`, `epost` | ZERO; README updated |
| `identity/resolve.py` | whole file (one unused dataclass) | ZERO |
| `api_audit/discover_clinical_evidence.py` | `candidate_to_clinical_entry`, `build_key_endpoints`, `pubmed_find_pmid_for_nct` | RETARGETED. Wrote ready-to-insert clinical entries, which data doctrine forbids without per-entry review. |
| `ingest_suppai.py` | `build_known_supplement_cuis`, `enrich_curated_with_suppai`, `_agent_to_cui` | RETARGETED; the ingest CLI never called them |
| `serving_frequency.py` | `daily_use_direction_state`, `_DAILY_USE_RE`, `_CONTINGENT_USE_RE` | SUPERSEDED. Its "contingent -> minimum" consumer was tried and reverted in Task 2 (5c9996f4). |
| `scoring_v4/modules/immune_support.py` | `gummy_or_syrup` / `high_glycemic_sugar` in `_immune_design_flags`, `_has_high_glycemic_sugar` | FIELD. Computed, never read (the caller reads only `high_zinc`, `high_vitamin_d`). Found by the key census. |

## Kept (listed in `audit_dead_code.KEEP` with the reason)

| Item | Why it stays |
|---|---|
| `normalization.clear_caches`, `normalization.validate_normalized_key`, `cert_resolver.recency_for`, `identity_integrity.resolve_unambiguous`, `release_artifact_paths.*`, `grounding.ungrounded`, `evidence_resolver.resolve_evidence_for_canonical` | Test support: tests reach a live object or the live resolver (`resolve_evidence_for_row`) through them. |
| `profile_gate_evaluator.*`, `safety_alerts.applies_to`, `export_schema.resolve_warning_rule_refs` | Reference implementations the app must match (shared fixtures / Dart resolver). |
| `clinical_evidence_schema.validate_ingredient_context` | A validator no gate runs yet: a wiring decision, not dead code. |
| `submission_review/extraction/development.run_development_split` | The submission-extraction lane owns the harness. |
| `release_safety.gates.failure_summary` (with `evaluate_cleanup_gates`) | Unwired since e3e64f43 and superseded by the protected blob set, the `--expected-count` approval report and reversible quarantine. Removing the gate module is a release-chain call. |

## Follow-up batch (same branch)

| Item | Decision | Evidence |
|---|---|---|
| `api_audit/audit_v4_step10_cohorts.py` | Deleted | The v3 -> v4 cutover gate; v4 has been the production contract since 2026-06-09. |
| `tools/author_phase3_pairwise_floors.py` | Deleted | The 2026-07-02 one-off whose output is curated in `curated_interactions_v1.json`; `--apply` would overwrite it. |
| `explain_v4_product`, `verify_semantic_applicability`, `botanical_cui_resolver`, `import_upc_overrides` | Kept | Now named in `docs/runbooks/verification-gates.md`. |
| `release_safety.blob_inventory.require_complete` + `IncompleteInventoryError` | Deleted | All six inventory consumers refuse when `complete` is False; tests pin that. |
| `orphan_reconcile.total_objects_examined`, `supabase_client.storage_object_exists`, `cleanup_old_versions.list_version_directory` | Deleted | No caller; the lister was replaced by the recursive enumerator in e3e64f43. |

`audit_dead_code.py trace` on the 1,261 frozen labels: 209 functions (4,197 lines) in 99 imported
modules never entered (`~/pg_quality/deadcode_20261001/trace.json`). A review list only: dormant
guards stay.

## Score neutrality

`replay.py snapshot` of the 1,261 frozen raw labels (`~/pg_quality/cleanup_20260930/frozen`,
clean -> enrich -> score) on this branch at e1693089 is byte-identical to the baseline taken at
3b002e78 (`base_3b00.jsonl`, source hashes verified against git): `compare` reports 0 changed
products. Output: `~/pg_quality/deadcode_20261001/`.
