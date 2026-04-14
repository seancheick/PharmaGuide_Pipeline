# Interaction Enhancement Plan — Session Handoff

## Goal
Fix 3 critical bugs that make 128 curated interactions silently not fire, then enhance the matching engine for generic/brand resolution, combination drugs, and expanded coverage.

## Critical Bugs to Fix

### B1: canonical_id NULL in interaction DB (Pipeline)
- File: `scripts/build_interaction_db.py`
- Problem: `agent1_canonical_id` / `agent2_canonical_id` copied from JSON source, but source doesn't have them → all NULL
- Fix: For supplement agents, map `agent_id` (CUI like "C0042878") → canonical IQM key (like "vitamin_k") using IQM + botanical lookup tables. For drug agents, canonical_id stays null (drugs match via rxcui/class).
- Impact: Unblocks `lookupByCanonicalId` in Flutter — the primary supplement matching path

### B2: _canonicalIdsForProduct returns wrong keys (Flutter)
- File: `/Users/seancheick/PharmaGuide ai/lib/features/stack/providers/stack_providers.dart` line 602
- Problem: Reads `ingredient_fingerprint` top-level keys → returns `["nutrients", "herbs", "categories", "pharmacological_flags"]` for EVERY product
- Fix: Replace with `key_ingredient_tags` parsing (same as `_ingredientTagsForProduct` built for timing feature)
- Impact: Unblocks supplement×supplement, medication×supplement, synergy, AND recall matching
- Also fix: `_extractCanonicalIds` in `product_detail_screen.dart` (line 176) — same bug

### B3: No brand→generic RXCUI normalization (Flutter)
- File: `/Users/seancheick/PharmaGuide ai/lib/services/medications/rxnorm_api_service.dart`
- Problem: "Synthroid" stores brand rxcui (224920), but curated DB has levothyroxine rxcui (10582) → no match
- Fix: After user selects medication, call `GET /REST/rxcui/{rxcui}/related.json?tty=IN` to get generic ingredient RXCUI. Store both in user_stack.
- API endpoints (verified live against NLM production):
  - Brand→generic: `GET /REST/rxcui/{brand_rxcui}/related.json?tty=IN`
  - Properties/TTY: `GET /REST/rxcui/{rxcui}/properties.json`
  - Combination ingredients: `GET /REST/rxcui/{rxcui}/allrelated.json` → filter tty=IN
- Impact: Synthroid/Coumadin/all brand names will match their generic interaction entries

## Task Breakdown

### Layer 1: Fix the Plumbing (Critical — Session 1)

T1: Pipeline — populate canonical_id in build_interaction_db.py
  - Build CUI→canonical_id mapping from IQM (571 entries have CUI) + botanical_ingredients + standardized_botanicals
  - In build_interaction_db.py, when processing supplement agents, look up agent_id (CUI) in the mapping
  - Write canonical_id into the interaction row
  - Rebuild interaction_db.sqlite, verify non-null canonical_ids
  - Files: scripts/build_interaction_db.py

T2: Flutter — fix _canonicalIdsForProduct
  - Replace fingerprint key decoding with key_ingredient_tags JSON parsing
  - Use same pattern as _ingredientTagsForProduct (already built for timing)
  - Return Set<String> of actual canonical IDs like {"iron", "calcium", "vitamin_d"}
  - Also fix _extractCanonicalIds in product_detail_screen.dart
  - Files: stack_providers.dart, product_detail_screen.dart

T3: Flutter — add brand→generic RXCUI normalization
  - In RxNormApiService, add resolveGenericRxcui(String rxcui) method
  - Call GET /REST/rxcui/{rxcui}/properties.json → check tty
  - If tty != "IN", call GET /REST/rxcui/{rxcui}/related.json?tty=IN → get generic rxcui
  - Add generic_rxcui column to user_stacks_local table
  - In medication_entry_screen.dart, resolve and store generic_rxcui on save
  - In stack_interaction_checker.dart, lookupByRxcui with BOTH rxcuis
  - Files: rxnorm_api_service.dart, medication_entry_screen.dart, stack_interaction_checker.dart, user_database.dart

T4: Pipeline — add canonical_id fields to curated interaction JSON
  - For each supplement agent in curated_interactions_v1.json, map CUI → canonical_id
  - Use IQM CUI lookup: "C0042878" → "vitamin_k", "C0007320" → "calcium", etc.
  - Verify each mapping via API (verify_cui.py)
  - Files: curated_interactions_v1.json, med_med_pairs_v1.json

### Layer 2: Enhance Matching (Session 2)

T5: Flutter — dual-path rxcui matching in StackInteractionChecker
  - checkMedicationInteractions: try both rxcui AND generic_rxcui
  - Add class-based fallback: if rxcui lookup finds nothing, try drug_classes
  - Files: stack_interaction_checker.dart

T6: Flutter — combination drug ingredient decomposition
  - Add getIngredients(rxcui) to RxNormApiService
  - Call GET /REST/rxcui/{rxcui}/allrelated.json → filter tty=IN
  - Store ingredient_rxcuis JSON array in user_stack
  - Match each ingredient independently
  - Files: rxnorm_api_service.dart, medication_entry_screen.dart, stack_interaction_checker.dart

T7: Flutter — add MOA class source for broader class matching
  - In getClasses(), also fetch relaSource=MEDRT classes (MOA, EPC)
  - "All serotonin reuptake inhibitors" matches any SSRI the user adds
  - Files: rxnorm_api_service.dart

### Layer 3: Expand Coverage (Session 3)

T8: Pipeline — add missing supplement-supplement interactions (15-20 new entries)
  - Fish Oil + Vitamin E (additive antiplatelet)
  - Fish Oil + Ginkgo (additive bleeding risk)
  - Melatonin + Valerian (additive sedation)
  - Calcium + Fluoroquinolones (chelation)
  - Iron + PPIs (acid reduction impairs absorption)
  - Magnesium + Bisphosphonates (chelation)
  - Ginkgo + Antiplatelet drugs
  - All entries must have verified PMIDs via api_audit scripts

T9: Flutter — offline drug→class cache
  - Cache rxcui→classes mapping in SQLite on successful API call
  - On offline med add with known rxcui, check cache for classes
  - Files: rxnorm_api_service.dart, user_database.dart

T10: Pipeline — verify and fix remaining interaction PMIDs
  - Run verify_all_citations_content.py on curated_interactions files
  - Replace any content-mismatched PMIDs

## Key Files

Pipeline:
- scripts/build_interaction_db.py — builds interaction_db.sqlite
- scripts/data/curated_interactions/curated_interactions_v1.json — 99 entries
- scripts/data/curated_interactions/med_med_pairs_v1.json — 29 entries
- scripts/data/ingredient_quality_map.json — CUI→canonical_id mapping source

Flutter:
- lib/features/stack/providers/stack_providers.dart — provider wiring
- lib/services/stack/stack_interaction_checker.dart — matching engine
- lib/data/database/interaction_database.dart — SQLite queries
- lib/services/medications/rxnorm_api_service.dart — RxNorm API
- lib/features/medications/medication_entry_screen.dart — med entry UI
- lib/data/database/user_database.dart — user stack schema

## Current DB Stats
- 128 curated interactions in interaction_db.sqlite
- 99 in curated_interactions_v1.json (86 Med-Sup, 7 Sup-Sup, 5 Med-Food)
- 29 in med_med_pairs_v1.json (26 Med-Med, 3 other)
- 571 IQM parents with CUI fields for canonical_id mapping

## API Endpoints (verified live)
- Brand→generic: GET /REST/rxcui/{rxcui}/related.json?tty=IN
- Drug properties: GET /REST/rxcui/{rxcui}/properties.json
- Drug classes: GET /REST/rxclass/class/byRxcui.json?rxcui={rxcui}&relaSource=ATC
- MOA classes: GET /REST/rxclass/class/byRxcui.json?rxcui={rxcui}&relaSource=MEDRT
- Combination ingredients: GET /REST/rxcui/{rxcui}/allrelated.json → filter tty=IN
- Autocomplete: GET /REST/approximateTerm.json?term={text}

## Next Action
Start with T2 (fix _canonicalIdsForProduct in Flutter) — fastest win, broadest impact.
Then T1+T4 (pipeline canonical_id population) — requires CUI→canonical mapping.
Then T3 (brand→generic normalization) — requires user_database schema change.

---

## SESSION 2 PROGRESS (2026-04-14)

### Layer 2 COMPLETE — All T5-T7 done

T5: Dual-path rxcui matching + class fallback ✅
  - checkMedicationPairInteractions now tries brand rxcui, generic rxcui, 
    ingredient rxcuis, AND class-based fallback
  - 0 analyze issues

T6: Combination drug decomposition ✅
  - Covered by T3's resolveGenericRxcuis() — returns multiple IN-level
    rxcuis for combination drugs
  - ingredient_rxcuis stored in user_stack, indexed in checker

T7: MOA/MEDRT class source ✅
  - getClasses() now fetches BOTH ATC and MEDRT sources in parallel
  - "All SSRIs" (MOA class) will match any specific SSRI the user adds
  - 0 analyze issues

### Layer 3 IN PROGRESS

T8: PMID research agent running — finding verified PMIDs for 10 new 
    supplement-supplement interactions

### All Tests Passing
- Flutter: 20/20 timing tests
- Pipeline: 151/151 interaction tests
- Flutter analyze: 0 issues across all changed files

### Files Modified This Session (Layer 2)
Flutter:
- lib/services/stack/stack_interaction_checker.dart — dual-path + class fallback
- lib/services/medications/rxnorm_api_service.dart — MOA/MEDRT classes + resolveGenericRxcuis
- lib/features/medications/medication_entry_screen.dart — generic resolution on selection
- lib/features/stack/providers/stack_providers.dart — _canonicalIdsForProduct fix + addMedication params
- lib/features/product_detail/product_detail_screen.dart — _extractCanonicalIds fix
- lib/data/database/tables/user_stacks_table.dart — 2 new columns
- lib/data/database/user_database.dart — v2 migration
- assets/db/interaction_db.sqlite — rebuilt with canonical_ids

Pipeline:
- scripts/data/curated_interactions/curated_interactions_v1.json — canonical_ids
- scripts/data/curated_interactions/med_med_pairs_v1.json — canonical_ids
- scripts/dist/interaction_db.sqlite — rebuilt

### Next Action
Wait for PMID agent to complete, then add the 10 new curated interactions
to curated_interactions_v1.json, rebuild the interaction DB, and copy to Flutter.
