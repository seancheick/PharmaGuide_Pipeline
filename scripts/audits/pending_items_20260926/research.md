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

## RULE_INGREDIENT_GINSENG: anticoagulant dose-threshold citation
- PMID 22137021 (efetch 2026-09-26): "Intensity-modulated radiation therapy with concurrent
  chemotherapy as preoperative treatment for localized gastric adenocarcinoma." No ginseng, no
  warfarin: a ghost reference in `dose_thresholds[anticoagulants].note`.
- PMID 15238367 (Yuan CS et al. Ann Intern Med 2004;141(1):23-7, DOI 10.7326/0003-4819-141-1-200407060-00011,
  efetch 2026-09-26): randomized, double-blind, placebo-controlled; 20 healthy volunteers; American
  ginseng from week 2; "The peak INR statistically significantly decreased after 2 weeks of ginseng
  administration"; INR AUC, peak plasma warfarin and warfarin AUC also reduced. MeSH: Panax,
  Warfarin, International Normalized Ratio.
- Applicability: IQM `ginseng` includes the form "american ginseng (panax quinquefolius)". Panax
  ginseng studies found no warfarin effect (Jiang X et al. Br J Clin Pharmacol 2004;57(5):592-9,
  healthy subjects; Lee YH et al. Int J Cardiol 2010;145(2):275-6, Korean red ginseng after valve
  replacement), as tabulated in Choi S et al. PLoS One 2017 (PMC5552262). The rule's mechanism
  already calls the evidence mixed.
- Species limit, from the article's online correspondence (acpjournals.org page opened by Sean
  2026-09-26): Plotnikoff et al. (21 Jul 2004) note P. quinquefolius data are not applicable to other
  Panax species; Yuan's reply (8 Sep 2004): "We did not extrapolate our data on American ginseng to
  other species" and "Whether Asian ginseng interacts with warfarin remains to be tested." The note
  names American ginseng for that reason; the threshold still gates every IQM ginseng form.
- Dose: the abstract gives none. The publisher page is behind a bot check. A secondary review (EXCLI J
  2014, PMC4464477) reports 0.5 g capsules "at the high end of the recommended dose range", not a daily
  total. No source found supports ">1000 mg"; it is the authored threshold from e0978c2e (2026-04-27
  dose-gating pass). Value and severities unchanged.

## RULE_IQM_NAC_BLEEDING: threshold citation and floors
- PMID 22467323 (efetch 2026-09-26): "Albuminuria, proteinuria, and urinary albumin to protein ratio in
  chronic kidney disease." No NAC: a ghost in `dose_thresholds[anticoagulants].note`.
- PMID 21600014 (efetch 2026-09-26): "Therapeutic potential of N-acetylcysteine as an antiplatelet agent in
  patients with type-2 diabetes." Blood from 13 patients incubated with NAC 10-100 micromolar "at
  concentrations attainable with tolerable oral dosing"; "NAC inhibited thrombin- and ADP-induced platelet
  aggregation in vitro". No oral mg dose stated, so it cannot establish the 600 mg floor or "~100-1000 mg oral".
- PMID 39881835 (Oktar S et al. Sovrem Tekhnologii Med 2024, doi 10.17691/stm2024.16.4.06, efetch
  2026-09-26): patients on NAC 600 mg/day for 7-14 days; D-dimer fell and factor VII rose "but these changes
  were not significant (p=0.069 and p=0.062)"; "Other coagulation and hemogram values did not change".
  Platelet aggregation not measured.
- No source found for a 1200 mg cut-off; it stays the authored threshold (escalation only).
- Decision applied: Sean, D8 (2026-09-26), remove a floor its source does not establish. Floors removed on
  bleeding_disorders and anticoagulants; both now presence, severity monitor unchanged.

## RULE_IQM_RESVERATROL_BLEEDING: threshold citation
- PMID 27040449 (efetch 2026-09-26): "Effects of angiopoietin-like protein 3 deficiency on postprandial lipid
  and lipoprotein metabolism." No resveratrol: a ghost in `dose_thresholds[anticoagulants].note`.
- PMID 26947597 (Chiba T et al. J Atheroscler Thromb 2016, doi 10.5551/jat.31765, efetch 2026-09-26): mice fed
  0.005-0.5% trans-resveratrol; "0.5% trans-resveratrol enhanced the anticoagulant activity of warfarin" and
  "The 0.05% trans-resveratrol did not interact with warfarin". This is the study the note already described.
- Also on topic, not added: PMID 32985569 (Huang TY et al. Sci Rep 2020, rats, resveratrol 100 mg/kg raised
  S-warfarin AUC and INR). The note's "animal-only" stays true.

## RULE_IQM_SAW_PALMETTO_LIVER: bleeding floors (D8)
- Floor source PMID 16985705 ("Saw Palmetto Berry as a Treatment for BPH", Rev Urol 2001): BPH efficacy, no
  bleeding content.
- PMID 11489067 (J Intern Med 2001): intraoperative haemorrhage case, bleeding time "normalized few days after he
  stopped the herb"; no dose in the abstract. PMID 20120986: coagulopathy case, no dose.
- PMID 18090773 (Plast Reconstr Surg 2007): 10 volunteers, saw palmetto "at the manufacturer's recommended dose
  for 2 weeks"; "In vivo platelet function was not affected" (PFA-100). mg not stated.
- PMID 15195032 (Minerva Urol Nefrol 2004): 320 mg/day Permixon for at least 8 weeks before TURP; perioperative
  bleeding "significantly lower than in the control one (respectively 124 vs 287 ml)".
- No human source documents a dose for a bleeding or platelet effect. Four floors removed; presence.

## RULE_INGREDIENT_BOSWELLIA: bleeding floors (D8) and a false mechanism sentence
- Floor source PMID 18667054 (Arthritis Res Ther 2008): 5-Loxin 100 or 250 mg/day for knee osteoarthritis;
  efficacy only, no platelet or bleeding outcome.
- Mechanism sources (17945191, 1602379, 8510458) are in vitro; no human platelet or bleeding study states a dose.
- PMID 21274401 (Italian surveillance of natural health products, Evid Based Complement Alternat Med 2011;
  full text PMC3025393, Table 2 "Reports of INR increase", read 2026-09-26): F 73, "Boswellia serrata dry
  extract (D E) 95%, 1500 mg/day; osteoarthritis", warfarin, INR increase, Naranjo "Probable [6]", recovered
  after withdrawal; F 64, "Boswellia serrata DE 95%, 1200 mg/day", warfarin, same outcome; a third
  multi-product case rated "Possible [4]". This contradicts the old "No clinical case reports" sentence.
- Case reports show the event can occur at those doses; they cannot show safety below them, so no floor.
  Three floors removed; presence. evidence_level stays theoretical ("limited direct human evidence").

## RULE_IQM_FEVERFEW_PREGNANCY: anticoagulant floor (D8)
- Floor source PMID 22096324 ("Feverfew (Tanacetum parthenium L.): A systematic review", Pharmacogn Rev 2011):
  abstract has no platelet content and no dose (efetch 2026-09-26).
- Human platelet data: Biggs 1982 (PMID 6125851, Lancet letter, no abstract) as summarised in that review:
  users' platelets aggregated normally to ADP and thrombin, less to serotonin; no dose stated.
- PMID 34434419 (J Med Cases 2021): one woman on "800 mg capsules of feverfew three times per day" with vaginal
  bleeding and altered coagulation tests, Naranjo probable. A single case cannot set a floor.
- Floor removed; presence.

## RULE_INGREDIENT_GINSENG: floors (D8)
- Old floor source PMID 35509826 (Panax ginseng metabolic meta-analysis): doses "ranged from 200 mg to 8 g"; no
  dose-response reported. Its rationale ("kept for hypertensives") was copied onto glucose, surgery and warfarin
  sub-rules.
- Glucose: PMID 8721940 (Sotaniemi EA et al. Diabetes Care 1995, doi 10.2337/diacare.18.10.1373): 36 newly
  diagnosed NIDDM patients, "ginseng (100 or 200 mg) or placebo" for 8 weeks; ginseng "reduced fasting blood
  glucose"; "The 200-mg dose of ginseng improved glycated hemoglobin". Dose split from the full text (publisher
  page behind a bot check) as reported by Derosa G et al. Phytother Res 2022 (PMID 35912631, PMC9804244): "the
  dose of 100 mg significantly decreased FPG levels (-10.81 mg/dl, -7.20%, p < .05) while that of 200 mg reduced
  HbA1c". Ginseng type not specified by the authors. Also: PMID 15982990 (Reay 2005), single 200 mg and 400 mg
  doses of Panax ginseng G115 lowered blood glucose in 30 healthy adults. Glucose floors set to 100 mg/day.
- Bleeding/warfarin: PMID 15238367 (American ginseng lowered INR; no dose in abstract); PMID 19913311 (Lee 2010,
  Korean red ginseng 1 g with warfarin after valve replacement, no significant INR change); PMID 23596810 (Kang
  2013, 1500 mg Korean red ginseng extract for 8 weeks, "Blood analyses for coagulation ... revealed no
  significant changes"); PMID 18090773 (Asian ginseng at the recommended dose, platelet function unchanged).
  No human source gives a dose for a bleeding effect: surgery and anticoagulants floors removed; presence.

## RULE_IQM_STINGING_NETTLE_DIABETES: glucose floors
- Old floor: 1000 mg/day, confidence_basis weak_signal_conservative, cited to PMID 35800714 (a general nettle
  review, no dose). The number had no source.
- PMID 24273930 (Kianbakht S et al. Clin Lab 2013, doi 10.7754/clin.lab.2012.121019, efetch 2026-09-26): RCT,
  46 vs 46 patients with advanced T2DM needing insulin, "nettle leaf extract (one 500 mg capsule every 8 hours
  for 3 months) combined with the conventional oral anti-hyperglycemic drugs"; fasting glucose, 2-h glucose and
  HbA1c fell significantly (p < 0.001, 0.009, 0.006).
- Other nettle trials: meta-analyses (PMIDs 31802554, 34587883) give no doses in their abstracts; PMID 28078249
  used a hydro-alcoholic extract in ml that cannot be converted to mg. 1500 mg/day is the lowest documented.
- Floors set to 1500 mg/day (extract). The label amount is compared as reported, so dried-leaf products are held
  to the extract dose.

## Licorice BP floors (RULE_BOTANICAL_LICORICE_ROOT, RULE_IQM_LICORICE_HYPERTENSION)
- Old floor source PMID 393503 (Takeda R et al. Endocrinol Jpn 1979): two mildly hypertensive women "administered
  273 to 546 mg glycyrrhizin daily"; no mention of 100 mg.
- PMID 38246526 (af Geijerstam P et al. Am J Clin Nutr 2024, efetch 2026-09-26): 28 healthy volunteers, nonblinded
  2x2 crossover, "a daily licorice intake containing 100 mg GA" for 2 weeks; systolic home BP "increased [mean
  difference: 3.1 mm Hg (95% CI: 0.8, 5.4 mm Hg)" vs -0.3 mm Hg on control, P = 0.018; renin -30%, aldosterone -45%.
- Conflicting null, smaller: Bernardi 1994 (PMID 8072387, efetch 2026-09-26), 108/217/380/814 mg glycyrrhizin in
  groups of 6 for 4 weeks, "No significant effects occurred in groups 1 and 2". Regulatory 100 mg/day figures (SCF 2003, JECFA 2005) are tolerated-intake
  limits, not effect doses.
- The enricher compares a floor with the ingredient row's label amount (`_evaluate_min_effective_dose`), not with
  glycyrrhizic acid content; a licorice row is at least its GA content, so the 100 mg floor never suppresses a
  product supplying 100 mg GA. Value unchanged in both rules; source and rationale replaced.

## Q24 green tea extract and liver disease (Sean's decision 2026-09-26: 800 mg EGCG is an observed risk dose)
- EFSA 2018, Scientific opinion on the safety of green tea catechins (EFSA J 16(4):e05239, PMID 32625874, PMC7009618;
  efetch, abstract + full text): "intake of doses equal or above 800 mg EGCG/day taken as a food supplement has been shown
  to induce a statistically significant increase of serum transaminases"; full text: "The Panel concluded that it was not
  possible to identify an EGCG dose from green tea extracts that could be considered safe." Traditional infusions "are in
  general considered to be safe"; rare idiosyncratic cases after infusions.
- USP 2020 review (PMID 32140423): case reports associate hepatotoxicity with "EGCG intake amounts from 140 mg to ~1000
  mg/day and substantial inter-individual variability"; USP monograph label: "Do not use if you have a liver problem".
  It does not tie first-pass saturation to 800 mg.
- LiverTox Green Tea (NBK547925, PMID 31643260): green tea extract "implicated in cases of clinically apparent acute
  liver injury, including instances of acute liver failure". Full chapter (dose dependence) not read: bot check.
- Removed as unsourced: "saturates first-pass elimination" at 800 mg, liver disease "lowers the threshold for injury",
  and a ">= 400 mg/dose" cut-off.
- Corpus (2026-09-22 enriched): 149 products stated EGCG < 800 mg (monitor, hidden), 83 stated none (hidden), 0 stated
  >= 800 mg. All 232 now show avoid to users with liver disease.
- Matcha: IQM files "matcha powder" and matcha aliases under green_tea_extract (5 products on the matcha form; more under
  "green tea extract (unspecified)"). Whole-leaf tea is not a concentrated extract (EFSA). Queued as Q25.

## D18 egg inside protein blends (Sean's decision 2026-09-26: evidence follows the intervention studied)
- Morton 2018 (PMID 28698222, PMC5867436, full text via efetch): 49 included RCTs are references 16-64 ("extracted from the
  final 49 studies.16-64"); sources: whey 23, casein 3, soy 6, pea 1, milk 10, whole food 7, 13 "non-specific protein
  blends or blends containing multiple protein sources (eg, whey, casein, soy and egg)". The only egg intervention is
  reference 45, Iglay 2009 (PMID 19299575): a whole-food diet with extra protein "predominately from egg sources", whose
  title reports it "does not influence" body composition responses. No included trial tested a whey/casein/soy blend with
  added egg; INGR_WHEY_PROTEIN has no egg alias and no egg evidence family exists.
- 25694 cleaned 2026-09-22 (read directly): active "Protein 22 g" plus whey/milk/soy source rows with no amounts; inactive
  "Protein Blend" forms: calcium caseinate, egg albumen, micellar casein, milk protein isolate, soy protein isolate, whey
  protein concentrate and isolate.

## Q23 printed 0% Daily Value (Sean's decision 2026-09-26: preserve it upstream, no category heuristic)
- enhanced_normalizer.py `_process_quantity`: `if dv:` dropped a printed 0.0; `.get("percent", 0)` turned a missing percent
  into 0.0 on the single-quantity path. Now a printed percent (0 included) is kept and none stays None.
- Raw corpus (~/Downloads/PharmaGuide_Datasets/staging/brands, 2026-09-26): top-level "0 NP" vitamin/mineral rows: 141 print
  0% (Vitamin A 59, Vitamin C 58: panel zeros), 18 print no percent (Vitamin B12 8, sodium 4: listed without an amount),
  328 print a positive %DV. The removed category heuristic misread the 18. All depths: 2,329 printed-0% rows in 1,059
  products now clean to dailyValue 0.0 instead of null.
- dailyValue readers checked: cleaner DV-unit repair and folate DFE (require > 0), scoring_input_contract and completeness
  gate (require > 0), enricher UL eligibility (>= 0: a 0% row becomes DV-confirmed; its amount is 0), nested DV owner
  (`is not None`: a parent printing 0% is no longer linked; not seen in tests), export (0.0 now ships where null did).

## D8 follow-up (Sean, 2026-09-26): a studied dose is not a warning threshold
- Ruling: a numeric floor needs threshold evidence (a dose-response study, multiple doses separating no effect
  from effect, or a monograph/regulatory threshold). A dose at which one study saw an effect is an observed-effect
  dose; it does not show that lower doses are inert.
- RULE_INGREDIENT_GINSENG glucose sub-rules: Sotaniemi 1995 (PMID 8721940) tested 100 and 200 mg/day only; the
  100 mg arm lowered fasting glucose (Derosa 2022, PMID 35912631). Floors removed; the 100 mg/day result is now
  stated in the four glucose mechanisms and 8721940 is in their sources. The four ghost-review entries for
  35912631 (which only the removed floor rationale cited) are deleted.
- RULE_IQM_STINGING_NETTLE_DIABETES: Kianbakht 2013 (PMID 24273930) is one regimen (500 mg every 8 hours); the
  diabetes mechanism stated it, the three hypoglycemic mechanisms now do too; all four cite it. Floors removed.
- Both rules now fire on presence at unchanged severities.

## standardized_botanicals ginger_extract: nonexistent PMID (Q22)
- PMID 28200047: esummary "cannot get document summary" (2026-09-26); it does not exist.
- The source line named "Marx et al. 2017 systematic review on ginger for chemotherapy-induced nausea". PubMed
  (esummary/efetch 2026-09-26): PMID 25848702, Marx W, Ried K, McCarthy AL, Crit Rev Food Sci Nutr 2017 Jan 2,
  "Ginger-Mechanism of action in chemotherapy-induced nausea and vomiting: A review" (publication type Review,
  not systematic); abstract: "Bioactive compounds within the rhizome of ginger, particularly the gingerol and
  shogaol class of compounds". The 2013 systematic review by the same group is PMID 23550785 (Nutr Rev).
- Source line now names 25848702 as a review. Citation only: the +1 standardized-botanical bonus depends on the
  label's gingerol claim, not on this source.

## standardized_botanicals slendesta: nonexistent PMID (Q22)
- PMID 22647284: esummary "cannot get document summary" (2026-09-26); it does not exist.
- PMID 28485429 (Zhu Y, Lasrado JA, Hu J et al. Food Funct 2017, doi 10.1039/c6fo01803c, efetch 2026-09-26):
  randomized double-blind placebo-controlled crossover, 44 healthy women, "potato extract standardized to 15 or
  30 mg PI2"; lower postprandial hunger and higher fullness; "Consumption of 15 mg PI2 also resulted in
  significantly higher postprandial plasma levels of cholecystokinin". Supports the entry's satiety/CCK note for a
  PI2-standardized potato extract; the abstract does not name the Slendesta brand.
- Other human PI2 trials seen: PMID 20644555 (Peters 2011, 30 mg PI2 minidrink), PMID 32161479 (Flechtner-Mors
  2020, 150 mg PI2 twice daily during weight reduction). Citation only; the bonus depends on the brand on the label.

## Licorice blood-pressure floors removed (D8, Sean 2026-09-26)
- PMID 38246526 (af Geijerstam 2024, efetch): "The World Health Organization has suggested that 100 mg GA/d would
  be unlikely to cause adverse effects"; in 28 healthy adults (median age 24) licorice with 100 mg GA/day raised home
  systolic BP by 3.1 mmHg (95% CI 0.8-5.4) over 2 weeks. A tolerable-intake level for most adults and one studied
  dose, not a floor.
- PMID 12574791 (Sigurjonsdottir 2003, efetch 2026-09-26): 100 g liquorice/day (150 mg glycyrrhetinic acid) for 4
  weeks raised office systolic BP 15.3 mmHg in essential hypertension vs 3.5 mmHg in normotensives (p=0.004).
- The floors compared a 100 mg value with the licorice ingredient's label mass (`_evaluate_min_effective_dose`),
  not glycyrrhizic acid content.
- Removed on RULE_BOTANICAL_LICORICE_ROOT antihypertensives and RULE_IQM_LICORICE_HYPERTENSION hypertension and
  antihypertensives; both sources added and the 100 mg figure stated as context in each mechanism. The IQM
  hypertension threshold (>= 2000 mg extract -> avoid, below -> monitor) stays; its note no longer calls 100 mg GA the
  point where BP elevation "becomes clinically significant".
- Impact, catalog 2026.09.22: 10 products newly show the IQM licorice hypertension warning (label licorice 1.5-80 mg);
  drug-class sub-rules are not in detail blobs. None hidden.
- Not verified here and not cited: the JECFA/WHO wording on susceptible subgroups and the WHO monograph
  contraindications quoted in Sean's pasted review.

## Q18 wrong-organism and wrong-preparation identities (Sean 2026-09-26: take care of Q18)
- Bionectria ochroleuca: NCBI Taxonomy 29856 (efetch 2026-09-26) is Clonostachys rosea, lineage Hypocreales;
  Bionectriaceae; synonyms include "Bionectria ochroleuca". UMLS C1002888 "Clonostachys rosea" (atoms: MSH/NCBI
  "Bionectria ochroleuca"). Cordyceps militaris is Cordycipitaceae. Raw DSLD rows (Garden of Life RM-10 297676/297677/
  321368/326697, mykind Vegan D3 233695/243404/274574) name only "Bionectria ochroleuca" inside mushroom blends, NP.
- Fermented soybean powder: IQM nattokinase listed it as a same-identity alias. Nattokinase is an isolated fibrinolytic
  enzyme sold by activity (FU); a soybean powder label states no enzyme activity. Rows (78306 5.61 mg, 31148 NP) now
  resolve to IQM soybean. EstroSoy 229950 "Fermented Soy extract" (670 mg, form Isoflavones) keeps IQM soybean through
  an explicit alias (it would otherwise fall to the other_ingredients fermented-soy descriptor).
- Essential oils: the cleaner already matched bergamot_essential_oil (GSRS 39W1PKE3JI "BERGAMOT OIL") and
  chamomile_essential_oil (GSRS SA8AR2W4ER "MATRICARIA CHAMOMILLA FLOWERING TOP OIL"); `identity_integrity.resolve_identity`
  replaced them with the DSLD group identity (citrus_bergamot, chamomile) because no parent relationship was
  registered. P1 had already ruled oils are not twinned ("preparation: essential oil, not fruit/flower extract").
- Dandelion root: EU herbal monograph on Taraxacum officinale F.H. Wigg., radix, EMA/HMPC/475726/2020, final
  2021-11-24 (read in full): indication 3 "Traditional herbal medicinal product to increase the amount of urine to
  achieve flushing of the urinary tract"; 4.4 "dandelion root is not recommended for patients with conditions where
  reduced fluid intake is advised by a medical doctor"; 4.4 not recommended in bile-duct obstruction, cholangitis,
  liver disease, gallstones; 4.5 "None reported"; 4.6 use in pregnancy and lactation "not recommended".
- Measured (raw -> clean -> enrich -> score, worktree vs origin/main a3abb199): 7 Bionectria products lose
  RULE_IQM_CORDYCEPS_AUTOIMMUNE; 31148 and 78306 lose RULE_IQM_NATTOKINASE_BLEEDING; 222867 loses the bergamot rule
  and 232878/232905/232942 the chamomile rule; 7 dandelion_root products gain RULE_IQM_DANDELION_KIDNEY. No score or
  status changes.

## Q25 matcha split from green tea extract (Sean 2026-09-26: take care of Q25)
- IQM green_tea_extract carried a "matcha powder" form (bio 8) and five matcha aliases under its unspecified form;
  standardized_botanicals green_tea (extract bonus registry) carried "matcha". Botanical matcha_tea_powder already
  existed. All 18 matcha products in the cleaned corpus now resolve there; DSLD groups every one under "Green Tea".
- Nadolol evidence is brewed tea and EGCG: Misaka 2014 (PMID 24419562, efetch): green tea 700 mL/day for 14 days cut
  nadolol Cmax and AUC by 85.3% and 85.0% and reduced its systolic BP effect; Abe 2018 (PMID 29480324): single-dose
  EGCG-rich extract AUC ratios 0.72 and 0.60; EGCG inhibits OATP1A2 nadolol uptake. Carried to matcha as
  RULE_BOTAN_MATCHA_BETA_BLOCKERS (avoid, presence), not the liver sub-rule (EFSA 2018: traditional infusions generally
  safe; the concern is concentrated extracts).
- Measured: 13 matcha products lose the extract liver warning and keep the beta-blocker warning; scores 330026-330029
  53.1 -> 51.2, 335679 62.4 -> 64.4, 326246 54.5 -> 58.8, others unchanged; statuses unchanged.

## Q15 "FDA ban effective" labels on 36 banned_recalled records (Sean's D10 standard, 2026-09-26)
Two research agents read the primary document for each record (fda.gov live or via Wayback, federalregister.gov
API, ecfr.gov, govinfo, accessdata import alerts, DOJ releases on fda.gov, opss.org); per-record JSON receipts with
verbatim quotes were checked by script against the saved sources. Spot-checked here: Federal Register API for 64 FR
4050, 63 FR 6862, 91 FR 42150, 91 FR 40917, 75 FR 80061; Hydroxie 709661 (2025-06-25); the DMHA/phenibut update
(12 letters 2019-04-10; phenibut misbranded, DMHA NDI-or-unsafe-food-additive); Peak Nootropics 557887 (2019-02-04,
footnote: the letter "does not address ... whether products containing piracetam can be lawfully marketed as
dietary supplements"); Melanotan II consumer update (Wayback 2008-12-19 capture).
- Genuine bans (label kept): ephedra (69 FR 6788, effective 2004-04-12, 21 CFR 119.1; the rule cites "more than
  18,000 AERs", not 155 deaths/17,000); FD&C Red No. 2 (41 FR 5823 delisting, effective 1976-02-12 per 41 FR 6774;
  "41 FR 41858" is not FDA's citation); titanium dioxide EU (Regulation (EU) 2022/63, in force 2022-02-07;
  2022-08-07 ended sell-through).
- Warning letters / advisories / import alerts (verified; legal status per FDA's own theory):
  1,4-butanediol T99-21 1999-05-11 (Class I Health Hazard; unapproved new drugs; not scheduled, not List I);
  7-OH Hydroxie 2025-06-25 ("not lawful in dietary supplements"; DEA notice of intent only, no 2024 scheduling);
  aristolochic acid Import Alert 54-10 2000-07-06 (not 54-12) + 2001-04-09 letter (adulterated; "over 100 cases of
  nephropathy", not transplants); BMPEA 2015-04-23 (not a dietary ingredient -> misbranded; "4-amino-2-methylpentane"
  is a DMBA synonym; 9 of 21 is Pawar 2013); comfrey 2001-07-06 letter (adulterated; FTC preliminary injunction vs one
  firm); DMAA letters from 2012-04-24 (not a dietary ingredient; 11th Cir. 2019 upheld seizure); DMBA 2015-04-28 (NDI
  without notification -> adulterated, FDA directory category 7); DMHA 2019-04-10 (now: not a dietary ingredient,
  unsafe food additive); higenamine IronMag 622504 2022-05-04 (a dietary ingredient marketed as an NDI without
  notification -> adulterated; not drug exclusion; Advisory List by 2019-06-24); phenibut 2019-04-10 (misbranded;
  2023 Chill6 injunction; 2023 Nootropics Depot plea); picamilon 2015-11-30 (misbranded, niacin-GABA entity);
  sibutramine FDA withdrawal request 2010-10-08, NDA withdrawn 2010-12-21, DEA Schedule IV 1998-02-11; tianeptine
  MA Labs 566831 2018-11-07 (DEA proposed Schedule I 2026-07-08, not III, not final); yellow oleander tejocote
  warning 2024-01-26 (Nuez de la India Sept 2023; no 2021 alert, no import alert, no deaths in FDA text);
  dymethazine Hardcore Formulations 522783 2017-06-05 + recall 2017-06-28 (the cited 2012 "Ultra Research" recall
  URL 404s and was never archived; not in 21 U.S.C. 802(41)(A)); adrafinil, aniracetam, Noopept, phenylpiracetam
  Peak 557887 2019-02-04 ("not dietary supplements", unapproved new drugs by claims); modafinil DEA Schedule IV
  1999-01-27 (1998-12-24 is the Provigil approval); Melanotan II warning letter on or about 2007-08-30 (FDA 2016
  NOOH) + 2007 consumer update; kratom Import Alert 54-15 firms from 2014-02-28 (FDA: 44 reported deaths); DMAA
  analogs: per-compound DMBA/DMHA actions, no class statement.
- No US determination (policy unverified, legal status under_review, gate routes a match to review): fasoracetam,
  IGF-1, IGF-1 LR3, sunifiram (only the DoD list names it), 9-Me-BC, flmodafinil (analogue law covers Schedule I/II
  only), piracetam (FDA's letters say they do not decide supplement lawfulness). The 2019-11-25 date on four
  nootropics is the publication date of a non-FDA study.
- Non-bans outside "banned": potassium bromate (21 CFR 172.730/137.155 permit it; California bans it in food from
  2027-01-01; EU/Canada/Brazil claims unverified, EUR-Lex unreadable); synthetic estrogens (no supplement document;
  21 CFR 310.530 covers OTC topical hormone drugs); lobelia (21 CFR 310.544: OTC smoking-deterrent drugs only, "After
  December 1, 1993"; the Poisonous Plant Database page is gone).
- DoD rows: all named on the DoD Prohibited Dietary Supplement Ingredients list (opss.org, DoDI 6130.06, updated
  2026-05-26): enobosarm/Ostarine, LGD-4033, vosilasarm/RAD140, DMAA, adrafinil, modafinil, fonturacetam
  (phenylpiracetam), DMBA, DMHA, sunifiram. Retyped from state_statute to the list (type regulatory, agency scope).
- Corpus: none of the 36 records matches a product in the 2026-09-22 enriched corpus, so no verdict moves today.
  Gate probe: a DMAA product went from quarantine (policy unverified) to BLOCKED; piracetam stays in review.

## Q21/Q29 botanical interaction closure (2026-09-27)
- Eleuthero: the EMA community monograph for *Eleutherococcus senticosus* reports no interactions and says pregnancy/lactation safety is not established, so use is not recommended. The associated assessment report says the old hypertension contraindication was removed because the literature did not justify it. The existing `siberian_ginseng` identity therefore gets only a pregnancy/lactation rule; no Panax, drug-class, or blood-pressure claims were transferred.
- Dandelion root: the EMA EU monograph for *Taraxacum officinale* root says use is not recommended during pregnancy/lactation and with bile-duct obstruction, cholangitis, liver disease, gallstones, or other biliary disease because of possible bile-secretion stimulation. These statements now live on the existing dandelion interaction owner.
- DGL: the codebase already had `botanical_ingredients.dgl_deglycyrrhizinated_licorice` and explicitly prohibited twinning it to IQM licorice. DGL/GutGard aliases were removed from the ordinary licorice identities and routed to that owner. The unread `form_exclusion` field was deleted.
- Validation: focused identity/interaction regressions passed; strict citation verification passed with 152 rules, 258 PubMed IDs, 16 Bookshelf chapters, and zero unresolved sources.

## Q30 omega transparency closure (2026-09-27)
- Owner: `scripts/scoring_v4/quality_score.py` with magnitudes in `scripts/scoring_v4/config/quality_score.json`; omega disclosure components live in `scripts/scoring_v4/modules/omega_transparency.py`. Lot-level oxidation evidence stays with Verification/certification evidence.
- Removed the retired zero-point `oxidation_disclosed` execution branch and corrected the omega-native transparency cap from 13 to the live component sum of 11.
- Projected against `release_candidate_a0eee3e5.jsonl`: 76 scored omega products; 68 score changes, range +0.6 to +2.3, mean +1.85; 13 tier shifts; no status, safety, or route changes. This is a cap-only projection because the retired signal was absent from the cohort.

## Final combined fast-suite receipt (2026-09-27)
- Corrected branch HEAD `d173ca14`: `scripts/test.sh fast` passed 16,759 tests, skipped 170, exit 0 in 434.51 seconds.
- The first combined run exposed stale omega cap fixtures, a second dandelion rule owner, and one raw-serving fallback test. Those contracts were corrected before this passing run; none was waived.
- Owner Check: Evidence headline `scripts/scoring_v4/modules/generic_evidence.py::_evidence_result_state`; omega score magnitudes `scripts/scoring_v4/config/quality_score.json`; interaction policy `scripts/data/ingredient_interaction_rules.json`; export brand/serving `scripts/build_final_db.py::resolve_catalog_brand` and `generate_dosing_summary`. Evidence: source-of-truth matrix plus focused `rg` traces recorded in the commits above. Will NOT create another evidence state, scorer, interaction registry, brand resolver, serving owner, or export field.

## PHGG/Sunfiber — indexed clinical-source review (2026-10-02)

Entry:backed_clinical_studies/BRAND_SUNFIBER. Full primary methods identify Sunfiber in both PMID26855665 ([Niv2016](https://doi.org/10.1186/s12986-016-0070-5)) and PMID31509971 ([Yasukawa2019](https://doi.org/10.3390/nu11092170)). Published positive findings are selective, with null overall severity/QOL/frequency outcomes and commercial support. Two indexed RCTs randomized121+44=165; modified ITT/endpoint populations differ. Later unindexed PMID36936875's60subjects cannot silently supply this entry's enrollment or stress/mood claim.
Source-corrected attribution, date/authors/enrollment, outcome scope, funding context and unqualified GuarFiber alias. Live PMID titles/topics match; parent UNIIE89I1637KE independently resolves to GUAR GUM in FDA-SRS, not proof of hydrolysis/brand. Exact preparation applicability comes from explicit label form and trial methods; no chemical form is inferred from that parent identifier.
Existing positive_strong classification and raw18floor remain pending cross-family certainty/calibration; no re-ratification, new dose benchmark or sponsorship deduction. Raw227960 has6.4g/daydeclaredSunfiber preparation, different from dietary-fiber assay exposure. Source trials distinguish titrated6g/dayIBSbloating versus5g/dayhealthyloose-stoolform. Full source receipt and saved XML/text: `/Users/seancheick/pg_quality/phgg_clinical_review_20261002/primary_review.md`; clinical-study prospective registration/SAP check remains open. Verify outcomes individually rather than equating branded-RCT status with strong general efficacy.

## INGR_INULIN — bounded factual receipt, October2

Sources verified live: https://pubmed.ncbi.nlm.nih.gov/35833477/ (chicory ITFs,50studies/2525participants,3–20g/day, bowel benefits healthy subjects, no significant GI-disorder bifidogenic subgroup); https://pubmed.ncbi.nlm.nih.gov/34555168/ (full healthy-adult review78publications;11/20stool-frequency positive and9null; calcium absorption/balance/serum concentrations distinct, preparation/chain-length caveats, General Mills support); https://pubmed.ncbi.nlm.nih.gov/38309832/ (55RCTs/2518participants; low/very-low-certainty LDL/triglyceride/body-weight risk-factor effects, no cardiovascular-event claim). Bibliographic BENEO affiliations/support verified for35833477; precise funder roles and inaccessible publisher details remain unresolved. FDA https://precision.fda.gov/uniisearch/srs/unii/JOS53KRJ01 identifies inulin, not FOS equivalence.
Correction: remove generic prebiotic-fiber identity and unsupported tags/discovery fields; preserve ITF-family FOS applicability with explicit outcome/preparation bounds.420/224 originated as automated registry metadata with no NCT mapping; total_enrollment is optional largest-registry-trial per schema, not pooled meta-analysis count. Never add review totals because they overlap. Existing grading retained pending calibration, no universal dose benchmark supplied. Canonical one-entry patch, source/test/replay/review receipts under /Users/seancheick/pg_quality/inulin_clinical_review_20261002/.

## XOS/PreticX bounded source correction — October2

Existing IQM XOSnotes only. https://pubmed.ncbi.nlm.nih.gov/24513849/ verifies2014healthy-adult microbial/tolerability study; indexed primary https://pubs.rsc.org/en/content/articlehtml/2014/fo/c3fo60348b exposes Table3week-eight low/placeboP=.052 versus stronger prose. Directpublisher requests403; partial indexed retrieval is not full direct-access closure.2015 https://pubmed.ncbi.nlm.nih.gov/26300782/ and full https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2015.00216/full explicitly distinguish2gXOS from2.8g70%preparation (1.96rounded2), with no significant metabolic benefit. Supplier LifeBridge/manufacturerShandongLonglive are not explicitPreticXbrand/grade proof. Shared authors are not independent-team replication. No cross-study purity borrowing or universal benchmark supplied. Registration/2014funding/detailedsource equivalence remain unverified.
One-parent canonical patch contains only XOSnotes+metadata; allidentity/numerical/consumer-note values unchanged. Live changed-parentcitationcheck4MATCH/0mismatch, two new XOSclaims andtwo unchangedsiblings.15real raw/control captures identical; copied-primary sources/receipts in /Users/seancheick/pg_quality/xos_clinical_review_20261002/. Current0Evidence is a pending clinical-credit determination, not absence of human research. Current fiber-dose table credit is not XOS-specific studied-range proof. Remaining decisions stay in existing D24/calibration owners.

## October 2 — GOS/Bimuno and PreforPro primary-source determinations

Owner: existing IQM form `notes`; no new clinical registry, scorer, parser, benchmark or numerical policy. Source `c527c43c`, baseline `bf12f605`. Receipts: `/Users/seancheick/pg_quality/gos_phage_review_20261002/primary_dispositions.md`; complete primary texts in adjacent GOS and PreforPro research folders.

| Entry | Verified finding | Correction | Still unresolved |
|---|---|---|---|
| GOS/Bimuno | PMID30109908: 2.75 g powder contains 1.37 g active GOS; selected symptomatic adults, two-week periods, bloating/flatulence/pain benefit versus placebo, stool/QOL/mood null. PMID26218845: 5.5 g powder at48% GOS; healthy65–80, ten-week periods, microbial/immune biomarkers, bowel/mood null. Clasado support and overlapping investigators. | Remove universal efficacy/tolerability claim; preserve preparation/population/outcome bounds and both positive/null findings. | Current label preparation correspondence, clinically meaningful outcome grading, independent replication and appropriate Dose benchmark. PMID19053980's full preparation details remain inaccessible; no purity borrowed from another trial. |
| PreforPro/phage | PMID30157383 and30897686 report one PHAGE trial; 28-day periods, 15mg carrier-containing capsule and10^6 phages/dose. Selected microbial changes and global-diversity null do not establish infection treatment or no effect on every beneficial organism. PMID32824480: BL04+10^6PFU phages, no phage-only arm, no significant between-group symptom-score change; questionnaire GI inflammation is perceived symptoms. Deerland support and investigator overlap. | Remove overbroad pathogen/beneficial-flora/GI-immune claims; preserve trial identity, combination attribution and potency distinction. | Applicability to the exact marketed preparation, clinical outcome grade and phage-specific Dose assessment. Neither arbitrary formula benefit nor absence of human research is established. |

The nine-match automated citation receipt includes four unchanged prebiotic sibling citations. It is a topic/identifier check, not proof of clinical grading. Thirty source-text matching labels plus nine controls yield identical scored captures; these are a text-match superset, not39 independently reviewed Evidence subjects. No new points awarded and no runtime publication.

### Cross-family decision inputs after the source corrections

This table is a clinical/calibration input, not an approved scoring change. Scores describe the named frozen labels, not universal category grades.

| Family / example | Current Evidence /20 | What the source review establishes | Decision still needed before numerical change |
|---|---:|---|---|
| PHGG / Nature's Way227960 | 20 | Branded-preparation trials, bounded symptom/stool outcomes, null findings and commercial provenance retained. | Certainty/replication and preparation applicability must justify normalization of raw18/reference18 to20. |
| Inulin / Nutricost306369 | 15.6 | Human chicory ITF studies; bowel, microbial and preparation-specific calcium findings; risk-factor certainty limits. | Which intervention/outcome legitimately applies to the label, and comparable clinical grade across families. |
| XOS / Pure302463 and294036 | 0 | Human research exists; mostly microbial outcomes, no significant metabolic benefit in the retrieved2015 study,2014 table/prose discrepancy. | Exact PreticX grade/purity linkage and whether reviewed microbial outcomes merit any Evidence credit under approved policy. |
| Bimuno GOS / GNC219246,304444,318195 | 0 | Preparation-specific human symptom benefits and null endpoints; declared label1.37g does not independently prove composition equivalence. | Preparation correspondence and clinical certainty/outcome credit; powder-versus-active Dose basis. |
| PreforPro / Thorne323127 | 0 | One standalone trial with tolerance/microbial observations; PHAGE-2 combination has no significant between-group symptom-score improvement. | Standalone versus exact-formula applicability and eligible endpoint grade.15mg cannot become active-potency benchmark. |
| Seed / previously preserved manual product | 14.5 | Existing source receipt retained; no new Seed replay in this39-label batch. | Compare its recorded outcome certainty/replication with the currently credited IS-2/LactoSpore families after exact strain/formula source checks. |

Apply one certainty/applicability standard to every family. Positive within-group change is not controlled superiority; multiple papers from one trial are not replication; microbiome biomarkers are not automatically patient benefit. Funding is provenance under current policy. Missing benchmark is a knowledge state, not zero amount; generic fiber-mass credit is not preparation-specific trial adequacy. No arbitrary ceiling, rescale, sponsorship deduction, new benchmark or missing-benchmark withholding decision is approved by this table.

Q53 queue refreshed through current Clean → Enrich → `build_scored_artifact` at `c527c43c`: all nine historical labels still have incomplete Evidence readiness (12091,1834,19171,19172,19890,264105,35694,46802,65049). Receipt: `/Users/seancheick/pg_quality/gos_phage_review_20261002/q53_current_readiness.json`. Their `quality_assessment_status=complete` reflects the currently enforced identity/Dose/route/verification dimensions; it is not completed clinical Evidence. The actual Evidence readiness remains incomplete. Preserve that distinction instead of marking the research queue closed from the overall assessment field. Named-strain SD-5845 and Bioflora/Advanced Acidophilus identity review is the first bounded follow-up; species-only labels must not inherit unrelated strain evidence.

## Q56 DEA dates for α-PHP and CUMYL-PICA

Checked 2026-10-02. Sources: Federal Register API (federalregister.gov/api/v1), eCFR 21 CFR 1308.11 as of 2026-09-30
(api/versioner/v1/full/2026-09-30), PubChem PUG REST, Crossref, PubMed efetch.

**STIM_ALPHA_PHP.** PubChem CID 102107923, 1-phenyl-2-pyrrolidin-1-ylhexan-1-one, matches the 1308.11 listing
"alpha-Pyrrolidinohexanophenone (Other names: α-PHP; ... 1-phenyl-2-(pyrrolidin-1-yl)hexan-1-one) 7544".
Federal Register: temporary scheduling order 84 FR 34291 (2019-07-18, effective 2019-07-18; doc 2019-15184),
extension 86 FR 37672 (effective 2021-07-18), final rule 87 FR 32996 (2022-06-01, effective 2022-06-01;
doc 2022-11740). The record's 2014-01-01 matches no document (2014 is when α-PHP appeared on the Japanese market,
PMID 38672701). Result: date 2019-07-18 "DEA scheduling effective", controlled_substance, US row cites both rules,
policy verified (federalregister.gov URL), as NOOTROPIC_MODAFINIL under Q15.

**SYNTH_CUMYL_PICA.** PubChem CID 86273678, 1-pentyl-N-(2-phenylpropan-2-yl)indole-3-carboxamide (UNII H4APZ90T9U).
Not in 1308.11 by name (searched "CUMYL-PICA", "1-pentyl", "phenylpropan-2-yl": the five hits are 4-CN-CUMYL-BUTINACA,
5F-CUMYL-P7AICA, 5F-CUMYL-PINACA, CUMYL-PEGACLONE and mesocarb). Paragraph (g)(1)(i) classes A–E are
hydroxycyclohexylphenols, naphthoylindoles/naphthylmethylindoles, naphthoylpyrroles, naphthylmethyleneindenes and
phenylacetyl/benzoylindoles; an indole-3-carboxamide is none of them. Federal Register full-text search for
"CUMYL-PICA" and for its systematic name: 0 documents. Prosecution as a controlled-substance analogue (21 U.S.C. 813)
is a case-by-case court question, not a scheduling, and no document dates one. Result: date and label removed (not
replaced), under_review, policy unverified (as BANNED_FASORACETAM under Q15).

**Citations.** Removed: 10.1016/j.forsciint.2015.09.002 (Crossref: "Facial soft biometric features for forensic face
recognition") and 10.1016/j.forsciint.2017.03.004 ("Toolmarks made by lathe chuck jaws"), plus two DEA references
without a URL. Added, abstracts read: PMID 38672701 (α-PHP/α-PiHP review: no medical use, cardiac/psychiatric/
neurologic effects, fatal intoxications); 39987764 (α-PHP mice plus Pavia Poison Centre cases: agitation,
hallucinations, tachycardia, hyperthermia, rhabdomyolysis); 28792725 (CUMYL-PICA potent CB1/CB2 agonist, hypothermia
and bradycardia in rats at 1 mg/kg); 29549157 (CUMYL-PICA high CB1 affinity, greater efficacy than THC).
`verify_all_citations_content.py --file banned_recalled_ingredients.json --changed-since origin/main`: 4 MATCH.

**Impact.** Warning titles: α-PHP "Not lawful as a supplement" → "Controlled substance"; CUMYL-PICA "Controlled
substance" → "Unapproved ingredient". Neither rule matches any of the 15,133 detail blobs (catalog 2026-09-29) or the
38 enriched brand outputs, so no shipped product changes. Safety copy: CUMYL-PICA safety_warning loses its regulatory clause ("Not a lawful
supplement ingredient;"), keeping the harm statement and "Stop any product containing it and consult a doctor."
No replacement regulatory phrase ("no approved use" was tried and dropped: it states a determination nobody made).

## Q57 DOI citation integrity

Checked 2026-10-02. Extraction: `verify_all_citations_content.py` (now DOI-aware), so the receipt and the gate use one
definition of a citation. Each DOI resolved on Crossref (`api.crossref.org/works/<doi>`) and PubMed (`esearch <doi>[doi]`);
the citing text (reference title/summary, `scientific_references` string, prose sentence) read against the resolved title,
abstracts read where the title left doubt. Per-citation verdicts: `q57_doi_dispositions_20261002.json`.

- **Inventory.** 206 DOI citations: banned_recalled 88, harmful_additives 113, other_ingredients 5. A first regex pass
  found 175 and missed DOIs cited as bare text; the verifier's walker is the inventory of record. IQM's 44 DOIs all
  resolve on topic (42 match, 2 partial) and are unchanged.
- **Removed (127).** Unrelated paper (e.g. 10.1093/jat/bks078 for DMAA -> Moscow theatre siege casualties;
  10.1124/jpet.116.232215 for 7-OH -> relaxin and lung injury; 10.1016/j.forsciint.2012.02.015 for yohimbe -> facial soft
  tissue; 10.1093/jnci/djq516 for nitrite cancer risk, five entries -> osteonecrosis of the jaw), or nothing (19 Crossref
  404s with no PubMed DOI hit), or wrong for the claim (EFSA chemical-mixtures statement for EDC health effects; the
  enobosarm DILI case report filed under RAD140; "How bad is fructose?" cited for syrup glycemic effects; four audit notes
  "REMOVED/NEEDS_VERIFICATION" stored as scientific_references).
- **Corrected (6).** Mistyped DOI of the document the entry names, target checked on Crossref: fats DRV 1459 -> 1461
  (canola, corn oil), E475 4743 (PGPR E476) -> 5089, nitrite 4787 (nitrate) -> 4786, nickel 4007 (Allura Red exposure) ->
  4002, carmine 4037 (pesticide MRL) -> 2015;13(11):4288. E475 opinion (PMID 32625376): "no need for a numerical ADI";
  the entry's "ADI 25 mg/kg bw/day retained" (regulatory_status.EU, notes, scientific_references) was the PGPR conclusion
  and is corrected. No EFSA "Tin in food" 2016 opinion exists on Crossref; that citation was removed, not guessed.
- **Added (5).** PMID 34368386 (Bedi 2021, cholestatic liver injury from ostarine) to SARM_OSTARINE; EFSA 2017;15(6):4786
  to ADD_POTASSIUM_NITRITE and 4787 to ADD_POTASSIUM_NITRATE; NTP Report on Carcinogens BHA profile (NBK590883, title and
  sections confirmed via NCBI E-utilities; the Bookshelf page is CAPTCHA-gated) to ADD_BHA; EFSA 2004;2(9):83 parabens
  opinion to ADD_PROPYLPARABEN. Williams 1999 (BHA/BHT "pose no cancer hazard") was not used for BHA's harm claim.
- **Kept (71)** including McCann 2007 on Blue 1/2 (cited for the note that E133/E132 were NOT in the Southampton mixes) and
  Chassaing 2015 on two emulsifiers (framed as class-level evidence). Ten correct citations the identity-word heuristic
  scores "mismatch" are in `citation_content_backlog.json` with a note.

## Q57b harm sources

Per-entry before/after, evidence, grades, sources and Sean flags: `q57b_harm_sources_20261002.md` (same folder). Regression: `scripts/tests/test_q57b_harm_sources.py`.

## October 2 combined clinical completion — current source qualification

Baseline753aa5cf. All nine Q53 queue labels and eight comparison families reviewed together; this section supersedes older ingredient-by-ingredient next-step instructions. Research disposition is not a new clinician signoff, numerical-policy approval or release qualification. Source receipts, raw hashes, live API responses and primary full texts: `/Users/seancheick/pg_quality/clinical_completion_batch_20261002/`.

Applied corrections: LA-5 monostrain candidiasis source scope/current qualification attribution, preserved historical withdrawal/clinical holds; MTCC5856 five double-blind design facts, already-resolved daily regimen, endpoint hierarchy and funding-versus-author-affiliation distinctions; IS2 correct Bacillus clausii comparator and null respiratory outcomes; LactoSpore indexed digestive studies cannot claim clinical immune benefit; oat-bran powder is not 3g beta-glucan soluble fiber; Actilight FOS bifidobacterial response does not imply a Lactobacillus increase or universal clinical effect. Six existing curated entries changed; no new grade, benchmark or registry.

Two owner fixes: ALCAR cannot borrow the nonacetylated L-carnitine reference; the existing no-reference Dose behavior remains. Shared probiotic assessment awards no Evidence and leaves scoring citations empty; only the existing Evidence winner supplies awarded native-family citations. IS2's winning IBS trial is31434935, not the athlete+whey35249118 trial. Source inventories and historical review controls remain retained.

Verification so far: seven actual fail-first cases across source classes plus three ALCAR and three IS2 amount scenarios;616owner/consumerchecks passed. Citation verifier46matches/0mismatches (includes unchanged citations inside changed entries); full-primary reading supports actual corrected claims. Independent reviews48+79checks, all27ALCARaliases and seven adversarial family controls; protected registry grades/thresholds/context eligibility byte-identical to baseline. Combined raw/candidate CI/local checkpoint receipts are recorded in LEDGER/masterplan, not implied by this research packet.

# Q53 remaining clinical subjects: complete read-only batch

Verified 2026-10-02. Requested baseline 753aa5cf; this report makes no refreshed branch-state assertion. All nine historical labels inspected together: 12091, 1834, 19171, 19172, 19890, 264105, 35694, 46802, 65049. No repository source edits, tests, grades, numerical policy, new semantic owner, or release. Research is source-reviewed agent evidence, not a new clinician sign-off.

Procedure: read `.claude/skills/data-fix/SKILL.md`, `.claude/rules/clinical-data.md`, current handoff, prepared Q53 follow-up report, and current readiness receipt. Reused prepared SD-5845/Bioflora/LA-5 receipts; independently fetched all nine live NIH labels and LA-5/Bioflora primary full texts. Each label's ingredientRows, servingSizes and statements equals retained raw. Durable source manifest and files accompany this report. Live official APIs are historical label evidence, not proof of the current marketed formula.

Owner: `scripts/data/clinically_relevant_strains.json::clinically_relevant_strains[STRAIN_ACIDOPHILUS_LA5]`; existing fiber/form owners `scripts/data/ingredient_quality_map.json::oat_bran.forms`, `::prebiotics.forms.fructooligosaccharides (FOS)`; nonpositive literature applicability owner `scripts/data/literature_evidence_records.json::records[canonical_id=oat_bran]`; preparation-specific human-study owner `scripts/data/backed_clinical_studies.json`; readiness consumer `scripts/assessment_readiness.py::evaluate_evidence_assessment`. Evidence: matrix/glossary/registry searches plus owner and readiness function reads. Will NOT create: strain identity, efficacy registry, score, benchmark, public field, or parallel readiness owner.

## Disposition register: every unresolved evidence row, plus retained subjects

The supplied current readiness file has 13 not-yet-evaluated individual rows across nine labels. Psyllium is already supported at ingredient level; eight probiotic-total projections are module aggregates, not individual efficacy evidence. All nine currently report overall complete/live-ready while Evidence remains incomplete because Evidence is not among enforced dimensions. This report completes the bounded research review, not production readiness or clinical integration.

| Label / source row | Verified subject | Research disposition | Constraint |
|---|---|---|---|
|12091 / ingredientRows[2]|B. infantis SD-5845,10mg|Insufficient independently linked strain identity; bounded exact-code search negative|No 35624 equivalence; total5B cells cannot allocate component CFU|
|1834 / ingredientRows[0]|Psyllium husks400mg|Known preparation class, ingredient human evidence supported; existing match retained|Evidence existence does not validate this dose or formula|
|1834 / ingredientRows[1]|Oat bran powder200mg|Known crude identity; limited preparation/population-specific evidence, applicability to this label unestablished|No measured beta-glucan, particle size or study-preparation match|
|1834 / ingredientRows[2]|Wheat bran powder200mg|Known crude identity; mixed/null IBS evidence with tolerance limitations; applicability unestablished|No coarse-bran equivalence or10g/day study-dose equivalence|
|1834 / ingredientRows[3]|L. acidophilus200mg|Insufficient strain identity|No code or CFU anywhere in retained/live label|
|1834 / ingredientRows[4]|FOS500mg|Known broad fructooligosaccharide class; preparation-specific positive/null/surrogate and combination evidence; label applicability unestablished|DP/purity/manufacturer not declared; no tested matching combined formula|
|19171 / ingredientRows[0]|L. acidophilus1mg; over100M organisms|Insufficient strain identity|Species-only; count at manufacture, not strain identity|
|19172 / ingredientRows[0]|L. acidophilus10mg;1B CFU|Insufficient strain identity|Species-only; current promises do not identify archived strain|
|19890 / ingredientRows[1]|L. acidophilus25mg;1B CFU|Insufficient strain identity|No strain code; no transfer from other up&up formula|
|264105 / ingredientRows[0].forms[0]|LA-5;5mg;500M CFU/capsule|Known exact named strain; monostrain comparator/null-or-negative VVC evidence; digestive efficacy inapplicable/unestablished|No gut benefit, equivalence or Solgar-formula trial inferred|
|35694 / ingredientRows[0]|L. acidophilus5mg/2 tablets;1B CFU/serving|Insufficient strain identity|No code; no current LA-14/NCFM marketing substitution|
|46802 / ingredientRows[0]|Bioflora10mg including metabolic products|Insufficient formula/strain identity|Branded parent of below child, not a second demonstrated probiotic|
|46802 / ingredientRows[0].nestedRows[0]|Active L. acidophilus2B organisms|Insufficient strain identity|Product-specific unit correction supplies no strain|
|65049 / ingredientRows[0]|L. acidophilus5mg;1B CFU|Insufficient strain identity|No code; no LA-14/LA-5 substitution|

12091's additional named blend subjects were also inspected despite not being separate material Evidence rows in the supplied snapshot: `ingredientRows[3]` proprietary15mg blend and children B. animalis lactis, B. longum, B. bifidum (all NP component quantities) have insufficient strain/formula identity. Do not transfer BB-12, HN019, BB536 or other named-strain trials. One total5B product count does not establish four component doses or a validated complete-formula identity.

## Per-label primary/readiness receipts

### 12091 — up&up 4X Probiotic

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/12091), retained `staging/brands/Up_and_Up/12091.json`, independently matching live fields. Adults1 caplet/day; SD-5845 10mg plus15mg blend of three species, total5B live cells at manufacture. Comparison explicitly distinguishes SD-5845 from Align35624. No deposit/sequence linkage or trial formula identity is provided. Live Europe PMC query `"SD-5845" OR "SD5845" OR "SD 5845"` returns0; prepared exact-code web searches retained. This is a bounded negative search, not proof of absent research. Readiness has one unevaluated SD-5845 row; totalCFU is not applicable individually. Manufacturer/deposit linkage remains necessary for exact-strain attribution.

### 1834 — GNC Preventive Nutrition Colon Care

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/1834), retained `staging/brands/GNC/1834.json`, independently matching. Three capsules/day provide psyllium400mg, oat bran200mg, wheat bran200mg, L. acidophilus200mg, FOS500mg. No beta-glucan measurement, bran particle size, FOS DP/purity/preparation, probiotic code or CFU. No reviewed source located identifies this exact five-component preparation as its intervention. Readiness already supports psyllium but leaves all other four rows unevaluated. The mass quantities are label facts, not proof of therapeutic dosing.

**Psyllium:** existing `INGR_PSYLLIUM_HUSK` owner supplies human evidence. Independently reviewed primary [PMID19713235 / PMC3272664](https://pmc.ncbi.nlm.nih.gov/articles/PMC3272664/): psyllium10g/day versus bran/placebo in275 adults with IBS, with primary adequate-relief benefit in months1–2; no new dose judgment at400mg is made. Preserve the distinction between ingredient evidence and applicability/adequacy.

**Oat bran:** [PMID19214342 / PMC12877458 / DOI10.1007/s12603-009-0020-2](https://pmc.ncbi.nlm.nih.gov/articles/PMC12877458/) is a small controlled parallel intervention,30 frail geriatric residents,15/group,7–8g/day common oat bran mixed into food for12weeks. Laxative use reduced, bodyweight retained; stool frequency did not significantly change. Random allocation is not established in the read methods. Common oat bran has direct human intervention evidence; it is not confined to beta-glucan extracts. Neither geriatric feeding context nor tested mass establishes this200mg capsule's benefit. Existing literature record's unestablished applicability can remain bounded; an empty qualifying-study list must not be represented as proof that human oat-bran studies do not exist.

**Wheat bran:** same [PMID19713235](https://pmc.ncbi.nlm.nih.gov/articles/PMC3272664/) directly compares10g/day bran with psyllium and rice-flour placebo for12weeks. Bran's month3 apparent adequate-relief benefit disappears under worst-case missing-data analysis; symptom-severity change is not significant versus placebo, and early withdrawal was most common with bran, often from worsened IBS symptoms. Preparation-specific mixed/null/tolerability evidence; no universal IBS efficacy or harm and no claim for200mg powder. Particle size remains undeclared.

**FOS:** direct primary evidence exists but needs preparation/outcome limits:

- [PMID17697398 / DOI10.1017/S000711450779894X](https://doi.org/10.1017/S000711450779894X): Actilight950P, chemically described GF2/GF3/GF4 preparation,5g/day for6weeks,105 adults with minor functional bowel disorders randomized. Positive symptom-intensity/discomfort findings are reported in the50-person per-protocol subset; symptom-frequency change nonsignificant. Eight withdrew and47 were less compliant. Supplier-affiliated authors, narrow population, adherence selection and missing registration/endpoint hierarchy limit certainty. This does not establish500mg genericFOS or ColonCare efficacy.
- [PMID27477485 / DOI10.1111/nmo.12911](https://pubmed.ncbi.nlm.nih.gov/27477485/):79 IBS patients with rectal hypersensitivity, scFOS5g/day for4weeks. Primary rectal-sensitivity and IBS/QoL changes similar to placebo; post-hoc constipation subgroup P=.051. Bifidobacteria/anxiety findings do not replace the null primary outcome. Live abstract content-verified; publisher full-text access403 is retained as a limitation.
- [PMID16569219 / PMC1448190](https://pmc.ncbi.nlm.nih.gov/articles/PMC1448190/):40 healthy volunteers, Actilight scFOS2.5–10g/day,7days. Bifidobacteria rise, no significant Lactobacillus change. Microbiological surrogate, not clinical colon-health efficacy. More intense bloating at2.5/5g/day prevents a universal tolerability claim. Paper is a focused report from a larger carbohydrate study, not an independent second replication of that cohort.
- [PMID37614109 / PMC10453972](https://pmc.ncbi.nlm.nih.gov/articles/PMC10453972/):106 healthy adults, HN019+HN001+FOS500mg/day,8weeks. Formula/immune-surrogate evidence; no FOS-only arm and no LA-acidophilus match. Same FOS mass is not sufficient identity or efficacy attribution.
- [PMID30388751 / PMC6266108](https://pmc.ncbi.nlm.nih.gov/articles/PMC6266108/):infants with constipation,100%FOS DP2–6,6/9/12g/day by weight,36 completers,4weeks. Primary therapeutic success nonsignificant (one-sided P=.073), secondary stool/straining findings positive. Infant/pediatric preparation not applicable to adult ColonCare.
- [PMID25292404 / PMC4737566](https://pubmed.ncbi.nlm.nih.gov/25292404/):nine elderly peritoneal-dialysis patients,20g/day FOS crossover, bowel-frequency/consistency improvement. Specialist population/dose cannot become generic adult500mg evidence. Live abstract verified; XML endpoint500 twice, so no full-method attribution beyond accessible source.

L. acidophilus in this label remains strain-unspecified. [PMID12368393](https://pubmed.ncbi.nlm.nih.gov/12368393/) factorial study of FOS6g/day and acidophilus2B CFU/day in68 healthy adults is not this preparation; abstract findings concern fecal metabolites, including unfavorable acidophilus-associated protein catabolites. Species overlap is insufficient trial identity and surrogate findings cannot become positive digestive benefit.

### 19171 — CVS Pharmacy Probiotic Acidophilus

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/19171), retained raw path recorded in manifest. One capsule/day;1mg preparation with over100M active organisms at manufacture, including naturally occurring metabolic products. Forms array empty and no code in statements. Known species/label count; insufficient exact strain. Readiness one individual row unevaluated, aggregate not applicable. No numerical or efficacy transfer from another CVS product.

### 19172 — CVS Pharmacy Probiotic Formula Acidophilus

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/19172). One tablet/day;10mg,1B CFU, minimum1B live bacteria manufactured and undefined effective level at best-used-by. No code in ingredient/forms/statements. Insufficient strain identity; same species as19171 does not prove same strain or clinical formula. One individual row unevaluated, aggregate not applicable.

### 19890 — up&up Acidophilus

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/19890). One tablet/day;25mg,1B CFU in row notes, no strain or mixed formula code. Insufficient strain identity; SD-5845 label12091 is a different preparation and organism. One individual row unevaluated, aggregate not applicable.

### 264105 — Solgar Advanced Acidophilus

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/264105). Exact LA-5 named in `ingredientRows[0].forms[0]`;5mg preparation and500M CFU per capsule explicitly stated. Directions1 capsule twice/day, not a conversion from mass. No BB-12 or other organism is declared. Distinct Solgar Acidophilus Plus formulas do not apply. One individual row unevaluated, aggregate not applicable.

Independent live primary XML [PMID36198994 / PMC9534588](https://pmc.ncbi.nlm.nih.gov/articles/PMC9534588/) confirms a monostrain LA-5 trial,80 women with vulvovaginal candidiasis, triple-blinded LA-5+matching fluconazole-placebo versus fluconazole+matching probiotic-placebo. Hansen LA-5 with potato starch,1e9CFU/g,30capsules. No untreated placebo-only arm. First follow-up negative cultures27.8% vs45.5%,P=.127; later follow-up worse LA-5 culture clearance, with inconsistent body/abstract P and table percentage. Similarity/non-significance is not equivalence, superiority or demonstrated efficacy versus no treatment. Vaginal candidiasis is not gut-health outcome. Study reporting conflicts include follow-up dates and denominators; route remains insufficiently literal in reviewed publication/registry, so no route equivalence is asserted. Prepared IRCT50819 receipt reused (500mg capsule/CFU concentration); no CFU/day reconstruction or Solgar formulation linkage.

Disposition: exact named strain with direct human monostrain experiment, bounded comparator/null-or-negative evidence and digestive-context inapplicability. Correct an absolute combination-only factual statement; retain evidence_level none, withdrawn ex-vivo citation and clinician-history/hold unless existing authority separately reviews them. This source grants no positive score.

### 35694 — Nature's Bounty Extra Strength Acidophilus Probiotic Gold

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/35694). Two tablets/day,5mg and1B CFU per2-tablet serving at manufacture; naturally occurring metabolic products included. Empty forms, no code. Insufficient strain identity. Current branded products, LA-14 references or unrelated Probiotic Gold organisms cannot identify archived label. One row unevaluated; aggregate not applicable.

### 46802 — Member's Mark Acidophilus / Bioflora

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/46802). One caplet/day; Bioflora10mg parent containing active L. acidophilus2B organisms, count at manufacture. Raw child unit `{Unit(s)}` has an existing product-specific CFU correction; it supplies no strain/formula identity. Both material evidence rows unevaluated, aggregate not applicable. Parent and child describe one contained preparation; no double organism or mass-to-CFU conversion.

Independent live [PMID34267437 / PMC8240938](https://pmc.ncbi.nlm.nih.gov/articles/PMC8240938/) confirms Tak Gen Zist Iranian Bioflora with T16/BIA6/BIA7/BIA8 in5g powder, with15g prebiotic mixture or placebo, hemodialysis population. Different maker/preparation/four-species formula. No supplier/deposit linkage found to Member's Mark. It is inapplicable, not supportive evidence for this unnamed acidophilus. Prior NIH PDF retained; API content is independently verified, but PDF image confirmation remains unperformed.

### 65049 — Spring Valley Acidophilus

[Official NIH label](https://api.ods.od.nih.gov/dsld/v9/label/65049). One caplet/day;5mg,1B CFU at manufacture. No code in row/forms/statements. Insufficient exact strain identity; current LA-14 or other Spring Valley versions do not identify this historical record. One row unevaluated; aggregate not applicable.

## Factual registry findings and bounded follow-up

1. **Confirmed factual defect: LA-5 absolute combination-only assertion.** Exact owner `scripts/data/clinically_relevant_strains.json::clinically_relevant_strains[id=STRAIN_ACIDOPHILUS_LA5].notable_studies`, especially “Human trials test it only in combination”. PMID36198994 proves otherwise. Adjacent `cfu_thresholds.dr_pham_signoff_verification_note` is dated review history; preserve original attribution, append/reopen with separately attributed current receipt rather than silently rewriting what Dr Pham reviewed. Evidence_level none is not disproved, and the source does not justify gut benefit or dosing tiers.
2. **Confirmed factual ambiguity: oat health-claim mass basis.** `scripts/data/ingredient_quality_map.json::oat_bran.description` says “FDA-approved heart health claim at3g/day” without specifying beta-glucan; its `.forms.oat bran (unspecified).notes` correctly distinguishes beta-glucan. Live [21CFR101.81(c)(2)(i)(G)(1)](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/subpart-E/section-101.81) requires3g/day beta-glucan soluble fiber from eligible whole oats/barley, not3g oat-bran mass. Harmonize description to its existing notes; no dose policy change required. Reviewed source PMID25411276 likewise measures beta-glucan, not generic powder. Existing unspecified consumer note remains honest.
3. **Limited source-description boundary: FOS Lactobacillus preferential-feeding claim.** IQM `prebiotics.forms.fructooligosaccharides (FOS).notes` universally says preferentially feeds Bifidobacterium and Lactobacillus. Live single-preparation PMID16569219 shows Bifidobacterium increase and no significant Lactobacillus change. This does not falsify every mechanistic experiment, but it does disallow using the sentence as established clinical Lactobacillus/acidophilus benefit or a universal response. Factual curation can bind prose to specific verified preparations/results; do not invent positive clinical efficacy. Consumer note identifies FOS class and need not change.
4. **Not a proven factual defect: oat literature applicability record.** Existing `literature_evidence_records.json` has oat_bran/“crude_material_lacks_standardization”, empty qualifying list. That can be defensible for this unstandardized200mg label, but direct human common-oat-bran evidence exists. Preserve label non-applicability while recording actual studied preparation/population/results; do not treat the empty list as absence of all clinical studies.
5. **Readiness remains an integration question, not a research omission.** `evaluate_evidence_assessment` only recognizes linked reviewed records or existing native strain assessment states. A research markdown receipt alone cannot change persisted completeness. Insufficient identity is a completed bounded review conclusion, but cannot manufacture native strain evidence. Integrator must use existing owners/contracts and keep remaining manufacturer-linkage limits visible. No new statuses or numerical policies selected here.

The entire requested batch has now been inspected. Next work is one combined factual curation/applicability integration packet with existing owners, explicit null/inapplicable/insufficient-identity boundaries, fail-first defect-class tests and measured affected-label replay. No request to manufacture strain codes or positive grades. Evidence closure must distinguish reviewed-as-limited from demonstrated benefit and from runtime integration.

## Receipt/access ledger

Files:9 `live_dsld_ID.json`;7 live full-text XMLs and extracted review text (LA5,Bioflora,oat,wheat,FOS-infant,FOS-bifidogenic,FOS500mg-combination); EuropePMC core records for exact-coded search, LA5,oat-primary,oat-beta-glucan,FOS symptom/IBS/factorial/combination/bifidogenic/dialysis; Cambridge FOS full HTML/text and current CFR HTML/text. Reused prepared SD-5845/Bioflora search, IRCT50819 and46802PDF retain source provenance. `raw_review.json` records label/source SHA256 and field equality. `source_manifest.json` maps receipt URLs and read dates.

Limits: no exhaustive manufacturer archive/deposit census; no inferred current marketed strains; no route/dose equivalence from unclear trial language; Bioflora PDF image unconfirmed; Wiley full text403; CAPD XML500 twice (live abstract available). No guessed identifiers used in findings. No corpus/tests/source mutation or release; no measurement claims.


# Cross-family clinical completion packet — 2026-10-02

Read-only baseline: `753aa5cf3a9062695c362133cff753975cb305da`. Eight families assessed together. No repository edits, tests, replay, grading changes, registry additions or releases. Goal: source facts and clinical applicability before numerical calibration. Existing clinician holds and clinician-reviewed summaries remain in force. This packet is a bounded review of indexed/current references, not a systematic discovery claim or clinician sign-off.

## Owner check and provenance

Owner: `scripts/data/backed_clinical_studies.json::{BRAND_SUNFIBER,INGR_INULIN,FORMULA_SEED_DS01,BRAND_LACTOSPORE}`, `scripts/data/clinically_relevant_strains.json::{STRAIN_COAGULANS_IS2,STRAIN_COAGULANS_MTCC5856}`, and existing IQM `prebiotics.forms`/`bacteriophages.forms` notes. Runtime evidence owner: `scripts/probiotic_measurements.py::{effective_strain_evidence,derived_context_evidence}`, existing enrichment matcher, `clinical_applicability::assess_clinical_applicability`, route Dose and generic Evidence. Evidence: matrix and glossary inspected; canonical entries recursively extracted into `canonical_snapshot.json`; names/stems searched and runtime owner read. Will NOT create: registry, scorer, matcher, public field/status, numerical benchmark, sponsorship deduction or ranking eligibility classifier.

Read current handoff, master-plan clinical sequence, and `.claude/skills/data-fix/SKILL.md`. Source-correction workflow applies per entry; research receipts do not authorize replacing clinician meaning. Earlier memory supplied only the warning to distinguish structure from clinical content and legacy precedence; current records/primary content independently checked.

Reused same-day saved primary receipts from PHGG, inulin, XOS, GOS and PreforPro folders. Several earlier `primary_review.md` files identify defects subsequently fixed; they are source receipts, not a present defect inventory. Current canonical notes were checked against them. Independently retrieved all 18 unique Seed/IS2/LactoSpore current citation identities from live Europe PMC, 11 available linked full texts plus the separately retrieved pediatric full text (12 full articles total). `live_source_receipt.json` records successful URLs and failures; `sources/<PMID>_epmc.json` preserves full live indexed abstracts/affiliations, `<PMID>.xml/.txt` preserve open primary articles. PMID38269290 has no PMCID in the live search metadata, but known PMC10806110 fullTextXML was retrieved independently. No abstract-only claim below is represented as a full methods check.

## One disposition per family

| Family | Preparation, population and exact dose basis | Outcome hierarchy and direction | Trial independence/funding; disposition |
|---|---|---|---|
| PHGG / Sunfiber | Both indexed papers explicitly Sunfiber. Rome III adult IBS: 3 g preparation/day for week 1, then 6 g/day for 11 weeks. Healthy Japanese loose-stool adults, IBS excluded: 5 g preparation/day for 12 weeks, distinct from 3.5–4 g dietary-fiber assay mass. | 2016 primary symptom/severity/QOL set: bloating/gas positive; pain, overall severity, stool frequency and QOL null. 2019 primary stool form positive selectively, frequency null; Bifidobacterium abundance secondary surrogate. No measured SCFA increase or clinical immune benefit. Published hierarchy verified, prospective registry history/SAP not verified. | Two distinct trials, distinct populations/questions; neither independently funded. Pro Natura/Sunwic support in 2016 with operational-independence claim; Taiyo protocol/product/funding and employee authors in 2019. Current factual corrections sound. Retain narrow digestive signal; strong/tier1/raw18 normalization to Evidence20 remains a policy decision, not a source-established certainty conclusion. |
| Inulin / FOS | Inulin-type fructan family, including oligofructose/scFOS, is broader than one preparation; chicory restriction belongs to PMID35833477. Its reported exposure range is 3–20 g/day. Chain length/preparation matters, especially mineral outcomes. Do not assign every product one universal dose from pooled reviews. | Strong consistent bifidogenesis is surrogate. Healthy-adult review reports 11 positive/9 null stool-frequency studies; calcium absorption, balance and serum values differ. Cardiometabolic synthesis low/very-low certainty risk-factor outcomes, not events. Reviews do not turn each included endpoint into primary efficacy for every preparation. | Overlapping review populations cannot be summed as independent trials/enrollment. General Mills support for PMID34555168; BENEO indexed funding/affiliations for35833477; precise latter/full38309832 roles remain access-limited. Current factual notes/scope correction acceptable; FOS alias denotes family evidence, not molecule identity or universal clinical equivalence. Evidence15.6 is frozen pending cross-family policy. |
| XOS / PreticX | Finegold2014: healthy adults, 32; 1.4/2.8 g/day for 8 weeks in abstract/indexed methods. Supplier Life Bridge, manufacturer Shandong Longlive; original purity and explicit PreticX linkage unverified. Yang2015: 16 healthy/13 prediabetic; 2.8 g/day 70% powder (1.96 g, authors round to2 g XOS), 8 weeks. | Bifidobacterial/microbial measurements, tolerability; no established symptomatic disease efficacy. Yang metabolic endpoints null, insulin trend nonsignificant. Finegold stool mass/pH/SCFA null; graded GI symptom diaries are tolerability, not constipation treatment. Do not transfer2015 purity backward to2014. | Separate trials with major team overlap, not independent-team replication.2015 departmental support and supplied products;2014 funding unresolved. Current zero Evidence means absent reviewed clinical owner, not absent research. Clinical credit magnitude and preparation eligibility need an approved determination; no minimum-dose benchmark justified. |
| GOS / Bimuno | B-GOS2018: symptomatic adults without diagnosed GI disease, 2.75 g powder/day explicitly1.37 g active GOS, two-week crossover periods.2015 healthy65–80y:5.5 g48% powder/day=2.64 g active, ten-week periods. Silk2009 IBS:3.5/7 g preparation/day; original composition/full tables unavailable. |2018 short-term pain/bloating/flatus/global symptom signal; stool frequency/consistency, mood/QOL null.2015 microbiome/immune biomarkers, bowel/mood null.2009 lower arm symptom benefits, higher arm mainly global/anxiety signal; not a monotonic symptom dose-response. Do not treat immune biomarkers as clinical prevention. | Distinct trials but overlapping investigators/Clasado product/funding and affiliations; no independent-team replication claim. Current broad efficacy note corrected. Retain preparation-specific symptom research; universal GOS equivalence/benchmark/positive grading not authorized by source alone. |
| PreforPro | Four named E.coli-targeting phages. PHAGE15 mg capsule/day, reported10^6 phages/dose,28-day crossover periods. PHAGE2 BL04 10^9 CFU plus10^6 PFU same phages,15 mg capsule/day,4 weeks; no phage-only arm. Capsule/carrier mass is not active potency. | PHAGE symptoms improved in both arms/carryover; companion microbiome report not separate trial. Selective microbial/IL4 findings, most biomarkers/SCFA null. PHAGE2 no significant between-arm symptom-score change, despite positive within-combination changes; powered for microbial endpoint. 'GI inflammation' questionnaire measures perceived symptoms. | PHAGE reports30157383/30897686 same NCT03269617. PHAGE2 separate NCT04511221, related team, Deerland support/protocol/product. Current notes corrected. Do not borrow combination symptom credit for phage-only or arbitrary probiotic blends; zero current Evidence is not no human research. |
| Seed DS01 | Complete24-strain+pomegranate ViaCap formula, native53.6B AFU/day+400 mg>40% polyphenol extract. Symptom trial starts1capsule/day3days then2/day;6weeks. Mechanistic91day trials2capsules/day; one includes7day cipro/metronidazole challenge. No AFU→CFU conversion/per-strain allocation. |41599868 primary DQLQ positive; bloating/gas and pain secondary positive.350 baseline/219week6.40944126 primary microbial composition; metabolite/CRP secondary surrogates including subgroup/correlation interpretations.41750436 proof-of-mechanism, microbial/barrier endpoints; no demonstrated antibiotic-diarrhea prevention. | Symptom study separate from mechanistic protocol;40944126/41750436 share NCT04171466, participant overlap unresolved, never summed as independent symptom replication. Seed funding/employee shareholder/advisory authors; operations described independent. Current formula scope/native potency correct; preserve positive_weak baseline, specify endpoint hierarchy and titration factually. No current reproduced formula mismatch. |
| Unique IS2 | Exact strain. Adult IBS2B CFU/day8wk; constipation2B CFU/day4wk; newer healthy infrequent-BM144participants2B/day4wk. Pediatric IBS chewable8wk, daily CFU not resolved by accessible abstract. Lactulose adjunct2B spores/day+10 g lactulose4wk. Whey study2B CFU/day+20 gWPC powder (15.4 gprotein)60days in trained men. COVID2B spores twice/day14days with standard care. | Adult IBS pain/CSBM primary positive, cytokines null. Newer healthy study BM frequency primary positive; consistency secondary positive; GI/QOL/microbiota null. Lactulose frequency transient, endpoint null vs lactulose; adjunct interpretation retained. Protein absorption surrogate/performance population cannot substantiate digestive benefit. Constipation meta's class-positive response does not establish IS2 subgroup frequency (null). COVID respiratory/clinical comparisons null despite selected biomarker positives. | Distinct trial families, frequently manufacturer investigators.31434935 fully Unique-funded;40456531 PepsiCo/Nutrasource authors (funding roles not full-text-verified).2026 meta pools pediatric+adult trials; not new independent cohort and age mixture/high heterogeneity explicit. Clinician-reviewed legacy35249118 remains controlling; its q2=NO gastrointestinal applicability conflict is confirmed, while credit correction requires existing gate/owner assessment. Do not replace signoff automatically. |
| LactoSpore MTCC5856 | Exact strain; IBS-D2B CFU/day90days with domperidone/esomeprazole/metronidazole in both groups, not monotherapy. MDD+IBS2B spores/day90days selected untreated population. Gas/bloat2B spores/day4wk. Healthy-microbiome one2B CFU capsule/day28days. Pediatric acute diarrhea4e8 spores/sachet twice/day=8e8/day5days with ORS/Zn. | IBS-D declared primary symptoms positive, QOL secondary. MDD+IBS HAM-D/MADRS/CES-D/QOL primary positive; MPO within-group surrogate. Gas/bloat GSRS/global primary positive. Healthy global composition essentially null. Pediatric duration primary positive/frequency primary null; no adult maintenance inference. Meta SUCRA ranking is not efficacy;2026 QOL synthesis pools same2016/2018 trials. | Manufacturer-run/team-linked studies; distinct conditions cannot count as replication of one question.2018 explicitly Sabinsa-sponsored;2023 papers declare no funding disclosed but manufacturer employee affiliations. Current tier1/positive_strong branded summary not independently ratified. Correct verified context metadata and unsupported immune goal without creating new grade/benchmark. |

## Confirmed current factual defects and bounded source corrections

F1 — `STRAIN_COAGULANS_MTCC5856.study_contexts[mtcc5856_healthy_microbiome_37335737].dose.basis` and `limitations`: says daily dose unresolved although daily value/verified status already stored. Primary Methods2.4 explicitly one capsule orally once daily after dinner,2B CFU/capsule for28days. Correct the contradiction to verified daily arm and remove the false limitation; no new benchmark. Receipt: `sources/37335737.txt:21,27` / XML; [primary](https://pmc.ncbi.nlm.nih.gov/articles/PMC10194586/). Source factual completion, not positive efficacy.

F2 — All five MTCC5856 RCT contexts `blinding=unreported` contradict source title/Methods double-blind. Registers incorrectly null for IBS-D26922379 (CTRI/2014/03/004502), MDD29997457 (CTRI/2015/05/005754), gas/bloat36862903 (CTRI/2019/06/019617) and microbiome37335737 (CTRI/2018/10/015913). Correct blinding metadata. Published CTRIs are research leads only: do NOT insert or replace registration fields until live official registry content is independently verified; that access was not completed here. Keep prospective-history verification separate. Gas/bloat limitation 'endpoint hierarchy not stated in abstract' is false: current abstract explicitly identifies primary/secondary. Receipts: same-named saved primary XML/text files;26922379:23,29997457:22,36862903:6/30/124,37335737:23/146;38269290 abstract/Methods for fifth blinding confirmation. [IBS-D](https://pmc.ncbi.nlm.nih.gov/articles/PMC4769834/), [MDD](https://pmc.ncbi.nlm.nih.gov/articles/PMC6034030/), [bloating](https://pmc.ncbi.nlm.nih.gov/articles/PMC9982755/).

F3 — `STRAIN_COAGULANS_IS2.study_contexts[is2_moderate_covid19_adjunct_39866999].population.description/limitations` misnames comparator UBBC-07 as B.coagulans. Source title/Methods identify **Bacillus clausii UBBC-07**. Correction affects comparator description only, not IS2 identity. Receipt:`sources/39866999.txt:1,7,33`; [primary](https://pmc.ncbi.nlm.nih.gov/articles/PMC11763649/).

F4 — Same COVID context limitation 'inflammatory-marker surrogates only' omits measured clinical recovery/respiratory outcomes and their null between-group comparisons. Source Results reports oxygen saturation,respiratory rate and clinical recovery; no significant between-group differences. Correct limitation/add source-qualified null clinical result under existing outcome representation; hierarchy must remain unresolved unless verified. Dose4B/day correct. Blinding is incorrectly unreported: paper describes double-blind. CTRI/2021/03/031720 is a published registry lead only; leave registration null until official live record content verification. Source explicitly declares no financial support, distinguish that from generic 'unreported'. Receipts:`sources/39866999.txt:25,33,51,90–96` / XML. No claim it treats COVID or worsens clinical outcomes.

F5 — `BRAND_LACTOSPORE.health_goals_supported` includes 'Immune Support'; its two cited trials26922379/29997457 establish selected GI/depression/QOL findings, not measured clinical immune benefit. MPO is an inflammatory surrogate/within-group result, not infection prevention. Remove or qualify this unsubstantiated goal under existing source-correction policy; preserve reviewed strain summary/signoff and numerical policy. Receipts:`sources/26922379.txt:32,60`;`29997457.txt:10,66,83`; current brand entry snapshot still needs inclusion in integrator batch. This is lack of support in this exact record, not a global claim that no immune research exists.

F6 — `STRAIN_COAGULANS_IS2.cfu_thresholds.evidence` pairs gut-health indication with athlete+whey PMID35249118; record's own validation says q2 outcome relevance NO. Live source confirms absorption/leg-press/vertical-jump, not IBS/constipation. `effective_strain_evidence` retains clinician legacy when human summary asserted. Confirmed source/applicability conflict, **not yet a reproduced matcher eligibility defect** in this lane: integrator must inspect current scoring probe on real IS2 products before changing credit. Replacing clinician-owned citation/grade or overriding its gate needs applicable reviewer authority. Receipt:`sources/35249118_epmc.json`, canonical snapshot, `scripts/probiotic_measurements.py:776`; [primary abstract](https://pubmed.ncbi.nlm.nih.gov/35249118/). Correct digestive source eligibility, not 'no human research'.

F7 — MTCC5856 gas/bloating and healthy-microbiome contexts hardcode `funding=industry`, although full papers state no funding disclosed. Employee affiliations demonstrate commercial involvement, not verified financing. Correct/qualify provenance using existing funding enum after schema check; keep affiliation caveat. Receipt:`sources/36862903.txt:125` and`37335737.txt:142–143`. No sponsorship penalty or claim of financial independence follows.

Seed factual completion: record is accurate about formula,AFU,attrition and mechanistic scope. Its summary could explicitly say primary DQLQ/secondary symptoms and first3day titration. These are source detail additions, not confirmed false identity or current matcher defect. Receipt:`sources/41599868.txt:19,21,28`; [primary](https://pmc.ncbi.nlm.nih.gov/articles/PMC12845427/).

No additional current PHGG/inulin/XOS/GOS/phage factual defect was reproduced after their integrated source corrections. Their remaining unknowns above must stay open; zero scores do not close clinical review. No matcher eligibility defect is claimed solely from source absence or from a desirable rank.

## Cross-family decision packet for Sean

Apply the same existing facts first: named preparation is not generic family equivalence; patient-important between-group outcomes differ from biomarkers, within-group changes, subgroups and network rankings; papers/reviews are not independent new trials; population and co-therapy restrictions remain visible; active/preparation/carrier/AFU/CFU quantities stay distinct. These boundaries already exist and need no new policy owner.

What needs a clinical/numerical decision after corrections: whether PHGG's selective positive trials warrant retained positive_strong/tier1 compared with Seed's single positive primary-QOL trial, IS2's different populations and LactoSpore's small condition-specific pilots; clinical credit for preparation-specific GOS/XOS/phage under the existing owner; any new preparation-specific Dose benchmark or approval of industry1B/10B/50B CFU tiers as clinical adequacy. Do not infer these magnitudes from dose studied, funding, brand or a target score. Funding is descriptive; no new deductions. Inulin's pooled heterogeneity cannot become universal preparation equivalence.

Preserve frozen scores until verified owner corrections or approved policy justify movement. Subsequent implementation must use fail-first per defect class, source-by-source content checks, exact expected data batch, targeted tests and bounded real-label replay; then one integrator checkpoint. Full corpus/release and clinician holds remain open. This research packet itself proves neither score changes nor release readiness.

## Concrete batch handoff

`patch_proposals.json` supplies 15 exact before→after field proposals for F1–F5/F7, including source locations, authority and consumer. Existing metadata enum supports `blinding=double`, `funding=unreported`; it has no 'none_declared' value, so use unreported plus explicit disclosure prose, never independent. No registration change is proposed because official live registry content was not verified. Source-reported identifiers remain retrieval leads only. `lactospore_brand_snapshot.json` captures the exact current brand fields.

Full primary Methods/Results are saved in XML/text; bounded exact excerpts for reviewer navigation:

- PMID37335737 Methods2.4: “Subjects were randomly assigned to receive either 1 capsule”; the same sentence continues with once-daily-after-dinner timing. Full paragraph21/27 establishes2B CFU/capsule and daily frequency. This is fixed trial administration, not industry adequacy or generic preparation equivalence.
- PMID36862903 abstract: “global evaluation of patient’s scores from screening to the final visit were the primary outcomes.” Methods2.7 independently declares hierarchy; source paragraphs39–40 and52–65 retain outcomes and between-group results.
- PMID39866999 Results: “no significant differences (p > 0.05) were observed between the treatment groups”; paragraph51 specifies respiratory/clinical context. Methods33 distinguishes B.clausii UBBC-07 from B.coagulans IS2 and preserves standard-care co-therapy.
- PMID26922379 Methods: “The primary efficacy outcomes were measured by”; paragraph32 lists questionnaires/stool/pain, and paragraph60 plusTable4 preserves positive results. The title and blinding paragraph25 independently support double-blind.
- PMID29997457 Methods: “The primary outcome for this study was a mean 90-day change”; paragraph66 lists depression/QOL outcomes;83 is the full efficacy table and118 explicitly describes Sabinsa support.
- PMID38269290 Methods: “The primary efficacy endpoints were the mean duration of diarrhea”; paragraph40 also identifies frequency, with secondary perceived efficacy/dehydration. Paragraph38 proves sachet twice-daily8e8 spores/day. Paragraph71 preserves frequency-null.

F6 has no numerical replacement patch proposed: its current legacy summary/signoff owns clinical meaning. Keep clinical holds, fail-closed scope and reviewer provenance. Parent must reproduce downstream digestive eligibility before altering credit. Existing Dose tiers remain industry convention; neither correcting dose.basis nor descriptive funding/blinding is expected to supply new points. Metadata correction can clear a native-context inconsistency, so verify owner consumers and measured impact rather than promise identical scores. Seed hierarchy/titration can be added to existing prose without changing full-dose formula identity requirements, but is optional factual completeness rather than a demonstrated false field.


### Combined candidate dispositions and review correction

Research findingF6 does not establish athlete+whey35249118 driving digestive points. Three synthetic amount scenarios and real332954/328090 identify IBS31434935 as the16-point native winner. The reproduced defect was descriptive scoring provenance, now fixed through the sole Evidence owner. Clinical grade/signoff changes are not authorized by that source finding.

Accepted344-label replay at51595506:150capture deltas,54internalDose changes (three round away),51publicDose-only changes (50drops/one+0.4),96metadata/copy-only captures;25quality-tier downgrades/no upgrades,zero routes/statuses/readiness/Safety gates or other pillar scores changed. All input/output hashes and436tracked candidate source hashes checked. Five ignored FDAcache/bulk files present only in baseline are an environmental difference; do not claim full-environment/release equivalence. The initial intermediate snapshot was rejected by its source-mutation guard and excluded.

Independent reviewer accepted source/alias/provenance/adversarial and all150per-ID delta classifications in durablefresh_review.md. Positive219977: removing the wrong0.4ALCARcoverage term changes existing mean9.7712→10.3099 and breadth1.3333→1.1667; rawDose13.6045→13.9766,public11.8→12.2,total60.1→60.5. This uses existing denominator policy, not a new benchmark or risk improvement. That denominator remains in the approval packet.

Local527pass/24approved opt-in skips; two earlier worktree mount omissions were refused by the skip guard, then existing main corpus/dist/build/canary/baseline artifacts were connected and checked.51595506CI had one stale historical Wave2 fixture assertion: corrected records differed from old hardcoded authoring facts.59d96720 updates only those six fixture facts plus3adversarial rerun regressions; no equality/status/source guard relaxed, no registry writes or runtime score changes. Exact final CI/integration status is in LEDGER/masterplan.

## October 4, 2026 — Nature Made magnesium capsule certification aliases

Owner: scripts/cert_resolver.py::resolve/_check_override, existing cert_verification_overrides.json; certification_evidence matrix entry. Will NOT create: matcher, alias registry, magnitude, score policy or export field.

Primary verification: retrieved https://www.quality-supplements.org/usp_verified_products?page=12 using the existing listing parser on October4; HTTP200, capsule entry “Nature Made High Absorption Magnesium Glycinate 200mg Capsules” links to https://www.naturemade.com/products/high-absorption-magnesium-glycinate-200-mg-capsules?variant=34480293576843. The separate gummy entry links to the gummy page. Saved response/parser receipt: /Users/seancheick/pg_quality/certification_match_20261004/usp_page12.html and usp_live_check.json. Existing sourced record USP_VERIFIED_EED67511C424 supplies certification provenance/recency; its September16 verification date is preserved. The official capsule page independently shows USP Verified,200mg per two capsules,60 capsules. No new efficacy/safety claim or clinical identifier added.

- DSLD310116: reviewed frozen NIH label, Nature Made, “Magnesium Glycinate200mg”,60 Capsule(s),30 servings,2 capsules/serving,200mg magnesium as Magnesium Bisglycinate. Nutrition panel additionally has calories/carbohydrate/protein; these do not identify a different magnesium intervention. Result: same USP-listed200mg capsule product; reviewed SKU alias bound to310116, explicit capsule form and200mg strength in alias. No gummy/preparation borrowing.
- DSLD322551: reviewed frozen NIH label, same brand/title,60 Capsule(s),30 servings,2 capsules/serving,200mg magnesium as Magnesium Bisglycinate. Result: same USP-listed200mg capsule product; separate reviewed SKU alias bound to322551, explicit capsule form and200mg strength. No transfer to unreviewed DSLD IDs.

Root cause: both source titles omit High Absorption; the existing conservative resolver requires those registry qualifiers unless an explicit reviewed alias exists. Kept that rule and used its canonical reviewed-override mechanism. Existing raw strength/form/population, delisting, recency and brand gates still apply. Full Nature Made glycinate-label census found these two missing capsule mappings and separately certified gummy313829. Frozen raw cohort:310116,322551 plus313829,298074,299065,294015 controls. Measurements/checkpoint are recorded in LEDGER/master when complete; this receipt itself is identity/source review, not release acceptance.


## October 4, 2026 — Certification renewal: complete recognized-program source inventory

Owner: `scripts/api_audit/verify_certifications.py` fetchers/parsers and `scripts/cert_resolver.py` matching; `scripts/scoring_v4/cert_evidence.py` consumes existing verified evidence. Will NOT create: another registry, matcher, score owner or public field. This is source research, not automatic approval of new program capabilities or numerical credit.

Reviewed all 23 current `third_party_programs` entries, their exact `verified_capabilities`/`implies_gmp` declarations and nine existing fetchers. There are eight named product-program capability mappings; NSF GMP is the ninth, facility-scoped fetcher. Detection rules and `points_if_eligible` alone do not demonstrate current verified database coverage or justify new capability activation. Durable policy snapshot and 35 primary-response receipts (including failures, URLs, dates and hashes): `/Users/seancheick/pg_quality/certification_renewal_20261004/source_research/`. URLs below were content-checked on October 4, 2026; successful page retrieval is not proof of exhaustive source pagination.

| Existing rule | Official listing / standard reviewed | Scope and current policy boundary | Fetch / renewal disposition |
|---|---|---|---|
| USP Verified | [USP directory](https://www.quality-supplements.org/usp_verified_products) | Named supplement SKU; existing purity/heavy-metal/label-accuracy capabilities and GMP implication. | Existing paginated fetcher; direct research request403, prior capsule-specific response200. Treat blocked retrieval as unavailable, never removal or renewal. |
| NSF Sport | [Product directory](https://www.nsfsport.com/certified-products/) | Named products and tested lots; broader contents testing plus prohibited-substance screening. Existing capabilities/GMP. | Existing live directory/detail fetcher; preserve exact product/lot restrictions, require all detail retrievals. |
| NSF Contents Certified | [NSF/ANSI173 official listings](https://info.nsf.org/Certified/Dietary/Listings.asp) | Finished-product trade designation, form and daily serving; raw ingredients can appear separately. Existing capabilities/GMP. | Existing HTML fetcher; distinguish Finished Products from ingredient/facility sections. |
| ConsumerLab | [Quality Certification listings](https://www.consumerlab.com/quality-certification-program/certified-products/) | Voluntary named-product certification; paid member reviews are a separate population. Existing capabilities. | Existing public fetcher. Current bold listings have24-month certification; historical rows must not gain freshness merely because retrieved today. |
| Informed Sport | [Process](https://sport.wetestyoutrust.com/about/certification-process) and [directory](https://sport.wetestyoutrust.com/certified-products/) | Product and batch prohibited-substance screening. Current broader capability list empty; GMP implication declared. | Existing paginated fetcher; preserve regional/form/lot distinctions. Do not infer general heavy-metal or label-accuracy testing. |
| Informed Choice | [Process](https://choice.wetestyoutrust.com/about/certification-process) and [directory](https://choice.wetestyoutrust.com/certified-products) | Recurring prohibited-substance testing; not the every-batch Sport program. Broader capabilities empty; GMP implication declared. | Existing paginated fetcher; do not promote Choice into Sport. |
| BSCG | [Database](https://www.bscg.org/certified-drug-free-database), [Drug Free process](https://www.bscg.org/certified-drug-free-supplement-certification-process) | Certified Drug Free product/lot program, label and contaminant requirements; distinct BSCG programs are not interchangeable. Existing purity/label accuracy, no heavy-metal capability. | Existing AJAX/detail fetcher. Keep selected program, brands and lots; no blanket BSCG-family equivalence. |
| IFOS | [Nutrasource directory](https://certifications.nutrasource.ca/certified-products), [FAQ standards](https://www.nutrasource.ca/about/faq/) | Fish-oil product/lot potency, contaminants and freshness; current purity/heavy-metal capability, not general label-accuracy flag. | Existing AJAX/detail fetcher; preserve underlying lot reports and program marker. |
| Labdoor | [Testing process](https://labdoor.com/about/testing), [certification standards](https://labdoor.com/enterprise/certifications/standards) | Rankings/testing and formal Quality, Sport and THC-Free certification are different evidence. No existing verified-capability declaration. | Source gap. Inspect named product report, current certification and testing date; ranking alone cannot be mapped to a current formal seal. Existing notes incorrectly deny formal certification. |
| Friend of the Sea | [Current certificate portal](https://friendofthesea.org/certified-products-and-services/), [audit standard](https://friendofthesea.org/wp-content/uploads/19122022_FOS-Audit-Guidance-ver.-2.1-1.pdf) | Sustainability/traceability; specified product/species/holder, status and validity, not purity testing. No capabilities declaration. | Public portal redirects to WSO and embeds Zoho registry plus company-list download. Potential targeted FOS-ID adapter; do not turn company or ingredient certificates into every finished SKU. |
| MSC | [Public supplier directory](https://cert.msc.org/SupplierDirectory/VController.aspx?Path=02D03D11-054D-44F5-9076-B1BD00A2EBDF), [Data Validation API](https://www.msc.org/for-business/msc-data-validation-api) | Fishery/chain-of-custody sustainability; optional API can validate a consumer product by barcode or logo-license code. No capabilities declaration. | Public CoC listing alone insufficient for SKU. API is promising but access, onboarding and bulk completeness are unverified; not implemented coverage. |
| GOED | [Membership application](https://goedomega3.com/members/how-to-apply), [technical standards](https://goedomega3.com/technical-information) | Trade membership plus monograph/quality documentation, not independent certification of every marketed SKU/lot. No capabilities declaration. | Member-directory lookup is membership only. Do not infer all-brand certification or contaminants testing from GOED Member claim. |
| Clean Label Project | [Public certified-products](https://cleanlabelproject.org/certified-products/), [Seeking Health certificate and product schedule](https://cleanlabelproject.org/wp-content/uploads/20250219_CLP-Certificate_Seeking-Health.pdf) | Separate Purity Award, Pesticide-Free and CLP Certified marks, identified products, annual certificates. No verified-capabilities declaration. | Strong adapter candidate: public HTML brands/products plus PDF schedules and validity. Certificate-only without attached product schedule is insufficient. No new capability policy selected here. |
| iTested | [Official program](https://www.iherb.com/info/itested), [official report guidance](https://information.iherb.com/hc/fi/articles/30908334102804-Analyysitodistukset-COA-iHerb-merkkisille-tuotteille) | iHerb-exclusive product pages link batch-specific reports; official support says not every production lot tested. No capabilities declaration. | Product/report-specific candidate crawler; no complete certified-directory proven. Read actual report lab, date, lot and analytes; not automatic Eurofins attribution or all-batch testing. English support request403; alternate official support text available. |
| Informed BST | [Sport](https://sport.wetestyoutrust.com/about/certification-process), [Choice](https://choice.wetestyoutrust.com/about/certification-process) | Banned-substances-tested wording; distinct standalone certification directory not established. No capabilities declaration. | Resolve actual named Sport/Choice program when proven; generic BST wording cannot become new independent program or duplicate credit. |
| TGA Listed | [Official listed-medicine requirements](https://www.tga.gov.au/products/medicines/listed-medicines/application-and-market-authorisation/certifying-your-listed-or-assessed-listed-medicines-meet-all-regulatory-requirements) | AUST L sponsor-certified listed medicine; no individual premarket quality/safety/efficacy evaluation. AUST L(A) efficacy-assessed and AUST R registered are distinct. No capabilities declaration. | Regulatory ARTG identity/status lookup, not independent testing. Existing notes falsely say all listed products pass an individual premarket safety/quality review. Direct request timeout; official browser/search content checked. |
| Ecocert | [Certificate portal](https://certificats.ecocert.com/) | Organic/sustainability program and holder/product schedule specific; not broad purity-testing evidence. No capabilities declaration. | TLS chain verification failed locally and web unavailable. Directory exists as candidate URL but current content/completeness not established; unavailable, not zero or withdrawn. |
| NSF/ANSI455 | [Official GMP standard](https://www.nsf.org/nutrition-wellness/gmp-certification), [455 listing](https://info.nsf.org/Certified/455GMP/Listings.asp) | Manufacturer/packager/facility GMP audit. Separate from173 finished-product or Sport certification. No capabilities declaration for this rule. | Covered through existing NSF GMP source only with facility scope. Existing notes incorrectly claim broader SKU label/contaminant testing. No brand-wide product-testing promotion. |
| Soil Association | [Certificate checker](https://www.soilassociation.org/for-business/soil-association-certification/business-support/organic-certificate-checker/) | Organic licence holder; full certificate/trading schedule needed for listed approved products. No capabilities declaration. | Public daily-updated checker; dynamic supplier schedule investigation needed. Organic traceability only, not supplement batch potency/contaminants. |
| Canada NPN | [Current licensing search](https://produits-sante.canada.ca/lnhpd-bdpsnh/newSearch?lang=eng), [official JSON API](https://health-products.canada.ca/api/documentation/lnhpd-documentation-en.html) | Eight-digit licensed product, form/ingredients/recommended conditions and active/discontinued/stop-sale/cancelled/suspended states. Marketed status separate. No capabilities declaration. | Reliable identity-specific API candidate; regulatory authorization is not independent batch testing. Match NPN and actual formula, not just title. |
| EU GMP+ | [GMP+ official directory](https://portal.gmpplus.org/en-US/cdb/certification-body/) | Animal-feed chain safety/sustainability scheme. No capabilities declaration. | Out of human-supplement product-testing scope; current notes incorrectly generalize it as EU manufacturing akin to pharmaceuticals. No adapter to product credit. |
| ISURA | [Certification process](https://isura.ca/product-certification/), [standard](https://isura.ca/wp-content/uploads/2023/08/ISURA-standard-Rev10Jan282022.pdf), [current thresholds](https://isura.ca/wp-content/uploads/2025/12/ContaminantsThresholdLimitsRev10Nov302025.html) | Product/raw-material certification includes authenticated composition, contaminants/adulterants and non-GMO requirements; exact finished-product scope matters. No capabilities declaration. | Standards publicly retrievable, but no complete public SKU registry found through site and targeted searches. Manual current certificate verification until authoritative directory available; no inferred brand-wide coverage. |
| Third-party generic | No identified certification authority by definition. | Weak,0 points, no named-program capabilities. | Preserve as display-only unverified claim; no fetcher or guessed lab assignment. |

### Additional Nutrasource sources: fetch coverage can precede scoring approval

The same [public directory](https://certifications.nutrasource.ca/certified-products) explicitly provides IKOS, IAOS and IPRO filters; [official FAQ](https://www.nutrasource.ca/about/faq/) describes their tests. These are not existing recognized `third_party_programs` mappings. Extend the existing AJAX/detail retrieval owner into source-only candidate snapshots; do not insert unapproved program semantics into production credit.

- **IKOS:** krill-oil lot testing, omega-3/astaxanthin potency, contaminants and freshness. Match lot/product identity; current IFOS credit must not automatically transfer.
- **IAOS:** algal-oil content, contaminants and stability. Distinguish algal preparation/form/product and report validity.
- **IPRO:** probiotic ingredients and finished products; microbe/heavy-metal checks, capsule disintegration and total probiotic count. This is testing evidence, not clinical strain/formula efficacy or automatic stability-through-expiration proof.
- **ISURA:** recognized already, standards substantiated, exhaustive public current listing remains unestablished; do not declare source coverage completed.

### Demonstrated factual copy defects for integrator correction

Correct existing notes through the original rule entries, with source-grounded regression assertions and without changing point values/capability mappings: NSF455 facility-vs-product distinction; GMP+ animal-feed scope; Labdoor formal certifications versus rankings; TGA AUST L sponsor declaration versus individual premarket evaluation. GOED membership and iTested report/lot limits also require careful copy, not product-credit activation. Current source failures and incomplete scope are explicit unresolved coverage, not justification to lower scores or remove prior records.

Live adapter probes: source-only first-page requests reported IKOS27, IAOS42 and IPRO24 records on October4 (not a complete refresh). Payload flags are `IsIkos`, `IsIaos`, `IsIpro`; common stable identity is `ProductNum`. Sample detail headings explicitly identify their respective testing program. Individual program standards were also saved as `ikos_standard.html`, `iaos_standard.html`, `ipro_standard.html`; bounded payloads/detail pages and all artifact hashes are in the research receipt directory. Ingredients and finished products occur in the same source; certificate identity does not automatically imply finished-SKU scope.


### October4 — concluded reviews versus open identity, and ALA source packet

Fresh raw probes keep Q53 identity boundaries explicit:264105/LA-5 has a completed no-qualifying-applicable-human-evidence determination;1834 has reviewed psyllium/limited ancillary literature but unspecified acidophilus remains pending;12091 retains unresolvedSD-5845 and undosed disclosed species children. Species-only19171/19172/19890/35694/65049 and preparation-insufficient46802 cannot acquire a positive grade from similar names. Readiness now consumes these existing owners; shadow Evidence completeness does not alter publication policy.

Tesnor primary source [PMID35928723](https://pubmed.ncbi.nlm.nih.gov/35928723/), retrievedOctober4: aging-males' symptom score is primary; hormones, hand-grip and perceived stress are secondary. Notes previously denied these were clinical outcomes, now corrected. Exact LN18178 intervention and approved grade/benchmark remain unchanged; no claim of long-term disease benefit.

ALA review covers the ten named subjects12315/18141/241665/293406/295103/295198/295470/328010/328011/840; Six currently expose exact `alpha_linolenic_acid` subjects (12315/18141/241665/295103/295470/840); four declare flaxseed oil with generic omega-3/6/9 components and do not currently expose a canonical ALA subject (293406/295198/328010/328011). Do not invent an explicit ALA label amount from those carrier/component declarations; their preparation/subject coverage still needs the final census. Per-label current canonical resolutions are saved in `~/pg_quality/clinical_role_completion_20261004/ala_subjects.json`. [Cochrane2020 RCT review, PMID32114706](https://pubmed.ncbi.nlm.nih.gov/32114706/) separates ALA from long-chain EPA/DHA: little/no effect on mortality and coronary outcomes, possible limited cardiovascular-event/arrhythmia findings with outcome-specific certainty. Therefore a blanket “no human evidence” or “no effect” ALA determination would be inaccurate. [BMJ2021 cohort review, PMID34645650](https://pubmed.ncbi.nlm.nih.gov/34645650/) is dietary observational association, not proof of efficacy for an individual ALA supplement. ALA-specific intervention/preparation/outcome grading remains open; no marine record, essential-nutrient amount benchmark, or observational association silently supplies positive supplement Evidence. No ALA clinical grade was authored in this correctness batch.

The five prebiotic-family reviews retain actual pending preparation/clinical-grade decisions: PHGG selective outcomes/null overall symptoms; inulin/FOS heterogeneous preparations and overlapping syntheses; XOS microbial surrogate versus clinical benefit; GOS preparation-versus-active mass; PreforPro standalone versus combination attribution and carrier mass. Source verification is complete where recorded, but new clinical grading, missing preparation equivalence and clinician holds are not implicitly approved. Sytrinol's matched reviewed state already works; do not reopen stale D23/Dose-header claims as pending code work.

### October4 — bounded Spirulina population/comparator correction

Entry `INGR_SPIRULINA`: [PMID25057105](https://pubmed.ncbi.nlm.nih.gov/25057105/), live primary abstract retrieved October4, studies73 HIV-infected women before HAART at5g/day for3months. Antioxidant capacity improved; immunological and virological markers did not differ between groups. [PMID12487756](https://pubmed.ncbi.nlm.nih.gov/12487756/), live primary abstract retrieved October4, studies23 children aged2–13 with nephrotic syndrome receiving medication with/without1g/day Spirulina for2months. The quoted116.33/94.14mg/dL reductions are within-group changes; medication-only controls also improved. Correct endpoint summaries and reference notes; no general longevity inference.

Fail-first source regression in `test_clinical_applicability.py` reproduced missing population/comparator qualifiers, then passed after `data_batch.load/save`. Tesnor+Spirulina exact batch check:2entries changed,0problems. No numerical grade, benchmark, enrollment/count or clinical applicability policy changed. Existing Spirulina `positive_strong`,58-count aggregates and Healthy Aging classification remain unresolved clinical-review debt and must be assessed before release; this bounded factual repair does not ratify them. Independent read-only reviewer confirms corrected source meaning and no new policy.

### October4 — remaining bounded clinical applicability determinations

Current source batch `32fa1be2`, independently reviewed against the existing clinical/applicability and numerical owners. This supersedes the previous frozen-grade obligations for the records below, not explicit clinician holds in the separate form queue.

- **ALA:** add one verified existing-registry literature determination, `alpha_linolenic_acid`, with mixed outcomes and no new numerical credit. [Cochrane32114706](https://www.cochrane.org/evidence/CD003177_omega-3-intake-cardiovascular-disease) separates plant ALA from EPA/DHA: mortality/CHD little or no effect, limited event/arrhythmia signals with outcome-specific certainty. [32643951](https://pubmed.ncbi.nlm.nih.gov/32643951/) reports lipid biomarkers; [37778442](https://pubmed.ncbi.nlm.nih.gov/37778442/) has mixed risk-factor results; [20929341](https://pubmed.ncbi.nlm.nih.gov/20929341/) is an overall-null post-MI margarine trial. Overlapping studies/populations are not independent replication. No universal optimal-dose benchmark, marine substitution, observational efficacy or whole-seed transfer.
- **Flaxseed:** preserve ground-whole-seed [24126178](https://pubmed.ncbi.nlm.nih.gov/24126178/)/[25740909](https://pubmed.ncbi.nlm.nih.gov/25740909/) research and trial exposure facts. Oil cannot inherit the ground-seed preparation; direct resolver consumes the same preparation guard as numerical Evidence. Generic omega children do not establish an explicit ALA amount.
- **Sunfiber PHGG:** existing direction corrected to `mixed`, confidence medium, exact source-label Sunfiber preparation required. [26855665](https://pmc.ncbi.nlm.nih.gov/articles/PMC4744437/) shows selective bloating/gas benefit but registered primary IBS severity and QOL null; [31509971](https://pmc.ncbi.nlm.nih.gov/articles/PMC6769658/) shows healthy loose-stool form benefit with important null outcomes. Largest individual-trial enrollment121 replaces summed165; unsupported completed-registry count removed after [NCT01779765](https://clinicaltrials.gov/api/v2/studies/NCT01779765) verification. Existing mixed multiplier applies, not a new sponsor penalty.
- **Inulin/FOS:** `INGR_INULIN` corrected to mixed/medium and source-preparation scope. [34555168](https://pmc.ncbi.nlm.nih.gov/articles/PMC8970830/) distinguishes eleven positive/nine null stool-frequency studies and preparation/chain-length effects. [38309832](https://pubmed.ncbi.nlm.nih.gov/38309832/) risk factors are low/very-low certainty, not clinical cardiovascular events. Generic `prebiotics` cannot lend this review to XOS/GOS. `chicory_root` [27492975](https://pubmed.ncbi.nlm.nih.gov/27492975/) exposure corrected5g→12g/day Orafti Inulin, with no operational benchmark basis. Raw root equivalence remains unestablished. `nha_fos` now retains actual human research [16569219](https://pubmed.ncbi.nlm.nih.gov/16569219/):40 volunteers, Actilight scFOS44/46/10%GF2/GF3/GF4, seven days, microbial surrogate and bloating limitation. Subset report is not independent replication; no false absence or automatic symptom-benefit claim.
- **XOS/PreticX and GOS/Bimuno:** completed bounded source reviews retain their genuine human research and preparation-specific limitations. XOS microbial findings are not symptomatic clinical efficacy; old trial purity cannot be inferred from later70% preparation or retail branding. GOS symptom findings apply to the studied B-GOS preparations/populations; powder grams and active GOS grams remain distinct. No universal new Dose threshold or borrowed inulin credit. Reuse October2 primary methods receipts; source review completed, unverified retail/trial correspondence remains limited.
- **PreforPro:** existing `bacteriophages` literature entry now preserves [30157383](https://pubmed.ncbi.nlm.nih.gov/30157383/), [30897686](https://pmc.ncbi.nlm.nih.gov/articles/PMC6471193/), [32824480](https://pmc.ncbi.nlm.nih.gov/articles/PMC7468981/):three reports/two trials. PHAGE primary tolerability/metabolic/GI outcomes, its secondary microbiome report, and PHAGE2 BL04+phage combination are separated. Neither placebo improvements nor within-group findings establish standalone between-group clinical efficacy;15mg includes carrier and is not potency. Research-present/applicability-unestablished replaces a false no-human-trials claim; no affirmative clinical points or benchmark added.
- **Spirulina:** mixed/low certainty replaces overstated broad positive aggregate; existing conservative `rct_single`/tier2 numerical representation retained, not upgraded merely because reviews exist. [34538515](https://pubmed.ncbi.nlm.nih.gov/34538515/) has null LDL/HbA1c alongside positive biomarkers; [35988871](https://pubmed.ncbi.nlm.nih.gov/35988871/) direct eight-study/420-person LDL finding is VERY LOW certainty, not the entire131-trial nutraceutical network. [37263369](https://pubmed.ncbi.nlm.nih.gov/37263369/) is the lipid review, not PPI withdrawal. [38401078](https://pubmed.ncbi.nlm.nih.gov/38401078/) is43 randomized after45 screened, dyspepsia benefit/reflux null after PPI withdrawal. NCT01752972 is nonrandomized/open-label; NCT05016557 is a25g-protein-bolus basic-science study, not ordinary-dose muscle recovery. Unsupported58/58/101 aggregates removed. Existing preparation/outcome scope rejects extract equivalence and limits purpose to metabolic biomarkers; HIV women/pediatric null-context words do not become supported purposes.
- **Q53:** all eight remaining raw labels12091/1834/19171/19172/19890/35694/46802/65049 match live NIH rows, servings and statements. Source investigations are complete, but SD-5845, species-only rows and Bioflora do not establish exact trial/deposit/formula correspondence. These remain justified identity/applicability exceptions, not false absence conclusions or positive scores. Evidence completeness and actual catalog eligibility are separate; no blanket new publication gate was invented.

Owner fixes: existing resolver consumes `clinical_applicability.assess_clinical_applicability(... assess_amount=False)` with exact row context; legacy matched-form exclusions share this owner; named undosed subjects retain Evidence review and receive no borrowed quantity. Dose retains strict exposure access. Reviewed outcome scope outranks incidental null-population prose. Existing census now uses `get_evidence_subject_rows`, frozen manifest ownership/checksums, full raw Clean/Enrich boundaries, every row disposition and explicit unresolved exceptions; source/audit/input mutation or missing/duplicate inputs fail rather than silently producing a success report.

Receipts: `/Users/seancheick/pg_quality/clinical_completion_20261004/`. Per-entry primary/full methods, reviewer receipts and exact curated batch checks retained. Bounded existing verifiers: three backed records/17 PMID-entry claims, zero title drift/mismatch/topic flags/missing; six literature records/12 studies, zero corrections/failures/retractions. The general citation verifier reports0changed citations because these registries have separate verification owners; it is not their evidence receipt. Final census/replay/checkpoint and integration receipts belong in LEDGER; source review does not validate a release.


Final source-owner review supplement: provided-marker selection uses existing label-phrase and same-parent form owners. Raw231979 names DMAE bitartrate;37%DMAE is a composition disclosure, not37% form-quality credit. Raw58801 supplies2000FU Nattokinase from Soy Natto extract; that enzyme declaration remains disclosed/unmapped, rather than becoming unproved isoflavones credit or clearing an identity hold. Raw232485 remains whole Spirulina powder with a Phycocyanin marker, not isolated extract. Real251338/254958 provider anchors corroborate exact printed Inulin children through existing linked_rows; no parent mass or clinical Dose benchmark is borrowed. Source-only identity, ambiguous-child and foreign-record negative controls remain fail-closed. Independent review receipts and the new four-live/one-dormant amount-scope inventory are in `clinical_completion_20261004/`; final census and numerical receipts are separate from research signoff.

Final source380e1713 census covers15,421frozen labels/102,281subjects:15,101resolver-completeproducts/320partial,340pending subjects/58canonicals. ALA,nha_inulin,nha_sunfiber are no longer pending. All340exact source rows and every58canonical exception retained in accepted_subject_census.json/accepted_census_summary.json plus independent final_census_review.md/json. Q53eight labels are concluded research-present/applicability-unestablished determinations; LA-5 concluded no-qualifying-human-evidence. They are not counted in the340pending, and no exactstrain equivalence, affirmative efficacy or automatic catalog hold follows. The source/role/preparation queue and genuine research gaps remain explicit; resolver completeness does not equal comprehensive fresh independent clinical review. Final2,101raw-label replay has85explained total movements and0status/safety/DoseSafety/completeness changes; existing numerical rules consume source corrections. Source380e all4CIgroups green,537local/24declared opt-in skips,1,019final ownerchecks. No publication or release validation.


## October 5 — census-discovered source/preparation corrections

Baseline dfeff692. Existing-owner factual corrections only; numerical policy, clinical grades and publication unchanged. The original fbf6d299 measurement/provider gate is superseded: it excluded sole-purpose Triphala/Univestin and was removed before acceptance.

Owner: enhanced_normalizer::_printed_nutrient_identity and _process_single_ingredient_enhanced; enrich_supplements_v3::_resolve_iqd_identity; IQM collagen/acacia; botanical triphala_powder. Evidence: ownership matrix cleaner_row_role/normalization/scoring_input_contract, glossary, callers and fail-first production-seam tests. Will NOT create scorer, registry, public field/status, policy or grade.

Per-entry results verified October 5:
- collagen.forms[hydrolyzed collagen peptides].aliases: remove eggshell membrane/nem/nem eggshell membrane. NEM is a membrane preparation; PMC5822842 describes collagen plus other ECM constituents and partial gentle hydrolysis preserving membrane activity. Partial hydrolysis does not establish equivalence to the generic purified peptide form. https://pmc.ncbi.nlm.nih.gov/articles/PMC5822842/ . Existing NHA_NEM identity and collagen taxonomy/Dose owner retained. Eggshell Membrane Collagen, Fermented remains a separately disclosed uncertain preparation; no replacement score invented.
- acacia_catechu.forms[acacia catechu wood and bark extract].notes: incorrect Morus companion and 250-500mg implication corrected to Scutellaria baicalensis+Acacia catechu UP446 combination,500mg/day,one week,79 adults40-90 with knee OA; not an Acacia-only efficacy/dose benchmark. PMID 24611484 live abstract archived PMID24611484.json. https://pubmed.ncbi.nlm.nih.gov/24611484/ . Otheringredient/anchor component identities already correct; no clinical grade added.
- botanical triphala_powder.aliases: remove Triphala fruit extract; raw Triphala formula with explicit extracted fruit forms cannot receive powder identity. Existing unknown identity and structural-source handling retain raw preparation, quantity and component facts. PMID22557240 pharmacognosy describes churnam powder microscopy separately from aqueous/alcoholic extracts, not clinical efficacy equivalence. https://pubmed.ncbi.nlm.nih.gov/22557240/ . Actual powder and sole-purpose formula subjects retained; no new extract registry/id.
- active 267347 non-GMO Ascorbic Acid: source category vitamin and existing stripped exact Ascorbic Acid IQM identity establish Vitamin C; current literal otheringredient/preservative collision must not overwrite it. Original OI collision is required for this restoration, so qualified Vitamin A with full beta-carotene UNII remains beta_carotene/bio5. Inactive Ascorbic Acid remains OI preservative. Raw input hash retained in immutable manifest; no dose borrowed for undosed child.
- 178674 Essential Oil Blend: raw ingredientGroup Blend(Fatty Acid or Fat/Oil Supplement) and EveningPrimrose/BlackCurrant/Borage children establish fatty oils, not the botanical volatile-oil preparation. Cleaner leaves contradictory header identity unresolved; named members retained and existing lent-mass contract prohibits member-dose borrowing. No new volatile/fatty oil clinical determination.

Remaining classified exceptions: all 58 canonical groups retain their individual research/preparation/source classifications from accepted census. Dicalcium phosphate is a distinct compound; Calcium grouping cannot establish an elemental amount or clinical authority by itself. Olive/rice-bran/sunflower oil nutrition/carrier/formula cases stay contextual; active essential oils and sole-material products must not be globally demoted. NEM/Univestin/Triphala preparation-specific clinical determinations remain open despite identity containment. Marker-purpose and sole-purpose protections continue through existing provider; no second exclusion list.

Validation and final measurements are recorded in the existing research/LEDGER. The initial 122-label cohort includes all current raw NEM/eggshell,Univestin/Acacia,Triphala,EssentialOilBlend and quality-qualified vitamin names plus named source/sole-purpose/clinical controls. Final artifact/clinical/corpus/device/release closure is not inferred from this subset.

Source candidate `8084ca71`: frozen 123-label compare changes three reason/readiness payloads only (178674 fatty-oil header/member linkage;184942 extracted Triphala structural identity;267347 active VitaminC authority identity). Zero numerical pillar/total, status or route movements. Final independent review accepted source `8084ca71` on 123 labels, including unchanged Calcium Ascorbate 306193. Local537passed/24declared opt-in skips149.77s and all four CI 37268235385 groups pass; LEDGER records complete checkpoint limits. Earlier broad header exclusion was removed; provider is exactly baseline. No new clinical grade, blanket oil demotion or fresh all-label census.

## October5 remaining preparation exceptions — bounded disposition

Current implemented source is e79d8cff. Reviewed historical pending groups against retained raw labels and existing owners;183 immutable labels supply bounded current-output controls, not a refreshed corpus census. Durable primary-source receipts: `/Users/seancheick/pg_quality/clinical_regimens_20261005/remaining_clinical_receipts.md`, `remaining_preparation_receipts.md`, `source_review.md`. Receipts are research evidence, not a runtime registry or a second execution register.

| Group / source | Applied disposition / remaining boundary |
|---|---|
| Clove315309 / powder184659,185088 | Extract→powder identity bug fixed; existing cloves review corrected against live PMID31064377. Source-specific human pilot acknowledged; unnamed-extract standardization and liver-purpose bridge remain unestablished. Powder rows retain identity and unresolved review ownership. No borrowed efficacy or dose reward. |
| White kidney bean | Approved OptionA; exact Phaseolean source preparation/potency/assay permits descriptive exposure only. Generic material stays reference-uncertain. |
| Pancreatin | Prescription enzyme-replacement evidence does not identify retail mixture coating/activity/indication. Preserve activity fields; mass/USP protease do not establish equivalent lipase activity. No universal conversion or generic-digestion award. |
| Hesperidin complexes | Purified hesperidin/MPFF research cannot identify unknown complexes or their active fraction; preserve explicit30%/3mg source. Existing Formulation signoff hold retained. |
| Piperine and oil/essence subjects | Preserve Sean's removed standalone efficacy treatment and existing absorption-aid owner. Oil/essence cannot be reclassified as isolated piperine, or globally made incidental. |
| Litesse213508 / polydextrose | Selected-scoop exposure6.25g retained; positive/null acute appetite research does not establish chronic weight-loss benefit or generic formulation equivalence. No new clinical grade. |
| Soluble corn fiber74427 / allulose protein powders | Retain actual source section/role/amount. Research in another dose/matrix/population does not establish this formulation's benefit; no blanket absence-of-human-research or automatic incidental exclusion. |
| Whole matcha | Whole-material mixed/null research differs from isolated green-tea constituents; no extract borrowing or universal positive/negative grade. |
| Triphala / Bergamonte / oral essential oils | Identity corrections do not establish exact formula, oral route, chemotype, purpose or retained preparation equivalence. Keep specific holds. |
| Mushroom/formula mixtures / Bionectria | Preserve named constituent identity, source role and actual member exposure; no formula or Cordyceps borrowing. Independent Wellmune owner remains distinct. |

Known four-transfer/source defects are implemented. These research/preparation boundaries remain honest holds; they are not silently converted into clinical negatives or declared closed. Final whole-corpus coverage/readiness must be measured from Sean's new Clean output before release.

## October5 source-role continuation — shared identity causes

Baseline main d02454eb. Bounded follow-up examines all34 retained oil/mineral subject traces, current raw→Clean→Enrich controls, the remaining pepper preparation queue, and exact whole-matcha sources. Role investigation does not authorize blanket carrier demotion or clinical absence stamps.

Owner: `enhanced_normalizer::_process_single_ingredient_enhanced/_printed_nutrient_identity` — evidence: raw-boundary regressions and existing IQM match_rules/source_form_aliases. `identity_integrity::resolve_identity/validated_canonical_parent_relationships` owns broad-to-specific resolution; `evidence_resolver` and `clinical_applicability` consume the existing literature registry. Will NOT create: per-label overrides, competing classifier/registry/scorer, extra grade/status, numerical benchmark or denominator policy.

| Shared cause | Existing-owner correction / disposition |
|---|---|
| Source botanical/oil aliases claimed isolated piperine | Remove whole-pepper/oil aliases from piperine and bare species aliases from the standardized extract. Apply authored IQM preparation exclusions at the canonical row seam, covering alias, group and UNII routes while distinguishing independently declared marker identity from source/carrier descriptors. Oil remains unresolved rather than falsely isolated; declared piperine/BioPerine/extract controls retain existing identity. |
| Generic olive oil claimed extra-virgin grade; generic taxonomy could then replace a truly declared grade | Correct the existing OI standard_name to Olive Oil (retain its stable key), transfer explicit extra-virgin aliases to the existing IQM grade, and declare the existing generic→specific relationship. Generic/virgin/organic/cold-pressed wording cannot infer extra-virgin grade; explicitly declared grade survives a generic group. Source-role context remains separate. |
| Qualified vitamin groups bypassed parent-local source aliases | Consolidate the existing parent-local source alias owner for plain and qualified nutrient headings; if a qualifier exists it must match reviewed aliases within that same exact parent. Active beta/delta tocopherol retains its raw chemical name and mass; unknown alpha activity stays ineligible for nutrient adequacy. Inactive/unrelated/unknown-source controls do not gain this bridge. |
| Whole-matcha research absent from exact literature owner | Existing matcha record now acknowledges two directly reviewed human studies, mixed acute tasks and null primary outcomes in the longer trial. Applicability remains unestablished, with no positive grade or generic effective-dose benchmark. Extract/isolated constituents do not inherit it. |
| Oil/mineral contexts without corroborated defect | Olive/seed-oil blend anchors remain explicitly blend-level; selected Evidence owner follows existing purpose facts. DCP77108 appears both as calcium source and undosed hydration member, but raw evidence does not prove one repeated exposure. Preserve the independent material/hold; do not deduplicate from name overlap. |

Content verified October5: primary pepper chemistry PMID19456163 distinguishes volatile oil from piperine-rich oleoresins; live GSRS confirms OLIVE OIL6UYK2W1W1E, PIPERINEU71XL721QK and BLACK PEPPERKM66971LVF. [IOC grade definitions](https://www.internationaloliveoil.org/olive-world/olive-oil/) distinguish olive-oil grades. Matcha PMID28784536:23-participant placebo crossover,4g powder in drink/bar, selected attention/psychomotor findings with most tasks/mood null and matrix dependence; full methods unavailable. PMID39213264 primary PLOS methods:99 older SCD/MCI adults,2g/day Hojin no shiro powder12months; primary MoCA/ADCS-MCI-ADL null, selective secondary social-acuity signal and nonsignificant sleep trend. Employee-author interests retained; no independent replication or dementia-prevention inference.

Durable evidence `/Users/seancheick/pg_quality/source_role_completion_20261005/`: primary PMID/UNII JSON, clinical_receipts.md, raw freeze/manifest and source verification. Existing `source_role_current_probe_20261005.json` supplies34-row context and10 representative current boundary probes. Omega mapping and Tesnor/Sytrinol wiring are already implemented; remaining omega gate requires fresh corpus verification. Triphala/Bergamonte/mushroom/Bionectria/oral-oil exact material, formula, route and purpose blockers remain explicit. Source research is not comprehensive clinical/release closure.

Independent review and310-label replay rejected the first candidate: generic plant taxonomy repaired two genuine BioPerine labels away from piperine, while generated extract aliases still captured whole-fruit spellings. The shared canonical registry now requires literal preparation proof (using existing label-qualifier rules moved intact to normalization); Clean and Enrich use that same proof and reviewed parent relationships. No missing/wrong generic taxonomy can supply isolated marker identity. Canonical owner standard names follow the recovered identity; source name/forms/mass remain retained. Declared piperine with a carrier form remains piperine; a whole plant with a constituent descriptor does not acquire isolated marker mass. Whole GoldenMilk243271 remains black_pepper with its existing absorption-aid role, correcting a stale piperine test pin.
