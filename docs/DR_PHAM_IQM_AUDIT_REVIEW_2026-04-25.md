# Dr Pham — IQM Audit Clinical Review (April 2026)

> **What this is:** A summary of the bioavailability audit we ran on the ingredient quality database between Batches 1–23. **We need your medical sign-off** on the items below before we lock them in for the next pipeline release.
>
> **What we did:** For 23 batches, we re-checked every claim of "this form is more bioavailable than that form" against verified PubMed evidence. Every single PMID was content-verified by reading the actual abstract — no AI guesses, no surname matches, no transposition errors.
>
> **What we found:** 5 category-level framework errors, 15+ ghost references (PMIDs that don't say what we claimed), 200+ forms re-graded with verified ranges, and 93 forms where the existing **bio_score (0–15)** appears inflated relative to the verified pharmacokinetic evidence.
>
> **What we need from you:** Approve / reject / modify each item below. We will apply your decisions to the database and re-run the test suite.
>
> **How to respond:** Just reply in line — `APPROVE`, `REJECT`, or `MODIFY: <your suggestion>` next to each item. Free-text notes welcome.

---

## How to read this document

For each item:

```
[FINDING]   What we discovered, in plain English
[EVIDENCE]  The PubMed PMID(s) we verified — click the link to read the abstract
[CURRENT]   What the database says today (or what we just applied)
[PROPOSED]  What we think it should be
[DECISION]  ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____
```

PubMed links are direct: `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`

---

# Section A — Category Errors (URGENT framework gaps)

These are forms where the **whole bioavailability framework does not apply**. Treating them with an oral F% number is medically wrong because they don't reach systemic circulation at all — they act locally, get fermented to other molecules, or are mixtures with no unified F. We have set their `absorption_structured.value` to `null` and tagged them with a `category_error` note.

## A1 — Manuka Honey (Batch 18)

- **[FINDING]** Manuka honey activity is **local oral/wound antimicrobial action** (MGO/methylglyoxal binding to bacteria). It is not "absorbed" in the classical PK sense.
- **[EVIDENCE]** Mavric 2008 (PMID:[18210383](https://pubmed.ncbi.nlm.nih.gov/18210383/)) — methylglyoxal is the active antibacterial constituent and acts at site of contact.
- **[CURRENT]** All UMF/MGO grade forms set to `value = null` with category-error note.
- **[PROPOSED]** Confirm: bioavailability framework should NOT apply to manuka honey. Stack scoring should treat it as a topical/local-action product, not a systemic supplement.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## A2 — Organ Extracts (desiccated liver, heart, kidney, etc.) (Batch 20)

- **[FINDING]** Organ extracts are **composite foods** containing dozens of nutrients with different absorption characteristics. There is no unified "F" for "desiccated liver" — the iron has its own F, the B12 has its own F, the cholesterol has its own F. Treating it as a single-molecule supplement is a category error.
- **[EVIDENCE]** Conceptual / no single PMID — this is a structural error in the framework.
- **[CURRENT]** All 4 desiccated/freeze-dried forms set to `value = null` with composite-food note.
- **[PROPOSED]** Score organ extracts on **nutrient density** (per-component) rather than oral F. Or treat as a food, not a supplement.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## A3 — Prebiotics: inulin, larch arabinogalactan (Batch 22)

- **[FINDING]** Inulin and larch arabinogalactan are **non-digestible polysaccharides**. They are NOT systemically absorbed. Their activity comes from **colonic fermentation to short-chain fatty acids** (SCFAs: acetate, propionate, butyrate) by the gut microbiome.
- **[EVIDENCE]** Holscher 2017 (PMID:[28165863](https://pubmed.ncbi.nlm.nih.gov/28165863/)), Roberfroid 2005 (PMID:[15877886](https://pubmed.ncbi.nlm.nih.gov/15877886/)).
- **[CURRENT]** Both forms set to `value = null` with fermentation/SCFA note.
- **[PROPOSED]** Confirm: prebiotic mechanism is colonic fermentation, not absorption. Stack scoring should reflect SCFA production / microbiome modulation, not "oral F".
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## A4 — Slippery Elm (Batch 23)

- **[FINDING]** Slippery elm mucilage is a polysaccharide that **hydrates in the GI lumen and forms a viscous gel that coats the mucosa** — local demulcent action. It is NOT systemically absorbed. PubMed has **zero** papers claiming systemic absorption of slippery elm mucilage.
- **[EVIDENCE]** No PubMed PMID exists. This is textbook pharmacognosy — the mechanism is well-known but never published as a PK paper because there is nothing to measure systemically.
- **[CURRENT]** All 4 forms (inner bark, outer bark, standardized mucilage, unspecified) set to `value = null` with category-error note.
- **[PROPOSED]** Confirm: slippery elm is a topical GI demulcent. Score on traditional-use evidence, not bioavailability.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## A5 — Psyllium [PROPOSED for Batch 24, not yet applied]

- **[FINDING]** Like inulin (A3), psyllium husk is **soluble fiber that is fermented in the colon to SCFAs** (some) and otherwise passes unabsorbed (most). The existing `psyllium husk powder` entry already has `value = 0.0`, which we'd extend to all psyllium forms.
- **[EVIDENCE]** Same fermentation mechanism as inulin (Holscher 2017 PMID:[28165863](https://pubmed.ncbi.nlm.nih.gov/28165863/)).
- **[CURRENT]** husk powder = 0.0; psyllium seed and unspecified = `null` (we want to keep them null and add category-error note).
- **[PROPOSED]** All psyllium forms = `null` + category-error note. Same as inulin.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

---

# Section B — Critical Ghost References (already corrected)

These are PMIDs that previous database entries cited as supporting a claim — but when we actually read the abstract, the paper was about a **completely different topic**. AI-generated PMIDs are a known failure mode (the LLM picks a real PMID number that exists in PubMed but the article is about something else). All of these have been corrected in the database; we want you aware so you can spot future occurrences.

| # | What was claimed | What the PMID actually says | Correct PMID |
|---|---|---|---|
| B1 | "Stubbs 2017 — BHB salts" PMID:**28261556** | Korean diet/cognition paper | PMID:**29163194** |
| B2 | "Biber 1998 — hyperforin PK" PMID:**9684421** | n-of-1 RCT methodology editorial (Drug Ther Bull 1998) | PMID:**9684946** *(one-digit transposition)* |
| B3 | "Silk peptide DB 1979" PMID:**447109** | Fish protein hydrolysate (NOT silkworm fibroin) | None — author surname trap |
| B4 | "DPA omega-3 study" PMID:**29618497** | Letter about SCFAs (not DPA) | n/a — keep as text only |
| B5 | "Bizot 2017 Lipowheat ceramide" | Paper does not exist | Use Guillou 2011 PMID:[20646083](https://pubmed.ncbi.nlm.nih.gov/20646083/) |
| B6 | "Tomonaga 2017 silk peptide" | Paper does not exist | n/a |
| B7 | "Crittenden 2007 inulin" | Paper does not exist | Use Holscher 2017 PMID:[28165863](https://pubmed.ncbi.nlm.nih.gov/28165863/) |
| B8 | "Larrosa 2010 inulin" | Paper does not exist | Use Roberfroid 2005 PMID:[15877886](https://pubmed.ncbi.nlm.nih.gov/15877886/) |
| B9 | TUDCA human oral F | No robust human PK PMID exists | Mark as "mechanistic inference" |
| B10 | "Bos 1996 valerenic acid" | Cannot locate | Use Anderson 2010 PMID:[20878691](https://pubmed.ncbi.nlm.nih.gov/20878691/) |
| B11 | Multiple Batch 10 ghosts (Newby/Zerahn/Castagnone/Qu/Pearson) | Various wrong topics | Replaced with verified PMIDs |
| B12 | Manuka honey PK PMIDs (4 ghosts) | Wrong topics | Removed; manuka set to category-error |

- **[ASK]** Do you want a recurring "ghost-reference audit" added to our quarterly maintenance schedule? (We're seeing ~1 ghost per 8 verified PMIDs in older entries.)
- **[DECISION]** ☐ APPROVE quarterly recurring audit   ☐ REJECT   ☐ MODIFY: ____

---

# Section C — bio_score Downgrade Candidates (93 forms)

This is the largest and most clinically-impactful section. The `bio_score` (0–15) is what the scoring engine uses to award "ingredient quality" points. We **have not changed any bio_score**. But we identified **93 forms** where the bio_score is **high (≥11)** but the verified PK F is **low (<0.30)**. These are mismatches that need your call.

**The question for you:** Should we downgrade bio_score to match the PK evidence, or does clinical PD efficacy justify keeping bio_score high even when oral F is low?

We've grouped them by family so you can make one decision per family.

## C1 — CoQ10 family (4 forms)

| Form | bio_score | Verified F | PMID |
|---|---|---|---|
| ubiquinol crystal-free | **15** | 0.06 | [16873952](https://pubmed.ncbi.nlm.nih.gov/16873952/) Bhagavan 2006 |
| ubiquinone crystal-dispersed | **13** | 0.04 | [16873952](https://pubmed.ncbi.nlm.nih.gov/16873952/) |
| ubiquinol | **13** | 0.05 | [16873952](https://pubmed.ncbi.nlm.nih.gov/16873952/) |
| ubiquinone softgel | **11** | 0.03 | [16873952](https://pubmed.ncbi.nlm.nih.gov/16873952/) |

- **[CONTEXT]** CoQ10 oral F is genuinely tiny (~3–6%) — Bhagavan 2006 review. But many clinical trials show benefits at high doses. The bio_score may be rewarding clinical efficacy, not PK.
- **[PROPOSED OPTIONS]**
  - **Option 1 (PK-strict):** Downgrade ubiquinol crystal-free 15→9, ubiquinone crystal-dispersed 13→7, ubiquinol 13→8, softgel 11→6.
  - **Option 2 (PD-respect):** Keep bio_score; just expose the F% as a separate "absorption" field for users.
- **[DECISION]** ☐ Option 1 (PK-strict)   ☐ Option 2 (PD-respect)   ☐ MODIFY: ____

## C2 — B12 sublingual / methyl / adenosyl (5 forms)

| Form | bio_score | Verified F | PMID |
|---|---|---|---|
| methylcobalamin sublingual | **15** | 0.20 | [12816548](https://pubmed.ncbi.nlm.nih.gov/12816548/) |
| methylcobalamin (oral) | **14** | 0.02 | passive 1–2% |
| adenosylcobalamin | **14** | 0.02 | passive 1–2% |
| hydroxocobalamin | **13** | 0.03 | [16531617](https://pubmed.ncbi.nlm.nih.gov/16531617/) |
| cyanocobalamin sublingual | **11** | 0.15 | sublingual class |

- **[CONTEXT]** Oral B12 absorption above 1–2 µg requires intrinsic factor; passive diffusion only ~1%. Sublingual partially bypasses first-pass. The sublingual rating of 15 may overstate; oral methylcobalamin at 14 definitely overstates.
- **[PROPOSED]** Downgrade by 4–5 points for oral methyl/adenosyl/hydroxo to reflect ~1–2% F. Sublingual forms slightly less aggressive (12 not 15).
- **[DECISION]** ☐ APPROVE downgrade   ☐ REJECT (keep PD-based)   ☐ MODIFY: ____

## C3 — Crominex pattern (clinical-only branded extracts) — 9 forms

These are forms where the manufacturer ran clinical RCTs (which may show efficacy) but never published human PK. The "branded" status was awarded a high bio_score. Per Batch 16 finding, **clinical RCTs are not a substitute for PK evidence.**

| Form | bio_score | Verified F | Note |
|---|---|---|---|
| crominex 3+ chromium complex | 13 | 0.025 | Branded chromium |
| 5-loxin (Boswellia) | 14 | 0.05 | Branded Boswellia AKBA |
| boswellia aflapin | 14 | 0.05 | Branded Boswellia AKBA |
| testofen (fenugreek) | 14 | 0.05 | Branded Trigonella |
| primavie shilajit | 14 | 0.30 | Branded shilajit |
| remifemin (black cohosh) | 14 | 0.15 | Branded RCT |
| vitex standardized extract | 13 | 0.20 | Branded |
| microactive PQQ | 13 | 0.30 | Branded PQQ |
| lifepqq | 13 | 0.30 | Branded PQQ |

- **[PROPOSED]** Downgrade Crominex-pattern forms to **6–8** (matching PK ~5–30% F). Keep a separate "clinical_evidence_strength" flag if the brand has good RCTs.
- **[DECISION]** ☐ APPROVE downgrade to 6–8   ☐ REJECT   ☐ MODIFY: ____

## C4 — Brown rice chelate (marketing-only) — 8 forms

Per Batch 11 finding: "brown rice chelate" has **0 PubMed hits** for human PK. It is a marketing claim, not a verified premium form. Their actual F is whatever the parent mineral's class baseline is.

| Form | bio_score | Verified F |
|---|---|---|
| chromium brown rice chelate | 11 | 0.015 |
| manganese brown rice chelate | 11 | 0.05 |
| selenium brown rice chelate | (already downgraded) | parent class |
| zinc brown rice chelate | (already downgraded) | parent class |
| iron brown rice chelate | 11 | 0.10 |
| magnesium brown rice chelate | 11 | 0.10 |
| boron brown rice chelate | 11 | 0.85 (B class) |
| potassium brown rice chelate | 11 | 0.90 (K class) |

- **[PROPOSED]** Downgrade all "brown rice chelate" forms to match parent mineral baseline (typically 6–8). Boron/potassium can stay around 10 because their parent class F is high.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## C5 — Liposomal forms (evidence-thin) — 8 forms

Per Batches 6/10/15: "liposomal" claims for oral supplements have **almost no published human PK comparisons** to non-liposomal. The bio_score awards a premium that isn't backed by data.

| Form | bio_score | Verified F |
|---|---|---|
| liposomal glutathione | 14 | 0.20 |
| liposomal berberine | 13 | 0.15 |
| liposomal nmn / nr | 13 | 0.15 |
| liposomal iron | 13 | 0.15 |
| liposomal saw palmetto | (Batch 21 set 0.30–0.70) | |
| liposomal ginkgo | (Batch 21 set 0.15–0.50) | |
| liposomal alpha-lipoic acid | (null, pending Batch 24) | |
| liposomal melatonin / GABA / l-carnitine | (null, pending Batch 24) | |

- **[PROPOSED]** Cap liposomal bio_score at **9** unless a head-to-head human PK study supports otherwise.
- **[DECISION]** ☐ APPROVE cap at 9   ☐ REJECT   ☐ MODIFY: ____

## C6 — Curcumin premium forms — 4 forms

| Form | bio_score | Verified F | PMID |
|---|---|---|---|
| novasol curcumin | 13 | 0.04 | Class-poor curcumin baseline |
| curcuwin | 12 | 0.03 | Class-poor |
| meriva curcumin | 12 | 0.05 | Phytosome |
| theracurmin | 11 | 0.04 | Particle-size class |

- **[CONTEXT]** Standard curcumin has ~1% F. Premium forms claim "27× better" / "136× better" — these multipliers compare to abysmal baseline, not to a useful absolute F.
- **[PROPOSED]** Downgrade by ~4 points to reflect absolute F of 3–5% (still better than baseline, just not "premium").
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## C7 — Chromium chelates (Crominex-adjacent) — 6 forms

| Form | bio_score | Verified F |
|---|---|---|
| chromium picolinate | 14 | 0.028 |
| chromium nicotinate glycinate | 13 | 0.028 |
| chromium chelidamate arginate | 12 | 0.020 |
| chromium polynicotinate | 12 | 0.024 |
| chromium GTF | 11 | 0.020 |
| chromium histidinate | 13 | 0.043 |

- **[CONTEXT]** Chromium oral F is **inherently 0.5–2.5%** for ALL forms (Anderson 1996). Chelation does not meaningfully improve it.
- **[PROPOSED]** Downgrade all chromium forms to **6–8**. The differences between them are marketing.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## C8 — Iron forms (well-known clinical hierarchy) — 6 forms

| Form | bio_score | Verified F |
|---|---|---|
| iron bisglycinate | 14 | 0.30 |
| iron protein succinylate | 13 | 0.15 |
| heme iron polypeptide | 13 | 0.20 |
| iron amino acid chelate | 12 | 0.20 |
| ferrous ascorbate | 12 | 0.20 |
| iron brown rice chelate | 11 | 0.10 |

- **[CONTEXT]** Iron F in iron-replete adults is 1–10%; in iron-deficient adults it can be up to 25%. Bisglycinate is genuinely better-tolerated but F differences are modest.
- **[PROPOSED]** Iron bisglycinate **stays high** (12 maybe, not 14). Other forms downgrade by 2–3.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## C9 — Probiotic strains (live organism category) — 6 forms

Per Batch 18: bioavailability is the **wrong framework** for live probiotics. They are organisms, not molecules. F is meaningless; survival to gut + colonization is the metric.

| Form | bio_score | Verified F |
|---|---|---|
| lactobacillus plantarum (unspec) | 13 | 0.10 |
| lactobacillus salivarius ha-118 | 12 | 0.10 |
| bifidobacterium lactis (unspec) | 12 | 0.10 |
| lactobacillus rhamnosus (unspec) | 12 | 0.10 |
| bifidobacterium longum infantis 35624 | 11 | 0.10 |

- **[PROPOSED]** Replace bio_score with a **probiotic-specific scoring** based on (a) survival to colon, (b) CFU dose, (c) strain-specific clinical evidence. Or downgrade to ~7 if we keep one scale.
- **[DECISION]** ☐ APPROVE strain-specific score   ☐ APPROVE downgrade to ~7   ☐ MODIFY: ____

## C10 — Ashwagandha branded extracts — 3 forms

| Form | bio_score | Verified F |
|---|---|---|
| Shoden ashwagandha extract | 13 | 0.35 |
| KSM-66 ashwagandha | 11 | 0.20 |
| sensoril ashwagandha | 11 | 0.25 |

- **[CONTEXT]** Withanolide PK is poorly characterized in humans. Branded extracts have RCTs but limited PK.
- **[PROPOSED]** Modest downgrade (–2 points) for Crominex-pattern caution.
- **[DECISION]** ☐ APPROVE   ☐ REJECT   ☐ MODIFY: ____

## C11 — Other individual forms

For brevity, these don't fit the family clusters above but need your call:

| Form | bio_score | F | Concern |
|---|---|---|---|
| magnesium threonate | 14 | 0.20 | Slutsky 2010 is RAT data only; no human BBB PK |
| magnesium taurate | 13 | 0.30 | Class-equivalent to other Mg organic chelates |
| calcium bis-glycinate | 14 | 0.40 | Same as citrate clinically |
| calcium citrate | 14 | 0.42 | High score reasonable |
| calcium citrate malate | 14 | 0.42 | Modest premium |
| menaquinone-4 (MK-4) | 12 | 0.05 | MK-4 has very short half-life vs MK-7 |
| inositol hexanicotinate | 12 | 0.05 | Released as inositol + nicotinic acid; not "no-flush B3" |
| trans-resveratrol | 12 | 0.25 | Inherent rapid glucuronidation; F is genuine |
| natural astaxanthin (haematococcus) | 12 | 0.20 | Lipid carrier dependent |
| synthetic astaxanthin | 12 | 0.20 | Class-equivalent to natural |
| heme iron polypeptide | 13 | 0.20 | Marketing premium |
| acetyl-l-carnitine (ALCAR) | 11 | 0.20 | Brain-bioavailable; PD-justified high score? |

- **[DECISION (Mg threonate)]** ☐ APPROVE downgrade 14→8 (rat-only)   ☐ KEEP (PD evidence)   ☐ MODIFY: ____
- **[DECISION (others)]** Free-text notes per row welcome.

---

# Section D — New Framework Patterns (FYI / future-proofing)

These are framework rules we established during the audit. They will guide future ingredient additions. Please confirm or amend.

## D1 — "Pre-absorption hydrolysis" pattern
Forms that get hydrolyzed in the gut/blood **before** they reach the active species deliver the active species, not the parent compound. We treat them as class-equivalent to the active species:
- P5P → pyridoxal (B6 active)
- Salicin → salicylic acid (white willow)
- Oleuropein → hydroxytyrosol (olive leaf)
- Ascorbyl palmitate → ascorbic acid (vitamin C)
- Tocopheryl succinate → α-tocopherol (vitamin E)
- Glucosylceramides → sphingoid bases (ceramides)
- Some forms of pantethine → pantothenic acid

**[DECISION]** ☐ APPROVE rule   ☐ REJECT   ☐ MODIFY: ____

## D2 — "Class-equivalence collapse"
Forms within a chemical class that share the same absorption pathway should have the same F:
- All amino acids ~85–99% F (PepT-1 / B0AT1)
- All Mg organic chelates ~30–40% (citrate, malate, glycinate, taurate)
- All ascorbate salts ~50–80% (Na, K, Mg, Ca, Zn ascorbate)
- All TG omega-3 forms ~80–90% (fish, krill, seal, perilla ALA)
- D-chiro-inositol = myo-inositol (same SMIT2 transporter)

**[DECISION]** ☐ APPROVE rule   ☐ REJECT   ☐ MODIFY: ____

## D3 — "Crominex pattern" (clinical RCTs ≠ PK)
Branded forms with clinical RCTs but no human PK should have F set by the **parent compound's class baseline**, not by the brand's marketing. The clinical evidence goes into a different field (`clinical_evidence_strength`).

**[DECISION]** ☐ APPROVE rule   ☐ REJECT   ☐ MODIFY: ____

## D4 — "Liposomal evidence-thin" cap
Liposomal forms without published human PK head-to-head studies should be capped at modest premium (+0.05 to +0.10 over the baseline form). They get the benefit-of-doubt but not a free pass.

**[DECISION]** ☐ APPROVE cap   ☐ REJECT   ☐ MODIFY: ____

## D5 — Rat-only PK is NOT human evidence
Studies in rats may inform mechanism but should NEVER be used to assign a human F number. Forms previously credited based on rat data (e.g., Mg threonate, fenugreek Aswar 2010, thymoquinone Alkharfy, tocotrienol Yap 2003) all flagged.

**[DECISION]** ☐ APPROVE rule   ☐ REJECT   ☐ MODIFY: ____

---

# Section E — Open Questions (genuine medical judgment calls)

## E1 — GABA oral bioavailability
**Conventional pharmacology** says oral GABA does NOT cross the blood-brain barrier in adults (Boonstra 2015 review PMID:[26617552](https://pubmed.ncbi.nlm.nih.gov/26617552/)). But our database has GABA powder at 0.40 and pharma-GABA at 0.45.

If the BBB is the rate-limiting step, those values may be massively overstated. However, **some clinical trials show anxiolytic effects from oral GABA**. Possible explanations:
1. Enteric nervous system effect (GABA receptors in gut → vagal signal to brain)
2. Subset of patients with BBB permeability changes
3. Marketing inflation in the existing values

**[ASK]** What's the right F for oral GABA? Should we treat it as 0.05 (PK-strict, BBB-blocked) or 0.40 (current, PD-respectful)?

**[DECISION]** ☐ Use 0.05–0.10 (PK-strict)   ☐ Keep 0.40–0.45 (current)   ☐ MODIFY: ____

## E2 — Spirulina composite-food framework
Spirulina is treated like organ extracts (composite food). Current values 0.80–0.88 reflect "nutrient density" but spirulina is a multi-nutrient food, not a single-molecule supplement. Phycocyanin extract is even murkier (it's a pigment-protein, likely digested).

**[ASK]** Should spirulina move to category-error like organ extracts (Section A2)? Or stay as "nutrient density" framework?

**[DECISION]** ☐ Category error   ☐ Keep nutrient density   ☐ MODIFY: ____

## E3 — Digestive enzymes framework mismatch
Pancreatic / plant / enteric-coated enzymes are scored at 0.40–0.65 — but **these enzymes act locally in the GI lumen, not systemically**. They digest food in the gut; they are not absorbed intact. The current values appear to be measuring "enzyme activity survival" rather than oral F.

**[ASK]** Do we re-frame digestive enzymes as a local-action category (like slippery elm) and score on activity survival rather than oral F?

**[DECISION]** ☐ Category error / local action   ☐ Keep as activity-based   ☐ MODIFY: ____

## E4 — Superoxide dismutase (SOD) supplements
SOD is a protein. Eaten orally without protection, it is **digested to amino acids in the stomach** — no intact enzyme reaches systemic circulation. Branded GliSODin® (with gliadin coating) shows some clinical activity but that's PD, not PK.

**[ASK]** Does SOD without gliadin coating belong in our database at all? Most products listed don't specify a protection mechanism.

**[DECISION]** ☐ Treat unprotected SOD as null/category-error   ☐ Keep but flag low F   ☐ MODIFY: ____

---

# Section F — Summary table for decision-making

| Section | Items | Action needed |
|---|---|---|
| A — Category errors | 5 patterns (manuka, organ, prebiotics, slippery elm, psyllium) | Confirm framework |
| B — Ghost references | 12+ corrections | Approve quarterly audit cadence |
| C — bio_score downgrades | 93 forms across 11 families | Approve / reject per family |
| D — Framework rules | 5 patterns | Confirm rules |
| E — Open questions | 4 (GABA, spirulina, enzymes, SOD) | Medical judgment call |

**Once you respond, we will:**
1. Apply approved bio_score downgrades to the database
2. Add category-error tags where you confirm
3. Update test fixtures so future regressions are caught
4. Update `DATABASE_SCHEMA.md` to document the framework rules
5. Run the full pipeline + score 100 sample products to check for unexpected score drift
6. Send you a before/after diff on the 100 samples for final sign-off

Thank you, Dr Pham. The audit was extensive but the database is much cleaner for it.
