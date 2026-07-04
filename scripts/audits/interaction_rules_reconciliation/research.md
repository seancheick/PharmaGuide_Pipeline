# Interaction-rules reconciliation — clinical source research

Batch goal: author the app-table (`condition_thresholds.dart`) suppressions the
pipeline does not yet emit, as content-verified `condition_rules` in
`ingredient_interaction_rules.json`, so the app fallback table can be retired.

All findings below were fetched + content-verified by research subagents
(2026-07-04). PMIDs confirmed on-topic by reading the abstract, not existence
alone. **Floors err LOW.** Where a source contradicts the app's current
threshold, the source wins.

---

## 1. bleeding_disorders / vitamin_e — AUTHOR (dose_dependent)
- **direction** harmful · **materiality** dose_dependent · **severity** caution (escalate → avoid with anticoagulant/antiplatelet drug use)
- **floor** 400 IU/day (≈180 mg synthetic α-tocopherol). Distinct from and BELOW the UL (1,000 mg ≈ 1,500 IU) — the UL alone under-warns for hemorrhagic risk.
- **sources**
  - NIH ODS Vitamin E (HP): https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/ — "Vitamin E can inhibit platelet aggregation and antagonize vitamin K–dependent clotting factors." + "a large group of male physicians … consumed 400 IU (180 mg) … increased risk of hemorrhagic stroke."
  - Schürks 2010 BMJ, **PMID 21051774** — "the risk for haemorrhagic stroke was increased (pooled relative risk 1.22 …)".
- **DO NOT cite** Miller 2005 (PMID 15537682) for bleeding — it is an all-cause **mortality** meta-analysis; abstract contains no bleeding/hemorrhage terms. (Verified.)
- app 400 IU hypothesis: **SUPPORTED** (trial-anchored). confidence: high.

## 2. bleeding_disorders / garlic — AUTHOR (dose_dependent), floor CORRECTED
- **direction** harmful · **materiality** dose_dependent · **severity** caution
- **floor** 1200 mg/day. App's **600 mg is CONTRADICTED**: the one RCT with a 600 mg arm (Fakhar & Hashemi Tayer, **PMID 24575255**: 600/1200/2400 mg) found platelet-aggregation decrease only at 1200 & 2400 mg — no effect at 600 mg.
- **sources** NCCIH Garlic: https://www.nccih.nih.gov/health/garlic — "Taking garlic supplements may increase the risk of bleeding." (NCCIH gives no numeric floor.) + PMID 24575255.
- confidence: medium (floor is single-study; other prep-dependent RCTs bracket 800–1200 mg). No NIH/ODS garlic fact sheet exists.

## 3. vitamin_a / pregnancy + ttc — REFINE to form-gated (preformed retinol only)
- **direction** harmful · **materiality** presence-leaning **but form-gated: preformed retinol / retinyl esters ONLY — NOT beta-carotene** · **severity** caution, escalate → avoid at ≥10,000 IU
- **evidence threshold** 10,000 IU/day = 3,000 mcg RAE (pregnancy UL AND Rothman's observed teratogenic threshold, RR 4.8). App's 3,000 IU is a *conservative precautionary* trigger, not the evidence threshold — keep only if framed as precautionary, store 10,000 IU as the escalation threshold.
- **sources**
  - NIH ODS Vitamin A (HP): https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/ — "advise women who are or might be pregnant … not to take high doses (more than 3,000 mcg RAE [10,000 IU]) …" + "Unlike preformed vitamin A, beta-carotene is not known to be teratogenic …" + ULs "apply only to … retinol or its ester forms, such as retinyl palmitate."
  - Rothman 1995 NEJM, **PMID 7477116** — "an apparent threshold near 10,000 IU per day of supplemental vitamin A" (RR 4.8).
- **ttc** = same mechanism/threshold (pre-conception window; neural-crest development precedes pregnancy detection). Mirror the pregnancy rule.
- **KEY REFINEMENT**: current pipeline pregnancy/vitamin_a is `presence` but must be **form-gated to retinol** so it does NOT fire on beta-carotene-only prenatals (which ODS calls the safe form). confidence: high.

## 4. vitamin_b6_pyridoxine / seizure_disorder — AUTHOR (dose_dependent)
- **direction** harmful · **materiality** dose_dependent · **severity** caution/monitor
- **floor** 100 mg/day (conservative, = UL; neuropathy basis). Drug-interaction (phenytoin/phenobarbital serum-lowering) is documented at ~200 mg/day; 100 mg is the protective conservative floor. Keep 100 mg.
- **sources** NIH ODS Vitamin B6 (HP): https://ods.od.nih.gov/factsheets/VitaminB6-HealthProfessional/ — "pyridoxine supplementation (200 mg/day for 12–120 days) can reduce serum concentrations of phenytoin and phenobarbital …" + UL 100 mg/day. StatPearls NBK554500 corroborates. Hansson 1976 Lancet **PMID 55569** (title-verified; no abstract — dose from ODS).
- NOT presence, NOT contraindicated (RDA B6 has no AED interaction; AEDs actually deplete B6). confidence: high (direction), medium (200 mg cutoff).

## 5. zinc / kidney_disease — DO NOT AUTHOR; RETIRE the app entry
- **finding**: NOT a renal hazard. In CKD/dialysis the evidence-based concern is zinc **DEFICIENCY**; guidelines supplement 45–100 mg/day (ABOVE the 40 mg UL) under monitoring. The 40 mg UL is a **general-population copper-antagonism** ceiling, not renal-specific. No authoritative source establishes a kidney-specific zinc floor.
- **sources** NIH ODS Zinc (HP): https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/ — "The Tolerable Upper Intake Level for zinc is 40 mg for adults" … "based on the levels of zinc that have an adverse effect on copper status" (no kidney mention). Nutrients 2025 PMC12252395 — "Zinc deficiency is common in patients with CKD … recommends administering zinc … 50–100 mg/day."
- **DECISION**: do NOT author kidney/zinc as harmful (would flag clinically-appropriate supplementation). Retire the app-table `kidney_disease/zinc` entry. (If any zinc rule is wanted, it's a general copper caution ≥40–50 mg, severity monitor — not kidney-gated.) confidence: high.

---

## 6. caffeine / ttc — AUTHOR (dose_dependent, informational)
- **direction** harmful (only at high intake) · **materiality** dose_dependent · **severity** informational (caution ≥500 mg)
- **floor** fertility-specific harm is ~500 mg/day (ASRM); 200 mg is a **pregnancy** ceiling (ACOG), NOT a fertility threshold — ASRM says 1–2 cups (~200 mg) has "no apparent adverse effects on fertility." Use **200 mg as a conservative precautionary floor** but frame as precautionary, severity informational (do NOT say "reduces fertility" at 200 mg).
- **sources** ASRM Optimizing Natural Fertility (2022): https://www.asrm.org/practice-guidance/practice-committee-documents/optimizing-natural-fertility-a-committee-opinion-2021/ — "High levels of caffeine consumption (500 mg; >5 cups … per day …) have been associated with decreased fertility (OR 1.45 …)"; "moderate caffeine consumption (1–2 cups …) … has no apparent adverse effects on fertility." ACOG CO 462 **PMID 20664420** (pregnancy 200 mg; via Cleveland Clinic + NIH PMC — acog.org paywalled). confidence: high.

## 7. vitamin_d / kidney_disease — DO NOT AUTHOR at 4,000 IU; RETIRE (or informational)
- **finding**: nutritional D3 (what the pipeline scores) is neutral-to-beneficial in CKD; the hypercalcemia hazard belongs to **prescription active analogs** (calcitriol/paricalcitol/doxercalciferol — out of scope). 4,000 IU is the UL, NOT a CKD-harm threshold. ODS: toxicity "unlikely at daily intakes below 250 mcg (10,000 IU)"; CKD safety inflection is mega-bolus ≥100,000 IU.
- **sources** ODS Vitamin D: https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/ ("UL … 4,000 IU"; "unlikely at daily intakes below 250 mcg (10,000 IU)"); NKF CKD-MBD (calcitriol/paricalcitol are the active drugs); Frontiers 2025 (mega-bolus); RCT **PMID 28088187** (nutritional D preferred, less hypercalcemia).
- **DECISION**: retire the app `kidney/vitamin_d` dose rule at 4,000 IU (over-warns on beneficial D3). If any rule is kept, it's `informational` and the real trigger is co-ingestion (D3 + high calcium, or + thiazide) in renal impairment — not D3 dose alone. confidence: high.

---

## DECISIONS SUMMARY (author / refine / retire)

| # | canonical_id / condition | action | direction | materiality | floor | severity |
|---|---|---|---|---|---|---|
| 1 | vitamin_e / bleeding_disorders | **AUTHOR** | harmful | dose_dependent | 180 mg (=400 IU) | caution |
| 2 | garlic / bleeding_disorders | **AUTHOR** | harmful | dose_dependent | 1200 mg | caution |
| 3 | vitamin_b6_pyridoxine / seizure_disorder | **AUTHOR** | harmful | dose_dependent | 100 mg | caution |
| 4 | vitamin_a / ttc | **AUTHOR** (form-gated retinol) | harmful | **presence** (base caution any preformed retinol) + dose_threshold >10,000 IU→avoid | — (escalation 10,000 IU) | caution→avoid |
| 5 | caffeine / ttc | **AUTHOR** | harmful | dose_dependent | 200 mg (precautionary) | informational |
| 6 | vitamin_a / pregnancy | **REFINE** (form-gate retinol; fix floor 3,000→10,000 IU) | harmful | presence(form-gated) | 10,000 IU escalation | caution→avoid |
| 7 | zinc / kidney_disease | **RETIRE** (not a renal hazard; CKD = deficiency) | — | — | — | — |
| 8 | vitamin_d / kidney_disease | **RETIRE** (UL-as-floor over-warns; D3 beneficial in CKD) | — | — | — | — |

**Deviations from app thresholds (source-backed):** garlic 600→1200 mg (600 mg contradicted); retinol 3,000→10,000 IU (3,000 IU is near-RDA, no teratogenic signal); kidney/zinc + kidney/vitamin_d retired (evidence says don't warn).

**pregnancy/caffeine presence review**: evidence supports dose_dependent at 200 mg (ACOG: <200 mg not a major factor), i.e. current `presence` over-warns on trace caffeine. Left as a flagged follow-up (materiality change to an existing rule), not part of this batch.
