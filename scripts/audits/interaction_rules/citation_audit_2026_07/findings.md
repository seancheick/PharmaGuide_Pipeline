# Interaction-rules citation audit — 2026-07-02

Full live-PubMed content-verification of every PMID in
`scripts/data/ingredient_interaction_rules.json` (191 distinct PMIDs) and the
Flutter app's `condition_thresholds.dart` (11 PMIDs). Triggered by the user
finding a wrong-topic ("ghost") PMID and demanding every identifier be
verified against the real API — no agent hearsay, no existence-only checks.

Verifier tool added (permanent gate): `scripts/api_audit/verify_interaction_rules_citations.py`
(reuses `verify_all_citations_content.fetch_articles`; the mandated content tool
did NOT cover this file because its sources are nested under
`interaction_rules[].condition_rules[]/drug_class_rules[]/pregnancy_lactation`).

Method note: the automated no-overlap heuristic has FALSE NEGATIVES (spurious
token match — e.g. osimertinib is a "tyrosine kinase" inhibitor, so "tyrosine"
overlapped and hid a ghost). A full MANUAL title review of all 191 esummary
titles was required and is the source of the off-claim list below.

## FIXED this session — total-topic ghosts (ingredient entirely absent)

Pipeline (`ingredient_interaction_rules.json`):
- blue_cohosh pregnancy_lactation: 17592099 (pravastatin/vitE/CKD trial) → 30000839 (LactMed "Blue Cohosh")
- DHEA pregnancy: removed 32852449 (NAMS menopause GSM statement); MedlinePlus DHEA monograph remains
- red_clover **bleeding** sub-rule: 9464451 (soybean anti-thyroid isoflavones) → MSK red clover (bleeding). NOTE: 9464451 is CORRECT for the red_clover **thyroid** sub-rule (same TPO-inhibiting isoflavones) — left in place there.
- l_tyrosine **maois** sub-rule: 37937763 (osimertinib NSCLC trial) → 6472051 (tyrosine pressor effect, self-verified) + DailyMed ZELAPAR/selegiline label §7.5 (self-verified tyramine/MAOI hypertension)

App table (`condition_thresholds.dart`, PharmaGuide ai repo) — 8 ghosts, all replaced with live-verified authoritative sources (NIH ODS / NCCIH / MSK / verified PMID), gating thresholds left unchanged (conservative = err toward warning):
- vitamin_d/diabetes 28202713 (respiratory-infection RCT) → ODS Vitamin D. **Claim was also wrong**: ODS says NO glycemic benefit; reworded to "not a diabetes risk," kept suppress.
- inositol/PCOS 26424907 (swine slaughterhouse microbiology) → 29042448 (Unfer 2017 myo-inositol PCOS meta-analysis, verified)
- omega_3/bleeding 17353583 (pediatric leukemia) → ODS Omega-3 (soften: no clean 3 g cutoff; FDA safe ≤5 g)
- vitamin_e/bleeding 15537682 (all-cause mortality only) → ODS Vitamin E (covers 400 IU bleeding interaction + mortality)
- ginkgo/bleeding 17435408 (adolescent smoking/depression) → NCCIH ginkgo (soften to bleeding-risk-with-anticoagulants)
- curcumin/bleeding 22781239 (x-ray astronomy) → MSK turmeric (drop the unsupported 1 g/day figure)
- selenium/Hashimoto's 25038305 (pre-pregnancy obesity cortisol) → ODS Selenium (soften: mixed evidence, no routine-use support)
- vitamin_b6/anticonvulsants 21882118 (antiepileptic teratogenicity) → ODS B6 (studied dose is 200 mg, not 100; kept 100 mg gate as conservative)

Verified-clean, left as-is: app-table 28150351 (Mg/glycemia), 22318649 (Mg/BP),
22374556 (ALA T2D RCT — the earlier ghost-21134318 replacement, re-confirmed).

## GENERIC-FILLER CLEANUP (2026-07-02, all live-verified)

A `>=3 distinct ingredients` scan found 58 sub-rules whose SOLE citation was a
generic landing page that never names the ingredient (FDA "drug-interactions-
what-you-should-know" x21 ingredients, NCCIH "/health/safety" x10, LactMed
front page NBK501922 x11) — effectively unsourced warnings. Now 0 remain.

Re-sourced by cluster (each target self-verified live; LactMed NBK ids
content-checked to the right herb — they mis-map easily):
- Diabetes/glucose (aloe, fenugreek, fiber, ginseng, psyllium) -> NCCIH
  diabetes-and-dietary-supplements page; vanadyl -> PMID 37958659; psyllium/
  lithium -> PMID 1968148 (ispaghula/lithium).
- MAOI: 5-HTP -> serotonin-syndrome PMID 31523132; pressor amines
  (phenylethylamine, hordenine, tyramine-rich) -> DailyMed MAOI label.
- Pregnancy: yohimbe/dong-quai/bitter-melon/ephedra -> MSK; mugwort ->
  PMC7583039; rue -> PMID 15639078; vitamin A -> ODS Vitamin A.
- Lactation: sage NBK501816, fenugreek NBK501779, senna NBK501349, cascara
  NBK501328, aloe NBK501829, black cohosh NBK501781, caffeine NBK501467,
  St. John's wort NBK501770 (all LactMed, id-verified).
- Interactions: ginger/schisandra/berberine/ginkgo/cat's-claw -> MSK; selenium
  -> ODS Selenium; melatonin -> NCCIH melatonin; CBD -> DailyMed Epidiolex label.
- niacin diabetes/hypoglycemic rules: dropped redundant FDA filler (verified ODS
  Niacin co-source kept).

REMOVED 8 CLAIM-DUBIOUS sub-rules (no authoritative source, per live checks):
- vitamin_d / autoimmune, / nsaids, / antiplatelets, / immunosuppressants — ODS
  lists only orlistat/statins/corticosteroids/thiazides; frames vitamin D as
  protective in autoimmunity, not interacting. (anticoagulants + thiazide_diuretics kept.)
- dhea / ttc — MSK doesn't support a "trying-to-conceive" caution (pregnancy kept).
- guarana / seizure — only a multi-ingredient energy-drink case report.
- elderberry / autoimmune + immunosuppressants — MSK calls the immune effect
  "controversial"; no contraindication anywhere.

Softening still worth doing (PARTIAL per sources, low urgency): fenugreek
galactagogue evidence is weak; sage milk-reduction "purported/unstudied"; black
cohosh lactation split-opinion; senna is *acceptable* in lactation (not "avoid");
caffeine = moderation not avoid; vitamin A risk is preformed only (>10,000 IU);
melatonin "lowers seizure threshold" unproven (epilepsy caution is real);
cat's-claw hard immunosuppressant contraindication not on current MSK page;
ginkgo pre-op *timing* should cite ASA/SPAQI. 444 interaction tests pass.

---

## RESOLUTION LOG — off-claim batch (2026-07-02, all live-verified)

Second commit (off-claim batch). Final verifier state: 186 PMIDs, 4 ghost-suspect
(all verified false-positives: Morus alba, Andrographis, Schisandra, NAC —
efetch title-truncation on italic species names), 2 not-found (LactMed Bookshelf
blue cohosh 30000839 + dong quai 30000896, legitimate). 457 interaction tests pass.

RE-SOURCED (verified authoritative replacement):
- cordyceps autoimmune/immunosuppressants/anticoagulants: 37513265 -> MSK cordyceps
- chromium/thyroid_medications: 33584551 -> ODS Chromium + PMID 17725434 (verified)
- icariin heart_disease/antihypertensives: 30342950 -> MSK epimedium + PMID 18778098 (PDE5) + 15546831 (CV case)
- l_tyrosine thyroid_disorder/thyroid_medications: 33795250 -> Cleveland Clinic + PMID 39608720 (verified)
- resveratrol bleeding/anticoagulants/antiplatelets: 29737899 -> MSK resveratrol; resveratrol/pregnancy -> PMID 24563374 (verified primate study, found via live search after my first guess 24941454 proved a ghost)
- forskolin antihypertensives/anticoagulants: 38623169 -> MSK forskolin
- lions_mane/anticoagulants: 40284172 -> PMID 20637576 (verified); mechanism corrected (hericenone B acts via collagen/integrin a2b1, NOT thromboxane — the old "reduced TXB2" claim was contradicted by the source)
- vanadyl_sulfate/pregnancy_lactation: 37958659 -> ATSDR vanadium NBK592340 (animal teratogenicity + no human data)
- wild_yam pregnancy/lactation/ttc: ovariectomy PMIDs 30735081+21800902 -> MSK wild-yam
- fish_oil/antiplatelets: dropped psychiatric 35311615 (ODS + NCCIH co-sources remain)

SOFTENED (claim overstated vs source):
- senna/pregnancy: sources 36702448 (Cassiae semen) + NBK548375 (Muscle Relaxants LiverTox!) -> LiverTox Senna NBK547922 + BUMPS; mechanism reworded (BUMPS: uterine-contraction concern is theoretical + "not observed"; senna is an acceptable second-line laxative in pregnancy)

REMOVED (CLAIM-DUBIOUS — no authoritative source supports it):
- gotu_kola/bleeding_disorders: MSK documents only CYP450 + hepatotoxicity, no bleeding basis (liver + sedatives sub-rules kept)
- huperzine_a/seizure_disorder: CONTRADICTED — evidence (PMID 40140526) shows huperzine A is ANTI-seizure, not pro-convulsant (anticholinergics + PL sub-rules kept)
- pygeum/nsaids: undocumented interaction; MSK has no herb-drug section, drug refs report "no known interactions" (PL kept)

LEFT AS DEFENSIBLE (citation supports the mechanism + a valid co-source exists — reviewed, not defects):
- tribulus/liver (20667992: abstract confirms hepatotoxicity + elevated aminotransferases, not just nephrotoxicity)
- magnesium/heart (25864370 dialysis paper backs the renal-comorbidity concern; + ODS Magnesium)
- citrus_bergamot/statins (grapefruit paper 23184849 backs the shared furanocoumarin/CYP3A4 mechanism; + bergamot-specific 39517207)
- saw_palmetto/ttc (alopecia paper 30980598 demonstrates the 5-AR/DHT mechanism; + NCCIH)
- rhodiola/sedatives (26613955 IS the cited rhodiola CYP study)

STILL OPEN (generic-reference imprecision, low urgency):
- iron/thyroid_medications + fiber/thyroid_medications still cite the generic LT4-dosing review 33584551 (calcium has a specific co-source 30368654); deep-link/replace with ingredient-specific evidence.
- NBK501922 = LactMed database landing page cited for 11 herbs; deep-link each to its per-herb monograph.

---

## (historical) off-claim mismatches (right ingredient, WRONG condition/organ/context)

Lesser than total-topic ghosts but still defects: the cited paper is about the
ingredient but NOT about the sub-rule's claim. Fix one ingredient at a time,
source a paper that supports the SPECIFIC claim, content-verify via live API,
test-first. Do NOT bulk-edit.

| rule / sub-rule | PMID | real topic | mismatch |
|---|---|---|---|
| gotu_kola / bleeding_disorders | 23653088 | anxiety-disorder herb review | wrong condition |
| resveratrol / bleeding_disorders | 29737899 | cosmetic/dermatological use | wrong context |
| lions_mane / anticoagulants | 40284172 | neuroprotection review | wrong claim |
| tribulus / liver_disease | 20667992 | Tribulus **nephrotoxicity** (kidney) | wrong organ |
| icariin / heart_disease | 30342950 | icariin in the **nervous system** | wrong system |
| huperzine_a / seizure_disorder | 19370686 | Huperzine A for **vascular dementia** | wrong condition |
| wild_yam / pregnancy | 21800902, 30735081 | **ovariectomized-rat** bone/CV models | wrong population |
| forskolin / antihypertensives | 38623169 | biotech **production** of forskolin | wrong claim |
| pygeum / nsaids | 31627963 | urological efficacy review | wrong claim |
| vanadyl_sulfate / pregnancy_lactation | 37958659 | vanadium **antidiabetic** potential | wrong claim |
| fish_oil / antiplatelets | 35311615 | omega-3 in **psychiatric** disorders | wrong claim |
| magnesium / heart_disease | 25864370 | magnesium in **dialysis** | wrong context |
| rhodiola / sedatives | 26613955 | rhodiola on **CYP enzymes** | wrong claim |
| saw_palmetto / ttc | 30980598 | androgenetic **alopecia** | wrong claim |
| chromium / thyroid_medications | 33584551 | levothyroxine therapy (chromium not in title) | verify |
| citrus_bergamot / statins | 23184849 | **grapefruit**-statin interaction | wrong ingredient (analogy) |
| senna / pregnancy | 36702448 | **Cassiae Semen** (cassia seed) | related species, not senna |

## TODO — weak / imprecise (on-topic but should be strengthened)

- l_tyrosine thyroid_disorder + thyroid_medications: 33795250 ("Amino Acid
  Metabolism" generic review). Tyrosine→thyroid-hormone precursor is real;
  upgrade to a source that states the supplement caution (Cleveland Clinic
  L-tyrosine page verified live, or a tyrosine-specific review).
- cordyceps autoimmune / immunosuppressants / anticoagulants: 37513265
  ("Medicinal Mushrooms functional food review"). MSK cordyceps SUPPORTS the
  immunostimulant + anticoagulant claims (use it) but has NO autoimmune/
  immunosuppressant caution — that sub-rule needs its own verified source or a
  downgrade.
- NBK501922 cited in 11 rules = the LactMed **database landing page**, not the
  per-herb monograph. Deep-link each to its specific record (blue cohosh's is
  30000839; the others each have their own NBK id).

## Cached verified replacement sources (from live-fetched subagent quotes)

- ODS Vitamin D HP: "no significant effects on glucose homeostasis, insulin ... or hemoglobin A1c"
- ODS Omega-3 HP: "2–15 g/day EPA and/or DHA might ... increase bleeding time"; FDA safe ≤5 g/day
- ODS Vitamin E HP: bleeding effects "probably exceed 400 IU/day"; mortality risk at 400 IU (begins ~150 IU)
- ODS Selenium HP: lowers TPOAb in levothyroxine-treated but "evidence does not support the use of selenium supplementation for AIT"
- ODS Vitamin B6 HP: "pyridoxine supplementation (200 mg/day ...) can reduce serum concentrations of phenytoin and phenobarbital"
- NCCIH Ginkgo: "may increase the risk of bleeding in people who are taking anticoagulant drugs"
- MSK Turmeric: "Turmeric may increase your risk of bleeding" (preclinical + case report; no mg/day cutoff)
- MSK Red clover: "Red clover may increase your risk of bleeding"; "Anticoagulants/Antiplatelets: Preclinical studies suggest red clover may increase their effects"
- MSK Cordyceps: immunostimulant ("stimulates T helper cells ... NK cells") + "inhibits platelet aggregation" (cordycepin); NO autoimmune caution present
- PMID 29042448 (Unfer 2017): myo-inositol PCOS, significant fasting-insulin + HOMA-IR reduction
- PMID 6472051 (Conlay/Maher/Wurtman 1984): "Tyrosine's pressor effect in hypotensive rats"
