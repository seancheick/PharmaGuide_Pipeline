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
