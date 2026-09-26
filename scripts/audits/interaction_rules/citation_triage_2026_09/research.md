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
