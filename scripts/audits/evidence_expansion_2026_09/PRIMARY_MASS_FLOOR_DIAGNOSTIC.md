# PRIMARY-MASS FLOOR — PRODUCTION ROUTES ONLY

Measured, not changed. No scoring constant moved: not the 14.0/11.0 floors, not the 0.85 direction weight, not the archetype references, not the 20-point scale.

> # ⛔ INVALID FOR CALIBRATION
>
> **Do not quote any decisive count, Evidence delta, final-score delta or tier-change number from this report.** The counterfactual disabled BOTH the primary-mass floor and the DRI/nutrition-authority floor, so every delta credits the primary-mass rule with points the authority floor would have supplied.
>
> Product 261812 (Airborne): reported here as Evidence 14.0 -> 8.7 without the floor, delta 5.3. With the authority floor left live the correct counterfactual is 14.0 -> 11.8, delta 2.2.
>
> Population and eligibility counts remain valid - they do not depend on the counterfactual. Everything downstream of them does not.
>
> **Use instead:** `primary_mass_floor_calibration.json` and its report `PRIMARY_MASS_FLOOR_CALIBRATION.md`.

Four states, reported separately because the word *material* was ambiguous enough to hide the difference between the last three. They nest.

```
Products scored:                         15,109
Eligible for primary-mass floor:         11,786
Actually receiving nonzero floor:         5,485
Decisive for public Evidence:             5,029
Changes final 0-100 score:                5,027
Changes published tier:                   3,063

Separate rule, same component key:
DRI/nutrition-authority floor:              672
```

The decisive population is **33.28%** of the scored catalog; the tier-changing population is **20.27%**.

- Evidence delta (median / p90 / max): **7.8 / 11.3 / 16.2** of 20
- Final-score delta (median / p90 / max): **7.8 / 11.3 / 16.2** of 100
- Tier crossings: **3063 upward, 0 downward**

| tier crossing | products |
|---|---:|
| Needs improvement -> Good | 1589 |
| Good -> Very good | 995 |
| Poor -> Needs improvement | 194 |
| Needs improvement -> Very good | 97 |
| Good -> Excellent | 75 |
| Very good -> Excellent | 64 |
| Very good -> Exceptional | 38 |
| Excellent -> Exceptional | 9 |
| Poor -> Good | 2 |

## The decisive population

| effect direction | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `positive_strong` | 3225 | 8.4 / 13.4 / 16.2 | 8.4 / 13.4 / 16.2 | 2155 |
| `positive_weak` | 1110 | 7.1 / 9.1 / 13.6 | 7.1 / 9.1 / 13.6 | 638 |
| `mixed` | 654 | 5.7 / 6.4 / 9.3 | 5.7 / 6.4 / 9.3 | 245 |
| `None` | 40 | 8.1 / 9.3 / 9.3 | 8.1 / 9.3 / 9.3 | 25 |

| study type | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `systematic_review_meta` | 3868 | 7.7 / 10.8 / 14.0 | 7.7 / 10.8 / 14.0 | 2310 |
| `rct_multiple` | 780 | 8.6 / 11.6 / 16.0 | 8.6 / 11.6 / 16.0 | 563 |
| `rct_single` | 339 | 7.4 / 9.8 / 16.2 | 7.4 / 9.8 / 16.2 | 165 |
| `None` | 40 | 8.1 / 9.3 / 9.3 | 8.1 / 9.3 / 9.3 | 25 |
| `clinical_strain` | 2 | 9.3 / 9.3 / 9.3 | 9.3 / 9.3 / 9.3 | 0 |

| module | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `generic` | 4704 | 7.6 / 11.2 / 16.2 | 7.6 / 11.2 / 16.2 | 2859 |
| `sports` | 220 | 8.6 / 14.0 / 15.0 | 8.6 / 14.0 / 15.0 | 138 |
| `fiber_digestive` | 105 | 9.6 / 14.0 / 16.0 | 9.6 / 14.0 / 16.0 | 66 |

| archetype | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `generic_single_molecule` | 3241 | 7.5 / 11.6 / 16.0 | 7.5 / 11.6 / 16.0 | 2056 |
| `generic_botanical_branded` | 1380 | 7.8 / 10.8 / 16.2 | 7.8 / 10.8 / 16.2 | 784 |
| `sports_single` | 168 | 9.6 / 14.0 / 15.0 | 9.6 / 14.0 / 15.0 | 119 |
| `fiber_digestive` | 105 | 9.6 / 14.0 / 16.0 | 9.6 / 14.0 / 16.0 | 66 |
| `immune_support` | 83 | 3.4 / 8.1 / 8.8 | 3.4 / 8.1 / 8.8 | 19 |
| `sports_bcaa_eaa` | 32 | 8.1 / 8.1 / 8.6 | 8.1 / 8.1 / 8.6 | 10 |
| `sports_protein` | 11 | 5.7 / 9.6 / 9.6 | 5.7 / 9.6 / 9.6 | 8 |
| `sports_pre_workout` | 9 | 1.8 / 2.8 / 4.0 | 1.8 / 2.8 / 4.0 | 1 |

| single active? | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `True` | 3019 | 8.4 / 13.4 / 16.2 | 8.4 / 13.4 / 16.2 | 2191 |
| `False` | 2010 | 5.3 / 9.5 / 16.2 | 5.3 / 9.5 / 16.2 | 872 |

| raw floor | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `14.0` | 2231 | 8.4 / 10.8 / 11.6 | 8.4 / 10.8 / 11.6 | 1428 |
| `11.9` | 1117 | 7.1 / 9.1 / 10.7 | 7.1 / 9.1 / 10.7 | 637 |
| `18.0` | 690 | 13.4 / 14.0 / 16.0 | 13.4 / 14.0 / 16.0 | 587 |
| `8.4` | 625 | 5.7 / 6.4 / 6.9 | 5.7 / 6.4 / 6.9 | 228 |
| `11.0` | 295 | 7.4 / 9.0 / 9.8 | 7.4 / 9.0 / 9.8 | 127 |
| `17.0` | 33 | 14.9 / 16.2 / 16.2 | 14.9 / 16.2 / 16.2 | 31 |
| `15.3` | 20 | 10.9 / 13.2 / 13.6 | 10.9 / 13.2 / 13.6 | 14 |
| `6.6` | 11 | 5.4 / 5.4 / 5.4 | 5.4 / 5.4 / 5.4 | 7 |
| `10.8` | 5 | 9.3 / 9.3 / 9.3 | 9.3 / 9.3 / 9.3 | 4 |
| `9.35` | 2 | 6.7 / 6.7 / 6.7 | 6.7 / 6.7 / 6.7 | 0 |

| archetype reference max | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `18.0` | 4946 | 7.8 / 11.6 / 16.2 | 7.8 / 11.6 / 16.2 | 3044 |
| `17.0` | 83 | 3.4 / 8.1 / 8.8 | 3.4 / 8.1 / 8.8 | 19 |

## `positive_weak` + primary-mass-floor decisive

The population amla and white kidney bean exposed. The question was whether `13.2/20` is a rare edge or a systematic characteristic.

- products: **1110** (22.1% of all decisive)
- public Evidence after rescale — median **13.2**, p90 **13.2**
- at or above 13.0/20: **1108**
- Evidence delta (median / p90 / max): 7.1 / 9.1 / 13.6
- final-score delta (median / p90 / max): 7.1 / 9.1 / 13.6
- changes published tier: **638**

| study type | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `systematic_review_meta` | 1078 | 7.1 / 9.1 / 10.9 | 7.1 / 9.1 / 10.9 | 613 |
| `rct_multiple` | 30 | 9.8 / 13.2 / 13.6 | 9.8 / 13.2 / 13.6 | 25 |
| `rct_single` | 2 | 6.7 / 6.7 / 6.7 | 6.7 / 6.7 / 6.7 | 0 |

| raw floor | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `11.9` | 1088 | 7.1 / 9.1 / 10.7 | 7.1 / 9.1 / 10.7 | 624 |
| `15.3` | 20 | 10.9 / 13.2 / 13.6 | 10.9 / 13.2 / 13.6 | 14 |
| `9.35` | 2 | 6.7 / 6.7 / 6.7 | 6.7 / 6.7 / 6.7 | 0 |

| archetype | products | Evidence delta med / p90 / max | final-score delta med / p90 / max | changes tier |
|---|---:|---|---|---:|
| `generic_single_molecule` | 724 | 7.1 / 9.1 / 13.6 | 7.1 / 9.1 / 13.6 | 438 |
| `generic_botanical_branded` | 324 | 7.1 / 9.1 / 10.7 | 7.1 / 9.1 / 10.7 | 183 |
| `immune_support` | 56 | 5.3 / 8.1 / 8.1 | 5.3 / 8.1 / 8.1 | 16 |
| `sports_bcaa_eaa` | 3 | 3.0 / 3.0 / 3.0 | 3.0 / 3.0 / 3.0 | 0 |
| `fiber_digestive` | 3 | 5.0 / 6.9 / 6.9 | 5.0 / 6.9 / 6.9 | 1 |

## Data-quality note

40 decisive products have a floor anchor whose canonical name does not resolve to a registry record, so their direction and study type are unknown here. They are counted, not guessed at.

## Architecture debt logged, not fixed here

`primary_evidence_floor` is one component key for two semantically different mechanisms: the primary-mass floor and the DRI-essential nutrition-authority floor. That shared key is what let the first run of this diagnostic conflate them. The arithmetic can stay identical; the keys should eventually differ so a reader cannot mistake one rule for the other.

