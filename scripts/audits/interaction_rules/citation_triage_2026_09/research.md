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

## RULE_IQM_RHODIOLA_IMMUNE_BP — re-sourced (sedatives)

- Ghost for sedatives: **PMID 26613955** = "Effect of commercial Rhodiola rosea on CYP enzyme activity in
  humans" (Eur J Clin Pharmacol 2016): 21% lower CYP2C9 activity; "clinically relevant during
  treatment with CYP2C9 substrates with a narrow therapeutic index, such as phenytoin and warfarin".
  Nothing on sedatives. (It stays on immunosuppressants, where it passed.)
- The sub-rule's "adaptogenic/stimulant profile may interact unpredictably with CNS sedatives.
  Bidirectional modulation (stimulant at low dose, sedating at high dose) is reported in the
  literature" had no source; its alert said "Rhodiola has mild sedative effects".
- **EU herbal monograph, Rhodiola rosea L., rhizoma et radix, Rev.1** — EMA/HMPC/24177/2023, 20 March
  2024. `https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-rhodiola-rosea-l-rhizoma-et-radix-revision-1_en.pdf`
  4.5: "No clinically relevant interactions have been observed." 4.8: headache; nausea, abdominal
  pain, diarrhoea; skin rash, itching. No sedation or drowsiness. 4.6: pregnancy/lactation "not
  recommended" in the absence of sufficient data.
- No study of rhodiola with sedative drugs found. evidence_level probable → theoretical. Reported to
  Sean: this sub-rule has no supporting evidence and is a candidate for retirement (deletion is his).

## RULE_IQM_SAME — re-sourced (maois)

- Ghost: **PMID 38423354** = "Efficacy and acceptability of S-adenosyl-L-methionine (SAMe) for depressed
  patients: A systematic review and meta-analysis" (2024). Efficacy only; nothing on MAOIs, serotonin
  or interactions. Sole source of an avoid / "established" sub-rule.
- **NCCIH SAMe: In Depth** (https://www.nccih.nih.gov/health/sadenosyllmethionine-same-in-depth): "It's
  also possible that SAMe might interact with drugs and dietary supplements that increase levels of
  serotonin ... such as antidepressants, L-tryptophan, and St. John's wort"; SAMe "may worsen
  symptoms of mania" in bipolar disorder.
- **PMID 7854515** (Bodner, Neurology 1995): serotonin syndrome "occurs following the use of
  serotomimetic agents (... S-adenosylmethionine) alone or in combination with monoamine oxidase
  inhibitors".
- **PMID 8434674** (Iruela, Am J Psychiatry 1993; letter, no abstract; MeSH clomipramine, drug
  interactions, s-adenosylmethionine, serotonin): "Toxic interaction of S-adenosylmethionine and
  clomipramine".
- No study of SAMe with an MAOI found. evidence_level established → limited.

## RULE_IQM_CHINESE_SKULLCAP_LIVER — re-sourced (pregnancy, pregnancy_lactation)

- Ghost: **PMID 31236960** = "Scutellaria baicalensis Georgi. (Lamiaceae): a review of its traditional
  uses, botany, phytochemistry, pharmacology and toxicology" (J Pharm Pharmacol 2019; not in PMC).
  Abstract has no pregnancy, reproductive or teratogenicity content. Cited for "Animal data suggest
  possible teratogenic risk at high doses".
- The only animal reproductive data found contradict that claim:
  - **PMID 26303163** (Yimam, Birth Defects Res B 2015, Part I): UP446, "a standardized bioflavonoid
    composition from the roots of Scutellaria baicalensis and the heartwoods of Acacia catechu", 250–
    1000 mg/kg/day orally during organogenesis in rabbits and rats; "no statistically significant
    differences in implantation, congenital malformation, embryo-fetal mortalities"; NOAEL > 1000 mg/kg.
  - **PMID 26033919** (Part II, rats): "No treatment-related prenatal or postnatal in-life or necropsy
    abnormalities were observed"; NOAEL > 1000 mg/kg.
- No human pregnancy safety study found. The CYP1A2/CYP2C9 sentence in the pregnancy mechanism had no
  source and no pregnancy relevance; removed. Severity (avoid) / category unchanged; avoidance is
  precautionary. Reported to Sean.

## RULE_INGREDIENT_GENISTEIN__THYROID — re-sourced (thyroid_medications; thyroid_disorder sources)

- **PMID 36017706** ("Peripubertal soy isoflavone consumption leads to subclinical hypothyroidism in male
  Wistar rats", 2023): soy isoflavone mixture; TSH rose, T3/T4 unchanged. Fits thyroid_disorder as a
  class (soy isoflavone) source; it does not name genistein and says nothing about levothyroxine, yet
  it was the only source for "Soy isoflavones can inhibit levothyroxine absorption".
- **PMID 30132047** (Hüser 2018, PMC6132702; see red clover above): a case report of a soy protein
  supplement decreasing levothyroxine absorption (Bell and Ovalle 2001); "the administration of 60 mg
  soy isoflavones did not affect the rate and extent of absorption of the concomitantly applied
  levothyroxine" (Persiani 2015, n = 12); "isoflavones might exhibit a negative impact on the thyroid
  hormone system in patients with thyroid dysfunction. The mechanism of the isoflavone interaction
  with levothyroxine medication is not clear".
- **PMID 9464451** (Divi 1997): genistein and daidzein inhibit TPO-catalysed reactions (IC50 ~1-10 µM)
  as alternate substrates. It names genistein; it was cited on red clover but not here.
- **SYNTHROID prescribing information**, DailyMed setid 1e11ad30-1041-4520-10b0-8f9d30d30fcc, revised
  2/2024: 7.9 "Soybean flour, cottonseed meal, walnuts, and dietary fiber may bind and decrease the
  absorption of SYNTHROID"; 2.1 "Administer SYNTHROID at least 4 hours before or after drugs known to
  interfere with SYNTHROID absorption" (basis for the sub-rule's existing 4-hour action).

## PMID 10902065 (Heck, AJHP 2000) on herbs its abstract does not name

The abstract lists the herbs it covers (angelica ... willow bark; documented: coenzyme Q10, danshen,
devil's claw, dong quai, ginseng, green tea, papain, vitamin E). Cat's claw, evening primrose oil,
saw palmetto and fish oil/omega-3 are not in it, and the full text is not open, so it cannot carry
those rules. (It stays on chamomile, devil's claw and red clover, which it names.)

### RULE_INGREDIENT_CAT_S_CLAW — re-sourced (anticoagulants)
- The mechanism said cat's claw "is documented in the Heck et al. 2000 AJHP review" — not verifiable.
- **PMID 33091497** (Kolodziejczyk-Czepas, J Ethnopharmacol 2021; in vitro/in silico): U. tomentosa
  extracts "demonstrated slight antiplatelet activity. The thrombin time was slightly prolonged";
  thrombin inhibition (IC50 5.86 µg/ml, ethanolic leaf fraction); procyanidins B2 and C1 bound
  thrombin with the highest affinity in silico.
- **NCCIH Cat's Claw** (https://www.nccih.nih.gov/health/cats-claw): "Cat's claw may slow blood clotting";
  "There are theoretical reasons to suspect that cat's claw might interact with anticoagulant,
  antiplatelet, and blood pressure drugs". evidence_level probable → theoretical.

### RULE_INGREDIENT_EVENING_PRIMROSE_OIL — re-sourced (anticoagulants)
- The mechanism said EPO is "Listed among herbs with potential warfarin potentiation in clinical
  pharmacology references" (the Heck citation) and attributed the effect to "GLA-derived PGE1".
- **PMID 19783511** (Riaz, Pak J Pharm Sci 2009; rabbits, 30-60 days): "significant increase in all
  assays except Fibrinogen time"; "significantly decreased platelet count".
- **MSKCC About Herbs: Evening Primrose Oil**: "In vitro, evening primrose oil ... inhibits platelet
  aggregation"; "Antiplatelet and anticoagulant effects are likely related to decreased thromboxane
  B2 synthesis"; "Anticoagulants/Antiplatelets: May have additive effects and increase bleeding
  risk"; "In a small study of humans on several months of supplementation with GLA from evening
  primrose oil, a significant increase in bleeding time was observed in 9 of 12 patients"; "Evening
  primrose oil is about 10% GLA".
- Not changed: the sub-rule's min_effective_dose rationale attributes "~300 mg GLA ~ 3 g oil" to PMID
  19783511 (a rabbit study dosed in µl/kg); that figure matches the MSKCC human data, not 19783511.
  Dose-floor source attribution reported to Sean.

### RULE_INGREDIENT_OMEGA_3 — re-sourced (nsaids)
- 10902065 was the only source; it is a warfarin review and says nothing on NSAIDs or fish oil. The
  mechanism said the combination "may modestly increase GI bleeding risk".
- **PMID 18841286** (Larson, Thromb Haemost 2008; n = 10): prescription omega-3 "alone did not inhibit
  platelet aggregation, but did (with two agonists) when combined with aspirin. Since previous
  studies have not reported a clinically significant risk for bleeding in subjects on combined
  therapy, P-OM3 may safely enhance the anti-platelet effect of aspirin."
- **PMID 26280541** (Roberto, Basic Clin Pharmacol Toxicol 2016; nested case-control): low-dose aspirin
  plus omega-3 "does not affect the UGIC risk" (current users OR 0.66, 95% CI 0.44-1.00).
- **PMID 17368277** (Bays, Am J Cardiol 2007): "clinical trial evidence has not supported increased
  bleeding with omega-3 fatty acid intake, even when combined with other agents that might also
  increase bleeding (such as aspirin and warfarin)".
- No study with non-aspirin NSAIDs found. evidence_level probable → theoretical; headline and alert no
  longer say omega-3 adds to NSAID bleeding risk.

## RULE_IQM_STINGING_NETTLE_DIABETES — re-sourced (diabetes, three hypoglycemic drug classes)

- **PMID 35800714** ("Nutritional and pharmacological importance of stinging nettle", Heliyon 2022;
  PMC9253158) — abstract has no glucose content; full text: aqueous leaf extract anti-diabetic in
  diabetic mice, "decreased glucose absorption in their intestine", "nettle stimulates insulin
  secretion". No alpha-glucosidase or human data. Kept only as the min_effective_dose source.
- **PMID 24273930** (Kianbakht, Clin Lab 2013; RCT, 46 vs 46, advanced T2DM needing insulin): nettle leaf
  extract 500 mg every 8 hours for 3 months "combined with the conventional oral anti-hyperglycemic
  drugs" lowered fasting glucose, 2-h postprandial glucose and HbA1c vs placebo; background: nettle
  leaves "have insulin secretagogue, PPARgamma agonistic, and alpha-glucosidase inhibitory effects".
- **PMID 31802554** (Ziaei, Phytother Res 2020; SR/MA, 8 RCTs, n = 401): fasting blood sugar WMD
  -18.01 mg/dl (95% CI -30.04 to -5.97); insulin, HOMA-IR and HbA1c not significantly reduced.

## RULE_IQM_VANADIUM_DIABETES — re-sourced (diabetes, three hypoglycemic drug classes)

- **PMID 37958659** ("Vanadium Compounds with Antidiabetic Potential", IJMS 2023; PMC10650557): review of
  vanadium compounds; the abstract never names vanadyl sulfate (verifier subject miss). Full text:
  vanadium "seems to avoid the risk of hypoglycemia" alone, "vanadyl compounds can enhance the
  effectiveness of administered insulin", and human vanadyl sulfate trials (30-150 mg/day) were small
  and short with "ambiguous" relevance. It does not carry "Clinical studies showed FBG and HbA1c
  reductions at 150 mg/day" or "inhibits PTP-1B" for vanadyl sulfate. Replaced by the trials:
- **PMID 11238540** (Cusi, JCEM 2001; n = 11 T2DM): vanadyl sulfate 150 mg/day for 6 weeks; "fasting plasma
  glucose (FPG) decreased from 194 +/- 16 to 155 +/- 15 mg/dL, hemoglobin A(1c) decreased from 8.1 +/-
  0.4 to 7.6 +/- 0.4%"; endogenous glucose production reduced ~20%; "liver, rather than muscle, is the
  primary target".
- **PMID 10726921** (Goldfine, Metabolism 2000; n = 16 T2DM, 75/150/300 mg/day for 6 weeks): "Fasting
  glucose and hemoglobin A1c (HbA1c) decreased significantly in the 150- and 300-mg VOSO4 groups";
  "The 150- and 300-mg vanadyl doses caused some gastrointestinal intolerance"; "it does not
  dramatically improve insulin sensitivity or glycemic control".

## RULE_IQM_HORNY_GOAT_WEED_HEART — re-sourced (heart_disease, antihypertensives)

- **PMID 15546831** (Partin, Psychosomatics 2004; letter, no abstract): "Tachyarrhythmia and hypomania with
  horny goat weed". MSKCC summarises it: a 66-year-old man with congestive heart failure hospitalised
  with new-onset symptomatic arrhythmia. Fits heart_disease (the old heart mechanism never mentioned
  it); says nothing about hypotension, so it is removed from antihypertensives.
- **PMID 18778098** (Dell'Agli, J Nat Prod 2008): icariin inhibits PDE5A1 with "IC50 5.9 microM"; the
  synthetic derivative 3,7-bis(2-hydroxyethyl)icaritin matched sildenafil ("IC50 75 vs 74 nM").
- **MSKCC About Herbs: Epimedium**: "Icariin can also exhibit a mild phosphodiesterase-5 inhibition
  effect"; "Do Not Take if ... You have heart disease: Epimedium caused rapid irregular heartbeat and
  excitability in a patient with heart disease"; estrogen-like activity is attributed "to icariin
  derivatives icaritin and desmethylicaritin, rather than icariin itself".
- **VIAGRA (sildenafil) prescribing information**, DailyMed setid 0b0be196-0c62-461c-94f4-9a35339b4501:
  4.1 "VIAGRA was shown to potentiate the hypotensive effects of nitrates, and its administration to
  patients who are using nitric oxide donors ... is therefore contraindicated"; 7.2 Alpha-blockers.
  Class reference for the PDE5 extrapolation; no icariin-nitrate case found.
- Removed as unsourced: PDE4 inhibition, "weak estrogen receptor agonist activity" of icariin,
  "producing additive hypotension".

## RULE_IQM_BLACK_SEED_OIL_DIABETES — re-sourced (all nine sub-rules)

- **PMID 34073784** ("Black Cumin (Nigella sativa L.): A Comprehensive Review ...", Nutrients 2021;
  PMC8225153) was the only source for all nine sub-rules. Its abstract names no drug, pregnancy or
  blood-pressure effect. Full text (read 2026-09-25):
  - herb-drug table: "TQ Glibenclamide (GBC) Rat PO 10 mg/kg Plasma concentration of GBC increased by
    13.4% (Single dose) and 21.8% (multiple doses) with TQ Synergistic effect on glucose level"; TQ
    "Moderate inhibitors of the CYP2C9" (fluorescence assay).
  - toxicity: pregnant rats given TQ i.p. on gestation days 11 and 14 — 15 mg/kg "no adverse effect",
    35 mg/kg "maternal and embryonic toxicities", 50 mg/kg "complete fetal resorption"; intravaginal
    black cumin oil in pregnant rats "did not cause any adverse effect".
  - hypertension: one RCT in elderly hypertensives "slight but insignificant reduction"; another
    positive; angiotensin II rat model positive.
  - Not in the review: "PPAR-gamma activation" as the glucose mechanism, "fasting glucose reductions of
    15-20 mg/dL", "voltage-gated calcium channels ... eNOS", "Reductions of 5-10 mmHg systolic",
    "inhibits thromboxane B2 synthesis and platelet aggregation", "uterine-effect activity". Removed.
  It stays (reviewed) on diabetes, the three hypoglycemic classes (glibenclamide), anticoagulants
  (CYP2C9) and pregnancy / pregnancy_lactation (rat data).
- **PMID 40210172** (Karimi, Complement Ther Med 2025; MA of 16 RCTs in T2DM): FBG "MD: -21.43 mg/dL";
  HbA1c "MD: -0.44"; no significant effect on fasting insulin or 2-h postprandial glucose.
- **PMID 27512971** (Sahebkar, J Hypertens 2016; MA of 11 RCTs, n = 860; already the dose-floor source):
  SBP "-3.26 (-5.10, -1.42)" and DBP "-2.80 (-4.28, -1.32)" mmHg vs control over ~8.3 weeks; powder
  more effective than oil.
- anticoagulant alert said "Black seed oil has mild antiplatelet or anticoagulant activity" with no
  source; rewritten to the CYP2C9 finding.

## RULE_IQM_QUERCETIN_THYROID — re-sourced (thyroid_disorder, anticoagulants)

- **PMID 29127724** (Andres, "Safety Aspects of the Use of Quercetin as a Dietary Supplement", Mol Nutr
  Food Res 2018; not in PMC) was the only source for both sub-rules. Abstract: rare mild adverse
  effects; possible nephrotoxicity in predamaged kidney; "interactions between quercetin and certain
  drugs leading to altered drug bioavailability". Nothing on thyroid, TPO, warfarin, CYP2C9 or
  platelets; full text not readable.
- Thyroid:
  - **PMID 8924586** (Divi & Doerge, Chem Res Toxicol 1996): 13 flavonoids, "IC50 values ranging from 0.6
    to 41 microM"; "Inhibition by the more potent compounds, fisetin, kaempferol, naringenin, and
    quercetin ... was consistent with mechanism-based inactivation of TPO".
  - **PMID 24447974** (Giuliani, Food Chem Toxicol 2014): quercetin decreases TSH receptor, TPO and
    thyroglobulin gene expression; rat radioiodine uptake "significantly decreased after 14 days";
    "caution is needed in its supplemental and therapeutic use".
  - **PMID 39456456** (Giuliani, Antioxidants 2024 review): thyroid disruptor in vitro and in rodents;
    inhibits 5'-deiodinase type 1; "caution is required in the use of high doses".
  - No human thyroid study found. The rule's ">500 mg/day" is the authored dose threshold (its
    dose_thresholds note says "per authored action"), not an evidence figure; the mechanism says so.
- Anticoagulants:
  - **PMID 36239716** (Ahmad, Curr Drug Saf 2023; rats): quercetin pretreatment for 14 days raised
    warfarin "Cmax ... by 30.43%, AUC0-∞ by 62.94%" and cut clearance 41.35%; background: quercetin
    inhibits "CYP3A4, CYP2C8, CYP2C9, CYP1A2, and Pglycoprotein".
  - **PMID 15613018** (Hubbard, J Thromb Haemost 2004; humans): 150 or 300 mg quercetin-4'-O-glucoside;
    "Platelet aggregation was inhibited 30 and 120 min after ingestion of both doses" (already the
    min_effective_dose source).
  - No human warfarin interaction study found.

## RULE_IQM_5HTP_SEROTONIN — re-sourced (pregnancy, pregnancy_lactation, maois)

- Ghost (not a PMID, so the verifier cannot see it): **NBK548375** = LiverTox "Muscle Relaxants"
  (NCBI Books esummary; page read in browser: no 5-HTP, serotonin or pregnancy content). It was one
  of two sources on both pregnancy sub-rules. All 16 NCBI Bookshelf IDs in the rules file were
  resolved; this is the only mismatch (NBK592340 = ATSDR Toxicological Profile for Vanadium, Health
  Effects; the rest are the named LactMed/LiverTox/StatPearls chapters).
- **PMID 16023217** (Turner, Pharmacol Ther 2006): 5-HTP "the serotonin precursor"; safety review of
  "eosinophilia myalgia syndrome (EMS) and serotonin syndrome". No pregnancy content (kept as the
  pharmacology source; reviewed entry for the topic heuristic).
- **Health Canada NHPID monograph: 5-HTP** (https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=5htp&lang=eng),
  dated August 28, 2024: "All uses (excluding weight management) Ask a health care practitioner ...
  before use if you are pregnant or breastfeeding"; "Weight management Do not use if you are pregnant";
  "Do not use if you are taking antidepressants".
- **MSKCC About Herbs: 5-HTP** (https://www.mskcc.org/cancer-care/integrative-medicine/herbs/5-htp-01;
  already the serotonergic_medications source): "Do Not Take if ... You are taking antidepressants or
  anxiolytics (including tricyclics, MAOIs, and SSRIs)"; "a case report of mania following use of an
  MAOI with 5-HTP"; "linezolid (Zyvox, an antibiotic MAOI): There is a case report of an interaction
  with 5-HTP causing serotonin syndrome". Added to maois beside the class review **PMID 31523132**
  (serotonin syndrome: MAOI plus serotonergic drugs "especially dangerous").

## RULE_INGREDIENT_BORAGE_SEED_OIL__SEIZURE — re-sourced (seizure_disorder)

- **PMID 17764919** (Puri, "The safety of evening primrose oil in epilepsy", 2007) was the only source. It
  is about evening primrose oil, not borage, and concludes the old GLA-seizure association "is shown
  to be spurious" — yet the rule said the concern "applies similarly to borage" and advised avoiding
  high doses. It stays as the GLA-class counterpoint (reviewed entry: subject heuristic).
- **PMID 21387119** (Al-Khamees, J Med Toxicol 2011): "We report a case of status epilepticus in a patient
  who consumed borage oil for one week"; borage oil is "an abundant source of gamma-linolenic acid".
- **MSKCC About Herbs: Borage**: case "Continuous seizure activity: In an otherwise previously healthy
  41-year-old woman, with short-term use (1 week) of borage oil"; "Borage oil products should be
  certified free of toxic compounds called unsaturated pyrrolizidine alkaloids (UPAs)"; UPAs cause
  "toxic liver effects". Removed as unsourced: "GLA, ~24%" and PAs "pose additional neurotoxic risk".
  evidence_level theoretical → limited (one human case).

## RULE_BANNED_RED_YEAST_RICE_STATINS — source added (high_cholesterol); reviewed (statins)

- high_cholesterol said "EFSA 2025 concluded no safe daily intake level for monacolins can be
  established" but cited the 2018 EFSA ANS opinion, **PMID 32626016** ("monacolin K in lactone form is
  identical to lovastatin"; adverse effects "at intake levels as low as 3 mg/day"; "unable to
  identify a dietary intake of monacolins from RYR that does not give rise to concerns"). 32626016 is
  on topic (its word is "hypercholesterolaemia", which the verifier's "cholester" stem misses) and
  stays as a reviewed entry.
- **PMID 40027377** (EFSA NDA Panel, EFSA J 2025): "reiterates the concerns of the ANS Panel ... that
  exposure to monacolin K from RYR at intake levels as low as 3 mg/day could lead to severe adverse
  effects on the musculoskeletal system, including rhabdomyolysis, and on the liver"; data "do not
  allow establishing the safety of monacolins in RYR supplements below 3 mg/day or to identify a daily
  intake ... that does not raise safety concerns". Added as the source of the "EFSA 2025" sentence.
- statins: **PMID 12622602** (Arch Intern Med 2003) — statin myopathy "is dose related and is increased
  when statins are used in combination with agents that share common metabolic pathways". Class-level
  support for stacking a lovastatin-equivalent on a statin (reviewed entry).

## RULE_IQM_CHASTEBERRY_PREGNANCY — mechanism trimmed (pregnancy); reviewed (pregnancy, pregnancy_lactation)

- **PMID 23136064** (van Die, Planta Med 2013; systematic review of RCTs): in latent hyperprolactinaemia
  Vitex reduced "TRH-stimulated prolactin secretion, normalising a shortened luteal phase, increasing
  mid-luteal progesterone and 17β-oestradiol levels"; comparable to bromocriptine. No pregnancy data
  (topic heuristic miss); supports the hormonal mechanism.
- **NCCIH Chasteberry** (https://www.nccih.nih.gov/health/chasteberry): "Some preclinical evidence states
  that the use of chasteberry during pregnancy or while breastfeeding may be unsafe"; "chasteberry
  may be unsafe during pregnancy".
- The pregnancy mechanism named "pituitary dopamine D2 receptors" and "modulate LH/FSH secretion";
  neither cited source says so (D2 activity is shown in vitro elsewhere, PMID 39519010, not cited
  here). Trimmed to what the two sources state.

## RULE_IQM_CHONDROITIN — mechanism trimmed (bleeding_disorders); dose-floor citation corrected

- **PMID 14986566** (Rozenfeld, AJHP 2004; letter, no abstract, not open): "Possible augmentation of
  warfarin effect by glucosamine-chondroitin"; MeSH chondroitin sulfates, glucosamine, warfarin,
  international normalized ratio, drug synergism. Kept (reviewed entry: no abstract, topic heuristic).
- **PMID 18363538** (Knudsen & Sokol, Pharmacotherapy 2008): warfarin patient stable on glucosamine 500 mg
  + chondroitin 400 mg twice/day; after increasing to glucosamine 1500 mg and chondroitin 1200 mg twice/day
  INR rose from 2.3 to 3.9 (then 4.7), normalised after stopping; FDA MedWatch: 20 reports of altered
  coagulation with glucosamine or glucosamine-chondroitin plus warfarin.
- The bleeding_disorders mechanism said "In vitro data suggest weak anticoagulant activity at high
  concentrations" with no source for supplement chondroitin; trimmed. The min_effective_dose credited
  the "1200 mg BID" escalation to 14986566; that figure is in 18363538 (source corrected, value 1200 mg
  unchanged).
- Sibling not changed (uncertain): the anticoagulants sub-rule says "One case report documented INR
  increase from 2.6 to 4.1"; that figure matches neither readable source (18363538: 2.3 -> 3.9 -> 4.7)
  and 14986566 is unreadable. Reported to Sean.

## RULE_IQM_GREEN_TEA_HYPERTENSION — source added (hypertension, antihypertensives)

- **PMID 25312732** (Curr Pharm Des 2015 review, "Overview of green tea interaction with cardiovascular
  drugs"): human interaction data "limited so far to warfarin, simvastatin and nadolol"; green tea "may
  interfere with the oral bioavailability or activity of cardiovascular drugs". On topic (nadolol is
  a beta-blocker antihypertensive; the verifier's stems miss it) but the abstract does not state the
  OATP mechanism the rule gives. Kept (reviewed entry).
- **PMID 24419562** (Misaka, Clin Pharmacol Ther 2014; RCT, n = 10): green tea 700 ml/day for 14 days
  "markedly decreased the maximum plasma concentration (C(max)) and area under the plasma
  concentration-time curve (AUC(0-48)) of nadolol by 85.3% and 85.0%"; "The effects of nadolol on
  systolic blood pressure were significantly reduced by green tea"; green tea inhibited "OATP1A2-
  mediated nadolol uptake". Added to both sub-rules; mechanism no longer attributes the effect to EGCG
  specifically (the study used brewed green tea).
