# Phase 1.5 Clinical Review — Verdicts

Reviewer: medical-grade verification pass against live PubMed eutils, NCCIH, NIH ODS, LiverTox.
Date: 2026-05-05.
Schema target: 6.0.2.

## Executive summary

Of the 16 entries (#129–#144), **1 has a hard-blocking ghost-reference defect** and **6 cite NIH URLs that 404 today** (link rot, not content defects, but they MUST be fixed before ship since end users see them in alert sources). The clinical content (severity, mechanism, scope) is largely sound — most issues are citation/copy-level, not scope-level. One real scope concern: bupleurum is gated on `cyp2d6_substrates` but the better-supported mechanism in the human/animal literature is CYP3A4 induction; the CYP2D6 claim is genuinely "theoretical" as the entry admits, so it's not a block, but a CYP3A4 sibling rule should be added in a follow-up batch. **Bromelain at `monitor` (not `caution`) is correctly conservative**; **white_mulberry's `caution` is fine but its `evidence_level: "established"` is overstated** for the alpha-glucosidase clinical-bleed mechanism — should be `probable`.

**Top action:** BLOCK #136 white_mulberry until ghost PMID 27092496 is removed/replaced. EDIT 6 entries to fix dead URLs. Remaining 9 are PASS or minor EDIT.

## Summary table

| # | canonical_id | verdict | priority | notes |
|---|---|---|---|---|
| 129 | BANNED_PENNYROYAL | EDIT | high | NCCIH pennyroyal URL is 404; replace with MedlinePlus 480 (which is already cited and resolves) or NIH ODS herb fact sheet |
| 130 | BANNED_TANSY | EDIT | med | NBK547852 is LiverTox root book, not a tansy chapter; LiverTox has no tansy entry. Replace with a real tansy source (e.g. NIEHS or a peer-reviewed thujone tox review) |
| 131 | BANNED_BITTER_ORANGE | EDIT | low | NCCIH URL 301-redirects to `/bitter-orange`; update slug. Otherwise sound |
| 132 | ginkgo_biloba_leaf | PASS | — | Sole NCCIH ginkgo URL resolves; mechanism, severity, copy all correctly conservative |
| 133 | holy_basil | EDIT | low | NCCIH `herbsataglance` URL resolves but is a generic landing page; cite the holy-basil-specific page or a peer review of Ocimum sanctum |
| 134 | maca | EDIT | high | NCCIH maca URL is 404 — replace |
| 135 | l_carnitine | PASS | — | ODS Carnitine HP fact sheet resolves; `informational` severity matches the modest evidence |
| 136 | white_mulberry | **BLOCK** | high | **PMID 27092496 is a GHOST REFERENCE** — that paper is "Hepatotoxicity Induced by 'the 3Ks': Kava, Kratom and Khat" (Int J Mol Sci 2016), zero relation to mulberry / alpha-glucosidase / glucose. Also `evidence_level: "established"` overstates the case |
| 137 | phenylethylamine | PASS | — | Mechanism and severity (`contraindicated`) are correct for MAOI co-use; FDA generic interactions URL is acceptable but a specific MAOI tyramine/PEA reference would strengthen it |
| 138 | l_tryptophan | EDIT | high | ODS Tryptophan fact sheet URL is 404 — replace with current ODS path or LiverTox L-tryptophan chapter |
| 139 | ADD_HORDENINE | PASS | — | β-PEA analog framing is accurate; severity `contraindicated` matches PEA precedent |
| 140 | same | EDIT | high | NCCIH SAMe URL is 404 — replace |
| 141 | sodium | EDIT | high | ODS Sodium HP URL is 404 — replace; CDC `/salt/` URL also worth re-verifying |
| 142 | bromelain | EDIT | low | PMID 11577981 verified — Maurer 2001 CMLS review on bromelain. But it's a general pharmacology review, not specifically a warfarin/antiplatelet bleeding paper. Mechanism claim ("clinical bleeding events with warfarin documented in case reports") needs a case-report citation, not just the review |
| 143 | ADD_TYRAMINE_RICH_EXTRACT | PASS | — | Cheese-reaction framing is textbook-accurate; `contraindicated` correct |
| 144 | bupleurum_root | EDIT | med | Profile gate `cyp2d6_substrates` is debatable — primary literature on saikosaponins is CYP3A4 (induction) and possibly CYP1A2; CYP2D6 is weaker. Either re-scope or add a CYP3A4 sibling rule. Entry honestly tags `evidence_level: theoretical` so not a block |

Aggregate: PASS=5, EDIT=10, BLOCK=1.

## Per-entry findings

### [129] BANNED_PENNYROYAL — EDIT
- **Severity check:** `contraindicated` is correct. Pulegone hepatotoxicity is well established (multiple fatal case reports, FDA warnings). PASS on severity.
- **Mechanism accuracy:** "Pulegone and related hepatotoxic constituents… abortifacient concern" is accurate and not overstated.
- **Citations verified:**
  - `https://www.nccih.nih.gov/health/pennyroyal` → **HTTP 404** (link rot).
  - `https://medlineplus.gov/druginfo/natural/480.html` → not directly retested but MedlinePlus IDs of this form are stable; assume OK (mark as `likely-OK, unverified by curl in this pass`).
- **Proposed edits:** Replace dead NCCIH URL. Suggested replacement: NIH ODS botanical safety page or LiverTox pennyroyal chapter (NBK548280 — verify). Field path: `condition_rules[0].sources[0]`.
- **Confidence:** high.

### [130] BANNED_TANSY — EDIT
- **Severity check:** `contraindicated` correct (thujone neurotoxicity + abortifacient history).
- **Mechanism accuracy:** "Thujone and other toxic constituents" is fine.
- **Citations verified:**
  - `https://www.ncbi.nlm.nih.gov/books/NBK547852/` → resolves to LiverTox **root book** ("LiverTox: Clinical and Research Information on Drug-Induced Liver Injury"), NOT a tansy chapter. PubMed esearch on `tansy AND livertox` returns 0 hits. **This is a near-ghost reference**: the URL is real, but it does not specifically support the tansy-toxicity claim. End users clicking through will land on a generic LiverTox home page.
  - `https://www.nccih.nih.gov/health/herbsataglance` → 200 (generic A-Z landing page; not tansy-specific).
- **Proposed edits:** Replace NBK547852 with a tansy-specific source (e.g. PMID for a thujone tox review, or an NCCIH/NIH botanical monograph if one exists). Either way the current pair gives the user nothing tansy-specific. Field path: `condition_rules[0].sources` (replace `NBK547852`).
- **Confidence:** high.

### [131] BANNED_BITTER_ORANGE — EDIT
- **Severity check:** `contraindicated` for pregnancy at supplement dose is reasonable given synephrine sympathomimetic + stacking with caffeine; Health Canada has restricted synephrine. The dose threshold (`>=3 mg/day → contraindicated, else avoid`) is sensible.
- **Mechanism accuracy:** "Synephrine is a sympathomimetic" — correct and not overstated.
- **Citations verified:**
  - `https://www.nccih.nih.gov/health/bitterorange` → **301 → /bitter-orange** (works after redirect). Update slug.
  - Health Canada synephrine page → not curl-tested but Canada.ca paths of this form are stable.
- **Proposed edits:** Update URL: `bitterorange` → `bitter-orange`. Field path: `condition_rules[0].sources[0]`.
- **Confidence:** high.

### [132] ginkgo_biloba_leaf — PASS
- **Severity check:** `avoid` (not `contraindicated`) for chronic pregnancy use is appropriately conservative — antiplatelet activity is real but not a categorical bar.
- **Mechanism accuracy:** "Antiplatelet effects make peripartum bleeding the main concern" — accurate and scoped (peripartum specifically).
- **Citations verified:** `https://www.nccih.nih.gov/health/ginkgo` → 200.
- **Proposed edits:** none.
- **Confidence:** high.

### [133] holy_basil — EDIT
- **Severity check:** `informational` + `theoretical` is appropriately conservative for sparse human pregnancy data.
- **Mechanism accuracy:** "Animal data raise endocrine and uterotonic uncertainty" — supported by rodent studies (anti-fertility effects of Ocimum sanctum extract). Not overstated.
- **Citations verified:** `https://www.nccih.nih.gov/health/herbsataglance` → 200 but generic landing page; not holy-basil-specific.
- **Proposed edits:** Cite holy-basil/tulsi-specific source (NCCIH does not appear to have a dedicated tulsi page; consider PubMed review of Ocimum sanctum reproductive effects, or remove the source and downgrade `evidence_level` honestly to `theoretical` which it already is). Field path: `condition_rules[0].sources[0]`.
- **Confidence:** med.

### [134] maca — EDIT
- **Severity check:** `informational` + `theoretical` is correct for "data sparse."
- **Mechanism accuracy:** "Human pregnancy safety data are sparse" is itself the mechanism claim — honest and correct.
- **Citations verified:** `https://www.nccih.nih.gov/health/maca` → **HTTP 404**.
- **Proposed edits:** Replace dead URL. Possible replacements: ODS botanical fact sheet for Lepidium meyenii, or a PubMed review (e.g. Gonzales 2012 on maca clinical safety). Field path: `condition_rules[0].sources[0]`.
- **Confidence:** high.

### [135] l_carnitine — PASS
- **Severity check:** `informational` is correct — meta-analyses (e.g. Vidal-Casariego 2013) show modest HbA1c effects; not severe enough for `caution`.
- **Mechanism accuracy:** "May modestly affect fuel utilization and insulin sensitivity" — correctly hedged ("may modestly").
- **Citations verified:** `https://ods.od.nih.gov/factsheets/Carnitine-HealthProfessional/` → 200.
- **Proposed edits:** none.
- **Confidence:** high.

### [136] white_mulberry — **BLOCK**
- **Severity check:** `caution` for diabetes co-use with acarbose/insulin is reasonable. But `evidence_level: "established"` is overstated. Human RCT evidence for white-mulberry alpha-glucosidase inhibition lowering postprandial glucose exists but is small (a few small trials); clinical interaction with acarbose/insulin is **mechanistic plausibility**, not "established" interaction in the Hansten/Stockley sense. Should be `probable`.
- **Mechanism accuracy:** "Alpha-glucosidase inhibition slows carbohydrate absorption" — correct in vitro and in small trials. The claim is not overstated.
- **Citations verified:**
  - `https://pubmed.ncbi.nlm.nih.gov/27092496/` → **GHOST REFERENCE**. Verified via eutils esummary: title is *"Hepatotoxicity Induced by 'the 3Ks': Kava, Kratom and Khat"* (Int J Mol Sci 2016 Apr 16). Abstract confirms it's about kava/kratom/khat liver injury. **Zero relation to white mulberry, alpha-glucosidase, or glucose.** This is exactly the failure mode called out in the user's `critical_no_hallucinated_citations` memory.
  - `https://www.nccih.nih.gov/health/herbsataglance` → 200 (generic landing).
- **Proposed edits:**
  - **REMOVE** PMID 27092496 from `dose_thresholds[0].note` and any other reference. Field path: `dose_thresholds[0].note` (currently has the bad URL inline).
  - **REPLACE** with a verified human-trial PMID. Candidates from a fresh esearch on `mulberry alpha-glucosidase postprandial glucose`: 41228506, 40419090, 40024750, 39064619, 39055216. **Each must be content-verified** before substitution — do not trust the search result alone.
  - **DOWNGRADE** `condition_rules[0].evidence_level` from `"established"` to `"probable"`.
- **Confidence:** high (on the ghost defect; replacement PMID requires a separate content-verification step before commit).

### [137] phenylethylamine — PASS
- **Severity check:** `contraindicated` for MAOI co-use is correct; PEA + MAOI hypertensive crisis is established pharmacology.
- **Mechanism accuracy:** "PEA is a direct MAO substrate; combination with MAOIs causes hypertensive crisis" — correct and unambiguous.
- **Citations verified:** `https://www.fda.gov/drugs/resources-you/drug-interactions-what-you-should-know` → not curl-tested in this pass; FDA generic interactions page (assume stable). It's a **generic** source, not PEA-specific, but defensible for a "do not combine with MAOI" public-health claim.
- **Proposed edits:** none required for ship; optional follow-up: add a PEA/MAOI-specific reference (e.g. Sabelli et al. on PEA pharmacology) for stronger evidentiary backing.
- **Confidence:** high.

### [138] l_tryptophan — EDIT
- **Severity check:** `contraindicated` for MAOI is correct (precursor + MAOI → serotonin syndrome documented in literature; also EMS/L-tryptophan history).
- **Mechanism accuracy:** "Serotonin precursor combined with MAOI inhibition → serotonin syndrome" — correct.
- **Citations verified:** `https://ods.od.nih.gov/factsheets/Tryptophan/` → **HTTP 404**.
- **Proposed edits:** Replace dead URL. ODS may have moved it to a different slug; otherwise cite LiverTox L-tryptophan chapter or the FDA L-tryptophan import alert as backstop. Field path: `drug_class_rules[0].sources[0]`.
- **Confidence:** high.

### [139] ADD_HORDENINE — PASS
- **Severity check:** `contraindicated` with MAOI is justified by structural class (β-PEA analog); precautionary but proportional.
- **Mechanism accuracy:** "Hordenine is a β-PEA analog and direct MAO substrate" — accurate at the mechanism level. The animal-vs-human caveat is acknowledged elsewhere ("often combined with PEA in pre-workout stacks compounding the risk") which is accurate.
- **Citations verified:** FDA generic URL (same caveat as #137).
- **Proposed edits:** none for ship; optional: add a primary pharmacology reference for hordenine MAO substrate activity.
- **Confidence:** med-high.

### [140] same — EDIT
- **Severity check:** `avoid` (not `contraindicated`) is correctly less aggressive than tryptophan/PEA — SAMe's serotonergic activity is real but indirect (methyl donor with antidepressant-like effects, not direct serotonin precursor). Severity choice is well calibrated.
- **Mechanism accuracy:** "Methyl donor with antidepressant activity; serotonergic potentiation when combined with MAOIs raises serotonin syndrome risk." — accurate and appropriately hedged ("raises risk", not "causes").
- **Citations verified:** `https://www.nccih.nih.gov/health/same` → **HTTP 404**.
- **Proposed edits:** Replace dead URL. NCCIH may have moved SAMe to `s-adenosyl-l-methionine-same` or similar slug; otherwise cite LiverTox SAMe chapter or NIH ODS. Field path: `drug_class_rules[0].sources[0]`.
- **Confidence:** high.

### [141] sodium — EDIT
- **Severity check:** `monitor` (not `caution`) for sodium-lithium consistency is exactly right — this is a "keep stable" rule, not an "avoid" rule. Excellent calibration.
- **Mechanism accuracy:** "High sodium intake increases lithium clearance. Low sodium increases lithium retention → toxicity risk" — textbook accurate; this is a foundational lithium-pharmacology fact.
- **Citations verified:**
  - `https://ods.od.nih.gov/factsheets/Sodium-HealthProfessional/` → **HTTP 404**.
  - `https://www.cdc.gov/salt/index.html` → not curl-tested in this pass; CDC has reorganized salt content under `/salt/` and `/sodium/` so this URL may also be stale. Verify.
- **Proposed edits:** Replace dead ODS URL (try `factsheets/Sodium-Consumer/` or current path). Verify CDC URL. Field path: `drug_class_rules[0].sources` (both entries).
- **Confidence:** high.

### [142] bromelain — EDIT (minor)
- **Severity check:** `monitor` (NOT `caution`) is the **correct** choice for high-dose bromelain + anticoagulant — clinical bleeding events with warfarin are case-report-level, not RCT-level. Calibration is right; do **not** soften further.
- **Mechanism accuracy:** "Mild fibrinolytic / antiplatelet activity at high dose (≥500 mg/day). Bromelain enhances plasmin generation and modestly inhibits platelet aggregation. Clinical bleeding events with warfarin are rare but documented in case reports." — the first two sentences are supported by Maurer 2001. The case-report claim is plausible but **not directly supported by PMID 11577981** (which is a general pharmacology review, not a case series). This is a citation-attribution mismatch, not a fabrication.
- **Citations verified:**
  - `https://pubmed.ncbi.nlm.nih.gov/11577981/` → verified Maurer H, *"Bromelain: biochemistry, pharmacology and medical use"*, Cell Mol Life Sci 2001 Aug. Abstract confirms fibrinolytic/antithrombotic activity. **Topic match: YES for fibrinolytic/antiplatelet claim. NO for the warfarin case-report claim.**
  - `https://www.nccih.nih.gov/health/bromelain` → 200.
- **Proposed edits:** Either (a) soften mechanism to drop the warfarin case-report sentence (since it's not supported by either citation), or (b) add a case-report PMID that does support it. Recommend (a) for this batch — drop the sentence "Clinical bleeding events with warfarin are rare but documented in case reports." Field path: `drug_class_rules[0].mechanism`.
- **Confidence:** high.

### [143] ADD_TYRAMINE_RICH_EXTRACT — PASS
- **Severity check:** `contraindicated` with MAOI is **the** classic textbook contraindication ("cheese reaction"). Severity is correct.
- **Mechanism accuracy:** Cheese-reaction description is textbook-accurate. "Documented fatalities in the clinical literature" is a strong claim but well-established for tyramine + MAOI hypertensive crisis (multiple decades of pharmacology literature).
- **Citations verified:** FDA generic URL — fine for a public-health-message claim of this strength, since the cheese-reaction is textbook.
- **Proposed edits:** none for ship. Optional: `alert_body` is truncated mid-word ("This i...") and `informational_note` is truncated ("isocarboxa..."). These look like dump truncation in BASELINE.md, not the actual data — verify the live JSON has full text. If the JSON is also truncated, **fix** before ship. Field paths: `drug_class_rules[0].alert_body`, `drug_class_rules[0].informational_note`.
- **Confidence:** high (clinical), med (depends on whether truncation is real).

### [144] bupleurum_root — EDIT
- **Severity check:** `caution` + `theoretical` is appropriately conservative.
- **Mechanism accuracy:** "Saikosaponins inhibit CYP2D6 in vitro and in animal models" — this is the **weakest part** of the entry. The bupleurum / saikosaponin literature in humans and animals more strongly implicates **CYP3A4 induction** (rat hepatocyte studies, Sho-saiko-to interactions) and CYP1A2; CYP2D6 inhibition has thinner support. The entry honestly tags `evidence_level: theoretical` which is fine, but the **profile_gate** scope of `cyp2d6_substrates` may be the wrong cytochrome.
- **Citations verified:** FDA generic URL — does NOT support the saikosaponin/CYP2D6-specific claim at all. This is a generic public-health resource attached to a specific pharmacology claim. Borderline ghost-reference-by-attribution.
- **Proposed edits:** Two options:
  1. **Re-scope** to `cyp3a4_substrates` (better-supported mechanism) and rewrite alert text accordingly.
  2. **Keep CYP2D6 as theoretical** but cite a primary source (e.g. PubMed review of saikosaponin CYP modulation) instead of the FDA generic page; **and** add a follow-up CYP3A4 sibling rule in the next batch.
  Recommend option 2 for this batch (don't re-scope without doing the literature legwork). Field paths: `drug_class_rules[0].sources[0]` (replace), and add a TODO to file a CYP3A4 sibling rule.
- **Confidence:** med (the CYP2D6 vs CYP3A4 question deserves a focused literature pass before final commit).

## Pregnancy/lactation block consistency check

All 16 entries' P/L blocks are internally consistent with their condition rule severity:
- Banned/recalled entries (#129, #130, #131, #139, #143) all carry `contraindicated` or `caution` P/L — consistent.
- Botanical/IQM entries with sparse data (#132, #133, #134, #135, #136, #137, #138, #140, #141, #142) carry `no_data` P/L — appropriate.
- #144 bupleurum carries `caution` P/L with emmenagogue rationale — appropriate.

No P/L inconsistencies flagged.

## Citation index — verification status

| URL/PMID | Used in | Status |
|---|---|---|
| PMID 27092496 | #136 white_mulberry | **GHOST — paper is about kava/kratom/khat, not mulberry** |
| PMID 11577981 | #142 bromelain | Verified — Maurer 2001 CMLS bromelain review. Topic match for fibrinolytic claim, not for warfarin case-report claim |
| NBK547852 | #130 tansy | LiverTox root book; no tansy chapter exists. Near-ghost — replace |
| nccih.nih.gov/health/pennyroyal | #129 | **HTTP 404** |
| nccih.nih.gov/health/maca | #134 | **HTTP 404** |
| nccih.nih.gov/health/same | #140 | **HTTP 404** |
| ods.od.nih.gov/factsheets/Tryptophan/ | #138 | **HTTP 404** |
| ods.od.nih.gov/factsheets/Sodium-HealthProfessional/ | #141 | **HTTP 404** |
| nccih.nih.gov/health/bitterorange | #131 | 301 → `/bitter-orange` (update slug) |
| nccih.nih.gov/health/ginkgo | #132 | 200 OK |
| nccih.nih.gov/health/bromelain | #142 | 200 OK |
| nccih.nih.gov/health/herbsataglance | #130, #133 | 200 OK (generic landing — not subject-specific) |
| ods.od.nih.gov/factsheets/Carnitine-HealthProfessional/ | #135 | 200 OK |
| medlineplus.gov/druginfo/natural/480.html (pennyroyal) | #129 | unverified by curl in this pass; MedlinePlus IDs of this form are stable |
| canada.ca/.../synephrine.html | #131 | unverified by curl in this pass |
| fda.gov/drugs/resources-you/drug-interactions... | #137, #139, #143, #144 | unverified by curl in this pass; generic FDA interactions page (assume stable) |
| cdc.gov/salt/index.html | #141 | unverified; CDC has reorganized salt content; **suspect stale** — verify |

## Recommendation for this ship

- **BLOCK ship of #136 white_mulberry** until ghost PMID 27092496 is removed and either replaced with a content-verified PMID or the dose_thresholds note is rewritten to drop the bad citation. Also downgrade `evidence_level` from `established` to `probable`.
- **EDIT and ship the 9 entries with stale URLs** (#129, #130, #131, #133, #134, #138, #140, #141, plus minor edit on #142 and #144). All of these are link-rot / citation-attribution issues, not clinical-content defects. They can be batch-fixed with a URL-replacement pass — but each replacement URL must itself be curl-verified before commit.
- **PASS and ship without changes:** #132 ginkgo, #135 l_carnitine, #137 phenylethylamine, #139 hordenine, #143 tyramine.
- **Verify before ship** that #143 `alert_body` and `informational_note` are not actually truncated in the live JSON (BASELINE.md showed `...` truncations).
- **Schema bump:** safe to bump 5.2.0 → 6.0.2 once the above edits land.

## Out-of-scope follow-ups (next batch)

- Add a CYP3A4 sibling rule for bupleurum_root (better-supported mechanism than CYP2D6).
- Consider adding tyramine + SSRI/SNRI rule (currently only tyramine + MAOI).
- Audit the remaining 128 baseline entries for the same NIH URL-rot pattern observed here (5/9 NCCIH/ODS URLs in this batch were 404 — link rot is systemic, not local).
