# PRIMARY-MASS FLOOR — POLICY SIMULATION

Simulation only. No production constant, config, registry or product changed.

**Contract violations: 0.** Baseline is scored with the hook uninstalled, so it is production by construction; each product is then re-scored through the passthrough hook and the two must agree on Evidence, total and tier.

```
Products scored:                              15,109
Eligible for primary-mass floor:              11,786
Receiving a nonzero primary-mass floor:        5,485
  decisive (authority floor left intact):      5,029
  shadowed by the DRI authority floor:             0
  shadowed by the evidence pipeline:             456
Changes final 0-100 score:                     5,029
Changes published tier:                        2,690

Held out of every comparison, authority floor live in all variants:
DRI/nutrition-authority population:              672
```

Of the decisive products, **24** anchor their floor on a RECOVERED match carried on the product blob rather than on a record in the reviewed registry, and **0** have no resolvable anchor record at all. Counted, not fixed: the freeze holds.

The two shadowed rows matter: removing the primary-mass floor produces no shipped change for those products, and for a real reason. Counting them as affected would overstate the rule exactly the way the first run did.

## Isolation regression case

```
{
 "baseline_evidence": 14.0,
 "evidence_without_mass_floor": 11.8,
 "raw_without_mass_floor": 10.0,
 "authority_floor_without_mass_floor": true,
 "note": "The old flag-based A/B read 14.0 -> 8.7 for this product because it disabled the authority floor as well."
}
```

## Where a cap is applied

raw Evidence space, inside _primary_mass_floor, BEFORE the archetype rescale - the same space the 14.0/11.0/10.0 floor constants live in. A cap of the same magnitude applied on the public 0-20 scale would mean a different raw amount per archetype (18.0 vs 17.0 references), so it is NOT interchangeable.

## Direction ceiling — derived, not tabulated

EFFECT_DIRECTION_MULTIPLIERS and PRIMARY_FLOOR_MODERATE, read live from generic_evidence. No second direction table.

```
{
 "positive_strong": "exempt - may still anchor on PRIMARY_FLOOR_STRONG",
 "positive_weak": 9.35,
 "mixed": 6.6
}
```

## Policy comparison

| policy | products changed | % of corpus | Evidence delta med/p90/max | final-score delta med/p90/max | tier changes (down/up) | unexpected gains | inversions introduced |
|---|---:|---:|---|---|---|---:|---:|
| `no_primary_mass_floor` | 5,029 | 33.28 | -6.4 / -2.1 / -0.1 | -6.4 / -2.1 / 0.0 | 2,690 (2,690/0) | 0 | 3 |
| `capped_uplift_3` | 4,064 | 26.9 | -4.7 / -1.2 / -0.1 | -4.7 / -1.2 / 0.0 | 1,605 (1,605/0) | 0 | 1 |
| `capped_uplift_5` | 2,993 | 19.81 | -3.3 / -0.1 / -0.1 | -3.3 / -0.1 / 0.0 | 1,015 (1,015/0) | 0 | 1 |
| `direction_ceiling` | 1,767 | 11.7 | -2.1 / -2.0 / -0.1 | -2.1 / -2.0 / -0.1 | 354 (354/0) | 0 | 0 |
| `study_strength_scaled` | 1,028 | 6.8 | -2.6 / -1.1 / -0.2 | -2.6 / -1.1 / -0.2 | 250 (250/0) | 0 | 0 |

Every mechanism here weakens or leaves the floor unchanged, so **unexpected gains should be 0**. A nonzero count means a policy raised a product's Evidence, which would be a defect in the mechanism, not a finding about the floor.

### `no_primary_mass_floor`

No such guarantee. Evidence is whatever the pipeline earns - but the DRI nutrition-authority floor still applies. This isolates the mass floor; it does not remove every floor.

- positive_weak changed: **1,139**, median Evidence after: **8.3**, p90 **11.6**, tier changes 526
- positive_strong changed: **3,249**, median Evidence after: **9.4**, p90 **12.2**, tier changes 1,925
- study-hierarchy inversions: **5** observed, 3 already present at baseline, **3 introduced by this policy**

| effect direction | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `positive_strong` | 3249 | -8.4 / -2.0 / -0.1 | -8.4 / -2.0 / 0.0 | 1925 |
| `positive_weak` | 1139 | -5.3 / -1.8 / -0.1 | -5.3 / -1.8 / -0.1 | 526 |
| `mixed` | 641 | -5.7 / -5.0 / -0.2 | -5.7 / -5.0 / -0.2 | 239 |

| study type | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `systematic_review_meta` | 3921 | -5.7 / -2.1 / -0.1 | -5.7 / -2.1 / 0.0 | 2047 |
| `rct_multiple` | 767 | -8.6 / -2.1 / -0.1 | -8.6 / -2.1 / -0.1 | 524 |
| `rct_single` | 339 | -5.4 / -1.1 / -0.3 | -5.4 / -1.1 / -0.3 | 119 |
| `clinical_strain` | 2 | -9.3 / -9.3 / -9.3 | -9.3 / -9.3 / -9.3 | 0 |

| module | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic` | 4704 | -6.3 / -2.0 / -0.1 | -6.3 / -2.0 / -0.1 | 2488 |
| `sports` | 220 | -8.6 / -3.0 / -0.1 | -8.6 / -2.8 / 0.0 | 138 |
| `fiber_digestive` | 105 | -9.0 / -5.0 / -1.1 | -9.0 / -5.0 / -1.1 | 64 |

| archetype | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic_single_molecule` | 3241 | -5.4 / -1.7 / -0.1 | -5.4 / -1.7 / -0.1 | 1686 |
| `generic_botanical_branded` | 1380 | -7.8 / -3.6 / -0.1 | -7.8 / -3.6 / -0.1 | 784 |
| `sports_single` | 168 | -9.6 / -5.7 / -0.1 | -9.6 / -5.7 / 0.0 | 119 |
| `fiber_digestive` | 105 | -9.0 / -5.0 / -1.1 | -9.0 / -5.0 / -1.1 | 64 |
| `immune_support` | 83 | -2.2 / -1.2 / -0.2 | -2.2 / -1.2 / -0.2 | 18 |
| `sports_bcaa_eaa` | 32 | -8.1 / -2.4 / -0.2 | -6.7 / -0.2 / 0.0 | 10 |
| `sports_protein` | 11 | -5.7 / -0.4 / -0.4 | -5.7 / -0.4 / -0.4 | 8 |
| `sports_pre_workout` | 9 | -1.8 / -1.8 / -0.1 | -1.8 / -1.8 / -0.1 | 1 |

| single active? | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `True` | 3019 | -8.1 / -2.1 / -0.6 | -8.1 / -2.1 / -0.6 | 1875 |
| `False` | 2010 | -4.5 / -1.1 / -0.1 | -4.5 / -1.1 / 0.0 | 815 |

Inversions INTRODUCED by this policy (within archetype and direction):

```
[
 {
  "archetype": "sports_single",
  "direction": "positive_strong",
  "stronger_study_type": "systematic_review_meta",
  "stronger_median_evidence": 6.0,
  "weaker_study_type": "rct_multiple",
  "weaker_median_evidence": 10.7
 },
 {
  "archetype": "generic_single_molecule",
  "direction": "positive_strong",
  "stronger_study_type": "rct_multiple",
  "stronger_median_evidence": 10.0,
  "weaker_study_type": "rct_single",
  "weaker_median_evidence": 11.1
 },
 {
  "archetype": "sports_bcaa_eaa",
  "direction": "positive_strong",
  "stronger_study_type": "systematic_review_meta",
  "stronger_median_evidence": 16.4,
  "weaker_study_type": "rct_multiple",
  "weaker_median_evidence": 17.4
 }
]
```

### `capped_uplift_3`

A BOUNDED GUARANTEE: being the primary active can add at most 3.0 raw points on top of what the formula's evidence already earned. Rank order between a weak and a strong evidence base survives instead of collapsing to a shared minimum.

- positive_weak changed: **672**, median Evidence after: **8.9**, p90 **12.2**, tier changes 265
- positive_strong changed: **2,796**, median Evidence after: **10.5**, p90 **14.9**, tier changes 1,231
- study-hierarchy inversions: **3** observed, 3 already present at baseline, **1 introduced by this policy**

| effect direction | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `positive_strong` | 2796 | -5.6 / -1.2 / -0.1 | -5.6 / -1.2 / 0.0 | 1231 |
| `positive_weak` | 672 | -4.3 / -1.1 / -0.2 | -4.3 / -1.1 / -0.2 | 265 |
| `mixed` | 596 | -2.4 / -1.6 / -0.7 | -2.4 / -1.6 / -0.7 | 109 |

| study type | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `systematic_review_meta` | 3208 | -4.3 / -0.9 / -0.1 | -4.3 / -0.9 / 0.0 | 1144 |
| `rct_multiple` | 674 | -6.0 / -2.0 / -0.4 | -6.0 / -2.0 / -0.4 | 387 |
| `rct_single` | 180 | -5.1 / -2.4 / -0.4 | -5.1 / -2.4 / -0.4 | 74 |
| `clinical_strain` | 2 | -6.0 / -6.0 / -6.0 | -6.0 / -6.0 / -6.0 | 0 |

| module | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic` | 3770 | -4.5 / -1.2 / -0.1 | -4.5 / -1.2 / -0.1 | 1452 |
| `sports` | 193 | -6.3 / -2.4 / -0.1 | -6.3 / -2.4 / 0.0 | 103 |
| `fiber_digestive` | 101 | -6.3 / -1.9 / -0.3 | -6.3 / -1.9 / -0.3 | 50 |

| archetype | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic_single_molecule` | 2486 | -3.7 / -0.9 / -0.1 | -3.7 / -0.9 / -0.1 | 900 |
| `generic_botanical_branded` | 1253 | -4.8 / -2.1 / -0.1 | -4.8 / -2.1 / -0.1 | 546 |
| `sports_single` | 159 | -6.3 / -2.4 / -0.3 | -6.3 / -2.4 / 0.0 | 91 |
| `fiber_digestive` | 101 | -6.3 / -1.9 / -0.3 | -6.3 / -1.9 / -0.3 | 50 |
| `immune_support` | 31 | -4.0 / -1.0 / -0.2 | -4.0 / -1.0 / -0.2 | 6 |
| `sports_bcaa_eaa` | 24 | -4.8 / -0.3 / -0.1 | -4.8 / 0.0 / 0.0 | 7 |
| `sports_protein` | 9 | -6.3 / -0.9 / -0.9 | -6.3 / -0.9 / -0.9 | 5 |
| `sports_pre_workout` | 1 | -0.6 / -0.6 / -0.6 | -0.6 / -0.6 / -0.6 | 0 |

| single active? | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `True` | 2688 | -5.1 / -1.2 / -0.7 | -5.1 / -1.2 / -0.7 | 1223 |
| `False` | 1376 | -2.7 / -0.4 / -0.1 | -2.6 / -0.4 / 0.0 | 382 |

Inversions INTRODUCED by this policy (within archetype and direction):

```
[
 {
  "archetype": "sports_single",
  "direction": "positive_strong",
  "stronger_study_type": "systematic_review_meta",
  "stronger_median_evidence": 9.3,
  "weaker_study_type": "rct_multiple",
  "weaker_median_evidence": 14.0
 }
]
```

### `capped_uplift_5`

The same mechanism at 5.0, so the reader sees a curve and not a number.

- positive_weak changed: **535**, median Evidence after: **10.7**, p90 **11.7**, tier changes 139
- positive_strong changed: **1,963**, median Evidence after: **11.6**, p90 **16.7**, tier changes 856
- study-hierarchy inversions: **3** observed, 3 already present at baseline, **1 introduced by this policy**

| effect direction | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `positive_strong` | 1963 | -4.0 / -2.2 / -0.1 | -4.0 / -2.2 / 0.0 | 856 |
| `positive_weak` | 535 | -2.5 / -1.5 / -0.4 | -2.5 / -1.5 / -0.4 | 139 |
| `mixed` | 495 | -0.1 / -0.1 / -0.1 | -0.1 / -0.1 / -0.1 | 20 |

| study type | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `systematic_review_meta` | 2234 | -3.3 / -0.1 / -0.1 | -3.3 / -0.1 / 0.0 | 685 |
| `rct_multiple` | 593 | -4.4 / -0.7 / -0.1 | -4.4 / -0.7 / -0.1 | 277 |
| `rct_single` | 164 | -2.9 / -1.2 / -0.1 | -2.9 / -1.2 / -0.1 | 53 |
| `clinical_strain` | 2 | -3.8 / -3.8 / -3.8 | -3.8 / -3.8 / -3.8 | 0 |

| module | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic` | 2722 | -3.3 / -0.1 / -0.1 | -3.3 / -0.1 / -0.1 | 895 |
| `sports` | 181 | -4.0 / -0.1 / -0.1 | -4.0 / -0.1 / 0.0 | 85 |
| `fiber_digestive` | 90 | -4.0 / -3.4 / -1.0 | -4.0 / -3.4 / -1.0 | 35 |

| archetype | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic_single_molecule` | 1589 | -3.3 / -0.1 / -0.1 | -3.3 / -0.1 / -0.1 | 575 |
| `generic_botanical_branded` | 1115 | -2.8 / -0.7 / -0.1 | -2.8 / -0.7 / -0.1 | 320 |
| `sports_single` | 154 | -4.0 / -0.1 / -0.1 | -4.0 / -0.1 / -0.1 | 74 |
| `fiber_digestive` | 90 | -4.0 / -3.4 / -1.0 | -4.0 / -3.4 / -1.0 | 35 |
| `sports_bcaa_eaa` | 20 | -2.5 / -2.5 / -0.1 | -2.5 / -0.5 / 0.0 | 6 |
| `immune_support` | 18 | -2.2 / -1.6 / -0.8 | -2.2 / -1.6 / -0.8 | 0 |
| `sports_protein` | 7 | -4.0 / -0.1 / -0.1 | -4.0 / -0.1 / -0.1 | 5 |

| single active? | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `True` | 2251 | -3.4 / -0.1 / -0.1 | -3.4 / -0.1 / -0.1 | 819 |
| `False` | 742 | -2.6 / -0.7 / -0.1 | -2.6 / -0.7 / 0.0 | 196 |

Inversions INTRODUCED by this policy (within archetype and direction):

```
[
 {
  "archetype": "sports_single",
  "direction": "positive_strong",
  "stronger_study_type": "systematic_review_meta",
  "stronger_median_evidence": 11.6,
  "weaker_study_type": "rct_multiple",
  "weaker_median_evidence": 16.3
 }
]
```

### `direction_ceiling`

Still an absolute minimum, but only a positive_strong primary may anchor on the STRONG floor base. Every weaker direction anchors on the MODERATE base the scorer already defines, weighted by the direction multiplier the scorer already owns. No new direction table.

- positive_weak changed: **1,137**, median Evidence after: **10.4**, p90 **11.6**, tier changes 281
- positive_strong changed: **0**, median Evidence after: **None**, p90 **None**, tier changes 0
- study-hierarchy inversions: **3** observed, 3 already present at baseline, **0 introduced by this policy**

| effect direction | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `positive_weak` | 1137 | -2.8 / -1.8 / -0.1 | -2.8 / -1.8 / -0.1 | 281 |
| `mixed` | 630 | -2.0 / -2.0 / -0.2 | -2.0 / -2.0 / -0.2 | 73 |

| study type | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `systematic_review_meta` | 1575 | -2.1 / -2.0 / -0.1 | -2.1 / -2.0 / -0.1 | 314 |
| `rct_multiple` | 192 | -2.0 / -1.2 / -1.0 | -2.0 / -1.2 / -1.0 | 40 |

| module | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic` | 1693 | -2.1 / -2.0 / -0.1 | -2.1 / -2.0 / -0.1 | 347 |
| `sports` | 69 | -2.0 / -2.0 / -2.0 | -2.0 / -2.0 / -0.8 | 7 |
| `fiber_digestive` | 5 | -2.4 / -2.0 / -2.0 | -2.4 / -2.0 / -2.0 | 0 |

| archetype | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic_single_molecule` | 1066 | -2.1 / -2.0 / -0.2 | -2.1 / -2.0 / -0.2 | 228 |
| `generic_botanical_branded` | 548 | -2.8 / -2.0 / -0.1 | -2.8 / -2.0 / -0.1 | 109 |
| `immune_support` | 79 | -2.2 / -1.2 / -0.2 | -2.2 / -1.2 / -0.2 | 10 |
| `sports_single` | 47 | -2.0 / -2.0 / -2.0 | -2.0 / -2.0 / -2.0 | 1 |
| `sports_bcaa_eaa` | 20 | -2.8 / -2.8 / -2.0 | -2.8 / -2.0 / -0.8 | 6 |
| `fiber_digestive` | 5 | -2.4 / -2.0 / -2.0 | -2.4 / -2.0 / -2.0 | 0 |
| `sports_protein` | 2 | -2.0 / -2.0 / -2.0 | -2.0 / -2.0 / -2.0 | 0 |

| single active? | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `True` | 1080 | -2.1 / -2.0 / -0.6 | -2.1 / -2.0 / -0.6 | 217 |
| `False` | 687 | -2.2 / -1.2 / -0.1 | -2.2 / -1.2 / -0.1 | 137 |

### `study_strength_scaled`

An absolute minimum scaled by the strength of the study behind it, using the scorer's OWN study-type hierarchy (STUDY_TYPE_BASE_POINTS) rather than a new invented ladder. A single RCT anchors proportionally less than a systematic review.

- positive_weak changed: **32**, median Evidence after: **11.1**, p90 **14.2**, tier changes 4
- positive_strong changed: **823**, median Evidence after: **13.0**, p90 **16.7**, tier changes 220
- study-hierarchy inversions: **3** observed, 3 already present at baseline, **0 introduced by this policy**

| effect direction | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `positive_strong` | 823 | -2.6 / -1.1 / -0.2 | -2.6 / -1.1 / -0.2 | 220 |
| `mixed` | 173 | -1.5 / -1.2 / -1.0 | -1.5 / -1.2 / -1.0 | 26 |
| `positive_weak` | 32 | -2.1 / -2.1 / -2.0 | -2.1 / -2.1 / -2.0 | 4 |

| study type | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `rct_multiple` | 687 | -2.6 / -1.5 / -0.2 | -2.6 / -1.5 / -0.2 | 162 |
| `rct_single` | 339 | -3.4 / -1.1 / -0.3 | -3.4 / -1.1 / -0.3 | 88 |
| `clinical_strain` | 2 | -4.1 / -4.1 / -4.1 | -4.1 / -4.1 / -4.1 | 0 |

| module | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic` | 974 | -2.6 / -1.1 / -0.3 | -2.6 / -1.1 / -0.3 | 237 |
| `fiber_digestive` | 39 | -4.1 / -3.3 / -2.6 | -4.1 / -3.3 / -2.6 | 9 |
| `sports` | 15 | -3.3 / -0.2 / -0.2 | -3.3 / -0.2 / -0.2 | 4 |

| archetype | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `generic_single_molecule` | 572 | -2.6 / -1.1 / -0.3 | -2.6 / -1.1 / -0.3 | 135 |
| `generic_botanical_branded` | 377 | -2.6 / -1.5 / -1.1 | -2.6 / -1.5 / -1.1 | 102 |
| `fiber_digestive` | 39 | -4.1 / -3.3 / -2.6 | -4.1 / -3.3 / -2.6 | 9 |
| `immune_support` | 25 | -1.2 / -1.2 / -1.2 | -1.2 / -1.2 / -1.2 | 0 |
| `sports_single` | 12 | -3.3 / -3.3 / -3.3 | -3.3 / -3.3 / -3.3 | 4 |
| `sports_bcaa_eaa` | 3 | -0.2 / -0.2 / -0.2 | -0.2 / -0.2 / -0.2 | 0 |

| single active? | products | Evidence delta med/p90/max | final-score delta med/p90/max | changes tier |
|---|---:|---|---|---:|
| `True` | 621 | -2.6 / -1.1 / -1.1 | -2.6 / -1.1 / -1.1 | 133 |
| `False` | 407 | -3.3 / -1.2 / -0.2 | -3.3 / -1.2 / -0.2 | 117 |

## Placeholder constants

```
{
 "uplift_caps": {
  "capped_uplift_3": 3.0,
  "capped_uplift_5": 5.0
 },
 "applied_in": "raw Evidence space, inside _primary_mass_floor, BEFORE the archetype rescale - the same space the 14.0/11.0/10.0 floor constants live in. A cap of the same magnitude applied on the public 0-20 scale would mean a different raw amount per archetype (18.0 vs 17.0 references), so it is NOT interchangeable.",
 "direction_ceiling": "derived, not tabulated - PRIMARY_FLOOR_MODERATE x EFFECT_DIRECTION_MULTIPLIERS[direction]",
 "study_strength_scale": "STUDY_TYPE_BASE_POINTS[st] / STUDY_TYPE_BASE_POINTS[systematic_review_meta]"
}
```

Pick the mechanism first. These numbers exist to show what each mechanism does, not to be adopted.

