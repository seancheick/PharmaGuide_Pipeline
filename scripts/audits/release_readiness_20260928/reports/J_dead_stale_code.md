# J. Dead, stale or confusing code (proof standard: AGENTS.md "delete once proven dead"; nothing here is asserted dead on grep alone)

| Item | Status | Proof so far | Next proof needed |
|---|---|---|---|
| `enrich_supplements_v3._derive_interaction_subject_ref` registry-fallback (ce8c38fa) | redundant defence since 7dbbf677 fixes the stamp | code read | census: 0 rows with `canonical_source_db` not holding `canonical_id` after enrichment at HEAD |
| `score_tier.dart::legacyTierForScore` | compatibility fallback with a named condition | code read | keep until no pre-2.5 cached rows |
| Core columns `_SCHEMA3_REMOVED_COLUMNS` (11) | compatibility mirrors, app reads 0 | grep lib/ | D14 decision; Supabase/other consumers NOT ESTABLISHED |
| Blob keys `v4_safety_gate`, `v4_dose_safety`, `v4_score_provenance`, `compliance_detail`, `dietary_sensitivity_detail` | produced, 1 audit read each, 0 app reads | grep | name the audit that needs them or retire per the twin discipline |
| `assessment_readiness.py` owner-scoped module set literal | duplicate of module call sites (L-7) | code read | move to one constant |
| `immune_support.py` fiber cleanse/detox and stimulant-laxative literals | Sean chose to delete in a separate measured change (07cb56a8 body); still present | commit body | measured deletion |
| `graphify-out/` | stale navigation artifact (2026-05-30) | built_at_commit | regenerate or delete |
| `scripts/audits/iqm_recalibration_20260925/RECONCILIATION.md` | referenced by b999a29b/c480dcac (reverted pair); directory absent at HEAD | ls | none (already gone) |
| `docs/archive/**`, `docs/superpowers/**` | historical by rule | AGENTS.md | none |
| `_v4_clean_label_flags` writer in scored artifact | blob export removed (4ebdd0cf); is the scored-artifact key still written and read anywhere? | not checked | grep `_v4_clean_label_flags` writers/readers |
Not swept in this pass: unused functions across the 24k-line enricher (a call-graph pass is a separate session); orphan tests; unused registries.
