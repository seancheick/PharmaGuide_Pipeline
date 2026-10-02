# Q57b: harm claims re-sourced in banned_recalled_ingredients.json (2026-10-02)

Q57 removed 127 DOI citations that pointed at unrelated papers or nothing. For the 57 banned_recalled entries left without a cited source for their harm claims, three research agents proposed sources (discovery only); Claude read every cited abstract, LiverTox record, EFSA opinion, FDA label, NCCIH page, MMWR full text (PMC13065088), ClinicalTrials.gov posted results, the 1976 Red No. 2 Federal Register notice and PubChem's IARC annotations before using it. A claim stays only where a read source supports it; otherwise it is weakened to what the source does say, or removed.

**Scope.** `reason` (shipped as the blocked-page detail) and `references_structured` only. `safety_warning` and `safety_warning_one_liner` are Sean-owned and unchanged; where they repeat an unsupported claim, the entry carries a flag below.

**Evidence grade** (set from study type): A systematic review or meta-analysis; B randomized trial, registry, surveillance, outbreak report, regulatory or authoritative monograph (LiverTox, EFSA, FDA label, MMWR); C case series, cross-sectional, narrative review, product analysis; D case report, animal or in-vitro study.

**No harm claims to source (unchanged):** NOOTROPIC_ANIRACETAM, NOOTROPIC_MODAFINIL, NOOTROPIC_PIRACETAM.

## ADD_HORDENINE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| concentrated in supplements at pharmacological doses. | concentrated in supplements. |
| Frequently combined with other stimulants in weight-loss and pre-workout products, amplifying cardiovascular risk. | It is found in sports supplements, sometimes with other stimulants. In animals, high or intravenous doses raise blood pressure and heart rate; no human cardiovascular data were found. |

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [[Pharmacological effects of hordenine]](https://pubmed.ncbi.nlm.nih.gov/8582256/) · Indirect adrenergic agent; in rats and dogs, raises systolic/diastolic BP with positive inotropy; effects brief and only at high doses.
- **D** · mechanism_of_harm · [Hordenine: pharmacology, pharmacokinetics and behavioural effects in the horse](https://pubmed.ncbi.nlm.nih.gov/2269269/) · IV hordenine roughly doubled heart rate and caused respiratory distress and sweating; effects transient (<30 min).
- **C** · clinical_outcomes · [Detection and quantification of phenethylamines in sports dietary supplements by NMR approach](https://pubmed.ncbi.nlm.nih.gov/29413984/) · Hordenine, synephrine, BMPEA, deterenol and others identified in US sports supplements by NMR.
- **Flag for Sean:** safety_warning says 'drug-strength doses' and 'blood-pressure elevation and cardiovascular strain'; evidence is animal-only (also Q58 Cat 3).

## ADD_RED3 (high_risk)
Claims unchanged; they are supported as written.

Sources added (grade · what it supports · finding):
- **B** · mechanism_of_harm · [Scientific Opinion on the re-evaluation of Erythrosine (E 127) as a food additive (EFSA Journal 2011;9(1):1854)](https://doi.org/10.2903/j.efsa.2011.1854) · Rat thyroid tumours are secondary to thyroid-function effects, not genotoxicity, and of limited human relevance; ADI 0.1 mg/kg bw/day kept.
- Thyroid tumours in rats supported; EFSA calls them secondary to thyroid-function effects and of limited human relevance.

## ADULTERANT_RIMONABANT (banned)
Claims unchanged; they are supported as written.

Sources added (grade · what it supports · finding):
- **A** · clinical_outcomes · [Efficacy and safety of the weight-loss drug rimonabant: a meta-analysis of randomised trials](https://pubmed.ncbi.nlm.nih.gov/18022033/) · 2.5x more discontinuations for depressive mood disorders and 3x for anxiety; cites FDA finding of increased suicide risk.
- **A** · clinical_outcomes · [Rimonabant for overweight or obesity](https://pubmed.ncbi.nlm.nih.gov/17054276/) · 20 mg caused significantly more general and serious adverse effects, especially nervous-system, psychiatric and GI; ~40% attrition at one year.
- **C** · clinical_outcomes · [Detection of hazardous weight-loss substances in adulterated slimming formulations using ultra-high-pressure liquid chromatography with diode-array detection](https://pubmed.ncbi.nlm.nih.gov/22150438/) · Hazardous substances detected included rimonabant, sibutramine, clenbuterol, phenolphthalein.
- **C** · clinical_outcomes · [Active pharmaceutical ingredients detected in herbal food supplements for weight loss sampled on the Dutch market](https://pubmed.ncbi.nlm.nih.gov/25247833/) · 24 samples contained undeclared APIs including rimonabant, sibutramine and phenolphthalein.

## BANNED_14_BUTANEDIOL (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| — with a narrow therapeutic window made worse because conversion speed varies by individual | _removed_ |

Sources added (grade · what it supports · finding):
- **B** · mechanism_of_harm · [Butanediol Conversion to Gamma-Hydroxybutyrate Markedly Reduced by the Alcohol Dehydrogenase Blocker Fomepizole](https://pubmed.ncbi.nlm.nih.gov/30450642/) · Fomepizole raised BDO levels, confirming alcohol dehydrogenase as the primary BDO-to-GHB pathway in humans.
- **C** · clinical_outcomes · [Adverse events, including death, associated with the use of 1,4-butanediol](https://pubmed.ncbi.nlm.nih.gov/11150358/) · Vomiting, incontinence, agitation, labile consciousness, respiratory depression; 2 deaths with no other intoxicants (5.4-20 g); withdrawal in one patient.
- **C** · clinical_outcomes · [Fatal intoxication with 1,4-butanediol: Case report and comprehensive review of the literature](https://pubmed.ncbi.nlm.nih.gov/37277927/) · Lethal GHB intoxication after 1,4-BD ingestion, with no other substances at relevant levels; fatal cases are rarely reported.
- **C** · clinical_outcomes · [Consequences of 1,4-Butanediol Misuse: A Review](https://pubmed.ncbi.nlm.nih.gov/38076667/) · High addiction potential and potentially severe withdrawal, including delirium.

## BANNED_7_HYDROXYMITRAGYNINE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| with full mu-opioid receptor agonist potency estimated at 13 times greater than morphine by weight. It is responsible for most of kratom's opioid effects. | that acts on mu-opioid receptors (a partial agonist in human-receptor cell studies) and was more potent than morphine in animal and isolated-tissue studies. In mice it accounts for most of mitragynine's opioid pain-relieving effect, and repeated dosing causes tolerance and withdrawal like morphine. |
| Products containing isolated or concentrated 7-HMG carry full opioid overdose risk. | Poison-center data link 7-OH and related high-potency kratom alkaloids to serious breathing and nervous-system effects, especially in children. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [Synthetic and Receptor Signaling Explorations of the Mitragyna Alkaloids: Mitragynine as an Atypical Molecular Framework for Opioid Receptor Modulators](https://pubmed.ncbi.nlm.nih.gov/27192616/) · Both are PARTIAL agonists at the human mu receptor, G-protein biased (no beta-arrestin recruitment). Contradicts 'full agonist'.
- **D** · mechanism_of_harm · [Studies on the synthesis and opioid agonistic activities of mitragynine-related indole alkaloids: discovery of opioid agonists structurally different from other opioid ligands](https://pubmed.ncbi.nlm.nih.gov/11960505/) · 7-OH was an opioid agonist more potent than morphine in guinea-pig ileum; the abstract gives no 13x figure.
- **D** · mechanism_of_harm · [Antinociceptive effect of 7-hydroxymitragynine in mice: Discovery of an orally active opioid analgesic from the Thai medicinal herb Mitragyna speciosa](https://pubmed.ncbi.nlm.nih.gov/14969718/) · More potent than morphine in tail-flick and hot-plate tests; orally active, unlike oral morphine at 20 mg/kg.
- **D** · mechanism_of_harm · [7-Hydroxymitragynine Is an Active Metabolite of Mitragynine and a Key Mediator of Its Analgesic Effects](https://pubmed.ncbi.nlm.nih.gov/31263758/) · Brain 7-OH levels explain most or all of mitragynine's opioid-receptor-mediated analgesia in mice.
- **D** · mechanism_of_harm · [Antinociception, tolerance and withdrawal symptoms induced by 7-hydroxymitragynine, an alkaloid from the Thai medicinal herb Mitragyna speciosa](https://pubmed.ncbi.nlm.nih.gov/16169018/) · Tolerance, cross-tolerance with morphine, and naloxone-precipitated withdrawal comparable to morphine.
- **C** · clinical_outcomes · [Buprenorphine for the Management of 7-Hydroxymitragynine (7-OH) Use: A Retrospective Case Series](https://pubmed.ncbi.nlm.nih.gov/42225057/) · Describes problematic 7-OH use managed with buprenorphine, a human opioid-use-disorder-like pattern.
- **D** · clinical_outcomes · [Risk of respiratory and neurologic effects in children ingesting kratom and related alkaloids](https://pubmed.ncbi.nlm.nih.gov/42715782/) · 7-OH/MP exposures had higher odds of serious respiratory (OR 2.5) and neurologic (OR 2.6) effects and more naloxone use.
- **Flag for Sean:** safety_warning says 'estimated around 13 times morphine potency'; no source states 13x (only 'more potent than morphine' in animals).

## BANNED_ADD_PHTHALATES (watchlist)
| Before (removed or reworded) | Final claim |
|---|---|
| Packaging contaminants that leach from plastic bottles and containers into supplements. Powerful endocrine disruptors linked to reproductive harm, developmental issues, and cancer (DEHP classified IARC Group 2B, possibly carcinogenic, Monograph Vol 101, 2013). 2024-2025 research continues to find widespread contamination in supplements packaged in plastic. Choose glass packaging when possible. Not intentionally added but common contaminant. | Phthalates can be in supplements as coating ingredients (diethyl or dibutyl phthalate in some extended-release or enteric coatings) or as contaminants; DEHP and DBP have been detected in some prenatal vitamins. Some phthalates, including DEHP and DBP, are reproductive and developmental toxicants in animal studies, and IARC classifies DEHP as possibly carcinogenic to humans (Group 2B). Phthalate polymer coatings (HPMCP, CAP, PVAP) are different substances with no known toxicity. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm, clinical_outcomes · [Identification of phthalates in medications and dietary supplement formulations in the United States and Canada](https://pubmed.ncbi.nlm.nih.gov/22169271/) · DEHP and DBP are reproductive/developmental toxicants in animals; 3 OTC/supplement products listed DBP, 64 DEP; phthalate polymers have no known toxicity.
- **C** · clinical_outcomes · [Heavy metals and phthalate contamination in prenatal vitamins and folic acid supplements](https://pubmed.ncbi.nlm.nih.gov/40020868/) · Cadmium above LOQ in 73% of commercial prenatal vitamins. Funded by Clean Label Project; authors report paid expert testimony (COI).
- **C** · clinical_outcomes · [Use of dietary supplements in relation to urinary phthalate metabolite concentrations: Results from the National Health and Nutrition Examination Survey](https://pubmed.ncbi.nlm.nih.gov/30826666/) · Multivitamin users had 11% higher MEP; no other significant associations. DEP/DBP can be coating components.
- DEHP IARC Group 2B confirmed via PubChem (CID 8343).
- **Flag for Sean:** safety_warning says phthalates are packaging contaminants and 'presence reflects contamination rather than an added ingredient'; DEP/DBP are declared coating excipients in some products. Matching: check that 'phthalate' does not match HPMCP/CAP/PVAP.

## BANNED_ADD_SYNTHETIC_FOOD_ACIDS (watchlist)
| Before (removed or reworded) | Final claim |
|---|---|
| Synthetic acids may have different effects than natural food acids. Can contribute to dental erosion and digestive issues. | No evidence shows that synthetic food acids act differently from the same acids from natural sources. Like other acids, frequent exposure can contribute to dental erosion. |

Sources added (grade · what it supports · finding):
- **B** · mechanism_of_harm · [Chapter 9: Acidic Beverages and Foods Associated with Dental Erosion and Erosive Tooth Wear](https://pubmed.ncbi.nlm.nih.gov/31940633/) · Erosive potential depends on pH, titratable acidity, buffer capacity and Ca/phosphate; soft drinks, fruit juices and acidic sweets are associated with erosion.
- **Flag for Sean:** No defensible harm basis found for this watchlist entry; safety_warning cites 'labeling and tolerability concerns'. Keep or retire is Sean's decision.

## BANNED_BMPEA (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| BMPEA has stimulant activity; it raises blood pressure and heart rate and has structural similarity to amphetamines. | It is a positional isomer of amphetamine. In rats it raised blood pressure like amphetamine but did not substantially change heart rate; it has never been studied in humans. |
| (Pawar et al. 2013) | (Pawar et al. 2014) |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Determination of selected biogenic amines in Acacia rigidula plant materials and dietary supplements using LC-MS/MS methods](https://pubmed.ncbi.nlm.nih.gov/24176750/) · BMPEA, described as a non-natural compound, was found in 9 of 21 supplements labelled A. rigidula; it can be misidentified as amphetamine.
- **C** · clinical_outcomes · [An amphetamine isomer whose efficacy and safety in humans has never been studied, β-methylphenylethylamine (BMPEA), is found in multiple dietary supplements](https://pubmed.ncbi.nlm.nih.gov/25847603/) · 11/21 brands contained BMPEA; up to 93.7 mg/day at maximum servings; efficacy and safety in humans never studied.
- **D** · mechanism_of_harm · [The Supplement Adulterant β-Methylphenethylamine Increases Blood Pressure by Acting at Peripheral Norepinephrine Transporters](https://pubmed.ncbi.nlm.nih.gov/30898867/) · BMPEA raised blood pressure like amphetamine but did not substantially affect heart rate or locomotor activity in rats.
- **Flag for Sean:** safety_warning says 'Linked to cardiovascular risk'; evidence is a rat blood-pressure study only.

## BANNED_COMFREY_INTERNAL (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| causing hepatic veno-occlusive disease (Budd-Chiari syndrome), progressive liver failure, and cancer. | causing hepatic veno-occlusive disease (sinusoidal obstruction syndrome) and severe liver injury, which has been fatal in reported cases; comfrey also causes liver tumors in laboratory animals. |
| There is no safe intake level for hepatotoxic PAs. | _removed_ |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Comfrey](https://pubmed.ncbi.nlm.nih.gov/31643691/) · Comfrey contains pyrrolizidine alkaloids; taken orally it can cause sinusoidal obstruction syndrome and severe liver injury.
- **D** · clinical_outcomes · [Hepatic veno-occlusive disease associated with comfrey ingestion](https://pubmed.ncbi.nlm.nih.gov/2103401/) · 23-year-old developed veno-occlusive disease with portal hypertension and died of liver failure; association judged possible.
- **C** · mechanism_of_harm · [Metabolism, genotoxicity, and carcinogenicity of comfrey](https://pubmed.ncbi.nlm.nih.gov/21170807/) · Comfrey is hepatotoxic in livestock and humans, carcinogenic in experimental animals; PA metabolites form DHP-DNA adducts, causing mutations in liver.
- **D** · mechanism_of_harm · [Carcinogenic activity of Symphytum officinale](https://pubmed.ncbi.nlm.nih.gov/278864/) · Hepatocellular adenomas in all comfrey-fed groups; occasional liver hemangioendothelial sarcoma.
- **C** · mechanism_of_harm · [Hepatotoxicity and tumorigenicity induced by metabolic activation of pyrrolizidine alkaloids in herbs](https://pubmed.ncbi.nlm.nih.gov/21619520/) · CYP450 activation of PAs yields reactive pyrrolic metabolites that bind proteins and DNA, causing hepatotoxicity and genotoxicity.

## BANNED_DMAA (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| It has been linked to heart attacks, strokes, deaths (including military personnel), and psychiatric events. | Case reports link DMAA-containing products to cerebral hemorrhage, heart attack, cardiac arrest and deaths, including two soldiers who collapsed during exercise; most involved multi-ingredient products. In a small trial, single 50-75 mg doses raised blood pressure. |

Sources added (grade · what it supports · finding):
- **B** · mechanism_of_harm · [Effects of 1,3-dimethylamylamine and caffeine alone or in combination on heart rate and blood pressure in healthy men and women](https://pubmed.ncbi.nlm.nih.gov/22030947/) · DMAA raised systolic and diastolic BP dose-dependently without raising heart rate; peak ~20% SBP rise with caffeine + 75 mg DMAA at 60 min.
- **D** · clinical_outcomes · [Use of recreational drug 1,3 Dimethylamylamine (DMAA) [corrected] associated with cerebral hemorrhage](https://pubmed.ncbi.nlm.nih.gov/22575212/) · Three cases of cerebral hemorrhage after DMAA use; describes DMAA as a sympathomimetic, potent pressor agent.
- **D** · clinical_outcomes · [Another bitter pill: a case of toxicity from DMAA party pills](https://pubmed.ncbi.nlm.nih.gov/21358791/) · Cerebral haemorrhage shortly after ingesting two DMAA capsules.
- **D** · clinical_outcomes · [Acute myocardial infarction associated with dietary supplements containing 1,3-dimethylamylamine and Citrus aurantium](https://pubmed.ncbi.nlm.nih.gov/24512406/) · NSTEMI with LAD thrombus; resolved with medical therapy.
- **D** · clinical_outcomes · [Cardiac arrest in a 21-year-old man after ingestion of 1,3-DMAA-containing workout supplement](https://pubmed.ncbi.nlm.nih.gov/24878759/) · Cardiac arrest after a DMAA-containing supplement; abstract lists cardiac arrest, hemorrhagic stroke and death among reported effects.
- **D** · clinical_outcomes · [Case reports: Death of active duty soldiers following ingestion of dietary supplements containing 1,3-dimethylamylamine (DMAA)](https://pubmed.ncbi.nlm.nih.gov/23397688/) · Both soldiers had exertional cardiac arrest and died; authors say DMAA with other ingredients may be associated with serious outcomes.

## BANNED_DMHA (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Like DMAA, it raises blood pressure, heart rate, and has been linked to cardiovascular events. | Its human pharmacology has barely been studied; side effects reported, mostly by users online, include high blood pressure, breathing difficulty and overheating, and it has been found in supplements at about twice its former pharmaceutical dose. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Octodrine: New Questions and Challenges in Sport Supplements](https://pubmed.ncbi.nlm.nih.gov/29461475/) · Only five relevant publications; reported side effects (largely from online sources) include hypertension, dyspnoea and hyperthermia.
- **C** · clinical_outcomes · [Four experimental stimulants found in sports and weight loss supplements: 2-amino-6-methylheptane (octodrine), 1,4-dimethylamylamine (1,4-DMAA), 1,3-dimethylamylamine (1,3-DMAA) and 1,3-dimethylbutylamine (1,3-DMBA)](https://pubmed.ncbi.nlm.nih.gov/29115866/) · Octodrine found at ~72 mg/serving, over twice the largest former pharmaceutical dose; safety of 1,4-DMAA and 1,3-DMBA in humans unknown.
- **C** · clinical_outcomes · [Nine prohibited stimulants found in sports and weight loss supplements: deterenol, phenpromethamine (Vonedrine), oxilofrine, octodrine, beta-methylphenylethylamine (BMPEA), 1,3-dimethylamylamine (1,3-DMAA), 1,4-dimethylamylamine (1,4-DMAA), 1,3-dimethylbutylamine (1,3-DMBA) and higenamine](https://pubmed.ncbi.nlm.nih.gov/33755516/) · Found up to 4 experimental stimulants per product, incl. octodrine 18-73 mg, BMPEA up to 92 mg, higenamine 48 mg per serving; safety unknown.
- **Flag for Sean:** safety_warning says 'associated with elevated blood pressure and cardiovascular risk'; only user-reported side effects exist. Aliases 'valerophenone' (a ketone) and '2-aminoheptane' (tuaminoheptane) are different compounds.

## BANNED_EPHEDRA (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Citing more than 18,000 adverse event reports and documented heart attacks, strokes and deaths, FDA banned | After a federally commissioned review screened more than 18,000 adverse-event case reports, and case reviews documented strokes, seizures and deaths, FDA banned |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Adverse cardiovascular and central nervous system events associated with dietary supplements containing ephedra alkaloids](https://pubmed.ncbi.nlm.nih.gov/11117974/) · 62% of reports at least possibly related; hypertension, palpitations/tachycardia, stroke (10), seizures (7); 10 deaths and 13 permanent disabilities.
- **A** · clinical_outcomes · [Efficacy and safety of ephedra and ephedrine for weight loss and athletic performance: a meta-analysis](https://pubmed.ncbi.nlm.nih.gov/12672771/) · 2.2-3.6-fold higher odds of psychiatric, autonomic, GI symptoms and palpitations; screened >18,000 case reports.
- **C** · clinical_outcomes · [Ischemic stroke after using over the counter products containing ephedra](https://pubmed.ncbi.nlm.nih.gov/14675610/) · Five ischemic strokes associated with ephedra products seen over 2 years at one hospital.
- **C** · clinical_outcomes · [The relative safety of ephedra compared with other herbal products](https://pubmed.ncbi.nlm.nih.gov/12639079/) · Ephedra products were 64% of herb adverse reactions but 0.82% of herb sales; relative risk 100-720 vs other herbs.
- **Flag for Sean:** safety_warning says 'heart attacks' and 'many in otherwise healthy users'; neither is in the sources read (strokes, seizures and deaths are). Alias 'sida cordifolia' is a different plant.

## BANNED_FASORACETAM (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| was investigated as a pharmaceutical for ADHD in adolescents but failed clinical trials and was never approved. | was tested for ADHD in adolescents: a small open-label study reported improvement, but two later placebo-controlled trials (NCT03265119, NCT02777931) posted no clear advantage over placebo, and it was never approved. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Fasoracetam in adolescents with ADHD and glutamatergic gene network variants disrupting mGluR neurotransmitter signaling](https://pubmed.ncbi.nlm.nih.gov/29339723/) · Reported symptom improvement and no difference in adverse events vs placebo week. Short duration, small, sponsor-founder conflict of interest.
- **Flag for Sean:** safety_warning and one-liner say 'failed clinical trials' / 'Failed investigational drug'; posted results show no clear advantage over placebo, with no published analysis.

## BANNED_FDC_RED_2_AMARANTH (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| — specifically bladder and mammary tumors in animal studies, though the data were considered inconclusive by some scientists | _removed_ |
| after studies submitted to the agency raised concerns about carcinogenicity. | after an FDA feeding study found a statistically significant increase in malignant tumors in aged female rats given a high dose, raising questions about carcinogenicity. |

Sources added (grade · what it supports · finding):
- **B** · context · [Scientific Opinion on the re-evaluation of Amaranth (E 123) as a food additive (EFSA Journal 2010;8(7):1649)](https://doi.org/10.2903/j.efsa.2010.1649) · EFSA set an ADI of 0.15 mg/kg bw/day from a 2-year rat study and reproductive studies; the abstract reports no carcinogenicity finding. Adult high exposure could exceed the ADI.
- **R** · mechanism_of_harm (existing 41 FR 5823 reference, now tagged) · FDA: high-dose feeding gave 'a statistically significant increase in a variety of malignant neoplasms among aged Osborne-Mendel female rats'.
- **Flag for Sean:** No source found for a specific tumor type; the 1976 FDA action (already cited) is the basis for 'cancer concerns'. EFSA 2010 set an ADI of 0.15 mg/kg bw/day and reports no carcinogenicity finding in its abstract.

## BANNED_HIGENAMINE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| At doses used in pre-workout supplements it elevates heart rate and blood pressure; cardiovascular adverse events have been reported. | Given intravenously it raises heart rate; small oral supplement trials found no significant change in heart rate or blood pressure, and no published cardiovascular adverse-event reports were found. |

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [Higenamine in Plants as a Source of Unintentional Doping](https://pubmed.ncbi.nlm.nih.gov/35161335/) · Describes higenamine as a plant beta-2 agonist on WADA's prohibited list since 2017.
- **B** · mechanism_of_harm · [A phase I study on pharmacokinetics and pharmacodynamics of higenamine in healthy Chinese subjects](https://pubmed.ncbi.nlm.nih.gov/23085737/) · Heart rate rose with plasma concentration (Emax model, baseline 68 bpm, Emax 73 bpm).
- **B** · clinical_outcomes · [Clinical safety assessment of oral higenamine supplementation in healthy, young men](https://pubmed.ncbi.nlm.nih.gov/25591969/) · No significant changes in heart rate, blood pressure, blood chemistry or liver enzymes in any group.
- **B** · clinical_outcomes · [Influence of Higenamine on Exercise Performance of Recreational Female Athletes: A Randomized Double-Blinded Placebo-Controlled Trial](https://pubmed.ncbi.nlm.nih.gov/34557123/) · No differences in blood pressure or other safety outcomes vs placebo.
- **Flag for Sean:** safety_warning says 'linked to cardiovascular stimulation risk'; oral trials found no heart-rate or blood-pressure change.

## BANNED_IBOTENIC_ACID (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Decarboxylates to muscimol during drying/processing. The combination of ibotenic acid (excitotoxin) and muscimol (GABAergic sedative) creates an unpredictable and dangerous pharmacological profile. Ibotenic acid is used in neuroscience research to create brain lesions — its neurotoxicity is well-established. | Drying and heating change the mushroom's ibotenic acid and muscimol content, and mushrooms containing both can cause excitation, sedation, or both. Injected into animal brains, it is used in research to create lesions; brain injury from eating it has not been shown in people. |

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [Ibotenic Acid and Muscimol in Amanita muscaria: Chemistry, Sources of Variability, Analytical Determination, and Toxicological Significance](https://pubmed.ncbi.nlm.nih.gov/42796518/) · Muscimol is a potent GABAergic agonist; content varies with species, tissue and processing; toxicity depends on dose and preparation.
- **D** · mechanism_of_harm · [Intrahippocampal Administration of Ibotenic Acid Induced Cholinergic Dysfunction via NR2A/NR2B Expression: Implications of Resveratrol against Alzheimer Disease Pathophysiology](https://pubmed.ncbi.nlm.nih.gov/27199654/) · Used as an excitotoxic lesion model; caused hippocampal neuron loss and memory impairment.
- **C** · clinical_outcomes · [Toxicity of muscimol and ibotenic acid containing mushrooms reported to a regional poison control center from 2002-2016](https://pubmed.ncbi.nlm.nih.gov/30073844/) · GI upset, CNS excitation and/or depression; 5 intubated; no seizures and no deaths in this series.
- **Flag for Sean:** safety_warning says it 'can cause excitotoxic brain injury'; that is shown only by direct brain injection in animals.

## BANNED_IGF1 (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| At supraphysiological levels, IGF-1 promotes cell proliferation and may accelerate growth of existing tumors. No safe supplement dose has been established. | In children treated with the approved injectable drug, low blood sugar is the most common side effect and several malignant tumours have been reported; its label says to stop treatment if one develops. These data come from injected mecasermin, not oral products. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [INCRELEX (mecasermin) prescribing information, Warnings and Precautions 5.1 and 5.7 (openFDA label)](https://api.fda.gov/drug/label.json?search=openfda.brand_name:INCRELEX&limit=1) · Severe hypoglycemia including seizures; several cases of malignant neoplasia in treated children; stop therapy if neoplasia develops.
- **B** · clinical_outcomes · [Effectiveness and Safety of rhIGF-1 Therapy in Children: The European Increlex® Growth Forum Database Experience](https://pubmed.ncbi.nlm.nih.gov/25824333/) · Hypoglycemia was the most frequent targeted adverse event (17.6%); 37 treatment-related serious adverse events.
- **B** · clinical_outcomes · [Effectiveness and safety of rhIGF1 therapy in patients with or without Laron syndrome](https://pubmed.ncbi.nlm.nih.gov/33434161/) · 65.3% had treatment-emergent adverse events; hypoglycaemia was the most common.
- **Flag for Sean:** safety_warning says 'acromegaly risk'; no source found, and all harm data are for injected mecasermin.

## BANNED_MUSCIMOL (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| It is a potent GABA-A receptor agonist causing sedation, euphoria, altered perception, and at higher doses: seizures, loss of consciousness, and respiratory depression. The margin between psychoactive and toxic doses is narrow and highly variable. | It is a potent GABA-A receptor agonist. Poisonings from muscimol-containing mushrooms have caused confusion, deep sedation or coma, sometimes needing a breathing tube, and seizures have been reported; muscimol content varies widely between mushrooms and with processing. |
| Muscimol itself (as isolated compound or concentrated extract) has been marketed in gummies and capsules, leading to the 2024 Diamond Shruumz mass poisoning event. | Muscimol was one of several psychoactive substances found in Diamond Shruumz products linked to a 2024 outbreak of severe illness. |

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [Ibotenic Acid and Muscimol in Amanita muscaria: Chemistry, Sources of Variability, Analytical Determination, and Toxicological Significance](https://pubmed.ncbi.nlm.nih.gov/42796518/) · Muscimol is a potent GABAergic agonist; content varies with species, tissue and processing; toxicity depends on dose and preparation.
- **C** · clinical_outcomes · [Toxicity of muscimol and ibotenic acid containing mushrooms reported to a regional poison control center from 2002-2016](https://pubmed.ncbi.nlm.nih.gov/30073844/) · GI upset, CNS excitation and/or depression; 5 intubated; no seizures and no deaths in this series.
- **C** · clinical_outcomes · [Acute Amanita muscaria Toxicity: A Literature Review and Two Case Reports in Elderly Spouses Following Home Preparation](https://pubmed.ncbi.nlm.nih.gov/41441606/) · Rapid GI symptoms, profound CNS depression and cholinergic features requiring ICU care; both recovered.
- **B** · clinical_outcomes · [Severe Illness Associated with Eating Mushroom-Containing Chocolate Products - United States, January-October 2024](https://pubmed.ncbi.nlm.nih.gov/41955162/) · FDA testing found psilocin in some tested products.

## BANNED_PHENIBUT (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| is a CNS depressant with GABAergic and GHB receptor activity | is a CNS depressant that acts on GABA-B receptors, like baclofen, |
| It causes physical dependence and severe withdrawal (anxiety, insomnia, psychosis) even after short-term use at doses found in supplements. Overdose with sedatives or alcohol can be fatal. | Regular daily use can cause physical dependence, and stopping can cause severe withdrawal; reported withdrawal cases mostly involved gram doses taken daily, and supplements have contained up to about 1,160 mg per serving. Serious poisonings, including coma and deaths, have been reported, many also involving alcohol or benzodiazepines. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Notes from the Field: Phenibut Exposures Reported to Poison Centers - United States, 2009-2019](https://pubmed.ncbi.nlm.nih.gov/32881852/) · Coma in 6.2% and major effects in 12.6%; 3 deaths, 1 of them phenibut-only. Coingestants in 40% of adult cases. Notes the dependence potential.
- **A** · clinical_outcomes · [Clinical Presentations and Treatment of Phenibut Toxicity and Withdrawal: A Systematic Literature Review](https://pubmed.ncbi.nlm.nih.gov/37579098/) · Toxicity: altered mental status, somnolence, psychosis; 48.7% intubated; benzos and alcohol common coingestants. Withdrawal (95.7% daily users): anxiety, agitation, insomnia, psychosis.
- **A** · clinical_outcomes · [A Systematic Review of Phenibut Withdrawals](https://pubmed.ncbi.nlm.nih.gov/39376891/) · Withdrawal cases mostly in people with substance-use histories; doses reported up to 28.5 g/day. Case-level evidence only.
- **C** · clinical_outcomes · [Quantity of phenibut in dietary supplements before and after FDA warnings](https://pubmed.ncbi.nlm.nih.gov/34550038/) · After FDA warnings, products contained 21-1,164 mg per serving, up to 450% of a typical 250 mg Russian tablet.
- **D** · mechanism_of_harm, clinical_outcomes · [Phenibut, a GABAB Agonist, Detected in a Fatality](https://pubmed.ncbi.nlm.nih.gov/34520515/) · Phenibut confirmed in blood and urine of a 26-year-old found dead; autopsy and routine toxicology otherwise unremarkable. Causation not established.

## BANNED_S23 (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| it suppresses LH, FSH, and sperm production at moderate doses. | in male rats it suppressed LH and FSH and, combined with estradiol, reversibly stopped sperm production; no human data were found. |
| and carries the same risks as other SARMs (endocrine suppression, hepatotoxicity). | _removed_ |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [Preclinical characterization of a (S)-N-(4-cyano-3-trifluoromethyl-phenyl)-3-(3-fluoro, 4-chlorophenoxy)-2-hydroxy-2-methyl-propanamide: a selective androgen receptor modulator for hormonal male contraception](https://pubmed.ncbi.nlm.nih.gov/18772237/) · Suppressed LH >50% at >0.1 mg/d; with estradiol, azoospermia in 4/6 and no pregnancies; fully reversible after 100 days.
- **Flag for Sean:** safety_warning says 'testicular suppression, liver strain, and cardiovascular risk'; only rat hormone/sperm data exist.

## BANNED_SR9009 (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Important note: animal studies suggest it has near-zero oral bioavailability, meaning supplement products claiming metabolic or endurance benefits are likely fraudulent in addition to selling an unapproved compound. | Its effects in cells are not limited to its intended target, and one case report describes liver injury after use of a product labeled Stenabolic. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [SR9009 has REV-ERB-independent effects on cell proliferation and metabolism](https://pubmed.ncbi.nlm.nih.gov/31127047/) · SR9009 reduced cell viability and altered metabolism and transcription even without its REV-ERB targets.
- **D** · clinical_outcomes · [In Vitro Metabolic Studies of REV-ERB Agonists SR9009 and SR9011](https://pubmed.ncbi.nlm.nih.gov/27706103/) · No pharmaceutical preparations exist; SR9009 found in an internet black-market product; described as potentially harmful.
- **D** · clinical_outcomes · [When Gains Go Wrong: A Case of Selective Androgen Receptor Modulator-Related Liver Injury](https://pubmed.ncbi.nlm.nih.gov/40765588/) · Hepatocellular injury attributed to Stenabolic after excluding infectious/autoimmune causes; improved after stopping.
- **Flag for Sean:** safety_warning says 'Poor oral bioavailability'; no pharmacokinetic source was found.

## BANNED_TIANEPTINE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| acts as a full agonist at mu-opioid receptors at the doses found in US supplement products. | acts as a mu-opioid receptor agonist. |
| At doses used in supplements (well above the therapeutic range of 12.5mg/day used in Europe), it causes | People misusing it have reported taking grams a day, far above the usual prescription dose abroad of 37.5 mg a day (12.5 mg three times daily). It causes |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [The atypical antidepressant and neurorestorative agent tianeptine is a μ-opioid receptor agonist](https://pubmed.ncbi.nlm.nih.gov/25026323/) · An efficacious MOR agonist (human EC50 about 194 nM); the paper calls it a 'full' agonist only at the delta receptor, at much lower potency.
- **B** · clinical_outcomes · [Improvement in subjective and objective neurocognitive functions in patients with major depressive disorder: a 12-week, multicenter, randomized trial of tianeptine versus escitalopram, the CAMPION study](https://pubmed.ncbi.nlm.nih.gov/24525660/) · Used tianeptine 37.5 mg/day, the standard therapeutic dose.
- **A** · clinical_outcomes · [Tianeptine misuse and addiction: A systematic review of withdrawal, toxicity, and clinical management](https://pubmed.ncbi.nlm.nih.gov/42177839/) · Opioid-like dependence and withdrawal. Overdose with CNS and respiratory depression; 7 of 22 detailed overdose cases were fatal; 22% of series patients needed ICU.
- **B** · clinical_outcomes · [Tianeptine Exposures Reported to United States Poison Centers, 2015-2023](https://pubmed.ncbi.nlm.nih.gov/39724478/) · Exposure rate rose 1,400%; 12% major effects; 22.9% critical care; withdrawal accounted for 22.5% of exposures.
- **B** · clinical_outcomes · [Tianeptine-involved emergency department visits, fatal overdoses, and substance seizures in Tennessee, 2021-2023](https://pubmed.ncbi.nlm.nih.gov/39258110/) · 6 tianeptine-involved fatal overdoses, all involving other substances (polysubstance).
- **C** · clinical_outcomes · [Poison control center experience with tianeptine: an unregulated pharmaceutical product with potential for abuse](https://pubmed.ncbi.nlm.nih.gov/29799284/) · Reported abuse doses of 5 and 10 g daily; 5 patients had opioid-withdrawal symptoms.

## BANNED_YELLOW_OLEANDER_RECENT (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| contains cardiac glycosides (thevetin A and B, cerberin) that cause life-threatening cardiotoxicity — bradycardia, heart block, ventricular arrhythmia — at very low doses. | contains cardiac glycosides (thevetin A, thevetin B and neriifolin) that cause life-threatening heart toxicity, mainly slow heart rhythms and heart block. |
| in multiple documented cases, where the substitution was not disclosed on labels. | in multiple documented cases, where the substitution was not disclosed on labels; in 2022 a child who ate such a product needed antidote treatment for slow heart rhythm and low blood pressure. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Acute yellow oleander (Thevetia peruviana) poisoning: cardiac arrhythmias, electrolyte disturbances, and serum cardiac glycoside concentrations on presentation to hospital](https://pubmed.ncbi.nlm.nih.gov/10677410/) · Most symptomatic patients had sinus-node or AV-node conduction defects; few had ventricular tachyarrhythmias; severity tracked glycoside levels and hyperkalaemia.
- **C** · mechanism_of_harm · [A review of the natural history, toxinology, diagnosis and clinical management of Nerium oleander (common oleander) and Thevetia peruviana (yellow oleander) poisoning](https://pubmed.ncbi.nlm.nih.gov/20438743/) · All parts are toxic and contain cardiac glycosides (neriifolin, thevetin A/B); causes vomiting, dysrhythmias and hyperkalaemia; potentially lethal; Fab effective.
- **B** · clinical_outcomes · [Notes from the Field: Online Weight Loss Supplements Labeled as Tejocote (Crataegus mexicana) Root, Substituted with Yellow Oleander (Cascabela thevetia) - United States, 2022](https://pubmed.ncbi.nlm.nih.gov/37708076/) · Child had bradycardia, hypotension and PVCs needing digoxin Fab twice; 9 of 10 tejocote-labeled products were yellow oleander (full text read, PMC10511264).
- **C** · clinical_outcomes · [Authentication of tejocote (Crataegus mexicana) dietary supplements based on DNA barcoding and chemical profiling](https://pubmed.ncbi.nlm.nih.gov/34415825/) · Alipotec samples labeled tejocote contained yellow oleander instead.

## HIGH_RISK_CHAPARRAL (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| contains nordihydroguaiaretic acid (NDGA), which has been associated with at least 18 cases of severe liver injury in the literature, including hepatitis, cirrhosis, and fulminant liver failure requiring transplantation. | has been linked to liver injury: of 18 adverse-event reports FDA reviewed from 1992 to 1994, 13 showed liver toxicity, including cirrhosis and fulminant liver failure requiring transplantation. Its main lignan, nordihydroguaiaretic acid (NDGA), is a suspected cause. |
| The mechanism involves reactive NDGA metabolites that form adducts with liver proteins. | In laboratory studies NDGA can be oxidized to reactive quinones, one proposed mechanism. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Chaparral-associated hepatotoxicity](https://pubmed.ncbi.nlm.nih.gov/9129552/) · 13 of 18 had hepatotoxicity, mostly cholestatic hepatitis; 4 progressed to cirrhosis, 2 had fulminant failure needing liver transplant.
- **D** · clinical_outcomes · [Chaparral ingestion. The broadening spectrum of liver injury caused by herbal medications](https://pubmed.ncbi.nlm.nih.gov/7837368/) · Severe hepatitis with no other cause progressed to fulminant failure requiring orthotopic liver transplant.
- **B** · clinical_outcomes · [Chaparral](https://pubmed.ncbi.nlm.nih.gov/31643676/) · Chaparral extracts linked to several cases of liver injury, some leading to acute liver failure and emergency transplantation.
- **D** · mechanism_of_harm · [Oxidation of the lignan nordihydroguaiaretic acid](https://pubmed.ncbi.nlm.nih.gov/17672511/) · NDGA likely forms a reactive ortho-quinone; GSH adducts formed in rat microsomes, though mostly by autoxidation. Human liver toxicity is described as suggested.
- **Flag for Sean:** safety_warning says 'at least 18 reported cases of severe liver injury'; the source reports 13 of 18 FDA reports with liver toxicity.

## HIGH_RISK_PENNYROYAL (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| metabolized by CYP2E1 to the reactive hepatotoxin menthofuran. | metabolized by cytochrome P450 enzymes to the reactive hepatotoxin menthofuran. |
| Even a few milliliters of the essential oil can cause fulminant liver failure and death. The oil was historically used as an abortifacient — making it particularly dangerous during pregnancy. | Ingesting about 10 mL or more of the oil has caused moderate to severe toxicity, including fatal liver failure, and mint teas contaminated with pennyroyal oil have caused liver and nerve injury in infants. The oil was historically used as an abortifacient despite its potentially lethal liver toxicity. |
| Topical use at very low concentrations is less concerning. | _removed_ |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Pennyroyal toxicity: measurement of toxic metabolite levels in two cases and review of the literature](https://pubmed.ncbi.nlm.nih.gov/8633832/) · One of 4 patients died. Prior reports showed moderate-to-severe toxicity after at least 10 mL of oil; long used as an abortifacient.
- **D** · clinical_outcomes · [Multiple organ failure after ingestion of pennyroyal oil from herbal tea in two infants](https://pubmed.ncbi.nlm.nih.gov/8909490/) · One infant died of fulminant liver failure with cerebral edema; the other had liver dysfunction and severe epileptic encephalopathy.
- **B** · clinical_outcomes · [Pennyroyal Oil](https://pubmed.ncbi.nlm.nih.gov/31643984/) · Taken by mouth, pennyroyal oil is highly toxic and linked to several cases of toxic liver injury and death; formerly used as an abortifacient.
- **C** · mechanism_of_harm · [A decades-long investigation of acute metabolism-based hepatotoxicity by herbal constituents: a case study of pennyroyal oil](https://pubmed.ncbi.nlm.nih.gov/25512112/) · Reviews P450-mediated bioactivation of pulegone and menthofuran underlying the oil's acute liver toxicity.
- **D** · mechanism_of_harm · [Tandem mass spectrometric analysis of S- and N-linked glutathione conjugates of pulegone and menthofuran and identification of P450 enzymes mediating their formation](https://pubmed.ncbi.nlm.nih.gov/26969934/) · Menthofuran is a hepatotoxic pulegone metabolite bioactivated by CYPs; CYP1A2, 2B6 and 3A4 formed most reactive conjugates.

## HM_ARSENIC (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| It also causes peripheral neuropathy, cardiovascular disease, and diabetes. Organic arsenic (found in seafood) is less toxic. | Chronic exposure is also linked to neurological, cardiovascular and endocrine effects. |
| In supplements, arsenic contamination is most common in rice protein, kelp, spirulina, certain Ayurvedic preparations, and marine-sourced ingredients. | _removed_ |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [The broad scope of health effects from chronic arsenic exposure: update on a worldwide public health problem](https://pubmed.ncbi.nlm.nih.gov/23458756/) · Arsenic is a known carcinogen (skin, lung, bladder, kidney, liver); also dermatological, neurological, cardiovascular, immunological and endocrine effects.
- Inorganic arsenic IARC Group 1 confirmed via PubChem carcinogen classification (CID 5359596, IARC Suppl 7).

## HM_CADMIUM (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| causing progressive renal tubular damage and ultimately kidney failure (itai-itai disease at high environmental exposures). It also causes bone demineralization by interfering with vitamin D metabolism. IARC Group 1 carcinogen (lung cancer, endometrial cancer evidence). | causing kidney tubular damage that can progress to kidney failure. It can also damage bone, directly or as a result of kidney damage. IARC Group 1 carcinogen. |
| Common in plant-based supplements grown in cadmium-rich soils (cocoa, leafy greens, grains). | Food is the main source of cadmium for non-smokers. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Current status of cadmium as an environmental health problem](https://pubmed.ncbi.nlm.nih.gov/19409405/) · Kidney half-time 10-30 years; nephrotoxic, starting with tubular damage that can progress to renal failure; bone damage; suggested increased cancer risk.
- Cadmium IARC Group 1 confirmed via PubChem (CID 23973).

## HM_LEAD (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| is a cumulative neurotoxin with no established safe blood level, particularly for cognitive development in children. It distributes to bone, brain, kidney, and liver. Chronic low-level exposure impairs IQ, attention, and impulse control in children; in adults it raises cardiovascular risk. | is a cumulative neurotoxin. In children, intellectual deficits have been found even at blood lead levels below 7.5 µg/dL; in adults, low-level exposure is linked to higher cardiovascular death rates. |
| Lead contamination in supplements is common in mineral products, certain botanicals, and products manufactured with inadequate heavy metal testing. | Lead has been detected in many supplements; a 2025 study found it in most prenatal vitamins tested, with higher levels in products containing more calcium and iron. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Low-level environmental lead exposure and children's intellectual function: an international pooled analysis](https://pubmed.ncbi.nlm.nih.gov/16002379/) · Inverse blood lead-IQ relation; steeper decrements below 7.5 µg/dL; 3.9 IQ points lost from 2.4 to 10 µg/dL. Erratum published 2019.
- **B** · clinical_outcomes · [Low-level lead exposure and mortality in US adults: a population-based cohort study](https://pubmed.ncbi.nlm.nih.gov/29544878/) · Blood lead 1.0 to 6.7 µg/dL linked to higher all-cause (HR 1.37), cardiovascular (HR 1.70) and ischaemic heart disease (HR 2.08) mortality.
- **C** · clinical_outcomes · [Heavy metals and phthalate contamination in prenatal vitamins and folic acid supplements](https://pubmed.ncbi.nlm.nih.gov/40020868/) · Cadmium above LOQ in 73% of commercial prenatal vitamins. Funded by Clean Label Project; authors report paid expert testimony (COI).
- Inorganic lead IARC Group 2A confirmed via PubChem IARC note (CID 9317: 'inorganic lead (Group 2A)').
- **Flag for Sean:** safety_warning says 'no safe blood level' and 'kidney ... harm'; the sources read show deficits below 7.5 µg/dL without stating no safe level, and no kidney source was read. 40020868 is Clean Label Project funded (graded C).

## NOOTROPIC_9MEBC (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| studied in preclinical neurochemistry for dopaminergic effects. No human safety data exists. | studied only in cell and animal experiments, mainly for dopaminergic effects; no human studies were found. |
| At the same time, β-carbolines as a class include monoamine oxidase inhibitors, raising the risk of dangerous drug-supplement interactions with serotonergic medications. | In laboratory studies it inhibits monoamine oxidase (MAO-A and MAO-B), so it could interact with antidepressants and other serotonergic drugs; this has not been studied in people. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [9-Methyl-β-carboline inhibits monoamine oxidase activity and stimulates the expression of neurotrophic factors by astrocytes](https://pubmed.ncbi.nlm.nih.gov/32285253/) · 9-MBC inhibited MAO-A (IC50 1 uM) and MAO-B (IC50 15.5 uM); authors frame it as a candidate anti-Parkinson drug.
- **D** · mechanism_of_harm · [9-Methyl-β-carboline-induced cognitive enhancement is associated with elevated hippocampal dopamine levels and dendritic and synaptic proliferation](https://pubmed.ncbi.nlm.nih.gov/22380576/) · 10 days of 9-MBC raised hippocampal dopamine and improved spatial learning in rats.
- **C** · mechanism_of_harm · [Stimulation, protection and regeneration of dopaminergic neurons by 9-methyl-β-carboline: a new anti-Parkinson drug?](https://pubmed.ncbi.nlm.nih.gov/21651332/) · Summarizes dopaminergic stimulation, MAO-A/B inhibition, and anti-inflammatory effects; all evidence preclinical.

## NOOTROPIC_ADRAFINIL (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Adrenal and cardiovascular effects mirror modafinil. | FDA laboratory analysis has found adrafinil in products sold as dietary supplements. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [Identification of adrafinil and its main metabolite modafinil in human hair. Self-administration study and interpretation of an authentic case](https://pubmed.ncbi.nlm.nih.gov/33457050/) · Adrafinil is primarily metabolized in vivo to modafinil; both were detected in hair after a single 200 mg dose.
- **C** · clinical_outcomes · [Development and Validation of an Analytical Method to Identify and Quantitate Novel Modafinil Analogs in Products Marketed as Dietary Supplements](https://pubmed.ncbi.nlm.nih.gov/39466147/) · Adrafinil was found in all 4 supplement products tested; the authors call unsupervised use of analogs a public health risk.

## NOOTROPIC_BROMANTANE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| At high doses it has shown dopaminergic effects and the potential for psychostimulant dependence. | In rats it increases dopamine synthesis and release. Human data come mainly from Russian clinical studies of 50-100 mg a day for about four weeks, so long-term and high-dose safety is not established. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [The effects of ladasten on dopaminergic neurotransmission and hippocampal synaptic plasticity in rats](https://pubmed.ncbi.nlm.nih.gov/17854844/) · Single dose altered tyrosine hydroxylase and dopamine/L-DOPA content in several brain regions; D1/D5-dependent plasticity effects.
- **D** · mechanism_of_harm · [[Ladasten induces the expression of genes regulating dopamine biosynthesis in various structures of rat brain]](https://pubmed.ncbi.nlm.nih.gov/15500036/) · Increased dopamine release early, then de novo tyrosine hydroxylase and DOPA-decarboxylase gene expression.
- **D** · clinical_outcomes · [[Treatment of asthenic disorders in patients with psychoautonomic syndrome: results of a multicenter study on efficacy and safety of ladasten]](https://pubmed.ncbi.nlm.nih.gov/20559263/) · Adverse effects reported in 3%, discontinuation 0.8%, and no serious adverse effects. This is uncontrolled, sponsor-region data.
- **Flag for Sean:** safety_warning says 'FDA has stated is not a lawful supplement ingredient'; no FDA document naming bromantane was found (Q58 Cat 1).

## NOOTROPIC_FLMODAFINIL (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| a synthetic difluoro analog of modafinil with greater potency. | a synthetic difluoro analog of modafinil. |
| No human clinical safety data exists. | No human clinical safety data exist; the only published human data are a drug-testing study in six volunteers given 20 mg. |

Sources added (grade · what it supports · finding):
- **D** · clinical_outcomes · [Investigations Into the Metabolism and Elimination of Flmodafinil and Fladrafinil for Sports Drug Testing Purposes](https://pubmed.ncbi.nlm.nih.gov/42210629/) · Characterizes urinary and blood metabolites; notes rising non-medical use for cognitive enhancement and WADA S6 status.
- **C** · clinical_outcomes · [Development and Validation of an Analytical Method to Identify and Quantitate Novel Modafinil Analogs in Products Marketed as Dietary Supplements](https://pubmed.ncbi.nlm.nih.gov/39466147/) · Adrafinil was found in all 4 supplement products tested; the authors call unsupervised use of analogs a public health risk.
- **Flag for Sean:** aliases may include mono-fluoro 'fluoromodafinil'/'4-fluoromodafinil', a different compound (identity check).

## NOOTROPIC_OMBERACETAM (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Psychoactive mechanism: potentiates AMPA/NMDA receptors; safety data in humans at supplement doses is absent. | Its mechanism is not established (laboratory work points to HIF-1 activation). Supplements have been found to deliver up to about four times its typical 10 mg pharmacological dose; the health effects of such doses are unknown. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [Molecular Mechanism Underlying the Action of Substituted Pro-Gly Dipeptide Noopept](https://pubmed.ncbi.nlm.nih.gov/27099787/) · Proposes HIF-1 activation (prolyl hydroxylase binding) as the primary mechanism. This contradicts the stated AMPA/NMDA-potentiation mechanism, which was not found in any abstract.
- **C** · clinical_outcomes · [Five Unapproved Drugs Found in Cognitive Enhancement Supplements](https://pubmed.ncbi.nlm.nih.gov/34484905/) · Serving sizes delivered up to 40.6 mg omberacetam (typical dose 10 mg) and 502 mg aniracetam; 75% of declared quantities inaccurate; health effects unknown.

## NOOTROPIC_PHENYLPIRACETAM (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| At pharmacological doses it produces stimulant and nootropic effects similar to controlled stimulants. | In laboratory studies it blocks dopamine reuptake; its abuse potential in people has not been well studied. |

Sources added (grade · what it supports · finding):
- **D** · mechanism_of_harm · [S-phenylpiracetam, a selective DAT inhibitor, reduces body weight gain without influencing locomotor activity](https://pubmed.ncbi.nlm.nih.gov/28743458/) · S-phenylpiracetam is a selective dopamine transporter inhibitor; notably it did NOT increase locomotor activity in these models.
- **A** · clinical_outcomes · [[Efficacy and safety of fonturacetam in asthenia: a systematic review and meta-analysis]](https://pubmed.ncbi.nlm.nih.gov/40047835/) · Side effects in about 5.5%, transient. Russian-language, sponsor-region literature.
- **C** · clinical_outcomes · [Unauthorized ingredients in "nootropic" dietary supplements: A review of the history, pharmacology, prevalence, international regulations, and potential as doping agents](https://pubmed.ncbi.nlm.nih.gov/37357012/) · Fonturacetam/phenylpiracetam was the first nootropic prohibited in sport (1998); many nootropic supplement ingredients are unauthorized or unapproved drugs.

## PEPTIDE_MELANOTAN_II (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Serious safety concerns include: melanoma risk (promoting pre-existing melanocytic lesions), nausea and vomiting, spontaneous penile erections, and the near-universal practice of injection by users — creating sterility and contamination risks that do not apply to oral supplements. | Reported harms include melanoma and rapidly changing moles in users (case reports, often with sunbed use; causation not established), frequent nausea, spontaneous erections and priapism, and the infection and contamination risks of injecting. |

Sources added (grade · what it supports · finding):
- **D** · clinical_outcomes · [Melanocortin receptor agonists, penile erection, and sexual motivation: human studies with Melanotan II](https://pubmed.ncbi.nlm.nih.gov/11035391/) · Erection without stimulation in 17/20; nausea and yawning frequent; 12.9% severe nausea at 0.025 mg/kg.
- **D** · clinical_outcomes · [Melanotan-induced priapism: a hard-earned tan](https://pubmed.ncbi.nlm.nih.gov/30796078/) · Low-flow priapism requiring aspiration and phenylephrine; erectile function not recovered at 4 weeks.
- **D** · clinical_outcomes · [Melanotan-associated melanoma in situ](https://pubmed.ncbi.nlm.nih.gov/22724573/) · Melanoma in situ; notes prior reports of dysplastic naevi and melanoma with melanotropic peptides.
- **D** · clinical_outcomes · [Melanoma associated with the use of melanotan-II](https://pubmed.ncbi.nlm.nih.gov/24355990/) · Cutaneous melanoma 3 months after a 3-4 week MT-II course combined with sunbed use (confounded by UV).
- **C** · clinical_outcomes · [Melanotropic peptides: more than just 'Barbie drugs' and 'sun-tan jabs'?](https://pubmed.ncbi.nlm.nih.gov/20545686/) · MHRA warned of blood-borne virus transmission from needle sharing and product impurity; users may have rapidly pigmenting naevi.
- **C** · clinical_outcomes · [Melanotan II: a possible cause of renal infarction: review of the literature and case report](https://pubmed.ncbi.nlm.nih.gov/31953620/) · Renal infarction likely attributed to MT-II; states MT-II-induced rhabdomyolysis and renal failure have been described previously.

## PHARMA_LORCASERIN (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| users receive a withdrawn drug with confirmed cancer risk signals, | users receive a withdrawn drug with a cancer risk signal, |

Sources added (grade · what it supports · finding):
- **A** · clinical_outcomes · [Is lorcaserin really associated with increased risk of cancer? A systematic review and meta-analysis](https://pubmed.ncbi.nlm.nih.gov/33258543/) · Notes FDA's Feb 2020 report; pooled cancer RR 1.08 (0.96-1.23), driven by CAMELLIA-TIMI 61 with more lung and pancreatic cancers.
- **C** · clinical_outcomes · [First identification and quantification of lorcaserin in an herbal slimming dietary supplement](https://pubmed.ncbi.nlm.nih.gov/24905289/) · Lorcaserin found at 6.6 mg/capsule in a supplement claimed to be natural.

## RC_CARDARINE_ANALOGS (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| whose parent compound caused rapid multi-tissue carcinogenesis in animal trials. | whose parent compound was abandoned after rodent studies linked it to widespread tumour development. |
| Products containing Cardarine derivatives should be treated with the same concern as the parent compound. | _removed_ |

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [Harnessing the benefits of PPARβ/δ agonists](https://pubmed.ncbi.nlm.nih.gov/24184294/) · States GSK discontinued further research after rodent preclinical studies linked GW501516 to widespread tumour development.
- **D** · mechanism_of_harm · [Activation of nuclear hormone receptor peroxisome proliferator-activated receptor-delta accelerates intestinal adenoma growth](https://pubmed.ncbi.nlm.nih.gov/14758356/) · GW501516 significantly increased number and size of intestinal polyps (fivefold more polyps >2 mm).

## RECALLED_HYDROXYCUT (recalled)
| Before (removed or reworded) | Final claim |
|---|---|
| was linked to 23 reports of serious liver injury including one death before FDA issued a consumer warning and initiated a voluntary recall in 2009. The original formulation contained a combination including hydroxycitric acid (Garcinia cambogia) and other ingredients. The exact hepatotoxic mechanism was not isolated to a single ingredient. | was linked to serious liver injury and was recalled in May 2009; a published series of 17 cases included three liver transplants and one death. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Hepatotoxicity due to hydroxycut: a case series](https://pubmed.ncbi.nlm.nih.gov/20104221/) · All 8 hospitalized, 3 transplants; one fatal acute liver failure among MedWatch cases; 8 definite, 5 highly likely causality; recalled May 2009.
- **Flag for Sean:** safety_warning says '23 reports of severe liver injury and one death'; the 23 is FDA's 2009 figure, not verified here (Hydroxycut recall is Q58 Cat 4).

## RECALLED_JACK3D (recalled)
| Before (removed or reworded) | Final claim |
|---|---|
| was recalled after the product — which contained DMAA (1,3-dimethylamylamine) as an active ingredient — was linked to two deaths of US military personnel during exercise, as well as multiple hospitalizations from hemorrhagic stroke and heart attack. | contained DMAA (1,3-dimethylamylamine) and was recalled. Two US soldiers who collapsed and died during exercise had been taking DMAA-containing supplements, and case reports describe a hemorrhagic stroke and a heart attack in young men taking Jack3d. |

Sources added (grade · what it supports · finding):
- **D** · clinical_outcomes · [Case reports: Death of active duty soldiers following ingestion of dietary supplements containing 1,3-dimethylamylamine (DMAA)](https://pubmed.ncbi.nlm.nih.gov/23397688/) · Both soldiers had exertional cardiac arrest and died; authors say DMAA with other ingredients may be associated with serious outcomes.
- **D** · clinical_outcomes · [Hemorrhagic stroke in young healthy male following use of sports supplement Jack3d](https://pubmed.ncbi.nlm.nih.gov/23397687/) · Right thalamic hemorrhagic stroke shortly after taking Jack3d; authors note several constituents could contribute.
- **D** · clinical_outcomes · [Acute myocardial infarction associated with dietary supplements containing 1,3-dimethylamylamine and Citrus aurantium](https://pubmed.ncbi.nlm.nih.gov/24512406/) · NSTEMI with LAD thrombus; resolved with medical therapy.
- **Flag for Sean:** safety_warning says Jack3d's DMAA 'was linked to two deaths'; the case report names DMAA-containing supplements, not Jack3d.

## RECALLED_OXYELITE_PRO (recalled)
| Before (removed or reworded) | Final claim |
|---|---|
| over 97 cases reported, 44 hospitalizations, 3 liver transplants, and 1 death. | Hawaii's investigation found 44 cases (36 exposed to OxyELITE Pro), two liver transplants and one death, and FDA adverse-event reports included 55 liver-disease cases, 33 hospitalizations and three transplants. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Notes from the field: acute hepatitis and liver failure following the use of a dietary supplement intended for weight loss or muscle building--May-October 2013](https://pubmed.ncbi.nlm.nih.gov/24113901/) · Severe acute hepatitis and fulminant liver failure in seven patients who had all used OxyELITE Pro.
- **B** · clinical_outcomes · [Hepatotoxicity associated with the dietary supplement OxyELITE Pro™ - Hawaii, 2013](https://pubmed.ncbi.nlm.nih.gov/26538199/) · 36/44 cases had OEP exposure; two transplants and one death; mechanism of hepatotoxicity not identified.
- **D** · clinical_outcomes · [The Role of Adverse Event Reporting in the FDA Response to a Multistate Outbreak of Liver Disease Associated with a Dietary Supplement](https://pubmed.ncbi.nlm.nih.gov/26327730/) · 55 non-viral liver disease reports, 33 hospitalized, 3 transplants; DMAA replaced by aegeline without required NDI notice; no toxic contaminant found.
- **B** · clinical_outcomes · [Severe Acute Hepatocellular Injury Attributed to OxyELITE Pro: A Case Series](https://pubmed.ncbi.nlm.nih.gov/27142670/) · 6/7 hospitalized, 3 acute liver failure, 2 transplants; causality definite to possible.
- **Flag for Sean:** safety_warning says '97 cases, three liver transplants, and one death'; no source gives 97.

## RISK_BITTER_ORANGE (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| a sympathomimetic amine that binds adrenergic receptors similarly to ephedrine. | a sympathomimetic amine structurally related to ephedrine. |
| FDA has received adverse event reports including hypertension, tachycardia, stroke, and myocardial infarction associated with bitter orange supplements. At doses used in supplements, synephrine may raise blood pressure and heart rate, particularly in combination with caffeine. Its cardiovascular risk profile closely mirrors the pattern that led to ephedra's federal ban. | Case reports link multi-ingredient products containing bitter orange or synephrine, usually with caffeine, to stroke, heart attack and severe high blood pressure; causation by synephrine has not been established. In small human studies, synephrine products raised heart rate, and blood pressure rose with caffeine-containing products. Whether bitter orange alone carries ephedra-like risk is debated. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [[Risk assessment of synephrine in dietary supplements]](https://pubmed.ncbi.nlm.nih.gov/28058460/) · Animal data show BP rise and arrhythmia enhanced by caffeine/exercise; some human studies show CV effects; case reports of hypertension, arrhythmia, MI.
- **B** · mechanism_of_harm · [Hemodynamic effects of ephedra-free weight-loss supplements in humans](https://pubmed.ncbi.nlm.nih.gov/16164886/) · Xenadrine EFX raised SBP/DBP and HR; Advantra Z raised HR at 6 h but not BP; BP effects probably not due to C. aurantium alone.
- **D** · mechanism_of_harm · [Human pharmacology of a performance-enhancing dietary supplement under resting and exercise conditions](https://pubmed.ncbi.nlm.nih.gov/18341680/) · Post-exercise diastolic BP and glucose higher than placebo; no substantial HR or SBP difference; no significant adverse events.
- **D** · clinical_outcomes · [Ischemic stroke associated with use of an ephedra-free dietary supplement containing synephrine](https://pubmed.ncbi.nlm.nih.gov/15819293/) · Thalamic and cerebellar infarcts with no major risk factors; vasospasm considered most likely.
- **D** · clinical_outcomes · [Vasospasm and stroke attributable to ephedra-free xenadrine: case report](https://pubmed.ncbi.nlm.nih.gov/18700609/) · Left middle cerebral artery vasospasm and stroke during Xenadrine-EFX use.
- **C** · clinical_outcomes · [STEMI in a 24-year-old man after use of a synephrine-containing dietary supplement: a case report and review of the literature](https://pubmed.ncbi.nlm.nih.gov/20069086/) · ST-elevation MI with extensive LAD thrombus within hours of taking the product; no risk factors found.
- **D** · clinical_outcomes · [Hypertensive Urgency Associated With Xenadrine EFX Use](https://pubmed.ncbi.nlm.nih.gov/21676849/) · Hypertensive urgency (BP 234/130) that resolved after the product was stopped and treatment given.
- **C** · clinical_outcomes · [Review of Published Bitter Orange Extract and p-Synephrine Adverse Event Clinical Study Case Reports](https://pubmed.ncbi.nlm.nih.gov/30835576/) · Argues no case report confirmed p-synephrine presence or causation and ephedrine effects cannot be extrapolated to p-synephrine.
- **Flag for Sean:** safety_warning says 'ephedrine-like cardiovascular effects'; that equivalence is disputed in the literature. Alias 'citrus bioflavonoids' may not contain synephrine.

## RISK_GERMANIUM (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| Inorganic germanium compounds (germanium dioxide, organic germanium carboxylate) were marketed | Germanium compounds (germanium dioxide and organic forms such as carboxyethyl germanium sesquioxide) were marketed |
| Japan reported over 30 deaths from kidney failure associated with inorganic germanium use. The compound accumulates in the kidneys and peripheral nerves, causing progressive and irreversible nephropathy and peripheral neuropathy. | At least 31 reported cases worldwide linked prolonged germanium intake to kidney failure, some fatal. Germanium accumulates in the kidneys; kidney function recovers slowly and incompletely after stopping, and peripheral neuropathy has also been reported. Organic forms have not been shown to be less harmful to the kidneys. |
| Products containing inorganic germanium compounds should be considered immediately unsafe. | Products containing germanium compounds should be considered unsafe. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Hazard assessment of germanium supplements](https://pubmed.ncbi.nlm.nih.gov/9237323/) · At least 31 cases of renal failure, some fatal; tubular degeneration, Ge accumulation, anemia, weakness, neuropathy; recovery slow and incomplete.
- **C** · clinical_outcomes · [Nephrotoxicity and neurotoxicity in humans from organogermanium compounds and germanium dioxide](https://pubmed.ncbi.nlm.nih.gov/1726409/) · 18 cases of acute renal dysfunction or failure, 2 deaths; tubular vacuolar degeneration; recovery never complete.
- **Flag for Sean:** safety_warning says 'Inorganic germanium compounds'; the case reports include organic forms (Ge-132, germanium lactate-citrate).

## RISK_GREEN_TEA_EXTRACT_HIGH (watchlist)
| Before (removed or reworded) | Final claim |
|---|---|
| is associated with drug-induced liver injury (DILI) when taken at doses exceeding approximately 800mg EGCG per day. | is associated with drug-induced liver injury (DILI). In clinical trials, intakes of 800 mg EGCG a day or more raised liver enzymes, and published liver-injury case reports involve intakes from about 140 mg to 1,000 mg EGCG a day. |
| The European Food Safety Authority (EFSA) issued a warning in 2018 that GTE preparations providing ≥800mg EGCG/day taken on an empty stomach 'raise concerns for liver safety.' | EFSA concluded in 2018 that supplement intakes of 800 mg EGCG a day or more raised liver enzymes; taking concentrated extract as a single dose on an empty stomach increases EGCG exposure. |
| At doses found in typical green tea beverages and low-dose extracts, the risk is not significant — the concern is concentrated extract supplements specifically. | Brewed green tea is generally considered safe, though rare liver injury has been reported; the main concern is concentrated extract supplements. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Green Tea](https://pubmed.ncbi.nlm.nih.gov/31643260/) · Green tea extract, and more rarely large amounts of tea, implicated in acute liver injury including liver failure, transplantation or death.
- **B** · clinical_outcomes · [Scientific opinion on the safety of green tea catechins (EFSA Journal 2018;16(4):5239)](https://doi.org/10.2903/j.efsa.2018.5239) · Trials show significant transaminase rises at >=800 mg EGCG/day as supplements; infusions generally safe but rare idiosyncratic liver injury reported.
- **A** · clinical_outcomes, mechanism_of_harm · [United States Pharmacopeia (USP) comprehensive review of the hepatotoxicity of green tea extracts](https://pubmed.ncbi.nlm.nih.gov/32140423/) · Fasting bolus dosing raises EGCG bioavailability; case reports at 140 to ~1000 mg EGCG/day; USP label: take with food, avoid with liver problems.
- **Flag for Sean:** Possible under-warning: safety_warning says 'particularly above 800 mg EGCG per day', but liver-injury case reports start near 140 mg/day; 800 mg is the trial enzyme-rise level, not a safe floor. Any change to the Q24 800 mg threshold is Sean's decision.

## RISK_KAVA (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| has been associated with over 100 documented cases of severe liver injury globally, including hepatitis, cirrhosis, and liver failure requiring transplantation. | has been linked to dozens of reported cases of liver injury worldwide (36 in one 2003 German series), including hepatitis, liver failure requiring transplantation, and deaths. |
| The mechanism may involve kavalactone metabolites (pipermethystine) or CYP2D6/CYP3A4 inhibition causing drug interactions. | The mechanism is not established; proposed causes include reactive kavalactone metabolites, other kava constituents and contaminated raw material. |
| At-risk populations include people with liver disease or those taking hepatotoxic medications. | Reported risk factors include high doses, prolonged use, and use with other drugs or supplements. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Hepatitis induced by Kava (Piper methysticum rhizoma)](https://pubmed.ncbi.nlm.nih.gov/12821045/) · Hepatic necrosis or cholestatic hepatitis; 9 fulminant failures, 8 liver transplants, 3 deaths; others recovered after stopping kava.
- **B** · clinical_outcomes · [Hepatic toxicity possibly associated with kava-containing products--United States, Germany, and Switzerland, 1999-2002](https://pubmed.ncbi.nlm.nih.gov/12500906/) · 11 kava users had liver failure and underwent liver transplantation; describes the FDA March 2002 advisory.
- **B** · clinical_outcomes · [Kava Kava](https://pubmed.ncbi.nlm.nih.gov/31643949/) · Products labeled as kava are linked to clinically apparent acute liver injury that can be severe and even fatal.
- **C** · clinical_outcomes · [Kava hepatotoxicity--a clinical review](https://pubmed.ncbi.nlm.nih.gov/20720265/) · Causality highly probable/probable/possible in 14; risk factors were overdose, prolonged treatment and comedication; raw-material quality suspected.
- **C** · mechanism_of_harm · [Constituents in kava extracts potentially involved in hepatotoxicity: a review](https://pubmed.ncbi.nlm.nih.gov/21506562/) · Mechanism not established; enzyme-inhibition results ambiguous; reactive kavalactone metabolites shown in vitro and in vivo.
- **Flag for Sean:** safety_warning says 'over 100 cases of severe liver injury'; the largest series found has 36.

## RISK_YOHIMBE (high_risk)
| Before (removed or reworded) | Final claim |
|---|---|
| FDA has received adverse event reports of anxiety, hypertension, tachycardia, and cardiac arrhythmia from yohimbe supplements. At doses found in supplements, yohimbine can trigger dangerous blood pressure spikes in individuals with hypertension or cardiovascular disease. Drug interactions include dangerous potentiation with antidepressants, antihypertensives, and stimulants. | Poison-center reports of yohimbine products include rapid heart rate, anxiety and high blood pressure, and NIH's NCCIH links yohimbine to irregular heartbeat, blood pressure problems, heart attacks and seizures; toxicity is dose-dependent. It should not be used with MAO inhibitor or tricyclic antidepressants. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Adverse drug events associated with yohimbine-containing products: a retrospective review of the California Poison Control System reported cases](https://pubmed.ncbi.nlm.nih.gov/20442348/) · GI distress 46%, tachycardia 43%, anxiety/agitation 33%, hypertension 25%; more severe outcomes than average exposures (OR 5.81).
- **B** · clinical_outcomes · [NCCIH: Yohimbe (Usage and Safety)](https://www.nccih.nih.gov/health/yohimbe) · Yohimbine associated with irregular heartbeat, blood pressure problems, heart attacks and seizures; do not use with MAO inhibitor or tricyclic antidepressants.
- **C** · clinical_outcomes · [Yohimbine use for physical enhancement and its potential toxicity](https://pubmed.ncbi.nlm.nih.gov/22432773/) · In excess doses, yohimbine typically causes agitation, anxiety, hypertension and tachycardia; toxicity is dose-dependent.
- **C** · mechanism_of_harm · [Herb-drug interactions](https://pubmed.ncbi.nlm.nih.gov/10675182/) · Lists increased risk of hypertension when tricyclic antidepressants are combined with yohimbine.
- **Flag for Sean:** Aliases rauwolscine and corynanthine are distinct stereoisomers. BfArM restriction in the reason is unsourced (regulatory).

## SARM_ANDARINE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| At doses used in supplements, it has caused reversible visual disturbances — yellow-tinted vision and difficulty adapting to light and dark — as well as androgenic suppression of testosterone. | Its safety in people has not been established, and products sold online as SARMs often contain other or undeclared drugs. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Chemical Composition and Labeling of Substances Marketed as Selective Androgen Receptor Modulators and Sold via the Internet](https://pubmed.ncbi.nlm.nih.gov/29183075/) · Only 23/44 contained a SARM (ostarine, LGD-4033 or andarine); 17 contained another unapproved drug; SARMs are not FDA-approved.
- **Flag for Sean:** safety_warning says 'linked to vision disturbances and hormonal suppression'; no peer-reviewed source found.

## SARM_CARDARINE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Clinical trials were halted in 2007 after it caused rapid multi-tissue carcinogenesis in animal studies at doses resembling those used in supplements. | Its developer stopped research after rodent studies linked it to widespread tumour development; in mice it enlarged intestinal polyps and, after a carcinogen, drove rapid metastatic stomach cancer. There are no human data. |

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [Harnessing the benefits of PPARβ/δ agonists](https://pubmed.ncbi.nlm.nih.gov/24184294/) · States GSK discontinued further research after rodent preclinical studies linked GW501516 to widespread tumour development.
- **D** · mechanism_of_harm · [Activation of nuclear hormone receptor peroxisome proliferator-activated receptor-delta accelerates intestinal adenoma growth](https://pubmed.ncbi.nlm.nih.gov/14758356/) · GW501516 significantly increased number and size of intestinal polyps (fivefold more polyps >2 mm).
- **D** · mechanism_of_harm · [Induction of metastatic gastric cancer by peroxisome proliferator-activated receptorδ activation](https://pubmed.ncbi.nlm.nih.gov/21318167/) · GW501516 after carcinogen exposure produced rapid, highly metastatic forestomach squamous cell carcinomas within two months.

## SARM_LIGANDROL (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Case reports have documented drug-induced liver injury and testosterone suppression in otherwise healthy users taking doses typical of supplement use. | Case reports describe drug-induced liver injury in users, and in a controlled trial in healthy young men it lowered testosterone and HDL cholesterol even at 0.1-1 mg a day. |

Sources added (grade · what it supports · finding):
- **D** · clinical_outcomes · [Ligandrol (LGD-4033)-Induced Liver Injury](https://pubmed.ncbi.nlm.nih.gov/32637435/) · Severe DILI; biopsy showed cholestatic hepatitis with mild fibrosis.
- **D** · clinical_outcomes · [Drug-Induced Liver Injury Associated With Alpha Bolic (RAD-140) and Alpha Elite (RAD-140 and LGD-4033)](https://pubmed.ncbi.nlm.nih.gov/33062783/) · Biopsy-supported cholestatic DILI; enzymes normalised ~3 months after stopping.
- **B** · mechanism_of_harm, clinical_outcomes · [The safety, pharmacokinetics, and effects of LGD-4033, a novel nonsteroidal oral, selective androgen receptor modulator, in healthy young men](https://pubmed.ncbi.nlm.nih.gov/22459616/) · Dose-dependent suppression of total testosterone, SHBG, HDL and triglycerides (FSH/free T at 1 mg); reversible; no ALT/AST change.

## SARM_OSTARINE (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Documented risks include testosterone and LH suppression, liver enzyme elevation, and cardiovascular effects. | Case reports describe drug-induced liver injury, and raised liver enzymes were among the most common serious drug-related events in a cancer trial. |

Sources added (grade · what it supports · finding):
- **D** · clinical_outcomes · [Drug-Induced Liver Injury Secondary to Enobosarm: A Selective Androgen Receptor Modulator](https://pubmed.ncbi.nlm.nih.gov/35655632/) · Hepatocellular DILI that improved after stopping the supplement.
- **B** · clinical_outcomes · [Activity and safety of enobosarm, a novel, oral, selective androgen receptor modulator, in androgen receptor-positive, oestrogen receptor-positive, and HER2-negative advanced breast cancer (Study G200802): a randomised, open-label, multicentre, multinational, parallel design, phase 2 trial](https://pubmed.ncbi.nlm.nih.gov/38342115/) · Grade 3-4 drug-related events in 8-16%, most often increased hepatic transaminases (3-4%).
- **Flag for Sean:** safety_warning says it 'failed cancer-cachexia trials' and 'hormonal suppression'; neither is in the sources read (liver injury is).

## SARM_RAD140 (banned)
Claims unchanged; they are supported as written.

Sources added (grade · what it supports · finding):
- **D** · clinical_outcomes · [RAD-140 Drug-Induced Liver Injury](https://pubmed.ncbi.nlm.nih.gov/36561105/) · Cholestatic injury, peak bilirubin 38.5 mg/dL; biopsy consistent with RAD-140 DILI; resolved after stopping.
- **D** · clinical_outcomes · [Idiosyncratic drug-induced liver injury related to use of novel selective androgen receptor modulator RAD140 (Testalone): a case report](https://pubmed.ncbi.nlm.nih.gov/36978171/) · Acute liver injury with jaundice, hospitalized, normalised by 2 months after stopping.
- **B** · clinical_outcomes · [A First-in-Human Phase 1 Study of a Novel Selective Androgen Receptor Modulator (SARM), RAD140, in ER+/HER2- Metastatic Breast Cancer](https://pubmed.ncbi.nlm.nih.gov/34565686/) · Elevated AST 59%, ALT 45%, bilirubin 27%; grade 3/4 AST/ALT rises 22.7%; SHBG fell in 18/18.
- **D** · clinical_outcomes · [Myopericarditis Following Use of Selective Androgen Receptor Modifier "RAD-140"](https://pubmed.ncbi.nlm.nih.gov/39157568/) · Myopericarditis after the first dose.
- **D** · clinical_outcomes · [Acute Myocarditis From the Use of Selective Androgen Receptor Modulator (SARM) RAD-140 (Testolone)](https://pubmed.ncbi.nlm.nih.gov/35233331/) · Possible acute myocarditis after SARM self-use.
- **Flag for Sean:** safety_warning says 'cardiovascular strain, and hormonal suppression'; evidence is two myocarditis case reports and an SHBG fall in a cancer trial.

## SCHED_AMANITA_MUSCARIA (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| In 2024, Diamond Shruumz brand gummies (containing Amanita muscaria extract) triggered a multistate outbreak with 70+ hospitalizations, seizures, loss of consciousness, and deaths. | Eating it can cause confusion, agitation, hallucinations and deep sedation, and seizures have been reported. In 2024, Diamond Shruumz mushroom edibles (mainly chocolate bars) were linked to a multistate outbreak of 180 illnesses, 73 hospitalizations and two deaths; the products contained several psychoactive substances, and FDA found muscimol and ibotenic acid in a raw ingredient reportedly used in some of them. |

Sources added (grade · what it supports · finding):
- **B** · clinical_outcomes · [Severe Illness Associated with Eating Mushroom-Containing Chocolate Products - United States, January-October 2024](https://pubmed.ncbi.nlm.nih.gov/41955162/) · FDA testing found psilocin in some tested products.
- **C** · clinical_outcomes · [Toxicity of muscimol and ibotenic acid containing mushrooms reported to a regional poison control center from 2002-2016](https://pubmed.ncbi.nlm.nih.gov/30073844/) · GI upset, CNS excitation and/or depression; 5 intubated; no seizures and no deaths in this series.
- **C** · clinical_outcomes · [Acute Amanita muscaria Toxicity: A Literature Review and Two Case Reports in Elderly Spouses Following Home Preparation](https://pubmed.ncbi.nlm.nih.gov/41441606/) · Rapid GI symptoms, profound CNS depression and cholinergic features requiring ICU care; both recovered.
- **Flag for Sean:** aliases may include Amanita pantherina, a different species (identity check).

## SCHED_PSILOCIN (banned)
Claims unchanged; they are supported as written.

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [Metabolism of psilocybin and psilocin: clinical and forensic toxicological relevance](https://pubmed.ncbi.nlm.nih.gov/28074670/) · Psilocybin is a prodrug dephosphorylated by alkaline phosphatase to psilocin; both are 5-HT2A agonists or partial agonists.
- **B** · clinical_outcomes · [Severe Illness Associated with Eating Mushroom-Containing Chocolate Products - United States, January-October 2024](https://pubmed.ncbi.nlm.nih.gov/41955162/) · FDA testing found psilocin in some tested products.

## SCHED_PSILOCYBIN (banned)
Claims unchanged; they are supported as written.

Sources added (grade · what it supports · finding):
- **C** · mechanism_of_harm · [Metabolism of psilocybin and psilocin: clinical and forensic toxicological relevance](https://pubmed.ncbi.nlm.nih.gov/28074670/) · Psilocybin is a prodrug dephosphorylated by alkaline phosphatase to psilocin; both are 5-HT2A agonists or partial agonists.
- **A** · mechanism_of_harm · [Pharmacokinetics of Psilocybin: A Systematic Review](https://pubmed.ncbi.nlm.nih.gov/40284409/) · Psilocybin is rapidly dephosphorylated to psilocin; psilocin is metabolized by CYP2D6, CYP3A4 and MAO-A, a potential drug-interaction risk.

## STIM_METHYLHEXANAMINE_ANALOGS (banned)
| Before (removed or reworded) | Final claim |
|---|---|
| Like DMAA, these compounds raise blood pressure and heart rate and have been associated with cardiovascular events. | Their safety in humans has not been studied; DMBA has been found in supplements at up to 214 mg per daily dose. |

Sources added (grade · what it supports · finding):
- **C** · clinical_outcomes · [Four experimental stimulants found in sports and weight loss supplements: 2-amino-6-methylheptane (octodrine), 1,4-dimethylamylamine (1,4-DMAA), 1,3-dimethylamylamine (1,3-DMAA) and 1,3-dimethylbutylamine (1,3-DMBA)](https://pubmed.ncbi.nlm.nih.gov/29115866/) · Octodrine found at ~72 mg/serving, over twice the largest former pharmaceutical dose; safety of 1,4-DMAA and 1,3-DMBA in humans unknown.
- **C** · clinical_outcomes · [Identification and quantification of 1,3-dimethylbutylamine (DMBA) from Camellia sinensis tea leaves and dietary supplements](https://pubmed.ncbi.nlm.nih.gov/26209774/) · DMBA, a CNS stimulant homologue of DMAA, has been identified in multiple dietary supplements, sometimes labelled as a tea constituent.
- **C** · clinical_outcomes · [Nine prohibited stimulants found in sports and weight loss supplements: deterenol, phenpromethamine (Vonedrine), oxilofrine, octodrine, beta-methylphenylethylamine (BMPEA), 1,3-dimethylamylamine (1,3-DMAA), 1,4-dimethylamylamine (1,4-DMAA), 1,3-dimethylbutylamine (1,3-DMBA) and higenamine](https://pubmed.ncbi.nlm.nih.gov/33755516/) · Found up to 4 experimental stimulants per product, incl. octodrine 18-73 mg, BMPEA up to 92 mg, higenamine 48 mg per serving; safety unknown.
- **Flag for Sean:** safety_warning says 'Linked to the same cardiovascular risks as DMAA'; that is class transfer with no analog data.

## Flags for Sean (safety copy, identity, policy)

- **ADD_HORDENINE**: safety_warning says 'drug-strength doses' and 'blood-pressure elevation and cardiovascular strain'; evidence is animal-only (also Q58 Cat 3).
- **BANNED_7_HYDROXYMITRAGYNINE**: safety_warning says 'estimated around 13 times morphine potency'; no source states 13x (only 'more potent than morphine' in animals).
- **BANNED_ADD_PHTHALATES**: safety_warning says phthalates are packaging contaminants and 'presence reflects contamination rather than an added ingredient'; DEP/DBP are declared coating excipients in some products. Matching: check that 'phthalate' does not match HPMCP/CAP/PVAP.
- **BANNED_ADD_SYNTHETIC_FOOD_ACIDS**: No defensible harm basis found for this watchlist entry; safety_warning cites 'labeling and tolerability concerns'. Keep or retire is Sean's decision.
- **BANNED_BMPEA**: safety_warning says 'Linked to cardiovascular risk'; evidence is a rat blood-pressure study only.
- **BANNED_DMHA**: safety_warning says 'associated with elevated blood pressure and cardiovascular risk'; only user-reported side effects exist. Aliases 'valerophenone' (a ketone) and '2-aminoheptane' (tuaminoheptane) are different compounds.
- **BANNED_EPHEDRA**: safety_warning says 'heart attacks' and 'many in otherwise healthy users'; neither is in the sources read (strokes, seizures and deaths are). Alias 'sida cordifolia' is a different plant.
- **BANNED_FASORACETAM**: safety_warning and one-liner say 'failed clinical trials' / 'Failed investigational drug'; posted results show no clear advantage over placebo, with no published analysis.
- **BANNED_FDC_RED_2_AMARANTH**: No source found for a specific tumor type; the 1976 FDA action (already cited) is the basis for 'cancer concerns'. EFSA 2010 set an ADI of 0.15 mg/kg bw/day and reports no carcinogenicity finding in its abstract.
- **BANNED_HIGENAMINE**: safety_warning says 'linked to cardiovascular stimulation risk'; oral trials found no heart-rate or blood-pressure change.
- **BANNED_IBOTENIC_ACID**: safety_warning says it 'can cause excitotoxic brain injury'; that is shown only by direct brain injection in animals.
- **BANNED_IGF1**: safety_warning says 'acromegaly risk'; no source found, and all harm data are for injected mecasermin.
- **BANNED_S23**: safety_warning says 'testicular suppression, liver strain, and cardiovascular risk'; only rat hormone/sperm data exist.
- **BANNED_SR9009**: safety_warning says 'Poor oral bioavailability'; no pharmacokinetic source was found.
- **HIGH_RISK_CHAPARRAL**: safety_warning says 'at least 18 reported cases of severe liver injury'; the source reports 13 of 18 FDA reports with liver toxicity.
- **HM_LEAD**: safety_warning says 'no safe blood level' and 'kidney ... harm'; the sources read show deficits below 7.5 µg/dL without stating no safe level, and no kidney source was read. 40020868 is Clean Label Project funded (graded C).
- **NOOTROPIC_BROMANTANE**: safety_warning says 'FDA has stated is not a lawful supplement ingredient'; no FDA document naming bromantane was found (Q58 Cat 1).
- **NOOTROPIC_FLMODAFINIL**: aliases may include mono-fluoro 'fluoromodafinil'/'4-fluoromodafinil', a different compound (identity check).
- **RECALLED_HYDROXYCUT**: safety_warning says '23 reports of severe liver injury and one death'; the 23 is FDA's 2009 figure, not verified here (Hydroxycut recall is Q58 Cat 4).
- **RECALLED_JACK3D**: safety_warning says Jack3d's DMAA 'was linked to two deaths'; the case report names DMAA-containing supplements, not Jack3d.
- **RECALLED_OXYELITE_PRO**: safety_warning says '97 cases, three liver transplants, and one death'; no source gives 97.
- **RISK_BITTER_ORANGE**: safety_warning says 'ephedrine-like cardiovascular effects'; that equivalence is disputed in the literature. Alias 'citrus bioflavonoids' may not contain synephrine.
- **RISK_GERMANIUM**: safety_warning says 'Inorganic germanium compounds'; the case reports include organic forms (Ge-132, germanium lactate-citrate).
- **RISK_GREEN_TEA_EXTRACT_HIGH**: Possible under-warning: safety_warning says 'particularly above 800 mg EGCG per day', but liver-injury case reports start near 140 mg/day; 800 mg is the trial enzyme-rise level, not a safe floor. Any change to the Q24 800 mg threshold is Sean's decision.
- **RISK_KAVA**: safety_warning says 'over 100 cases of severe liver injury'; the largest series found has 36.
- **RISK_YOHIMBE**: Aliases rauwolscine and corynanthine are distinct stereoisomers. BfArM restriction in the reason is unsourced (regulatory).
- **SARM_ANDARINE**: safety_warning says 'linked to vision disturbances and hormonal suppression'; no peer-reviewed source found.
- **SARM_OSTARINE**: safety_warning says it 'failed cancer-cachexia trials' and 'hormonal suppression'; neither is in the sources read (liver injury is).
- **SARM_RAD140**: safety_warning says 'cardiovascular strain, and hormonal suppression'; evidence is two myocarditis case reports and an SHBG fall in a cancer trial.
- **SCHED_AMANITA_MUSCARIA**: aliases may include Amanita pantherina, a different species (identity check).
- **STIM_METHYLHEXANAMINE_ANALOGS**: safety_warning says 'Linked to the same cardiovascular risks as DMAA'; that is class transfer with no analog data.
