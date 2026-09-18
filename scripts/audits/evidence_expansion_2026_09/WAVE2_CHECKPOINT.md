# Wave 2 checkpoint — 50 unreviewed identities searched and screened (2026-09-18)

**No production evidence write, no score movement, no catalog rebuild, no release.** The only
production change in this branch since the last checkpoint is the four legacy scope repairs
(`LEGACY_SCOPE_REPAIR.md`), which are measured and committed separately. Wave 2 has authored
nothing into the registry.

## What was done

| stage | measure |
|---|---:|
| identities searched | 50 |
| PubMed queries run and logged | 150 |
| records retrieved | 3192 |
| records classified deterministically | 3192 |
| efficacy candidates after classification | 1504 |
| records read by a screener (shortlists) | 481 |
| sources selected by screening | 112 |
| selected sources re-verified live | 112 |
| identities with a catalog-visible integrity hold | 6 |

## Decision table

`class` is the screening recommendation, which is triage and untrusted until centrally verified.
`Evidence=0` is the number of products this identity leaves at Evidence 0 today.

| identity | products | Evidence=0 | retrieved | candidates | selected | class | action | blocker |
|---|---:|---:|---:|---:|---:|---|---|---|
| `common_bean_extract` | 22 | 21 | 8 | 5 | 4 | curate | deep-curate | Effective extracts are branded/standardized preparations (Phase 2, Phaseolean) whose specific al |
| `d_aspartic_acid` | 28 | 21 | 81 | 52 | 4 | curate | deep-curate | 40248985 is a 3-component combination product (DAA + ubiquinol + zinc) in a clinical infertility |
| `green_coffee_bean` | 76 | 21 | 40 | 22 | 4 | curate | deep-curate | This identity's own integrity_hold lists two retracted PMIDs (22291473, 25340633) for a well-kno |
| `feverfew` | 21 | 20 | 60 | 24 | 4 | curate | deep-curate | Feverfew is most often studied and dosed as standardized extract by parthenolide content, but th |
| `goji_berry` | 24 | 20 | 73 | 36 | 4 | curate | deep-curate | 34213407 and part of the underlying RCTs in 37773857/28401234 study Lycium barbarum polysacchari |
| `activated_charcoal` | 19 | 19 | 160 | 71 | 1 | curate | deep-curate | The evidence base is decontamination/overdose pharmacology (charcoal given within hours of a spe |
| `amla` | 52 | 19 | 74 | 38 | 4 | curate | deep-curate | One selected trial (40262554) uses a specific standardized extract (AMX-160/Tri-Low) that may no |
| `schisandra_berry` | 48 | 19 | 43 | 18 | 4 | curate | deep-curate | Two of the four selected trials are combination products (schisandra + soybean; schisandra + Rho |
| `theobromine` | 42 | 19 | 90 | 53 | 2 | curate | deep-curate | 37615657 dosed theobromine on top of a shared low-calorie diet in both arms; effect sizes are sm |
| `horsetail` | 57 | 18 | 32 | 13 | 2 | curate | deep-curate | 35168030 studies diagnosed hypertension patients and benchmarks against a prescription antihyper |
| `oregano` | 20 | 18 | 69 | 15 | 3 | curate | deep-curate | 34496170 and 34496170-type essential-oil dosing (mL or drops) may not map cleanly to a capsule/s |
| `fennel` | 37 | 17 | 126 | 63 | 3 | curate | deep-curate | None of the three selected meta-analyses states a single consistent oral dose or preparation for |
| `hoodia_gordonii` | 18 | 17 | 6 | 2 | 1 | curate | deep-curate | The only direct oral-Hoodia RCT found a null effect on energy intake and body weight, so it does |
| `mucuna_pruriens` | 31 | 17 | 43 | 11 | 4 | curate | deep-curate | All Parkinson's disease trials dose Mucuna like a drug (mg/kg or gram amounts titrated to replac |
| `cayenne_pepper` | 105 | 16 | 70 | 12 | 4 | curate | deep-curate | The positive and null findings come from materially different preparations (whole fruit powder,  |
| `d_mannose` | 25 | 16 | 68 | 37 | 4 | curate | deep-curate | Doses across the underlying primary trials range widely (200 mg to 2-3 g/day), and most of the s |
| `devils_claw` | 25 | 16 | 47 | 27 | 4 | curate | deep-curate | Effective doses are standardized to harpagoside content (50-100 mg/day), so a catalog product wo |
| `l_serine` | 26 | 16 | 55 | 28 | 3 | curate | deep-curate | 32520991 co-administers l-serine with EPA, so the pain-relief effect cannot be attributed to l-s |
| `tudca` | 16 | 16 | 54 | 22 | 4 | curate | deep-curate | 25664595 and 12183720 are in serious clinical disease populations (ALS patients on riluzole; TPN |
| `royal_jelly` | 17 | 15 | 97 | 52 | 4 | curate | deep-curate | No dose is given for the menopause meta-analysis (41401249) or the broader cardiometabolic umbre |
| `senna` | 15 | 15 | 132 | 94 | 4 | curate | deep-curate | 33767108 and 35943487 appear to be closely related/updated publications from the same review pro |
| `cat_s_claw` | 22 | 14 | 26 | 8 | 3 | curate | deep-curate | The osteoarthritis trial (11603848) uses Uncaria guianensis, a related but different species fro |
| `globe_artichoke` | 37 | 14 | 41 | 20 | 4 | curate | deep-curate | None of the three meta-analyses states a single consistent oral dose in the abstract, and severa |
| `holy_basil` | 37 | 14 | 21 | 9 | 4 | curate | deep-curate | The Cochrane diabetes review (15266492) gives only a brief, non-dosed mention of holy basil with |
| `siberian_ginseng` | 25 | 14 | 26 | 9 | 4 | curate | deep-curate | Across these four single-ingredient RCTs spanning fatigue, glycemic response, athletic performan |
| `l_ornithine` | 27 | 21 | 115 | 64 | 4 | hold | hold | All efficacy evidence in the shortlist is in cirrhosis/hepatic-encephalopathy patients, a clinic |
| `pregnenolone` | 22 | 20 | 90 | 59 | 4 | hold | hold | Every shortlisted quantitative record is from schizophrenia adjunct-therapy trials where pregnen |
| `hawthorn` | 31 | 19 | 111 | 69 | 2 | hold | hold | 18254076's population is diagnosed chronic heart failure (NYHA II) patients under medical superv |
| `alfalfa_leaf` | 18 | 17 | 59 | 8 | 2 | hold | hold | The only trial using alfalfa leaf itself (9677811) combines it with sage (Salvia officinalis) in |
| `dong_quai` | 33 | 17 | 81 | 38 | 2 | hold | hold | Neither review gives the underlying dong quai RCTs' own PMIDs, populations, or doses; central ve |
| `l_threonine` | 32 | 17 | 38 | 17 | 3 | hold | hold | The two ALS trials (8909433, 11231032) dose L-threonine only in combination with pyridoxal phosp |
| `chaga` | 19 | 16 | 22 | 1 | 1 | hold | hold | Combination herbal product — chaga (Inonotus obliquus) is only about 20% of a 4-herb blend, so t |
| `hops` | 46 | 16 | 109 | 64 | 2 | hold | hold | 40462685 tests a fixed valerian+hops combination product (Ze 91019), not hops alone, and is expl |
| `papaya_fruit_powder` | 18 | 16 | 61 | 27 | 1 | hold | hold | Nearly every other human study of Carica papaya in this shortlist uses a different plant part (L |
| `fo_ti` | 16 | 14 | 32 | 8 | 1 | hold | hold | No shortlisted trial compares oral Fo-Ti/Polygonum multiflorum extract against a true placebo; t |
| `l_cysteine` | 37 | 14 | 117 | 62 | 1 | hold | hold | The mechanism (locally neutralizing salivary acetaldehyde) is specific to a slow-release lozenge |
| `papaya` | 19 | 14 | 100 | 49 | 1 | hold | hold | Papain is combined with bromelain and chymotrypsin in every study reviewed; no trial isolates pa |
| `rosemary` | 38 | 14 | 116 | 59 | 1 | hold | hold | 40536553 does not isolate a rosemary-specific dose, trial population, or effect size from the ot |
| `white_willow_bark` | 33 | 14 | 28 | 9 | 1 | hold | hold | 17163262 is a 2-herb combination (feverfew plus willow) and an open-label study with no placebo  |
| `goldenseal` | 51 | 23 | 28 | 2 | 0 | handoff_only | route | No efficacy outcome studied in the shortlist; both records measure CYP450 enzyme activity, which |
| `dimethyl_glycine` | 23 | 22 | 3 | 2 | 0 | no_qualifying | record review state | Shortlist records concern a topical mouthrinse (C31G, alkyl dimethyl glycine/alkyl dimethyl amin |
| `silica` | 258 | 20 | 160 | 61 | 0 | no_qualifying | record review state | Every shortlisted record is either an occupational-dust inhalation exposure study or an in vitro |
| `yohimbe` | 56 | 20 | 24 | 3 | 0 | no_qualifying | record review state | The two intervention studies dose yohimbe only as part of a 3-ingredient stack (higenamine + caf |
| `wild_yam_root` | 19 | 19 | 6 | 1 | 0 | no_qualifying | record review state | Wrong route of exposure: the only shortlisted RCT used a topical cream, not an oral product, so  |
| `l_norvaline` | 21 | 18 | 13 | 3 | 0 | no_qualifying | record review state | No shortlisted record administers L-norvaline as a supplement; all are observational metabolomic |
| `cascara_sagrada` | 20 | 17 | 10 | 2 | 0 | no_qualifying | record review state | 29958034 tests an 8-ingredient 'detoxification' blend (papaya leaf, cascara sagrada bark, slippe |
| `l_proline` | 29 | 16 | 129 | 77 | 0 | no_qualifying | record review state | No shortlisted record administers L-proline as a supplement to humans; the search results are do |
| `aloe_vera` | 32 | 15 | 151 | 60 | 0 | no_qualifying | record review state | Every shortlisted record uses Aloe vera as a topical/local application (skin wounds, burns, psor |
| `chrysin` | 26 | 15 | 43 | 16 | 0 | no_qualifying | record review state | The only human RCTs involving chrysin (14559928, 11601567, 11725694) are 5-6 ingredient combinat |
| `eyebright` | 20 | 14 | 4 | 2 | 0 | no_qualifying | record review state | This appears to be a name-collision retrieval defect: the search matched the medical device comp |

## Where the wave landed

| class | identities | products | Evidence=0 products |
|---|---:|---:|---:|
| curate | 25 | 845 | 432 |
| hold | 14 | 389 | 229 |
| handoff_only | 1 | 51 | 23 |
| no_qualifying | 10 | 504 | 176 |
| **total** | **50** | **1789** | **860** |

## Screening QA

Screening output is untrusted input and is checked in code before any of it is used.

| check | result |
|---|---:|
| identities screened | 50 |
| PMIDs named that are not in that identity's own retrieval | 1 |
| selected sources outside the shortlist given | 0 |
| verbatim spans of 60+ characters copied from an abstract | 3 |
| class/content conflicts | 0 |

The one out-of-retrieval PMID is worth naming, because it shows what the check is for: a screener listed PMID 18206062 under `activated_charcoal` as an exclusion, correctly describing it as a criminology paper whose 'Hawthorne effect' has nothing to do with charcoal. The description is accurate and the record is real - it just was not in that identity's retrieval, so it came from the model rather than from the corpus. It is rejected on that ground alone.

Wave 1's screening produced 119 elided and 135 non-contiguous quotes that all had to be thrown away. Wave 2 forbade quotes outright, since every fact is re-extracted centrally anyway; three borderline copied spans appeared and were rejected. The defect class is effectively closed.

## Deep central verification — three identities read from the live sources

Screening is triage. These three were re-read centrally, source by source, because they carry the
wave's two best approval candidates and its worst integrity problem.

### `common_bean_extract` — the wave's first class-A candidate

22 products, 21 of them at Evidence 0, every label row printing "white kidney bean extract", measured
label median **1,500 mg/day** (p25 650 mg).

PMID 42066439 (Nutrition Research, 2026) is an **ingredient-level** meta-analysis of oral white kidney
bean (Phaseolus vulgaris) extract, 8 RCTs, n=543: weight −1.62 kg (95% CI −1.99 to −1.25), BMI −0.58
kg/m2, fat mass −1.17 kg, waist −1.58 cm, all P < .05, no serious adverse events. PMID 39170208 is a
branded (Phaseolean) placebo-controlled RCT at 1,500 and 3,000 mg/day, positive at both.

The material matches what the catalog prints, the dose is in the studied range, and the population is
adults with overweight — the people who buy it. **This is scorer-compatible today.** The caveat that
must travel with it: alpha-amylase inhibitor extracts are not standardised by inhibitor units, so
label milligrams are not a potency guarantee, and the pooled effect is small.

### `d_mannose` — class A, and blocked only by the parked null decision

25 products, 16 at Evidence 0, form uniformly "d-mannose", measured label median **1,000 mg**, p75
**2,000 mg**.

PMID 38587819 (JAMA Internal Medicine, 2024) is the decisive source: 598 women in 99 UK primary-care
centres, **2 g/day for 6 months**, placebo-controlled. Primary outcome null — 51.0% vs 55.7%, risk
difference −5% (95% CI −13% to 3%), P = .26 — and the authors state it should not be recommended for
prophylaxis in this group. PMID 41004704 (2025) pooled 6 RCTs and 1,167 participants and also found no
reduction (RR 0.57, 95% CI 0.29–1.15). The positive syntheses that screening surfaced are older and
weaker: PMID 32972899 (2021) is a narrative systematic review of mostly open-label studies, and PMID
39095666 is a network meta-analysis pooling those same older trials.

Everything needed to score this exists: a generic material, a studied daily dose that maps to real
labels, and an outcome the existing cranberry record already expresses. The direction is **null** —
so under the rule that a null record is not proposed for approval until the direction semantics are
decided, it cannot be approved. **The parked null decision has stopped being a scoring adjustment and
started blocking approvals.**

### `green_coffee_bean` — an integrity problem inside the syntheses

76 products, 21 at Evidence 0. Its own retrieval contains **two retracted records** (PMIDs 22291473
and 25340633), the retracted green-coffee-extract weight-loss trial. None of them was selected, and
the live verification pass confirmed no retracted or expression-of-concern record reached the selected
set. But all four selected sources are meta-analyses, and a meta-analysis can carry a retracted trial
inside it without saying so in its abstract. **No green coffee bean record may be authored until each
synthesis's included-study list is checked against those two PMIDs.** That is a curation-time
requirement, recorded here rather than assumed away.

Retracted or flagged records also appeared in the retrieval for goji berry, hawthorn, theobromine and
papaya. The retraction detector repaired earlier in this project (RetractionIn links that precede the
publication type) is what surfaced them.

## What the wave says about the expansion itself

25 of 50 identities have candidate human efficacy evidence worth deep curation, covering
432 of the 860 Evidence=0 products in the wave. 14 are held with real evidence the
current architecture cannot safely apply (229 products), and 10 have no qualifying evidence at
all (176 products).

The held and no-qualifying reasons repeat, and they are not curation failures:

- **combination products** — the trial gave the ingredient inside a multi-herb formula (hops with
  valerian, white willow with feverfew, holy basil with rhodiola and schisandra, chaga as a fifth of a
  four-herb blend);
- **wrong route** — the literature is topical or local, not swallowed (aloe vera, wild yam, dimethyl
  glycine);
- **clinical population and indication** — L-ornithine in hepatic encephalopathy, pregnenolone as an
  antipsychotic adjunct, hawthorn in diagnosed heart failure, TUDCA in ALS;
- **name collision** — the retrieval is about something else entirely (eyebright returned an
  intraocular-lens manufacturer; L-proline and L-norvaline returned endogenous-biomarker studies);
- **potency, not milligrams** — devil's claw is dosed by harpagoside content, feverfew by
  parthenolide, cayenne by capsaicin; a label's extract milligrams do not state those.

That last one is the structural finding of this wave. Several botanicals have genuine positive
evidence that the catalog cannot receive, because the studied exposure is a marker compound and the
label prints extract weight. It is the same shape as the Permixon and BR-DIM problems fixed this week,
and it will recur in every botanical wave.

## Handoffs

28 safety, pharmacokinetic or interaction findings were separated from efficacy during
screening rather than being folded into an efficacy direction. `goldenseal` (51 products) is
handoff-only: both of its retrieved human studies are CYP450 interaction work, and an interaction rule
for goldenseal already exists in the interaction owner's file. The full list is in the per-identity
screen files.

## What has not been done

No pending context was authored, so no record is owner-approvable yet. The two class-A candidates
above are the only identities verified to the depth that would justify one, and one of them
(`d_mannose`) is blocked by the null decision. Deep curation of the remaining 23 `curate` identities is
the next block of work, and it is where the cost is.

