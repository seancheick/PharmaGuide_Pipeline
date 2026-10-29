# Literature-record content review — receipt (2026-10-20)

Scope: every study row in `scripts/data/literature_evidence_records.json` (237 records with qualifying studies,
282 rows, 264 PMIDs) read against its PubMed title + abstract (fetched 2026-10-20 via eutils efetch;
`~/pg_quality/literature_record_scan_20261020/abstracts.json`), and against PMC full text where the abstract
lacks a figure and a PMC copy exists (PMCID cited in the row). Follow-up of PR #212 (tart cherry).

## Result of the read

| Records | Count |
|---|---|
| Consistent with the article (incl. the curated October block and tart cherry, fixed in #212) | 82 |
| Batch A: determination corrections plus broccoli citation repair, including the NAD material hold found during integration | 40 |
| Batch B: study facts corrected without changing the determination after A; overlaps six A records | 115 + 6 |

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
  of the new abstract (batch A: broccoli 24913818, already verified in broccoli_sprout; batch B: goldenseal 17495878, dong quai 9418683, chitosan 18646097, ipriflavone 11255425).
  PMIDs recalled from memory were all wrong when checked and were not used.
- Applied by `apply.py` from the explicit per-record patches in `spec_a.py` / `spec_b.py`; nothing fetched or
  generated during the apply. `data_batch.py check --expect` proves the diff equals the spec.

## Measurement (replay.py freeze-raw → snapshot --full --blob → compare --all-paths; ~/pg_quality/literature_records_review_20261020)

Batch A: 474 frozen raw labels = 414 that carry a batch-A record's ingredient (up to 12 per record, evenly spaced over
the 1,648 corpus products those records reach) + 60 random controls touching neither batch. Base origin/main
e55b6ccef, candidate 09362edbc. 226 changed; **no score, pillar score, tier, status, safety, warning, interaction,
allergen or identity path changed; all 60 controls identical.** Every change is Evidence state or copy:

| Cause | Products | Change |
|---|---|---|
| A1 preparation mismatch | 125 | ingredient reason_code only (e.g. `literature_reviewed_human_clinical_evidence` → `literature_applicability_unestablished`) |
| A1 (chrysin, wild yam) | 14 | evidence state `evaluated_null` → `applicability_unestablished` (food-matrix / topical null does not transfer) |
| A2 barberry null | 6 + 4 | `applicability_unestablished` → `evaluated_null` (single-ingredient barberry); reason code only in blends |
| A3 review pending | 31 + 17 + 11 | `quality_assessment_status` complete → partial; evidence state → `clinical_review_not_covered` ("review pending") from `applicability_unestablished`, `evaluated_applicable` or `evaluated_null` |
| A3 review pending | 18 | readiness reason code only |

Corpus reach of the A3 "review pending" move: 366 products carry one of its 9 ingredients (l_phenylalanine and the
schisandra pair most often). These products' Evidence now reads review pending instead of a conclusion the
citations never supported; points do not move because literature records are shadow-only.

Batch B: 484 frozen labels = 424 carrying a batch-B record's ingredient (up to 4 per record) + the same 60 controls.
Base 31fc2b653, candidate 86d5aa789 (rebased unchanged to the branch tip). **0 of 484 changed in any stage**
(cleaned, enriched, scored, blob): the corrected study facts are not projected into artifacts.

## Owner findings (not changed here)

- `scripts/api_audit/verify_all_citations_content.py` has no `FILE_CONFIGS` entry for
  `literature_evidence_records.json` ("no config for file"), so these citations were never content-verified;
  `verify_literature_records.py` checks existence/topic only. This is how the wrong-paper rows passed.
- `evidence_resolver.py` pumpkin gate treats "oil" in a label as a material match to "purified oil trials", but
  the only cited trial (GRANU, PMID 25196580) had no oil arm and its extract arm was null.
- Historical October20 finding: `verify_literature_records.py` had no `--help` or dry-run and rewrote data by default. The October23 clearance batch below replaces that behavior with read-only default and explicit report/apply options.
- `myricetin`: `effect_direction: negative` with no studies (pre-existing `verify_semantic_applicability` violation).
- graviola neurotoxicity has no safety-owner rule (harmful_additives / banned_recalled); its only signal is this
  Evidence record.

## backed_clinical_studies dose-bearing entries — checked, no change

The 15 entries that carry `min_clinical_dose`, `max_studied_clinical_dose`, `dose_range` or `studied_regimens`
were checked against their cited abstracts (PMC full text for BCAA). All stated amounts match:

| Entry | Stated | Article |
|---|---|---|
| BRAND_KSM66 | 250-600 mg | 125 or 300 mg twice daily (32021735); 300 mg twice daily (23439798) |
| INGR_LACTOFERRIN | 200 mg | 100 mg twice daily (19639462) |
| BRAND_CARNIPURE | 2,000 mg | 2 g/day L-carnitine as LCLT (11788381, 20045157) |
| INGR_L_CARNITINE | 1,000-4,000 mg; peak ~2,000 | 1-4 g/day (32958033); 2,000 mg/day maximal effect (32359762) |
| BRAND_OPTIMSM / INGR_MSM | 2,000-6,000 mg | 3 g twice daily (16309928); 10 x 200 mg/day (37447322) |
| INGR_ZINC_PICOLINATE regimens | 80-92, 192-207 mg | same ranges in 28515951 (acetate/gluconate lozenges, as the notes say) |
| INGR_ACETYL_L_CARNITINE | 1,000-3,000; 1,500-3,000 mg | 1.5-3.0 g/day (12598816); 1,500-3,000 mg/day neuropathy trials (31201734) |
| INGR_BRANCHED_CHAIN_AMINO_ACIDS | 5,000-29,300 mg | 3.15-29.3 g/day; > 5 g/day more favourable for soreness (38625669, PMC11021390) |
| INGR_L_ARGININE | 1,500-12,000; >= 4,000 mg | 1.5-2 and 10-12 g/day (32370176); >= 4 g/day for SBP (34967840) |
| INGR_WHITE_KIDNEY_BEAN | 1,500 or 3,000 mg (notes) | Phaseolean 1,500 or 3,000 mg/day, 45 days (39170208) |
| INGR_D_MANNOSE regimen | 2,000 mg | 2 g daily for 6 months, null (38587819) |
| INGR_D_ASPARTIC_ACID regimens | 3,000; 6,000 mg | 3 g/day climbers (29893592); 6 g/day (28841667, 38201906); 3 and 6 g (25844073) |
| BRAND_TESNOR | 200-400 mg | 200 or 400 mg LN18178 (35129040, 35928723) |
| BRAND_SYTRINOL | 300 mg | 270 mg citrus flavonoids + 30 mg tocotrienols (17985810) |

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
| `fucoxanthin` | 19840063 | Combination weight-loss findings concern brown-seaweed extract with fucoxanthin plus pomegranate seed oil; standalone fucoxanthin also increased resting energy expenditure, a surrogate. | applicability_unestablished for transferable standalone efficacy | Preserve both source findings; no standalone weight-loss transfer |
| `fennel` | 12566188 | CONTRA 12566188 not RCT (self-controlled cycles), n 60 -> 30 analysed; dose "120 mg/day seed extract" -> 2% fennel fruit essence 25 drops q4h; "comparable" -> mefenamic more potent days 2-3; sde/appl 120 invented | reviewed_clinical → applicability_unestablished | A1 preparation mismatch |
| `pomegranate` | 38410857 | Primary full-text tables include seven extract trials; heterogeneous extract subgroup SBP benefit, nonsignificant DBP. No universal extract/punicalagin threshold established. | reviewed_clinical retained; positive_weak | Integrator corrected the initial juice-only inference; SDE cleared |
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
| `l_carnosine` | 20091069 → none | GHOST 20091069 = narrative review of beta-alanine (Sale, Saunders & Harris 2010), not a 1000 mg/day L-carnosine RCT; n/dose/duration invented -> remove row; record has no study left | reviewed_clinical → verification_pending | A3 no verified trial |
| `l_phenylalanine` | 37629744 → none | GHOST 37629744 narrative review of depression in Parkinson's; open-label n40 100-500 mg 15 d invented -> remove row | reviewed_clinical → verification_pending | A3 no verified trial |
| `docosapentaenoic_acid_dpa` | 30716358 | GHOST 30716358 = narrative review; RCT n24/1000 mg DPA/4 wk/platelet invented -> citation kept, labelled by its real design, scoring_eligible false | reviewed_clinical → verification_pending | A3 no verified trial |
| `dimethyl_glycine` | 34823458 | GHOST 34823458 = DMG-in-autism review; RCT n16/1500 mg/14 d/VO2max null invented -> citation kept, labelled by its real design, scoring_eligible false | reviewed_null → verification_pending | A3 no verified trial |
| `boswellia_serrata_resin` | 32565872 | GHOST 32565872 = rat MIA + in vitro (LI13019F1); RCT n75/100 mg/90 d invented -> citation kept, labelled by its real design, scoring_eligible false | reviewed_clinical → verification_pending | A3 no verified trial |
| `perilla_oil` | 21909287 | GHOST 21909287 = narrative review of perilla fatty acids; RCT n60/3-5 g/12 wk/EPA-DHA invented -> citation kept, labelled by its real design, scoring_eligible false | reviewed_clinical → verification_pending | A3 no verified trial |
| `superoxide_dismutase` | 15742357 | GHOST 15742357 = animal study ("animals supplemented with Glisodin"); human RCT n40/500 mg/4 wk invented -> citation kept, labelled by its real design, scoring_eligible false | reviewed_clinical → verification_pending | A3 no verified trial |
| `schisandra_berry` | 18515024 | CONTRA 18515024 narrative overview of Russian research: n500, 500-1500 mg/day, multi-week invented; appl ">=500 mg/day" + sde invented | reviewed_clinical → verification_pending | A3 no verified trial |
| `schisandra` | 18515024 | CONTRA 18515024 narrative review; n250, 500-1500 mg, 2-12 wk invented (same as R38) | reviewed_clinical → verification_pending | A3 no verified trial |
| `broccoli` | 30372361 → 24913818 | 30372361 is a short narrative review of sulforaphane: its n250 / 100 umol / multi-week / systematic-review facts are invented. Citation re-pointed to the verified broccoli sprout beverage RCT 24913818 (291 adults, 600 umol glucoraphanin + 40 umol sulforaphane daily, 12 weeks; same row as broccoli_sprout), which crude powder cannot inherit; determination unchanged. | applicability_unestablished | citation re-pointed, determination unchanged |


Batch B also carries a second pass over fields the first patches left untouched (population, material,
endpoint wording, unverified figures) in `spec_b.RESIDUAL`, including five batch-A records (cat_s_claw,
l_threonine, boswellia_serrata_resin, perilla_oil, schisandra). `apply.py b` refuses to run if any batch-B patch
changes a resolver determination.

### Batch B — 116 records

| Record | PMID(s) | What the article reports (receipt) | Determination | Verdict |
|---|---|---|---|---|
| `l_leucine` | 16507602, 24284442, 32483625 | OK (16507602 n=16 not in abstract -> FT) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `citrus_bioflavonoids` | 33141449 | CONTRA? 33141449 Cochrane phlebotonics: dose "1000 mg/day MPFF" + "3 months" not in abstract (review of many phlebotonics, MPFF not named); n 7944 vs abstract 69 RCTs / 7690 in efficacy analysis. FT | applicability_unestablished | CONTRADICTED |
| `l_glutamine` | 30108163, 32992440 | CONTRA 32992440 n=8 -> 14; dose 0.1-0.5 g/kg -> 0.3/0.6/0.9 g/kg FFM single dose. appl ">= 5,000 mg/day" -> studied 15 g/day (5 g t.i.d.). SDE 5000 basis daily not studied | reviewed_clinical | CONTRADICTED |
| `l_tyrosine` | 26424423, 10230711 | N 10230711 n=20 -> 21 (10 tyr + 11 control); dose: 5 daily drinks each 2 g -> FT; 26424423 n=390 not in abstract (narrative review) FT; appl "100-150 mg/kg" not in cited abstracts FT | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `cayenne_pepper` | 24246368, 23844093 | OK; SDE 4 mg not in sources (2 mg min; 2.56 mg/meal) MINOR | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `gamma_linolenic_acid` | 21328257, 23633319 | FT 21328257 n=387, appl ">=1,400 mg/day", sde [1400,2800] not in abstract | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `cla` | 17490954, 21990002 | FT 17490954 n=282, "12 weeks" not in abstract; 21990002 n=573, dose 2.4-6.0 g not in abstract; SDE 4000 | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `glutathione` | 24791752 → 24791752 | CONTRA second row 24791752 (n=40, erythrocyte GSH/oxidative stress null) contradicts same paper (n=54; erythrocyte GSH up, GSSG:GSH down) -> wrong-PMID row (likely Allen&Bradley 2011) remove; FT "Setria" not in abstract | reviewed_clinical | CONTRADICTED |
| `blueberry` | 30999017 | FT 30999017 n=482; appl ">=20-25 g/day powder or >=500 mg/day extract"; sde 24000 not in abstract (review: doses heterogeneous) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `flaxseed` | 24126178, 25740909 | OK; N 25740909 n=1004 FT | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `lignans` | 17987126, 32575611 | CONTRA 32575611 dose 600 -> 50 mg/day SDG; n 44 -> 46; outcome "modulation of BA" -> no intervention effects; effect positive_weak -> null; SDE 600 wrong | reviewed_clinical | CONTRADICTED |
| `cryptoxanthin` | 37242207 | CONTRA 37242207 n 32 -> 90; dose 3 and 6 mg/day; pop postmenopausal -> healthy Asian women 21-35 y; Citrus unshiu extract not in abstract; appl "standardized Citrus unshiu extract >=3 mg" unsupported | applicability_unestablished | CONTRADICTED |
| `garcinia_cambogia` | 9820262, 21197150 | CONTRA 21197150 effect null -> abstract: small significant -0.88 kg, clinical relevance uncertain; appl "meta-analysis ... no statistically significant" contradicted; n=706 FT; SDE 2800 | reviewed_null | CONTRADICTED |
| `green_coffee_bean` | 20871849, 16820341 | CONTRA 16820341 n 117 -> 28; dose basis 140 mg CGA; appl ">=400 mg/day" + sde [400,800] not in abstract; 20871849 n=142 FT | reviewed_clinical | CONTRADICTED |
| `linoleic_acid` | 23386268, 27071971 | OK (sde = DRI AI, basis says so) 23386268 effect null -> negative (same data) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `pumpkin` | 25196580 | CONTRA 25196580 n 47->1431; dose -> 5 g pumpkin seed b.i.d. or 500 mg pumpkin seed extract b.i.d.; outcome: extract = placebo; seed descriptively significant responder rate; appl premise "purified oil extract trials" wrong (no oil arm). sde 320 wrong. FINDING: evidence_resolver pumpkin gate treats "oil" as material match though no oil was studied | applicability_unestablished | CONTRADICTED |
| `rose_hips` | 18384191, 16195164 | CONTRA 18384191 = systematic review w/o pooled n/dose/duration/OA-pain result (n287, 5000 mg, 3 mo, sig pain reduction not in abstract) FT; 16195164 n 112 -> 94 (crossover); material = powder of seeds+shells of a Rosa canina subspecies | reviewed_clinical | CONTRADICTED |
| `dandelion` | 19678785 | FMT dose 8 mL TID x1 day; sde 500 mg invented | applicability_unestablished | UNVERIFIABLE FIGURE REMOVED |
| `agmatine` | 20447305 | CONTRA appl/sde 1300 = open-label lowest cohort 1.335 g; RCT 2.670 g/day 14 d -> appl/sde 2670 | reviewed_clinical | CONTRADICTED |
| `chlorophyll` | 7350215 | FT 7350215 abstract no dose/duration (1980, no PMC likely) -> remove dose/duration | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `apple_cider_vinegar` | 28292654, 14694010 | FT 28292654 n312 and "10-20 mL (~1000 mg acetic acid)" not in abstract; 14694010 no abstract FT; appl ">=1000 mg acetic acid" invented | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `goldenseal` | 32591416 → 17495878 | GHOST 32591416 = in vitro human liver microsome study; replaced by PubMed-searched, content-verified PMID 17495878 (Gurley 2008): 16 healthy volunteers, goldenseal 14 days, CYP3A inhibition (midazolam AUC 107.9 -> 175.3). Record n12/900 mg tid not in either paper. | reviewed_clinical | WRONG PMID REPLACED |
| `guarana` | 16533867 | OK; FT "9 mg caffeine" | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `olive_leaf_powder` | 21036583 | CONTRA appl ">=500 mg/day" + sde 500 -> 500 mg twice daily (1000 mg/day) EFLA943, active comparator captopril; n232 FT | reviewed_clinical | CONTRADICTED |
| `lecithin` | 21490917 | PMC3065734: thirty volunteers aged 58-70 (n30 verified); one 500 mg soy lecithin capsule daily, 2 months, uncontrolled; TC -40.7 to -42.0%, LDL -42.1 to -56.2%. | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `OI_BEETROOT_POWDER` | 40085422 | CONTRA 40085422 n178 -> 2672 unique participants (20 SR/MA, 180 studies); dose ">=400 mg" -> subgroup min 6 mmol/d (372 mg/d) chronic >3 d; outcome "oxygen cost + time trial" -> TTE improved, other outcomes (incl not listed) no sig; appl/sde 400 -> 372 | applicability_unestablished | CONTRADICTED |
| `hops` | 17486686 | CONTRA outcome 17486686 "sleep quality and slow-wave sleep" -> reduced sleep latency (primary SL2); n184 FT | applicability_unestablished | CONTRADICTED |
| `nicotinamide_riboside` | 27721479, 31278280 | CONTRA 27721479 (PMC5062546): 12 subjects, single 100/300/1000 mg doses crossover (record 1000 mg/day, 7 days). 31278280 (PMC6611812): 140 enrolled, 100/300/1000 mg/day, NAD+ +22/51/142%. | reviewed_clinical | CONTRADICTED |
| `licorice` | 21747893 | PMC3123991: GutGard glycyrrhizin <= 0.5%, flavonoids >= 10%; 50 patients randomized; 75 mg twice daily, 30 days. 'DGL' label rests on low glycyrrhizin. | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `dgl_deglycyrrhizinated_licorice` | 21747893 | PMC3123991: GutGard glycyrrhizin <= 0.5%; 50 patients; 75 mg twice daily 30 days. '55% vs 19%' not found in full text (removed); appl 760 mg and 'without hypertension risk' not studied. | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `gotu_kola` | 11666126 | n40, 4 weeks FT; single-blind | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `omega_6_fatty_acids` | 23386268 | CONTRA effect 23386268 mixed -> negative (intervention higher mortality HR1.62 P=.05; MA no benefit); study_type is RCT re-analysis + updated MA; sde 1000 invented | reviewed_clinical | CONTRADICTED |
| `nattokinase` | 26109079 | CONTRA dose "2000 FU (100 mg/day)" -> single dose 2000 FU (NSK-SD); 100 mg not stated; appl/sde 100 mg FT | reviewed_clinical | CONTRADICTED |
| `evening_primrose_oil` | 23633319 | FT dose 1000-4000 mg/day, 3-16 weeks not in abstract; else OK | reviewed_null | UNVERIFIABLE FIGURE REMOVED |
| `pygeum` | 11869585 | CONTRA dose "100 mg/day standardized lipidic extract" -> review: "varied doses and preparations" (alone or in combination); appl ">=100 mg" unsupported; dir positive_strong vs "small, short" studies FT | reviewed_clinical | CONTRADICTED |
| `rosemary` | 21877951 | CONTRA material "standardized leaf extract" -> dried rosemary leaf powder; 750 mg lowest dose positive, 6000 mg impaired | reviewed_clinical | CONTRADICTED |
| `l_cysteine` | 33105552 | CONTRA PMC7690269: GluS contains N-acetylcysteine (not L-cysteine) with glutamine, alpha-ketoglutarate, alanine, glycine; 30 adults (15 per group), 8 weeks. Record n16 / 1000 mg/day L-cysteine / 14 days not in the paper. | applicability_unestablished | CONTRADICTED |
| `globe_artichoke` | 14653829 | CONTRA dose 640 mg/day -> 2x320 mg t.d.s. (1920 mg/day); appl/sde 320/640 wrong | reviewed_clinical | CONTRADICTED |
| `uva_ursi_leaf` | 34111592 | CONTRA 34111592 = acute uncomplicated UTI, n398, UU 105 mg 3x2 tablets x5 d vs fosfomycin; fewer antibiotic courses but failed symptom non-inferiority, 8 vs 2 pyelonephritis. Record n57/800 mg/1 year/recurrent cystitis vs placebo/positive_moderate all wrong. SAFETY-BEARING | reviewed_clinical | CONTRADICTED |
| `dong_quai` | 34090852 → 9418683 | GHOST 34090852 = Angelica polysaccharide review; replaced by PubMed-searched, content-verified PMID 9418683 (Hirata 1997): 71 postmenopausal women, 24 weeks, no difference vs placebo. 4.5 g dose not in abstract (removed). | reviewed_null | WRONG PMID REPLACED |
| `aloe_vera` | 27009750 | FT dose 300 mg/day, 8 weeks, decolorized material not in abstract (8 trials heterogeneous) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `hawthorn` | 12798455 | CONTRA n 855 -> 632 in MA (13 trials met criteria); dose 160-900 mg, 8-16 wk, WS1442/LI132 FT | reviewed_clinical | CONTRADICTED |
| `oat_straw` | 26618715 | CONTRA dose 1600 -> 800 and 1600 mg single doses (800 effective, "optimal at or below 800"); outcome Stroop -> global speed, delayed word recall, Peg and Ball; n36 FT | reviewed_clinical | CONTRADICTED |
| `lion_s_mane` | 18844328 | FMT dose (4x250 mg tablets 96% powder tid); appl ">=1000 mg" + sde 1000 not studied (3000 mg only) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `butterbur` | 15623680 | OK; appl "75-150 mg/day": only 75 mg bid (150/d) beat placebo, 50 mg bid did not | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `red_clover` | 33920485 | CONTRA PMC8069620: 1179 women (1043 analysed), isoflavones 37.1-160 mg/day (mean 65.1); >=80 mg/day subgroup WMD -2.80 p=0.12 (n.s.). Record n894 / 40-80 mg/day threshold not in paper. | reviewed_clinical | CONTRADICTED |
| `grape_seed` | 33671310 | PMC7922661: 80 healthy subjects with mildly elevated BP randomized (verified); 300 mg/day Enovita 16 weeks; appl '>=150 mg proanthocyanidins' not in source. | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `l_serine` | 30626650 | CONTRA n 14 -> 18 randomized (16 completed); HSAN1 patients only, 400 mg/kg/day; appl ">=500 mg/day" + sde invented -> applicability_unestablished outside HSAN1 | reviewed_clinical | CONTRADICTED |
| `beta_glucan` | 23378458 | CONTRA n 162 -> 77 (39 Wellmune / 38 placebo) | applicability_unestablished | CONTRADICTED |
| `blood_orange_extract` | 25588369 | OK; n30 FT | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `siberian_ginseng` | 21793317 | appl ">=300 mg" + sde 300 not studied (800 mg/d only) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `borage_seed_oil` | 8214997 | CONTRA n 56 -> 37; appl ">=1000 mg borage oil (>=200 mg GLA)" -> trial 1.4 g/d GLA, authors: usual doses far lower | reviewed_clinical | CONTRADICTED |
| `goji_berry` | 18447631 | CONTRA sde [120,500] mg -> 120 is mL juice, 500 unsupported -> remove | applicability_unestablished | CONTRADICTED |
| `atp` | 28080323 | CONTRA n 16 -> 42; "15 days" -> 2 weeks; outcome -> later-bout Wingate peak power + muscle excitability | reviewed_clinical | CONTRADICTED |
| `neurofactor` | 23312069 | CONTRA n 25 -> 10 per group (FT); outcome "exosomal BDNF" -> plasma BDNF single 100 mg dose CONTRA n 25 -> 10 per group, single 100 mg dose parallel groups (not crossover); "exosomal" not stated; cognition not measured | reviewed_clinical | CONTRADICTED |
| `coffeeberry` | 23312069 | CONTRA n 25 -> 10 per group, single 100 mg dose parallel groups (not crossover); "exosomal" not stated; cognition not measured | reviewed_clinical | CONTRADICTED |
| `coffee_fruit` | 23312069 | CONTRA n 25 -> 10 per group, single 100 mg dose parallel groups (not crossover); "exosomal" not stated; cognition not measured | reviewed_clinical | CONTRADICTED |
| `pregnenolone` | 25030803 | CONTRA 25030803 schizophrenia adjunct, 120 randomized (56/55), 8 weeks; "acute crossover" wrong; MCCB null but UPSA-B functional capacity improved -> effect mixed; dose FT; pop not "adults" | reviewed_null | CONTRADICTED |
| `d_beta_hydroxybutyrate_bhb` | 29338584 | CONTRA n 15 -> 19; dose 11000 mg -> 0.38 g/kg BHB salts at 60 and 15 min pre-exercise; outcome ">1.0 mmol/L" -> 0.33-0.44 mM; appl ">=5000 mg" invented | reviewed_clinical | CONTRADICTED |
| `guanidinoacetate` | 27497517 | CONTRA n 12 -> 5 men, case study not RCT; dose 3000 mg/day -> 36 mg/kg/d 4 wk then <=60 mg/kg/d, 8 wk; outcome brain creatine only, no muscle, no creatine comparator | reviewed_clinical | CONTRADICTED |
| `feverfew` | 2899663 | CONTRA n 57 -> 72 randomized (59 analysed); material "standardized parthenolide extract" -> one capsule of dried feverfew leaves daily; dose 100 mg FT | reviewed_clinical | CONTRADICTED |
| `oregano` | 10815019 | uncontrolled 14 patients; appl ">=200 mg" invented (600 mg/d studied) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `activated_charcoal` | 3521259 | CONTRA n 8 -> 99 (30 US + 69 India); 520 mg FT | reviewed_clinical | CONTRADICTED |
| `maitake` | 19253021 | CONTRA dose 0.1-5 mg/kg twice daily; effect: both stimulatory and inhibitory, non-monotonic -> mixed; appl ">=100 mg/day" invented | reviewed_clinical | CONTRADICTED |
| `OI_SHARK_CARTILAGE` | 15912493 | OK (1 g/kg, 40 d FT) | reviewed_null | UNVERIFIABLE FIGURE REMOVED |
| `butchers_broom_root` | 12040966 | FT dose 37-75 mg bid, P<0.001 | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `cranberry_fruit` | 37068952 | CONTRA n 8611 -> 8857 (50 studies); ">=36 mg PACs" not in abstract — review found no difference between low/moderate/high PAC doses and covers juice/tablets; appl threshold unsupported | reviewed_clinical | CONTRADICTED |
| `hibiscus_extract` | 23333908 | CONTRA 23333908 = comprehensive narrative review (animal + human), not SR/MA; n390, 500-1000 mg, 4-8 wk invented; RCTs used tea or extract | reviewed_clinical | CONTRADICTED |
| `tudca` | 8674405 | CONTRA n 80 -> 24 PBC patients; dose-response of 500/1000/1500 mg, NO placebo ("compared to placebo" wrong) | reviewed_clinical | CONTRADICTED |
| `nopal` | 22805855 | CONTRA n 10 -> 6 healthy active men; dose 500 -> 1000 mg OFI before and after OGTT; pop not T2D; "lower insulin peak" -> HIGHER insulin | reviewed_clinical | CONTRADICTED |
| `celery_seed` | 35624525 | CONTRA appl/sde "75 mg twice daily" -> 1.34 g/day (4 capsules); within-group BP changes | reviewed_clinical | CONTRADICTED |
| `lychee_polyphenol` | 40887285 | CONTRA n 36 -> 66 (63 analysed); dose 100 -> 200 mg Oligonol; waist FT | reviewed_clinical | CONTRADICTED |
| `horse_chestnut_seed` | 15106197 | FT n1633, 50-100 mg escin, 2-12 wk | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `colostrum` | 21148400 | CONTRA n 16 -> 12; appl/sde 1000 mg vs 20 g/d studied (FT) | reviewed_clinical | CONTRADICTED |
| `yerba_mate_leaf` | 26408319 | CONTRA dose 1000 mg/d -> 3 g/day | reviewed_clinical | CONTRADICTED |
| `milk_basic_protein` | 17048062 | CONTRA n 30 -> 35; site calcaneus -> lumbar L2-L4 | reviewed_clinical | CONTRADICTED |
| `picrorhiza` | 9715310 | CONTRA n 38 -> 33 (15/18); material root powder capsules (picroside content), not kutkin extract | reviewed_clinical | CONTRADICTED |
| `algae_oil` | 18589030 | CONTRA n 11 -> 32; open-label vs cooked salmon (no placebo); appl ">=250 mg" invented (600 mg) | reviewed_clinical | CONTRADICTED |
| `alpha_amylase` | 30156436 | FMT dose 50 mg TID DigeZyme | applicability_unestablished | UNVERIFIABLE FIGURE REMOVED |
| `larch_arabinogalactan` | 20796315 | appl/sde 1.5 g/day -> 4.5 g/day studied | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `olive_fruit` | 39828996 | CONTRA n 1248 -> 594 (14 studies); outcome oxLDL/inflammation -> TC, TG, insulin; ">=5 mg HT" not in source; material OLE/HT/TYR supplements | reviewed_clinical | CONTRADICTED |
| `jujube` | 33385511 | CONTRA n 40 -> 12; dose 1 g/d extract -> 2 g/d encapsulated Z. spinosa granules; pop postmenopausal -> adults with insomnia; feasibility crossover; appl 250 mg invented | reviewed_clinical | CONTRADICTED |
| `turkey_rhubarb_root` | 36499011 | CONTRA dose 300 mg/d -> rhubarb extract dosed by rhein 12.5 or 25 mg/day for 30 days; PMC9738964: 59 recruited, 42 completed (record n70); outcome questionnaires on stool frequency/consistency; appl 250 mg invented. | reviewed_clinical | CONTRADICTED |
| `broccoli_sprout` | 24913818 | appl ">=250 mg" invented (beverage 600 umol glucoraphanin + 40 umol SFN) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `graviola` | 14521988 | CONTRA 14521988 = in vitro neuron culture; study_type RCT/n0 wrong; "human epidemiological" overstated ("suspected") -> correct row facts, keep unfavorable signal (note: not human) | reviewed_null | CONTRADICTED |
| `puerarin` | 22578529 | CONTRA n 20 -> 10; 4 weeks -> 1 week before a 1.5 h drinking session; outcome 3.5 vs 2.4 beers; 600 mg + vascular invented | reviewed_clinical | CONTRADICTED |
| `cocoa` | 22895979 | CONTRA study_type RCT -> Cochrane MA; dose 200-500 -> 30-1080 mg flavanols (mean 545); "small" 2-3 mmHg short-term; appl threshold invented | reviewed_clinical | CONTRADICTED |
| `citrus_bergamot` | 30501605 | CONTRA n 107 -> 60 T2D mixed hyperlipemia; 650 bid/120 d/% values FT | reviewed_clinical | CONTRADICTED |
| `coleus_forskohlii_root` | 16129715 | CONTRA outcome "significant increase lean body mass" -> trend p=0.097 | reviewed_clinical | CONTRADICTED |
| `chitosan` | 32437302 → 18646097 | GHOST 32437302 = obesity-phenotype review; replaced by PubMed-searched, content-verified PMID 18646097 (Cochrane 2008): 15 trials, 1219 participants; pooled -1.7 kg but high-quality trials minimal, unlikely clinically significant. | reviewed_null | WRONG PMID REPLACED |
| `english_ivy` | 33523253 | CONTRA 33523253 = SR (6 RCT, 1 CCT, 4 OS; mono or combination ivy), not RCT; n2045, EA 575 100-150 mg not in abstract; "effects minimal at best, uncertain clinical importance" | reviewed_clinical | CONTRADICTED |
| `eps_7630` | 24146345 | CONTRA study_type -> Cochrane SR; n1957/dose/7 d FT; liquid effective, tablets not; low/very low quality; positive_strong overstated | reviewed_clinical | CONTRADICTED |
| `ginkgo_biloba_leaf` | 25114079 | CONTRA n 2372 -> 2561 (9 trials); benefits mainly 240 mg/day (appl "120-240") | reviewed_clinical | CONTRADICTED |
| `guggul` | 12915429 | CONTRA dose "1000-2000 mg/day (75-150 mg guggulsterones)" -> 1000 or 2000 mg THREE TIMES daily (2.5% guggulsterones); LDL rose 4-5% vs placebo -5%; rash in 6 | reviewed_null | CONTRADICTED |
| `deer_antler_velvet` | 14669926 | CONTRA outcome: powder group had greater isokinetic knee extensor strength (30 vs 13%) and endurance vs placebo; extract/powder no endocrine/VO2 change -> mixed; 1500 mg FT | reviewed_null | CONTRADICTED |
| `green_tea_leaf` | 21715508 | CONTRA n 1415 -> 1136 (14 RCTs); dose "250-500 mg/day EGCG" not in abstract; beverages + extracts; material extract | reviewed_clinical | CONTRADICTED |
| `turkey_tail` | 22185453 | CONTRA outcome "immune function" not in MA (survival only, cancer patients with conventional treatment); n8009/dose/6 mo FT | reviewed_clinical | CONTRADICTED |
| `arjuna` | 9505018 | CONTRA 9505018 not RCT: 12 treated vs 12 matched controls, bark stem POWDER 500 mg 8-hourly x3 mo, adjunct; n 58 -> 24; angina fell in BOTH groups; LVEF/LV mass improved in treated only | reviewed_clinical | CONTRADICTED |
| `diosmin` | 33141449 | CONTRA Cochrane phlebotonics SR (not RCT; MPFF/1000 mg not in abstract; 11 studies hidrosmine+diosmine); outcome "pain, ulcer healing" -> oedema slightly reduced, ulcer healing little/no effect, QoL no difference, more AEs; positive_strong overstated | reviewed_clinical | CONTRADICTED |
| `ipriflavone` | 10479216 → 11255425 | GHOST 10479216 = legumes/soy overview; replaced by PubMed-searched, content-verified PMID 11255425 (Alexandersen JAMA 2001): 474 women, 200 mg tid, 36 months, no BMD/fracture effect, lymphocytopenia 13.2%. SAFETY-BEARING negative kept. | reviewed_null | WRONG PMID REPLACED |
| `nad` | 29599478 | PMC5876407: 30 randomized, 500 mg twice daily NR, 6-week crossover (verified); the ~60% rise is NAD+ in PBMCs, not whole blood (CONTRA outcome). | reviewed_clinical | CONTRADICTED |
| `PII_ARTEMISININ` | 19680221 | CONTRA overreach: CDC case report (1 patient, 100 mg artemisinin supplement, hepatitis "might have been associated", causality not established); "WHO contraindicates monotherapy due to neurotoxicity and drug resistance" not in source; appl regulatory claim unsourced | reviewed_null | CONTRADICTED |
| `artemisinin` | 19680221 | CONTRA overreach: CDC case report (1 patient, 100 mg artemisinin supplement, hepatitis "might have been associated", causality not established); "WHO contraindicates monotherapy due to neurotoxicity and drug resistance" not in source; appl regulatory claim unsourced | reviewed_null | CONTRADICTED |
| `siberian_rhubarb` | 17213754 | CONTRA outcome: primary Hamilton Anxiety Scale (MRS II secondary); 4 mg FT (1 enteric-coated tablet) | reviewed_clinical | CONTRADICTED |
| `african_geranium` | 17184981 | CONTRA 17184981 = open observational study n 2099, age-dependent solution 14 days, no placebo; "RCT n468 vs placebo" wrong | reviewed_clinical | CONTRADICTED |
| `fucoidan` | 36307493 | CONTRA n 75 -> 20 asthma patients; PMC9616827: oligo-fucoidan 550 mg x 4 tablets twice daily (4.4 g/day) for 24 weeks (record: 550 mg twice daily); outcome IgE/IL-4/IL-5 -> WBC, FEV1/FVC, IFN+ cells, IL-8. | reviewed_clinical | CONTRADICTED |
| `lumbrokinase` | 24229674 | CONTRA not double-blind (standard care control), n 310 (192/118); outcome "microvascular blood flow" -> Fg, carotid IMT/plaque, vascular events; dose FT | reviewed_clinical | CONTRADICTED |
| `maqui_berry` | 26400431 | CONTRA dose -> extract (162 mg anthocyanins) three times daily; Ox-LDL/F2-IsoP fell vs baseline (within group); TAC not in abstract | reviewed_clinical | CONTRADICTED |
| `capsaicin` | 23844093 | OK | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `diamine_oxidase` | 31807350 | CONTRA open-label pilot n 28 (not RCT n39); PMC6859183: DAOSIN capsule = 0.3 mg DAO before meals up to three times daily; SDE 1.0 mg not studied. | reviewed_clinical | CONTRADICTED |
| `lactase` | 20391953 | CONTRA n 40 -> 60 (3 arms x20, tilactase/placebo/L. reuteri); ">=4500 FCC ALU" not in abstract; appl cites EFSA opinion that is not this source | reviewed_clinical | CONTRADICTED |
| `serrapeptase` | 23380245 | CONTRA appl/outcome "withdrawn by PMDA/manufacturers", "stripped of approved indications", "post-marketing confirmatory trials" not in source; n211 FT; source: evidence insufficient, poor methodology | reviewed_null | CONTRADICTED |
| `mucuna_pruriens` | 15548480 | OK | applicability_unestablished | UNVERIFIABLE FIGURE REMOVED |
| `strontium` | 14749454 | OK | applicability_unestablished | UNVERIFIABLE FIGURE REMOVED |
| `mastic_gum` | 19961914 | OK | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |
| `d_ribose` | 17109576 | OK (open-label uncontrolled) | reviewed_clinical | UNVERIFIABLE FIGURE REMOVED |

### Integrated follow-up — existing A/B specifications

| Finding | Records | Fix |
|---|---|---|
| F1 | chitosan | `studied_dose_exposure` [1200, 4500] removed: Cochrane 18646097 gives no dose |
| F2 | coleus_forskohlii_root, atp, milk_basic_protein, mastic_gum, capsaicin, activated_charcoal, cayenne_pepper | "≥ N" thresholds no cited study sets replaced by the studied regimen (250 mg twice daily = 500 mg/day; 400 mg/day; 40 mg/day; 350 mg three times daily; 2.56 mg per meal; no dose for charcoal). Cayenne keeps the meta-analysis's own "at least 2 mg capsaicinoids before a meal". SDE in one daily basis or `{}`. red_clover, cla, OI_BEETROOT_POWDER checked: their "≥ / at least" wording is stated by the source |
| F3 | olive_fruit_extract, black_garlic, superoxide_dismutase, schisandra, shiitake_mushroom, fucoxanthin, perilla_oil, undecylenic_acid | stale `applicability_status: applicable_reviewed_trials` → `applicability_unestablished` (existing value; the resolver does not read this field) |
| F5 | research.md | PMID 20091069 is Sale, Saunders & Harris 2010 (beta-alanine review) |
| F4 | — | `verify_literature_records.py` owns `verification_result` and, if rerun, would reset the nine review-pending records to verified; `test_a_record_without_a_verified_trial_reads_review_pending` fails if that happens |

## Integrator correction to the follow-up

The seven source-confirmed regimen/copy corrections from the follow-up are folded into the existing A/B specifications. NAD+ does not inherit the nicotinamide-riboside trial: its applicability hold belongs in A, while B retains source facts. The redundant C overlay is removed; the B determination-change guard remains intact. Reference schema and source-specific endpoint checks remain enforced.

## Independent integration review and limits

All 155 changed literature records were checked individually against current primary PubMed content, with available PMC/publisher full text for claims beyond the abstract. Broccoli uses PMID24913818: 291 participants, 12 weeks, a beverage supplying 600 µmol glucoraphanin plus 40 µmol sulforaphane; urinary benzene/acrolein conjugates are surrogate outcomes. Study exposure is descriptive, not a universal effective-dose floor.

Additional corrections retain beta-glucan's 250 mg regimen; distinguish titrated 24–96 g/day shark-cartilage exposure from an efficacy threshold; retain unknown chitosan/pregnenolone doses; distinguish within-group arjuna findings; and report 72-day larch exposure. Lecithin retains the placebo group without inventing random allocation. Grape-seed primary blood-pressure outcomes were null, with exploratory subgroup findings. Leucine umbrella enrollment is not assigned an unsupported 699 participants. Rhubarb had 42 randomized/39 analyzed and derivative content expressed as rhein; red-clover review totals are separated from its hot-flush subset. Vinegar reports AUC, and blueberry is a systematic review rather than a meta-analysis. Lion’s-mane tablet mass does not establish an exact powder dose or plant part; Schisandra preparation remains unknown and review pending. Capsaicin research does not establish capsiate equivalence.

The existing A/B application reproduces every current record exactly except clock-only replacement verification timestamps. B retains its no-determination-change guard. No new clinical policy, registry, status or efficacy threshold is introduced. Primary receipts and complete per-entry dispositions remain in the durable integration audit; CI and representative replay do not establish unreviewed clinical facts.

## 2026-10-23 bounded identity and benchmark continuation

Source-content review is not clinical approval. Exact NIH DSLD label299744 identifies
Lustriva as inositol-stabilized arginine silicate plus magnesium biotinate, not keratin:
https://api.ods.od.nih.gov/dsld/s3/pdf/299744.pdf . Label336100 really prints Biotin
from Advanced Hair Complex; no hierarchy correction is justified:
https://api.ods.od.nih.gov/dsld/s3/pdf/336100.pdf . Removed only the two false Lustriva
aliases from the existing keratin form. No replacement form score, amount or benchmark.

Three retained studies incorrectly carried human_subjects_verified=true:
- boswellia_serrata_resin / PMID32565872: rats and human-derived cells, not a human trial.
  https://pubmed.ncbi.nlm.nih.gov/32565872/
- superoxide_dismutase / PMID15742357: animal supplementation experiment.
  https://pubmed.ncbi.nlm.nih.gov/15742357/
- graviola / PMID14521988: cultured mesencephalic neurons. Its negative laboratory
  finding remains negative; denying human provenance must not remove that finding.
  https://pubmed.ncbi.nlm.nih.gov/14521988/

Corrected those three flags without changing evidence dispositions, safety text or approvals.
The machine verifier no longer accepts substrings such as men inside supplementation as human
subjects. Indexed human population is required; cultured-cell indexing remains unverified for
human-subject purposes. This deliberately requires source review for unindexed or mixed studies,
not a conclusion that they contain no human evidence. Existing reviewed negative/null source
findings retain their disposition. Fail-first tests exercise the actual verifier and registry.

Private source packets under pg_quality/assessment_integrity_20261023/research retain exact
label/API captures, hashes and per-entry dispositions in identity-source-continuation.json,
botanical-identity-continuation.json and benchmark-source-continuation.json. Schisandra
PMID32260466 and Extramel PMIDs19754931/24949549 have preparation-specific review packets,
not approved general benchmarks. Existing Boswellia preparation review is reused. Kelp taxonomy,
Prunus avium routing, Vaccinium oxycoccos species and mixed grape seed/skin ownership remain
separate source/owner follow-ups; no generic alias or component proportions were invented.

Owner comparison confirms unchanged evidence-resolution results for all three corrected records;
actual299744 source alias changes from keratin to unresolved. Full rebuilt closure is pending.
No Clean, Enrich, Score, export or release run was performed. The generic changed-citation tool
selected zero citations here and is not evidence of source verification; live content reads above
and the captured per-entry receipts are the verification evidence.

## 2026-10-23 species routing and ungraded magnesium biotinate

Owner: identity_integrity::resolve_identity (ADR-0005), IQM vitamin_b7_biotin.forms,
enrich_supplements_v3 form/identity resolution and scoring_input_contract. No parallel
matcher, chemical registry, clinical approval, inferred amounts or score calibration.

NIH labels294293–294296 were retrieved individually from
https://api.ods.od.nih.gov/dsld/v9/label/294296 (substitute each exact ID).
The294296 PDF previously visually inspected prints Prunus avium fruit500mg:
https://api.ods.od.nih.gov/dsld/s3/pdf/294296.pdf . Live Kew confirms the accepted
species: https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:30093848-2 .
Existing curated Prunus avium fruit-extract identity now outranks the generic
Wild Cherry grouping when the literal name is unresolved and a sole complete
botanical form establishes it. Mixed/partial declarations, independently resolved
contradictory names and interaction-rule loss retain identity_conflict. Exact source
wording is preserved. No global Wild Cherry alias or new botanical form grade.
294293–294295 already route correctly and remain43;294296 corrects black_cherry to
dark_sweet_cherry while retaining its unmapped-form hold. This is identity repair,
not a completed preparation/benchmark review.

Magnesium biotinate identity verified live on2026-10-23 against PubChem CID139593965:
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/139593965/property/IUPACName,MolecularFormula,InChI,InChIKey/JSON
Formula C20H30MgN4O6S2; InChIKey MVTGGXOWRFOAHX-VXTDSVKWSA-L. Health Canada18320
lists Magnesium biotinate as an approved chemical name with Biotin subingredient:
https://webprod.hc-sc.gc.ca/nhpid-bdipsn/ingredReq?id=18320&lang=eng&wbdisable=true .
These establish chemistry, not human absorption equivalence, effectiveness or approval.
The distinct IQM source form has bio_score=null and unknown absorption. Parent-scoped
form recognition cannot redefine a standalone source compound as the delivered nutrient.
A mapped null-grade form remains an unfinished assessment through the existing contract;
co-forms and branded fallbacks cannot supply its missing grade.

The2021 Kalman/Hewlings randomized90-person12-week oral Lustriva combination paper
is separate from the12-person oral-plus-topical abstract. Original full text inspected:
https://www.longdom.org/pdfdownload.php?aid=61185&download=open-access/a-randomized-doubleblind-evaluation-of-a-novel-biotin-and-silicon-ingredient-complex-on-the-hair-and-skin-of-healthy-wom.pdf .
Its title is A Randomized Double-Blind Evaluation of a Novel Biotin and Silicon Ingredient
Complex on the Hair and Skin of Healthy Women; the retrieval metadata has an unrelated
title, so the PDF content was checked. Combination findings do not isolate magnesium
biotinate or establish its numerical form quality. No efficacy credit or clinician approval
is added. Exact299744 and336100 NIH fixtures preserve their disclosed10000mcg biotin;
no magnesium/component quantity is inferred.299744 becomes mapped/ungraded;336100's
Advanced Hair Complex form remains unresolved. Both remain not_scored. Existing safety
hits, including the undisclosed magnesium source warning, remain present;299744's dose
provenance changes only its form-context text.

Fail-first regressions cover routing, contradictory species, partial/multiple forms,
warning preservation, mapped-but-ungraded readiness, null co-form arithmetic and source
preparation identity leakage. Bounded six-label owner replay is diagnostic only; no corpus
pipeline, artifact promotion or public release. Rebuilt closure and clinician reviews remain
open. Exact candidate validation and integration results are recorded in the execution LEDGER.

## 2026-10-23 preparation and benchmark review handoff

[Shareable clinical review request](CLINICAL_REVIEW_HANDOFF.md), with exact 83-record legacy
review dependencies and the separate 506-subject retained benchmark worklist. Source-context
checks use the current clinical owner; neither list creates approvals or a parallel registry.
These are retained diagnostic dependencies, not fresh corpus counts.

Kelp source labels331151/331152/331154/312063–312066 disclose Laminaria japonica Whole Grass
Extract500mg;309387 discloses Laminaria japonica Thallus Extract33.75mg beside separately
owned iodine225mcg and calcium80mg. All eight exact NIH JSON records retrieved individually
on2026-10-23; no visual PDF inspection newly claimed. Only the first three disclose10:1.
Live NCATS GSRS WE98HW412B confirms Laminaria japonica whole alga and thallus/extract names;
NLM C0696815 confirms the same species. NCBI taxonomy88149 records Saccharina japonica and
its Laminaria japonica basionym. No identifier or chemical-equivalence claim added.
Sources: https://gsrs.ncats.nih.gov/ginas/app/api/v1/substances(WE98HW412B)?view=full ;
https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=88149 ;
https://api.ods.od.nih.gov/dsld/v9/label/331151 and /309387 (each other ID independently fetched).

Owner correction: enhanced_normalizer::_single_declared_source_form_identity excluded thallus
and whole-grass wording. Existing kombu receives only the two exact source-preparation aliases;
complete single-form, no partial quantity, no nested blend, exact registry and source guards
remain. No IQM form score or botanical benchmark is created. Alias-only probing was insufficient;
source recognition and the existing complete-material owner both require correction.

Benchmark sources revisited: Schisandra32260466 and Extramel19754931/24949549 full text;
Boswellia18667054/35512759 source content and existing preparation review. No new general
benchmark is justified. Correction to the earlier packet: BOTH Extramel trials had Seppic/Bionov
support; the2014 paper separately declares no conflict. Full text inspected via Europe PMC XML
when PMC browser retrieval presented a challenge. Clinical-purpose/preparation holds remain.
Cranberry330664 and mixed grape330882 exact NIH rows reconfirm the separate-species and mixed-
component limitations. Numerical quality changes, bounded checks and integration are recorded
in the execution LEDGER; full corpus/Flutter closure remains deferred.

## 2026-10-23 clearance continuation: read-only API screening

Owner: `verify_literature_records::verify_literature_file`,
`verify_all_citations_content::fetch_articles`, `pubmed_client::parse_pubmed_article_xml`,
and `verify_clinical_trials::extract_nct_ids`. These are screening owners, not clinical
approval authorities. No curated data or scoring weights changed in this batch.

The five-source inventory (backed clinical, native strains, literature, nutrient references,
therapeutic references) requested 1,576 distinct citation identifiers. All resolved through
the existing PubMed/DOI/PMC client and its freshness-controlled cache. Identifiers include
aliases for the same paper; they must not be counted as 1,576 independent studies.
All five curated input SHA256 hashes remained unchanged. The 83 held legacy records retain
396 unique citation identifiers / 402 record-citation links and 410 frozen dependent products.
Retrieval is not content applicability, full-text review or clinician approval.

Whole literature screening inspected 808 records / 279 study rows / 261 distinct PMIDs.
It reported 618 findings: 573 records with no studies to verify, 31 human-indexing gaps,
nine correction notices and five topic-screen gaps. Zero retractions appeared in this
literature subset. Empty study lists are not evidence that a prior documented negative
finding is wrong; this verifier simply cannot certify them. No finding was auto-applied.
The broader inventory contains 42 distinct publication-notice records after PMID alias
reconciliation: 40 errata and two retraction-related records. The latter are the already
excluded lutein paper41573009 and notice42211211, not two newly discovered unsafe sources.

Coverage remains limited: full-text preparation/dose/outcome/population synthesis, all
non-PubMed nutrition authority content, historical/rejected literature references outside
qualifying_human_studies, trial-family independence, and genuine clinician approvals are
not established by this run. The generic citation gate and backed-studies gate are not
complete clinical-applicability verifiers. The existing DRI tool uses a pinned reference
comparison, not fresh authority-page verification. These are explicit remaining gates.

### Preparation packet additions; no grade or approval

- Magnesium biotinate: [2019 pharmacokinetic abstract](https://pmc.ncbi.nlm.nih.gov/articles/PMC6574044/),
  DOI10.1093/cdn/nzz031.P06-027-19, reports single-dose human exposure after magnesium
  biotinate. This is an abstract-level absorption lead, without a conventional-biotin
  comparator; it does not establish superior bioavailability, hair efficacy or a form grade.
  Primary indexed abstract was accessible; direct PMC access challenged and fullTextXML
  failed. No successful full-text API verification is claimed.
- The existing [2021 Lustriva randomized combination trial](https://www.longdom.org/open-access/a-randomized-doubleblind-evaluation-of-a-novel-biotin-and-silicon-ingredient-complex-on-the-hair-and-skin-of-healthy-women-61185.html)
  was re-read. Selected hair/wrinkle findings concern the complete combination; nail outcomes
  did not differ between groups. JDS funding and CRO employment belong in the review.
  Labels299744/336100 remain preparation/clinical-review cases, not established isolated
  magnesium-biotinate efficacy or inferred component quantities.
- [Oral plus topical experience abstract](https://pmc.ncbi.nlm.nih.gov/articles/PMC8181505/),
  DOI10.1093/cdn/nzab037_084, is a separate uncontrolled combined-route lead. It cannot
  establish oral-only effects. Direct full-text retrieval remains unverified.

### Publication notices affecting held legacy records

| Record | Original → correction | Review disposition |
|---|---|---|
| Saw palmetto |12006122 → J Altern Complement Med2006;12(2):199 | PubMed links a correction without a notice PMID; content unresolved. |
| Calcium |17720017 → Lancet2012;380(9844):806 | Notice content unresolved; do not invent an identifier. |
| Calcium |26510847 → [27401092](https://pubmed.ncbi.nlm.nih.gov/27401092/) | Correction includes additional analyses; exact numerical synthesis must use corrected paper. Current registry prose contains no obsolete percentage estimates; clinical review remains open. |
| Whey/protein |28698222 → [32943392](https://pmc.ncbi.nlm.nih.gov/articles/PMC7513243/) | Disclosure correction; incorporate author advisory-board relationship in limitations. No automatic invalidity or scoring change. |
| B. bifidum |31342226 → [34652462](https://pubmed.ncbi.nlm.nih.gov/34652462/) | Identity verified; correction scope inaccessible in this pass. |
| Omega-3 |31383846 → [34493705](https://pmc.ncbi.nlm.nih.gov/articles/PMC8423804/) | Author-name correction; clinical applicability and approval remain separate. |
| PQQ |34415830 → [35917215](https://pubmed.ncbi.nlm.nih.gov/35917215/) | Publisher describes corrected Table4; actual table/outcome impact still needs inspection. |
| Lutein |41573009 → [42211211](https://pubmed.ncbi.nlm.nih.gov/41573009/) | Retraction already explicitly excluded in current INGR_LUTEIN; no duplicate remediation. |

Native registrations NCT02974894 (299v stress/cortisol study) and NCT01773967
(LGG pediatric gastroenteritis) were retrieved through the existing ClinicalTrials client.
Their protocol populations/outcomes must not be transferred to unrelated claims. The former
has no posted results in this response; the latter has results. Neither fact supplies approval.

Audit receipts (inventory, source hashes, complete retrieved abstracts, publication notices,
literature findings and exact native registration payloads) are retained under
`.claude/state/clearance-audit/` and the durable assessment-integrity research directory.
All clinical and benchmark worklists retain their holds; none is scientifically closed merely
by these lookups. The 506-subject benchmark workload still requires owner-level applicability
and defensible numerical or completed-no-benchmark decisions. No corpus was regenerated.

### Five topic-screen findings: source-content triage

Full retrieved abstracts were read; these are not full-text applicability approvals.
Guarana [16533867](https://pubmed.ncbi.nlm.nih.gov/16533867/) is a lexical false positive
(accented guaraná), with a specific PC-102 extract and acute cognitive outcomes. The tested
doses are not a generic seed/extract benchmark. FOS [16569219](https://pubmed.ncbi.nlm.nih.gov/16569219/)
is a hyphenation/name-screen gap for short-chain fructo-oligosaccharides; microbial counts
are not proof of general symptom benefit. Its studied range must not become a universal
minimum-effective-dose threshold. Neither screen failure means the citation is unrelated.

Citrus bioflavonoids [33141449](https://pubmed.ncbi.nlm.nih.gov/33141449/) pools multiple
phlebotonic preparations; it cannot qualify an arbitrary crude citrus complex. Beetroot
[40085422](https://pubmed.ncbi.nlm.nih.gov/40085422/) reviews nitrate exposure and mixed
exercise outcomes; root-powder mass does not establish nitrate exposure. Alpha-amylase
[30156436](https://pubmed.ncbi.nlm.nih.gov/30156436/) tests a multienzyme combination;
its existing standalone-applicability hold is supported, not repaired by borrowing the
formula outcome. No source or numerical grade was altered from this triage.

The retained83-record projection finds zero mismatches or drifts among175available stored titles
across402citation links; absent stored titles are explicitly not compared.
The506benchmark projection finds341exact canonical literature records,124with study rows;
missing exact joins are not proof of missing evidence because other dose owners and aliases
still require tracing. These projections prioritize work and do not replace existing owners.

PQQ follow-up: the corrected Table4 remains inaccessible (publisher403; no accessible
repository copy located). Separately, [FDA-hosted GRN1118](https://www.fda.gov/media/173619/download),
PDF page53, describes mild events in both trial arms, whereas the original abstract says
no adverse events. This is a submitter-authored secondary account, not the corrected table
or FDA efficacy endorsement. Record the discrepancy for full-text review; do not infer
causation, invent corrected values, or repeat an unqualified no-events claim. Existing holds remain.


### Exact-species benchmark continuation — October 23, 2026

Owner: `clinical_applicability::assess_clinical_source_review` and
`scoring_v4/modules/botanical_profile::_botanical_benchmark`; existing handoff and
backlog own product dependencies. Will NOT create a registry, numeric benchmark or approval.
This batch adds source-review packets only; no runtime or curated assessment is changed.

**Kelp — labels 331151/331152/331154/312063–312066 and source 309387.**
[PMID34206160](https://pubmed.ncbi.nlm.nih.gov/34206160/),
[full text PMC8307228](https://pmc.ncbi.nlm.nih.gov/articles/PMC8307228/), methods 4.1–4.3,
results 2.3–2.5: iodine-reduced, boiled Laminaria japonica powder, approximately 6 g/day,
30 tablets/day for 8 weeks; 50 randomized overweight Japanese adults, 48 analyzed. Body-fat
benefit was observed in men; women and overall lipid results did not show equivalent
benefit. Tablet weight 500 mg is not kelp amount: tablets contain 39.3% kelp powder.
The preparation supplies measured alginate and iodine. A 500 mg extract or 10:1 ratio
alone cannot establish correspondence. Normal thyroid measures in this selected,
short-duration population do not justify universal iodine reassurance. Manufacturer/CRO
employment is disclosed. Full-text XML retrieved successfully through Europe PMC.
Disposition: this source does not establish a numerical benchmark for these exact labels;
preparation/clinical applicability remains unresolved. Clinician approval, where required,
must follow preparation correspondence; no dose, grade or warning changed.

**Sweet cherry — label 294296.**
[PMID40077655](https://pubmed.ncbi.nlm.nih.gov/40077655/),
[full text PMC11901987](https://pmc.ncbi.nlm.nih.gov/articles/PMC11901987/), methods 2.1–2.3,
results 3.2: 30-day single-blind trial, 40 completers with obesity. Each twice-daily drink
contains 50 mL concentrate plus 3 g Prunus avium powder, diluted to 200 mL. Neither powder
alone nor an unspecified extract is the tested intervention. Within-group digit-span
improvement does not establish an overall between-group effect: change in backward span
was not significant overall; subgroup findings and multiple outcomes require review.
Other cognitive tests showed no between-group advantage. The paper reuses an earlier
trial cohort (NCT05586386; recruitment 2020–2021, registration 2022); associated publications
must not count as independent replications. Full-text XML and primary indexed abstract
retrieved. Disposition: useful exact-species source, insufficient preparation correspondence
or threshold evidence for this label. Existing ungraded preparation/benchmark assessment
and applicable clinical holds remain; no generic tart-cherry evidence transfer.

**Cranberry — label 330664.**
[PMID11431298](https://pubmed.ncbi.nlm.nih.gov/11431298/), DOI10.1136/bmj.322.7302.1571:
primary indexed abstract verified through Europe PMC. 150 women with prior E.coli UTI;
open randomized study, 50 mL cranberry–lingonberry concentrate daily for 6 months, with
12-month follow-up. Fewer recurrences occurred versus no intervention at 6 months.
The indexed full-text search describes oxycoccos plus vitis-idaea; direct PMC access
challenged, Europe PMC fullTextXML returned 500, BMJ returned 403. Species attribution
therefore remains a full-text confirmation requirement, not a completed verification.
Even if confirmed, combination juice does not establish isolated oxycoccos extract
mass/PAC equivalence or a universal benchmark. Disposition: retain source lead and label
hold; do not claim absence of human research or import macrocarpon efficacy.

**Publication-notice access follow-up.**
[Correction34652462](https://link.springer.com/article/10.1007/s00394-021-02705-x)
resolves to the publisher preview, which requires subscription for the notice body.
Its clinical-content impact remains unknown. Existing B.bifidum reference-only summary
already separates CCFM16 microbiome findings from CCFM8610 symptom findings; no positive
species credit is restored. PQQ and the other inaccessible correction bodies remain open.

Verification: primary API JSON and two full-text XMLs retained in
`.claude/state/clearance-followup/`; no pipeline run. These are bounded source dispositions,
not exhaustive literature reviews, clinician sign-offs or rebuilt closure. Required next
steps: exact preparation/claim correspondence, source limitations and trial-family review,
attributable approval for affirmative contexts, then rebuilt owner/consumer verification.


### African mango source correction — October 23, 2026

Owner: `evidence_resolver::_load_literature_evidence` and existing
`literature_evidence_records.json` exposure/applicability fields. Will NOT create a
benchmark, grade, registry or clinical approval.

Entry `african_mango`, study [19254366](https://pubmed.ncbi.nlm.nih.gov/19254366/),
[primary full text PMC2651880](https://pmc.ncbi.nlm.nih.gov/articles/PMC2651880/):
methods describe IGOB131 150 mg before lunch and dinner for 10 weeks. Daily exposure
is 300 mg; the old `[150,300]` daily exposure and `>=150–300 mg/day` support language
mixed single-dose and daily amounts and asserted an untested threshold. Corrected
exposure to300mg/day and replaced threshold prose with the exact descriptive regimen
and explicit lack of minimum-dose, dose-response or other-preparation equivalence.
The trial's reported positive direction is retained, not upgraded or generalized.
Full text describes120 initially allocated and102completers, whereas abstract says102;
retained sample_size102 is now explicitly described as completers. Allocation/dropout
arithmetic is internally inconsistent, so no invented corrected enrollment is substituted.
Exact product applicability and required clinician approval remain unresolved.

Existing frozen benchmark dependencies:310617,310618,310619,310620,330138,330139,
330140,330141,339533,79524. They remain diagnostic dependencies, not newly cleared products.
Fail-first regression reproduced the150/300range;165 literature/source-owner tests pass.
Generic changed-entry citation verifier selected zero citations for this file; this is
not counted as source verification. The existing selected literature verifier inspected
one record/one PMID with zero screening findings/retractions; primary full text was read
separately for dose/counts. Data-batch exact indexed key225 check passes, one entry only.
Bounded replay and required local/whole-fast qualification are recorded in the LEDGER.
No full corpus run or release; no clinical hold was cleared by this correction.

Apple-cider-vinegar retraction screen: publisher
[retraction notice](https://nutrition.bmj.com/content/early/2025/09/23/bmjnph-2023-000823ret)
confirms trial38966098 is retracted. The current apple_cider_vinegar literature record
cites28292654 and14694010 instead; this search establishes no new defect in that record.
No retracted replacement source or weight-loss benchmark was introduced.


Additional high-exposure benchmark source checks (no curated changes):
- Pomegranate38410857: primary abstract confirms22 adult trials, mixed preparations
  and high heterogeneity. This cannot establish one punicalagin/extract benchmark.
  Extract-specific diastolic details still require accessible full tables.
- Blueberry30999017: primary indexed abstract confirms12studies across11articles,
  mostly freeze-dried blueberry, and inconsistent doses/anthocyanin exposure. Its
  cognition findings do not establish a general powder/extract dose threshold.
- Cayenne24246368: the authors themselves suggest2mg capsaicinoids for acute energy
  intake, with high heterogeneity; this is not an invented source number, but does
  not quantify crude pepper or establish long-term weight loss. Primary full text
  [23844093](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0067786),
  Dosage section, separately specifies2.56mg capsaicin per meal from red chili, not
  total capsaicinoids. Existing study prose preserves that distinction. The aggregate
  family-level exposure list is not a validated common-analyte dose-response curve;
  no active-basis reinterpretation or derived efficacy threshold was introduced.
These checks narrow remaining source work but clear no product preparation/benchmark
hold. Exact frozen dependencies remain in benchmark_review_backlog.csv.


### Same-class regimen corrections — October 23, 2026

Primary indexed abstracts retrieved through Europe PMC for each entry; full abstract
content was read against the existing study and parent-record fields. These corrections
preserve evidence direction and required clinical holds, and add no numeric benchmark.

| Entry | Verified source | Corrected interpretation |
|---|---|---|
|theobromine|[23595874](https://pubmed.ncbi.nlm.nih.gov/23595874/)|850mg/day pure theobromine was tested for4weeks; separate cocoa arms are distinct. Lipid biomarkers are not cardiovascular outcomes or a minimum-dose proof.|
|white_willow_bark|[10936472](https://pubmed.ncbi.nlm.nih.gov/10936472/)|Study row now retains both120and240mg/day salicin arms, not just240. Specific low-back-pain study cannot become an open-ended minimum for all musculoskeletal pain or crude bark mass.|
|l_ornithine|[19083482](https://pubmed.ncbi.nlm.nih.gov/19083482/)|Study was8days:2000mg/day for7days then6000mg on exercise day, as hydrochloride. Dose/duration/exposure corrected together; the complete regimen and subgroup findings do not establish a2000mg minimum.|
|maqui|[31193920](https://pubmed.ncbi.nlm.nih.gov/31193920/)|60mg/day MaquiBright for4weeks,74Japanese adults with prolonged display work. Exact preparation/regimen replaces unsupported minimum threshold.|
|royal_jelly|[31470366](https://pubmed.ncbi.nlm.nih.gov/31470366/)|1000mg/day for8weeks in200postmenopausal women. Abstract does not establish a universal standardized preparation or minimum dose; symptom findings require confirmation.|
|caralluma|[17097761](https://pubmed.ncbi.nlm.nih.gov/17097761/)|1000mg/day extract for60days with diet/activity advice. Hunger/waist changes must stay distinct from non-significant weight/BMI/body-fat/energy-intake differences; no minimum threshold.|
|ashwagandha_root|[23439798](https://pubmed.ncbi.nlm.nih.gov/23439798/)|300mg capsule twice daily gives600mg/day for60days, not a300–600mg/day minimum range. Exact preparation and chronically stressed population retained.|

Nine additional fail-first assertions reproduce threshold, omitted exercise-day dose,
and capsule/day errors;174combined literature/source-owner tests pass. Existing literature
screen selected all8changed records and retrieved all8PMIDs; it returns two human-indexing
findings for maqui and ashwagandha. Their primary abstracts explicitly describe human trial
participants, but no verifier flags were rewritten and no screening pass is claimed.
Source contents, not those indexing flags, support these bounded factual corrections.
Earlier CI40049888078 was superseded/cancelled before integration and is not a pass;
the final combined candidate receives its own checkpoint. Larger clinical and benchmark
worklists remain open; no source receipt substitutes for required clinician approval.


Final source-preparation reconciliation in the same eight-entry batch:
maqui's MaquiBright/BrightSight preparation replaces the unsupported Delphinol name.
Ashwagandha full text PMC3573577 explicitly identifies KSM-66 root-only extract,
at least5%withanolides by HPLC, so Sensoril is removed from this source description.
Royal-jelly10-HDA standardization, caralluma pregnane-glycoside standardization and
willow's exact Salix alba species were not established by the inspected abstracts;
their source descriptions now state the verified material and verification limits.
This does not change canonical identity routing or claim those preparations lack
such constituents. Five fail-first preparation assertions reproduced these unsupported
source descriptors.179combined owner/consumer checks pass. Final17raw-label comparison
spans all8subjects plus2controls (royal jelly has one representative);0errors and0full
Clean/Enrich/Score record changes. One earlier candidate capture was invalidated by a
concurrent commit; stable final capture, not the rejected receipt, supports comparison.
The intermediate source-data CI was superseded; final exact candidate qualification
is recorded below in the execution LEDGER. No clinical approval or benchmark closure.


## Consolidated completion batch — October 23, 2026

This section supersedes inherited 163 “actual-used” and incomplete 83-only workload counts.
Read-only manifest census covers 38 manifests, 15,437 products, 153 contributing record IDs,
152 curated records and 6,389 record-product dependencies. Enriched candidate matches (173 IDs)
are not proof of awarded credit. Frozen 727 cohort and original 83 records remain preserved in
clinical_review_holds.csv; its 155 union rows flag saved contributors separately. Five reference-only
withdrawals leave 147 source-eligible contributors needing attributable clinical contexts.
Generated RECOVERED_COLLAGEN_PEPTIDES_V1 is separately identified, not silently curated.

50 exact source records received factual attribution corrections. Representative primary receipts:
[sea buckthorn chicken experiment](https://pubmed.ncbi.nlm.nih.gov/23472020/),
[bilberry acute T2D crossover](https://pubmed.ncbi.nlm.nih.gov/25191571/),
[magnesium pregnancy cramps](https://pubmed.ncbi.nlm.nih.gov/22909270/),
[benfotiamine primary and secondary endpoints](https://pubmed.ncbi.nlm.nih.gov/33074237/),
[spermidine 12-month trial](https://pubmed.ncbi.nlm.nih.gov/35616942/),
[vitamin E mortality meta-analysis](https://pubmed.ncbi.nlm.nih.gov/15537682/).
Source-content screening was checked per entry against retrieved primary abstracts; full-text
access is not asserted for every source. Existing source titles/identifiers were retained and
strictly checked through verify_backed_studies_citations (50 entries, 198 PMID claims, all OK).
A bibliographic pass never substitutes for clinical-context approval.

Clinical source-integrity regressions record each corrected endpoint/design/preparation fact;
seven purpose-owner controls prove negated, null and adverse-effect text does not award unrelated
purpose credit. Trial limitations remain in notes, not deleted. Five withdrawals retain historical
sources with reference/scoring_eligible=False rather than fabricating negative efficacy grades.
No new approval or study_context was manufactured.

Benchmark CSV annotates all 506 subjects / 4,259 rows through actual alias-aware owner lookup:
43 guarded preparations; 1,771 literature-with-study; 1,206 literature-without-study;
1,239 without eligible owner. Exact canonical-only inventories give different partitions and
must not be mixed with this lookup. All remain scientifically open; absence of a benchmark is
not evidence that no benchmark exists. Preparation mismatch is not cured by a name match.
Final raw replays, qualification receipts and remaining gates are recorded in the LEDGER/handoff.

### Exact source correction register

All rows are implemented and source-screened; clinical approval and rebuilt closure remain open.

| Record | Retained source IDs | Candidate disposition |
|---|---|---|
| BRAND_SENSORIL | 27647541, 38732539 | Source scope reconciled; clinical context required |
| BRAND_BCM95 | 30975196, 33516238 | Source scope reconciled; clinical context required |
| BRAND_PYCNOGENOL | 18386255, 31585179, 31637782 | Source scope reconciled; clinical context required |
| BRAND_ASTAREAL | 22428137 | Source scope reconciled; clinical context required |
| BRAND_KANEKA_UBIQUINOL | 16919858, 32326664 | Source scope reconciled; clinical context required |
| BRAND_CREAPURE | 22971354, 24568653 | Source scope reconciled; clinical context required |
| INGR_LACTOFERRIN | 19639462, 35276902 | Source scope reconciled; clinical context required |
| INGR_PHOSPHATIDYLSERINE | 20523044, 21103034 | Source scope reconciled; clinical context required |
| BRAND_SUNTHEANINE | 22214254, 31623400 | Source scope reconciled; clinical context required |
| BRAND_OPTIMSM | 16309928, 37447322 | Source scope reconciled; clinical context required |
| BRAND_LONGVIDA | 25277322, 32512782 | Source scope reconciled; clinical context required |
| BRAND_UCII | 24153020, 26822714 | Source scope reconciled; clinical context required |
| BRAND_NIAGEN | 29599478, 29992272 | Source scope reconciled; clinical context required |
| BRAND_RELORA | 23924268 | Source scope reconciled; clinical context required |
| INGR_SELENIUM | 20883174, 27702392, 37335715, 38243784 | Source scope reconciled; clinical context required |
| INGR_MAG_GLYCINATE | 22909270 | Source scope reconciled; clinical context required |
| INGR_QUERCETIN | 27405810, 35948195 | Source scope reconciled; clinical context required |
| INGR_COQ10 | 25282031, 39462324 | Source scope reconciled; clinical context required |
| INGR_GINSENG | 29624410, 35509826, 35776997 | Source scope reconciled; clinical context required |
| INGR_RHODIOLA | 41080184 | Source scope reconciled; clinical context required |
| INGR_FENUGREEK | 32048383 | Source scope reconciled; clinical context required |
| INGR_CINNAMON_EXTRACT | 24019277 | Source scope reconciled; clinical context required |
| INGR_DIGESTIVE_ENZYMES | 37976892 | Source scope reconciled; clinical context required |
| INGR_LEMON_BALM | 34449930 | Source scope reconciled; clinical context required |
| PRECLIN_SPERMIDINE | 30388439, 35616942 | Source scope reconciled; clinical context required |
| PRECLIN_QUERCETIN_PHYTOSOME | 35776034, 36712674, 40037045 | Source scope reconciled; clinical context required |
| PRECLIN_ASTAXANTHIN_GENERIC | 32755613, 34578794, 35091276, 38243785 | Source scope reconciled; clinical context required |
| PRECLIN_PTEROSTILBENE | 23431291, 25057276 | Source scope reconciled; clinical context required |
| PRECLIN_DGL | 21747893, 23606875, 39929150, 4933135 | Source scope reconciled; clinical context required |
| PRECLIN_CORDYCEPS | 20804368, 27408987, 38501161 | Source scope reconciled; clinical context required |
| PRECLIN_BETAINE_HCL | 23980906, 25274610 | Reference only; affirmative credit disabled |
| PRECLIN_SAFFRON | 31135916, 38913392, 41693488 | Source scope reconciled; clinical context required |
| PRECLIN_RESVERATROL | 24111838, 29305228, 35905799, 36145131, 39255906, 39872318 | Source scope reconciled; clinical context required |
| BRAND_TESTOFEN | 21312304, 26791805 | Source scope reconciled; clinical context required |
| INGR_VITAMIN_E | 15537682 | Reference only; affirmative credit disabled |
| INGR_MAGNESIUM_GENERIC | 26752497, 41000008, 8792038 | Source scope reconciled; clinical context required |
| INGR_VITAMIN_B6 | 10334745, 36719452 | Source scope reconciled; clinical context required |
| INGR_PSYLLIUM_HUSK | 18985059, 30239559 | Source scope reconciled; clinical context required |
| INGR_ASTRAGALUS | 37952511 | Source scope reconciled; clinical context required |
| INGR_BROMELAIN | 37157782 | Source scope reconciled; clinical context required |
| INGR_PROPOLIS | 41003407 | Reference only; affirmative credit disabled |
| INGR_CHAMOMILE | 39106912 | Source scope reconciled; clinical context required |
| INGR_BEETROOT | 33554654, 34965876 | Source scope reconciled; clinical context required |
| INGR_BENFOTIAMINE | 23992649, 33074237 | Source scope reconciled; clinical context required |
| INGR_MOLYBDENUM | 16896051, 19318634 | Reference only; affirmative credit disabled |
| INGR_BLACK_SEED_OIL | 21675032, 34407441, 37341696, 40210172 | Source scope reconciled; clinical context required |
| INGR_SEA_BUCKTHORN | 20554904, 23472020, 36043374 | Source scope reconciled; clinical context required |
| INGR_SLIPPERY_ELM | 20954962, 32151878 | Reference only; affirmative credit disabled |
| INGR_BILBERRY | 25191571, 25923485, 32106548 | Source scope reconciled; clinical context required |
| INGR_CERAMIDES | 33055441, 35719159, 35807914, 38999848 | Source scope reconciled; clinical context required |

Final contract review: CI40057355582 failed three existing assertions: inappropriate empty
outcome categories, named-hair-complex hold regression, and direct/cache result inequality.
All reproduced locally. Unrepresentable optional primary_outcome is omitted (existing schema/
consumer contract), preserving exact endpoint/source facts. Proprietary Blend exception removed;
336100 retains its preparation hold. Private context sanitation moved to implementation boundary;
cache equivalence test expanded, equality assertion unchanged. Existing safety/hold/vocabulary
assertions not weakened.131source/contract and196producer checks pass; final combined checkpoint
and stable raw comparisons qualify the corrected candidate, not the failed one.


## October 24 final completion campaign — source corrections and open scientific work

Runtime candidate `6eb67c797ec7f36a3230edd30616c00e138bc92e`; baseline `5c3982c5f97c2686558a7ea85e88523b85874e98`. See rewritten [consolidated handoff](CLINICAL_REVIEW_HANDOFF.md) for measured behavior, API dispositions and the authoritative remaining-work list. No pipeline or clinical approval performed.

### Eleven factual clinical corrections

| Record | Retained source facts and limitations |
|---|---|
| BRAND_MAGTEIN | 39252819 original restored;40567408 correction is not independent efficacy trial. Combination36558392 distinct;41601871 subjective/selected rather than general objective benefit. No fabricated aggregate enrollment; correction body still pending. |
| BRAND_MITOPURE | Primary peak-power endpoint null; peak VO2 versus placebo p=.058; walking/aerobic within-group findings and funding/author relationships retained. |
| BRAND_LUTEMAX_2020 | 25251377 EyePromise zeaxanthin/lutein/omega-3 preparation is not independent Lutemax/meso-zeaxanthin replication. |
| PRECLIN_SULFORAPHANE | 39929977 failed prespecified0.3mmol/L primary target;0.2overall and exploratory subgroup findings distinct; gastrointestinal effects retained. |
| INGR_COLLAGEN_PEPTIDES | 40324552 funding/high-quality sensitivity; OA37717022 distinct with high risk of bias. No universal preparation, skin-to-joint or longevity transfer. |
| INGR_BERBERINE | 27157250 multiingredient; NCT03281096 dose description/arms conflict unresolved; NCT04697186 antibiotic/PPI combination separate. |
| INGR_ST_JOHNS_WORT | 28064110 compares SSRIs, not placebo. Existing CYP/P-gp warnings preserved verbatim. |
| INGR_RHODIOLA | 41080184 endurance evidence does not support stale generic stress-fatigue opening claim. |
| INGR_GINSENG | Retained fatigue/metabolic sources do not establish stale opening cognition claim. |
| INGR_LEMON_BALM | 34449930 anxiety/depression synthesis does not establish uncited cognition claim. |
| INGR_HYALURONIC_ACID | 28761365/34203487/40911749 skin sources; removed unsupported joint/longevity and untraceable aggregate counts. Existing grade retained under incomplete-context hold. |

### Literature source-existence corrections, not clinical qualification

Fifteen previously overstated human-evidence absence claims now preserve actual source existence with applicability_unestablished / verification_failure_unresolved, no studied-dose reference and scoring_eligible=false on every added source. Theacrine blood-pressure/symptom findings are trial-specific, not an invented safety limit; peppermint volume is not converted to mass; mushroom PSP/PSK oncology preparations are not raw mushroom; Solarplast supplier-funded exploratory endpoints are not independent replication. Tart cherry20459662 regimen is seven days before and on race day.

Exact changed subjects: skullcap, noni, corn_silk, yarrow_aerial_parts, korean_pine, tremella_fuciformis, cistanche, french_oak, shatavari, black_rice, juniper, peppermint_essential_oil, theacrine, kawaratake, oi_solarplast, tart_cherry. Retraction40434025→42820926 was excluded rather than used affirmatively.

### Per-record source access and outstanding scientific synthesis

The clinical CSV now records per-paper access for every eligible record. All147 context checks remain incomplete. Frozen cohort/dependency columns are unchanged; this index does not create clinical contexts or approvals.

| Record | Sources | Access: retrieved / indexed unavailable / no PMC | Screening |
|---|---|---|---|
| BRAND_AFFRON | [28735826](https://pubmed.ncbi.nlm.nih.gov/28735826/), [29510352](https://pubmed.ncbi.nlm.nih.gov/29510352/), [40414301](https://pubmed.ncbi.nlm.nih.gov/40414301/) | 0/0/3 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_ASTAREAL | [22428137](https://pubmed.ncbi.nlm.nih.gov/22428137/) | 0/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_BCM95 | [30975196](https://pubmed.ncbi.nlm.nih.gov/30975196/), [33516238](https://pubmed.ncbi.nlm.nih.gov/33516238/) | 2/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_BIOCELL | [22486722](https://pubmed.ncbi.nlm.nih.gov/22486722/), [22956862](https://pubmed.ncbi.nlm.nih.gov/22956862/), [31221944](https://pubmed.ncbi.nlm.nih.gov/31221944/) | 1/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_CARNIPURE | [11788381](https://pubmed.ncbi.nlm.nih.gov/11788381/), [20045157](https://pubmed.ncbi.nlm.nih.gov/20045157/) | 0/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_KANEKA_UBIQUINOL | [32326664](https://pubmed.ncbi.nlm.nih.gov/32326664/), [16919858](https://pubmed.ncbi.nlm.nih.gov/16919858/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_KSM66 | [23439798](https://pubmed.ncbi.nlm.nih.gov/23439798/), [32021735](https://pubmed.ncbi.nlm.nih.gov/32021735/) | 2/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_LACTOSPORE | [26922379](https://pubmed.ncbi.nlm.nih.gov/26922379/), [29997457](https://pubmed.ncbi.nlm.nih.gov/29997457/) | 2/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_LJ100 | [23243445](https://pubmed.ncbi.nlm.nih.gov/23243445/), [24550993](https://pubmed.ncbi.nlm.nih.gov/24550993/), [34262417](https://pubmed.ncbi.nlm.nih.gov/34262417/) | 3/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_LUTEMAX_2020 | [28661438](https://pubmed.ncbi.nlm.nih.gov/28661438/), [25251377](https://pubmed.ncbi.nlm.nih.gov/25251377/), [38890092](https://pubmed.ncbi.nlm.nih.gov/38890092/) | 2/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_MAGTEIN | [36558392](https://pubmed.ncbi.nlm.nih.gov/36558392/), [41601871](https://pubmed.ncbi.nlm.nih.gov/41601871/), [40567408](https://pubmed.ncbi.nlm.nih.gov/40567408/) | 2/1/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_MITOPURE | [35584623](https://pubmed.ncbi.nlm.nih.gov/35584623/), [32694802](https://pubmed.ncbi.nlm.nih.gov/32694802/) | 1/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_NIAGEN | [29599478](https://pubmed.ncbi.nlm.nih.gov/29599478/), [29992272](https://pubmed.ncbi.nlm.nih.gov/29992272/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_NITROSIGINE | [27869715](https://pubmed.ncbi.nlm.nih.gov/27869715/), [32093766](https://pubmed.ncbi.nlm.nih.gov/32093766/), [34959823](https://pubmed.ncbi.nlm.nih.gov/34959823/) | 3/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_OPTIMSM | [16309928](https://pubmed.ncbi.nlm.nih.gov/16309928/), [37447322](https://pubmed.ncbi.nlm.nih.gov/37447322/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_PUREWAY_C | [18971870](https://pubmed.ncbi.nlm.nih.gov/18971870/), [17901843](https://pubmed.ncbi.nlm.nih.gov/17901843/) | 0/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_PYCNOGENOL | [18386255](https://pubmed.ncbi.nlm.nih.gov/18386255/), [31585179](https://pubmed.ncbi.nlm.nih.gov/31585179/), [31637782](https://pubmed.ncbi.nlm.nih.gov/31637782/) | 0/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_QUATREFOLIC | [36034319](https://pubmed.ncbi.nlm.nih.gov/36034319/), [23698160](https://pubmed.ncbi.nlm.nih.gov/23698160/) | 2/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_RELORA | [23924268](https://pubmed.ncbi.nlm.nih.gov/23924268/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_SENSORIL | [27647541](https://pubmed.ncbi.nlm.nih.gov/27647541/), [38732539](https://pubmed.ncbi.nlm.nih.gov/38732539/) | 2/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_SETRIA | [24791752](https://pubmed.ncbi.nlm.nih.gov/24791752/), [28490897](https://pubmed.ncbi.nlm.nih.gov/28490897/) | 1/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_SHODEN | [31517876](https://pubmed.ncbi.nlm.nih.gov/31517876/), [32540634](https://pubmed.ncbi.nlm.nih.gov/32540634/), [39286132](https://pubmed.ncbi.nlm.nih.gov/39286132/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_SUNFIBER | [26855665](https://pubmed.ncbi.nlm.nih.gov/26855665/), [31509971](https://pubmed.ncbi.nlm.nih.gov/31509971/) | 2/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_SUNTHEANINE | [22214254](https://pubmed.ncbi.nlm.nih.gov/22214254/), [31623400](https://pubmed.ncbi.nlm.nih.gov/31623400/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_SYTRINOL | [17985810](https://pubmed.ncbi.nlm.nih.gov/17985810/), [25828621](https://pubmed.ncbi.nlm.nih.gov/25828621/) | 0/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_TAMAFLEX | [31337958](https://pubmed.ncbi.nlm.nih.gov/31337958/), [35096104](https://pubmed.ncbi.nlm.nih.gov/35096104/), [37351019](https://pubmed.ncbi.nlm.nih.gov/37351019/) | 3/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_TESNOR | [35129040](https://pubmed.ncbi.nlm.nih.gov/35129040/), [35928723](https://pubmed.ncbi.nlm.nih.gov/35928723/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_TESTOFEN | [21312304](https://pubmed.ncbi.nlm.nih.gov/21312304/), [26791805](https://pubmed.ncbi.nlm.nih.gov/26791805/) | 0/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_THERACURMIN | [25308211](https://pubmed.ncbi.nlm.nih.gov/25308211/), [29246725](https://pubmed.ncbi.nlm.nih.gov/29246725/), [35494290](https://pubmed.ncbi.nlm.nih.gov/35494290/) | 2/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| BRAND_UCII | [24153020](https://pubmed.ncbi.nlm.nih.gov/24153020/), [26822714](https://pubmed.ncbi.nlm.nih.gov/26822714/) | 2/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| BRAND_ZYNAMITE | [32717999](https://pubmed.ncbi.nlm.nih.gov/32717999/), [30736383](https://pubmed.ncbi.nlm.nih.gov/30736383/), [31661850](https://pubmed.ncbi.nlm.nih.gov/31661850/) | 3/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| FORMULA_SEED_DS01 | [41599868](https://pubmed.ncbi.nlm.nih.gov/41599868/), [40944126](https://pubmed.ncbi.nlm.nih.gov/40944126/), [41750436](https://pubmed.ncbi.nlm.nih.gov/41750436/) | 3/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_5HTP | [12169147](https://pubmed.ncbi.nlm.nih.gov/12169147/), [11869656](https://pubmed.ncbi.nlm.nih.gov/11869656/) | 0/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_ACETYL_L_CARNITINE | [12598816](https://pubmed.ncbi.nlm.nih.gov/12598816/), [12804452](https://pubmed.ncbi.nlm.nih.gov/12804452/), [28349514](https://pubmed.ncbi.nlm.nih.gov/28349514/), [31118753](https://pubmed.ncbi.nlm.nih.gov/31118753/), [31201734](https://pubmed.ncbi.nlm.nih.gov/31201734/) | 1/3/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_ALPHA_GPC | [36683513](https://pubmed.ncbi.nlm.nih.gov/36683513/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_ALPHA_LIPOIC_ACID | [17065669](https://pubmed.ncbi.nlm.nih.gov/17065669/), [37630823](https://pubmed.ncbi.nlm.nih.gov/37630823/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_ASHWAGANDHA | [36017529](https://pubmed.ncbi.nlm.nih.gov/36017529/), [39348746](https://pubmed.ncbi.nlm.nih.gov/39348746/) | 0/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_ASTRAGALUS | [37952511](https://pubmed.ncbi.nlm.nih.gov/37952511/) | 0/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BACOPA | [24252493](https://pubmed.ncbi.nlm.nih.gov/24252493/), [27912958](https://pubmed.ncbi.nlm.nih.gov/27912958/) | 0/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_BEETROOT | [33554654](https://pubmed.ncbi.nlm.nih.gov/33554654/), [34965876](https://pubmed.ncbi.nlm.nih.gov/34965876/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BENFOTIAMINE | [33074237](https://pubmed.ncbi.nlm.nih.gov/33074237/), [23992649](https://pubmed.ncbi.nlm.nih.gov/23992649/) | 2/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BERBERINE | [18442638](https://pubmed.ncbi.nlm.nih.gov/18442638/), [27157250](https://pubmed.ncbi.nlm.nih.gov/27157250/) | 0/1/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_BERBERINE_HCL | [34956436](https://pubmed.ncbi.nlm.nih.gov/34956436/), [36999891](https://pubmed.ncbi.nlm.nih.gov/36999891/) | 1/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_BETA_ALANINE | [22270875](https://pubmed.ncbi.nlm.nih.gov/22270875/), [27797728](https://pubmed.ncbi.nlm.nih.gov/27797728/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BILBERRY | [25191571](https://pubmed.ncbi.nlm.nih.gov/25191571/), [25923485](https://pubmed.ncbi.nlm.nih.gov/25923485/), [32106548](https://pubmed.ncbi.nlm.nih.gov/32106548/) | 3/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BIOTIN | [32762597](https://pubmed.ncbi.nlm.nih.gov/32762597/), [40896024](https://pubmed.ncbi.nlm.nih.gov/40896024/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BITTER_MELON | [30385422](https://pubmed.ncbi.nlm.nih.gov/30385422/) | 0/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_BLACK_COHOSH | [15565808](https://pubmed.ncbi.nlm.nih.gov/15565808/), [16039414](https://pubmed.ncbi.nlm.nih.gov/16039414/), [17565936](https://pubmed.ncbi.nlm.nih.gov/17565936/) | 0/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BLACK_SEED_OIL | [40210172](https://pubmed.ncbi.nlm.nih.gov/40210172/), [37341696](https://pubmed.ncbi.nlm.nih.gov/37341696/), [21675032](https://pubmed.ncbi.nlm.nih.gov/21675032/), [34407441](https://pubmed.ncbi.nlm.nih.gov/34407441/) | 1/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BRANCHED_CHAIN_AMINO_ACIDS | [36235655](https://pubmed.ncbi.nlm.nih.gov/36235655/), [38241335](https://pubmed.ncbi.nlm.nih.gov/38241335/), [38625669](https://pubmed.ncbi.nlm.nih.gov/38625669/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_BROMELAIN | [37157782](https://pubmed.ncbi.nlm.nih.gov/37157782/) | 0/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CAFFEINE | [30926628](https://pubmed.ncbi.nlm.nih.gov/30926628/), [32551869](https://pubmed.ncbi.nlm.nih.gov/32551869/), [33800853](https://pubmed.ncbi.nlm.nih.gov/33800853/), [34139220](https://pubmed.ncbi.nlm.nih.gov/34139220/) | 1/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CALCIUM | [17720017](https://pubmed.ncbi.nlm.nih.gov/17720017/), [26510847](https://pubmed.ncbi.nlm.nih.gov/26510847/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CERAMIDES | [33055441](https://pubmed.ncbi.nlm.nih.gov/33055441/), [38999848](https://pubmed.ncbi.nlm.nih.gov/38999848/), [35807914](https://pubmed.ncbi.nlm.nih.gov/35807914/), [35719159](https://pubmed.ncbi.nlm.nih.gov/35719159/) | 3/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CHAMOMILE | [39106912](https://pubmed.ncbi.nlm.nih.gov/39106912/) | 0/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CHLORELLA | [23234816](https://pubmed.ncbi.nlm.nih.gov/23234816/), [29037431](https://pubmed.ncbi.nlm.nih.gov/29037431/), [35331862](https://pubmed.ncbi.nlm.nih.gov/35331862/) | 0/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CHONDROITIN_SULFATE | [25629804](https://pubmed.ncbi.nlm.nih.gov/25629804/) | 0/1/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CINNAMON_EXTRACT | [24019277](https://pubmed.ncbi.nlm.nih.gov/24019277/) | 0/1/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_COLLAGEN_PEPTIDES | [37432180](https://pubmed.ncbi.nlm.nih.gov/37432180/), [37717022](https://pubmed.ncbi.nlm.nih.gov/37717022/), [39839727](https://pubmed.ncbi.nlm.nih.gov/39839727/), [40324552](https://pubmed.ncbi.nlm.nih.gov/40324552/) | 3/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_COQ10 | [25282031](https://pubmed.ncbi.nlm.nih.gov/25282031/), [39462324](https://pubmed.ncbi.nlm.nih.gov/39462324/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CRANBERRY | [34473789](https://pubmed.ncbi.nlm.nih.gov/34473789/), [37947276](https://pubmed.ncbi.nlm.nih.gov/37947276/) | 1/1/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_CREATINE_MONOHYDRATE | [39074168](https://pubmed.ncbi.nlm.nih.gov/39074168/), [39519498](https://pubmed.ncbi.nlm.nih.gov/39519498/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_DIGESTIVE_ENZYMES | [37976892](https://pubmed.ncbi.nlm.nih.gov/37976892/) | 0/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_ECHINACEA | [24554461](https://pubmed.ncbi.nlm.nih.gov/24554461/) | 0/1/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_ELDERBERRY | [30670267](https://pubmed.ncbi.nlm.nih.gov/30670267/), [33827515](https://pubmed.ncbi.nlm.nih.gov/33827515/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_FENUGREEK | [32048383](https://pubmed.ncbi.nlm.nih.gov/32048383/) | 0/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_FOLATE_MTHF | [31425504](https://pubmed.ncbi.nlm.nih.gov/31425504/), [16600937](https://pubmed.ncbi.nlm.nih.gov/16600937/), [16151461](https://pubmed.ncbi.nlm.nih.gov/16151461/), [25943647](https://pubmed.ncbi.nlm.nih.gov/25943647/), [25733468](https://pubmed.ncbi.nlm.nih.gov/25733468/) | 1/1/3 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_GABA | [33041752](https://pubmed.ncbi.nlm.nih.gov/33041752/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_GARLIC | [32010325](https://pubmed.ncbi.nlm.nih.gov/32010325/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_GINGER | [21818642](https://pubmed.ncbi.nlm.nih.gov/21818642/), [24642205](https://pubmed.ncbi.nlm.nih.gov/24642205/), [31937153](https://pubmed.ncbi.nlm.nih.gov/31937153/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_GINSENG | [29624410](https://pubmed.ncbi.nlm.nih.gov/29624410/), [35509826](https://pubmed.ncbi.nlm.nih.gov/35509826/), [35776997](https://pubmed.ncbi.nlm.nih.gov/35776997/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_GLUCOSAMINE_SULFATE | [33488785](https://pubmed.ncbi.nlm.nih.gov/33488785/), [40005447](https://pubmed.ncbi.nlm.nih.gov/40005447/) | 2/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_GRAPE_SEED_EXTRACT | [33671310](https://pubmed.ncbi.nlm.nih.gov/33671310/), [34798267](https://pubmed.ncbi.nlm.nih.gov/34798267/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_GREEN_TEA | [19597519](https://pubmed.ncbi.nlm.nih.gov/19597519/), [38031409](https://pubmed.ncbi.nlm.nih.gov/38031409/) | 0/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_HMB | [24599749](https://pubmed.ncbi.nlm.nih.gov/24599749/), [25700845](https://pubmed.ncbi.nlm.nih.gov/25700845/), [35911112](https://pubmed.ncbi.nlm.nih.gov/35911112/), [41305674](https://pubmed.ncbi.nlm.nih.gov/41305674/) | 3/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_HONEY | [32817011](https://pubmed.ncbi.nlm.nih.gov/32817011/), [22419319](https://pubmed.ncbi.nlm.nih.gov/22419319/), [22869830](https://pubmed.ncbi.nlm.nih.gov/22869830/), [36126325](https://pubmed.ncbi.nlm.nih.gov/36126325/) | 0/0/4 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_HYALURONIC_ACID | [28761365](https://pubmed.ncbi.nlm.nih.gov/28761365/), [34203487](https://pubmed.ncbi.nlm.nih.gov/34203487/), [40911749](https://pubmed.ncbi.nlm.nih.gov/40911749/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_INOSITOL | [38163998](https://pubmed.ncbi.nlm.nih.gov/38163998/), [36703143](https://pubmed.ncbi.nlm.nih.gov/36703143/), [35477841](https://pubmed.ncbi.nlm.nih.gov/35477841/) | 2/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_INULIN | [34555168](https://pubmed.ncbi.nlm.nih.gov/34555168/), [35833477](https://pubmed.ncbi.nlm.nih.gov/35833477/), [38309832](https://pubmed.ncbi.nlm.nih.gov/38309832/) | 1/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_IRON_BISGLYCINATE | [36728680](https://pubmed.ncbi.nlm.nih.gov/36728680/) | 0/1/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_LACTOFERRIN | [35276902](https://pubmed.ncbi.nlm.nih.gov/35276902/), [19639462](https://pubmed.ncbi.nlm.nih.gov/19639462/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_LEMON_BALM | [34449930](https://pubmed.ncbi.nlm.nih.gov/34449930/) | 0/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_LION_MANE | [18844328](https://pubmed.ncbi.nlm.nih.gov/18844328/), [38140277](https://pubmed.ncbi.nlm.nih.gov/38140277/), [40276537](https://pubmed.ncbi.nlm.nih.gov/40276537/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_LUTEIN | [28661438](https://pubmed.ncbi.nlm.nih.gov/28661438/), [41573009](https://pubmed.ncbi.nlm.nih.gov/41573009/) | 1/1/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_L_ARGININE | [22137067](https://pubmed.ncbi.nlm.nih.gov/22137067/), [32370176](https://pubmed.ncbi.nlm.nih.gov/32370176/), [34967840](https://pubmed.ncbi.nlm.nih.gov/34967840/) | 1/1/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_L_CARNITINE | [32958033](https://pubmed.ncbi.nlm.nih.gov/32958033/), [32154768](https://pubmed.ncbi.nlm.nih.gov/32154768/), [32359762](https://pubmed.ncbi.nlm.nih.gov/32359762/) | 1/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_L_CITRULLINE | [30150102](https://pubmed.ncbi.nlm.nih.gov/30150102/), [30284051](https://pubmed.ncbi.nlm.nih.gov/30284051/), [33308806](https://pubmed.ncbi.nlm.nih.gov/33308806/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_L_THEANINE | [24946991](https://pubmed.ncbi.nlm.nih.gov/24946991/), [40314930](https://pubmed.ncbi.nlm.nih.gov/40314930/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_MAGNESIUM_GENERIC | [26752497](https://pubmed.ncbi.nlm.nih.gov/26752497/), [41000008](https://pubmed.ncbi.nlm.nih.gov/41000008/), [8792038](https://pubmed.ncbi.nlm.nih.gov/8792038/) | 1/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_MAG_GLYCINATE | [22909270](https://pubmed.ncbi.nlm.nih.gov/22909270/) | 0/1/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_MELATONIN | [12076414](https://pubmed.ncbi.nlm.nih.gov/12076414/), [38888087](https://pubmed.ncbi.nlm.nih.gov/38888087/) | 0/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_MILK_THISTLE | [17943794](https://pubmed.ncbi.nlm.nih.gov/17943794/), [38579127](https://pubmed.ncbi.nlm.nih.gov/38579127/) | 0/1/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_MSM | [16309928](https://pubmed.ncbi.nlm.nih.gov/16309928/), [37447322](https://pubmed.ncbi.nlm.nih.gov/37447322/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_NAC | [29457216](https://pubmed.ncbi.nlm.nih.gov/29457216/), [31107966](https://pubmed.ncbi.nlm.nih.gov/31107966/), [39632267](https://pubmed.ncbi.nlm.nih.gov/39632267/), [9230243](https://pubmed.ncbi.nlm.nih.gov/9230243/) | 1/1/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_OMEGA3 | [31567003](https://pubmed.ncbi.nlm.nih.gov/31567003/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_PANTETHINE | [24600231](https://pubmed.ncbi.nlm.nih.gov/24600231/), [21925346](https://pubmed.ncbi.nlm.nih.gov/21925346/) | 1/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_PASSIONFLOWER | [21294203](https://pubmed.ncbi.nlm.nih.gov/21294203/), [33352740](https://pubmed.ncbi.nlm.nih.gov/33352740/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_PEA | [36986081](https://pubmed.ncbi.nlm.nih.gov/36986081/) | 1/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_PEPPERMINT_OIL | [35942669](https://pubmed.ncbi.nlm.nih.gov/35942669/), [31470006](https://pubmed.ncbi.nlm.nih.gov/31470006/), [24100754](https://pubmed.ncbi.nlm.nih.gov/24100754/), [26319955](https://pubmed.ncbi.nlm.nih.gov/26319955/) | 1/0/3 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_PHOSPHATIDYLSERINE | [20523044](https://pubmed.ncbi.nlm.nih.gov/20523044/), [21103034](https://pubmed.ncbi.nlm.nih.gov/21103034/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_PLANT_STEROLS | [19109655](https://pubmed.ncbi.nlm.nih.gov/19109655/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_POTASSIUM | [40612568](https://pubmed.ncbi.nlm.nih.gov/40612568/) | 1/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_PROBIOTICS | [37772692](https://pubmed.ncbi.nlm.nih.gov/37772692/), [38999862](https://pubmed.ncbi.nlm.nih.gov/38999862/), [41682832](https://pubmed.ncbi.nlm.nih.gov/41682832/) | 2/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_PSYLLIUM_HUSK | [18985059](https://pubmed.ncbi.nlm.nih.gov/18985059/), [30239559](https://pubmed.ncbi.nlm.nih.gov/30239559/) | 0/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_QUERCETIN | [27405810](https://pubmed.ncbi.nlm.nih.gov/27405810/), [35948195](https://pubmed.ncbi.nlm.nih.gov/35948195/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_RED_YEAST_RICE | [35264949](https://pubmed.ncbi.nlm.nih.gov/35264949/) | 1/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_RHODIOLA | [41080184](https://pubmed.ncbi.nlm.nih.gov/41080184/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_RIBOFLAVIN_B2 | [9484373](https://pubmed.ncbi.nlm.nih.gov/9484373/), [33779525](https://pubmed.ncbi.nlm.nih.gov/33779525/), [41769676](https://pubmed.ncbi.nlm.nih.gov/41769676/) | 1/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_SAW_PALMETTO |  | 0/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_SEA_BUCKTHORN | [20554904](https://pubmed.ncbi.nlm.nih.gov/20554904/), [36043374](https://pubmed.ncbi.nlm.nih.gov/36043374/), [23472020](https://pubmed.ncbi.nlm.nih.gov/23472020/) | 0/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_SELENIUM | [20883174](https://pubmed.ncbi.nlm.nih.gov/20883174/), [27702392](https://pubmed.ncbi.nlm.nih.gov/27702392/), [37335715](https://pubmed.ncbi.nlm.nih.gov/37335715/), [38243784](https://pubmed.ncbi.nlm.nih.gov/38243784/) | 2/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_SPIRULINA | [12487756](https://pubmed.ncbi.nlm.nih.gov/12487756/), [25057105](https://pubmed.ncbi.nlm.nih.gov/25057105/), [30544795](https://pubmed.ncbi.nlm.nih.gov/30544795/), [34538515](https://pubmed.ncbi.nlm.nih.gov/34538515/), [35988871](https://pubmed.ncbi.nlm.nih.gov/35988871/), [37263369](https://pubmed.ncbi.nlm.nih.gov/37263369/), [38401078](https://pubmed.ncbi.nlm.nih.gov/38401078/) | 2/0/5 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_ST_JOHNS_WORT | [28064110](https://pubmed.ncbi.nlm.nih.gov/28064110/), [18843608](https://pubmed.ncbi.nlm.nih.gov/18843608/) | 0/1/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_TAURINE | [32871172](https://pubmed.ncbi.nlm.nih.gov/32871172/), [41275513](https://pubmed.ncbi.nlm.nih.gov/41275513/) | 0/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_TURMERIC | [38576215](https://pubmed.ncbi.nlm.nih.gov/38576215/), [38945354](https://pubmed.ncbi.nlm.nih.gov/38945354/), [40615851](https://pubmed.ncbi.nlm.nih.gov/40615851/) | 1/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_VALERIAN | [33086877](https://pubmed.ncbi.nlm.nih.gov/33086877/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_VITAMIN_B3_NIACIN | [11498460](https://pubmed.ncbi.nlm.nih.gov/11498460/), [15642562](https://pubmed.ncbi.nlm.nih.gov/15642562/), [25141367](https://pubmed.ncbi.nlm.nih.gov/25141367/), [9732910](https://pubmed.ncbi.nlm.nih.gov/9732910/) | 0/0/4 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_VITAMIN_B6 | [36719452](https://pubmed.ncbi.nlm.nih.gov/36719452/), [10334745](https://pubmed.ncbi.nlm.nih.gov/10334745/) | 0/1/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_VITAMIN_C | [17636648](https://pubmed.ncbi.nlm.nih.gov/17636648/), [23440782](https://pubmed.ncbi.nlm.nih.gov/23440782/), [38082300](https://pubmed.ncbi.nlm.nih.gov/38082300/) | 1/1/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_VITAMIN_D3 | [28202713](https://pubmed.ncbi.nlm.nih.gov/28202713/), [30293909](https://pubmed.ncbi.nlm.nih.gov/30293909/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_WHEY_PROTEIN | [28698222](https://pubmed.ncbi.nlm.nih.gov/28698222/), [39303495](https://pubmed.ncbi.nlm.nih.gov/39303495/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| INGR_WHITE_KIDNEY_BEAN | [42066439](https://pubmed.ncbi.nlm.nih.gov/42066439/), [39170208](https://pubmed.ncbi.nlm.nih.gov/39170208/) | 1/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| INGR_ZINC_PICOLINATE | [25888289](https://pubmed.ncbi.nlm.nih.gov/25888289/), [27378206](https://pubmed.ncbi.nlm.nih.gov/27378206/), [28515951](https://pubmed.ncbi.nlm.nih.gov/28515951/) | 2/1/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_ARTICHOKE | [14653829](https://pubmed.ncbi.nlm.nih.gov/14653829/), [18424099](https://pubmed.ncbi.nlm.nih.gov/18424099/), [22746542](https://pubmed.ncbi.nlm.nih.gov/22746542/), [28609140](https://pubmed.ncbi.nlm.nih.gov/28609140/), [34569671](https://pubmed.ncbi.nlm.nih.gov/34569671/) | 0/0/5 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_ASTAXANTHIN_GENERIC | [32755613](https://pubmed.ncbi.nlm.nih.gov/32755613/), [34578794](https://pubmed.ncbi.nlm.nih.gov/34578794/), [35091276](https://pubmed.ncbi.nlm.nih.gov/35091276/), [38243785](https://pubmed.ncbi.nlm.nih.gov/38243785/) | 1/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_BERBERINE_GENERIC | [34956436](https://pubmed.ncbi.nlm.nih.gov/34956436/), [36467075](https://pubmed.ncbi.nlm.nih.gov/36467075/), [37598753](https://pubmed.ncbi.nlm.nih.gov/37598753/), [36941490](https://pubmed.ncbi.nlm.nih.gov/36941490/) | 2/0/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_BETAINE_ANHYDROUS | [30064450](https://pubmed.ncbi.nlm.nih.gov/30064450/), [37409757](https://pubmed.ncbi.nlm.nih.gov/37409757/) | 2/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_BOSWELLIA | [32680575](https://pubmed.ncbi.nlm.nih.gov/32680575/), [35512759](https://pubmed.ncbi.nlm.nih.gov/35512759/), [39092235](https://pubmed.ncbi.nlm.nih.gov/39092235/) | 2/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_CORDYCEPS | [20804368](https://pubmed.ncbi.nlm.nih.gov/20804368/), [27408987](https://pubmed.ncbi.nlm.nih.gov/27408987/), [38501161](https://pubmed.ncbi.nlm.nih.gov/38501161/) | 1/1/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_CURCUMIN_GENERIC | [38576215](https://pubmed.ncbi.nlm.nih.gov/38576215/), [38945354](https://pubmed.ncbi.nlm.nih.gov/38945354/), [39478418](https://pubmed.ncbi.nlm.nih.gov/39478418/), [40615851](https://pubmed.ncbi.nlm.nih.gov/40615851/) | 1/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_DGL | [21747893](https://pubmed.ncbi.nlm.nih.gov/21747893/), [23606875](https://pubmed.ncbi.nlm.nih.gov/23606875/), [39929150](https://pubmed.ncbi.nlm.nih.gov/39929150/), [4933135](https://pubmed.ncbi.nlm.nih.gov/4933135/) | 3/1/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_FISETIN | [39269340](https://pubmed.ncbi.nlm.nih.gov/39269340/) | 0/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_HUPERZINE_A | [24086396](https://pubmed.ncbi.nlm.nih.gov/24086396/), [21502597](https://pubmed.ncbi.nlm.nih.gov/21502597/), [24639880](https://pubmed.ncbi.nlm.nih.gov/24639880/), [30989926](https://pubmed.ncbi.nlm.nih.gov/30989926/) | 2/1/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_NMN | [39116016](https://pubmed.ncbi.nlm.nih.gov/39116016/), [39531138](https://pubmed.ncbi.nlm.nih.gov/39531138/), [38789831](https://pubmed.ncbi.nlm.nih.gov/38789831/), [36443648](https://pubmed.ncbi.nlm.nih.gov/36443648/), [35215405](https://pubmed.ncbi.nlm.nih.gov/35215405/) | 2/1/2 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_PQQ | [34415830](https://pubmed.ncbi.nlm.nih.gov/34415830/), [38908296](https://pubmed.ncbi.nlm.nih.gov/38908296/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_PTEROSTILBENE | [25057276](https://pubmed.ncbi.nlm.nih.gov/25057276/), [23431291](https://pubmed.ncbi.nlm.nih.gov/23431291/) | 2/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_QUERCETIN_PHYTOSOME | [40037045](https://pubmed.ncbi.nlm.nih.gov/40037045/), [35776034](https://pubmed.ncbi.nlm.nih.gov/35776034/), [36712674](https://pubmed.ncbi.nlm.nih.gov/36712674/) | 1/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_RESVERATROL | [24111838](https://pubmed.ncbi.nlm.nih.gov/24111838/), [29305228](https://pubmed.ncbi.nlm.nih.gov/29305228/), [35905799](https://pubmed.ncbi.nlm.nih.gov/35905799/), [36145131](https://pubmed.ncbi.nlm.nih.gov/36145131/), [39255906](https://pubmed.ncbi.nlm.nih.gov/39255906/), [39872318](https://pubmed.ncbi.nlm.nih.gov/39872318/) | 2/0/4 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_SAFFRON | [31135916](https://pubmed.ncbi.nlm.nih.gov/31135916/), [38913392](https://pubmed.ncbi.nlm.nih.gov/38913392/), [41693488](https://pubmed.ncbi.nlm.nih.gov/41693488/) | 0/0/3 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_SPERMIDINE | [30388439](https://pubmed.ncbi.nlm.nih.gov/30388439/), [35616942](https://pubmed.ncbi.nlm.nih.gov/35616942/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| PRECLIN_SULFORAPHANE | [40041932](https://pubmed.ncbi.nlm.nih.gov/40041932/), [40458076](https://pubmed.ncbi.nlm.nih.gov/40458076/), [39929977](https://pubmed.ncbi.nlm.nih.gov/39929977/) | 3/0/0 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| PRECLIN_ZINC_CARNOSINE | [23826914](https://pubmed.ncbi.nlm.nih.gov/23826914/), [24286534](https://pubmed.ncbi.nlm.nih.gov/24286534/), [28407007](https://pubmed.ncbi.nlm.nih.gov/28407007/), [35999163](https://pubmed.ncbi.nlm.nih.gov/35999163/), [36235778](https://pubmed.ncbi.nlm.nih.gov/36235778/) | 3/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| STRAIN_BB12 | [31797399](https://pubmed.ncbi.nlm.nih.gov/31797399/), [32059116](https://pubmed.ncbi.nlm.nih.gov/32059116/) | 1/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| STRAIN_BC30 | [40707016](https://pubmed.ncbi.nlm.nih.gov/40707016/) | 0/0/1 | new linked-abstract inspection; full applicability/RoB/approval unresolved |
| STRAIN_HN019 | [29227175](https://pubmed.ncbi.nlm.nih.gov/29227175/) | 1/0/0 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| STRAIN_LGG | [26365389](https://pubmed.ncbi.nlm.nih.gov/26365389/), [26756877](https://pubmed.ncbi.nlm.nih.gov/26756877/) | 0/0/2 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |
| STRAIN_SBOULARDII | [26216624](https://pubmed.ncbi.nlm.nih.gov/26216624/), [40535538](https://pubmed.ncbi.nlm.nih.gov/40535538/) | 1/0/1 | retained bounded packet; limitations preserved; full applicability/RoB/approval unresolved |

Public-paper summaries and source URLs are review evidence, not approved claims. Durable local primary bodies, exact frozen checksums, per-entry decisions, fail-first logs and350-label artifacts reside in `.claude/state/final-completion-campaign/`; private intake identifiers/photos are intentionally not added to this report.

### Reproducibility bindings

- Frozen15437 snapshot SHA-256 `1c4f581c8a52189751815f6f2fe9b6f5c1e59493c2409b04a95e88cf5810c983`; original baselinee88c61007bcf55533b190a2f3cf091399ae2ec7d.288retained payload/manifest checksums pass; no frozen-ID additions/removals.
- Original clinical register binding before this report update: `412703f6ccb410800e5659d90ad5be1eace170ed1ed8cda0e9516618b77df6c1`; recover exact original CSV from5c3982c5. All155clinical/506benchmark key sets and frozen dependency columns verified unchanged.
- Local `final-manifest.json` SHA-256 `700a3b3e270258e0fbb835c006df841ea89ff20a765c6d3f50b0e4ae61d8d3de`.
- Local `final-baseline.jsonl` SHA-256 `347be3efb9168f9db42fcbd2881ccdd3806978b28d0bbed0aa0c09f0f3f844ae`.
- Local `final-candidate.jsonl` SHA-256 `1d094666ff68d24db5a86ddffea09614a0aabf93165e5974ed7131274c6b9dde`.
- Local `measurement.json` SHA-256 `83892842db6ad4f82e017b9c16886fc60d2f84c76a8d43674429d36f4cad0970`.
- Candidate source-vector SHA-256 `c13a189f8f5b4618a7433110c60a109ea3cd49181e68b317c026a6170f21dd12`;443runtime files rechecked against current source, zero differences. Capture meta retains baselineHEAD because capture preceded commits; file-content vector binds actual candidate.
- Superseded305raw captures were byte-checked against final350capture and removed as exact duplicates; final capture, frozen manifests, baseline/candidate records, research and unique inputs retained. Private submissions and unrelatedSupabase work untouched.


## October25 — returned A001–A148 response verification

Original response is explicitly AI-assisted research, not an attributable Dr.Pham acceptance. All148rows checked against the original request/records and retained primary evidence; no comprehensive new148-paper full-text review claimed. [Per-item findings and corrected end blocks](A_RESPONSE_VERIFICATION_20261025.md).148unique numbers,146exactkeys plus2recovered; no2020–2026-only inclusionrule in request/owners.38age-restricted dispositions were not imported; A122availability is separate. Existing147sourceownerchecks still0complete andallcontextsmissing.

A011: complete official PMC indexed correctionbody now inspected despite directopen challenge. Retrospective2024-04-15registration ISRCTN14728094, author-statedunchangedprotocol andAIDPcommission/funding/patent/paidrelationship disclosures confirmed. This supersedes only the old correction-content accessgap, not studyqualification/approval. [Primary correction](https://pmc.ncbi.nlm.nih.gov/articles/PMC12190206/).

A090: primary22909270confirmsbisglycinate identity. Additional2025sleep source40918053/PMC12412596 identified; source methods, endpoints, relevantresults, funding/disclosures inspected. Report records a small subjective sleep finding with exact magnesium/glycine co-exposure; no efficacy threshold, exactproductapproval or registrychange. [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12412596/). A063abstract supports2caps/day400mgformula, not verifiedBIDtiming. PQQactualcorrectedTable4remainsunread. A146–A148full original sourceblocks existed allalong and are restored in the shortreport.

Three independent research slices cover50+50+48items; parent verified new substantive assertions and reconciliation. NCCIH/ODS generalcautions checked directly; CDCfolicacidguidancechecked, directACOGaccessunavailable/notmisattributed. ExistingCSV155rows/frozenIDs preserved; addedresponse receipt fields andpartialMagteincorrectioninspection only. No approval/completenessfields changed. Documentation/reportonly: no pytest/CI or pipeline rerun. Raw signedattachmentURLs notcommitted; original unchanged andhashbound.


## California poppy — bounded general Dose source review, October 28, 2026

Owner: `scripts/data/literature_evidence_records.json::california_poppy` →
`botanical_profile::_botanical_benchmark`; source proof:
`verify_literature_records::verify_reference_citations` /
`dose_assessment::verified_reference_citations`. Evidence: source-of-truth matrix Dose-reference
semantics, GLOSSARY, `rg reference_semantics/california_poppy/no_benchmark`, existing source-proof
and botanical callers. Will NOT create: registry, semantic/public field/status, numerical benchmark,
clinical approval, helper, material identity or alternate scorer. Behavioral data change; root owns the
combined CI/local checkpoint, final corpus and publication. Only this entry and named tests/fixture
are changed; existing helpers and consumer fixtures are untouched.

The real retained NIH raw MegaFood Dream Release62820 discloses California Poppy extract200mg
per tablet, with one tablet as needed before bedtime. Plant part, DER/extract ratio, solvent and marker
specification are absent. Its statement explicitly names California poppy with valerian for restlessness,
tension and sleep. The purpose-specific botanical Dose owner therefore assesses this row before its
fallback primary valerian300mg. Valerian's separately completed general reference cannot transfer.
The old October27 register's nonwinning/outside classification did not establish a California-poppy
source conclusion. Prior private review explicitly left it open; the vacuous historical bibliographic stamp
and empty qualifying-study list were not sufficient source proof.

Source content reviewed by **Codex**, not attributed to a clinician or an entry-specific October18
signoff. This review applies the already accepted DoseV4.1 policy: source regimens remain descriptive;
a completed review finding no generally applicable numerical curve uses existing neutral Dose, with
no efficacy minimum, optimum, safety UL or new magnitude. It is not a claim that no research exists.

| Source | Verified preparation/design and boundary |
|---|---|
| [EMA final assessment EMA/HMPC/680375/2013](https://www.ema.europa.eu/en/documents/herbal-report/final-assessment-report-eschscholzia-californica-cham-herba_en.pdf), pp20–22, sections4.2–4.4 | Explicitly no dose-response data. Describes an uncontrolled marketed2g sleep preparation, a fixed hawthorn/poppy/Mg trial, and a different standardized pain preparation. Concludes evidence does not meet well-established medicinal-use criteria. None establishes a universal dose scale for an unspecified200mg extract. |
| [EMA final monograph EMA/HMPC/680372/2013](https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-eschscholzia-californica-cham-herba_en.pdf), pp2–3 | Traditional use of powdered flowering aerial parts. Its powdered-herb posology remains a specific reference; no powder-to-extract equivalence or transfer to unspecified retail extract. |
| [EMA2022 addendum EMA/HMPC/648153/2022](https://www.ema.europa.eu/en/documents/herbal-report/addendum-assessment-report-eschscholzia-californica-cham-herba_en.pdf), review2015–June2022 | No new single-active-product/clinical basis requiring monograph revision. This is not an absence claim about combination research. |
| [PMID14741074](https://pubmed.ncbi.nlm.nih.gov/14741074/), Hanus2004; live PubMed abstract and EMA assessment4.2.2 | Randomized fixed Sympathyl combination in264 adults with mild-to-moderate anxiety: each tablet contains75mg hawthorn extract,20mg dry aqueous Eschscholzia extract and75mg elemental Mg; two tablets twice daily. No isolated poppy dose-response or equivalence to Dream Release. Original full article was not available in this bounded check; EMA authoritatively supplies the exact preparation detail. |
| [PMID32257874 / PMC7109475](https://pmc.ncbi.nlm.nih.gov/articles/PMC7109475/), sections1,2.1,2.3 | Open-label observational adjustment-insomnia study. Named Phytostandard combination:80mg flowering-aerial-parts Eschscholtzia extract plus32mg valerian extract per tablet, maximum four tablets nightly for one month. Full text explicitly links E.californica to California poppy. No monotherapy attribution, isolated threshold or transfer to an unspecified200mg extract. |
| [Publisher DOI10.1016/j.sleepe.2026.100138](https://www.sciencedirect.com/science/article/pii/S2667343626000119), available publisher abstract reviewedOctober28 | Four-week randomized fixed Eschscholtzia/valerian combination,847mg+353mg daily, for insomnia with anxiety; a combination comparison does not isolate a universal poppy benchmark. Direct full-page/PDF retrieval returned403; publisher-indexed abstract was accessible. Preparation details beyond that abstract were not assumed. No new efficacy grade is assigned. |

Official EMA PDFs were retrieved directly despite the web reader's429 response; durable copies,
extracted text and live PubMed articles are under
`~/pg_quality/condition_scope_20261028/california_poppy_sources/`. Source hashes:

- EMA assessment: `fff8cabe258f09bdfdc8ca9a509e32a4b60fcb0750bea7fe2d7a345ea82a07c9`.
- EMA monograph: `1a66324cb8ad1bbe6165e26c1bb912f140522afc2886e1810463ba178d1b876c`.
- EMA2022 addendum: `aadcad32b37903e133a80b34b5e3f58e2cf6d59debaa575c7fa86c36649dc87c`.
- PMC7109475 full-text XML: `1199cfbc8cf049879dc201a0b787640fe92e5fed4edaa550bf3135582c38cf50`.

The existing manual exact-content source-proof path is deliberate and tested by
`test_reference_recheck_preserves_reviewed_scope_only_for_identical_source`. The literal automated
California-poppy keyword screen cannot establish the Latin-named study relation. Actual API content
is not altered. Codex manually reviewed the identity/preparation relation using full text and EMA;
proof notes retain that attribution, limitations and document hashes. Subsequent machine recheck
preserves the reviewed source relationship only if the complete reference semantics and real article
content hashes remain identical; changed content invalidates it. No API-returned common-name text,
clinical approval, correction clearance or retraction flag was invented.

Decision: completed **general Dose no-applicable-universal-benchmark** review for this canonical,
using the existing `approved_existing_neutral_dose_v41_source_review` policy status. This names the
existing neutral policy, not a new clinician or Sean scientific signoff. Specific traditional and study
preparations are retained descriptively. Exact retail composition remains unknown; no concentration
conversion is made. `qualifying_human_studies=[]`, `effect_direction=null`, `studied_dose_exposure={}`
and `applicability_unestablished` remain. No affirmative Evidence credit is authorized.

Fail-first record and real raw→Clean→Enrich→public-score regressions reproduced the unresolved
reference before this entry change; both now pass. The test checks the configured archetype-neutral
Dose through its existing helper, with other pillar scores and safety unchanged. Named owner slice:
413 passed (`california_poppy/owner_slice.log`); final two source/public nodes also pass after prose
qualification (`focused_final.log`). Python correctness0new/11existing, diff check clean. Exact data
check since2bb61ca7: `literature_evidence_records[619]` (california_poppy),1changed entry/0problems.
The generic citation CLI has no configuration for this file; the dedicated literature verifier was used.
It fetched both PubMed sources live, validates2/2 reference-citation proofs and records no retraction.
Its sole clinical-screen finding remains `no_studies_to_verify`, because the qualifying-study list is
intentionally empty. That is not a failed Dose-source proof and is not hidden or changed into a clinical
approval. Overall clinical-verifier success is not claimed.

Clean pre-edit five-label baseline at2bb61ca7 is retained in `california_poppy/baseline.jsonl` with
source_unchanged=true. Frozen affected62820/62831 plus module controls306237/19055/182730 use
one manifest. Candidate measurement and fresh review follow the clean source commit; no combined
readiness or corpus qualification is inferred from these targeted tests.


Bounded measurement completed on clean source
`9afc2a00ddc2acb6bf40ee85c2b71b0c81fc7083`, five products/source_unchanged=true,
against clean2bb61ca7 with the identical frozen manifest/raw hashes. Both affected Dream Release
labels62820/62831 move Dose0→11.4 (the existing configured neutral), total49.2→60.6,
Poor→Needs improvement; controls306237/19055/182730 stay unchanged. Every other pillar,
route/subroute/profile/status, safety gate, Dose-safety and captured readiness projection is unchanged.
The benchmark disposition changes unresolved→absent. Receipts:
`california_poppy/candidate.jsonl[.meta.json]`, `delta.json`, `movement.txt`.

The complementary real public-artifact probe (`public_release_source_probe.json`) directly confirms
`unfinished_source_assessment` changes `dose_benchmark_identity_unresolved`→null for both labels.
Evidence remains0; no concern/warning or other pillar changes. Overall assessment remains partial on
this lane's source because the separate Evidence review is not cleared by Dose. Root owns combined
Evidence/readiness qualification; this is not an all-six-pillars or release-completion claim. The exact
existing backlog row is reconciled now; its frozen workload counts and product IDs are preserved.
Independent pregnancy_check review of9afc2a00 cleared the data/source interpretation: three named
policy/raw-preservation/manual-recheck tests pass; exact entry data check has0problems. Reviewer
independently matched all four retained EMA/PMC document hashes, verified the2004 fixed-combination
source and the2026 official publisher-indexed abstract's847mg+353mg methods. No source blocker
remains in this bounded batch. Root's combined CI/local, final artifact generation and release
qualification remain. No broad suite, corpus, branch push, main action or publication occurred.
