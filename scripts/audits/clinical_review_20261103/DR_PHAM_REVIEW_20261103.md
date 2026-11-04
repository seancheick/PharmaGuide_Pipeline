# Review as received from Sean in chat, 2026-11-03. Verbatim.

Attestation: asked whether Dr. Pham reviewed this text and approved it as her own decision, Sean answered in chat on 2026-11-03: "Yes, she approved it". Relayed by Sean; no agent reviewed clinically or signed. Unapproved by its own terms: a metformin or levothyroxine class mapping (E5). Open question to her: "per serving" in the caffeine copy against a per-day rule.

Evidence review • November 3, 2026 • NCCIH, NIH ODS, ACOG, Health Canada, PubMed and prescribing information

I recommend approving several changes, but not every proposal exactly as written. The most important corrections involve the difference between an established hazard and a precautionary recommendation, how vitamin forms affect upper-limit calculations, and when an unknown quantity warrants a review warning rather than a definitive contraindication.

The product counts below are the impact estimates supplied in your packet; I have not independently reproduced those counts against the current catalog.
1–3. Bitter orange and synephrine
Approve with corrections
Decision: Change pregnancy from contraindicated to avoid, retain avoid for breastfeeding, and remove the 3 mg contraindication threshold from the pregnancy rule.
What the evidence establishes
NCCIH states that bitter-orange use may be unsafe during pregnancy or breastfeeding. It also notes possible cardiovascular risks, uncertainty about the role of synephrine in reported serious adverse events, and problems with synephrine labeling accuracy.

LactMed provides additional support for avoiding bitter-orange supplements while breastfeeding because human lactation safety data are lacking and animal findings suggest possible suppression of milk production. 
NCCIH+1


That supports a strong precautionary warning. It does not establish that every exposure is a proven medical contraindication.
Recommended rule
Population	Severity	Decision
Pregnant	Avoid	Approve downgrade
Breastfeeding	Avoid	Retain
Ordinary culinary quantities	Separate from supplement rules	Do not automatically flag
Oral bitter-orange supplements	Avoid during pregnancy/lactation	No pregnancy-specific 3 mg cutoff

Warning: Avoid bitter-orange supplements during pregnancy or breastfeeding.

Explanation: Safety during pregnancy and breastfeeding has not been established. Bitter-orange supplements may contain synephrine, and the amount may be undisclosed or differ from the label. Choose an alternative and discuss supplement use with a healthcare professional.




I would use this wording for both RULE_BANNED_BITTER_ORANGE_HYPERTENSION and RULE_BANNED_BITTER_ORANGE_PREGNANCY when they trigger the same pregnancy/lactation warning.

Importantly, the rule named HYPERTENSION must retain its separate cardiovascular-risk assessment. Lowering its pregnancy branch must not weaken a justified hypertension or medication-interaction warning.
What about Health Canada's 3 mg line?
I verified both the archived 2010 notice and Health Canada's ingredient database.

The archived notice says no additional risk information was required at or below 3 mg/day of combined synephrine and octopamine. Above that amount, additional cautions were required. Its pregnancy/breastfeeding instruction was to consult a healthcare practitioner—not an absolute contraindication. 
Canada.ca+1


That is a risk-labeling threshold, not a scientifically demonstrated pregnancy-safety boundary. It cannot justify the existing rule that declares 3 mg contraindicated.

I recommend:
- Remove the 3 mg pregnancy threshold and use avoid for oral supplement exposures regardless of declared amount.
- Keep quantitative synephrine thresholds, if needed, in a separately sourced general cardiovascular-risk policy.
- Retain the archived notice as historical regulatory context, linked explicitly as Archived Health Canada guidance, and cite NCCIH as the primary source for the pregnancy/lactation recommendation.
The important distinction: PharmaGuide is recommending avoidance because a safe supplemental exposure in pregnancy has not been established, not because research proves every dose is harmful.
4. Tansy — pregnancy, mechanism and citations
Approve with revised wording
Decision: Keep contraindicated as PharmaGuide's conservative pregnancy safety classification for oral tansy preparations and tansy essential oil. Correct the scientific explanation.
What the papers actually establish
PMID 33673548 is a 2021 narrative review of essential oils and reproductive toxicity. It identifies Tanacetum vulgare oil as potentially rich in beta-thujone, reports neurotoxicity and convulsion concerns, and advises against thujone-rich essential oils during pregnancy.

The approximately 45% beta-thujone figure refers to a reported essential-oil composition. It is not a general percentage for every tansy plant or supplement. 
PMC


PMID 232204 is a 1979 ethnobotanical paper documenting traditional use of various plants, including tansy, as emmenagogues or abortifacients. It does not provide controlled human pregnancy-outcome evidence or an established miscarriage rate attributable to tansy. 
PubMed


The GABA-A mechanism has better direct support from experimental studies of thujone, including PMID 10725394. That research demonstrates receptor inhibition but does not quantify miscarriage risk from a tansy supplement. 
PubMed

Approved wording
Warning: Do not use tansy supplements or tansy essential oil during pregnancy.

Explanation: Tansy essential oil can contain thujone, a neurotoxic compound associated with convulsions. The amount of thujone varies by preparation, and pregnancy safety has not been established. PharmaGuide classifies oral tansy preparations as contraindicated during pregnancy as a precaution because of their potential toxicity and reproductive-safety concerns.




I would remove the definitive statement that whole-plant products can induce miscarriage from the clinical warning. It is too strong without qualification for the evidence presented.

Citation decision: Use PMID 33673548 as the main reproductive-safety reference and PMID 10725394 for the thujone mechanism. Keep PMID 232204 only if the rule separately mentions historical abortifacient use; do not use it as evidence of a proven clinical miscarriage effect.

The scientific evidence grade and warning severity should remain independent. A precautionary contraindication does not require mislabeling the human pregnancy evidence as established.
5–6. Vitamin A — pregnancy and trying to conceive
Decision: Approve the review note, and correct the pregnancy form filter.

NIH establishes these upper limits for preformed vitamin A, which includes retinol and retinyl esters, but not beta-carotene or other provitamin A carotenoids. 
Health Professional Fact Sheet

Age	Preformed vitamin A upper limit
14–18	2,800 mcg RAE/day (about 9,333 IU retinol)
19+	3,000 mcg RAE/day (10,000 IU retinol)

The limits include dietary and supplemental intake, whereas PharmaGuide generally knows the supplement quantity only.

For RULE_IQM_VITAMIN_A_PREGNANCY_DOSE, I recommend:
- Known preformed vitamin A above the age-specific UL: retain contraindicated in pregnancy and avoid when trying to conceive as PharmaGuide's conservative policy.
- Known beta-carotene or exclusively provitamin A carotenoids: exclude them from the preformed vitamin A upper-limit rule in both pregnancy and TTC.
- A mixture containing preformed vitamin A and carotenoids: evaluate the known preformed portion, rather than treating the entire mixture as retinol.
- Undisclosed form: show a form-specific safety review note. Never declare that the preformed UL was exceeded solely because the form is unknown.
An important correction: the exclusion should be consistent across pregnancy and TTC. There is no scientific reason to count beta-carotene as preformed vitamin A for pregnancy but exclude it for TTC.

Suggested copy:
Vitamin A form needs review

This product lists vitamin A without enough information to determine how much is preformed vitamin A. High intakes of preformed vitamin A can be harmful during pregnancy. Check the form and total intake with your pharmacist or prenatal care professional.




For product 16730, this should be a safety-review finding, not an invented confirmed excess. Approval should also require verification that the product's available label information truly cannot resolve the form.
7. Vitamin E — pregnancy and undisclosed form
Decision: Approve with an important conversion safeguard.

NIH establishes vitamin E ULs of 800 mg/day for ages 14–18 and 1,000 mg/day for adults. These limits concern supplemental alpha-tocopherol, including its natural and synthetic forms—not indiscriminately every compound marketed as vitamin E. 
Health Professional Fact Sheet


The FDA's modern label convention adds a complication: vitamin E is declared in mg of alpha-tocopherol activity. The mass of a synthetic preparation can differ from the label's declared activity-equivalent amount. Legacy IU labels also require form-specific conversion. 
FDA


Therefore:
Label condition	Recommended handling
Exact alpha-tocopherol preparation and exposure known	Apply age-specific UL
Legacy IU, natural/synthetic form known	Convert using the appropriate factor
Form unknown and conversion affects the threshold	Show safety review
Mixed tocopherols or tocotrienols without component quantities	Do not treat entire mixture as alpha-tocopherol
Confirmed exposure exceeds applicable UL	avoid during pregnancy

Keep the established over-limit warning. However, do not automatically clear every undisclosed-form product just because a numeric conversion cannot be completed.

A routine vitamin E amount below the UL does not, by itself, require an excess-dose warning. Independent bleeding-risk and medication-interaction rules should continue to operate.
A. Caffeine at exactly 200 mg during pregnancy
Decision: Yes, trigger at 200 mg and above.

ACOG recommends less than 200 mg/day during pregnancy. Accordingly, exactly 200 mg does not satisfy that recommendation. This is a daily-intake recommendation, not a demonstrated biological toxicity cliff at 200 mg. 
ACOG


I approve the inclusive threshold, with avoid as a conservative pregnancy supplement warning—not contraindicated.

The warning should say the product reaches the recommended daily limit, rather than asserting that 200 mg has been proven harmful.
High caffeine intake during pregnancy

This supplement provides 200 mg or more of caffeine per serving. ACOG recommends keeping total daily caffeine intake below 200 mg during pregnancy, including caffeine from drinks, foods and supplements. Avoid this high-caffeine supplement during pregnancy unless your prenatal care professional advises otherwise.




Product 249741: important additional finding
I inspected the actual NIH DSLD label for Transparent Labs Preseries Bulk V2, Blue Raspberry. It prints:
Ingredient	Per serving
Caffeine anhydrous	180 mg
Infinergy (di-caffeine malate)	30 mg compound
Theobromine	50 mg

Source: NIH DSLD original label, product 249741.

Di-caffeine malate is approximately 74–75% caffeine by molecular composition, so the 30 mg compound plausibly contributes another 22.2–22.5 mg caffeine. That implies approximately 202.2–202.5 mg total caffeine, if the ingredient conforms to that composition. This remains an estimate, not a verified product assay. 
NXT Ingredients+1


I would not count the full 30 mg as caffeine, nor count theobromine as caffeine. Record 180 mg confirmed from the label plus an estimated additional contribution, and flag a potential threshold exceedance until the composition is verified.

The four additional products from the duplicate-dose fix must also be recalculated without double-counting physical ingredient quantities.
B. Ages 14–18: vitamin A and E
Decision: Add age-specific checks. Do not apply the lower teen limits to all adults.

NIH explicitly distinguishes the limits:
Nutrient	Ages 14–18	Age 19+
Preformed vitamin A	2,800 mcg RAE	3,000 mcg RAE
Supplemental alpha-tocopherol	800 mg	1,000 mg


Health Professional Fact Sheet+1
For PharmaGuide, use the known age bracket where available. If age is unknown and a quantity crosses only the teen threshold, return an age-dependent safety review, not a definitive adult clearance and not a false adult excess warning.

For a 17-year-old user, use the teen threshold. For a 25-year-old, use the adult threshold. Do not default unknown age to either one without communicating that uncertainty.

This is a necessary rule-engine improvement, not a reason to stop scoring the entire product.
C. Vitamin A and E while breastfeeding
Decision: Yes, apply the age-specific ULs during breastfeeding.

NIH lists the same upper limits during lactation as during pregnancy for these two nutrients. The clinical consequence and resulting warning severity, however, need not be identical. 
Health Professional Fact Sheet+1

Nutrient	Confirmed above UL while breastfeeding	Recommended severity
Preformed vitamin A	Yes	Avoid
Supplemental alpha-tocopherol	Yes	Avoid
Either, within UL	No excess established	No automatic over-limit warning
Relevant form or quantity unresolved	Unknown	Safety review

I would not assign contraindicated to vitamin A during breastfeeding merely by transferring the pregnancy teratogenicity rationale. The concern during lactation warrants a high-dose avoidance warning, but the fetal-development mechanism is pregnancy-specific.

Likewise, being below a UL does not establish that a supplement is suitable for everyone. Bleeding disorders, anticoagulants and other relevant risks remain separate.
D. Tansy's evidence label
Decision: Change pregnancy-specific evidence from established to limited.

The 2021 reproductive-toxicity review, historical ethnobotanical observations, and direct thujone experiments support a real concern. They do not establish the frequency or magnitude of miscarriage caused by commercially available tansy preparations in humans. 
PMC+2


I would distinguish the fields this way:
Field	Value
Neurotoxic mechanism of thujone	Established experimentally
Direct human pregnancy-outcome evidence for tansy	Limited
Pregnancy safety severity	Contraindicated under PharmaGuide's precautionary policy
Human miscarriage-rate claim	Not established

This is more scientifically accurate than letting a precautionary safety severity automatically determine the evidence grade.
E. Remaining clinical packet
E1. Product 249741 caffeine
Covered above. My disposition is potential threshold exceedance pending quantified di-caffeine malate composition, with a pregnancy avoidance warning justified by the high and potentially over-target caffeine exposure. Do not label the 30 mg compound as 30 mg pure caffeine.
E2. Vitamin E products 211459, 4178 and 178778
Decision: Apply the age-appropriate rule, but distinguish a measured quantity from an upper bound.

The supplied 900 mg upper bound is below the adult 1,000 mg UL and above the teen 800 mg UL.

If 900 mg is only the maximum possible alpha-tocopherol exposure after considering different forms, it does not establish that a teenager necessarily exceeds 800 mg. It establishes a possible exceedance that must be investigated or communicated accurately.

The adult rule should not issue an exceedance alert based on 900 mg alone. The teen rule should issue a review warning unless the actual applicable amount is established.

This is particularly important for older 1,000 IU labels, where natural and synthetic forms produce different quantities. 
Health Professional Fact Sheet

E3. Tocotrienol/tocopherol complexes: 64845, 62796, 63428, 307739
Decision: Do not count the full complex weight toward the alpha-tocopherol UL.

The NIH guidance is specifically for alpha-tocopherol. Tocotrienols and gamma-, beta- or delta-tocopherol cannot automatically be assigned the same UL contribution. 
Health Professional Fact Sheet


If the product discloses an individual alpha-tocopherol amount, count that amount after the appropriate form conversion. If the complex lists a parent total and individual constituent amounts, count the parent and children as one physical material structure, not multiple independent doses.

For a complex whose alpha-tocopherol share is undisclosed, preserve the uncertainty. Do not invent a fraction or a zero exposure.
E4. Vitamin A, smoking and asbestos exposure
Decision: Yes, include beta-carotene—this is a separate safety rule from preformed vitamin A toxicity.

The strongest relevant trials involved high-dose supplemental beta-carotene:
- ATBC: 20 mg/day beta-carotene in male smokers, with increased lung cancer risk.
- CARET: 30 mg/day beta-carotene plus 25,000 IU/day preformed vitamin A in current/former smokers and asbestos-exposed participants, also showing harm.
The evidence does not justify treating ordinary dietary carotenoids as equivalent to these high-dose supplements. 
Health Professional Fact Sheet+1


Retain the previously established risk-qualified approach: a conservative caution tier can start below the directly studied 20 mg amount, but must be identified as precautionary, not trial-proven at that lower dose.

The rule should inspect quantified supplemental beta-carotene whether it appears as its own ingredient or as the beta-carotene portion of a vitamin A declaration. It should not trigger from an unspecified mixed-carotenoid weight as if that entire weight were beta-carotene.
E5. Metformin and levothyroxine medication classes
Decision: Keep the clinically supported interactions but do not broaden the drug matches indiscriminately.

The packet does not specify the precise proposed medication-class changes, so I cannot approve a particular class mapping. The evidence supports the following boundaries.

Metformin → vitamin B12: This relationship is established and supported by drug labeling, the ADA's 2026 Standards of Care, and NIH. Long-term metformin may reduce B12 levels, particularly with higher doses, longer use or other deficiency risks. The action is B12 assessment and clinically directed management—not automatically recommending supplementation to every user, and not advising discontinuation of metformin. 
American Diabetes Association+2


The mapping should include metformin's recognized formulations and combination medicines containing metformin. It should not automatically include every diabetes drug.

Levothyroxine ↔ calcium and iron: This is an established absorption interaction. Relevant prescribing information instructs separating levothyroxine from calcium carbonate and ferrous sulfate by at least four hours. The relationship is commonly managed with timing rather than requiring avoidance of either treatment. 
LEVOTHYROXINE SODIUM tablet


The mapping should include levothyroxine generics and brand equivalents, but should not automatically transfer identical timing instructions to every thyroid drug without evidence.

I also checked the existing PharmaGuide repository history: your earlier clinical review already approved corrected metformin–B12 copy and levothyroxine calcium/iron counseling. The October levothyroxine work also harmonized calcium and iron severity to caution. Those decisions should be preserved rather than reopened.
Implementation conditions for the team
This clinical packet should be translated into one change set with separate, testable rule decisions, not a general rewrite of the safety engine.

The release must demonstrate that:
1. Pregnancy, TTC and lactation checks use the correct population, exposure form, dose and age.
2. An unknown form or bounded exposure produces an honest review finding, without inventing a confirmed exceedance or silently suppressing a meaningful concern.
3. The same physical ingredient cannot contribute its mass twice, including blends and nested constituents.
4. Safety severity, scientific evidence grade, product quality score and interaction applicability remain separate.
5. Deduplicated warnings display one consumer-facing concern when overlapping rules reach the same product, while preserving each rule's provenance.
6. Every changed threshold has boundary tests immediately below, exactly at and above it, plus pregnancy/lactation and unknown-age controls.
Most importantly, do not publish the supplied impact counts as final until the team replays the revised rules against the current catalog and regression fixtures. Several results depend on the separate duplicate-dose correction and form-identification work.
