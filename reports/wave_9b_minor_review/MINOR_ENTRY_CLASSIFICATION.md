# Wave 9.B — Minor-severity Entry Classification (REPORT ONLY)

**Generated:** 2026-05-27 by Claude per clinician-authorized B2 task.
**Scope:** All 25 `severity: "Minor"` entries in `scripts/data/curated_interactions/curated_interactions_v1.json`.
**Mode:** Report-only — **NO data edits, NO demotions, NO removals, NO promotions** until clinician walks this and authorizes.

---

## Two-lane policy (per clinician guardrail, 2026-05-27)

- **Lane 1 — User-facing alert:** clear action + meaningful harm if missed + strong source support. Severity in {`Contraindicated`, `Major`, `Moderate`}. Interruptive in app.
- **Lane 2 — Background clinical insight:** depletion/timing/educational; routed to a "medication nutrient consideration" layer or similar non-interruptive surface. Does NOT belong as an interruption.

Wave 8 (`batch_critical_2026_05.json`) already enforces `severity ∈ {Major, Moderate}` for that batch's user-facing entries. The 25 legacy Minor entries below predate the policy and currently sit in the same alert layer as Major entries — they're exactly the noise the two-lane framework is trying to fix.

---

## Classification taxonomy used in this report

| Code | Meaning | Implied action |
|---|---|---|
| **A — Promote to alert** | Meaningful harm + actionable + decent evidence. Should be `Moderate` (some maybe `Major`). | Upgrade severity + add PMIDs if missing. |
| **B — Background insight** | Useful info but not interruptive. Often beneficial co-administration or generic timing tip. | Keep entry, route to background layer (not alert). |
| **C — Remove/deprecate** | Too speculative, generic, or no clinical action. Likely contributes only noise. | Remove from curated_interactions or mark deprecated. |
| **D — Needs evidence upgrade** | Mechanism is plausible, harm could be meaningful, but evidence (PMID) is empty or weak. Cannot classify A vs B without verified evidence. | Research PubMed + content-verify before deciding A vs B. |

A row may be flagged with two codes if the recommendation depends on a clinician decision (e.g., **A or B**) — those are explicit asks for review.

---

## Summary table

| # | id | Pair | Drug class | Current sev | Proposed lane | Harm if missed (Cl, my draft) | Directly actionable | PMIDs |
|---:|---|---|---|---|---|---|---|---|
| 1 | `DSI_SSRI_MELATONIN` | SSRIs ↔ Melatonin | `class:ssris` | Minor | **A — Moderate (fluvoxamine-qualified)** | Yes — 17× melatonin level with fluvoxamine = excessive sedation | Yes | `10877005` |
| 2 | `DSI_LEVOTHYROXINE_COFFEE` | Levothyroxine ↔ Coffee | `10582` | Minor | **A — Moderate** | Yes — under-treatment of hypothyroidism (TSH drift) | Yes (separate ≥30–60 min) | `18341376` |
| 3 | `DSI_THYROID_TURMERIC` | Levothyroxine ↔ Turmeric | `10582` | Minor | **D — Evidence review first** (was A in v1; downgraded 2026-05-27) | TSH drift plausible but entry's own text describes evidence as "in vitro/animal + plausible high-dose effect"; PMID `30070343` is a clinical interaction study for the Meriva® bioavailable formulation specifically, not a class claim about all curcumin. Promote only after a confirmed-high-dose clinical anchor is found. | Timing rule is actionable IF promoted | `30070343` (Meriva®-specific) |
| 4 | `DSI_WAR_GLUCOSAMINE` | Warfarin ↔ Glucosamine | `11289` | Minor | **D → likely A — Moderate** | INR change on narrow-therapeutic-index drug | Yes (monitor INR) | empty — needs PubMed work |
| 5 | `DSI_WAR_GINGER` | Warfarin ↔ Ginger (high dose) | `11289` | Minor | **D → likely A — Moderate, dose-qualified** | Bleeding on warfarin is high-stakes | Yes (high dose only; INR monitor) | empty — needs PubMed work |
| 6 | `DSI_DM_CINNAMON` | Diabetes meds ↔ Cinnamon | `class:diabetes_meds` | Minor | **B — Background** (+ separate coumarin-toxicity rule for cassia) | Low at supplement doses; coumarin tox is a separate signal | Mild | `14633804` |
| 7 | `DSI_DM_MAGNESIUM` | Diabetes meds ↔ Magnesium | `class:diabetes_meds` | Minor | **B — Background** (beneficial co-admin) | Low; usually beneficial | No alert needed | `35045911` |
| 8 | `DSI_DM_VITD` | Diabetes meds ↔ Vitamin D | `class:diabetes_meds` | Minor | **B — Background** (beneficial co-admin) | Low | No alert needed | `41707752` |
| 9 | `DSI_STATINS_COQ10` | Statins ↔ CoQ10 | `class:statins` | Minor | **B — Background** (mitigation, not interaction) | None — supplementation studied as helpful for SAMS | Info only | empty (Batch 9.A intentionally skipped this) |
| 10 | `DSI_ANTIHYP_COQ10` | Antihypertensives ↔ CoQ10 | `class:antihypertensives` | Minor | **B — Background** | Mild additive BP-lowering, mostly beneficial | Info only | `26935713` |
| 11 | `DSI_ANTIHYP_MAGNESIUM` | Antihypertensives ↔ Magnesium | `class:antihypertensives` | Minor | **B — Background** | Mild additive BP-lowering, mostly beneficial | Info only | `21205110` |
| 12 | `DSI_ANTIHYP_ASHWAGANDHA` | Antihypertensives ↔ Ashwagandha | `class:antihypertensives` | Minor | **B — Background** | Low | Info only | `25237891` |
| 13 | `DSI_ANTIHYP_VITD` | Antihypertensives ↔ Vitamin D | `class:antihypertensives` | Minor | **B — Background** (correction of deficiency) | Low | Info only | empty |
| 14 | `DSI_ANTIPSYCH_MELATONIN` | Antipsychotics ↔ Melatonin | `class:antipsychotics` | Minor | **B — Background** (use low dose) | Low — additive sedation | Mild | empty |
| 15 | `DSI_BENZO_MELATONIN` | Benzodiazepines ↔ Melatonin | `class:benzodiazepines` | Minor | **B — Background** (sometimes therapeutic) | Low | Mild | empty |
| 16 | `DSI_BETABLOCK_MELATONIN` | Beta-blockers ↔ Melatonin | `class:beta_blockers` | Minor | **B — Background** (β-blocker suppresses endogenous melatonin) | Beneficial direction; supplementation may improve sleep | Info only | `10877005` |
| 17 | `DSI_CORTICO_CALCIUM_VITD` | Corticosteroids ↔ Ca+VitD | `class:corticosteroids` | Minor | **B — Background** (recommended adjunct, not an interaction) | Beneficial — bone-loss prevention | Mild | empty |
| 18 | `DSI_ANTICONV_VITD` | Anticonvulsants ↔ Vitamin D | `class:anticonvulsants` | Minor | **B — Background** (correction of AED-induced deficiency) | Beneficial | Info only | empty |
| 19 | `DSI_SSRI_FISHOIL` | SSRIs ↔ Fish oil | `class:ssris` | Minor | **C — Deprecate** (effect_type=Neutral; not an interaction) | None at typical doses | None | empty |
| 20 | `DSI_OC_SOY` | OCs ↔ Soy isoflavones | `class:oral_contraceptives` | Minor | **B — Background** at dietary doses; **D** at high-dose supplement | Low | Info only (caution gate at >100 mg/d) | empty (CUI was just re-aligned in Batch 1; sources need a refresh) |
| 21 | `DSI_ACEI_IRON` | ACE-Is ↔ Iron | `class:ace_inhibitors` | Minor | **C — Deprecate or B — Background** | Very small effect at typical iron doses | Generic 2h-apart timing tip | empty |
| 22 | `DSI_MELATONIN_VALERIAN` | Melatonin ↔ Valerian | `C0025219` (supp-supp) | Minor | **C — Deprecate** (obvious additive sedation; doesn't need a rule) | None unique | None unique | `38359657` (mechanism inferred) |
| 23 | `DSI_SEDATIVES_ASHWAGANDHA` | Sedatives ↔ Ashwagandha | `class:sedatives` | Minor | **C — Deprecate or B — Background** | Generic CNS additive | None unique | `23439798` |
| 24 | `SSI_MAGNESIUM_CALCIUM` | Magnesium ↔ Calcium | `C0024467` (supp-supp) | Minor | **B — Background** (absorption-timing tip) | None at typical doses | Timing tip | empty |
| 25 | `SSI_VITD_VITK2` | Vitamin D (high) ↔ Vitamin K2 | `C0042866` (supp-supp) | Minor | **B — Background** (co-administration optimization) | None | None | `22516723` |

**Distribution (my draft, pre-clinician — corrected 2026-05-27):**

| Lane | Count |
|---|---|
| A — Promote to alert | 2 (entries 1, 2) |
| D — Promote after evidence upgrade | 3 (entries 3 `DSI_THYROID_TURMERIC` downgraded from A; 4, 5 warfarin pair) |
| B — Background insight | 16 (entries 6–18 + 20 + 24 + 25) |
| C — Remove/deprecate | 1 firm (entry 19) + 2 borderline (entries 21, 23 — C or B) |
| Borderline C/B | 2 (entries 21, 23) |

---

## Per-entry detail

### A — Promote to alert (Moderate)

#### 1. `DSI_SSRI_MELATONIN` — SSRIs ↔ Melatonin
- **Pair:** SSRIs (class) ↔ Melatonin
- **Current severity:** Minor; `effect_type: Enhancer`; PMID `10877005`
- **Mechanism (current text):** "Fluvoxamine (an SSRI) strongly inhibits CYP1A2, the main enzyme metabolizing melatonin. Fluvoxamine + melatonin can cause up to 17-fold increase in melatonin plasma levels, causing excessive sedation."
- **Why promote:** A 17-fold pharmacokinetic increase from a real CYP1A2 inhibition is NOT Minor. The current Minor label is mislabeled — this is a substantial pharmacokinetic interaction. The fluvoxamine-specific qualifier is critical (other SSRIs do NOT have this CYP1A2 issue), so the alert should be drug-specific, not class-wide. Either (a) keep as `class:ssris` with management text that names fluvoxamine specifically (current text already does), or (b) split into a fluvoxamine-specific entry and a low-noise class entry.
- **Recommended next action:** Promote to **Moderate**, retain PMID `10877005`, keep fluvoxamine-specific management text. Optional: add a second PMID for the CYP1A2 mechanism review.
- **Actionable:** Yes — patient should know not to take melatonin with fluvoxamine specifically.
- **Harm if missed:** Excessive sedation, plus general intuition that "melatonin is safe" is wrong here.

#### 2. `DSI_LEVOTHYROXINE_COFFEE` — Levothyroxine ↔ Coffee
- **Pair:** Levothyroxine ↔ Coffee
- **Current severity:** Minor; `effect_type: Inhibitor`; PMID `18341376`
- **Mechanism (current text):** "Coffee, particularly espresso, can reduce levothyroxine absorption when taken simultaneously."
- **Why promote:** This is a standard endocrinology recommendation: take levothyroxine with water only, ≥30–60 min before any food/coffee. Under-treated hypothyroidism due to chronic timing error is a real, common, and avoidable harm. Every patient on T4 should be told this.
- **Recommended next action:** Promote to **Moderate** with the timing-separation action. The current management text already encodes the action; only the severity is wrong.
- **Actionable:** Yes — concrete timing rule.
- **Harm if missed:** TSH drift, persistent hypothyroid symptoms, dose escalation without resolving the timing root cause.

### D — Needs evidence upgrade (some may move to A after, some to B)

#### 3. `DSI_THYROID_TURMERIC` — Levothyroxine ↔ Turmeric / Curcumin **(downgraded from A → D on 2026-05-27 per clinician)**
- **Pair:** Levothyroxine ↔ Turmeric/Curcumin
- **Current severity:** Minor; `effect_type: Inhibitor`; PMID `30070343`
- **Mechanism (current text):** "Curcumin may bind thyroid hormone and reduce its absorption when taken simultaneously. Evidence is limited to in vitro and animal data, but a small clinical effect on levothyroxine absorption is plausible."
- **Why D not A:** The entry's own text describes evidence as "in vitro and animal data + plausible high-dose effect." PMID `30070343` IS a clinical interaction study — "Interaction study between antiplatelet agents, anticoagulants, thyroid replacement therapy and a bioavailable formulation of curcumin (Meriva®)" — but the anchor is specific to the Meriva® bioavailable formulation, not curcumin generally, and the abstract truncation in my fetch did not show the conclusion. Promoting to Moderate next to `DSI_LEVOTHYROXINE_COFFEE` (which has a direct 8-case-series human study, PMID `18341376`) would be promoting on weaker evidence and risk the noise pattern the two-lane policy was built to avoid.
- **Recommended next action:** Read PMID `30070343` end-to-end (Meriva® dose, magnitude of TSH/T4 change, statistical significance) before promoting. If the Meriva® data shows a meaningful absorption effect, promote with a Meriva-or-equivalent-high-bioavailability-curcumin qualifier — NOT a generic curcumin alert. If the data are weak, hold in B (background "separate by 4h if on high-dose curcumin" timing tip).
- **Actionable IF promoted:** Yes — timing separation.
- **Harm if missed:** TSH drift, same as coffee — but at lower magnitude given current evidence.

### D — Needs evidence upgrade (likely A after upgrade — warfarin pair)

#### 4. `DSI_WAR_GLUCOSAMINE` — Warfarin ↔ Glucosamine
- **Current severity:** Minor; `effect_type: Enhancer`; PMIDs: empty
- **Mechanism (current text):** Case reports of INR increase. Mechanism not well established (possible mild CYP2C9 inhibition).
- **Why D:** Warfarin is the highest-stakes drug in the curated set — even small INR perturbations can mean bleeding events. The current absence of PMIDs makes promotion premature. Glucosamine ± chondroitin case reports DO exist (Knudsen 2008, Rozenfeld 2004 type reports).
- **Recommended next action:** PubMed search for "glucosamine warfarin INR" + "glucosamine chondroitin warfarin case report" → content-verify candidates → if ≥1 strong citation, promote to **Moderate** (monitor-INR action). If no defensible PMID surfaces, demote to B (background timing/awareness only).
- **Actionable post-promotion:** Yes — INR monitor when starting.
- **Harm if missed:** Bleeding, the warfarin foot-gun.

#### 5. `DSI_WAR_GINGER` — Warfarin ↔ Ginger (high dose)
- **Current severity:** Minor; `effect_type: Additive`; PMIDs: empty
- **Mechanism (current text):** Antiplatelet thromboxane synthase inhibition at high doses (>2 g/day).
- **Why D:** Same logic as glucosamine — warfarin is narrow-therapeutic-index; even modest antiplatelet additivity is meaningful. Empty PMIDs blocks confident promotion. Real evidence exists (Lumb 1994, Heck 2000 review, Tan 2021 systematic review of herb-warfarin).
- **Recommended next action:** PubMed search → content-verify → if confirmed at the high-dose qualifier, promote to **Moderate (dose-qualified ≥2 g/day ginger supplement)**. Keep culinary ginger exempt in management text.
- **Actionable post-promotion:** Yes — INR monitor + watch bruising at high dose.
- **Harm if missed:** Bleeding.

### B — Background insight (route to non-alert layer)

These 16 entries should remain in the dataset but be tagged for a non-interruptive surface (e.g., a `display_layer: "background"` field, or a separate sister shard like `background_insights_v1.json`). The mechanism descriptions are clinically valid; the harm-if-missed is low. Routing them out of the alert layer is the noise reduction. Detailed table only for the non-trivial ones:

| id | Lane B rationale |
|---|---|
| `DSI_DM_CINNAMON` | Cinnamon supplement adds mild insulin sensitivity; not an interaction. Note: cassia coumarin toxicity is a SEPARATE concern that probably deserves its own ingredient-level rule, not a drug-supplement alert. |
| `DSI_DM_MAGNESIUM` | Magnesium is GENERALLY BENEFICIAL in T2DM; "interaction" framing is wrong. Belongs in nutrient-recommendation guidance. |
| `DSI_DM_VITD` | Same — D supplementation in deficiency improves insulin sensitivity. Beneficial co-admin, not an interaction. |
| `DSI_STATINS_COQ10` | CoQ10 is STUDIED AS MITIGATION for statin-associated muscle symptoms (SAMS). Calling this an "interaction" promotes the noise pattern your two-lane policy is trying to remove. |
| `DSI_ANTIHYP_COQ10`, `DSI_ANTIHYP_MAGNESIUM`, `DSI_ANTIHYP_ASHWAGANDHA`, `DSI_ANTIHYP_VITD` | All mild additive BP-lowering. Usually beneficial. "Monitor BP at supplementation start" is normal clinical practice, not an alert. |
| `DSI_ANTIPSYCH_MELATONIN`, `DSI_BENZO_MELATONIN` | Therapeutic adjunct framings. "Use low dose, monitor for excess sedation" is profile guidance not interruption. |
| `DSI_BETABLOCK_MELATONIN` | Beta-blockers suppress ENDOGENOUS melatonin; supplementation may IMPROVE sleep — info, not warning. |
| `DSI_CORTICO_CALCIUM_VITD` | Standard prophylaxis for glucocorticoid-induced osteoporosis. This is RECOMMENDED CARE, not an interaction warning. |
| `DSI_ANTICONV_VITD` | AEDs deplete D; supplementation is BENEFICIAL. Same as above — recommended care. |
| `DSI_OC_SOY` | Dietary soy safe; high-dose isoflavone caution is uncertain. May belong in D if anyone wants to surface PMID evidence, but at dietary doses this is B. |
| `SSI_MAGNESIUM_CALCIUM` | Absorption-competition timing tip. Background education on supplement co-administration. |
| `SSI_VITD_VITK2` | Co-administration optimization guidance. Background. |

### C — Remove/deprecate (no clinical action, contributes only noise)

#### 19. `DSI_SSRI_FISHOIL` — SSRIs ↔ Fish oil
- **Why C:** Current `effect_type: Neutral`, `mechanism: "no pharmacokinetic interaction with SSRIs. No significant adverse interaction is known."` — this is literally saying *there isn't an interaction*. The management text adds a generic "at doses >3 g/day, minor antiplatelet effects could slightly increase bleeding risk" — but that's already covered by the broader high-dose-omega-3 antiplatelet concern, not specifically SSRI-related.
- **Recommended next action:** Remove the entry from `curated_interactions_v1.json`, OR mark `display_layer: "deprecated"` with a note that the EPA/depression literature is positive (no warning needed). Move the high-dose omega-3 antiplatelet concern (if anywhere) under anticoagulants/antiplatelets, not SSRIs.

#### 22. `DSI_MELATONIN_VALERIAN` — Melatonin ↔ Valerian
- **Why C:** Both are mild sedatives; combining them is COMMON and INTENTIONAL (sleep stack supplements often contain both). The management text says "Start with lower doses of both if combining" — that's generic sleep-supplement advice, not a drug-supplement interaction. It's a supplement-supplement (`SSI_`-style) entry that doesn't carry a unique clinical signal beyond "two sedative supplements add up."
- **Recommended next action:** Remove or merge into a generic "additive sedation" advisory under a sleep-stack profile category. Not interaction-DB material.

#### 21. `DSI_ACEI_IRON` — ACE Inhibitors ↔ Iron — **C or B**
- **Why split:** Mechanism is real (GI chelation) but the magnitude at typical iron-supplementation doses is small, the management text is a generic timing tip ("take 2h apart"), no PMID, low confidence. If you keep it, it's background (B). If you remove it, you lose nothing clinically meaningful.
- **Recommended next action:** Clinician choice. Lean **B** (keep with background tag) since "separate by 2 hours" is harmless guidance.

#### 23. `DSI_SEDATIVES_ASHWAGANDHA` — Sedatives ↔ Ashwagandha — **C or B**
- **Why split:** Generic CNS-additive guidance. Doesn't carry a unique clinical signal beyond "two sedating things add up." If kept, B (background CNS-additive flag). If removed, the broader sedative-class advisory in the user's app profile (if any) covers it.
- **Recommended next action:** Lean **B** at most; could be **C** if there's a broader sedative-additive rule somewhere that subsumes it.

---

## Cross-cutting observations

1. **All 25 entries have `clinical_confidence: low`.** That's an internally honest signal that they were known-soft when added. The "Minor" label has been doing double-duty as both severity (low harm) AND confidence (we're not sure). The two-lane policy is the right way to disentangle these.

2. **12 of 25 entries have empty `source_pmids`** (corrected 2026-05-27 — earlier draft said 9, recounted treating None / missing key / `[]` as empty):
   - `DSI_WAR_GLUCOSAMINE`, `DSI_WAR_GINGER`, `DSI_STATINS_COQ10`, `DSI_SSRI_FISHOIL`,
     `DSI_ACEI_IRON`, `DSI_ANTICONV_VITD`, `DSI_BENZO_MELATONIN`, `DSI_CORTICO_CALCIUM_VITD`,
     `DSI_OC_SOY`, `DSI_ANTIPSYCH_MELATONIN`, `SSI_MAGNESIUM_CALCIUM`, `DSI_ANTIHYP_VITD`

   None of these would survive a verify_interactions `--check-pubmed` strictness
   upgrade if PMIDs were required. Citation backfill should be paired with the
   lane decision: A-lane entries need PMIDs (per Batch 9.A precedent); B-lane
   entries may rest on NIH/NCCIH URLs alone.

3. **Of the 13 entries that *do* have a PMID, 5 are weak anchors that do not
   directly support the interaction claim** (content-verified via PubMed
   efetch 2026-05-27):

   | Entry | PMID | What the article is actually about | Verdict |
   |---|---|---|---|
   | `DSI_ANTIHYP_MAGNESIUM` | `21205110` | "Oral magnesium supplementation reduces insulin resistance in non-diabetic subjects" | Not BP / antihypertensive additivity. **Weak anchor** for an antihypertensive interaction rule. |
   | `DSI_ANTIHYP_ASHWAGANDHA` | `25237891` | "Withania somnifera in monocrotaline-induced pulmonary hypertension" | Animal model of pulmonary HTN, not human systemic HTN co-administration. **Weak anchor.** |
   | `DSI_SEDATIVES_ASHWAGANDHA` | `23439798` | "RCT of ashwagandha root for stress and anxiety in adults" | Supports ashwagandha-alone anxiolytic effect; says nothing about sedative co-administration. **Weak anchor for an interaction claim.** |
   | `DSI_MELATONIN_VALERIAN` | `38359657` | "Does valerian work for insomnia? An umbrella review" | About valerian alone for insomnia; not melatonin + valerian co-admin. **Weak anchor.** |
   | `SSI_VITD_VITK2` | `22516723` | "Vitamin K status and vascular calcification — observational/clinical evidence" | Supports a broader Vit-K role in vascular calcification, not specifically D+K2 co-administration. **Weak / generic anchor.** |

   These weak anchors *support* the report's conclusion that those entries
   belong in Lane B (background, not user-facing alert) — but the report
   should not imply they are cleanly verified interaction PMIDs. The PMID
   strength differs by entry; severity decisions need to look at PMID title
   + abstract, not just the PMID-count column.

4. **The melatonin cluster is 5 of 25** entries (table rows 1, 14, 15, 16, 22 —
   not 6; my earlier draft included row 19 `DSI_SSRI_FISHOIL` and row 24
   `SSI_MAGNESIUM_CALCIUM` by mistake, neither of which involves melatonin).
   The 5 melatonin entries are:
   - row 1  `DSI_SSRI_MELATONIN`      — fluvoxamine CYP1A2 (real PK signal — Lane A)
   - row 14 `DSI_ANTIPSYCH_MELATONIN` — generic additive sedation (Lane B)
   - row 15 `DSI_BENZO_MELATONIN`     — generic additive sedation (Lane B)
   - row 16 `DSI_BETABLOCK_MELATONIN` — β-blocker suppresses endogenous melatonin (Lane B, often beneficial)
   - row 22 `DSI_MELATONIN_VALERIAN`  — additive sedation (Lane C or B; weak PMID anchor)

   Fluvoxamine is the only PK signal worth a user-facing alert. The other
   four are "X + melatonin = sleepier" variants and could collapse into a
   single "melatonin + sedative-class" background note.

5. **`DSI_DM_VITD` PMID `41707752` is valid** (initial suspicion based on PMID-size heuristic was wrong — PubMed IDs are past 41M as of 2026). Live efetch 2026-05-27: title "Mini-review. Vitamin D for the prevention of type 2 diabetes: Evidence and implications." Content matches the entry's topic. No action needed.

6. **`DSI_OC_SOY` was just re-CUI-aligned in Batch 1 (commit `c7cfeaf5`).** The entry's current Minor status is independent of that work — the soy_isoflavones canonical CUI is now correct (C0061202, genistein), but the severity classification still needs to be decided per this report.

---

## What I'm asking the clinician to confirm (corrected 2026-05-27)

1. **Promote (Lane A) — confirm 2 entries to Moderate:**
   - `DSI_SSRI_MELATONIN` (fluvoxamine CYP1A2 PK; PMID `10877005` is a direct content-verified anchor)
   - `DSI_LEVOTHYROXINE_COFFEE` (timing rule; PMID `18341376` "Altered intestinal absorption of L-thyroxine caused by coffee" is a direct content-verified anchor)

2. **Evidence review first (Lane D) — authorize PubMed work on 3 entries:**
   - `DSI_THYROID_TURMERIC` — read PMID `30070343` end-to-end (Meriva® specifics) before promoting. Don't sit it next to coffee on weaker evidence.
   - `DSI_WAR_GLUCOSAMINE`, `DSI_WAR_GINGER` — find content-verified PMIDs first, then promote if defensible. Defer to background if no PMID survives.

3. **Background lane (Lane B) — confirm 13–16 entries demoted from alert layer.** The mechanism is real but the framing of "interaction" is wrong; they're nutrient/comedication insights. Needs an app-side decision: separate shard? new `display_layer` field? `background_insights_v1.json`? Note that 5 of these have **weak PMID anchors** (table in observation §3) — when those entries move to Lane B, the weak PMID can either stay (as a generic ingredient-effect reference) or be removed so the entry's only support is NIH/NCCIH/text-author.

4. **Remove/deprecate (Lane C) — confirm 1 outright + 2 borderline:**
   - `DSI_SSRI_FISHOIL` — explicitly "no interaction" in its own text
   - `DSI_MELATONIN_VALERIAN`, `DSI_ACEI_IRON`, `DSI_SEDATIVES_ASHWAGANDHA` — C or B per your call

No data changes in this report. Awaiting your row-by-row sign-off (or counterproposal) before any demote/remove/promote happens.
