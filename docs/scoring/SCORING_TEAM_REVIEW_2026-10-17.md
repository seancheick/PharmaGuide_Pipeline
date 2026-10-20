# PharmaGuide scoring explained — developer and clinical review packet

**Source review: October 17, 2026. Engine 4.6.0; public config 1.27.0-declared-serving-dose.**

This explains the implemented scorer, including its editorial choices and limitations. It is not an assertion that every calibration is clinically optimal. Code and its generated artifact remain authoritative; this document does not introduce scoring policy.

**Delivery boundary:** the serving-based Dose change is integrated in source. It still needs Sean's new pipeline run, artifact qualification and catalog/app delivery. Build 22 and the previously published catalog do not contain this latest change. Do not use this packet to claim that the phone already shows the new results.

## 1. The plain-English model

A product earns points for six different questions. A brand name does not receive an arbitrary premium.

| Pillar | Maximum | Question |
|---|---:|---|
| Formulation | 20 | What is the quality of the ingredient forms or preparation? |
| Dose | 20 | How does the amount in one declared serving fit the applicable benchmark? |
| Evidence | 20 | What reviewed research or nutritional authority supports the assessed purpose? |
| Transparency | 15 | Does the label disclose what is needed to evaluate the product? |
| Verification | 15 | What independently supported quality verification is on file, and at what scope? |
| Formula & quality checks (`safety_hygiene`) | 10 | What catalog-level formula, additive and quality concerns were found? |

The six public pillars add to 100. The internal module dimensions are intermediate calculations, not additional public pillars.

```text
public Formulation/Dose/Evidence = round(clamp(raw / applicable_reference × public_max), 1)
public Transparency = round(clamp(raw / module_dimension_max × 15), 1)
public Verification = supported evidence-tier calculation, bounded to 15
public Formula checks = bounded clean base minus owned deductions, bounded to 10
analytical total = round(sum(six public pillars), 1)
shipped total = floor(analytical total + 0.5)
```

A reference is the reviewed attainable scale for that calculation, not the highest-scoring product currently in the database. A module's nominal maximum may exceed the reference after obsolete credits were retired. **Example: omega Formulation has a nominal internal /25 container, but its retained ingredients can earn 12 raw points. Its public reference is 12: 12 raw becomes 20/20.** Reading 12/25 as the public score would be wrong.

The displayed whole score determines the tier: 95+ Exceptional; 90+ Excellent; 80+ Very good; 70+ Good; 55+ Needs improvement; below 55 Poor. A quality tier is not a personal safety conclusion.

## 2. What happens before points are awarded

1. **Clean:** preserve label identity, quantities, units, serving size, directions and source lineage; identify active versus inactive/parent/display rows.
2. **Enrich:** resolve ingredient/form identities, benchmarks, research, certifications and safety evidence. “Unknown” must remain distinct from “verified absent.”
3. **Score:** the canonical classifier chooses one route. Safety and completeness gates run before that route's numerical scoring. The route computes dimensions; the shared assembler produces all six public pillars and an auditable receipt.
4. **Export:** validate and consume the scored artifact. Export does not run another scoring system.
5. **App:** render the pipeline's score and assessment. The app does not calculate a replacement score or infer that a good score means a product is suitable for a particular person.

Confirmed banned/recalled products retain their reasons and suppress a rankable number. An unusable product is `not_scored`, rather than being assigned a convincing-looking invented score. Other cautions can coexist with a numerical quality score. Unfinished PharmaGuide research/identity work is distinguished from a label that genuinely withholds information.

**One fact, one numerical owner:** form chemistry → Formulation; amount/over-limit quality deduction → Dose; clinical support → Evidence; hidden blend amounts → Transparency; certification → Verification; additive/sugar formula deductions → Formula checks. A concern can be explained in several places without being deducted several times.

## 3. Formulation — how points are earned and lost

### Generic single ingredients

The ingredient-quality map (IQM) owns form ratings. Its `bio_score` is an ordinal, parent-relative 0–15 quality calibration. It is **not percent absorbed, clinical effect size, or a universal comparison between unrelated nutrients**. Parent-relative resolution matters: use the resolved form quality, not a number copied out of a different parent's record.

The generic form component averages eligible ingredient form values; the generic IQM profile uses a 15-point reference. A product with only an unrated form uses the shared neutral value of 9 raw, equivalent to 12/20, with an unknown/not-rated explanation. A low reviewed form rating lowers credit; unknown is not automatically poor.

Additional retained mechanisms include independently eligible delivery technology (tier 1/2/3: 3/2/1 raw, cap 3), eligible absorption support (cap 3), and applicable standardization credit. They can raise the public pillar only up to 20. **Chemistry already represented in the form rating cannot earn a second delivery bonus simply because the label says “chelated,” “complex,” or gives a preparation a brand name.** A distinct supported delivery mechanism must pass the existing eligibility owner.

### Preparation-specific profiles

- **Botanical:** retained reference 12: identity-neutral 7.2 + extract credit 1.6 + standardization up to 3.2. Lower standardization tiers receive 2.4 or 1.6. An extract ratio alone does not prove clinical superiority.
- **Collagen:** reference 8: identity-neutral 4.8 + hydrolysis 3.2.
- **Multivitamin/prenatal:** panel form-quality reference 12.
- **B-complex:** B-vitamin form-quality reference 8.
- **Protein:** source-quality reference 15; its own preparation/source rules apply.
- **Fiber:** source-quality reference 12.
- **Probiotic:** form/preparation and eligible delivery reference 15; naming more strains does not manufacture form-quality credit.
- **Omega:** molecular form and concentration, described fully below; reference 12.

Ingredients do not automatically earn Formulation points for count, breadth, being “natural,” organic/Non-GMO badges, a printed dose, research strength, or a familiar brand. Additive/sugar deductions belong to Formula checks, rather than being silently charged here again.

**20/20 means maximum credit under this implemented Formulation rubric. It does not establish that the form is clinically best for every person or purpose, that the whole formula was trialed, or that all six pillars are perfect.** Optional distinct components and the cap can produce the same 20 through different paths.

## 4. Dose — one serving for product quality, daily directions for separate safety

The declared serving is the Facts-panel serving, which may itself be multiple capsules. It is not necessarily one pill. Manufacturer directions may recommend several such servings daily; that larger amount is preserved for the separate daily-use safety assessment.

Example: one capsule contains 120 mg magnesium; directions permit 1–4 capsules daily. Dose quality now evaluates **120 mg**, while the maximum labeled daily warning evaluates **480 mg**. The warning does not assert that the user actually consumes 480 mg. The app should not place an unqualified “high dose” beside 120 mg merely because maximum directions reach 480 mg.

### Generic benchmark paths

- Applicable nutrient RDA/AI or authored clinical-purpose benchmarks determine adequacy. The scored amount is not inflated by the label's maximum daily range.
- The DRI vitamin/trace-mineral ramp reaches half window credit at 20% RDA/AI and full at 100%; lower amounts receive proportional credit. **Magnesium and calcium retain a separate legacy 25%-RDA full-credit threshold.** Do not present the whole Dose pillar as uniformly requiring 100% RDA.
- Generic upper-limit window handling reduces credit above the supported UL: over 100% but below 150% receives half window credit; at least 150% receives zero window credit. Eligible B7 flags also reduce Dose, at 2 raw per flag capped at 3 raw, under the typed safety owner. This describes existing combined Dose behavior; it is not a second Formula-checks charge.
- Clinical-purpose windows are ingredient/purpose-specific. Below-near amounts receive proportional credit; no universal dose target can replace the authored ranges.
- A disclosed amount with no applicable benchmark earns the generic neutral **11.4/20**, including supported botanical/collagen and sports off-list fallback paths. An amount withheld despite an applicable benchmark earns no substitute credit. An unresolved benchmark identity remains an unfinished assessment.
- Probiotic has a different rule: no assessed strain-dose benchmark means no Dose credit. Generic neutrality must not be copied onto that route.

**Important limitation for clinical review:** changing the assessment to one serving does not transform an authored daily clinical benchmark into proof of an effect from a single serving. The product score is now standardized to serving size; sports/fiber/omega benchmark calibration should be reviewed with that distinction in mind.

## 5. Evidence — research support is separate from amount and brand

Evidence does not mean “a trial proved this exact bottle works.” It may be ingredient-level evidence, preparation-specific research, or established nutritional authority. The result records that distinction.

Generic research scoring considers qualifying ingredient evidence, positive/mixed/null/unfavorable findings, study applicability and authored weighting. The internal per-ingredient cap is 7; retained top-contribution weights are 1, 0.7, 0.5 and 0.3, with a bounded research-depth addition. The structural reference is 18 raw → 20 public. Primary-ingredient floors can drive the result (strong 14 raw, moderate 11; qualifying branded evidence floors 18/17); an applicable nutrition-authority floor is 10 raw. These are PharmaGuide calibration values, not quantities measured by a paper.

Null and unfavorable results earn no affirmative evidence credit. Identity, route, preparation, purpose and population can prevent a paper from applying. A real PMID about the wrong preparation is not qualifying evidence. Unknown/not-yet-reviewed, reviewed-zero and applicability-unestablished states must have different explanations even when their numerical contribution is zero.

- **Sports:** evidence follows purpose-owning actives; trace vitamins cannot manufacture a sports evidence score.
- **Multivitamin/B-complex:** evidence follows the route-defining essential nutrient panel and nutritional-authority disposition; incidental add-ins cannot inflate it.
- **Probiotic:** research certainty /10 + product applicability /6 + independent replication/consistency /4. Research certainty is credited only when it applies to the assessed preparation/purpose/population. More CFU alone is not more evidence.
- **Omega:** uses its own reviewed purpose standard, not the generic adjunct-ingredient calculation. See section 10.

A missing review can lower or leave incomplete the assessment. It must not be explained as “science proves no benefit.” Conversely, a familiar ingredient does not justify invented positive credit.

## 6. Transparency — disclosure earns points; misleading or hidden information loses them

For generic products, the internal /10 calculation starts with a clear-label base of 6 and complete active disclosure of 4, then deducts applicable penalties; it maps to /15 publicly. The base requires resolved active identities, rather than any label text being treated as full disclosure.

Shared deductions include:

- **B2:** a supported contradiction of a free-from/allergen claim; severity values up to 2 raw (high 2, moderate 1.5, low 1). Merely printing an optional claim earns no positive points.
- **B5:** proprietary-blend opacity, based on disclosure completeness and hidden payload, not the word “blend” alone. Existing raw base/variable values are 0/0 for full disclosure, 1/3 for partial, 2/5 for none; class multipliers include generic 1, probiotic 0.4, multi 1.3 and sports 1.5. The exact helper applies its count denominator, caps and trivial-payload rules before subtraction.
- **B6:** an applicable disease/marketing claim deduction (5 raw for the disease-claim rule). Clinical implications and any caution remain separately owned.

Multivitamins instead allocate 5 raw to panel identity disclosure and 10 to individual amounts (/15); low-value adjunct blend penalties have a bounded exception when the main panel is adequately disclosed. Probiotics allocate 8 to identity and 7 to per-strain CFU disclosure; an aggregate CFU disclosure proxy can earn 4 of the latter without earning strain Dose adequacy. Omega uses a dedicated /11 rubric below.

Disclosure earns Transparency credit even when the disclosed form is mediocre. Form quality and honestly naming that form answer different questions.

## 7. Verification — scope of proof matters

All routes feed the same public assembler. It starts from **6/15 neutral when verification is unknown**, rather than interpreting missing verification data as a failed laboratory test.

| Strongest supported evidence tier | Public treatment before violations |
|---|---|
| Unknown | 6 |
| Label claim, own testing, reputation, traceability/COA/QR wording | Maximum 8 |
| Verified manufacturing/facility evidence | Maximum 10 |
| Registry-backed product SKU or curated product-line certification | At least 11; up to 15 |

Mechanically, the positive base is 6 + eligible certification + traceability + audited GMP + testing posture + eligible brand/facility certification + eligible reputation. The strongest tier limits or floors this base; positive credit is capped at 15. Quality-system violations are then subtracted, down to zero.

Current magnitudes: registry certification contribution is 12 when retained B4a ≥10, 9 when ≥6, and 5 when ≥1; label-asserted certification contributes 2 under the claim tier. Traceability contributes `(B4c/2) × 5`, capped at 5. Audited GMP adds 2; own-testing posture adds 2; eligible brand/facility certification adds 2 when no product registry certification supersedes it; reputation is capped at 2 and is not added again when derived from the same mid-tier certification evidence.

B4a itself is generated by the route's certification owner; those raw certification points are not an additional public bonus. A sufficiently strong registry-backed cert can saturate 15 without collecting every possible badge.

**USP Verified, NSF facility registration and NSF Certified for Sport have different scopes.** Product evidence must match the supported SKU/line; a brand's facility listing must not be silently upgraded into independent testing of every bottle. Label-only “GMP” or FDA-registration wording does not earn audited-GMP credit. Certification can support quality verification; it does not prove greater clinical efficacy.

## 8. Formula & quality checks — a bounded 10-point budget

This starts from the supported clean base, up to 10. Confirmed high-risk/watchlist findings can remove that base; unconfirmed review signals must not do so automatically. Hard banned/recalled gates can suppress the entire score instead.

Deductions within this budget include eligible serious manufacturer recall/contamination findings, formula additives/sweeteners/sugars and the existing bounded clean-label policy. Non-critical manufacturer quality-system violations belong to Verification.

Current harmful-additive raw severity magnitudes are critical 4, high 3, moderate 2 and low 0.5; dietary-sugar/sweetener rules use their own authored categories (including 1, 2, 3 and 4-point magnitudes, sugar component capped at 4). These are not a direction to charge every named excipient: matching, eligibility, role and deduplication must pass first. The combined additive/sweetener public charge cannot exceed this pillar's 10-point budget. Separate role-weighted clean-label charges are bounded by their existing owner and the final zero floor.

A low-concern excipient quality deduction must be explained as formula quality, not presented as a clinical danger. A full 10 means no point-losing concern in the checks performed, **not that pregnancy, medications, all conditions and the user's complete regimen were assessed**.

Maximum daily dose warnings remain visible. Their B7 quality deduction belongs only to serving-based Dose; it is not deducted a second time here. Some “What to consider” items are contextual warnings without a numerical deduction.

## 9. How the category rubrics differ

“Single ingredient” is a scoring concept; “single serving” is an amount basis. A multivitamin can also have a one-capsule serving. Category routing depends on canonical identities, product purpose and guarded label/taxonomy signals, not just a marketing word.

| Category | Formulation emphasis | Dose emphasis | Evidence emphasis |
|---|---|---|---|
| Generic vitamin/mineral/single molecule | IQM form quality; eligible distinct technology | RDA/AI or authored purpose window | Applicable ingredient research/authority |
| Botanical | Extract preparation and standardization | Preparation/purpose-specific amount | Applicable botanical preparation, not a vaguely similar plant |
| Collagen | Collagen preparation/hydrolysis | Applicable collagen amount benchmark | Matching preparation and assessed outcome |
| Multivitamin/prenatal | Panel form quality | Coverage plus critical nutrients; prenatal complement | Essential-nutrient panel authority |
| B-complex | Core B-vitamin form quality | Coverage of fixed core B panel | B-panel nutritional authority |
| Sports/protein/pre-workout/amino acids | Generic forms or protein-source adapter | Best eligible supported primary sports anchor, not sum of every active | Purpose-owning sports ingredients |
| Fiber/digestive | Fiber source or applicable generic preparation | Fiber grams; nonfiber enzymes use generic owner/activity units | Applicable fiber/digestive purpose |
| Probiotic | Preparation/form and eligible delivery | Measured strain adequacy | Certainty + applicability + independent replication |
| Omega | Molecular-form quality + EPA/DHA concentration | Disclosed EPA+DHA; prenatal DHA exception | Reviewed omega purpose/population standard |

### Multivitamin and B-complex Dose details

Multi coverage contributes up to 15 raw; critical nutrient coverage up to 5; prenatal DHA complement up to 1. The public reference is 20 for adult multi and 21 when the prenatal complement is assessed. Targeted gap-filler products use their existing targeted anchor selection rather than pretending to be complete multis. Prenatal coverage uses the source-carried pregnancy reference where available.

Multi per-nutrient coverage: below 25% RDA → `pct/50`; 25–<50% → `0.5 + (pct−25)/25 × 0.35`; 50–200% → 1; >200–500% → 0.85; >500% → 0.65. UL handling takes priority: >100% UL → 0.5, ≥150% UL → 0. Critical thresholds use their own retained nutrient rules; choline's threshold is 25% RDA and folate/iron/iodine/D/B12 thresholds are 50%. Falling short but positive earns partial critical credit rather than full. The shared B7 owner applies eligible excess-dose deductions.

B-complex coverage averages against the fixed core panel, not only nutrients that happened to be printed, and contributes up to 18 raw (reference 18). Below 50% RDA it uses the same low-dose ramp; 50–300% earns 1; >300–1000% 0.9; >1000% 0.75, with a 0.95 exception for B12/biotin above 300% when no UL applies. >100% UL gives 0.4; ≥150% gives 0. B7 remains Dose-owned. These are implemented editorial bands, not assertions that a 300%-RDA B complex is a clinical optimum.

### Sports Dose details

These are current primary-anchor raw points, before the public reference and shared excess-dose handling. Missing usable amounts give zero; eligible off-list disclosed ingredients delegate to the generic owner. Multiple listed actives do **not** simply add all these scores: the scorer selects the highest supported eligible anchor. That selection itself is a reviewable policy choice for combination products.

| Anchor | Implemented bands per declared serving |
|---|---|
| Protein | <15 g: 8; 15–<20 g: 16; 20–40 g: 20; >40 g: 16 |
| Creatine | <2 g: 8; 2–<3 g: 16; 3–10 g: 20; >10 g: 16, except labeled loading protocol up to 20 g retains 20 |
| Beta-alanine | <2 g: 8; 2–<4 g: 16; 4–6 g: 20; >6 g: 16 |
| L-citrulline | <3 g: proportional toward 16 at 3 g; 3–<6 g: 16; ≥6 g: 20 |
| Citrulline malate | <6 g: proportional toward 14 at 6 g; 6–<8 g: 14; ≥8 g: 20 |
| HMB | <1.5 g: proportional toward 8; 1.5–<3 g: 16; 3–6 g: 20; >6 g: 16 |
| Alpha-GPC | <300 mg: proportional toward 8; 300–<600 mg: 14; ≥600 mg: 20 |
| ATP | <400 mg: proportional toward 6; ≥400 mg: 12 |
| Caffeine | <150 mg: proportional toward 8; 150–<200 mg: 14; 200–400 mg: 18; >400 mg: 14 |
| Betaine | <2.5 g: proportional toward 10; ≥2.5 g: 16 |
| Taurine | <1 g: proportional toward 6; ≥1 g: 10 |

The citrulline branches currently have no later upper-dose reduction despite band labels mentioning upper ranges. Describe the executed comparisons, not the labels as if they were enforced ceilings. This is a clinical calibration review item, not a change approved by this packet.

BCAA: incomplete profile with a disclosed aggregate earns proportional-to-8 below 2 g, 10 at 2–<5 g, 14 at ≥5 g. A complete disclosed profile earns proportional-to-12 below 3 g, 12 at 3–<5 g, and at ≥5 g earns 20 with the accepted ratio or 14 without it. The accepted composition check can add 2 raw. EAA: fewer than six assessed amino acids earns zero; six to eight earns up to 12; complete nine earns proportional-to-12 below 5 g, 14 at 5–<8 g and 20 at ≥8 g, with 2 composition points when complete. The reference becomes 22 when BCAA/EAA composition is assessed, otherwise 20.

### Fiber and probiotic Dose details

Fiber raw bands: ≥7 g →22; ≥5 g →18; ≥3 g →13; ≥1 g →7; positive <1 g →`max(1, grams×4)`; zero →0. Public reference 22. The owner prefers applicable Nutrition Facts dietary fiber over ingredient mass and preserves whether it is total dietary fiber or ingredient mass; neither automatically establishes soluble-fiber content.

Probiotic Dose normally uses a 15-raw reference. For measured strains, the retained adequacy tiers low/adequate/good/excellent map to 0/1/2/3, normalized to 0/5/10/15 raw. The strongest qualifying measured strain drives adequacy, not a sum that rewards adding strains. Manufacture-only or unknown guarantee basis retains conservative reliability factors of 0.90 or 0.85 in the upstream assessment. Postbiotic/inactivated rows do not receive live-CFU credit. Total CFU, more named species, or strain mass without usable CFU does not substitute for this assessment.

**Studied-formula exception:** a source-assessed complete probiotic formula at its reviewed native dose can own the full internal Dose dimension (25 raw, then capped to 20 public against reference 15), without invented per-strain allocations. Individual allocation disclosure remains separately assessed in Transparency. Pending unresolved AFU measurements carry an unresolved-reference state, not a fabricated CFU conversion. The live studied-formula owner must establish that exception; it is not available to any blend that merely prints a total count.

## 10. Omega — complete public scoring walkthrough

### 10.1 Which products and amounts qualify?

Fish, krill and algal products can route here when the canonical class supports it. Prenatal omega-primary products use omega; a genuine prenatal nutrient panel can use multi/prenatal instead. ALA-only/flax products are not automatically EPA/DHA products.

The omega completeness rule requires a usable positive EPA, DHA or combined EPA+DHA amount. A bottle stating only “fish oil 1,000 mg” cannot be treated as 1,000 mg EPA+DHA. A pure EPA or DHA product can pass completeness even when the later Evidence standard remains unestablished for its identity/purpose.

```text
separate_total = disclosed EPA + disclosed DHA
active_total = max(separate_total, disclosed combined EPA+DHA)
```

That avoids adding a combined row twice when the label also lists its EPA and DHA components. Carrier oil mass is not active EPA+DHA mass. Units must resolve through the shared contract; a title cannot supply an omitted amount.

### 10.2 Formulation /20

Two retained components:

1. **Molecular-form quality: up to 8 raw.** Read mapped IQM rows and parent-relative form quality. When parent oil rows exist, they own the preparation; otherwise EPA/DHA rows can carry it. If multiple qualifying forms have unknown proportions, the weakest reviewed form is retained. `raw_form_component = resolved_quality_0_15 / 15 × 8`. No separate obsolete TG/rTG/PL/EE lookup overrides IQM.
2. **EPA+DHA concentration: up to 4 raw.** `ratio = active_total / disclosed_parent_oil_mass`.

| Active EPA+DHA share of oil | Concentration raw | Public contribution before cap |
|---|---:|---:|
| ≥75% | 4 | 6.7 |
| ≥50%, <75% | 3 | 5.0 |
| ≥30%, <50% | 2 | 3.3 |
| ≥15%, <30% | 1 | 1.7 |
| <15% | 0 | 0 |

If the oil row is absent, an eligible declared Total Fat amount plus its rounding upper bound can conservatively supply the denominator: +0.25 g up to 5 g declared fat, +0.5 g above. Without a defensible denominator, concentration earns zero and explains the missing input. An oil denominator smaller than EPA+DHA is inconsistent, not permission to display >100% concentration or award full credit.

```text
public omega Formulation = round(min(20, (form_raw + concentration_raw) / 12 × 20), 1)
```

Source disclosure, premium-form carry and sustainability certification give **zero Formulation points**. Source/form disclosure belongs to Transparency; an eligible independent testing program belongs to Verification. An MSC/Friend of the Sea attribute is not proof of purity, efficacy or an extra form bonus.

### 10.3 Dose /20

**Subsequent evidence review:** the current 2,000 mg full-credit curve is not justified as an ordinary-adult general-nutrition requirement. See the [omega dose analysis and proposed correction](OMEGA_DOSE_REVIEW_2026-10-17.md). The table below remains a description of current implementation; no replacement has been approved or applied.

After the shared serving wrapper, the scoring amount is active EPA+DHA **per declared serving**. Historical internal names such as `min_mg_day` survive in the rubric; they do not override the wrapper.

| EPA+DHA amount | Anchor Dose points |
|---|---:|
| <100 mg | 0 |
| 100 mg | 2.5 |
| 200 mg | 4 |
| 250 mg | 5 |
| 500 mg | 10 |
| 1,000 mg | 16 |
| 2,000 mg | 20 |
| 4,000 mg and above | 20; prescription-dose context flag at 4,000 |

**Between positive anchors, points interpolate linearly.** For example, 750 mg earns 13, not 10 or 16. Below 100 mg there is a zero-credit floor, not a ramp. Above 2,000 mg there is no additional positive Dose credit. The reference is 20, so these are also the public points before any applicable shared dose-safety adjustment.

Prenatal DHA exception: a prenatal-titled DHA-dominant product with explicit DHA compares its DHA amount to the retained target of 200 mg. ≥200 mg earns 20; ≥100 but <200 earns 14; positive below 100 earns 10. It takes the higher of this and the ordinary EPA+DHA band, not their sum. A combined EPA+DHA amount alone does not reveal the DHA fraction.

There is **no generic EPA:DHA ratio bonus**. These are product-quality calibration anchors; they are not personalized dosing advice and do not make a supplement equivalent to a prescription. The ordinary adult Dose scale still favors larger quantities despite general nutritional adequacy at a lower anchor. That trade-off deserves explicit clinical review.

### 10.4 Evidence /20

The live `resolve_omega_evidence_standard` selects a reviewed purpose record from `INGR_OMEGA3` and reads its score from the shared config. It does not add generic evidence from incidental D3/CoQ10, award a second amount bonus, or use a retired “clinical floor + indication bonus” formula.

| Applicable current standard | Public Evidence |
|---|---:|
| Ordinary adult, explicit EPA **and** DHA, no overriding held context | 10.4 |
| Explicit affirmative adult triglyceride-lowering purpose, qualifying identity/context | 20 |
| Prenatal with explicit DHA, no earlier held context | 11.1 |
| Held child/baby, specialized pro-resolving preparation, mixed purpose ownership or incomplete required identity | 0 numerical credit with the appropriate held/applicability state |

Priority matters: child/specialized/mixed-purpose holds run before the prenatal branch; ordinary EPA-only/DHA-only/incomplete identities do not automatically inherit the adult combined standard. Negated triglyceride claims do not activate the strong-purpose branch.

**The current fixed Evidence credit is purpose/population-selected and amount-independent.** The resolver records daily exposure for context but does not require the product's serving to meet a triglyceride-treatment dose before assigning the 20-point purpose standard. Dose is supposed to carry amount adequacy separately. This is a deliberate separation to review, not proof that any product claiming triglyceride support will produce the studied treatment effect.

Prenatal preterm-outcome credit is not added; EPA depression and high-dose atrial-fibrillation context are not positive ordinary-product efficacy bonuses. No universal cardiovascular prevention claim or prescription equivalence follows from this score.

### 10.5 Transparency /15

Internal /11 positives:

- Explicit positive EPA **or** DHA component amount: 5.
- Recognized molecular-form disclosure: 3.
- Supported source disclosure: 3.

```text
public omega Transparency = round(clamp((positive − B2 − B5 − B6) / 11 × 15), 1)
```

All three →15. EPA/DHA and source but no form →8/11×15=10.9. EPA/DHA alone →6.8. The combined-only row can satisfy completeness/Dose while not satisfying this more specific EPA-or-DHA component disclosure test; do not assume those gates are identical. Optional free-from/vegan/gluten-free claims give no positive bonus. Oxidation testing belongs to Verification, not this pillar.

### 10.6 Verification /15 and Formula checks /10

The shared rules in sections 7–8 apply. Omega certification matching must respect product/line versus facility/brand scope. The current omega trust owner awards retained raw B4a 10 for qualifying SKU/product-line certification, 2 for label-asserted product certification and zero for unsupported/held scopes; the shared public assembler interprets those inputs. COA/lot lookup is traceability context, not automatic proof of an independently tested current lot.

A verified program supporting oxidation/purity testing is a Verification fact; molecular chemistry is Formulation. A sustainability badge cannot be repurposed as purity proof. A full Formula-checks score is not a personal no-interaction guarantee.

### 10.7 Worked omega example — illustrative, not a real product claim

Assume a qualifying ordinary-adult product has a **resolved** form-quality value of 12/15; EPA 400 mg + DHA 350 mg in 1,000 mg disclosed oil per serving; all three omega disclosures; no point-losing formula findings. Assume no evidence-context hold or extra dose-safety adjustment.

| Pillar | Calculation | Points |
|---|---|---:|
| Formulation | `(12/15×8 + 4 concentration) /12 ×20` | 17.3 |
| Dose | 750 mg interpolates halfway between 500/10 and 1,000/16 | 13 |
| Evidence | Ordinary adult explicit EPA+DHA standard | 10.4 |
| Transparency | 11/11×15 | 15 |
| Verification | Unknown, neutral | 6 |
| Formula checks | No point-losing finding in checks performed | 10 |
| **Total** | 71.7 analytical →72 shipped | **72, Good** |

With sufficiently strong registry-backed certification reaching Verification 15, the same hypothetical product becomes 80.7 →81, Very good. Nothing about EPA/DHA dose or clinical evidence changed. This is why comparing only the oil form cannot explain the entire product score.

## 11. Questions for the clinical/dev team

These are review questions, not approved scoring changes:

1. Should general adult omega Dose still rise from 5 at 250 mg to 20 at 2,000 mg, or should targets depend on purpose while keeping treatment-dose context separate?
2. Is amount-independent 20/20 triglyceride-purpose Evidence, paired with separate Dose adequacy, the clearest and least misleading contract? How should the app describe a low-dose product on that branch?
3. Are the prenatal positive-low-dose floor of 10 and the ordinary <100 mg zero floor intentional and defensible together?
4. Does the fixed serving-based product comparison fairly communicate ingredients whose supporting studies used divided daily intake, particularly creatine, beta-alanine, HMB, omega and fiber?
5. Are the retained magnesium/calcium 25%-RDA threshold and different multi/B-complex coverage bands still the desired policy?
6. Are residual sports amount branches that explicitly cite evidence weakness (ATP, taurine/BCAA) conceptually duplicating Evidence, and should they be reviewed together rather than changed product by product?
7. Does highest-anchor sports Dose sufficiently represent a multi-active product's intended purpose? Are the unbounded upper citrulline branches intentional?
8. Are category-neutral unknown values (Formulation 12, generic Dose 11.4, Verification 6) explained distinctly from verified excellence, and are held Evidence states visible enough?
9. Should concentration be a Formulation quality component at its current 6.7/20 maximum public contribution, independent of clinical evidence?

Do not “fix” an unexpected brand order by assigning brand-specific scores. Trace the six pillars, label identity, certification scope, preparation and amount, then correct the shared owner if evidence shows a defect.

## 12. Source map and reproducibility

These are relative repository links for GitHub/team use. Config values alone are insufficient: follow the active caller and public assembler. Some old module comments still describe retired daily/rubric rules; the executed code below and its artifacts take precedence.

| Question | Current owner |
|---|---|
| Public pillar math, tiers, receipts | [quality_score.py](../../scripts/scoring_v4/quality_score.py): `_pillar_formulation`, `_pillar_dose`, `_pillar_evidence`, `_pillar_verification`, `_pillar_safety_hygiene`, `assemble_quality_score` |
| Magnitudes and normalization references | [quality_score.json](../../scripts/scoring_v4/config/quality_score.json) |
| Routes, score-eligible rows, EPA/DHA ownership, serving projection | [scoring_input_contract.py](../../scripts/scoring_input_contract.py) |
| Serving wrapper and isolated frequency scope | [generic_helpers.py](../../scripts/scoring_v4/modules/generic_helpers.py), [serving_frequency.py](../../scripts/serving_frequency.py) |
| Generic component math | [generic_formulation.py](../../scripts/scoring_v4/modules/generic_formulation.py), [generic_dose.py](../../scripts/scoring_v4/modules/generic_dose.py), [generic_evidence.py](../../scripts/scoring_v4/modules/generic_evidence.py), [generic_transparency.py](../../scripts/scoring_v4/modules/generic_transparency.py) |
| Multi/prenatal | [multi_prenatal_dose.py](../../scripts/scoring_v4/modules/multi_prenatal_dose.py), corresponding formulation/evidence/transparency modules |
| B panel | [b_complex.py](../../scripts/scoring_v4/modules/b_complex.py) |
| Sports | [sports_dose.py](../../scripts/scoring_v4/modules/sports_dose.py), [sports_formulation.py](../../scripts/scoring_v4/modules/sports_formulation.py) |
| Fiber | [fiber_digestive_dose.py](../../scripts/scoring_v4/modules/fiber_digestive_dose.py), corresponding formulation module |
| Probiotic | [probiotic.py](../../scripts/scoring_v4/modules/probiotic.py), corresponding dose/evidence/formulation/transparency modules |
| Omega | [omega_rubric.json](../../scripts/data/omega_rubric.json), [omega.py](../../scripts/scoring_v4/modules/omega.py), [omega_formulation.py](../../scripts/scoring_v4/modules/omega_formulation.py), [omega_dose.py](../../scripts/scoring_v4/modules/omega_dose.py), [omega_transparency.py](../../scripts/scoring_v4/modules/omega_transparency.py), [omega_evidence.py](../../scripts/scoring_v4/modules/omega_evidence.py), [omega_trust.py](../../scripts/scoring_v4/modules/omega_trust.py) |
| Omega purpose selection | [evidence_resolver.py](../../scripts/evidence_resolver.py): `resolve_omega_evidence_standard` |
| Certification scope | [cert_evidence.py](../../scripts/scoring_v4/cert_evidence.py) |
| Technical specification | [SCORING_ENGINE_SPEC.md](../../scripts/SCORING_ENGINE_SPEC.md) |

For an individual product review, preserve the raw label, enriched input, route, engine/config fingerprints, six public pillars, raw component receipt, Evidence state, dose basis, quality status and independent safety status. Compare affected examples and unaffected controls. A passing test confirms implementation behavior; it does not independently establish clinical validity of the calibration.

**Next operational step remains Sean's pipeline run, not another scoring change caused by this documentation.** After it finishes, qualify the new artifacts and catalog against source before publication. This packet did not run the pipeline, change scoring policy, publish a catalog or build an IPA.
