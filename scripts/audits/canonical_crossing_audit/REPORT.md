# Canonical Crossing Audit — Form Resolver Cross-Parent Jumps

> Generated: 2026-05-11 | Pipeline: enrich_supplements_v3.py v3.1.0

## Scope

For every active ingredient in the scored DSLD corpus, compare the `canonical_id` set by
the cleaner stage (top-level `activeIngredients[].canonical_id`) against the `canonical_id`
set by the form-resolver in `ingredient_quality_data.ingredients[]`. When they disagree,
the form resolver overrode the cleaner — a *canonical crossing*.

## Headline

- **Total scored ingredient rows:** 117,808
- **Canonical crossings:** 3,487
- **Crossing rate:** 2.96%
- **Distinct crossing patterns:** 212

## Root Cause

File: `scripts/enrich_supplements_v3.py:5862-5870`

```python
if cleaner_iqm_canonical and candidates:
    constrained = [c for c in candidates if c["parent_key"] == cleaner_iqm_canonical]
    if constrained:                       # ← only filters when constrained is non-empty
        candidates = constrained
    # ↑ If constrained is empty, candidates stays as the FULL unconstrained list.
    #   Cross-parent matches survive and win the tie-break.
```

The Phase 3 medical-accuracy fix (per docstring) intended to *hard-constrain* candidates to the
cleaner's resolved IQM parent. The constraint correctly drops off-canonical candidates when at
least one on-canonical candidate exists. But when **no on-canonical candidate exists** (the
label's form text matches an alias only under a different parent), the `if constrained:` guard
silently skips the filter and the off-canonical match wins.

The parent-level fallback at lines 5876–5895 was designed for exactly this case but never fires
because the trigger is `if not candidates:` (original list empty) rather than `if not constrained:`.

## Verdict Categories

| Code | Meaning |
|------|---------|
| **BUG** | Cross-parent jump is medically wrong. Form resolver picked a source descriptor or unrelated compound. Fix required. |
| **SEMANTIC** | Cross-parent jump matches reality but loses the headline-nutrient context. User bought the product for what the label says. Fix recommended. |
| **KEEP** | Cross-parent jump is more accurate than the cleaner's broader canonical. Source plant → active compound. Do not regress. |
| **REVIEW** | Clinical/regulatory implications. Requires named clinician sign-off. |

## Clinical Review Addendum — 2026-05-11

Dr Pham policy confirmation supersedes the draft `KEEP` interpretation for
source-to-marker, NAD-family, probiotic, and risk-canonical crossings:

- **Primary identity is authoritative.** The cleaner/label canonical must not be
  silently replaced by a related marker, source, strain, precursor, or normal
  ingredient identity.
- **Botanical active markers are secondary evidence.** Tomato/lycopene,
  broccoli/sulforaphane, green tea/catechins/caffeine, and coffee fruit/caffeine
  should remain at the declared botanical canonical unless the label explicitly
  declares or standardizes the active marker.
- **NAD/B3 family members stay distinct.** NR, NMN, NADH, niacinamide, and
  inositol hexanicotinate may carry B3/NAD relationship metadata, but must not
  collapse to generic `vitamin_b3_niacin` unless the label explicitly presents
  the row as niacin/B3.
- **Probiotic evidence is strain-specific.** Generic `probiotics` rows must not
  inherit a strain canonical or strain-level evidence unless the strain appears
  on the label.
- **Risk canonicals are immutable.** `RISK_*` and `BANNED_*` identities must not
  be downgraded to normal IQM canonicals. Normal ingredient IDs may be linked as
  secondary metadata, but safety gating remains primary.

Implementation status: the Phase 3 hard-stop now falls back to the cleaner's
IQM parent when every form candidate is off-parent. The allowlist is restricted
to reviewed identity refinements only; `turmeric -> curcumin` requires explicit
`curcuminoids` or `95%` form text.

## All Crossing Patterns

| Top (cleaner) | Resolved (form) | Hits | Avg bio | Verdict | Rationale |
|---|---|---:|---:|:---:|---|
| `vitamin_k` | `vitamin_k1` | 691 | 9.0 | **KEEP** | Generic "Vitamin K" defaulting to K1 (phylloquinone) is the standard regulatory assumption. |
| `tomato` | `lycopene` | 371 | 9.0 | **KEEP** | Tomato extract products deliver lycopene as the active. Lycopene canonical has the RCT evidence. |
| `calcium` | `vitamin_c` | 230 | 11.7 | **SEMANTIC** | Ca ascorbate label headed by Calcium — user bought it for Ca primarily. |
| `ginger_extract` | `ginger` | 142 | 9.6 | **KEEP** | Same root canonical; resolver dropped the "_extract" suffix. No score loss. |
| `curcumin` | `turmeric` | 119 | 6.0 | **SEMANTIC** | High-absorption Curcumin products are 95% curcuminoids — should be curcumin, not generic turmeric. |
| `phosphorus` | `calcium` | 115 | 6.1 | **BUG** | DCP-sourced Phosphorus row — exact pattern called out as fixed in code docstring, still happening. |
| `broccoli` | `sulforaphane` | 105 | 10.0 | **KEEP** | Broccoli sprout extracts are dosed for sulforaphane content. |
| `inositol` | `vitamin_b3_niacin` | 81 | 12.0 | **KEEP** | Inositol hexanicotinate is genuinely a niacin form (delivers niacin systemically). |
| `nicotinamide_riboside` | `vitamin_b3_niacin` | 63 | 11.7 | **KEEP** | NR is a niacin family member. |
| `dha` | `fish_oil` | 58 | 9.0 | **BUG** | Fish oil is the source; DHA is the molecule. Losing DHA-specificity costs evidence depth. |
| `guarana` | `caffeine` | 55 | 13.0 | **KEEP** | Guarana products are typically standardized for caffeine content. |
| `digestive_enzymes` | `papaya` | 43 | 6.0 | **REVIEW** | Papain (enzyme) routed to papaya fruit. Depends on label. |
| `NHA_COLLAGEN_HYDROLYZED` | `collagen` | 32 | 11.0 | **KEEP** | Branded → generic for the same molecule. |
| `creatine_monohydrate` | `fish_oil` | 32 | 8.6 | **BUG** | Cross-domain — likely form-alias collision (no biological relationship). |
| `magnesium` | `vitamin_c` | 32 | 11.8 | **BUG** | Mg ascorbate label headed by Magnesium — user bought it for Mg, not C. |
| `l_leucine` | `casein` | 31 | 11.9 | **BUG** | Leucine label routed to casein because leucine is a casein-derived amino acid. |
| `vitamin_e` | `sunflower_oil` | 31 | 5.0 | **BUG** | Sunflower oil is the SOURCE, not the form. Vit E α-tocopherol is the nutrient. |
| `phosphorus` | `potassium` | 30 | 10.0 | **BUG** | Same family — K-phosphate row tracked as K, not P. |
| `turmeric` | `curcumin` | 27 | 7.9 | **KEEP** | When label is generic turmeric BUT form is curcumin extract 95%, curcumin canonical is more accurate. |
| `RISK_YOHIMBE` | `yohimbe` | 26 | 5.0 | **REVIEW** | Risk canonical routed to safe canonical — needs safety/regulatory review. |
| `BANNED_7_KETO_DHEA` | `7_keto_dhea` | 25 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `green_tea` | `green_tea_extract` | 24 | 9.3 | **UNCATEGORIZED** | _(needs review)_ |
| `elderberries` | `elderberry` | 23 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_arginine` | `whey_protein` | 23 | 11.6 | **UNCATEGORIZED** | _(needs review)_ |
| `l_glutamine` | `whey_protein` | 23 | 11.7 | **UNCATEGORIZED** | _(needs review)_ |
| `ksm_66_ashwagandha` | `ashwagandha` | 23 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `curcumin` | `lecithin` | 22 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_isoleucine` | `casein` | 20 | 11.1 | **UNCATEGORIZED** | _(needs review)_ |
| `l_valine` | `casein` | 20 | 11.1 | **UNCATEGORIZED** | _(needs review)_ |
| `dha` | `algae_oil` | 20 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `dandelion_root` | `dandelion` | 18 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `RISK_GARCINIA_CAMBOGIA` | `garcinia_cambogia` | 18 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_ACACIA_GUM` | `prebiotics` | 18 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_aspartic_acid` | `d_aspartic_acid` | 18 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `kelp_powder` | `brown_kelp` | 18 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `potassium` | `vitamin_c` | 18 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `green_tea_extract` | `lecithin` | 18 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_isoleucine` | `whey_protein` | 17 | 11.4 | **UNCATEGORIZED** | _(needs review)_ |
| `blueberry_fruit` | `blueberry` | 17 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `cabbage` | `cabbage_extract` | 17 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `manganese` | `magnesium` | 17 | 14.0 | **UNCATEGORIZED** | _(needs review)_ |
| `reishi_mushroom` | `reishi` | 16 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `OI_ADRENAL_CORTEX` | `organ_extracts` | 16 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `papaya_fruit_powder` | `papaya` | 15 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `iodine` | `brown_kelp` | 15 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `lemon` | `vitamin_b9_folate` | 15 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `olive_fruit_extract` | `olive_leaf` | 15 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `american_ginseng` | `ginseng` | 14 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `probiotics` | `lactobacillus_acidophilus` | 13 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `picrorhiza_root` | `picrorhiza` | 13 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `calcium` | `vitamin_b5_pantothenic` | 12 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `coffee_fruit` | `caffeine` | 12 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `passionflower` | `hawthorn` | 12 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `nattokinase` | `soybean` | 12 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `hesperidin` | `citrus_bioflavonoids` | 11 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `choline` | `lecithin` | 11 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_tyrosine` | `whey_protein` | 11 | 11.7 | **UNCATEGORIZED** | _(needs review)_ |
| `alpha_gpc` | `choline` | 10 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_arginine` | `casein` | 10 | 10.6 | **UNCATEGORIZED** | _(needs review)_ |
| `shiitake_mushroom` | `shiitake` | 10 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `astaxanthin` | `cla` | 10 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `milk_thistle` | `lecithin` | 10 | 7.5 | **UNCATEGORIZED** | _(needs review)_ |
| `nmn` | `vitamin_b3_niacin` | 9 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `green_tea_extract` | `caffeine` | 9 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `gamma_linolenic_acid` | `cla` | 9 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `himematsutake` | `royal_sun_blazei` | 9 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `ADD_XYLITOL` | `xylitol` | 9 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `gamma_linolenic_acid` | `borage_seed_oil` | 9 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_glutamine` | `casein` | 8 | 9.7 | **UNCATEGORIZED** | _(needs review)_ |
| `methionine` | `whey_protein` | 8 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_CHICORY_ROOT_FIBER` | `inulin` | 8 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `yerba_mate_leaf` | `yerba_mate` | 8 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `curcumin` | `choline` | 8 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `alpha_linolenic_acid` | `flaxseed` | 7 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `potassium` | `iodine` | 7 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `phosphatidylserine` | `lecithin` | 7 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_tyrosine` | `casein` | 7 | 10.1 | **UNCATEGORIZED** | _(needs review)_ |
| `grape` | `grape_seed_extract` | 7 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_valine` | `whey_protein` | 7 | 10.4 | **UNCATEGORIZED** | _(needs review)_ |
| `moringa` | `vitamin_a` | 7 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `grape_seed_extract` | `lecithin` | 7 | 7.5 | **UNCATEGORIZED** | _(needs review)_ |
| `grape_seed_extract` | `red_wine_extract` | 7 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `strontium` | `citric_acid` | 6 | 4.0 | **UNCATEGORIZED** | _(needs review)_ |
| `epa` | `fish_oil` | 6 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_glutamic_acid` | `casein` | 6 | 10.7 | **UNCATEGORIZED** | _(needs review)_ |
| `tart_cherry_fruit` | `tart_cherry` | 6 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `ADD_SILICON_DIOXIDE` | `silica` | 6 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `alfalfa_leaf` | `alfalfa` | 6 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_CHERRY_FLAVOR` | `tart_cherry` | 6 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `devils_claw_tuber` | `devils_claw` | 6 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `whey_protein` | `lecithin` | 6 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `potassium` | `glucosamine` | 5 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `isoflavones` | `soybean` | 5 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `vitamin_a` | `fish_oil` | 5 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_leucine` | `collagen` | 5 | 12.4 | **UNCATEGORIZED** | _(needs review)_ |
| `l_leucine` | `whey_protein` | 5 | 10.6 | **UNCATEGORIZED** | _(needs review)_ |
| `wood_ear_mushroom` | `auricularia` | 5 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `fruits` | `apple_polyphenols` | 5 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `flavonoids` | `flavonols` | 5 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `bismuth` | `citric_acid` | 5 | 4.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_CHAMOMILE_EXTRACT` | `chamomile` | 5 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_LEMON_BALM_EXTRACT` | `lemon_balm` | 5 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `zinc` | `vitamin_c` | 4 | 13.6 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_YEAST_FERMENTATE_DRIED` | `yeast_fermentate` | 4 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `branched_chain_amino_acids` | `l_isoleucine` | 4 | 13.3 | **UNCATEGORIZED** | _(needs review)_ |
| `magnesium` | `tmg_betaine` | 4 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `tamarind_extract` | `turmeric` | 4 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `piperine` | `capsaicin` | 4 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `prickly_pear` | `nopal` | 4 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `colostrum` | `immunoglobulin` | 4 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `calcium` | `undecylenic_acid` | 4 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `colostrum` | `lactobacillus_rhamnosus` | 4 | 15.0 | **UNCATEGORIZED** | _(needs review)_ |
| `acerola_cherry` | `vitamin_c` | 4 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `quercetin` | `lecithin` | 4 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `lemon_balm_leaf` | `lemon_balm` | 4 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `phosphatidylserine` | `soybean` | 3 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `PII_PURIFIED_FISH_OIL` | `fish_oil` | 3 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `guarana` | `citrus_bioflavonoids` | 3 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `egcg` | `green_tea_extract` | 3 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `fish_oil` | `flaxseed` | 3 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `blood_orange_extract` | `citrus_bioflavonoids` | 3 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_isoleucine` | `collagen` | 3 | 11.8 | **UNCATEGORIZED** | _(needs review)_ |
| `l_valine` | `collagen` | 3 | 11.8 | **UNCATEGORIZED** | _(needs review)_ |
| `yerba_mate` | `caffeine` | 3 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `cinnamon_bark` | `cinnamon` | 3 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_lysine` | `whey_protein` | 3 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_proline` | `whey_protein` | 3 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_tryptophan` | `whey_protein` | 3 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `ginkgo_biloba` | `ginkgo` | 3 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `probiotics` | `lactobacillus_rhamnosus` | 3 | 14.0 | **UNCATEGORIZED** | _(needs review)_ |
| `grape_seed_extract` | `cranberry` | 3 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `magnesium` | `d_beta_hydroxybutyrate_bhb` | 3 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `gamma_butyrobetaine_ethyl_ester` | `fish_oil` | 3 | 7.5 | **UNCATEGORIZED** | _(needs review)_ |
| `polyphenols` | `cranberry` | 3 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `vitamin_a` | `lycopene` | 3 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `butyric_acid` | `dha` | 3 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `turkey_tail` | `beta_glucan` | 3 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `threonic_acid` | `vitamin_c` | 3 | 14.0 | **UNCATEGORIZED** | _(needs review)_ |
| `olive_fruit` | `olive_fruit_extract` | 3 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `pau_darco_bark` | `pau_darco` | 3 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `wild_blueberry` | `blueberry` | 3 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `nadh` | `vitamin_b3_niacin` | 2 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_ECHINACEA_EXTRACT` | `echinacea` | 2 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `vitamin_d` | `fish_oil` | 2 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `lecithin` | `choline` | 2 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `alpha_amylase` | `digestive_enzymes` | 2 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `BLEND_FITNOX` | `pomegranate` | 2 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `morosil` | `blood_orange_extract` | 2 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `saw_palmetto_berry` | `saw_palmetto` | 2 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_FOS` | `prebiotics` | 2 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `magnesium` | `creatine_monohydrate` | 2 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `ursolic_acid` | `holy_basil` | 2 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_glutamic_acid` | `whey_protein` | 2 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `guava` | `guava_leaf` | 2 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `diosmin` | `citrus_bioflavonoids` | 2 | 9.5 | **UNCATEGORIZED** | _(needs review)_ |
| `calcium` | `rice_bran` | 2 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `chlorella` | `omega_9_fatty_acids` | 2 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `PII_MICELLAR_CASEIN` | `casein` | 2 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `calcium` | `hmb` | 2 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `horny_goat_weed` | `flavones` | 2 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `chaste_tree` | `chasteberry` | 2 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `cognizin_citicoline` | `choline` | 2 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `lion_s_mane` | `lions_mane` | 2 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `potassium` | `prebiotics` | 2 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `astaxanthin` | `calanus_oil` | 2 | 11.5 | **UNCATEGORIZED** | _(needs review)_ |
| `genistein` | `ginkgo` | 2 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `boswellia` | `lecithin` | 2 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `kanna_sceletium` | `mesembrine` | 1 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_NEM_EGGSHELL_MEMBRANE` | `collagen` | 1 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `calcium` | `alpha_gpc` | 1 | 8.7 | **UNCATEGORIZED** | _(needs review)_ |
| `beta_glucans` | `beta_glucan` | 1 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `black_garlic` | `garlic` | 1 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_carnosine` | `zinc` | 1 | 15.0 | **UNCATEGORIZED** | _(needs review)_ |
| `calcium` | `dicalcium_phosphate` | 1 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `ADD_CARRAGEENAN` | `irish_sea_moss` | 1 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `cistanche` | `echinacea` | 1 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `vanadyl_sulfate` | `l_carnitine` | 1 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `fatty_acids` | `borage_seed_oil` | 1 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `probiotics` | `lactobacillus_salivarius` | 1 | 8.4 | **UNCATEGORIZED** | _(needs review)_ |
| `cayenne_pepper` | `capsaicin` | 1 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `triterpene_glycosides` | `black_cohosh` | 1 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `wild_yam_root` | `wild_yam` | 1 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `white_tea` | `green_tea_extract` | 1 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `linoleic_acid` | `omega_6_fatty_acids` | 1 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `gamma_linolenic_acid` | `omega_6_fatty_acids` | 1 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `phosphatidylcholine` | `lecithin` | 1 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `olive_leaf` | `olive_fruit_extract` | 1 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `l_glutamic_acid` | `l_glutamine` | 1 | 11.7 | **UNCATEGORIZED** | _(needs review)_ |
| `organ_extracts` | `pygeum` | 1 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `PII_SACCHAROMYCES_CEREVISIAE` | `brewers_yeast` | 1 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `barley_juice` | `barley_grass` | 1 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `kawaratake` | `turkey_tail` | 1 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `chasteberry` | `vitamin_e` | 1 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `olive_fruit` | `olive_leaf` | 1 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `calcium` | `d_beta_hydroxybutyrate_bhb` | 1 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `potassium` | `d_beta_hydroxybutyrate_bhb` | 1 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `icariin` | `flavones` | 1 | 11.0 | **UNCATEGORIZED** | _(needs review)_ |
| `pine_bark_extract` | `cranberry` | 1 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `NHA_BLADDERWRACK` | `brown_kelp` | 1 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `japanese_knotweed` | `resveratrol` | 1 | 12.0 | **UNCATEGORIZED** | _(needs review)_ |
| `beta_glucan` | `reishi` | 1 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `coq10` | `melatonin` | 1 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `keratin` | `l_arginine` | 1 | 13.0 | **UNCATEGORIZED** | _(needs review)_ |
| `phytosterols` | `pine_bark_extract` | 1 | 9.0 | **UNCATEGORIZED** | _(needs review)_ |
| `vitamin_e` | `canola_oil` | 1 | 5.0 | **BUG** | Brassica napus is the source plant, not the form. Same bug class. |
| `turmipure_gold` | `turmeric` | 1 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `vitamin_c` | `calcium` | 1 | 8.0 | **UNCATEGORIZED** | _(needs review)_ |
| `inulin` | `oligosaccharides` | 1 | 5.0 | **UNCATEGORIZED** | _(needs review)_ |
| `ADD_SENNA` | `senna` | 1 | 7.0 | **UNCATEGORIZED** | _(needs review)_ |
| `sophora_japonica` | `quercetin` | 1 | 6.0 | **UNCATEGORIZED** | _(needs review)_ |
| `astragalus_root` | `astragalus` | 1 | 10.0 | **UNCATEGORIZED** | _(needs review)_ |
| `vitamin_c` | `rose_hips` | 1 | 10.5 | **UNCATEGORIZED** | _(needs review)_ |

## Per-Pattern Detail (top 25 by volume)

### `vitamin_k` → `vitamin_k1` — 691 hits — **KEEP**

**Rationale:** Generic "Vitamin K" defaulting to K1 (phylloquinone) is the standard regulatory assumption.

**Avg bio_score assigned:** 9.0

**Form-text that triggered the jump:**

- `phytonadione` (483 hits)
- `vitamin k1` (201 hits)
- `phylloquinone` (7 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 12012 | CVS Pharmacy | Spectravite Advanced Formula | `Phytonadione` | `phylloquinone` | 9.0 |
| 12089 | CVS Pharmacy | Daily Multiple For Men 50+ | `Phytonadione` | `phylloquinone` | 9.0 |
| 18138 | CVS Pharmacy | Daily Multiple USP For Women | `Phytonadione` | `phylloquinone` | 9.0 |
| 18147 | CVS Pharmacy | Daily Multiple For Women 50+ | `Phytonadione` | `phylloquinone` | 9.0 |
| 18156 | CVS Pharmacy | Daily Multiple For Women 50+ | `Phytonadione` | `phylloquinone` | 9.0 |

### `tomato` → `lycopene` — 371 hits — **KEEP**

**Rationale:** Tomato extract products deliver lycopene as the active. Lycopene canonical has the RCT evidence.

**Avg bio_score assigned:** 9.0

**Form-text that triggered the jump:**

- `lycopene` (371 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 176181 | GNC SuperFoods | Ultra Mega Green Women's Multivitamin | `_(none)_` | `lycopene extract` | 9.0 |
| 176249 | GNC SuperFoods | Ultra Mega Green Women's Multivitamin | `_(none)_` | `lycopene extract` | 9.0 |
| 205803 | GNC Earth Genius | Women's Multivitamin | `_(none)_` | `lycopene extract` | 9.0 |
| 206910 | GNC Earth Genius | Women's Multivitamin | `_(none)_` | `lycopene extract` | 9.0 |
| 206914 | GNC Earth Genius | Men's Multivitamin | `_(none)_` | `lycopene extract` | 9.0 |

### `calcium` → `vitamin_c` — 230 hits — **SEMANTIC**

**Rationale:** Ca ascorbate label headed by Calcium — user bought it for Ca primarily.

**Avg bio_score assigned:** 11.7

**Form-text that triggered the jump:**

- `calcium ascorbate` (222 hits)
- `ascorbic acid` (5 hits)
- `ester-c` (2 hits)
- `ester-c calcium ascorbate` (1 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 175619 | GNC Pro Performance AMP | Mega Men Sport | `Calcium Ascorbate; Calcium Carbonate` | `calcium ascorbate` | 11.0 |
| 176166 | GNC Pro Performance AMP | Women's Ultra Mega Active Without Iron | `Calcium Ascorbate; Calcium Carbonate` | `calcium ascorbate` | 11.0 |
| 183541 | GNC AMP Advanced Muscle Performance | Mega Men Sport Multivitamin | `Calcium Ascorbate; Calcium Carbonate` | `calcium ascorbate` | 11.0 |
| 183595 | GNC AMP Advanced Muscle Performance | Women's Ultra Mega Active without Iron | `Calcium Ascorbate; Calcium Carbonate` | `calcium ascorbate` | 11.0 |
| 19431 | GNC WellBeing | Be-Whole Multivitamin & Mineral With Iron & Iodine | `Calcium Ascorbate; Calcium Carbonate` | `calcium ascorbate` | 11.0 |

### `ginger_extract` → `ginger` — 142 hits — **KEEP**

**Rationale:** Same root canonical; resolver dropped the "_extract" suffix. No score loss.

**Avg bio_score assigned:** 9.6

**Form-text that triggered the jump:**

- `ginger` (80 hits)
- `gingerols` (53 hits)
- `gingerol` (9 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 12847 | GNC Total Lean | Appetrex Control | `extract` | `ginger (unspecified)` | 10.0 |
| 15698 | GNC Women's Ultra Mega | Energy Enhancer | `extract` | `ginger (unspecified)` | 10.0 |
| 16369 | GNC Preventive Nutrition | Kidney Health | `extract` | `ginger (unspecified)` | 10.0 |
| 16372 | GNC Preventive Nutrition | Gastro Cleanser Formula | `Gingerol` | `ginger extract standardized` | 9.0 |
| 16374 | GNC Preventive Nutrition | Total Cleanser | `Gingerol` | `ginger extract standardized` | 9.0 |

### `curcumin` → `turmeric` — 119 hits — **SEMANTIC**

**Rationale:** High-absorption Curcumin products are 95% curcuminoids — should be curcumin, not generic turmeric.

**Avg bio_score assigned:** 6.0

**Form-text that triggered the jump:**

- `turmeric (curcuma longa) extract curcuminoids` (108 hits)
- `turmeric extract` (4 hits)
- `turmeric rhizome extract` (3 hits)
- `microactive turmeric (curcuma longa) extract` (2 hits)
- `turmeric extract curcuminoids` (1 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 202923 | Doctor's Best | High Absorption Curcumin 500 mg | `Bisdemethoxycurcumin; Curcumin; Curcuminoids; Demethoxycurcumin; Turmeric extract` | `turmeric extract (95% curcuminoids)` | 6.0 |
| 203024 | Doctor's Best | High Absorption Curcumin 1000 mg | `Bisdemethoxycurcumin; Curcumin; Curcuminoids; Demethoxycurcumin; Turmeric extract` | `turmeric extract (95% curcuminoids)` | 6.0 |
| 209396 | Doctor's Best | High Absorption Joint Support | `Curcuminoids; Turmeric extract` | `turmeric extract (95% curcuminoids)` | 6.0 |
| 269335 | Doctor's Best | High Absorption Curcumin 500 mg | `Bisdemethoxycurcumin; Curcumin; Curcuminoids; Demethoxycurcumin; Turmeric extract` | `turmeric extract (95% curcuminoids)` | 6.0 |
| 182725 | Pure Encapsulations | A.I. Formula | `Curcuminoids` | `turmeric extract (95% curcuminoids)` | 6.0 |

### `phosphorus` → `calcium` — 115 hits — **BUG**

**Rationale:** DCP-sourced Phosphorus row — exact pattern called out as fixed in code docstring, still happening.

**Avg bio_score assigned:** 6.1

**Form-text that triggered the jump:**

- `dicalcium phosphate` (107 hits)
- `dibasic calcium phosphate` (8 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 12012 | CVS Pharmacy | Spectravite Advanced Formula | `Dicalcium Phosphate` | `dicalcium phosphate` | 6.0 |
| 18269 | CVS Pharmacy | Spectravite Ultra Women's Health Senior | `Dicalcium Phosphate` | `dicalcium phosphate` | 6.0 |
| 19179 | CVS Pharmacy | B Complex With Vitamin C | `Dicalcium Phosphate` | `dicalcium phosphate` | 6.0 |
| 239455 | CVS Health | Spectravite Adults 50+ | `Dicalcium Phosphate` | `dicalcium phosphate` | 6.0 |
| 239509 | CVS Health | Spectravite Women | `Dicalcium Phosphate` | `dicalcium phosphate` | 6.0 |

### `broccoli` → `sulforaphane` — 105 hits — **KEEP**

**Rationale:** Broccoli sprout extracts are dosed for sulforaphane content.

**Avg bio_score assigned:** 10.0

**Form-text that triggered the jump:**

- `sulforaphane` (105 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 176181 | GNC SuperFoods | Ultra Mega Green Women's Multivitamin | `_(none)_` | `sulforaphane (unspecified)` | 10.0 |
| 176249 | GNC SuperFoods | Ultra Mega Green Women's Multivitamin | `_(none)_` | `sulforaphane (unspecified)` | 10.0 |
| 205803 | GNC Earth Genius | Women's Multivitamin | `_(none)_` | `sulforaphane (unspecified)` | 10.0 |
| 206910 | GNC Earth Genius | Women's Multivitamin | `_(none)_` | `sulforaphane (unspecified)` | 10.0 |
| 206914 | GNC Earth Genius | Men's Multivitamin | `_(none)_` | `sulforaphane (unspecified)` | 10.0 |

### `inositol` → `vitamin_b3_niacin` — 81 hits — **KEEP**

**Rationale:** Inositol hexanicotinate is genuinely a niacin form (delivers niacin systemically).

**Avg bio_score assigned:** 12.0

**Form-text that triggered the jump:**

- `inositol niacinate` (72 hits)
- `inositol hexanicotinate` (6 hits)
- `inositol hexaniacinate` (2 hits)
- `inositol nicotinate` (1 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 239475 | CVS Health | Flush Free Niacin Inositol Hexanicotinate 500 mg | `Inositol Hexanicotinate` | `inositol hexanicotinate` | 12.0 |
| 25895 | CVS Pharmacy | Flush Free Niacin Inositol Hexanicotinate 500 mg | `Inositol Hexanicotinate` | `inositol hexanicotinate` | 12.0 |
| 82340 | CVS Health | Flush Free Niacin Inositol Hexanicotinate 500 mg | `Inositol Hexanicotinate` | `inositol hexanicotinate` | 12.0 |
| 178685 | Equate | Men's Adult Gummy Natural Berry Flavors | `Inositol Niacinate` | `inositol hexanicotinate` | 12.0 |
| 178910 | Equate | Women's Adult Gummy Natural Berry Flavors | `Inositol Niacinate` | `inositol hexanicotinate` | 12.0 |

### `nicotinamide_riboside` → `vitamin_b3_niacin` — 63 hits — **KEEP**

**Rationale:** NR is a niacin family member.

**Avg bio_score assigned:** 11.7

**Form-text that triggered the jump:**

- `niacinamide` (63 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 62969 | Doctor's Best | Best Energy Featuring Niagen | `niacinamide` | `niacinamide` | 11.0 |
| 299751 | Pure Encapsulations | Mitochondria-ATP | `niacinamide` | `niacinamide` | 11.0 |
| 299752 | Pure Encapsulations | RevitalAge Ultra | `niacinamide` | `niacinamide` | 11.0 |
| 313541 | Pure Encapsulations | NR Longevity | `niacinamide` | `niacinamide` | 11.0 |
| 182278 | Thorne | ResveraCel | `niacinamide` | `niacinamide` | 11.0 |

### `dha` → `fish_oil` — 58 hits — **BUG**

**Rationale:** Fish oil is the source; DHA is the molecule. Losing DHA-specificity costs evidence depth.

**Avg bio_score assigned:** 9.0

**Form-text that triggered the jump:**

- `ethyl ester` (57 hits)
- `omega-3 concentrate` (1 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 239865 | Equate | Vision Formula 50+ | `ethyl ester` | `ethyl ester` | 9.0 |
| 239865 | Equate | Vision Formula 50+ | `ethyl ester` | `ethyl ester` | 9.0 |
| 239878 | Equate | Vision Formula 50+ | `ethyl ester` | `ethyl ester` | 9.0 |
| 239878 | Equate | Vision Formula 50+ | `ethyl ester` | `ethyl ester` | 9.0 |
| 179681 | Nature Made | One Per Day Fish Oil 1200 mg | `ethyl ester` | `ethyl ester` | 9.0 |

### `guarana` → `caffeine` — 55 hits — **KEEP**

**Rationale:** Guarana products are typically standardized for caffeine content.

**Avg bio_score assigned:** 13.0

**Form-text that triggered the jump:**

- `caffeine` (55 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 15698 | GNC Women's Ultra Mega | Energy Enhancer | `Caffeine` | `caffeine anhydrous` | 13.0 |
| 176190 | GNC SuperFoods | Whole Foods Energy & Metabolism | `Caffeine` | `caffeine anhydrous` | 13.0 |
| 18266 | GNC Herbal Plus Standardized | Guarana | `Caffeine` | `caffeine anhydrous` | 13.0 |
| 18317 | GNC Herbal Plus Formula | Energy Formula | `Caffeine` | `caffeine anhydrous` | 13.0 |
| 191084 | GNC Men's | Energy Enhancer | `Caffeine` | `caffeine anhydrous` | 13.0 |

### `digestive_enzymes` → `papaya` — 43 hits — **REVIEW**

**Rationale:** Papain (enzyme) routed to papaya fruit. Depends on label.

**Avg bio_score assigned:** 6.0

**Form-text that triggered the jump:**

- `papaya` (40 hits)
- `carica papaya` (3 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 175375 | GNC Pro Performance | Complete Vegan Protein Natural Chocolate | `Papaya` | `papaya fruit` | 6.0 |
| 175409 | GNC Pro Performance | Complete Vegan Gainer Natural Chocolate | `Papaya` | `papaya fruit` | 6.0 |
| 220034 | GNC Earth Genius | PurEdge Plant-Based Gainer Natural Chocolate | `Papaya` | `papaya fruit` | 6.0 |
| 229690 | GNC Earth Genius | PurEdge Plant-Based Gainer Natural Vanilla | `Papaya` | `papaya fruit` | 6.0 |
| 42271 | GNC PUREDGE | Complete Vegan Protein Natural Chocolate | `Papaya` | `papaya fruit` | 6.0 |

### `NHA_COLLAGEN_HYDROLYZED` → `collagen` — 32 hits — **KEEP**

**Rationale:** Branded → generic for the same molecule.

**Avg bio_score assigned:** 11.0

**Form-text that triggered the jump:**

- `hydrolyzed collagen` (32 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 1251 | Doctor's Best | Best Hyaluronic Acid with Chondroitin Sulfate | `_(none)_` | `hydrolyzed collagen peptides` | 11.0 |
| 202994 | Doctor's Best | Hyaluronic Acid + Chondroitin Sulfate | `_(none)_` | `hydrolyzed collagen peptides` | 11.0 |
| 203120 | Doctor's Best | Hyaluronic Acid + Chondroitin Sulfate | `_(none)_` | `hydrolyzed collagen peptides` | 11.0 |
| 203131 | Doctor's Best | Glucosamine Chondroitin MSM + Hyaluronic Acid | `_(none)_` | `hydrolyzed collagen peptides` | 11.0 |
| 209410 | Doctor's Best | Hyaluronic Acid + Chondroitin Sulfate | `_(none)_` | `hydrolyzed collagen peptides` | 11.0 |

### `creatine_monohydrate` → `fish_oil` — 32 hits — **BUG**

**Rationale:** Cross-domain — likely form-alias collision (no biological relationship).

**Avg bio_score assigned:** 8.6

**Form-text that triggered the jump:**

- `ethyl ester` (32 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 175429 | GNC Pro Performance AMP | Amplified Mass XXX Chocolate | `ethyl ester; hydrochloride` | `ethyl ester` | 8.5 |
| 210519 | GNC AMP | Mass XXX Chocolate | `ethyl ester; hydrochloride` | `ethyl ester` | 8.5 |
| 221167 | GNC AMP Advanced Muscle Performance | Mass XXX Vanilla | `ethyl ester; hydrochloride` | `ethyl ester` | 8.5 |
| 221370 | GNC AMP Advanced Muscle Performance | Mass XXX Cookies & Cream | `ethyl ester; hydrochloride` | `ethyl ester` | 8.5 |
| 221476 | GNC AMP Advanced Muscle Performance | Mass XXX Chocolate Raspberry Truffle | `ethyl ester; hydrochloride` | `ethyl ester` | 8.5 |

### `magnesium` → `vitamin_c` — 32 hits — **BUG**

**Rationale:** Mg ascorbate label headed by Magnesium — user bought it for Mg, not C.

**Avg bio_score assigned:** 11.8

**Form-text that triggered the jump:**

- `magnesium ascorbate` (27 hits)
- `ascorbic acid` (5 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 183533 | Pure Encapsulations | Buffered Ascorbic Acid Capsules | `Magnesium Ascorbate` | `magnesium ascorbate` | 13.0 |
| 184870 | Pure Encapsulations | PurePals (with Iron) Natural Cherry Flavor | `Magnesium Ascorbate; Magnesium Aspartate` | `magnesium ascorbate` | 11.0 |
| 185303 | Pure Encapsulations | PurePals (with Iron) Natural Cherry Flavor | `Magnesium Ascorbate; Magnesium Aspartate` | `magnesium ascorbate` | 11.0 |
| 201303 | Pure Encapsulations | Buffered Ascorbic Acid Capsules | `Magnesium Ascorbate` | `magnesium ascorbate` | 13.0 |
| 201304 | Pure Encapsulations | Buffered Ascorbic Acid Capsules | `Magnesium Ascorbate` | `magnesium ascorbate` | 13.0 |

### `l_leucine` → `casein` — 31 hits — **BUG**

**Rationale:** Leucine label routed to casein because leucine is a casein-derived amino acid.

**Avg bio_score assigned:** 11.9

**Form-text that triggered the jump:**

- `calcium caseinate` (31 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 183379 | GNC Beyond Raw | Re-Built Mass XP Chocolate | `Calcium Caseinate; L-Leucine; Whey Peptides, Hydrolyzed; Whey Protein Concentrate; Whey Protein Isolate` | `calcium caseinate` | 11.8 |
| 18452 | GNC Pro Performance AMP | Amplified Recovery Protein XR Chocolate | `Calcium Caseinate; L-Leucine, Micronized; Micellar Casein; Whey Peptides; Whey Protein Concentrate; Whey Protein Isolate` | `calcium caseinate` | 11.3 |
| 18469 | GNC Pro Performance AMP | Amplified Recovery Protein XR Vanilla | `Calcium Caseinate; L-Leucine, Micronized; Micellar Casein; Whey Peptides; Whey Protein Concentrate; Whey Protein Isolate` | `calcium caseinate` | 11.3 |
| 19483 | GNC Beyond Raw | Re-Built Mass Strawberry Milkshake | `Calcium Caseinate; L-Leucine; Soy Protein Isolate; Whey Peptides, Hydrolyzed; Whey Protein Concentrate; Whey Protein Isolate` | `calcium caseinate` | 12.2 |
| 19494 | GNC Beyond Raw | Re-Built Mass Cookies & Cream | `Calcium Caseinate; L-Leucine; Soy Protein Isolate; Whey Peptides, Hydrolyzed; Whey Protein Concentrate; Whey Protein Isolate` | `calcium caseinate` | 12.2 |

### `vitamin_e` → `sunflower_oil` — 31 hits — **BUG**

**Rationale:** Sunflower oil is the SOURCE, not the form. Vit E α-tocopherol is the nutrient.

**Avg bio_score assigned:** 5.0

**Form-text that triggered the jump:**

- `sunflower oil` (31 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 204501 | Garden of Life | Raw Organic Fit Chocolate | `Sunflower Oil` | `sunflower oil` | 5.0 |
| 204521 | Garden of Life | Raw Organic Fit Coffee | `Sunflower Oil` | `sunflower oil` | 5.0 |
| 204565 | Garden of Life | Raw Organic Fit Original | `Sunflower Oil` | `sunflower oil` | 5.0 |
| 204567 | Garden of Life | Raw Organic Fit Vanilla | `Sunflower Oil` | `sunflower oil` | 5.0 |
| 233274 | Garden of Life | Organic Fit Chocolate Flavor | `Sunflower Oil` | `sunflower oil` | 5.0 |

### `phosphorus` → `potassium` — 30 hits — **BUG**

**Rationale:** Same family — K-phosphate row tracked as K, not P.

**Avg bio_score assigned:** 10.0

**Form-text that triggered the jump:**

- `dipotassium phosphate` (30 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 182128 | GNC Total Lean Advanced | Lean Shake Burn Chocolate Fudge | `Dimagnesium Phosphate; Dipotassium Phosphate` | `potassium phosphate` | 10.0 |
| 182149 | GNC Total Lean Advanced | Lean Shake Burn Cookies & Cream | `Dimagnesium Phosphate; Dipotassium Phosphate` | `potassium phosphate` | 10.0 |
| 211331 | GNC Beyond Raw | Macros Chocolate Chip Muffin | `Dipotassium Phosphate; Tricalcium Phosphate` | `potassium phosphate` | 10.0 |
| 213307 | GNC Total Lean | Lean Shake Burn Chocolate Fudge | `Dimagnesium Phosphate; Dipotassium Phosphate` | `potassium phosphate` | 10.0 |
| 213308 | GNC Total Lean | Lean Shake Burn Vanilla Creme | `Dimagnesium Phosphate; Dipotassium Phosphate` | `potassium phosphate` | 10.0 |

### `turmeric` → `curcumin` — 27 hits — **KEEP**

**Rationale:** When label is generic turmeric BUT form is curcumin extract 95%, curcumin canonical is more accurate.

**Avg bio_score assigned:** 7.9

**Form-text that triggered the jump:**

- `curcuwin` (25 hits)
- `curcumin c3 complex` (2 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 81739 | Doctor's Best | High Absorption Curcumin 500 mg | `Bisdemethoxy Curcumin; Curcumin C3 Complex; Curcumin; Curcuminoids; Demethoxy Curcumin` | `curcumin c3 complex` | 6.0 |
| 219012 | GNC Mega Men | Mega Men Multivitamin | `Curcuminoids` | `curcuwin` | 8.0 |
| 219028 | GNC Mega Men | Mega Men Multivitamin | `20% Curcuminoids` | `curcuwin` | 8.0 |
| 228798 | GNC Mega Men | 50 Plus | `Curcuminoids` | `curcuwin` | 8.0 |
| 228799 | GNC Mega Men | 50 Plus | `20% Curcuminoids` | `curcuwin` | 8.0 |

### `RISK_YOHIMBE` → `yohimbe` — 26 hits — **REVIEW**

**Rationale:** Risk canonical routed to safe canonical — needs safety/regulatory review.

**Avg bio_score assigned:** 5.0

**Form-text that triggered the jump:**

- `yohimbe` (22 hits)
- `yohimbine hcl` (2 hits)
- `yohimbine hydrochloride` (2 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 2219 | GNC Beyond Raw | Ravage Grape | `_(none)_` | `yohimbe (unspecified)` | 5.0 |
| 27343 | GNC Pro Performance AMP | Amplified N.O. Loaded V2 Watermelon | `_(none)_` | `yohimbe (unspecified)` | 5.0 |
| 27346 | GNC Pro Performance AMP | Amplified N.O. Loaded V2 Fruit Punch | `_(none)_` | `yohimbe (unspecified)` | 5.0 |
| 28981 | GNC Beyond Raw | Ravage Fruit Punch | `_(none)_` | `yohimbe (unspecified)` | 5.0 |
| 2915 | GNC Pro Performance AMP Advanced Muscle Performance | Amplified N.O. Loaded Fruit Punch | `_(none)_` | `yohimbe (unspecified)` | 5.0 |

### `BANNED_7_KETO_DHEA` → `7_keto_dhea` — 25 hits — **UNCATEGORIZED**

**Rationale:** _(needs review)_

**Avg bio_score assigned:** 7.0

**Form-text that triggered the jump:**

- `7-keto dhea` (21 hits)
- `dhea-acetate-7-one` (3 hits)
- `7-keto-dhea` (1 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 31147 | GNC Beyond Raw | Re-Comp | `_(none)_` | `7-keto dhea (unspecified)` | 7.0 |
| 241706 | HUM | Ripped Rooster | `_(none)_` | `7-keto dhea (unspecified)` | 7.0 |
| 184353 | Pure Encapsulations | 7-Keto DHEA 25 mg | `_(none)_` | `7-keto dhea (unspecified)` | 7.0 |
| 204640 | Pure Encapsulations | 7-Keto DHEA 100 mg | `_(none)_` | `7-keto dhea (unspecified)` | 7.0 |
| 204647 | Pure Encapsulations | 7-Keto DHEA 100 mg | `_(none)_` | `7-keto dhea (unspecified)` | 7.0 |

### `green_tea` → `green_tea_extract` — 24 hits — **UNCATEGORIZED**

**Rationale:** _(needs review)_

**Avg bio_score assigned:** 9.3

**Form-text that triggered the jump:**

- `total tea catechins` (16 hits)
- `green tea extract` (8 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 26371 | GNC Mega Men | Mega Men Soft Chew Multivitamin Fruit Punch | `_(none)_` | `green tea extract (unspecified)` | 10.0 |
| 31121 | GNC Women's Ultra Mega | Soft Chew Multivitamin Mixed Berry | `_(none)_` | `green tea extract (unspecified)` | 10.0 |
| 74839 | GNC Women's Ultra Mega | Soft Chew Multivitamin Delicious Mixed Berry | `_(none)_` | `green tea extract (unspecified)` | 10.0 |
| 75121 | GNC Mega Men | Mega Men Soft Chew Multivitamin Fruit Punch | `_(none)_` | `green tea extract (unspecified)` | 10.0 |
| 77052 | Nutricost | Energy Complex | `_(none)_` | `green tea extract (unspecified)` | 10.0 |

### `elderberries` → `elderberry` — 23 hits — **UNCATEGORIZED**

**Rationale:** _(needs review)_

**Avg bio_score assigned:** 9.0

**Form-text that triggered the jump:**

- `elderberry` (20 hits)
- `elderberries` (3 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 315703 | Double Wood Supplements | Zinc Elderberry & Vitamin C | `_(none)_` | `elderberry (unspecified)` | 9.0 |
| 276844 | GNC Mega Men | Mega Men Multivitamin | `Sambucus nigra, Powder` | `elderberry (unspecified)` | 9.0 |
| 304642 | GNC Mega Men | Mega Men Multivitamin | `Sambucus nigra, Powder` | `elderberry (unspecified)` | 9.0 |
| 304645 | GNC Mega Men | Mega Men | `_(none)_` | `elderberry (unspecified)` | 9.0 |
| 305834 | GNC | Multivitamin + Immune | `Sambucus nigra, Powder` | `elderberry (unspecified)` | 9.0 |

### `l_arginine` → `whey_protein` — 23 hits — **UNCATEGORIZED**

**Rationale:** _(needs review)_

**Avg bio_score assigned:** 11.6

**Form-text that triggered the jump:**

- `whey protein isolate` (18 hits)
- `whey protein concentrate` (5 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 175944 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power French Vanilla | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |
| 221095 | GNC Women's Ultra Mega | Energy & Metabolism Chocolate | `Whey Protein Concentrate` | `whey protein concentrate` | 10.0 |
| 48186 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power Chocolate Fudge | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |
| 49174 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power French Vanilla | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |
| 49632 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power Strawberry | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |

### `l_glutamine` → `whey_protein` — 23 hits — **UNCATEGORIZED**

**Rationale:** _(needs review)_

**Avg bio_score assigned:** 11.7

**Form-text that triggered the jump:**

- `whey protein isolate` (17 hits)
- `whey protein concentrate` (5 hits)
- `hydrolyzed whey protein` (1 hits)

**Examples (real DSLD products):**

| DSLD | Brand | Product | Label forms | Resolver picked | Bio |
|---|---|---|---|---|---:|
| 176044 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Original Natural Chocola | `hydrolyzed Whey Protein; L-Glutamine, Micronized; Whey Protein Isolate` | `hydrolyzed whey protein` | 11.7 |
| 48186 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power Chocolate Fudge | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |
| 49174 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power French Vanilla | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |
| 49632 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power Strawberry | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |
| 49634 | GNC Pro Performance AMP | Amplified Wheybolic Extreme 60 Power Strawberry | `Whey Protein Isolate; Whey Protein, Hydrolyzed` | `whey protein isolate` | 12.0 |

## Summary by Verdict

| Verdict | Distinct patterns | Total rows affected |
|---|---:|---:|
| **BUG** | 8 | 330 |
| **SEMANTIC** | 2 | 349 |
| **KEEP** | 9 | 1,567 |
| **REVIEW** | 2 | 69 |
| **UNCATEGORIZED** | 191 | 1,172 |

## Proposed Fix (Surgical)

Apply the gap-close to `_match_quality_map` so the parent-fallback fires when the constraint
eliminates all candidates. Then add an *explicit allowlist* of legitimate cross-parent jumps so
the KEEP-verdict patterns continue to use the more-specific active-compound canonical.

```python
# scripts/enrich_supplements_v3.py — replace lines 5862–5870

# Allowlist: cleaner_cid → resolved_cid pairs where cross-parent jump is more
# medically accurate than the cleaner's broader canonical (source plant →
# standardized active compound). These bypass the hard-constraint.
LEGITIMATE_CROSS_PARENT = {
    ("tomato", "lycopene"),
    ("broccoli", "sulforaphane"),
    ("ginger_extract", "ginger"),
    ("turmeric", "curcumin"),
    ("guarana", "caffeine"),
    ("inositol", "vitamin_b3_niacin"),
    ("nicotinamide_riboside", "vitamin_b3_niacin"),
    ("vitamin_k", "vitamin_k1"),
    ("NHA_COLLAGEN_HYDROLYZED", "collagen"),
}

if cleaner_iqm_canonical and candidates:
    constrained = [c for c in candidates if c["parent_key"] == cleaner_iqm_canonical]
    if constrained:
        if len(constrained) != len(candidates):
            cleaner_canonical_enforced = True
        candidates = constrained
    else:
        # Check allowlist for legitimate cross-parent jumps
        legit = [c for c in candidates
                 if (cleaner_iqm_canonical, c["parent_key"]) in LEGITIMATE_CROSS_PARENT]
        if legit:
            candidates = legit  # keep the more-specific active-compound match
        else:
            # NEW: cleaner resolved an IQM parent but no on-canonical form matched.
            # Force fallthrough to parent-level fallback (unspecified form under
            # cleaner's canonical) rather than letting an off-canonical match win.
            cleaner_canonical_enforced = True
            cleaner_canonical_fallback = True
            candidates = []
```

## Expected Impact (After Fix)

| Verdict | Behavior | Rows affected |
|---|---|---:|
| BUG | Reassigned to cleaner's canonical (unspecified form, bio≈5–8) | 330 |
| SEMANTIC | Reassigned to cleaner's canonical | 349 |
| KEEP | Unchanged (allowlist) | 1,567 |
| REVIEW | Hold pending clinical sign-off | 69 |
| UNCATEGORIZED | Hold pending review | 1,172 |

## Required Tests (regression coverage)

Add fixtures based on real DSLD examples to `scripts/tests/test_canonical_constraint.py`:

- DSLD 18269 (Spectravite) — phosphorus row with dicalcium phosphate form must resolve as `phosphorus`
- DSLD 323711 (Ritual Essential for Men) — Vit E with Brassica napus form must resolve as `vitamin_e`
- DSLD 204501 (GoL Raw Organic Fit) — Vit E with sunflower oil form must resolve as `vitamin_e`
- DSLD 202923 (Doctor's Best Curcumin) — curcumin row with turmeric extract 95% form must resolve as `curcumin`
- DSLD 176181 (GNC Ultra Mega Green) — tomato row must resolve as `lycopene` (KEEP allowlist)

## Next Steps

1. **Clinical review** of every row in the All Crossing Patterns table — assign final verdict to each pair.
2. **Curate the allowlist** based on clinician feedback — what stays cross-parent, what falls back.
3. **Patch `_match_quality_map`** with the surgical fix above.
4. **Add regression tests** for at least 5 representative patterns.
5. **Re-enrich + re-score** the full corpus.
6. **Diff scores** — generate impact report comparing before/after for clinical QA.
7. **Roll forward** to Supabase only after impact report has been clinically signed off.
