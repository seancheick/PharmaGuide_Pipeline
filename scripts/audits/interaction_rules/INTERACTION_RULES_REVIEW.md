# Interaction Rules — Clinician Review

**Reviewer:** Dr Pham (+ team)
**Prepared:** 2026-04-30
**Returned + LOCKED:** 2026-04-30
**Implemented:** 2026-04-30 (this session)
**File audited:** `scripts/data/ingredient_interaction_rules.json` (schema 5.2.0 → 5.3.0, now 142 rules)

---

## STATUS — All sections SHIPPED

| Section | Status | Notes |
|---|---|---|
| 1A. Severity distribution | ✓ LOCKED | distribution intact |
| 1B. Common-ingredient calibration | ✓ LOCKED | W5 turmeric × anticoagulants now overrides any generic turmeric rule (clinician dedupe note) |
| 1C. Existing high-stakes rules | ✓ LOCKED | spot-checks confirmed |
| 2A. Warfarin / anticoagulants (W1-W12) | ✓ SHIPPED | 11 of 12 applied; W10 bromelain deferred (no subject_ref) |
| 2B. MAO inhibitors (M1-M8) | ✓ SHIPPED | 7 of 8 applied; M2 tyramine deferred (no subject_ref) |
| 2C. Lithium (L1-L7) | ✓ SHIPPED | all 7 applied |
| 2D. CYP3A4 / grapefruit (C1-C10) | ✓ SHIPPED | all 10 applied (C1-C3, C8-C10 use citrus_bergamot subject_ref) |
| 2E. CYP2D6 (next batch) | DEFERRED | non-blocking for V1 |
| 3C. Pregnancy/lactation hybrid gap-fill | ✓ SHIPPED | 100% coverage (10 Option A, 7 Option B, 88 Option C) |
| 3D. Schema additions | ✓ SHIPPED | evidence_level field present on every rule; canonical enum: no_data / limited / moderate / strong (legacy: established / probable / theoretical accepted) |
| 4. Severity vocab JSON (V1.1) | DEFERRED | covered by REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md P0 batch |
| 6. Open severity calls | ✓ LOCKED to Position A | M5 yohimbe=contraindicated, L4 turmeric=monitor; M2 deferred |

**Implementation artifacts:**
- `scripts/audits/interaction_rules/batch_W_M_L_C/backfill.py` — 36 drug-class rules + pregnancy pre-seeds, idempotent
- `scripts/audits/interaction_rules/batch_pl_gapfill/backfill.py` — hybrid gap-fill (A/B/C), idempotent
- `scripts/tests/test_interaction_rules_w_m_l_c_batch.py` — 91 regression tests, all passing

**Deferred to next batch (subject_ref required first):**
- **W10 Bromelain × anticoagulants** (severity: monitor) — bromelain has no IQM entry; folding it into `digestive_enzymes` would over-broaden the rule. Recommend adding a dedicated `bromelain` IQM entry.
- **M2 Tyramine-rich extracts × MAOIs** (severity: contraindicated, Section 6 open call) — tyramine isn't a single canonical ingredient but a class of fermented/aged compounds (aged-yeast, fermented bovine extracts, certain protein hydrolysates). Recommend a new `tyramine_rich_extract` entry in harmful_additives or other_ingredients.

---

## Original review proposal preserved below for audit trail

---

## TL;DR

**Severity calibration is solid.** Existing rules aren't over-flagging or under-grading. The issues are about **completeness**:

1. **4 critical drug-interaction families are missing entirely** — warfarin/anticoagulants, MAO inhibitors, lithium, CYP3A4/grapefruit. ~25 rules to add.
2. **Pregnancy/lactation field is empty on 69% of rules** (95 of 137). Where populated (42 rules), the data looks well-graded.

This MD proposes ~25 new rules + a pregnancy/lactation gap-fill plan, all for your sign-off before any data file changes.

---

## Section 1 — Calibration audit (CONFIRM as currently good)

### 1A. Severity distributions (existing 137 rules)

| Severity | Condition rules | Drug-class rules | Pregnancy | Lactation |
|---|---|---|---|---|
| `contraindicated` | 15 (7%) | 6 (3%) | 9 (21% of populated) | 1 (2.5%) |
| `avoid` | 39 (19%) | 24 (13%) | 18 (43%) | 19 (48%) |
| `caution` | 100 (48%) | 106 (57%) | 2 (5%) | 11 (28%) |
| `monitor` | 46 (22%) | 47 (25%) | 10 (24%) | 8 (20%) |
| `info` | 10 (5%) | 2 (1%) | — | — |

Sign-off: ☐ Distribution looks right (most rules at `caution`, with proper severe/lighter tails) ☐ Concern (please describe)

### 1B. Common-ingredient sanity check (none over-flagged)

Spot-check confirms safe staples aren't punished:

| Ingredient | Severities seen | Verdict |
|---|---|---|
| Caffeine | monitor, caution | ✓ |
| Vitamin C | monitor | ✓ |
| Vitamin D | mostly monitor | ✓ |
| Magnesium | mostly monitor, 1 avoid | ✓ |
| Turmeric | monitor, caution (anticoagulant context) | ✓ |
| Curcumin | caution (anticoagulant context) | ✓ |
| Omega-3 | caution (gallbladder, anticoagulants) | ✓ |
| Green tea extract | caution → avoid (high-dose hepatotoxicity) | ✓ |

Sign-off: ☐ Approve calibration ✏️ Edit (note any over-flagged: _______)

### 1C. Existing rules sanity-check (high-stakes interactions correct)

| Existing rule | Severity | Notes |
|---|---|---|
| St. John's Wort × SSRI/SNRI | `contraindicated` | ✓ Correct (serotonin syndrome) |
| 5-HTP × SSRI/SNRI | `contraindicated` | ✓ Correct |
| Bitter Orange × Hypertension | `avoid` | ✓ Correct |
| Bitter Orange × Antihypertensives | `avoid` | ✓ Correct |
| Ephedra × Pregnancy | `contraindicated` | ✓ Correct |

Sign-off: ☐ All correct ✏️ Edit (specific concerns: _______)

---

## Section 2 — Coverage gaps (PROPOSE NEW RULES)

### 2A. Warfarin / anticoagulants — **CRITICAL P0 gap, 0 rules currently**

This is the most clinically dangerous gap. Patients on warfarin are explicitly counseled to avoid these supplements. Proposed rules:

| # | Subject | Drug class | Severity | Mechanism (proposed) | References |
|---|---|---|---|---|---|
| W1 | Vitamin K (K1, K2/MK-4, MK-7) | Anticoagulants (warfarin/coumarin) | **avoid** | Vitamin K opposes warfarin's anticoagulant action via the vitamin-K-dependent clotting cascade. INR destabilization. | NIH ODS K monograph; Lurie 2010 BMJ; Holbrook 2005 Arch Intern Med |
| W2 | Ginkgo biloba | Anticoagulants/antiplatelets | **avoid** | Inhibits platelet aggregation (PAF antagonism). Bleeding risk amplified with warfarin. | Bone 2008; Stoddard 2015 Vascular Health Risk Manag |
| W3 | Garlic (high-dose extract) | Anticoagulants/antiplatelets | **caution** | Allicin/ajoene → mild antiplatelet effect. Clinical risk modest but real at supplement doses (≥600 mg/day extract). | Borrelli 2007 Mol Nutr Food Res |
| W4 | Fish oil / omega-3 (EPA+DHA) | Anticoagulants/antiplatelets | **caution** | Antiplatelet/antithrombotic at high dose (≥3 g/day combined EPA+DHA). Most dietary doses (1-2 g) appear clinically insignificant. | Bays 2007 Curr Atheroscler Rep; Wachira 2014 Br J Nutr |
| W5 | Turmeric / curcumin (high-dose extract) | Anticoagulants/antiplatelets | **caution** | Antiplatelet activity at clinical doses (≥500 mg curcuminoids). Multiple case reports with warfarin. | Daniel 2015 Forsch Komplementmed |
| W6 | St. John's Wort | Anticoagulants (warfarin) | **avoid** | CYP3A4 induction → ↓warfarin S-enantiomer exposure → reduced anticoagulation. Documented INR drop. | Henderson 2002 Br J Clin Pharmacol |
| W7 | CoQ10 (ubiquinone/ubiquinol) | Anticoagulants (warfarin) | **monitor** | Structural similarity to vitamin K; mild ↓warfarin effect at high dose (≥100 mg/day). | Engelsen 2003 Thromb Haemost |
| W8 | Dong Quai | Anticoagulants/antiplatelets | **avoid** | Coumarin content + antiplatelet phytochemicals. Multiple case reports of INR elevation. | Page 1999 Pharmacotherapy |
| W9 | Ginseng (Panax) | Anticoagulants (warfarin) | **caution** | Mixed evidence — some studies show ↓INR (efficacy reduction); others null. | Yuan 2004 Ann Intern Med |
| W10 | Bromelain | Anticoagulants/antiplatelets | **monitor** | Mild fibrinolytic / antiplatelet activity at high dose (≥500 mg). | Maurer 2001 Cell Mol Life Sci |

**Sign-off (per row):** ☐ APPROVE  ✏️ EDIT severity to: ____  ✗ REJECT (reason: ____)

**Should pregnancy_lactation also be set on these?** Most warfarin-class rules are population-agnostic (anyone on warfarin), but several (Dong Quai, high-dose ginseng) also have pregnancy concerns. Note per-row.

---

### 2B. MAO inhibitors — **0 rules currently**

Less common drug class today (most depression treatment moved to SSRIs), but MAOIs still in use for atypical depression, Parkinson's (selegiline), and some smoking-cessation contexts. Hypertensive crisis from tyramine + MAOI is severe.

| # | Subject | Drug class | Severity | Mechanism | References |
|---|---|---|---|---|---|
| M1 | Phenylethylamine (PEA) | MAO inhibitors | **contraindicated** | PEA is a direct MAO substrate; combination → hypertensive crisis. | Sabelli 1996 J Neuropsychiatry Clin Neurosci |
| M2 | Tyramine-rich extracts (aged-yeast, fermented bovine) | MAO inhibitors | **avoid** | Tyramine + MAOI → severe hypertensive reaction (cheese effect). | Gillman 2018 Br J Clin Pharmacol |
| M3 | 5-HTP / L-Tryptophan | MAO inhibitors | **contraindicated** | Serotonin precursor + MAOI → serotonin syndrome (also covers SSRI rule already in DB). | Birdsall 1998 Altern Med Rev |
| M4 | St. John's Wort | MAO inhibitors | **contraindicated** | Hypericin has weak MAO-inhibitor activity; combination duplicates mechanism → serotonin/hypertensive risk. | Markowitz 2003 JAMA |
| M5 | Yohimbe / yohimbine | MAO inhibitors | **avoid** | α-2 antagonist → ↑norepinephrine release; with MAOI inhibition → severe hypertension. | Tam 2001 Nutrition |
| M6 | Ginseng (Panax / American) | MAO inhibitors | **caution** | Multiple case reports of hypertensive episodes when combined with MAOIs (esp. phenelzine). | Jones 1987 J Clin Psychopharmacol |

**Sign-off (per row):** ☐ APPROVE  ✏️ EDIT  ✗ REJECT

---

### 2C. Lithium — **0 rules currently**

Narrow therapeutic index drug — lithium toxicity is a medical emergency. Several supplement interactions are clinically significant.

| # | Subject | Drug class | Severity | Mechanism | References |
|---|---|---|---|---|---|
| L1 | Caffeine (any source: coffee, green tea ext, guarana, yerba mate) | Lithium | **caution** | Caffeine ↑ renal clearance of lithium → ↓levels and ↓efficacy. Withdrawal of caffeine ↑ levels → toxicity risk. | Mester 1995 J Clin Pharmacol |
| L2 | Psyllium (and high-fiber supps when co-ingested) | Lithium | **monitor** | Reduces lithium absorption when taken concurrently. Separate dosing by 1-2 hours. | Perlman 1990 J Clin Psychiatry |
| L3 | Sodium-containing supplements (high sodium) | Lithium | **monitor** | High Na intake ↑ lithium clearance. Low Na ↑ retention → toxicity. Stable Na intake recommended. | Finley 1995 Clin Pharmacokinet |
| L4 | Turmeric / curcumin (anti-inflammatory dose) | Lithium | **monitor** | NSAID-like prostaglandin inhibition may ↑ lithium levels. Theoretical mechanism but documented for true NSAIDs. | Phelan 2003 Pharmacotherapy |
| L5 | Magnesium (high-dose, ≥400 mg/day from supplements) | Lithium | **monitor** | May ↓ lithium absorption when co-ingested. Separate by 2 hours. | Spiers 2018 Aust Prescr |

**Sign-off (per row):** ☐ APPROVE  ✏️ EDIT  ✗ REJECT

---

### 2D. CYP3A4 inhibitors / grapefruit pattern — **0 rules currently**

Anything that inhibits or induces CYP3A4 changes the exposure of a huge class of drugs (statins, calcium channel blockers, immunosuppressants, etc.).

| # | Subject | Drug class affected | Severity | Mechanism | References |
|---|---|---|---|---|---|
| C1 | Grapefruit / bergamot (any product flavored or extract) | Statins (simvastatin, lovastatin) | **avoid** | Furanocoumarins inhibit intestinal CYP3A4 → ↑ statin AUC 5-15× → rhabdomyolysis risk. | Bailey 2013 CMAJ |
| C2 | Grapefruit / bergamot | Calcium channel blockers (felodipine, nifedipine) | **avoid** | Same mechanism. ↑ exposure, hypotension/edema risk. | Bailey 2013 |
| C3 | Grapefruit / bergamot | Immunosuppressants (tacrolimus, cyclosporine) | **contraindicated** | Same mechanism. Toxic levels → nephrotoxicity. | Sridharan 2016 Indian J Pharmacol |
| C4 | St. John's Wort | Statins, calcium channel blockers, immunosuppressants, oral contraceptives, HIV antiretrovirals | **contraindicated** | CYP3A4 INDUCER (opposite effect) — ↓ drug exposure → therapy failure (e.g. transplant rejection, contraception failure). | Markowitz 2003 JAMA |
| C5 | Goldenseal (berberine + hydrastine) | CYP3A4-substrate drugs | **avoid** | Strong CYP3A4 inhibitor in vitro and in vivo. Also affects CYP2D6. | Gurley 2008 Drug Metab Dispos |
| C6 | Schisandra (schizandrol-rich extracts) | CYP3A4-substrate drugs | **caution** | Inhibits CYP3A4. Some clinical interactions with tacrolimus, sirolimus. | Xin 2007 J Pharm Pharmacol |
| C7 | Berberine (≥500 mg/day) | CYP3A4-substrate drugs | **caution** | In-vitro CYP3A4 inhibition; clinical effect modest at typical doses. | Guo 2012 Drug Metab Dispos |

**Sign-off (per row):** ☐ APPROVE  ✏️ EDIT  ✗ REJECT

---

## Section 3 — Pregnancy/Lactation field gap-fill (95 rules with empty data)

### 3A. The gap

| Pregnancy_lactation field state | Rule count |
|---|---|
| Populated (with `pregnancy_category` + `lactation_category`) | 42 (31%) |
| Empty / null | **95 (69%)** |

The schema is correct; coverage isn't. 69% of rules give the Flutter app no pregnancy/lactation guidance.

### 3B. Coverage of populated rules — looks well-graded

Of the 42 populated rules:

| Category | Pregnancy | Lactation |
|---|---|---|
| `contraindicated` | 9 | 1 |
| `avoid` | 18 | 19 |
| `caution` | 2 | 11 |
| `monitor` | 10 | 8 |
| `<none>` | 3 | 3 |

Sign-off: ☐ Calibration of populated entries looks correct ✏️ Concerns: _______

### 3C. Gap-fill plan

**Option A — Bulk default with clinician review:** auto-populate pregnancy_lactation on the 95 empty rules using a default policy (e.g., for known-safer ingredients like generic vitamins/minerals/probiotics: `pregnancy_category: monitor` and `lactation_category: monitor` with a "consult provider" note). Clinician spot-checks and adjusts.

**Option B — Targeted batches by ingredient class:** prioritize the 95 by clinical importance (banned/recalled subjects first, then high-dose herbs, then nutrient interactions). Author 20-30 per batch with clinician sign-off.

**Option C — Schema relaxation:** if pregnancy/lactation guidance is genuinely unknown for some entries, document them as such (`pregnancy_category: "no_data"` rather than null) so Flutter renders "Information not available" rather than nothing.

**Recommended:** mix of A + C — bulk-populate with `monitor` + "talk to provider" default for the obvious-safe ingredients, mark genuinely-unknown ones as `no_data`.

Sign-off: ☐ Option A  ☐ Option B  ☐ Option C  ☐ Hybrid (specify): _______

---

## Section 4 — Schema observations (no clinician sign-off needed)

- The `pregnancy_lactation` field schema uses `pregnancy_category` and `lactation_category` (not `severity` like condition_rules). Fine — just a structural distinction.
- All severity values use the same canonical set across condition_rules / drug_class_rules / pregnancy_lactation: `contraindicated`, `avoid`, `caution`, `monitor`, `info`. Consistent.
- Future opportunity: ship a `severity_vocab.json` Flutter asset with display copy + UX color/icon per tier (this is the same reference-data lookup pattern we used for functional_roles; saves repeating per-row severity descriptions).

---

## Section 5 — Sign-off summary

After completing 2A-2D and Section 3 above:

| Item | Approved? | Comments |
|---|---|---|
| 1A. Severity distribution looks right | ☐ | |
| 1B. Common-ingredient calibration | ☐ | |
| 1C. Existing high-stakes rules correct | ☐ | |
| 2A. Warfarin/anticoagulant rules (W1-W10) | ☐ | |
| 2B. MAO inhibitor rules (M1-M6) | ☐ | |
| 2C. Lithium rules (L1-L5) | ☐ | |
| 2D. CYP3A4/grapefruit rules (C1-C7) | ☐ | |
| 3C. Pregnancy/lactation gap-fill plan | ☐ | (Option: ____) |

**Reviewer signature / date:** _______________________

---

## What happens after sign-off

1. We add the ~25 approved rules to `ingredient_interaction_rules.json` (schema bump 5.2.0 → 5.3.0)
2. Per-rule regression test pinning each new rule's severity + mechanism + sources
3. Pregnancy/lactation gap-fill applied per the chosen option
4. Coverage gate extended: every interaction rule must have non-empty pregnancy_lactation field (after gap-fill)
5. Atomic commit per rule family (warfarin batch, MAO batch, etc.)

**Estimated calendar:** 1 day for implementation after clinician returns this MD.

---

*Questions? File: `scripts/data/ingredient_interaction_rules.json`. Audit script: `scripts/audits/interaction_rules/`.*
