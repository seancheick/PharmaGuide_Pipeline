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
