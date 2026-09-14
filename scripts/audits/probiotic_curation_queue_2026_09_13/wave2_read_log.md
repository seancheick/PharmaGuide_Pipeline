# Wave 2 — PubMed title/abstract read log (2026-09-14)

Working notes for wave2_contexts.py. Every PMID below was read title/abstract
via the PubMed API on 2026-09-14. "Recorded" PMIDs become contexts; "reviewed,
not recorded" PMIDs are listed with the reason so the clinician sees the full
search picture. Doses are noted only where the retrieved abstract text states
them unambiguously (older abstracts often keep "(9)" exponents; newer ones
lose superscripts).

## STRAIN_COAGULANS_IS2 (B. coagulans Unique IS-2, MTCC 5260)

Recorded:
- 31434935 — adult IBS RCT (Rome III), 153 enrolled / 136 randomized, 2e9
  CFU/day 8 wk, multicenter, double-blind; abdominal pain/discomfort and CSBM
  primary, positive; cytokines unchanged; industry (Unique Biotech authors).
- 29695183 — pediatric IBS RCT, n=141, 4-12 y, chewable once daily 8 wk;
  pain intensity positive (p<0.0001); industry.
- 30911991 — adult functional constipation RCT, n=100, 2e9 CFU 4 wk;
  >=3 spontaneous stools/wk positive; industry; CTRI/2017/11/010539.
- 34599466 — functional constipation, IS2+lactulose vs lactulose vs placebo,
  n=150, 2e9 spores + 10 g lactulose 4 wk; stool-frequency advantage
  transient (end-of-trial NS vs lactulose); consistency/evacuation/pain
  positive; co-therapy lactulose; industry; CTRI/2018/11/016399.
- 40456531 — healthy adults with infrequent BM (3-7 CSBM/wk), n=144, 2e9
  CFU/day 4 wk; BM frequency positive (p=0.037), consistency positive;
  GI symptoms, QoL, microbiota null; PepsiCo/Nutrasource; NCT05123664.
- 36372047 — chronic constipation SR/meta (30 probiotic RCTs): overall
  response positive, but IS2 specifically NOT significant for stool
  frequency (B. lactis species-level was). NULL kept for IS2.
- 41682832 + 37686889 — two IBS metas (strain-specific 2026 PROSPERO
  CRD420251047092; outcome-specific network meta 2023): IS2 among strains
  with efficacy for key IBS symptoms / top-ranked for abdominal pain.
  Same underlying IS2 trials as 31434935/29695183 — one context, family
  marks non-independence from the RCT contexts.
- 35249118 — whey-protein absorption/strength RCT, resistance-trained males,
  2e9 CFU + 20 g whey daily 60 d; plasma BCAA up, leg press/vertical jump
  positive; surrogate-heavy; industry co-authors; CTRI/2017/03/008117.
- 39866999 — moderate COVID-19 adjunct, 3-arm (UBBC-07 / IS-2 / placebo),
  n=56, 2e9 spores twice daily (4e9/day) 14 d with standard treatment;
  ferritin (both arms) and D-dimer (IS-2 arm) reduced; CRP/LDH/IL-6 null;
  small, Cureus, surrogates only.

Reviewed, not recorded:
- 33456469 — pediatric salivary/plaque S. mutans counts, n=48, 2 wk;
  chairside surrogate microbiology only.
- 32601955 — exam-stress multi-strain (IS2 + UBLR58/UBBLa70/UBLP40/UBBr01/
  UBBI01 + glutamine): partner strains are not registry identities; no
  scored product carries the formulation.
- 31965834 — UB0316 weight-management multi-strain: same registry-absence.
- 37804865, 36641109, 35735411 — rat models (OCD/anxiety/depression).
- 36975693, 34176401 — preclinical formulation (suppository/emulgel).
- 33694215 — in vitro HCT-116; 33677909 — broiler chickens.

## STRAIN_COAGULANS_MTCC5856 (B./Weizmannia coagulans MTCC 5856, LactoSpore)

Recorded:
- 26922379 — IBS-D pilot RCT, n=36, 3 centres, 2x10(9) cfu/day 90 d with
  standard care; bloating/vomiting/diarrhea/pain/stool frequency positive
  (p<0.01); pilot size; industry (Sami/Sabinsa).
- 29997457 — MDD-with-IBS pilot RCT, n=40, 2e9 spores/day 90 d; HAM-D/MADRS/
  CES-D/IBS-QOL positive; myeloperoxidase reduced; pilot, industry.
- 36862903 — functional gas/bloating RCT, n=70 (66 completed), 2e9 spores/day
  4 wk; GSRS-indigestion positive, patient global positive; industry.
- 38269290 — pediatric acute diarrhea adjunct (ORS+zinc both arms), n=110,
  1-10 y, 5 d; duration positive (51.3 vs 62.7 h, p=0.011), frequency NS;
  dose printed as "4 x 10 spores" with exponent stripped -> unresolved;
  CTRI/2022/06/043239; industry.
- 37335737 — healthy-adult microbiome/safety RCT, n=30, 2e9 CFU/capsule
  28 d; gut microbiome composition essentially unchanged (null physiology);
  industry.
- 41682832 + 37686889 — the same two IBS metas: MTCC 5856 improved IBS QoL
  (2026 meta) and ranked top for abdominal pain and IBS-D stool form
  (2023 network meta); family marks overlap with 26922379/29997457.

Reviewed, not recorded:
- 37016604 — LactoSporin topical cosmetic (extracellular metabolite, not the
  live strain; skin-aging endpoints).
- 41829987 (cosmeceutical review), 41358721 (narrative review),
  41258512/38907946 (fermented-food development), 39087597 (M-SHIME in
  vitro), 33773667/31421399/31554104/33580694/31108774 (food-processing
  survival), 29876118 (in vitro prebiotic), 29474436 (flow cytometry
  enumeration), 26925622 (genetic consistency; identity evidence only).

## STRAIN_ACIDOPHILUS_DDS1 (L. acidophilus DDS-1)

Recorded:
- 32019158 — IBS RCT n=330, 3-arm (placebo / DDS-1 / UABla-12 solo arms), 6 wk;
  APS-NRS primary positive for the DDS-1 arm; IBS-SSS positive; dose printed
  with a stripped exponent -> unresolved; industry (UAS Labs).
- 27207411 — lactose-intolerance crossover RCT (DDS-1 solo), 4-wk arms with
  washout; 6-h challenge symptom scores positive (diarrhea, cramping,
  vomiting, overall); dose not stated; industry (Nebraska Cultures).
- 36308983 — LI systematic review (PROSPERO CRD42022295691): DDS-1 improved
  LI symptoms, LOW certainty, no pooling possible; family overlaps 27207411
  (its DDS-1 trial IS 27207411).
- 33584665 — night-shift workers RCT, solo DDS-1 arm (n=29/arm), 14 d:
  moderated anticipatory-stress serum markers pre-shift; NO interaction
  effects across night shift -> mixed surrogate; ANZCTR 12617001552370.
- 37686889 — network meta: DDS-1 ranked first for IBS-SSS improvement
  (SUCRA 92.9%); family overlaps 32019158.
Combinations recorded under the EXISTING identity STRAIN_LACTIS_UABla12
(no stub needed: the 2026-09-14 add_identity attempt was refused because
every UABla-12 alias is already owned by that identity; the designation
"B. animalis subsp. lactis UABla-12" was also verified in the
32019158/36071965 reads):
- 36071965 — pediatric FC chewable (DDS-1+UABla-12, 5e9/day) n=92 4 wk;
  faster stool-frequency normalization; single-blind; Sirio/Chr. Hansen.
- 26463725 — pediatric ARI household-exposure (DDS-1+UABLA-12+FOS, 5e9/day)
  n=315/225 analyzed: incidence NULL primary (57% vs 65%, p=0.261);
  resolution time and severity positive secondary.
- 20642296 — atopic dermatitis 1-3 y (DDS-1+UABLA-12+FOS, 5e9 twice daily)
  n=90 8 wk: SCORAD percentage decrease positive (33.7% vs 19.4%); less
  topical corticosteroid.

Reviewed, not recorded:
- 31271261 — adult FC 4-strain (adds UABl-14 [registry stub] and UABb-10,
  which has NO registry identity): PAC-SYM between-group NULL primary;
  faster normalization secondary. Not recorded because a combination
  context must name every component and no identity stubs were added in
  Wave 2; candidate for a future wave if a UABb-10 identity is created.
- 16398599 (soy/probiotic hormones crossover; generic B. longum partner
  unnamed; hormones unaffected), 42141695/41399631/... (not fetched;
  bounded search).

## STRAIN_PLANTARUM_299V (L. plantarum 299v, DSM 9843)

Recorded:
- 37541528 — IBS SR/meta (82 RCTs / 10,332; Gastroenterology 2023): LOW
  certainty of benefit for 299v on global symptoms; strain named explicitly.
- 30388595 + 39271063 — MDD SSRI-augmentation RCT (n=79 randomized / 60
  analyzed, 8 wk): cognition (APT, CVLT) positive, kynurenine decreased;
  HAM-D not reported as improved between groups -> cognition-scoped record;
  metabolomics companion is the SAME cohort (one family).
- 31816981 — iron-absorption SR/meta (8 studies, n=950): SMD 0.55 positive;
  iron-status studies mostly unchanged -> absorption surrogate positive,
  status mixed.
- 32365981 — iron-deficient female athletes RCT (n=53/39 completed,
  20 mg iron +/- 299v, 4-12 wk): ferritin p=0.056 NS, CHr p=0.083 NS,
  POMS vigor positive, performance inconclusive -> mixed; Probi/Nature's
  Bounty industry.
- 33015813 — cancer home-enteral-nutrition RCT (n=35, 2 x 10^10 CFU/day
  4 wk): albumin positive, vomiting/flatulence reduced; nutritional status
  overall unchanged; QoL between-group NS.
- 12450890 — smokers CVD-risk RCT (n=36, rose-hip drink 400 mL x 5e7
  CFU/mL = 2e10/day, 6 wk): SBP, leptin, fibrinogen decreased; small, food
  matrix, older methodology.
- 28101105 — exam-stress salivary cortisol RCT (n=41, 14 d): cortisol rise
  prevented vs placebo, salivary IgA null; NCT02974894.
- 22434095 — elective colon-resection RCT (n=75): enteric bacteria load,
  bacterial translocation, postoperative complications all NULL.

Reviewed, not recorded: 36839232 (pregnancy feasibility pilot n=20;
retention/adherence endpoints only).

## STRAIN_ACIDOPHILUS_LA5 + STRAIN_LACTIS_BB12 (combinations + BB-12 solo)

Recorded (combination contexts owned by LA5 unless noted):
- 41255078 — non-constipated IBS RCT n=200, LA-5+BB-12, 84 d: IBS-GIS
  response and IBS-SSS pain/distension/QoL positive.
- 24772726 — AAD multicentric RCT (adults on cefadroxil/amoxicillin, 14 d
  LA-5+BB-12): AAD incidence NULL primary (10.8% vs 15.6%, p=0.19);
  diarrhea duration positive (2 vs 4 d); severe-diarrhea subgroup positive.
- 17356555 — hospitalized adults, fermented milk LGG+La-5+Bb-12 (n=87,
  14 d): AAD 5.9% vs 27.6% positive; components [LGG, LA5, BB12].
- 25588782 — children 1-12 y on antibiotics, yogurt LGG+Bb-12+La-5
  (n=70, 200 g/day): severe diarrhea 0 vs 6 (p=0.025); components
  [LGG, LA5, BB12].
- 21871144 — H. pylori-infected adults, fruit yogurt LA-5+BB-12 3-arm
  (n=88, 8 wk incl. eradication week): AAD days 4 vs 10 vs 10 positive;
  H. pylori urease activity fell in ALL milk arms -> activity change not
  attributable to the probiotic; nuance kept.
- 30439760 — hospitalized adults yogurt LA-5+BB-12+LC-01 (n=314): AAD
  NULL (23.0% vs 17.6%); third strain LC-01 has no registry identity —
  limitation states the 3-strain formulation.
- 39102225 — PRIMAL phase 3 preterm 28-32 wk (n=618): La-5+BB-12+
  unnamed B. longum subsp. infantis; MDRO+ colonization NULL primary;
  eubiosis score positive secondary; third component unnamed — limitation.
- 41748464 — ProPACT maternal LGG+Bb-12+La-5 (n=415 pregnant women):
  offspring atopic dermatitis reduced (stated in this longitudinal T-cell
  companion's abstract); components [LGG, LA5, BB12]; family propact.
BB-12-anchored:
- 39271904 — preterm infants <=32 wk BB-12 solo RCT (n=71): serum TLR4/
  NF-kB/IL-1b/TNF-a lower, feeding intolerance lower; surrogate-heavy.
- 33811784 — pediatric AD-prevention network meta (21 RCTs / 5406):
  LGG+Bb-12 mix reduces AD risk (RR 0.50, LOW quality); combination
  [LGG, BB12].
- 39310372 — WAO DRACMA SR: eHF-CM + L. casei CRL431 + Bb-12 -> higher CMA
  tolerance acquisition (RR 2.47) and less severe wheezing, LOW certainty;
  combination [CASEI_431, BB12] with formula co-therapy.
- 37020105 — preterm neonates n=68, LGG+Bb-12 direct vs via lactating
  mother: microbiota composition shifted (bifidobacteria up) only with
  direct administration; physiology surrogate; components [LGG, BB12].

Reviewed, not recorded: 42151830 (uncontrolled synbiotic pilot n=18),
40180370 (protocol), 35807801 (4-strain with UBLP-40 — no registry
identity), 29737805 (GDM combo with STY-31/LBY-27 — no registry
identities), 33473294 (4-arm yogurt vit-D cofortification; lipid NULL;
strain attribution confounded by matrix/vitD design), 34940074 (oncology
surgery SR, strain-nonspecific), 30937345 (LactoflorenePlus, different
strains), 38337634 (narrative review). BB-12 solo colic/daycare-RTI
classics were not re-fetched this wave (bounded search; the registry's
existing BB-12 context and Wave 1 families remain separate).

## STRAIN_HELVETICUS_R0052 + STRAIN_LONGUM_R0175 (pair; CEREBIOME lineage)

Recorded (combination contexts, owner R0052, components [R0052, R0175]):
- 20974015 — Messaoudi 2011 healthy volunteers, 30 d: HSCL-90 global severity,
  HADS and 24-h urinary free cortisol improved; the paper's rat arm is not a
  human context; dose not stated in the abstract.
- 32989186 — BDNF secondary analysis of the Kazemi cohort (110 randomized /
  78 analyzed, 8 wk): parent trial's depression improvement restated; BDNF
  up vs prebiotic and placebo; family kazemi_mdd (one cohort).
- 33658952 — open-label single-arm pilot, 10 treatment-naive MDD patients,
  3e9 CFU/day 8 wk: affective symptoms improved; NO control arm.
- 37049546 — healthy adults n=135, 4 wk: NO significant whole-sample effects
  (null primary); lifestyle-interaction finding is exploratory; NCT04823533.

Reviewed, not recorded: 35405944/35571902 (Örebro fMRI crossover adds
L. lactis R1012 — no registry identity), 40520599 (SCFA mediator secondary
only), 40572172 (n=15 exploratory, hypothesis-generating per authors),
31472678 (protocol), 23068715/29453804 (rat). Catalog note: Life
Extension/Pure labels print "Rosell-52 ME"/"Rosell-175 ME"; whether the ME
suffix reaches these identities is an alias question for identity work,
not for contexts.

## STRAIN_RHAMNOSUS_GR1 + STRAIN_FERMENTUM_RC14 (pair)

Recorded (owner GR1, components [GR1, RC14]):
- 34295831 — BV adjunct to metronidazole, n=126, 30 d oral: cure rate NULL
  at 30 and 90 d; probiotic species rarely detected in vaginal/fecal
  microbiota.
- 30932317 — pregnancy oral supplementation from 9-14 wk, n=238 analyzed,
  2.5e9 each (5e9/day): BV at 18-20 wk NULL; no colonization or microbiota
  change.
- 32325794 — pregnant women at risk for preterm labor, open crossover,
  n=38: vaginal colonization of the administered strains rare (null
  colonization surrogate).
- 27590374 — GBS-positive pregnant women 35-37 wk, n=99: conversion to GBS
  negative on admission 42.9% vs 18.0% (p=0.007) positive.
- 31953482 — ProSCIUTTU secondary (spinal-cord injury, n=207, 4-arm incl.
  LGG-BB12 arm): RC14-GR1 reduced NEW multiresistant gram-negative
  colonization (OR 0.10); no clearing effect; family prosciuttu (the UTI
  primary paper was not read this wave).

Reviewed, not recorded: 39836666 (phase 1 feasibility), 24299970 (narrative
review).

## STRAIN_COAGULANS_GBI30 (B. coagulans GBI-30, 6086 / BC30)

Recorded:
- 40707016 — healthy adults with functional GI complaints, n=111, 1e9/day
  4 wk: stool frequency, consistency and constipation-proportion positive;
  Kerry industry; NCT06644001.
- 31162597 — synbiotic whole-grain pasta (BC30 + barley beta-glucans),
  n=41, 12 wk: primary hs-CRP and lipid profile NULL overall; subgroup
  signals only; single-blind; matrix/co-therapy confound stated.
- 32318476 — geriatric indigestion, open-label, co-formulated with
  digestive enzymes, 5 d: dyspepsia severity positive; attribution
  confounded by enzymes; open label.

Reviewed, not recorded: 38172876 (PCOS synbiotic; unnamed partner strains),
39281311 (horses), 33940614 (dogs), 40831181/40777909 (not fetched; bounded).
Classic BC30 IBS/protein-cotherapy trials did not surface in this bounded
search and remain future curation.

## STRAIN_BREVE_M16V (B. breve M-16V)

Recorded:
- 41515257 — SiMPro five-year follow-up, extremely preterm <28 wk: single
  M-16V vs triple M-16V+M-63+BB536; neurodevelopment, growth, BP and atopy
  comparable (comparative design, no placebo); components joinable
  [M16V] with comparator description (M63 and BB536 exist in registry).
- 41994268 — neonatal jaundice under phototherapy, 4-arm n=79 (control /
  M-16V / Bb-12 / M-16V+Bb-12), 30 d: defecation frequency up, faster
  transcutaneous-bilirubin reduction, shorter stay; neurodevelopment
  domain signals for the Bb-12 arm; industry-adjacent (Diprobio).
- 39915586 — C-section-born healthy infants, synbiotic formula M-16V +
  scGOS/lcFOS vs prebiotic formula, n=284 randomized: bifidobacterial
  restoration surrogate positive; Danone; NCT03520764.

Reviewed, not recorded: 39469104 (n=29 subset analysis of a formula trial),
38523836 (protocol), 42544179/42533554/40085083 (Wave 1 families for
BB536/HN019 — already read there), remaining hits not fetched (bounded).
Classic Japanese preterm colonization trials remain future curation.

## STRAIN_PLANTARUM_LP01 (L. plantarum LP01, LMG P-21021)

Recorded:
- 29949873 — synbiotic (LP01 + BB12 + prebiotics), adults with Rome III
  functional constipation, n=85, 12 wk: stool evacuation, PAC-SYM and
  PAC-QOL differences NOT significant vs placebo (high placebo response);
  combination [LP01, BB12] with synbiotic co-therapy; null kept.

Reviewed, not recorded (defines why LP01 stays evidence-thin): the LP01
RCT base is multi-strain Probiotical formulations whose partner strains
have no registry identity - LF16/LR06/B. longum 04 mood/sleep/metabolic
trials (37720373 positive mood; 39468832 subthreshold depression with NULL
primary psychological outcomes; 38350465 subjective sleep positive;
40729791/41978077 secondary analyses), Abincol LLC02/LDD01 open studies
(38818860, 33426860), Abivisor post-eradication open study (38536095),
LF15+LP01 vaginal tablets pilot (25291116, non-oral delivery), and the
uncontrolled crystalluria phase II with BR03 (39206631). No controlled
BR03 co-trial was read, so no BR03 identity stub is added this wave.
