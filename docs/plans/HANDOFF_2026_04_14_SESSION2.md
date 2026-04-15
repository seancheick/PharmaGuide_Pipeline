# Agent Handoff — 2026-04-14 Session 2

## SESSION SUMMARY

**Goal:** Sprint 23b + 24 execution, data file standardization, synergy evidence audit, pipeline cleanup
**Commits:** 14 (from `8d61417` to `391fd76`)
**Duration:** Single session, continuation of Sprint 23a work

## COMPLETED

### Sprint 23b: UNII Local Cache
- Downloaded 172K FDA UNII substance registry (3.4 MB)
- Built `scripts/unii_cache.py` — `UniiCache` class with local-first lookup + GSRS API fallback
- Built `scripts/api_audit/build_unii_cache.py` — cache generator
- 23 tests in `test_unii_cache.py`

### Sprint 24: Drug Label Interaction Mining
- Downloaded 3/13 FDA drug label partitions (57K labels)
- Built `scripts/api_audit/mine_drug_label_interactions.py` — scans SPL text for supplement mentions
- Found 40 supplements in drug labels, 36 already covered (90%)
- 4 new candidates: fish_oil_omega3, cbd, ginkgo (alias), grape_seed_extract (false positive)

### Interaction Rules (127 → 129)
- **fish_oil**: bleeding risk with anticoagulants/antiplatelets, surgery scheduling, >3g/day dose threshold
- **CBD (BANNED_CBD_US)**: liver toxicity with valproate, immunosuppressant level increases (tacrolimus/sirolimus), CYP3A4/2C19 inhibition, pregnancy avoidance

### IQM Identifier Standardization
- **Hierarchy established** per NIH/FDA/NLM standards:
  - Parent level: `cui` (concept), `rxcui` (drug mapping), `external_ids.unii` (representative)
  - Form level: `forms[name].external_ids.unii` (chemical substance identity)
- 165 forms now have form-specific UNIIs (135 different from parent — proving forms are distinct substances)
- Moved 4 top-level `cas` → `external_ids.cas`, 3 `pubchem_cid` → `external_ids.pubchem_cid`
- Removed 665 null/orphaned fields from IQM
- Decoupled 15 duplicated form names, resolved 4 UNII conflicts
- 3 dual-nutrient forms get `cross_ref` (dicalcium phosphate, magnesium ascorbate, magnesium taurate)
- 11 new guardrail tests in `TestIdentifierStandardization`

### All 6 Data Files Standardized
| File | Entries | Changes |
|------|---------|---------|
| ingredient_quality_map.json | 588 | CUI→cui done earlier, nulls cleaned, 665 orphaned fields removed, form UNIIs added |
| harmful_additives.json | 115 | 2 missing external_ids fixed, 12 UNIIs filled, mechanism + confidence filled |
| banned_recalled_ingredients.json | 143 | 43 missing external_ids fixed, 17 UNIIs filled |
| botanical_ingredients.json | 433 | CUI→cui (421), 132 nulls removed, 5 external_ids added, 26 UNIIs filled |
| standardized_botanicals.json | 239 | CUI→cui (205), 1192 nulls removed, 21 UNIIs filled, 21 stubs marked |
| other_ingredients.json | 662 | CUI→cui (424), 886 nulls removed, 26 UNIIs filled, PEG wrong UNII caught |

### Synergy Cluster Overhaul
- **Reclassified all 58 clusters** using PMC10600480 systematic review + PubMed verification:
  - Tier 1 (PROVEN): 2 (curcumin+piperine, iron+vitamin C)
  - Tier 2 (SUPPORTED): 7 (AREDS2, B12+folate+B6, bone, prenatal, omega-3+niacin, dental, wound)
  - Tier 3 (PROMISING): 11 (sleep stack, Mg+B6, glucosamine+chondroitin, etc.)
  - Tier 4 (POPULAR): 38 (no combo evidence, each works individually)
- **Tiered scoring**: A5c bonus now 1.0/0.75/0.5/0.25 based on evidence tier
- **canonical_ids** added to all 58 clusters (92% ingredient mapping rate)
- **evidence_note** on every cluster explaining why it gets its tier
- **7 verified PMIDs** added to proven clusters
- **1 new cluster**: omega-3 + niacin (from PMC10600480)
- **Enricher** passes evidence_tier, evidence_label, synergy_mechanism, PMIDs
- **build_final_db** exports `synergy_detail` blob with bonus_explanation for Flutter

### Clinical Studies Cleanup
- **45 hallucinated ClinicalTrials.gov refs removed** (wrong studies — "Nexavar" for Niacin, etc.)
- **47 PMIDs extracted from key_endpoints text**, verified via PubMed API
- **6 new PMIDs added** for berberine, saw palmetto, grape seed extract
- **1 bad PMID caught**: 38341968 (wastewater treatment, not B. longum)
- Entries without PMIDs: 21 → 4 (minerals with fact sheets only)

### Pipeline Maintenance Schedule
- `PIPELINE_MAINTENANCE_SCHEDULE.md` — 24 tasks documented
- Weekly, monthly, quarterly, pre-release, post-release sections
- "What to do with results" for every task
- Full copy-paste maintenance cycle checklist
- Claude Code friendly — agent can run autonomously from file

## PIPELINE STATE

All data files are now clean:
- **Zero** top-level `unii`, `cas`, `pubchem_cid` leaks
- **Zero** null-valued fields (absent instead of null)
- **All** entries have `external_ids` dict and `aliases` list
- **All** CUI fields lowercase `cui`
- **165** IQM forms have chemical-identity UNIIs
- **129** interaction rules
- **58** synergy clusters with honest evidence tiers
- **444** PMIDs in clinical studies (verified)

## WHAT TO DO NEXT

### Before running the pipeline:
1. **Fix the 3 pre-existing test failures** — IQM alias duplicates (9 cross-ingredient dupes from Sprint 22 expansion) + absorption_quality validation. These should be fixed so the pipeline run starts from a clean test baseline.
2. **Enrich 21 branded botanical stubs** — Chromax, Cognizin, EpiCor, Wellmune etc. need real markers for A5b. Use manufacturer datasheets or Examine.com.

### Pipeline run:
3. **Re-run full pipeline** on fresh dataset to measure score impact of:
   - B8 CAERS penalties (strong -4, moderate -2, weak -1)
   - Tiered synergy bonus (was flat 1.0, now 0.25-1.0)
   - Context-aware harmful additive scoring
   - All the data file improvements
4. **Shadow score comparison** against previous baseline
5. **Coverage gate** — verify ≥99.5%

### Flutter:
6. Wire `TimingAdviceCard` into stack screen (widget built, not rendered)
7. Depletion Checker UI (data ready, UI not built)
8. Offline drug→class SQLite cache for offline med adds

## KEY DECISIONS

1. **IQM identifier hierarchy follows NIH/FDA/NLM standards**: CUI = parent concept (UMLS), RXCUI = parent drug mapping (RxNorm), UNII = form-specific chemical identity (FDA GSRS). CUI and RXCUI stay at parent level, UNII goes on both parent (representative) and forms (chemical-specific).

2. **Synergy tiers are evidence-based, not marketing-based**: Only 2 of 58 clusters have PROVEN synergy (>additive combo RCT). 38 are popular combinations with no combo evidence. The old system gave all of them Tier 1 — the new system is honest.

3. **Null = absent, not present-with-null**: Every data file follows this convention now. Scripts use `.get()` with defaults, so behavior is identical, but JSON is cleaner and no null-check bugs possible.

4. **PEG UNII lesson**: Automated UNII filling matched "Polyethylene Glycol" to ethylene glycol's UNII (FC72KVT52F) because "glycol" is a substring match. The existing test caught it. Chemical identifier automation ALWAYS needs test guardrails.

## COMMITS (14)

| Hash | Description |
|------|-------------|
| `28f3da1` | Sprint 23b (UNII cache) + Sprint 24 (drug label mining) |
| `3804cbc` | Pipeline maintenance schedule + fish_oil & CBD rules |
| `6d57ef8` | Maintenance schedule v2 (24 tasks) |
| `2a054fa` | Standardize external_ids across IQM + harmful + banned |
| `cb5103d` | Form-level UNII migration |
| `043ee24` | Decouple forms, fix UNII conflicts |
| `7a4ba89` | IQM cleanup — 665 null/orphaned fields |
| `bc23c95` | Test alignment + 11 identifier enforcement tests |
| `636c6a1` | Clinical studies — 45 hallucinated refs replaced |
| `239bfe3` | Synergy canonical_ids (92% mapping) |
| `3bebc80` | Synergy evidence reclassification |
| `111c27c` | Tiered synergy scoring + evidence export |
| `dbcef03` | Botanical files CUI→cui standardization |
| `391fd76` | other_ingredients standardization + botanical audit |

## ENVIRONMENT

- Pipeline repo: `/Users/seancheick/Downloads/dsld_clean` → `github.com/seancheick/PharmaGuide_Pipeline`
- Flutter repo: `/Users/seancheick/PharmaGuide ai` → `github.com/seancheick/Pharmaguide.ai`
- Python: 3.9 (system) — 41 test files need 3.13 for `datetime.UTC`
- UNII cache: gitignored (14.9 MB) — rebuild via `build_unii_cache.py`
- CAERS data: gitignored (99 MB) — rebuild via `ingest_caers.py`
- Drug labels: gitignored (600 MB+) — download from OpenFDA
