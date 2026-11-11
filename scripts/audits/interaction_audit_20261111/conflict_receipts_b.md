# Batch B: severity conflict source receipts (2026-11-11)

Worktree: /Users/seancheick/worktrees/dsld-interaction-baseline (read-only).
Raw fetched sources: /private/tmp/claude-501/-Users-seancheick-Downloads-dsld-clean/3bef6da5-f891-47f1-85be-767d3f9063d6/scratchpad/conflicts/src/

Sources shared across entries:
- Warfarin label, used as the drug-label authority: JANTOVEN (warfarin sodium), Upsher-Smith. DailyMed setid 19a69a72-ac5d-45d5-a94d-a5aaecbe4730, sections 5.1, 7.1, 7.5, 17, and 4 (Contraindications). Section 4 lists pregnancy and does not mention botanicals.
- Combined oral contraceptive label: YAZ (drospirenone/ethinyl estradiol), Bayer. DailyMed setid 065f33e4-b587-4e66-b896-ca9ab7b7c876.
- Not readable (HTTP 403, tried once): ODS fact sheets at https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/ and https://ods.od.nih.gov/factsheets/CoQ10-HealthProfessional/.
- Dead citation: MHRA https://www.mhra.gov.uk/home/groups/pl-p/documents/websiteresources/con019838.pdf returns HTTP 404. A Wayback `id_` capture also returned 404.

---

## DSI_NSAID_FISHOIL vs RULE_INGREDIENT_FISH_OIL/drug_class_rules[2]

- Severities: pair Moderate → **caution** (evidence_basis mechanism_inferred, clinical_confidence low). Rule **monitor** (evidence_level theoretical).
- Scope: the same class (NSAIDs) and the same subject (fish oil / EPA+DHA). Neither record has a dose gate. The pair has `applies_to: dose_dependent` with a null threshold.
- Action difference: the rule says "Monitor for GI symptoms… Take NSAIDs with food". The pair's management says food "does not establish protection from bleeding". The two actions contradict each other on the food advice.
- Sources:
  - ODS Omega-3 HP fact sheet (cited by both records): **not readable** (403).
  - NCCIH "Omega-3 supplements: in depth" (https://www.nccih.nih.gov/health/omega3-supplements-in-depth), cited by the rule: read in full. The page never mentions NSAIDs, bleeding, platelets, anticoagulants or warfarin. Its only "interact"/"medication" hits are about antidepressant, ADHD and rheumatoid arthritis treatment. **It supports neither record.** The citation is not off-topic for fish oil, but it does not support the NSAID claim.
- Sources support: **insufficient source**. No readable cited source addresses fish oil plus NSAIDs. The rule's "Take NSAIDs with food" has no source behind it.
- Proposed resolution: align on **monitor**, the lower and theoretical level. Both records already state that the interaction is not established, and "caution" is not backed by any readable source. Remove the unsourced "Take NSAIDs with food" from the rule action. Then re-verify against the ODS fact sheet by another route (browser), since it could not be read here.
- Confidence: **low** (the key source was unreadable).
- Ghost/dead: none dead. The NCCIH omega-3 page is a non-supporting citation for this sub-rule.

---

## DSI_OC_SJW vs RULE_INGREDIENT_ST_JOHNS_WORT/drug_class_rules[7]

- Severities: pair Major → **avoid**. Rule **contraindicated**.
- Scope: both cover oral contraceptives as a whole class (pair `applies_to: whole_class`; rule drug_class oral_contraceptives). The rule's mechanism names ethinyl estradiol specifically. The pair names both the estrogen and progestin components. Neither has a dose gate.
- Sources:
  - YAZ label, DailyMed 065f33e4-…, drug interactions: "Counsel women to use an alternative method of contraception or a back-up method when enzyme inducers are used with COCs, and to continue back-up contraception for 28 days". The same section lists "products containing St. John's wort" as possibly decreasing effectiveness. → **Supports avoid with a backup method.** It does not list SJW as a contraindication. **Contradicts "contraindicated"**, but matches the rule's *action text* ("use additional non-hormonal contraception or discontinue").
  - NCCIH SJW (https://www.nccih.nih.gov/health/st-johns-wort): "St. John's wort can weaken the effects of many medicines, including… Birth control pills". → It supports that the interaction exists. It does not grade severity.
  - PMID 27444983 (CDC/FDA systematic review): "Limited evidence showing increased risk of ovulation and breakthrough bleeding raises concern for decreased contraceptive efficacy… weak to moderate induction". → **Supports avoid/caution-level concern and contradicts contraindicated.** The review also notes that a low-hypericin product showed no PK change, so the effect varies by preparation.
  - FDA DDI table page (cited by the pair): readable, but the HTML page text has no "St. John" or "contracept" match, so it **does not support** the pair as fetched. The tables may sit in linked sub-pages that were not fetched.
- Sources support: **avoid** (the label instruction is to use a backup or alternative method, not an absolute contraindication).
- Proposed resolution: set the rule to **avoid**, matching the pair. Keep the rule's action text, which already mirrors the label. The label's "alternative or back-up method… 28 days" instruction outranks the mechanism papers and is not a contraindication.
- Confidence: **high**.
- Ghost/dead: the FDA DDI table URL does not mention SJW or contraceptives on the fetched page, so it is a weak or unsupportive citation for this pair. The old NCCIH `ataglance.htm` URL redirects to the current SJW page and works.

---

## DSI_SEDATIVES_ASHWAGANDHA vs RULE_IQM_ASHWAGANDHA/drug_class_rules[0]

- Severities: pair Minor → **monitor** (display_layer background, clinical_confidence medium). Rule **caution** (evidence_level "probable").
- Scope: same class (sedatives), whole class, no dose gate in either record. The rule's mechanism claims GABAergic additive CNS depression.
- Sources:
  - NCCIH ashwagandha (https://www.nccih.nih.gov/health/ashwagandha), cited by the pair: "There is evidence that ashwagandha might interact with some medications, including… sedatives, anti-seizure medications…". → It supports a possible interaction with no severity or magnitude. That **fits monitor** and does not establish "probable"/caution.
  - PMID 38003702 (Wiciński 2023, "Can Ashwagandha Benefit the Endocrine System?"), cited by the rule: the abstract and the PMC full text (BioC) have 0 hits for "sedat", "benzodiaz", "drug interaction" and "CNS depress". The only relevant line is in-vitro: "W. somnifera can exhibit GABA-mimetic action due to its interactions with GABA type A receptors" (in the context of GnRH secretion). → **It does not support** a sedative drug interaction, the "probable" evidence level, or caution.
- Sources support: **monitor** (an unquantified "might interact" from NCCIH). The rule's only source is an endocrine review with no interaction content.
- Proposed resolution: set the rule to **monitor**, matching the pair. Downgrade the rule's evidence_level from "probable", and replace or add NCCIH as its source. The single cited source cannot carry caution/probable.
- Confidence: **medium**.
- Ghost/dead: **PMID 38003702 is a near-ghost for this claim.** It is a real ashwagandha paper, but about endocrine effects, and it contains no sedative-interaction content.

---

## DSI_WAR_COQ10 vs RULE_IQM_COQ10_HEART_DISEASE_STATINS/drug_class_rules[0]

- Severities: pair Moderate → **caution**. Rule **monitor** (theoretical).
- Scope: the pair covers warfarin only (RXCUI 11289) and is `applies_to: dose_dependent` without a threshold. The rule covers the whole anticoagulants class, so it also fires for DOACs, which no source here addresses. Its action text is warfarin-specific. Its mechanism cites a 100 mg/day RCT (24 stable warfarin users, no INR effect) that is not in its sources list.
- Sources:
  - Warfarin label (JANTOVEN, §7.5): "some botanicals may decrease the effects of JANTOVEN (e.g., co-enzyme Q 10, St. John's wort, ginseng)". It also says "More frequent INR monitoring should be performed when starting or stopping botanicals". → **Supports a monitor-level instruction** (INR monitoring at start or stop). Both records' actions say to monitor INR or ask about monitoring.
  - NCCIH CoQ10 (https://www.nccih.nih.gov/health/coenzyme-q10; the pair's old `nccih.nih.gov/health/coq10` redirects here): "CoQ10 may interact with the anticoagulant (blood thinner) warfarin". → It supports a possible interaction and does not grade it.
  - ODS CoQ10 HP fact sheet (cited by the pair): **not readable** (403).
- Sources support: an INR-monitoring instruction on starting or stopping, which **fits monitor**. No readable source supports a higher grade. The pair's claim "Case reports describe decreased INR" is plausible but was not verifiable from the readable sources, because ODS could not be read.
- Proposed resolution: **monitor** for warfarin, which is the rule's level. The label's instruction is more frequent INR monitoring, not avoidance. Separately flag that the rule's class scope is wider than the warfarin-only evidence, and that its RCT claim needs its PMID added to sources.
- Confidence: **medium**.
- Ghost/dead: none dead. The rule's mechanism cites an RCT that is not present in its `sources`, so it is an unsourced claim.

---

## DSI_WAR_CRANBERRY vs RULE_INGREDIENT_CRANBERRY/drug_class_rules[0]

- Severities: pair Moderate → **caution**. Rule **monitor** (theoretical).
- Scope: the pair covers warfarin only, all preparations, with no dose gate, and asserts CYP2C9 inhibition and fatal-hemorrhage case reports. The rule covers the whole anticoagulants class, but its action names warfarin and states a ≥1 L juice/day or extract threshold in text only (profile_gate dose is null). The rule's mechanism explicitly says CYP2C9 inhibition is not established.
- Sources:
  - MHRA PDF (the pair's only source): **dead** (404; Wayback 404).
  - NCCIH cranberry (https://www.nccih.nih.gov/health/cranberry), cited by the rule: "There is conflicting evidence about whether cranberry interacts with the anticoagulant (blood thinner) warfarin. If you take warfarin… talk with your health care provider". → **It supports monitor** and contradicts an established-interaction framing. It does not support the rule's "≥1 L/day" threshold.
  - Warfarin label (JANTOVEN): cranberry is **not named** anywhere in the label. The generic §7.5 instruction "More frequent INR monitoring should be performed when starting or stopping botanicals" applies. → It supports monitor-level handling.
- Sources support: **monitor**. The pair's CYP2C9 mechanism, its fatal-hemorrhage claim and its caution level have no readable source.
- Proposed resolution: set the pair to **monitor**, matching the rule. Re-source or remove the pair's CYP2C9 and fatal-hemorrhage claims, because its only citation is dead. Remove the rule's "≥1 L/day" figure unless a source for it is added.
- Confidence: **medium** (direction is clear; the original MHRA wording could not be checked).
- Ghost/dead: **the MHRA con019838.pdf is a dead citation, and it is the pair's sole source.**

---

## DSI_WAR_SJW vs RULE_INGREDIENT_ST_JOHNS_WORT/drug_class_rules[1]

- Severities: pair Major → **avoid**. Rule **contraindicated**.
- Scope: the pair covers warfarin only. The rule covers the whole anticoagulants class, but its action text names "warfarin or other vitamin-K antagonists". The SJW mechanism (induction) is not shown for DOACs by any source cited here. Neither record has a dose gate.
- Sources:
  - Warfarin label (JANTOVEN, §7.5): "some botanicals may decrease the effects of JANTOVEN (e.g., co-enzyme Q 10, St. John's wort, ginseng)". It also says "More frequent INR monitoring should be performed when starting or stopping botanicals". In §17 it advises patients not to take herbal products "except on advice of your physician". The label lists SJW under CYP450 interactions. §4 Contraindications does not mention SJW. → **It contradicts contraindicated.** It supports avoid-without-clinician-review plus INR monitoring.
  - PMID 15089812 (Jiang 2004 RCT, rule): "St John's wort significantly induced the apparent clearance of both S-warfarin and R-warfarin… significant reduction in the pharmacological effect". INR AUC ratio was 0.79. → It supports a clinically meaningful interaction and does not grade it.
  - PMID 15260917 (Zhou 2004 review, pair): "St John's wort decreased the blood concentrations of… phenprocoumon… and warfarin". → It supports the interaction.
  - PMID 15049433 (Izzo 2004 review, pair): "SJW has been shown to lower the plasma concentration (and/or the pharmacological effect) of… warfarin, phenprocoumon". → It supports the interaction.
  - NCCIH SJW: "St. John's wort can weaken the effects of many medicines… Warfarin, an anticoagulant (blood thinner)". → It supports the interaction.
- Sources support: **avoid** (the pair's level and management). The label's instruction is clinician-directed use with INR monitoring, which is short of a contraindication.
- Proposed resolution: set the rule to **avoid**, matching the pair. Soften the rule's action from "Do not combine" toward the pair's "Avoid adding… without the anticoagulation clinician reviewing it" plus INR monitoring. Narrow the rule's scope to vitamin-K antagonists, or flag it, because no source covers DOACs.
- Confidence: **high**.
- Ghost/dead: none. All three PMIDs are on-topic.
