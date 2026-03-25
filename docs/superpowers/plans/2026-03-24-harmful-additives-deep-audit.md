# Harmful Additives Deep Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deep audit all 112 entries in `harmful_additives.json` for schema compliance, scientific accuracy, CUI/CAS/PubChem correctness, and severity calibration — using the audit protocol in `Harmful_additive_audit_prompt.md`.

**Architecture:** Process in 12 batches of ~10 entries. Each batch: read entries → verify against external sources (PubMed MCP, PubChem MCP, ChEMBL MCP, WebSearch for FDA/EFSA) → apply fixes ONE ENTRY AT A TIME → run targeted tests → commit. No batch fixes. Accuracy over speed.

**Tech Stack:** Python 3.13, pytest, PubMed MCP, ChEMBL MCP, PubChem via verify_pubchem.py, UMLS via verify_cui.py, UNII via verify_unii.py

**Critical Rules (from CLAUDE.md):**
- NEVER assume, ALWAYS verify against primary sources
- NO batch fixes — one entry at a time, verify each change
- This is a medical app — accuracy over speed
- IQM = bonuses. harmful_additives = penalties. Don't confuse them.
- DO NOT remove `entity_type` on class/category entries — `enrich_supplements_v3.py:5908-5916` depends on it for routing filters
- `gsrs` and `rxcui` fields (present on ~92 entries from verify_unii.py enrichment) should be PRESERVED — they contain FDA identity data. Do not remove them.

**Pre-Audit Safety:** Before starting, create a rollback point:
```bash
git tag pre-harmful-additives-audit
```

---

## Pre-Audit: Baseline & Gap Analysis

### Task 0: Establish Baseline

**Files:**
- Read: `scripts/data/harmful_additives.json`
- Read: `Harmful_additive_audit_prompt.md`
- Test: `scripts/tests/test_harmful_schema_v2.py`, `scripts/tests/test_harmful_additives_cui_cleanup.py`, `scripts/tests/test_harmful_additives_enrichment_structure.py`

- [ ] **Step 1: Run all harmful additives tests to confirm green baseline**

Run: `python3 -m pytest scripts/tests/test_harmful_schema_v2.py scripts/tests/test_harmful_additives_cui_cleanup.py scripts/tests/test_harmful_additives_enrichment_structure.py -v`
Expected: ~27 tests pass (14 schema + 6 CUI + 2 enrichment + parametrized expansions)

- [ ] **Step 2: Run verify_cui.py dry run to get CUI status snapshot**

Run: `.venv/bin/python scripts/api_audit/verify_cui.py --file scripts/data/harmful_additives.json --list-key harmful_additives --id-field id --cui-field cui`
Record: counts for VERIFIED, INVALID_CUI, MISMATCH, MISSING_CUI, NOT_FOUND, ANNOTATED_NULL

- [ ] **Step 3: Run verify_unii.py dry run to get UNII status snapshot**

Run: `.venv/bin/python scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives`
Record: counts for each status bucket

- [ ] **Step 4: Record gap summary**

Document in the audit output:
- All 112 entries need `dose_thresholds` populated where ADI/TDI exists (105 have null, 7 have the key present but with list wrapper instead of dict)
- 9 entries missing `jurisdictional_statuses` (BHA, BHT, parabens, TBHQ, etc.)
- 41 missing CAS, 56 missing PubChem CID, 15 missing CUI
- 2 entries with `entity_type` field (ADD_UNSPECIFIED_COLORS: "category", ADD_SYNTHETIC_ANTIOXIDANTS: "class") — these are FUNCTIONAL, used by enrichment routing. DO NOT REMOVE.
- 8 entries in batches 10-11 have extra `gsrs`/`rxcui`/`reason` fields and are missing `population_warnings`/`entity_relationships` — need schema normalization
- ~92 entries have `gsrs` and `rxcui` fields from verify_unii.py — PRESERVE these (FDA identity data)

---

## Batch Audit Protocol (Repeat for Each Batch)

Each batch follows this exact sequence. DO NOT skip steps.

### Per-Batch Workflow

For each entry in the batch:

1. **Read the entry** — understand current fields
2. **Verify standard_name and aliases** — cross-check against PubChem (use MCP `mcp__claude_ai_ChEMBL__compound_search` or `mcp__claude_ai_PubMed__search_articles` for mechanism verification)
3. **Verify CUI** — if present, confirm it maps to the right substance in UMLS. If null, check if there's a valid CUI available.
4. **Verify CAS** — cross-check via PubChem. Wrong CAS = wrong substance = patient safety risk.
5. **Verify PubChem CID** — look up if missing, confirm if present
6. **Verify mechanism_of_harm** — must describe a real biochemical pathway, not "may cause harm". Check against PubMed literature.
7. **Verify regulatory_status** — check CFR section numbers (common error source), EFSA re-evaluations (2022-2025), ADI values
8. **Verify severity_level** — calibrate against criteria in audit prompt
9. **Verify references** — DOIs must resolve to correct papers. No hallucinated refs.
10. **Check migration criteria** — if banned in all jurisdictions or FDA-banned, flag for migration to `banned_recalled_ingredients.json`
11. **Fill gaps** — add missing `dose_thresholds`, `jurisdictional_statuses`, `external_ids` where verifiable
12. **Update review block** — set `last_reviewed_at` to today, `reviewed_by` to audit batch number

After ALL entries in a batch are individually verified and fixed:
- Run targeted tests
- Commit the batch

---

## Batch Definitions

### Task 1: Batch 1 — Artificial Sweeteners & Early Entries (entries 1-10)

**Entries:** ADD_ACESULFAME_K, ADD_ACRYLAMIDE, ADD_ADVANTAME, ADD_ANTIMONY, ADD_ARTIFICIAL_FLAVORS, ADD_ASPARTAME, ADD_BLUE1, ADD_BLUE2, ADD_CALCIUM_ALUMINUM_PHOSPHATE, ADD_CALCIUM_CITRATE_LAURATE

**Focus areas:**
- Ace-K: Verify EFSA 2025 re-evaluation raised ADI to 15 mg/kg/day
- Acrylamide: Verify IARC Group 2A classification (check for upgrades)
- Antimony: Verify IARC 2023 upgrade to Group 2A (Vol 131)
- Aspartame: Verify IARC 2023 Group 2B classification + EFSA maintained ADI at 40 mg/kg
- Blue 1/2: Verify E133/E132, Southampton study inclusion, current EFSA ADI
- All: Verify CAS numbers, add PubChem CIDs where missing

**Files:**
- Modify: `scripts/data/harmful_additives.json` (entries 1-10 only)
- Test: `scripts/tests/test_harmful_schema_v2.py`

- [ ] **Step 1: Read entries 1-10 and verify each against sources**

Use PubMed MCP, ChEMBL MCP, and WebSearch to verify mechanism_of_harm, regulatory_status, CAS, CUI for each entry. Document findings per the audit output format.

- [ ] **Step 2: Apply fixes one entry at a time**

Edit ONLY the specific entry being fixed. Read the file before each edit. Verify the change after.

- [ ] **Step 3: Run targeted tests**

Run: `python3 -m pytest scripts/tests/test_harmful_schema_v2.py scripts/tests/test_harmful_additives_cui_cleanup.py scripts/tests/test_harmful_additives_enrichment_structure.py -q`
Expected: All pass

- [ ] **Step 4: Commit batch 1**

```bash
git add scripts/data/harmful_additives.json
git commit -m "Audit: harmful_additives batch 1 — sweeteners & early entries (10 entries verified)"
```

---

### Task 2: Batch 2 — Calcium Compounds & Early Fillers (entries 11-20)

**Entries:** ADD_CALCIUM_DISODIUM_EDTA, ADD_CALCIUM_LAURATE, ADD_CALCIUM_SILICATE, ADD_CANDURIN_SILVER, ADD_CANE_MOLASSES, ADD_CANE_SUGAR, ADD_CANOLA_OIL, ADD_CARAMEL_COLOR, ADD_CARBOXYMETHYLCELLULOSE, ADD_CARMINE_RED

**Focus areas:**
- EDTA compounds: Verify chelation mechanism, FDA GRAS status, CFR 172.120
- Candurin Silver: Verify mica-based pearlescent pigment status
- Caramel Color: Verify Class III/IV distinction, 4-MEI concern, EFSA opinion
- Carmine: Verify insect-derived allergen concern, E120 status
- CMC (E466): Verify EFSA 2023 re-evaluation opinion

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 3: Batch 3 — Carrageenan, Corn Derivatives, Copper (entries 21-30)

**Entries:** ADD_CARRAGEENAN, ADD_CASSAVA_DEXTRIN, ADD_CORN_OIL, ADD_CORN_SYRUP_SOLIDS, ADD_CROSCARMELLOSE_SODIUM, ADD_CROSPOVIDONE, ADD_CUPRIC_SULFATE, ADD_DEXTROSE, ADD_DISODIUM_EDTA, ADD_D_MANNOSE

**Focus areas:**
- Carrageenan: Verify degraded vs undegraded distinction, EFSA 2018 ADI revision, Tobacman inflammation studies
- Cupric Sulfate: Verify mineral_compound category, copper toxicity threshold
- Croscarmellose/Crospovidone: Verify excipient classification, no ADI concern

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 4: Batch 4 — Sugar Alcohols, Iron Oxide, Stearates (entries 31-40)

**Entries:** ADD_ERYTHRITOL, ADD_FATTY_ACID_POLYGLYCEROL_ESTERS, ADD_GREEN3, ADD_HYDROGENATED_STARCH_HYDROLYSATE, ADD_IRON_OXIDE, ADD_ISOMALTOOLIGOSACCHARIDE, ADD_MAGNESIUM_CITRATE_LAURATE, ADD_MAGNESIUM_LAURATE, ADD_MAGNESIUM_STEARATE, ADD_MALTITOL_MALITOL

**Focus areas:**
- Erythritol: Verify 2023 Cleveland Clinic clotting study (Witkowski et al, Nature Medicine), EFSA response
- Green 3 (E143): Verify FDA-only approval, not permitted in EU
- Iron Oxide (E172): Verify EFSA 2024 opinion on nanoparticle form
- Magnesium Stearate: Verify T-cell suppression claim is overstated (common misinformation)
- Maltitol: Check ID typo — `ADD_MALTITOL_MALITOL` (double check correct spelling)

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 5: Batch 5 — Maltodextrin, MSG, Neotame, Nickel, Nitrites (entries 41-50)

**Entries:** ADD_MALTODEXTRIN, ADD_MALTOL, ADD_MALTOTAME, ADD_MICROCRYSTALLINE_CELLULOSE, ADD_MINERAL_OIL, ADD_MODIFIED_STARCH, ADD_MSG, ADD_NEOTAME, ADD_NICKEL, ADD_POTASSIUM_NITRITE

**Focus areas:**
- MSG: Verify EFSA 2017 group ADI (30 mg/kg for glutamic acid + salts), aliases must NOT include nucleotides
- Neotame (E961): Verify FDA approval, EFSA ADI 2 mg/kg
- Nickel: Verify TDI (EFSA 2020: 13 ug/kg), contaminant classification
- Potassium Nitrite: Verify IARC Group 2A "under conditions that result in endogenous nitrosation" qualifier
- Mineral Oil: Verify EFSA 2012 opinion, food-grade vs technical grade distinction

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 6: Batch 6 — Nitrates, Palm Oil, Polysorbates, PEG (entries 51-60)

**Entries:** ADD_POTASSIUM_NITRATE, ADD_PALM_OIL, ADD_POLYDEXTROSE, ADD_POLYETHYLENE_GLYCOL, ADD_POLYSORBATE80, ADD_POLYSORBATE_40, ADD_POLYSORBATE_65, ADD_POLYVINYLPYRROLIDONE, ADD_POTASSIUM_HYDROXIDE, ADD_POTASSIUM_SORBATE

**Focus areas:**
- PEG: Verify anti-PEG antibody concern, FDA guidance for PEGylated drugs
- Polysorbate 80: Verify gut barrier disruption (Chassaing et al), E433 status
- Polysorbate 40/65: Verify cross-matching aliases don't collide with Polysorbate 80
- Potassium Hydroxide: Verify excipient classification, pH adjuster role

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 7: Batch 7 — Propylene Glycol, Red 40, Senna, Shellac (entries 61-70)

**Entries:** ADD_PROPYLENE_GLYCOL, ADD_PUREFRUIT_SELECT, ADD_RED40, ADD_SACCHARIN, ADD_SENNA, ADD_SHELLAC, ADD_SILICON_DIOXIDE, ADD_SLIMSWEET, ADD_SODIUM_ALUMINUM_PHOSPHATE, ADD_SODIUM_BENZOATE

**Focus areas:**
- Red 40: Verify EFSA 2014 ADI revision (4 mg/kg), Southampton study, California warning law
- Saccharin: Verify IARC 1999 delisting from Group 2B, NTP delisting 2000
- Senna: Verify stimulant laxative concern, prolonged use warnings
- Sodium Benzoate: Verify benzene formation concern (reaction with ascorbic acid)
- PureFruit Select / SlimSweet: Verify these are proprietary blends — may need null CUI with annotation

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 8: Batch 8 — Sodium Compounds, Sulfites (entries 71-80)

**Entries:** ADD_SODIUM_CASEINATE, ADD_SODIUM_COPPER_CHLOROPHYLLIN, ADD_SODIUM_HEXAMETAPHOSPHATE, ADD_SODIUM_LAURYL_SULFATE, ADD_SODIUM_METABISULFITE, ADD_SODIUM_SULFITE, ADD_SODIUM_TRIPOLYPHOSPHATE, ADD_SORBIC_ACID, ADD_SORBITAN_MONOSTEARATE, ADD_SORBITOL

**Focus areas:**
- Sulfites (metabisulfite, sulfite): Verify EFSA 2022 ADI withdrawal, now uses Margin of Exposure approach
- SLS: Verify irritant concern, cosmetic vs supplement context
- Phosphate compounds: Verify cardiovascular concern at high intake
- Sorbitol: Verify sugar_alcohol category, GI tolerance threshold (20g/day)

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 9: Batch 9 — Soy, Stearic Acid, Sucralose, Synthetic Vitamins (entries 81-90)

**Entries:** ADD_SOY_MONOGLYCERIDES, ADD_STEARIC_ACID, ADD_SUCRALOSE, ADD_SUGAR_ALCOHOLS, ADD_SULFUR_DIOXIDE, ADD_SYNTHETIC_B_VITAMINS, ADD_SYNTHETIC_VITAMINS, ADD_SYRUPS, ADD_TAPIOCA_FILLER, ADD_TETRASODIUM_DIPHOSPHATE

**Focus areas:**
- Sucralose: Verify EFSA 2016 opinion, gut microbiome studies, thermal degradation concern
- Sulfur Dioxide (E220): Verify EFSA 2022 sulfite group ADI withdrawal applies here too
- Synthetic Vitamins: Verify this is a class/routing entry — may need `entity_type: "class"` or `match_mode: "disabled"` treatment
- Sugar Alcohols: Same routing concern as above

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 10: Batch 10 — Thaumatin, Tin, Dyes, BHA/BHT (entries 91-100)

**Entries:** ADD_THAUMATIN, ADD_TIME_SORB, ADD_TIN, ADD_UNSPECIFIED_COLORS, ADD_VANILLIN, ADD_YELLOW5, ADD_YELLOW6, ADD_BHA, ADD_BHT, ADD_HYDROGENATED_COCONUT_OIL

**Focus areas:**
- BHA: Verify IARC Group 2B (1986), EFSA 2011 opinion, missing jurisdictional_statuses. **SCHEMA GAP:** missing `population_warnings`, `dose_thresholds`, has extra `gsrs`/`rxcui`/`reason` fields — normalize.
- BHT: Verify FDA GRAS status, CFR 172.115, missing jurisdictional_statuses. **SCHEMA GAP:** missing `population_warnings`, `scientific_references`, `dose_thresholds` — normalize.
- TBHQ (in batch 11): Will need jurisdictional_statuses added
- Yellow 5 (E102): Verify EFSA 2013 ADI revision, Southampton study
- Yellow 6 (E110): Verify EFSA 2014 ADI revision
- Tin: Verify EFSA 2005 opinion, JECFA PTWI 14 mg/kg
- Hydrogenated Coconut Oil: Verify trans fat concern vs MCT distinction. **SCHEMA GAP:** missing jurisdictional_statuses, has extra fields — normalize.

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 11: Batch 11 — Parabens, TBHQ, Nitrites, Fructose, HFCS (entries 101-110)

**Entries:** ADD_METHYLPARABEN, ADD_PROPYLPARABEN, ADD_SYNTHETIC_ANTIOXIDANTS, ADD_TBHQ, ADD_PARTIALLY_HYDROGENATED_CORN_OIL, ADD_POTASSIUM_BENZOATE, ADD_SODIUM_NITRITE, ADD_SODIUM_NITRATE, ADD_FRUCTOSE, ADD_HFCS

**Focus areas:**
- Parabens: Verify endocrine disruption evidence (methylparaben weak, propylparaben stronger), EFSA 2024 opinion on cosmetic use. **SCHEMA GAP:** missing jurisdictional_statuses, has extra `gsrs`/`rxcui`/`reason` — normalize.
- TBHQ: Verify immune system concern (EWG studies), EFSA 2004 opinion. **SCHEMA GAP:** missing jurisdictional_statuses — normalize.
- Partially Hydrogenated Corn Oil: Verify this should flag trans fat concern — check if it should migrate to banned (FDA 2018 PHO ban). **SCHEMA GAP:** missing jurisdictional_statuses — normalize. **MIGRATION CHECK:** FDA banned PHOs in 2018 — if this is a PHO, it may belong in `banned_recalled_ingredients.json`.
- Sodium Nitrite/Nitrate: Verify these are the atomic children from parent ADD_POTASSIUM_NITRITE split
- HFCS: Verify metabolic syndrome evidence, verify this is distinct from ADD_FRUCTOSE
- ADD_SYNTHETIC_ANTIOXIDANTS: Verify this is the routing parent (disabled match_mode) — should NOT score

- [ ] Steps 1-4: Same workflow as Batch 1

---

### Task 12: Batch 12 — Bisphenols (entries 111-112)

**Entries:** ADD_BISPHENOL_S, ADD_BISPHENOL_F

**Focus areas:**
- BPS: Verify endocrine disruption evidence — "regrettable substitution" for BPA
- BPF: Same concern, verify EFSA 2023 opinion on bisphenol group assessment
- Both: Verify contaminant category, high severity is appropriate

- [ ] Steps 1-4: Same workflow as Batch 1

---

## Post-Audit Verification

### Task 13: Final Verification & CUI/UNII Sync

**Files:**
- Modify: `scripts/data/harmful_additives.json` (_metadata update)
- Test: All harmful additives tests + cross-DB overlap guard

- [ ] **Step 1: Update _metadata**

Update `last_updated`, `total_entries`, `risk_breakdown` counts, `last_audit`, `audit_notes`.

- [ ] **Step 2: Run verify_cui.py with --apply for safe CUI fills**

Run: `.venv/bin/python scripts/api_audit/verify_cui.py --file scripts/data/harmful_additives.json --list-key harmful_additives --id-field id --cui-field cui --apply`
Only applies MISSING_CUI matches. Review output — do NOT auto-apply mismatches.

- [ ] **Step 3: Run verify_unii.py with --apply for safe UNII fills**

Run: `.venv/bin/python scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply`
Review output before accepting.

- [ ] **Step 3b: Run verify_pubchem.py dry run, then apply safe fills**

Run (dry): `python3 scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives`
Review output. Then apply safe CAS/CID fills:
Run: `python3 scripts/api_audit/verify_pubchem.py --file scripts/data/harmful_additives.json --list-key harmful_additives --apply`

- [ ] **Step 3c: Run verify_efsa.py dry run for ADI/re-evaluation cross-check**

Run: `python3 scripts/api_audit/verify_efsa.py --file scripts/data/harmful_additives.json --list-key harmful_additives`
Review output for ADI mismatches, stale opinions, and re-evaluation flags.

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest scripts/tests/test_harmful_schema_v2.py scripts/tests/test_harmful_additives_cui_cleanup.py scripts/tests/test_harmful_additives_enrichment_structure.py scripts/tests/test_cross_db_overlap_guard.py scripts/tests/test_enrichment_regressions.py scripts/tests/test_score_supplements.py -q`
Expected: All pass

- [ ] **Step 5: Run release gate checks**

```bash
.venv/bin/python scripts/api_audit/verify_cui.py --file scripts/data/harmful_additives.json --list-key harmful_additives --id-field id --cui-field cui --cache-file /tmp/harmful_additives_live_cui_cache.json --cache-ttl-seconds 0
.venv/bin/python scripts/api_audit/verify_unii.py --file scripts/data/harmful_additives.json --list-key harmful_additives --no-cache
```

- [ ] **Step 6: Final commit**

```bash
git add scripts/data/harmful_additives.json
git commit -m "Audit: harmful_additives deep audit complete — 112 entries verified, CUI/UNII synced"
```

---

## Audit Output Deliverables

After all batches, produce the summary tables from the audit prompt:
1. **TABLE 1:** Entry Summary & Verdicts (all 112 entries)
2. **TABLE 2:** Field-Level Changes (only changed fields)
3. **TABLE 3:** Schema & Normalization Fixes
4. **TABLE 4:** Migration Candidates (entries that should move to banned_recalled)
5. **BATCH SUMMARY** per batch

---

## Key Verification Tools Available

| Tool | Purpose | Command |
|------|---------|---------|
| PubMed MCP | Verify study references, search for mechanism evidence | `mcp__claude_ai_PubMed__search_articles`, `mcp__claude_ai_PubMed__get_article_metadata` |
| ChEMBL MCP | Compound search, bioactivity, ADMET | `mcp__claude_ai_ChEMBL__compound_search`, `mcp__claude_ai_ChEMBL__get_admet` |
| verify_cui.py | UMLS CUI verification | See _metadata.audit_runbook |
| verify_unii.py | FDA UNII + GSRS verification | See _metadata.audit_runbook |
| verify_pubchem.py | PubChem CID + CAS verification | `python3 scripts/api_audit/verify_pubchem.py` |
| WebSearch | FDA/EFSA regulatory status verification | For CFR numbers, EFSA re-evaluations |
| WebFetch | Fetch specific FDA/EFSA pages | For verifying source URLs |

---

## Estimated Scope

| Metric | Count |
|--------|-------|
| Total entries | 112 |
| Batches | 12 |
| Entries per batch | ~10 |
| Expected severity changes | 5-15 (based on IARC upgrades, EFSA re-evaluations) |
| Expected migration candidates | 1-3 (e.g., PHO if not already caught) |
| Expected CAS/CID fills | 30-50 |
| Expected dose_threshold fills | 40-60 (where ADI/TDI exists) |
| Expected jurisdictional fills | 9 (known gaps) |
