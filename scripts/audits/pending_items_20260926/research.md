# Pending-item corrections, 2026-09-26: evidence receipts

Each correction below was checked against a live primary source on 2026-09-26 before editing.
Agent-verified, not clinician-reviewed. Thresholds, severities and categories were not changed.

## IQM cascara_sagrada: RxNorm anchor
- RxNav `rxcui/66869/properties`: name "cascara sagrada", synonym "cascara", tty IN; allProperties:
  ATC A06AB07, SNOMEDCT 23888001, DrugBank DB15478.
- RxNav `rxcui/1350209/properties`: "Frangula purshiana bark extract", synonym "Cascara sagrada bark
  extract", tty IN. `rxcui.json?name=cascara sagrada` -> 66869.
- The entry said "No RxNorm concept found via GSRS lookup". RxNorm has the ingredient concept 66869.

## RULE_IQM_CHONDROITIN: INR figures and dose-floor attribution
- PMID 18363538 (Knudsen JF, Sokol GH. Pharmacotherapy 2008;28(4):540-8), abstract: on glucosamine
  500 mg / chondroitin 400 mg twice a day the INR held at 2.5-3.2; after increasing to glucosamine
  1500 mg and chondroitin 1200 mg twice/day "his INR previous to this change was 2.3. Approximately
  3 weeks later, his INR increased to 3.9."
- PMID 14986566 (Rozenfeld V et al. Am J Health Syst Pharm 2004;61(3):306-7) is a letter with no
  PubMed abstract; the publisher page returned a bot check, so its figures could not be read.
- The anticoagulant copy said "INR increase from 2.6 to 4.1", a figure neither readable source states.
  Two dose-floor rationales credited PMID 14986566 with "1200 mg BID", which is Knudsen's figure.
- Not changed (clinical threshold, for Sean): the floor is 1200 mg per day while the source escalated
  to 1200 mg twice a day (2400 mg per day).

## RULE_IQM_BLACK_SEED_OIL_DIABETES: dose-floor rationale
- PMID 27512971 (Sahebkar A et al. J Hypertens 2016;34(11):2127-35): meta-analysis of 11 RCTs
  (860 people) on blood pressure only; SBP -3.26 mmHg, DBP -2.80 mmHg; "No association was observed
  between SBP lowering and time on treatment, N. sativa dosage or type of N. sativa."
- The rationale said the meta-analysis shows "(and glucose/lipids)" lowering. It reports neither.
- Not changed (for Sean): the "~2 g oil / 1.5 g powder per day" basis is not in the abstract, and the
  abstract reports no dose association.

## RULE_INGREDIENT_EVENING_PRIMROSE_OIL: dose-floor rationale
- PMID 19783511 (Riaz A, Khan RA, Ahmed SP. Pak J Pharm Sci 2009;22(4):355-9): healthy rabbits given
  90, 180 or 360 microlitres/kg for 30 and 60 days; all coagulation assays except fibrinogen time
  increased and platelet count fell.
- The rationale said the study shows increased bleeding time "at supplemental GLA doses (~300 mg GLA ~
  3 g oil)". It reports no human dose and no bleeding time. The 3 g oil floor is the clinical-team
  threshold recorded on the rule's dose_thresholds note (sign-off 2026-04-24).

## IQM miroestrol: structural class
- PubChem CID 165001 Miroestrol: C20H22O6, IUPAC
  (1S,3R,13S,16R,17R,18S)-7,13,16,17-tetrahydroxy-2,2-dimethyl-10-oxapentacyclo[14.2.1.03,12.04,9.013,18]nonadeca-4(9),5,7,11-tetraen-14-one.
- PubChem "coumestan": CID 638309, C15H8O3, [1]benzofuro[3,2-c]chromen-6-one. Miroestrol does not
  have the coumestan skeleton, so "coumestan constituent" was wrong.
- GSRS `substances/search?q=miroestrol`: 0 results. The entry's gsrs block is hand-authored (for Sean).

## DSI_WAR_GARLIC: wrong-topic citation
- PMID 10594976 (Ankri S, Mirelman D. Microbes Infect 1999): "Antimicrobial properties of allicin
  from garlic." Right ingredient, wrong topic for a warfarin bleeding interaction.
- NCCIH garlic page (https://www.nccih.nih.gov/health/garlic, read 2026-09-26): "Taking garlic
  supplements may increase the risk of bleeding ... medicines, such as anticoagulants or aspirin".
  That source stays and supports the pair.
- Not changed (uncertain): the mechanism's "Some evidence of mild CYP2C9 inhibition" has no cited source.

## DEP_BETABLOCKERS_COQ10: source label
- PMID 12392188 (Cocco T et al. J Bioenerg Biomembr 2002 Aug): "The antihypertensive drug carvedilol
  inhibits the activity of mitochondrial NADH-ubiquinone oxidoreductase."
- The source label named a different paper (Folkers K, lovastatin, PNAS 1990) while its URL pointed to
  12392188. The record is already suppressed (citation_review_status needs_revision).

## D10 SARM regulatory terminology (Sean's decision 2026-09-26: a warning letter is not a ban)
- FDA In Brief 2017-10-31 "FDA warns against using SARMs in body-building products" (live URL 404; Wayback
  fda.gov/NewsEvents/Newsroom/FDAInBrief/ucm583021.htm, 2017-11-01): products "are not dietary supplements. The
  products are unapproved drugs". Names no compound; no "ban".
- Infantry Labs 535333 (2017-10-23, read live): "The Officer (MK-2866)" and "Lieutenant (LGD-4033)" labeled as dietary
  supplements; excluded under 201(ff)(3)(B)(ii); unapproved new drugs and misbranded. No "ban". Panther 535341 and
  IronMag 494623 (2017-10-22/23) name ostarine/LGD-4033 only (agent-read).
- Dynamic Technical Formulations 535717 (2017-12-13): "your Tri-ton product contains ostarine and andarine".
- Umbrella 612037 (2021-05-18): "GW-501516 Cardarine" among research-labeled products marketed as SARMs.
- Prime Sports Nutrition 719433 (2025-12-12): "S-23"; research-only labeling; unapproved new drugs (505(a)).
- TITAN SARMS 719645 (CDER, 2025-12-12, read live): LGD-4033, RAD-140, S-4, YK-11; "unapproved new drugs under section
  505(a)"; labeled "Research-grade compound"; contains none of "dietary supplement", "recall", "adulterated",
  "misbranded", "ban". openFDA drug/food recalls: no Titan entry.
- openFDA recalls: D-0800-2020 (initiated 2019-08-24) "Entropic Labs SARM RAD-140" - "Marketed Without An Approved
  NDA/ANDA"; D-0910-2016 (2016-03-31) "LGD-Xtreme (ligandrol LGD-4033)" - "Contains an unapproved drug".
- FDA page "Certain bodybuilding products put consumers at risk..." (content current 2025-12-02): YK-11 confirmed in a
  product marketed as a supplement; "not dietary supplements... unapproved drugs".
- SR9009: no fda.gov document found (letters, openFDA recalls, Import Alert 66-41).
- No statute: SARMs Control Act S.2742 (2018) and S.2895 (2019) were referred to committee and not enacted (govinfo).
- Not changed (unverified): the DoD "Prohibited for military personnel" rows on ostarine, ligandrol and RAD140
  (source typed state_statute); opss.org shows the list but not per-compound entries.
- Corpus: 0 products in the 2026-09-22 cleaned corpus name any SARM, MK-677 or Titan, so no verdict moves today.

## D5 senna pregnancy (Sean's decision: pregnancy-profile warning from the exact source wording)
- EU herbal monograph Senna alexandrina folium Rev. 1 (EMA/HMPC/625849/2015, 2018; pdftotext): 4.3 "Pregnancy and
  lactation (see section 4.6 and 5.3)"; 4.6 "The use during pregnancy is contraindicated because experimental data
  concerning a genotoxic risk of several anthranoids, e.g. emodin and aloe-emodin"; lactation contraindicated (rhein in
  milk). Fructus Rev. 1 identical; the 2022 addendum (EMA/HMPC/18310/2022) kept it.
- UKTIS "Treatment of constipation in pregnancy" (v4, March 2026, read live): "The limited available data regarding the
  use of docusate sodium and senna in pregnancy suggest no increased risk of congenital malformations but are
  insufficient to conclusively state that there is no increase in risk"; stimulants after bulk-forming and osmotic.
- LactMed NBK501349 (PMID 30000408): "Usual doses of senna are acceptable to use during breastfeeding."
- NBK547922 is LiverTox Senna (liver injury), not a pregnancy source.
- Result: pregnancy caution -> avoid (not contraindicated, given the UK human data); lactation stays caution. Same EU
  wording also covers cascara (avoid), frangula, rhubarb and Aloe (contraindicated); frangula and rhubarb have no rule.

## D8 unsupported dose floors (Sean's decision: remove, never substitute a number)
- PMID 18363538 (Knudsen & Sokol 2008, efetch): after glucosamine 750 mg / chondroitin 600 mg per day "a repeat INR done
  16 days later was 4.7"; MedWatch: "20 reports of glucosamine or glucosamine-chondroitin sulfate use with warfarin";
  the authors attribute the interaction to glucosamine and say "More information is necessary". No threshold.
- PMID 27512971 (Sahebkar 2016): "No association was observed between SBP lowering and ... N. sativa dosage".
- PMID 40210172 (Karimi 2025, 16 RCTs in T2D): FBG -21.43 mg/dL pooled; HbA1c, HOMA and LDL lowered "in higher doses
  (>1 g/day)" subgroups. Sets no 2000 mg threshold. No source gives a black seed warfarin dose.
- Corpus (2026-09-22 enriched): chondroitin rule on 130 products, floor suppressed it on 43; black seed on 15, floor
  suppressed it on 14. These warnings now show to profile-matched users; severities unchanged; no verdict inputs.
