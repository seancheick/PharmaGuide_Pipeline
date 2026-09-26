# Interaction-rule citation triage — evidence receipts (2026-09-25)

Scope: the 88 suspect (PMID, rule, sub-rule) citations / 48 PMIDs reported by
`scripts/api_audit/verify_interaction_rules_citations.py --strict` at b1dbe9d1. Every PubMed
record below was read live (efetch, whole abstract; PMC full text where noted) and every web
source fetched on 2026-09-25 by an agent. Not clinician-reviewed. Quotes are verbatim.
Dispositions: **re-sourced** (wrong-topic citation replaced, mechanism rewritten to the new
source, one commit per rule) or **reviewed** (legitimate class-level / constituent citation,
recorded in `scripts/data/interaction_rules_ghost_review.json`).

## RULE_IQM_RED_CLOVER — re-sourced (anticoagulants, thyroid_disorder; sibling bleeding_disorders)

- Ghost: **PMID 9464451** = "Anti-thyroid isoflavones from soybean: isolation, characterization,
  and mechanisms of action" (Biochem Pharmacol 1997). Soybean TPO study; cited for
  drug:anticoagulants, where it supports nothing. It stays on thyroid_disorder as a constituent
  citation: "genistein and daidzein blocked TPO-catalyzed tyrosine iodination by acting as
  alternate substrates"; "IC50 values ... ca. 1-10 microM".
- **PMID 10902065** (Heck, AJHP 2000), abstract: herbs "that may potentially increase the risk of
  bleeding or potentiate the effects of warfarin therapy include ... red clover"; "nearly all of
  it is based on in vitro data, animal studies, or individual case reports".
- **PMID 29541484** (Hall, Surg Neurol Int 2018), abstract: "Red Clover have theoretical bleeding
  risks based on coumarin content with very little underlying evidence"; 65-year-old woman,
  acute-on-chronic subdural hemorrhage; "Her normal INR combined with an intraoperative
  thromboelastogram confirmed a coagulopathy which was more consistent with anti-platelet
  effects than coumarin toxicity."
- **MSKCC About Herbs: Red Clover** (https://www.mskcc.org/cancer-care/integrative-medicine/herbs/red-clover):
  "Red clover may increase effects of anticoagulants and antiplatelet drugs"; "Preclinical
  studies suggest red clover may increase their effects. Clinical relevance has yet to be
  determined."; case reports of subdural hematoma (red clover) and subarachnoid hemorrhage (a
  supplement containing red clover, dong quai and Siberian ginseng). No coumestrol statement.
- **PMID 30132047** (Hüser, Arch Toxicol 2018; PMC6132702, CC BY), full text: "The major
  constituents of red clover and red clover-based food supplements are formononetin and
  biochanin A ... but other isoflavones, such as genistein, daidzein ... were also identified";
  "consumption of soy-based foods is unlikely to have an adverse effect on the thyroid gland
  system in healthy humans, if the iodine intake is adequate"; "the available studies indicate
  that isoflavones might exhibit a negative impact on the thyroid hormone system in patients
  with thyroid dysfunction".
- Removed as unsourced: coumestrol "structural similarity with vitamin K antagonists";
  "present in red clover at significant concentrations"; "competitively inhibit TPO at
  nutritional concentrations"; bleeding_disorders "no direct clinical evidence of red
  clover-induced bleeding has been documented" (contradicted by the case reports above).

## RULE_IQM_CITRUS_BERGAMOT_CHOLESTEROL — re-sourced (six drug-class sub-rules)

- Ghost: **PMID 39517207** = "Bergamot (Citrus bergamia), a (Poly)Phenol-Rich Source for Improving
  Osteosarcopenic Obesity: A Systematic Review" (Foods 2024). Names bergamot; says nothing about
  CYP3A4 or any drug. Was cited on all six drug sub-rules.
- **PMID 23184849** (Bailey, CMAJ 2013; no PubMed abstract; full text read at PMC3589309):
  furanocoumarins are "metabolized by CYP3A4 to reactive intermediates that bond covalently ...
  causing irreversible inactivation"; "Seville oranges ... limes and pomelos also produce this
  interaction"; simvastatin AUC "700%" (400 mL 3x/d) and "330%" (200 mL/d); pravastatin no
  interaction, rosuvastatin eliminated unchanged, fluvastatin via CYP2C9; felodipine "3-fold"
  (one serving), "5 times" (repeated); Table 1 lists nifedipine (hypotension, peripheral edema),
  apixaban and rivaroxaban ("GI bleeding"); cyclosporine bioavailability "162%" (one patient
  670%); tacrolimus "1000% higher trough"; amiodarone Cmax "180%", AUC "150%", QT prolongation and
  torsade de pointes; "increased oral bioavailability of estrogens (ethinylestradiol and
  17-β-estradiol)"; Table 2 venous thrombosis with ethinylestradiol after "1 fruit/d ... for
  preceding 3 d". Kept as the grapefruit (class) source; it does not name bergamot.
- **PMID 18830151** (Gardana, Molecules 2008): bergamot juice — "Bergapten and bergamottin were the
  primary furanocoumarins in BJ and their amounts were 9.0+/-0.4 and 18.2+/-0.5 mg/L".
- **PMID 15592332** (Goosen, Clin Pharmacol Ther 2004): bergamottin capsules with felodipine in 11
  volunteers; "with 12 mg bergamottin, felodipine C max increased by 40% ... and AUC increased by
  37%"; grapefruit juice (1.7 mg bergamottin) raised AUC 54%; "Bergamottin ... may cause a
  clinically relevant drug interaction in susceptible individuals. Grapefruit juice-drug
  interactions likely also involve other furanocoumarins".
- **FDA consumer update** "Grapefruit Juice and Some Drugs Don't Mix": grapefruit interacts with some
  statins (simvastatin, atorvastatin), nifedipine, cyclosporine, amiodarone; names Seville
  oranges, pomelos and tangelos, not bergamot, and no DOAC or contraceptive. Kept only on the four
  sub-rules whose drugs it names.
- No clinical study of a bergamot supplement with any of these drugs was found
  (PubMed: `(Citrus bergamia[tiab] OR bergamot[tiab]) AND (CYP3A4 OR cytochrome OR drug
  interaction OR furanocoumarin* OR bergamottin)`, 20 hits, none a bergamot-drug study).
  evidence_level "established" → "limited" on all six: the vocabulary reserves "established" for
  "consistent clinical or regulatory backing". Severities unchanged (policy; reported to Sean).
- Removed as unsourced: "statin AUC 5-15×", "P-gp inhibition" for DOACs, "effect is documented but
  small" for contraceptives, "dramatically raising drug levels".

## RULE_IQM_SAW_PALMETTO_LIVER — re-sourced (pregnancy_lactation, anticoagulants, ttc; sibling alert copy)

- Ghost: **PMID 16800417** = "Saw palmetto-induced pancreatitis" (South Med J 2006), a hepatitis +
  pancreatitis case; cited for pregnancy_lactation (it stays on liver_disease, where it fits).
- **NCCIH Saw Palmetto** (https://www.nccih.nih.gov/health/saw-palmetto): "Saw palmetto may be unsafe
  for use during pregnancy or while breastfeeding"; "Saw palmetto does not appear to affect readings
  of PSA". Nothing on fertility or bleeding.
- **PMID 16985705** (Fagelman, Rev Urol 2001): "in vitro some studies suggest that liposterolic
  extract of the plant has antiandrogenic effects that inhibit the type 1 and type 2 isoenzymes of
  5alpha-reductase; however there are no clinical studies that show any decrease in serum
  dihydrotestosterone or prostate-specific antigen".
- **PMID 31002161** (Cannarella, systematic review 2019): Serenoa repens extracts "has never been
  investigated for male infertility". (Rat data, PMID 34161166, found increased sperm counts.) The
  ttc claim that saw palmetto "can impair semen quality, reduce seminal fluid volume ... sperm
  motility" has no saw palmetto source; it is finasteride extrapolation. PMID 30980598 (herbal
  alternatives in androgenetic alopecia) was the ttc citation; it supports 5-alpha-reductase
  inhibition only and is replaced by 16985705. ttc evidence_level probable → theoretical.
- Ghost for anticoagulants: **PMID 10902065** (Heck 2000) does not list saw palmetto in its abstract
  (full text not open); dropped as unverifiable for this subject.
- **PMID 11489067** (Cheema 2001): severe intraoperative haemorrhage; "His bleeding time which was
  prolonged, normalized few days after he stopped the herb."
- **PMID 20120986** (Villanueva 2009): "a case of hematuria and coagulopathy in a patient who was
  using saw palmetto" — contradicts the old text "No documented case reports of saw palmetto
  altering INR".
- **PMID 18090773** (Beckert 2007): saw palmetto at the manufacturer's dose for 2 weeks in 10
  volunteers, PFA-100: "In vivo platelet function was not affected by the administration of any
  herbal agent". Contradicts the templated alert copy "Saw palmetto has mild antiplatelet
  activity" on anticoagulants, antiplatelets and nsaids.
- **PMID 19719333** (Izzo & Ernst systematic review 2009): "No interactions have been reported for
  saw palmetto (Serenoa repens)."
- Severities unchanged.

## RULE_IQM_VALERIAN_LIVER — re-sourced (pregnancy_lactation)

- Ghost: **PMID 18431248** = "A case of valerian-associated hepatotoxicity" (J Clin Gastroenterol
  2008; no abstract). A liver case cited for pregnancy/lactation; it stays on liver_disease.
- **EU herbal monograph, Valeriana officinalis L., radix** — EMA/HMPC/150848/2015 Corr.1, adopted
  2 February 2016.
  `https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-valeriana-officinalis-l-radix_en.pdf`
  4.6: "Safety during pregnancy and lactation has not been established. In the absence of sufficient
  data, the use during pregnancy and lactation is not recommended." 4.5: interactions "None reported".
- **LactMed: Valerian** — NBK501815, last revision 17 May 2021: "No data exist on the safety and
  efficacy of valerian in nursing mothers or infants"; "Valerian is often not recommended during
  lactation because of the theoretical concerns over its valepotriates and baldrinals which have
  been shown to be cytotoxic and mutagenic in vitro."

## RULE_IQM_KAVALACTONES_LIVER — re-sourced (pregnancy_lactation; seizure_disorder copy)

- Ghost for pregnancy_lactation: **PMID 27092496** = "Hepatotoxicity Induced by 'the 3Ks': Kava, Kratom
  and Khat" (Int J Mol Sci 2016). Liver review; no pregnancy/lactation content. Stays on liver_disease.
- **NCCIH Kava** (https://www.nccih.nih.gov/health/kava): "Kava may have special risks if taken during
  pregnancy or while breastfeeding because of the presence of harmful pyrone constituents"; "Various
  kava products have been linked to rare cases of liver injury, some of which have been serious or
  even fatal"; "Kava should not be used together with other substances that have sedative effects,
  such as benzodiazepines or alcohol." No seizure or withdrawal statement.
- No LactMed kava record (NCBI Books esearch `kava AND lactmed`: 0).
- seizure_disorder: **PMID 12383029** (Singh & Singh, CNS Drugs 2002) is on topic (kavalactones'
  "anticonvulsant" properties, GABA-A binding, sodium-channel blockade); the verifier's stems miss
  "anticonvulsant". Its withdrawal sentence is about conventional anxiolytics ("these agents"), not
  kava, so it cannot carry the rule's withdrawal-seizure claim. Sources that do:
  - **PMID 38829029** (Cassidy, J Addict Med 2024, case + systematic review): heavy user, "acute kava
    withdrawal with hyperactive delirium", treated with phenobarbital; of 9 studies, "Eight assessed
    withdrawal symptoms after cessation of a low controlled dose of kava extract with no symptoms
    noted. One reported a case series of heavy kava users with seizure-like events."
  - **PMID 22062945** (Pearl, Semin Pediatr Neurol 2011, herbs in epilepsy incl. kava): these herbs
    "paradoxically often have a proconvulsant effect"; "Herb-drug interactions also occur at the
    level of the P450 hepatic enzyme system ... and the P-glycoprotein transport system".
  Mechanism rewritten to these (withdrawal limited to heavy use); action keeps "do not stop
  abruptly" scoped to heavy use; evidence_level probable → limited (case-level evidence).

## RULE_IQM_COQ10_HEART_DISEASE_STATINS — re-sourced (heart_disease)

- The sub-rule's heart-failure claim ("improved ejection fraction and symptom class in Q-SYMBIO")
  cited only warfarin papers: **PMID 17723077** (CAM and warfarin bleeding cohort; CoQ10 OR 3.69 for
  self-reported bleeding) and **PMID 12083489** (CoQ10/Ginkgo and warfarin dosage RCT, a letter with
  no abstract, no DOI and no full-text link on PubMed: result unreadable, so dropped).
- **PMID 25282031** (Q-SYMBIO, JACC Heart Fail 2014): 420 patients, moderate to severe HF, CoQ10
  100 mg three times daily or placebo for 2 years; "There were no significant changes in short-term
  endpoints"; MACE "15% of the patients in the CoQ10 group versus 26% in the placebo group";
  cardiovascular mortality 9% vs 16%, all-cause 10% vs 18%, fewer HF hospital stays; "significant
  improvement of NYHA class ... after 2 years". No ejection-fraction result reported.
- **NCCIH Coenzyme Q10** (https://www.nccih.nih.gov/health/coenzyme-q10): "Research on the effects of
  CoQ10 in heart failure is also inconclusive"; "CoQ10 may interact with the anticoagulant (blood
  thinner) warfarin".
- 17723077 stays for the warfarin caveat the sub-rule carries (reviewed entry: topic heuristic miss).

## RULE_IQM_WHITE_WILLOW_BARK_BLEEDING — re-sourced (all five sub-rules)

- Ghost: **PMID 25997859** = "Efficacy and Safety of White Willow Bark (Salix alba) Extracts"
  (Phytother Res 2015). Efficacy review; says "Adverse effects appear to be minimal as compared to
  non-steroidal anti-inflammatory drugs including aspirin"; nothing on platelets, bleeding, warfarin
  or surgery. It was the only source for all five sub-rules. The verifier flagged three; antiplatelets
  and nsaids passed on the words "aspirin"/"non-steroidal".
- The mechanisms described aspirin, not willow: "Salicylates irreversibly acetylate
  cyclooxygenase-1 ... for the lifespan of the platelet (8-10 days)", "stopping willow bark 7-10 days
  pre-operatively is necessary", "displaces warfarin from albumin binding sites", "Additive
  irreversible COX-1 inhibition". None has a source; the sources below contradict the aspirin
  equivalence.
- **PMID 11345689** (Krivoy, Planta Med 2001; RCT): willow bark extract 240 mg salicin/day vs placebo
  vs 100 mg aspirin; mean maximal arachidonic-acid-induced aggregation "61%, 78% and 13%";
  willow vs placebo significant for AA (p = 0.04) and ADP (p = 0.01); "affects platelet
  aggregation to a far lesser extent than acetylsalicylate. Further investigation needs to clarify
  if this finding is of clinical relevance".
- **EU herbal monograph, Salix [various species], cortex** — EMA/HMPC/80630/2016, last revision
  31 January 2017.
  `https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-salix-various-species-including-s-purpurea-l-s-daphnoides-vill-s-fragilis-l-cortex_en.pdf`
  4.3 contraindications include "Active peptic ulcer disease", "Severe liver or renal dysfunction",
  "Coagulation disorders", "Third trimester of pregnancy"; 4.4 "Concomitant use with salicylates and
  other NSAIDs is not recommended without medical advice"; 4.5 "Willow bark may increase the effects
  of anticoagulants such as coumarin derivatives"; 4.6 first/second trimester and lactation "not
  recommended", "Salicylates cross the placenta and appear in breast milk"; 5.2 240 mg salicin →
  salicylic acid AUC "equivalent to that expected from an intake of 87 mg acetylsalicylic acid".
- surgery_scheduled evidence_level established → limited (no regulatory statement on surgery; one
  RCT with a modest platelet effect of uncertain clinical relevance). The "7-10 days" stop interval
  rested on irreversible COX-1 acetylation and is removed; action defers timing to the surgical team.
- Not changed, reported to Sean: pregnancy_lactation says limited data (no sources) while the EU
  monograph contraindicates willow bark in the third trimester and does not recommend it in
  lactation — a category/policy decision.

## RULE_BANNED_TANSY_PREGNANCY — re-sourced (pregnancy)

- Ghost: **PMID 28472675** = "Toxic essential oils. Part V: Behaviour modulating and toxic properties
  of thujones and thujone-containing essential oils of Salvia officinalis L., Artemisia absinthium
  L., Thuja occidentalis L. and Tanacetum vulgare L." (Food Chem Toxicol 2017). Rat open-field /
  diazepam-sleep tests and brine shrimp toxicity; no pregnancy content. Only source of a
  contraindicated pregnancy sub-rule.
- **PMID 33673548** (Dosoky & Setzer, "Maternal Reproductive Toxicity of Some Essential Oils and Their
  Constituents", Int J Mol Sci 2021; PMC7956842): "the whole plants of savin, pennyroyal, tansy, and
  rue can induce miscarriage and their oils were on the list of abortifacient oils"; "(R)-β-Thujone
  is found in ... tansy (Tanacetum vulgare L.) (45.2%)"; "thujone can affect the CNS and cause
  convulsions"; thujone inhibits GABA-A receptor currents.
- **PMID 232204** (Conway & Slocumb, J Ethnopharmacol 1979): plants used as abortifacients and
  emmenagogues by Spanish New Mexicans; "Other plants used are ... ponso or tanse-tansy".

## RULE_IQM_YERBA_MATE_CARDIOVASCULAR — re-sourced (anticoagulants)

- Ghost: **PMID 39708247** = "The Acute Ingestion of Yerba Mate (Ilex paraguariensis) Infusion Does Not
  Modify Endothelial Function, Hemodynamics, or Heart Rate Variability" (Plant Foods Hum Nutr 2024).
  Nothing on coagulation, vitamin K or warfarin. (It stays on hypertension/antihypertensives, whose
  mechanisms already state its null BP result.)
- The anticoagulant mechanism claimed yerba mate "contains vitamin K (phylloquinone) which may
  oppose" warfarin. No source found (PubMed: `(Ilex paraguariensis OR yerba mate OR mate tea) AND
  (warfarin OR vitamin K OR phylloquinone OR anticoagul* OR platelet* OR coagulation OR INR)`, 4 hits,
  none on vitamin K). It also contradicted the rule's own alert copy ("mild antiplatelet or
  anticoagulant activity").
- **PMID 25562195** (Yu, Exp Gerontol 2015; RCT, n = 142, high blood viscosity): yerba mate tea 5 g/day
  for 6 weeks; "the vasodilator 6-keto PGF1α increased while the thromboxane TXB2 decreased";
  whole-blood and plasma viscosity decreased.
- **PMID 23134458** (Dahmer, J Med Food 2012): chikusetsusaponin IVa from the fruit of Ilex
  paraguariensis "prolongs the recalcification time, prothrombin time, activated partial
  thromboplastin time, and thrombin time", inhibits thrombin, factor Xa and platelet aggregation in
  vitro; antithrombotic in rats "although it did not induce a significant bleeding effect".
- No clinical interaction study with anticoagulants found; evidence_level stays theoretical.

## RULE_IQM_ANDROGRAPHIS — re-sourced (autoimmune, immunosuppressants)

- Ghosts: **PMID 28745507** = "Discovery of Potent Orally Active Protease-Activated Receptor 1 (PAR1)
  Antagonists Based on Andrographolide" (J Med Chem 2017; synthetic antiplatelet derivatives) and
  **PMID 21822619** = "A novel role of andrographolide, an NF-kappa B inhibitor, on inhibition of
  platelet activation" (J Mol Med 2011). Both antiplatelet; cited for "immunostimulatory activity,
  upregulating T-cell proliferation, NK cell activity ... could theoretically exacerbate" autoimmune
  disease and for opposing immunosuppressants. Neither says anything about immune stimulation.
- No NCCIH andrographis page (404). No source found for immunostimulation worsening autoimmune disease.
- **PMID 19408036** (Burgos, Clin Rheumatol 2009; RCT, n = 60 active RA): A. paniculata extract
  (30% andrographolides) three times daily for 14 weeks; within-group reductions in swollen and tender
  joints, HAQ; "associated to a reduction of rheumatoid factor, IgA, and C4".
- **PMID 27215274** (Bertoglio, BMC Neurol 2016; RCT, 12 months, RRMS on interferon beta): 170 mg
  twice daily reduced fatigue; "No statistically significant differences were observed for relapse
  rate, EDSS or inflammatory parameters"; "A. paniculata was well tolerated".
- **PMID 33372366** (Worakunphanich, Pharmacoepidemiol Drug Saf 2021; SR/MA incl. autoimmune-disease
  trials): serious AEs "0.02 per 1000 patients"; nonserious AEs common (GI, skin).
- Mechanisms rewritten to these; severities (caution/caution) unchanged and reported to Sean as a
  probable over-warning. No study of andrographis with immunosuppressant drugs was found.

## RULE_IQM_BACOPA_THYROID — re-sourced (thyroid_disorder, thyroid_medications, sedatives)

- Ghost: **PMID 27912958** = "A systematic review of the Ayurvedic medicinal herb Bacopa monnieri in
  child and adolescent populations" (Complement Ther Med 2016). Cognition/behaviour in children;
  nothing on thyroid, levothyroxine or sedatives. Only source of all three sub-rules.
- **PMID 12065164** (Kar, J Ethnopharmacol 2002): male mice, B. monnieri leaf extract 200 mg/kg;
  "T(4) concentration was increased by B. monnieri extract suggesting its thyroid-stimulating role";
  "B. monnieri could increase T(4) concentration by 41%". No human data found (PubMed `Bacopa AND
  (thyroid OR thyroxine OR T4)`, 5 hits). The rule's "stimulation of thyroid iodide uptake and
  thyroglobulin synthesis" has no source and is removed; the thyroid-medication alert said bacopa
  affects "absorption" and advised dose timing, which fits no source.
- **PMID 36061899** (Front Nutr 2022, PMC9436272): bacopa "has been used for centuries in Ayurvedic
  medicine ... as a memory and learning enhancer, sedative, and anti-epileptic"; rodent data on
  GABAergic neurons.
- **PMID 18193203** (Prabhakar, Psychopharmacology 2008): in mice bacopa (120 mg/kg) reversed
  diazepam-induced anterograde amnesia ("antiamnesic effects"). No study of bacopa with sedative
  drugs was found; the rule's "Animal studies show additive sedative effects when combined with CNS
  depressants" has no source and is removed.

## RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES — re-sourced (antihypertensives; sibling sedatives copy)

- Ghosts for antihypertensives: **PMID 18296328** ("L-theanine, a natural constituent in tea, and its
  effect on mental state", EEG alpha activity at 50 mg) and **PMID 35378276** (herbal anxiety network
  meta-analysis; "L-theanine ... did not outperform a placebo"). Neither measures blood pressure; the
  rule said "modest blood pressure reductions (approximately 5-8 mmHg systolic) in small RCTs".
- **PMID 23107346** (Yoto, J Physiol Anthropol 2012; PMC3518171; crossover n = 14): L-theanine 200 mg
  "significantly inhibited the blood-pressure increases in a high-response group" under mental
  stress (already the rule's min_effective_dose source; 200 mg confirmed in full text).
- **PMID 17891480** (Rogers, Psychopharmacology 2008; RCT n = 48): 200 mg theanine "antagonised the
  effect of caffeine on blood pressure"; theanine "has been found to reduce blood pressure in
  hypertensive rats". No trial found of theanine with antihypertensive drugs, and none showing a
  fixed 5-8 mmHg fall.
- Sibling sedatives cites 18296328 and 35378276, which contradict its copy: 18296328 says L-theanine
  "relaxes the mind without inducing drowsiness"; 35378276 found no anxiolytic effect over placebo.
  Mechanism, headline, alert and note rewritten; "increases GABA, glycine, and serotonin" and "CNS
  depressant effects" had no source. Severity (caution) unchanged; reported as a likely over-warning.

## RULE_IQM_GUARANA — re-sourced (sedatives; alert copy inverted)

- Ghosts for sedatives: **PMID 15961987** ("Short-term metabolic and hemodynamic effects of ephedra and
  guarana combinations") and **PMID 21676849** ("Hypertensive Urgency Associated With Xenadrine EFX
  Use"). Both are cardiovascular effects of multi-ingredient weight-loss products; neither mentions
  sedatives. (They stay on the hypertension/heart sub-rules, where they fit.)
- The sub-rule's mechanism (stimulant opposes sedatives) contradicted its own alert copy: headline
  "May add to sedative drowsiness", body "Guarana has mild sedative effects", note "Guarana has
  sedative activity".
- **PMID 23981847** (Schimpl, J Ethnopharmacol 2013): guarana "is valued mainly for its stimulant
  property because of its high content of caffeine, which can be up to 6% in the seeds".
- **PMID 11125871** (Mattila, Int J Clin Pharmacol Ther 2000; n = 108 parallel + 6 crossover):
  "sedative effects of Mid 12 mg were only moderately antagonized by Caf 250 mg but not by Caf 125
  mg"; "the effects of zolpidem ... were not antagonized by Caf"; "Caf 300 mg increased plasma Mid at
  45 min". The old "rebound stimulation that disrupts sleep architecture" had no source; removed.

## RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS — re-sourced (anticholinergics)

- Ghost: **PMID 19370686** = "Huperzine A for vascular dementia" (Cochrane 2009): one 14-patient trial,
  no MMSE benefit; nothing on acetylcholinesterase pharmacology or anticholinergic drugs.
- **PMID 25191267** (Qian & Ke, Front Aging Neurosci 2014): "Huperzine A (HupA) is a natural inhibitor
  of acetylcholinesterase (AChE) ... a licensed anti-AD drug in China and is available as a
  nutraceutical in the US."
- **ARICEPT (donepezil) prescribing information**, DailyMed setid 98e451e1-e4d7-4439-a675-c5457ba20975,
  revised 12/2021, 7.1 Use with Anticholinergics: "Because of their mechanism of action, cholinesterase
  inhibitors have the potential to interfere with the activity of anticholinergic medications."
  Class-level statement; no huperzine-specific interaction study found.
- Removed as unsourced: the combination "can result in cholinergic toxidrome (bronchospasm,
  bradycardia, excessive secretions, miosis)".
