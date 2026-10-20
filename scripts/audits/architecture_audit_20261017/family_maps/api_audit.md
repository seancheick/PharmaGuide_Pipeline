# Family map — scripts/api_audit/ (Level 1)

Source: listing agent (sonnet, read-only, 20 tool calls) at `5fb2be1ca`. Facts here are Level-1
evidence; any line AUDIT.md relies on is re-verified against source by the main audit and cited
with its command in EVIDENCE_LEDGER.md.

72 files, 35,721 LOC. Legend: `CLI` = main guard/argparse and no importer found; `CLI+t` = CLI imported only by `scripts/tests/`; `both` = CLI also imported by non-test code; `library` = no main guard. `†` = header string placed after `from __future__ import annotations` (not a real `__doc__`). "invoked by" is a whole-word text grep over `scripts/**/*.py` (minus tests/audits), root `*.sh`, `scripts/*.sh`, `.claude/skills/**`, `docs/runbooks/**`, `.github/**`; `t:N` = test files mentioning the module. Four modules have same-named compat wrappers at `scripts/` top level (`verify_cui`, `fda_weekly_sync`, `audit_banned_recalled_accuracy`, `audit_clinical_sources`), excluded from counts. `rebuild_dashboard_snapshot.sh`, `batch_run_all_datasets.sh` and the CI workflow contain zero `api_audit` references. No file names Supabase or GitHub.

| file | LOC | kind | purpose | invoked by | external I/O | core imports |
|---|---|---|---|---|---|---|
| __init__.py | 2 | library | package marker | n/a | none | none |
| audit_alias_accuracy.py | 514 | CLI | † Alias accuracy auditor | none found | GSRS/UNII, PubChem | none |
| audit_banned_recalled_accuracy.py | 637 | CLI+t | One-command accuracy audit for banned_recalled_ingredients.json | 2: release_full.sh (release); runbook; t:2 | UMLS (via verify_cui); openFDA (subprocess fda_weekly_sync) | db_integrity_sanity_check, verify_cui |
| audit_clinical_evidence_strength.py | 159 | CLI+t | Audit claimed evidence strength vs PubMed metadata | 2: runbook; verify_interactions.py; t:1 | none | none |
| audit_clinical_sources.py | 91 | CLI+t | Audit source explicitness in backed_clinical_studies.json | none found; t:1 | none | none |
| audit_dv_plausibility.py | 271 | CLI+t | Audit FDA %DV dose plausibility in outputs | none found; t:1 | none | none |
| audit_notes_alignment.py | 774 | CLI+t | Notes alignment auditor for data files | none found; t:1 | none | none |
| audit_safety_oneliner_tone.py | 331 | CLI | Tone audit for banned_recalled one-liners | none found | none | none |
| audit_species_alignment.py | 218 | CLI | Cross-species/chemistry alias alignment audit | none found | none | none |
| audit_standardname_safety_separation.py | 473 | CLI+t | no docstring | none found; t:1 | none | identity.safety |
| audit_unii_data_quality.py | 633 | both | † UNII data-quality audit | 1: backfill_unii_from_cache.py | none | none |
| audit_unii_same_tier_conflicts.py | 638 | CLI+t | † Runtime-equivalent UNII same-tier conflicts | none found; t:3 | none | enhanced_normalizer |
| audit_v4_botanical_materiality_shadow.py | 281 | CLI+t | Shadow-audit botanical materiality thresholds | none found; t:1 | none | scoring_input_contract; sib: v4_canary_report |
| audit_v4_dose_zero.py | 223 | CLI+t | Audit v4 dose dimensions scoring zero | none found; t:1 | none | scoring_v4.router, scoring_v4.modules.{generic_dose, generic_helpers, multi_prenatal_dose, omega_dose, probiotic_dose, sports_dose} |
| audit_v4_native_classification_parity.py | 180 | CLI+t | Persisted ScoringClassification v1 parity | none found; t:1 | none | scoring_input_contract; sib: v4_canary_report |
| audit_v4_profile_consistency.py | 555 | both | Profile-consistency audit | 1: audit_v4_profile_cutover_impact.py; t:1 | none | score_supplements_v4, scoring_input_contract, scoring_v4.router, scoring_v4.modules.{botanical_profile, collagen_profile}; sib: v4_canary_report |
| audit_v4_profile_cutover_impact.py | 559 | CLI+t | Profile-selector cutover impact audit | none found; t:2 | none | score_supplements_v4, scoring_input_contract, scoring_v4.router, scoring_v4.scored_artifact, scoring_v4.modules.{botanical_profile, collagen_profile, generic_dose, generic_formulation}; sib ×2 |
| audit_v4_route_consistency.py | 346 | CLI+t | Route-consistency release gate (read-only) | none found; t:1 | none | score_supplements_v4, scoring_input_contract, scoring_v4.router; sib: v4_canary_report |
| author_probiotic_thresholds.py | 163 | CLI | Insert cfu_thresholds into clinically_relevant_strains.json | none found | none | none |
| backfill_unii_from_cache.py | 850 | CLI+t | † UNII backfill proposal + per-entry --apply | none found; t:2 | local UNII cache | dataset_paths, run_artifacts; sib: audit_unii_data_quality |
| botanical_cui_resolver.py | 204 | CLI | Botanical CUI re-resolution candidates | 1: runbook; t:1 | UMLS (via verify_cui) | env_loader, verify_cui |
| build_unii_cache.py | 140 | CLI | Build local UNII cache from openFDA bulk | none found; t:1 | openFDA bulk (urlretrieve) | none |
| cert_audit_report.py | 523 | CLI+t | Cert audit report: resolver vs canary set | 1: cert_resolver.py (mention); t:1 | local sqlite core DB | cert_resolver |
| cert_claim_provenance_audit.py | 458 | CLI+t | Cert claim provenance audit | none found; t:1 | local sqlite | cert_resolver |
| cert_label_registry_audit.py | 520 | CLI+t | Cert claim-vs-registry audit | 1: runbook; t:1 | local sqlite | cert_resolver |
| cert_needs_review_cluster.py | 578 | CLI+t | Cert needs_review cluster report | none found; t:1 | none | cert_resolver |
| cert_override_apply_rejects.py | 227 | CLI+t | Apply cluster-report reject suggestions | none found; t:1 | none | none |
| cert_override_apply_reviewed.py | 351 | CLI+t | Apply reviewed cert cluster decisions | none found; t:1 | none | none |
| discover_clinical_evidence.py | 1246 | CLI+t | Clinical evidence discovery and audit | none found; t:1 | ClinicalTrials.gov, ChEMBL | env_loader, run_artifacts |
| enrich_botanicals.py | 235 | CLI+t | Orchestrator: subprocess verify_cui/unii/pubchem | none found; t:1 | via subprocesses | none |
| enrich_chembl_bioactivity.py | 635 | CLI+t | † ChEMBL bioactivity enrichment | none found; t:1 | ChEMBL | env_loader |
| explain_v4_product.py | 84 | CLI | Explain one v4 product from its enriched blob | 1: runbook | none | score_supplements_v4, scoring_input_contract; sib: v4_canary_report |
| fda_alert_drafts.py | 322 | library | Classified FDA records → DRAFT safety alerts | 1: fda_weekly_sync.py; t:1 | none | none |
| fda_manufacturer_violations_sync.py | 1333 | both | Sync manufacturer violations from openFDA recall feeds | 3: release_full.sh (release); **enrich_supplements_v3.py (import)**; preflight.py; t:4 | openFDA, accessdata.fda.gov (via fda_weekly_sync) | run_artifacts; sib: fda_weekly_sync |
| fda_weekly_sync.py | 1424 | both | † FDA weekly sync from multiple sources | 7: skill fda-weekly-sync; run_fda_sync.sh; fda_manufacturer_violations_sync.py; t:2 | openFDA, accessdata.fda.gov, fda.gov RSS, federalregister.gov, wada-ama.org (requests.get ×5) | build_safety_alerts, env_loader; sib: fda_alert_drafts |
| generic_market_calibration_audit.py | 495 | CLI+t | v4 generic-market calibration audit | none found; t:1 | none | score_supplements_v4, scoring_v4.modules.generic_helpers; sib: v4_canary_report |
| ingest_caers.py | 503 | CLI+t | FDA CAERS adverse-event aggregator | 2: dashboard views (hint strings); t:2 | openFDA CAERS bulk (cached zip) | run_artifacts |
| iqm_identifier_sweep.py | 1589 | CLI+t | IQM identifier sweep: content verification of canonical_ids | none found; t:2 | UMLS, RxNorm, PubChem, GSRS (sibling clients + own urlopen) | env_loader; sib: verify_cui, verify_interactions, verify_pubchem, verify_unii |
| mine_drug_label_interactions.py | 329 | CLI | Extract interaction mentions from FDA SPL labels | none found | openFDA drug-label bulk (local) | none |
| normalize_clinical_pubmed.py | 278 | both | Normalize PubMed references in backed_clinical_studies.json | 2: **iqm_form_evidence.py (import)**; verify_pubmed_references.py; t:1 | PubMed (via pubmed_client) | sib: pubmed_client |
| probiotic_batch_verify.py | 298 | CLI | One-shot PubMed dose-anchor lookup for probiotic strains | 1: author_probiotic_thresholds.py (mention) | PubMed | sib: pubmed_client |
| pubmed_client.py | 505 | library | Shared PubMed/NCBI E-utilities client | 11: **iqm_form_evidence.py (import)**; verify_all_citations_content; verify_interactions; t:3 | PubMed/NCBI; JSON disk cache | env_loader; sib: pubmed_xml, system_trust_http |
| pubmed_xml.py | 83 | library | Stdlib PubMed XML helpers | 4; t:1 | none | none |
| review_evidence_derivation.py | 150 | CLI+t | Preview evidence-strength derivation | 1 (mention); t:1 | none | sib: verify_interactions |
| seed_drug_classes.py | 501 | CLI | Seed drug_classes.json via RxClass | none found; t:1 | RxNorm/RxClass | none |
| system_trust_http.py | 88 | library | HTTPS fallback via system trust store (curl subprocess) | 1: pubmed_client.py; t:1 | generic HTTPS | none |
| v4_canary_report.py | 473 | both | v4 canary comparator vs v3 shipped baseline | 7 siblings; t:1 | none | score_supplements_v4 |
| valyu_domain_targets.py | 167 | library | no docstring | 1: valyu_evidence_discovery.py; t:1 | local JSON | none |
| valyu_evidence_discovery.py | 216 | CLI | Review-only Valyu evidence watchtower | none found; t:1 | Valyu API (SDK) | env_loader; sib ×4 |
| valyu_query_planner.py | 46 | library | no docstring | 1; t:1 | none | none |
| valyu_report_types.py | 49 | library | no docstring | 1; t:1 | none | none |
| valyu_report_writer.py | 82 | library | no docstring | 1; t:1 | local write | none |
| verify_all_citations_content.py | 785 | both | Content-verify every PubMed citation across data files | 8: release_full.sh, test.sh, skills data-fix/verify-data, 3 siblings; t:6 | PubMed (via pubmed_client), Crossref | data_batch, env_loader; sib: pubmed_client, pubmed_xml |
| verify_backed_studies_citations.py | 353 | CLI+t | Content-verify citations in backed_clinical_studies.json | 3: release_full.sh, test.sh, sibling; t:2 | PubMed (via verify_all_citations_content) | identity_integrity; sib |
| verify_botanical_composition.py | 521 | CLI | Botanical composition reference builder/validator | none found; t:1 | USDA FDC, PubMed (requests.get ×2 + pubmed_client) | env_loader; sib: pubmed_client, pubmed_xml |
| verify_certifications.py | 1630 | CLI+t | Cert registry fetcher; stages reviewed-refresh candidates | 1: runbook; t:9 | NSF Sport, NSF 173, Nutrasource, BSCG, ConsumerLab, WeTestYouTrust, quality-supplements.org (requests.get ×8, Session L1109) | cert_resolver |
| verify_clinical_trials.py | 606 | CLI+t | † ClinicalTrials.gov verification | 2: skill verify-data; runbook; t:1 | ClinicalTrials.gov; PubMed | env_loader; sib: pubmed_client |
| verify_comptox.py | 902 | CLI | † EPA CompTox verification/enrichment | none found | CompTox | env_loader |
| verify_cui.py | 895 | both | UMLS CUI verification and lookup | 11: skills data-fix/fda-weekly-sync/verify-data; 4 siblings; t:6 | UMLS | env_loader |
| verify_depletion_timing_citation_content.py | 310 | CLI+t | Fail-closed content gate for depletion citations | 2: release_full.sh, test.sh; t:2 | PubMed | sib: pubmed_client |
| verify_depletion_timing_pmids.py | 277 | CLI+t | Verify PMIDs in timing_rules.json / medication_depletions.json | 3: skill verify-data, release_full.sh, test.sh; t:1 | PubMed | env_loader; sib: pubmed_client |
| verify_drug_class_rxcuis.py | 105 | both | Live RxNorm audit of drug_classes.json rxcuis | 4: release_full.sh, test.sh, sibling import, runbook; t:2 | RxNorm (urlopen L37) | none |
| verify_efsa.py | 584 | CLI+t | † EFSA OpenFoodTox validation (local CSV) | 1: runbook; t:1 | none (local CSV) | none |
| verify_interaction_rules_citations.py | 417 | CLI+t | Content-verify citations in ingredient_interaction_rules.json | 4: release_full.sh, test.sh, skills; t:4 | PubMed/Bookshelf (via verify_all_citations_content) | data_batch; sib |
| verify_interactions.py | 1694 | both | Verify and normalize curated interaction drafts before DB build | 7: rebuild_interaction_db.sh; **build_interaction_db.py (import)**; skills catalog-release/verify-data; 2 siblings; t:11 | RxNorm, PubMed (via pubmed_client), UMLS (via verify_cui) | profile_gate_evaluator, verify_cui; sib: pubmed_client (lazy) |
| verify_literature_records.py | 284 | CLI | Verification pipeline for literature_evidence_records.json | none found; t:1 | PubMed (via verify_all_citations_content) | sib ×2 |
| verify_medication_depletion_identifiers.py | 141 | CLI+t | Live identity gate for medication_depletions.json | 2: release_full.sh, test.sh; t:1 | RxNorm (via verify_drug_class_rxcuis) | sib |
| verify_pubchem.py | 1129 | both | † PubChem PUG REST verification/enrichment | 6: skills data-fix/verify-data; iqm_identifier_sweep (import); verify_unii; enrich_botanicals; t:1 | PubChem | none |
| verify_pubmed_references.py | 182 | CLI+t | Verify/enrich DOI/PMID references | none found; t:3 | PubMed | sib: pubmed_client, normalize_clinical_pubmed |
| verify_rda_uls.py | 1137 | CLI | RDA/AI/UL verification for rda_optimal_uls.json | 3: skill verify-data; runbook; verify_all_citations_content | USDA FDC, NAP | env_loader |
| verify_semantic_applicability.py | 184 | CLI | Semantic applicability gate for literature_evidence_records.json | 1: runbook | none | none |
| verify_unii.py | 1555 | both | † FDA GSRS/UNII verification/enrichment | 6: skills data-fix/verify-data; iqm_identifier_sweep (import); build_unii_cache; enrich_botanicals; runbook; t:3 | GSRS/UNII | sib: verify_pubchem |

## Families

1. **Verifier CLIs with a per-file HTTP client class plus disk cache** (`__init__(cache_path…)`, `_cache_get`, `_cache_set`, `save_cache`, circuit-breaker, `_get`/`get`): `verify_cui` (UMLSClient), `verify_unii` (GSRSClient), `verify_pubchem` (PubChemClient), `verify_comptox` (CompToxClient), `verify_clinical_trials` (ClinicalTrialsClient), `enrich_chembl_bioactivity` (ChEMBLClient), `discover_clinical_evidence` (APIClient).
2. **PubMed stack**: shared `pubmed_client` + `pubmed_xml` + `system_trust_http`; direct consumers `verify_all_citations_content`, `verify_pubmed_references`, `normalize_clinical_pubmed`, `verify_depletion_timing_pmids`, `verify_depletion_timing_citation_content`, `verify_botanical_composition`, `probiotic_batch_verify`, `verify_clinical_trials`, `verify_interactions` (PubMedValidator); second hop via `verify_all_citations_content`: `verify_backed_studies_citations`, `verify_interaction_rules_citations`, `verify_literature_records`.
3. **RxNorm/RxClass stdlib-urllib verifiers**: `verify_drug_class_rxcuis`, `verify_medication_depletion_identifiers`, `seed_drug_classes`, RxNormClient inside `verify_interactions`.
4. **Release-chain live gates** (`release_full.sh` and/or `scripts/test.sh`): `verify_drug_class_rxcuis`, `verify_medication_depletion_identifiers`, `verify_depletion_timing_pmids`, `verify_depletion_timing_citation_content`, `verify_backed_studies_citations`, `verify_interaction_rules_citations`, `verify_all_citations_content`; `release_full.sh` alone also calls `audit_banned_recalled_accuracy` and `fda_manufacturer_violations_sync`; `rebuild_interaction_db.sh` calls `verify_interactions`.
5. **v4 scoring audit reports (read-only, local artifacts)**: `audit_v4_*` ×6, `v4_canary_report`, `explain_v4_product`, `generic_market_calibration_audit`; seven import the sibling `v4_canary_report`.
6. **Certification family**: `verify_certifications` (fetcher); `cert_audit_report`, `cert_claim_provenance_audit`, `cert_label_registry_audit`, `cert_needs_review_cluster` (reports; four import `cert_resolver`, three read the core DB); `cert_override_apply_rejects`, `cert_override_apply_reviewed` (appliers).
7. **Identifier / UNII / CUI tooling**: `verify_unii`, `verify_pubchem`, `verify_cui`, `build_unii_cache`, `backfill_unii_from_cache`, `audit_unii_data_quality`, `audit_unii_same_tier_conflicts`, `botanical_cui_resolver`, `iqm_identifier_sweep`, `enrich_botanicals`.
8. **FDA regulatory and bulk ingest**: `fda_weekly_sync`, `fda_manufacturer_violations_sync`, `fda_alert_drafts`, `ingest_caers`, `mine_drug_label_interactions`, `audit_banned_recalled_accuracy`.
9. **Local reference-data audits, no network**: `audit_notes_alignment`, `audit_species_alignment`, `audit_safety_oneliner_tone`, `audit_dv_plausibility`, `audit_clinical_sources`, `audit_clinical_evidence_strength`, `audit_standardname_safety_separation`, `verify_semantic_applicability`, `review_evidence_derivation` (+ `audit_alias_accuracy`, same kind but live).
10. **Valyu watchtower**: `valyu_evidence_discovery` + 4 helpers (all helpers without docstrings).
11. **Standalone reference verifiers**: `verify_rda_uls`, `verify_botanical_composition`, `verify_efsa`.
12. **One-off authoring/backfill**: `author_probiotic_thresholds`, `probiotic_batch_verify`, `seed_drug_classes`, `build_unii_cache`, `backfill_unii_from_cache`.

## Level-2 candidates (agent's list; promotion decided by census criteria)

- >800 LOC: `verify_interactions` 1694, `verify_certifications` 1630, `iqm_identifier_sweep` 1589, `verify_unii` 1555, `fda_weekly_sync` 1424, `fda_manufacturer_violations_sync` 1333, `discover_clinical_evidence` 1246, `verify_rda_uls` 1137, `verify_pubchem` 1129, `verify_comptox` 902, `verify_cui` 895, `backfill_unii_from_cache` 850.
- Release-chain/skill references: `fda_manufacturer_violations_sync` (release_full.sh:223 `--check`; also imported by production `enrich_supplements_v3.py`), `audit_banned_recalled_accuracy` (release_full.sh:670), `verify_drug_class_rxcuis` (release_full.sh:638, test.sh:389), `verify_medication_depletion_identifiers` (:640 / :390), `verify_depletion_timing_pmids` (:642 / :391, skill verify-data), `verify_depletion_timing_citation_content` (:644 / :395), `verify_backed_studies_citations` (:650 / :403), `verify_interaction_rules_citations` (:655 / :406, skills), `verify_all_citations_content` (:660 / :409, skills), `verify_interactions` (skills catalog-release/verify-data; rebuild_interaction_db.sh:133; production `build_interaction_db.py`), `fda_weekly_sync` (skill; run_fda_sync.sh:74), `verify_cui`/`verify_pubchem`/`verify_unii`/`verify_clinical_trials`/`verify_rda_uls` (skills).
- **Reverse direction — production importing api_audit**: `enrich_supplements_v3.py` imports `fda_manufacturer_violations_sync`; `iqm_form_evidence.py` imports `pubmed_client` and `normalize_clinical_pubmed`; `build_interaction_db.py` imports `verify_interactions`; `preflight.py` mentions `fda_manufacturer_violations_sync`; `cert_resolver.py` mentions `cert_audit_report`.

## Duplicate HTTP, cache and `_get` patterns

- `_cache_get` defined in 8 files: `verify_cui` (UMLSClient L162; `_cache_get` L193, `_cache_set` L213, `_get` L226), `verify_unii` (GSRSClient L329; L356/L371/L386), `verify_pubchem` (PubChemClient L222; L249/L264/L279), `verify_comptox` (CompToxClient L83; L117/L132/L147), `verify_clinical_trials` (ClinicalTrialsClient L89; L120/L135/L150), `enrich_chembl_bioactivity` (ChEMBLClient L105; L132/L147/L162), `discover_clinical_evidence` (APIClient L213; `_cache_get` L228, `_cache_set` L243, public `get` L256), `pubmed_client` (PubMedClient L191; `_cache_get` L267, `_cache_put` L276, `_request` L289). The `enrich_chembl_bioactivity` and `discover_clinical_evidence` bodies are visually identical TTL-expiry JSON caches; the other copies were not diffed by the agent.
- `_cache_set` in 7 files; `_get` in 7 (six class methods + module-level `verify_all_citations_content.py` L261 delegating to `PubMedClient._request`; `verify_interaction_rules_citations.py` `_get_json` L267 delegates to it).
- Session/cache `__init__` without the trio: `verify_interactions.py` RxNormClient L364 (in-memory `_cache`) and PubMedValidator L422 (`_fetch_cache`); `verify_certifications.py` `requests.Session()` at L1109.
- Module-level HTTP helpers: `seed_drug_classes.http_get_json` L84; `audit_alias_accuracy._api_get_json` L66 / `_requests_get_json` L76; `fda_weekly_sync` requests.get ×5; `verify_botanical_composition` ×2; `verify_rda_uls` urlopen L927; `verify_drug_class_rxcuis` urlopen L37; `iqm_identifier_sweep` urlopen L112/L116 with `ssl.create_default_context` L110; `build_unii_cache` urlretrieve.
- SSL-context helper copies: `verify_cui._make_ssl_ctx` L67, `verify_pubchem` L198, `verify_unii` L307, `verify_interactions` L354, `seed_drug_classes` L64 + `_ssl_ctx` L77, `audit_alias_accuracy._get_ssl_ctx` L59; `system_trust_http` is a separate curl-based fallback used by `pubmed_client`.
- HTTP library split: `requests` in 7 files, `urllib` in 9, both in `audit_alias_accuracy`; `pubmed_client` has its own `_request` with curl fallback.
