# I. Schema and field report

| Field / family | Layer | Status | Evidence |
|---|---|---|---|
| `quality_score_v4_100`, `quality_score_status`, `quality_pillars_v4`, `quality_tier`, `quality_assessment_status`, `product_safety_status`, `verdict` | scored → core/blob → app | CURRENT, one owner (`scored_artifact.py`) | C, H |
| `score_100_equivalent`, `score_display_100_equivalent` | core 2.5.0 | COMPATIBILITY_ALIAS (app 0 reads; schema 3 removes) | `_SCHEMA3_REMOVED_COLUMNS`; D14 |
| v3 subscores `score_ingredient_quality*`, `score_safety_purity*`, `score_evidence_research*`, `score_brand_trust*`, `v4_confidence` | core 2.5.0 | DEAD for the app (0 reads), removed in schema 3 | same |
| `evidence_result_state` | scored pillar | **drifts by route**: emitted by generic/sports/fiber/probiotic/omega; `null` for multi/prenatal and B-complex (RR-11) | HEAD census |
| `form_source` (`row_notes`, `product_label_disclosure`, …) | enriched row | CURRENT provenance value; not exported on the blob row (blob rows carry `matched_form`, `form_match_status`, `label_display_form`) → provenance stops at the enriched layer | probe blob rows |
| `matched_form` / `form_id` / `matched_forms[]` / `final_form_bio_score` / `bio_score` | enriched row | one owner (matcher) with several projections; `bio_score` is the only quality value (c3afa98b); `score`/`natural` retired | T1 |
| `dailyValue` | cleaned/enriched row | NEW in window (11446221), declared | row-shape gate |
| `serving_basis` vs `servingSizes` | enriched | owner `serving_basis`; export no longer re-derives (4ebdd0cf) | T1 |
| `per_day_min` / `per_day_max` / `exposure.benchmark` | enricher vs scoring_v4/exposure.py | two readings of one label fact (RR-03) | G/L |
| `ingredient_assessment_complete` | safety gate | written, never read (RR-08) | grep |
| `display_ingredients[]` with no active/inactive counterpart (Chloride, Header rows) | cleaned | rows with no disposition reason (RR-09/10) | D.3 |
| `_v4_clean_label_flags` / `clean_label_flags_v4` | scored/blob | removed from blob in window (4ebdd0cf); app reads: 0 | grep |
| Blob audit families (34 keys) | blob | produced for audits/dashboard, not the app | H |
| `key_ingredient_tags`, `ingredient_fingerprint` | core | CURRENT (app 18/13 reads); fingerprint now carries family/twin ids | 01213079 |
| IQM `unknown_floor`, `parent_relationship`, `source_form_aliases`, `form_evidence` | data | CURRENT owners (56314f5c, a7065751, a7351548, 7dbd1447) | data |
| `quality_score.json` sections | config | CURRENT; version 1.21.3 at HEAD, 11 window commits | F |
Not examined in this pass: Supabase table columns vs core (sync script), `reference_data` table, FTS config.
