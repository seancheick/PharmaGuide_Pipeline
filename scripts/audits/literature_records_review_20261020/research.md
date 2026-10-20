# Literature-record content review — receipt (2026-10-20)

Scope: every study row in `scripts/data/literature_evidence_records.json` (237 records with qualifying studies,
282 rows, 264 PMIDs) read against its PubMed title + abstract (fetched 2026-10-20 via eutils efetch;
`~/pg_quality/literature_record_scan_20261020/abstracts.json`), and against PMC full text where the abstract
lacks a figure and a PMC copy exists (PMCID cited in the row). Follow-up of PR #212 (tart cherry).

## Result of the read

| Records | Count |
|---|---|
| Consistent with the article (incl. the curated October block and tart cherry, fixed in #212) | 82 |
| Batch A: Evidence determination changes (this PR) | 39 |
| Batch B: study facts corrected, determination unchanged (stacked PR) | 116 |

Defect classes found: rows citing a different paper than the trial they describe (review, in-vitro or animal
study under a trial's figures); sample sizes, doses, durations and outcomes the paper does not report;
`studied_dose_exposure` and `applicability_decision` thresholds no cited source states; evidence for one
preparation (combination, food, juice/tea, topical, other species or plant part, whole protein) credited to
another. The 10-item hand sample in the scan README (3 format-only, 5 unverifiable, 2 contradicted) understated it.

## Rules applied

- A study row states only what its article reports; a figure the abstract (or cited PMC full text) does not
  report is removed, never kept because it looks right.
- `studied_dose_exposure` keeps only doses a cited study used, in its unit; otherwise `{}` (the curated-record form).
- A1 — preparation mismatch: juice/food/tea, combination product, topical route, other species or plant part,
  or whole protein evidence does not transfer to the canonical's supplement form (goji / tart cherry precedent,
  DMAE combination precedent) → `effect_direction: applicability_unestablished`.
- A2 — direction contradicted by the article → the direction the article reports.
- A3 — no human trial remains once the row is read for what it is → `verification_result:
  verification_failure_unresolved` (existing vocabulary; the resolver's "literature verification pending",
  Evidence copy "review pending"). Real but non-trial citations stay, labelled by design, `scoring_eligible: false`.
  Exception kept: negative safety signals from non-trial sources (graviola, artemisinin, kava, aloe ferox) stay
  negative, matching the curated precedent.
- A wrong-PMID row whose described trial exists was re-pointed only after a PubMed search and a content read
  of the new abstract (batch B: goldenseal 17495878, dong quai 9418683, chitosan 18646097, ipriflavone 11255425).
  PMIDs recalled from memory were all wrong when checked and were not used.
- Applied by `apply.py` from the explicit per-record patches in `spec_a.py` / `spec_b.py`; nothing fetched or
  generated during the apply. `data_batch.py check --expect` proves the diff equals the spec.

## Owner findings (not changed here)

- `scripts/api_audit/verify_all_citations_content.py` has no `FILE_CONFIGS` entry for
  `literature_evidence_records.json` ("no config for file"), so these citations were never content-verified;
  `verify_literature_records.py` checks existence/topic only. This is how the wrong-paper rows passed.
- `evidence_resolver.py` pumpkin gate treats "oil" in a label as a material match to "purified oil trials", but
  the only cited trial (GRANU, PMID 25196580) had no oil arm and its extract arm was null. The broccoli gate's
  premise ("purified extract trials") rests on a record that cites only a narrative review.
- `myricetin`: `effect_direction: negative` with no studies (pre-existing `verify_semantic_applicability` violation).
- graviola neurotoxicity has no safety-owner rule (harmful_additives / banned_recalled); its only signal is this
  Evidence record.

### Batch A — 39 records

| Record | PMID(s) | What the article reports (receipt) | Determination | Verdict |
|---|---|---|---|---|
| `l_isoleucine` | 28638350 | PMC5461297 Table 1: the 5.6 g BCAA drink held 2.6 g leucine, 1.4 g isoleucine, 1.6 g valine (not 2:1:1); one post-exercise dose in 10 trained men; myofibrillar MPS +22% vs placebo. Mixed-BCAA acute surrogate; SDE [1000,1500] daily not studied. | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `l_valine` | 28638350 | CONTRA PMC5461297 Table 1: valine 1.6 g (record said 1.4 g); 5.6 g BCAA drink (2.6 g Leu, 1.4 g Ile); one post-exercise dose, 10 men; MPS +22%. Mixed-BCAA acute surrogate; SDE [1000,1500] not studied. | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `ginger_extract` | 11710709, 27419081 | CONTRA material 11710709 = combination extract Zingiber officinale + Alpinia galanga (EV.EXT 77), dose 510 FT; 27419081 = ginger POWDER 1 g/d, outcome NO/hs-CRP only (no pain) -> outcome contradicted | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `l_tryptophan` | 38185736 | CONTRA 38185736 = alpha-lactalbumin review (8 studies, 20-60 g alpha-lac), not L-tryptophan 1-5 g; n350 invented; material does not transfer -> applicability_unestablished; appl ">=1000 mg/day" invented | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `cyanidin_3_glucoside` | 25833778 | CONTRA 25833778 n160 -> 58 T2D; material purified C3G -> purified anthocyanin mixture (FT: Medox); appl/sde 100 -> 160 mg twice daily (320 mg/d); mixture->single compound transfer unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `phosphatidylcholine` | 33440385 | CONTRA 33440385 = MA 3 RCTs 160 UC patients, delayed-release 30% PC lecithin; >94% PC trial failed. n30/1000 mg/12 wk invented; purified PC material contradicted -> applicability_unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `marshmallow_root` | 16391481 | CONTRA 16391481 open trial n62 combined syrup (ivy leaf extract main active + thyme + aniseed + marshmallow mucilage) 10 mL/d mean 12 d; n822/500 mg/7 d invented; combination -> applicability_unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `keratin` | 25386609 | CONTRA material: Cynatine HNS = keratin 500 mg plus vitamins and minerals (combination) -> DMAE precedent applicability_unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `winged_treebine` | 16948861 | CONTRA PMC1570348: the 'Cissus quadrangularis formulation' also contains green tea, soy, chromium, selenium and B vitamins; 514 mg twice daily; 123 participants (92 obese in 3 arms + 31 overweight). Combination. | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `magnolia_bark` | 18426577 | CONTRA Relora = Magnolia + Phellodendron blend, 250 mg tid x 6 wk, ITT 40/26 completed; cortisol NOT changed; only STATE anxiety -> combination | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `fucoxanthin` | 19840063 | CONTRA material Xanthigen = brown seaweed extract (fucoxanthin) + pomegranate seed oil combination; 8.0 mg FT; -> combination | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `fennel` | 12566188 | CONTRA 12566188 not RCT (self-controlled cycles), n 60 -> 30 analysed; dose "120 mg/day seed extract" -> 2% fennel fruit essence 25 drops q4h; "comparable" -> mefenamic more potent days 2-3; sde/appl 120 invented | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `pomegranate` | 38410857 | FT/CONTRA? MA 38410857 pooled "pomegranate in different forms", conclusion names juice; record material "extract/standardized punicalagins", appl ">=500 mg extract (or ~200 mL juice)", sde [500,1000], n=619: none in abstract | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `acai_berry` | 21569436 | CONTRA dose -> 100 g acai pulp twice daily, open-label uncontrolled pilot n10; sde 1000 wrong; goji precedent -> applicability_unestablished for powder/extract | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `chrysin` | 14977449 | CONTRA 14977449 = propolis + honey containing chrysin, urinary testosterone; 3000 mg/day chrysin, n7, aromatase/bioavailability claims FT/not in abstract; food matrix -> null does not transfer to chrysin supplement | reviewed_null → applicability_unestablished | A1 preparation mismatch |
| `cat_s_claw` | 11603848 | CONTRA material 11603848 = freeze-dried Uncaria GUIANENSIS (30 vs 15 placebo), not U. tomentosa pentacyclic-alkaloid extract; species equivalence only in vitro; dose 100 mg FT | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `wild_yam_root` | 11428178 | CONTRA material: topical cream only (no oral); topical null does not establish oral; appl diosgenin claim unsourced | reviewed_null → applicability_unestablished | A1 preparation mismatch |
| `pumpkin_seed_oil` | 25196580 | CONTRA (safety of claim) 25196580: extract 500 mg bid did NOT differ from placebo; record says significant vs placebo P=0.014 positive_moderate; no oil arm -> applicability_unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `spearmint` | 25058311 | CONTRA "vs control" -> pain fell within high-rosA group only, no between-group difference; control = commercial spearmint tea; material tea not extract | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `moringa` | 37229639 | CONTRA n 60 -> 40 T2D; 4 g/d powder 12 wk -> 20/40/60 g leaves/day 14 days; FBG not different; no significant differences after adjustment -> null; whole leaves as food | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `shiitake` | 25866155 | CONTRA material: whole dried shiitake 5 or 10 g/day as food, healthy 21-41 y, two dose arms, no placebo; not AHCC/lentinan mycelial extract; appl ">=1000 mg/day extract" invented -> applicability_unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `shiitake_mushroom` | 25866155 | CONTRA same study as R127: "/ 1000 mg extract" invented; NK-T not NK; whole dried mushrooms 5 or 10 g/day food | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `oolong_tea_leaf` | 19271168 | CONTRA uncontrolled (not RCT); 8 g oolong tea/day; "equivalent standardized extract" + appl ">=500 mg extract" invented -> tea != extract | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `dark_sweet_cherry` | 12771324 | CONTRA n 18 -> 10 women; uncontrolled single 280 g fresh Bing cherries; "equivalent anthocyanin extract" + appl ">=500 mg extract" + muscle recovery invented -> applicability_unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `olive_fruit_extract` | 23516412 | CONTRA material: olive LEAF polyphenols (51.1 mg oleuropein + 9.7 mg HT), overweight middle-aged men crossover; not fruit extract -> plant part mismatch | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `black_garlic` | 26869811 | CONTRA material: aged garlic extract (1.2 g, 1.2 mg SAC), not black/fermented garlic; "-11.5 mmHg" = responders only (overall -5.0) | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `undecylenic_acid` | 6987185 | CONTRA 6987185 = TOPICAL powder (2% undecylenic acid + 20% zinc undecylenate) for tinea pedis; oral 250-500 mg/day "fungal microbiome" invented -> applicability_unestablished | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `barberry_root` | 37575603 | CONTRA 37575603 schizophrenia on antipsychotics, n 88 (41/47), 3x500 mg/d x3 months; NOT effective, weight/waist higher than placebo; effect positive_moderate -> null; record dir -> null | reviewed_clinical → reviewed_null | A2 direction contradicted |
| `l_threonine` | 37004875 | CONTRA n 7 -> 11; dose -> six intakes 5-35 mg/kg/d IAAO requirement study, not efficacy; dir positive_moderate unsupported -> applicability_unestablished (methionine pattern) | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `l_carnosine` | 20091069 → none | GHOST 20091069 = narrative review of beta-alanine (Derave/Artioli 2010), not a 1000 mg/day L-carnosine RCT; n/dose/duration invented -> remove row; record has no study left | reviewed_clinical → verification_pending | A3 no verified trial |
| `l_phenylalanine` | 37629744 → none | GHOST 37629744 narrative review of depression in Parkinson's; open-label n40 100-500 mg 15 d invented -> remove row | reviewed_clinical → verification_pending | A3 no verified trial |
| `docosapentaenoic_acid_dpa` | 30716358 | GHOST 30716358 = narrative review; RCT n24/1000 mg DPA/4 wk/platelet invented -> remove row | reviewed_clinical → verification_pending | A3 no verified trial |
| `dimethyl_glycine` | 34823458 | GHOST 34823458 = DMG-in-autism review; RCT n16/1500 mg/14 d/VO2max null invented -> remove row | reviewed_null → verification_pending | A3 no verified trial |
| `boswellia_serrata_resin` | 32565872 | GHOST 32565872 = rat MIA + in vitro (LI13019F1); RCT n75/100 mg/90 d invented -> remove row | reviewed_clinical → verification_pending | A3 no verified trial |
| `perilla_oil` | 21909287 | GHOST 21909287 = narrative review of perilla fatty acids; RCT n60/3-5 g/12 wk/EPA-DHA invented -> remove row | reviewed_clinical → verification_pending | A3 no verified trial |
| `superoxide_dismutase` | 15742357 | GHOST 15742357 = animal study ("animals supplemented with Glisodin"); human RCT n40/500 mg/4 wk invented -> remove row | reviewed_clinical → verification_pending | A3 no verified trial |
| `schisandra_berry` | 18515024 | CONTRA 18515024 narrative overview of Russian research: n500, 500-1500 mg/day, multi-week invented; appl ">=500 mg/day" + sde invented | reviewed_clinical → verification_pending | A3 no verified trial |
| `schisandra` | 18515024 | CONTRA 18515024 narrative review; n250, 500-1500 mg, 2-12 wk invented (same as R38) | reviewed_clinical → verification_pending | A3 no verified trial |
| `broccoli` | 30372361 | CONTRA 30372361 short narrative review: n 250, 100 umol, multi-week, systematic_review all invented; sde 500 invented | applicability_unestablished → verification_pending | A3 no verified trial |
