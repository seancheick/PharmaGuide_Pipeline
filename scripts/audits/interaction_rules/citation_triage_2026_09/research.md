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
