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
