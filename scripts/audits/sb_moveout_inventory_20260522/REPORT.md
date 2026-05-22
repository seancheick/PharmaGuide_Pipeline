# SB Move-Out Inventory — 2026-05-22 (post-SB-chain)

## Context

Fresh re-audit of `standardized_botanicals.json` after the SB-1..SB-13 chain landed on `origin/main` (commit `ea8adf34`). The original 2026-05-22 audit ran against 201 entries and flagged 107 as `NO marker` move-out candidates. After SB-3..SB-13 cleaned up 14 §8.5 contamination cases plus added v6 contracts (boswellia, bilberry, ginger, nettle, rhodiola, grape_seed, cordyceps, turkey_tail, sea_buckthorn, turmeric, curcumin, plus 4 brown-algae species splits), the move-out queue is now **89 entries**.

Current state: **241 entries** in standardized_botanicals.json.

## Headline

| Bucket | Count | Action |
|---|---|---|
| **v6-annotated (DONE)** | 15 | None — these are the tutorial entries (SB-2..SB-13) |
| **Has marker signal, no v6 yet** | 137 | PROMOTE_V6 in future batches (similar to SB-5..SB-13 cadence) |
| **NO marker signal** | **89** | move-out / merge / promote-branded |
|   → MOVE_TO_BOTANICAL_INGREDIENTS (plain identity) | **52** | bring identity to bot, no bonus |
|   → DELETE_OR_MERGE (id already in bot) | **14** | alias-diff + drop std entry |
|   → PROMOTE_V6_BRANDED (commercial brand) | **23** | reviewer-signed v6 contract |

## Group A: MOVE_TO_BOTANICAL_INGREDIENTS

**52 entries** — plain identity, no documented standardization marker. Each move: copy aliases + UNII + cui to a new bot entry, delete std entry, bump metadata. Recommended batch size: 5-8 per batch.

| id | UNII | aliases | category | bot alias collisions |
|---|---|---|---|---|
| `african_mango` | `—` (—) | 3 | herb | ⚠ 1 |
| `akarkara` | `—` (—) | 5 | herb | ⚠ 1 |
| `alfalfa` | `HY3L927V6M` (ALFALFA LEAF) | 4 | herb | ⚠ 2 |
| `american_ginseng` | `8W75VCV53Q` (AMERICAN GINSENG) | 4 | adaptogen | no |
| `astaxanthin` | `8XPW32PR7I` (ASTAXANTHIN) | 3 | herb | no |
| `astaxanthin_haematococcus_pluvialis` | `31T0FF0472` (HAEMATOCOCCUS PLUVIALIS) | 7 | herb | no |
| `astazine` | `—` (—) | 2 | herb | no |
| `baobab` | `—` (—) | 3 | herb | no |
| `barley_grass` | `86507VZR9K` (HORDEUM VULGARE TOP) | 3 | herb | ⚠ 1 |
| `bee_pollen` | `3729L8MA2C` (BEE POLLEN) | 4 | herb | no |
| `black_cohosh` | `K73E24S6X9` (BLACK COHOSH) | 4 | herb | no |
| `black_musli` | `715B59598O` (CURCULIGO ORCHIOIDES WHOLE) | 5 | herb | no |
| `black_sesame` | `—` (—) | 4 | herb | no |
| `blackberry` | `8A6OMU3I8L` (BLACKBERRY) | 5 | seed_fruit | no |
| `blue_green_algae` | `49VG1X560X` (APHANIZOMENON FLOSAQUAE) | 4 | algae | no |
| `camu_camu` | `—` (—) | 15 | herb | no |
| `caraway` | `W2FH8O2BBE` (CARAWAY SEED) | 4 | seed_fruit | no |
| `century_plant` | `024852X0VD` (AGAVE AMERICANA WHOLE) | 4 | herb | no |
| `cinnamon` | `5S29HWU6QB` (CINNAMON) | 4 | herb | ⚠ 2 |
| `cistanche` | `—` (—) | 5 | adaptogen | no |
| `d_mannose` | `PHA4727WTP` (MANNOSE) | 2 | active_compound | no |
| `damiana` | `812R0W1I3K` (TURNERA DIFFUSA LEAF) | 4 | herb | no |
| `elder_flower` | `07V4DX094T` (SAMBUCUS NIGRA FLOWER) | 2 | herb | no |
| `flaxseed` | `—` (—) | 4 | seed_fruit | no |
| `galdieria` | `2E5CL9KYZ8` (GALDIERIA SULPHURARIA) | 3 | algae | no |
| `garlic` | `V1V998DC17` (GARLIC) | 7 | herb | ⚠ 2 |
| `grapefruit_seed` | `598D944HOL` (CITRUS PARADISI (GRAPEFRUIT) SEE) | 4 | seed_fruit | no |
| `horsetail` | `—` (—) | 3 | herb | ⚠ 2 |
| `huperzine_a` | `0111871I23` (HUPERZINE A) | 2 | herb | no |
| `inulin` | `JOS53KRJ01` (INULIN) | 3 | herb | no |
| `kelp` | `168S4EO8YJ` (ASCOPHYLLUM NODOSUM) | 3 | herb | ⚠ 2 |
| `l_theanine` | `8021PR16QO` (THEANINE) | 3 | herb | no |
| `linden_flower` | `CFN6G1F6YK` (TILIA CORDATA FLOWER) | 3 | herb | ⚠ 1 |
| `lion_s_mane` | `—` (—) | 8 | mushroom | ⚠ 2 |
| `mallow` | `—` (—) | 3 | herb | no |
| `muira_puama` | `—` (—) | 4 | herb | ⚠ 3 |
| `mulungu` | `NU815YHH1S` (ERYTHRINA STRICTA WHOLE) | 4 | herb | no |
| `onion` | `492225Q21H` (ONION) | 3 | herb | no |
| `oregano` | `0E5AT8T16U` (ORIGANUM VULGARE LEAF) | 5 | herb | ⚠ 1 |
| `phosphatidylserine` | `394XK0IH40` (PHOSPHATIDYLSERINE) | 4 | active_compound | no |
| `pine_bark_extract` | `50JZ5Z98QY` (MARITIME PINE) | 4 | bark | no |
| `polygala` | `—` (—) | 4 | herb | no |
| `psyllium` | `0SHO53407G` (PSYLLIUM HUSK) | 3 | herb | ⚠ 2 |
| `pycnogenol` | `50JZ5Z98QY` (MARITIME PINE) | 3 | herb | no |
| `rosehip` | `—` (—) | 3 | herb | ⚠ 1 |
| `saffron` | `E849G4X5YJ` (SAFFRON) | 7 | herb | no |
| `shilajit` | `—` (—) | 7 | adaptogen | no |
| `slippery_elm` | `63POE2M46Y` (ELM) | 4 | herb | no |
| `soy_isoflavones` | `71B37NR06D` (SOY ISOFLAVONES) | 3 | herb | ⚠ 1 |
| `spinach` | `6WO75C6WVB` (SPINACH) | 4 | vegetable_greens | no |
| `wheatgrass` | `3C3Y389JBU` (TRITICUM AESTIVUM WHOLE) | 4 | herb | ⚠ 1 |
| `yellow_dock` | `S9T422Q956` (RUMEX CRISPUS TOP) | 4 | herb | ⚠ 2 |

## Group B: DELETE_OR_MERGE

**14 entries** — same id already exists in botanical_ingredients. Alias-diff + drop std entry. Each takes 1-2 minutes of reviewer time. Recommended batch size: 3-5 per batch.

| id | std UNII | bot UNII | std aliases | bot aliases | only-in-std |
|---|---|---|---|---|---|
| `aloe_vera` | `ZY81Z83H0X` | `ZY81Z83H0X` | 4 | 16 | 1 (['aloe vera extract']) |
| `carrot` | `L56Z1JK48B` | `L56Z1JK48B` | 4 | 3 | 2 (['carrot extract', 'carrot powder']) |
| `catuaba` | `—` | `—` | 4 | 5 | 0 ([]) |
| `chamomile` | `FGL3685T2X` | `FGL3685T2X` | 6 | 6 | 4 (['chamomile extract', 'german chamomile extract', 'matricaria recutita']) |
| `cranberry` | `0MVO31Q3QS` | `0MVO31Q3QS` | 6 | 10 | 5 (['american cranberry', 'cranberry extract', 'cranberry fruit extract']) |
| `cucumber` | `YY7C30VXJT` | `YY7C30VXJT` | 3 | 3 | 2 (['cucumber extract', 'cucumber seed extract']) |
| `fennel` | `557II4LLC3` | `557II4LLC3` | 4 | 6 | 2 (['fennel extract', 'sweet fennel']) |
| `graviola` | `AN924793RM` | `5EI0SM9VVE` | 3 | 6 | 1 (['soursop extract']) |
| `kale` | `0Y3L4J38H1` | `0Y3L4J38H1` | 4 | 5 | 1 (['curly kale']) |
| `lavender` | `ZBP1YXW0H8` | `ZBP1YXW0H8` | 5 | 13 | 0 ([]) |
| `marshmallow_root` | `TRW2FUF47H` | `TRW2FUF47H` | 4 | 10 | 3 (['althaea', 'marsh mallow', 'marshmallow root extract']) |
| `mullein` | `C9TD27U172` | `C9TD27U172` | 5 | 5 | 3 (['mullein extract', 'mullein leaf extract', 'standardized mullein']) |
| `sarsaparilla` | `2H1576D5WG` | `2H1576D5WG` | 5 | 7 | 3 (['sarsaparilla extract', 'smilax extract', 'smilax officinalis']) |
| `yucca` | `08A0YG3VIC` | `08A0YG3VIC` | 4 | 5 | 2 (['mojave yucca', 'yucca root']) |

## Group C: PROMOTE_V6_BRANDED

**23 entries** — branded commercial extracts. Each needs reviewer-signed v6 contract (standardization_basis=branded_extract, marker_compounds, sources, UNII). Cadence: 1 entry per batch, identical to SB-5..SB-13 v6 annotation pattern.

| id | UNII | aliases | category | likely brand owner |
|---|---|---|---|---|
| `bil_max` | `—` | 1 | standardized | Sabinsa (bilberry) |
| `blue_max` | `—` | 1 | standardized | Sabinsa (blueberry) |
| `chromax` | `—` | 2 | mineral_chelate | Nutrition 21 (chromium picolinate) |
| `cognigrape` | `RDS2V6DVY5` | 6 | seed_fruit | Bionap (anthocyanin grape) |
| `cran_max` | `—` | 1 | fruit | PharmaChem (whole-fruit cranberry) |
| `eps_7630` | `—` | 1 | herb | Schwabe (Pelargonium sidoides) |
| `floraglo` | `X72A60C9MT` | 1 | herb | Kemin (lutein) |
| `flowens` | `—` | 2 | standardized | Frutarom (cranberry PAC) |
| `fruitex_b_calcium_fructoborate` | `—` | 1 | mineral_complex | FutureCeuticals (calcium fructoborate) |
| `ksm_66_ashwagandha` | `—` | 3 | herb | Ixoreal Biomed (KSM-66) |
| `life_s_dha` | `—` | 2 | algal_oil | DSM (algal DHA) |
| `lutemax_2020` | `—` | 3 | herb | OmniActive (lutein+zeaxanthin) |
| `microactive_melatonin` | `—` | 1 | hormone_analog | BioActives LLC (sustained-release melatonin) |
| `neurofactor` | `—` | 4 | fruit | Futureceuticals (coffee fruit BDNF) |
| `optiberry` | `—` | 3 | berry | InterHealth (berry blend) |
| `organic_gold_standard_potentiating_nutrients` | `—` | 1 | blend | Unclear — needs reviewer triage |
| `pacran` | `—` | 2 | fruit | Naturex (cranberry PAC) |
| `sharp_ps_green` | `—` | 1 | standardized | Lipogen (phosphatidylserine) |
| `slendesta` | `—` | 4 | tuber | Kemin (potato extract satiety) |
| `sunactive_iron` | `—` | 1 | mineral | Taiyo (iron complex) |
| `thermosil` | `—` | 1 | mineral | Unclear — needs reviewer triage |
| `turmipure_gold` | `—` | 1 | herb | Naturex (curcumin) |
| `uniflex` | `—` | 1 | structural_protein | Unclear — needs reviewer triage |

## Recommended next batches

### MO-batches (move-out — lowest per-entry risk)

Group by category for narrative coherence.

| Category | Count | Sample ids |
|---|---|---|
| `herb` | 38 | african_mango, akarkara, alfalfa, astaxanthin, astaxanthin_haematococcus_pluvialis... |
| `seed_fruit` | 4 | blackberry, caraway, flaxseed, grapefruit_seed |
| `adaptogen` | 3 | american_ginseng, cistanche, shilajit |
| `algae` | 2 | blue_green_algae, galdieria |
| `active_compound` | 2 | d_mannose, phosphatidylserine |
| `mushroom` | 1 | lion_s_mane |
| `bark` | 1 | pine_bark_extract |
| `vegetable_greens` | 1 | spinach |

### DM-batches (delete-or-merge)

All 14 are alias-diff exercises. Suggested 2 batches of 7.

### PB-batches (promote-v6-branded)

One entry per batch, ordered by commercial visibility. Recommended order:

1. `pacran` (Naturex cranberry PAC — high visibility)
2. `cran_max` (PharmaChem whole-fruit cranberry)
3. `lutemax_2020` (OmniActive lutein+zeaxanthin)
4. `ksm_66_ashwagandha` (Ixoreal KSM-66)
5. `cognigrape` (Bionap — already has UNII RDS2V6DVY5)
6. `floraglo` (Kemin lutein)
7. `optiberry` (InterHealth berry blend)
8. `eps_7630` (Schwabe pelargonium)
9. `turmipure_gold` (Naturex curcumin)
10. `flowens` (Frutarom cranberry PAC)
11. `sharp_ps_green` (Lipogen PS)
12. `slendesta` (Kemin satiety)
13. `neurofactor` (Futureceuticals — already in coffee_fruit via RC-1!)
14. `chromax` (chromium picolinate — mineral, may not deserve v6)
15. `bil_max`, `blue_max` (Sabinsa — check for SB-5 bilberry overlap)
16. `fruitex_b_calcium_fructoborate`, `life_s_dha`, `microactive_melatonin`, `sunactive_iron`, `thermosil`, `uniflex`, `organic_gold_standard_potentiating_nutrients` (NEEDS REVIEW — may not fit branded_extract; some are minerals or oils)

## Score-impact assessment (recommended before each MO batch)

Per the SB-2 shadow-score discipline:
1. Run the enricher on the affected brands
2. Diff `has_standardized_botanical=True` count before/after
3. If a product loses a previously-valid bonus, abort and reclassify
4. If 0 products lose: proceed

The `meets_threshold` gate (`score_supplements.py:1148`) should already prevent inflation for plain mentions, so most moves should be score-neutral.

## Files

- `REPORT.md` — this file
- `inventory.json` — structured per-entry data for tooling
- `/Users/seancheick/Downloads/dsld_clean_audit/scripts/data/fda_unii_cache.json` — UNII source-of-truth used in audit
