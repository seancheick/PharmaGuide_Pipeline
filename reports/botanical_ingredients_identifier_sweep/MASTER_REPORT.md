# IQM Identifier Sweep — Master Report

- **Generated:** 2026-05-28T19:59:45.711749+00:00
- **IQM snapshot SHA-256:** `1a04944ee1a9c52d499a7297190cfa27d7cd14f4d1efd308cd475e8cd770ca46`
- **Parents audited:** 529 of 529
- **Run duration:** 135.5s

## Per-field verification totals

| Field | verified_clean | mismatched | unresolvable | ambiguous_authority | skipped_intentional_null |
|---|---|---|---|---|---|
| `cui` | 190 | 232 | 85 | 20 | 2 |
| `external_ids.cas` | 528 | 1 | 0 | 0 | 0 |
| `external_ids.inchi_key` | 529 | 0 | 0 | 0 | 0 |
| `external_ids.pubchem_cid` | 529 | 0 | 0 | 0 | 0 |
| `external_ids.unii` | 509 | 20 | 0 | 0 | 0 |
| `rxcui` | 523 | 5 | 1 | 0 | 0 |

## Severity breakdown (non-seed findings)

- **high:** 302
- **medium:** 26
- **low:** 7
- **informational:** 0

## Status breakdown (non-seed findings)

- **ambiguous_authority:** 20
- **mismatched:** 258
- **unresolvable:** 86

## Authority API call counts

- **umls:** 76
- **pubchem:** 0
- **gsrs:** 11
- **rxnorm_in_memory_cache_size:** 189

## Seed findings (pre-known content-verified bugs)

These are pre-populated per spec §'Existing seed findings' so re-runs prove the methodology catches known cases. Two are still pending IQM correction (`coq10`, `5_htp`); the third (`genistein`) is sanity-check only.

- **coq10** / `cui`: resolved_to_disease_or_syndrome (severity=high)
- **5_htp** / `cui`: resolved_to_branded_or_clinical_drug (severity=high)
- **genistein** / `agent2_id (in curated_interactions_v1.json, not IQM)`: previously_corrupted_in_curated_interactions_now_fixed (severity=informational)

## High-severity findings (this run)

- **acerola_cherry** / `cui` (no_token_overlap_with_iqm_name): current=`C0950505`
- **african_geranium** / `cui` (no_token_overlap_with_iqm_name): current=`C1090842`
- **alfalfa_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0085839`
- **aloe_vera_concentrated_gel** / `cui` (no_token_overlap_with_iqm_name): current=`C0002707`
- **amla_fruit** / `cui` (no_token_overlap_with_iqm_name): current=`C0971862`
- **angelica_archangelica** / `cui` (no_token_overlap_with_iqm_name): current=`C0331174`
- **angelica_gigas** / `cui` (no_token_overlap_with_iqm_name): current=`C1006839`
- **apocynum_venetum_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0949822`
- **apricot** / `cui` (no_token_overlap_with_iqm_name): current=`C0003607`
- **asparagus** / `cui` (no_token_overlap_with_iqm_name): current=`C0003741`
- **astragalus_root** / `cui` (cui_not_found_in_umls): current=`C0004133`
- **atractylodes** / `cui` (no_token_overlap_with_iqm_name): current=`C0949568`
- **bacopa** / `cui` (no_token_overlap_with_iqm_name): current=`C0950097`
- **barberry_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0004747`
- **beet_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0004749`
- **beetroot** / `cui` (no_token_overlap_with_iqm_name): current=`C0004749`
- **belleric_myrobalan** / `cui` (no_token_overlap_with_iqm_name): current=`C0950296`
- **bilberry_fruit** / `cui` (cui_not_found_in_umls): current=`C0004843`
- **bitter_melon_fruit** / `cui` (no_token_overlap_with_iqm_name): current=`C0004811`
- **black_cherry** / `cui` (cui_not_found_in_umls): current=`C0330497`
- **black_garlic** / `cui` (cui_not_found_in_umls): current=`C0993243`
- **black_ginger** / `cui` (no_token_overlap_with_iqm_name): current=`C3178990`
- **black_pepper** / `cui` (no_token_overlap_with_iqm_name): current=`C0030934`
- **blackcurrant** / `cui` (resolved_to_disease_or_syndrome): current=`C0004842`
- **blessed_thistle** / `cui` (no_token_overlap_with_iqm_name): current=`C0330621`
- **blue_cohosh** / `cui` (no_token_overlap_with_iqm_name): current=`C0331048`
- **blue_flag_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949872`
- **blue_vervain** / `cui` (no_token_overlap_with_iqm_name): current=`C0949588`
- **blueberry_fruit** / `cui` (cui_not_found_in_umls): current=`C0004843`
- **boldo_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0950026`
- **boneset_herb** / `cui` (no_token_overlap_with_iqm_name): current=`C0949776`
- **boswellia_serrata_resin** / `cui` (resolved_to_branded_or_clinical_drug): current=`C1260643`
- **broccoli_sprout** / `cui` (no_token_overlap_with_iqm_name): current=`C4521843`
- **buchu_leaf** / `cui` (cui_not_found_in_umls): current=`C0996116`
- **buckthorn_bark** / `cui` (no_token_overlap_with_iqm_name): current=`C0949619`
- **buckwheat_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0330501`
- **bupleurum_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949630`
- **burdock_root_powder** / `cui` (cui_not_found_in_umls): current=`C0003780`
- **butchers_broom_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0330653`
- **cacao_powder** / `cui` (cui_not_found_in_umls): current=`C0006879`
- **california_poppy** / `cui` (no_token_overlap_with_iqm_name): current=`C0949771`
- **caralluma** / `cui` (no_token_overlap_with_iqm_name): current=`C3178930`
- **caralluma_fimbriata** / `cui` (no_token_overlap_with_iqm_name): current=`C3178930`
- **cardamom** / `cui` (cui_not_found_in_umls): current=`C0006761`
- **carob** / `cui` (cui_not_found_in_umls): current=`C0006820`
- **carrot** / `cui` (resolved_to_disease_or_syndrome): current=`C0007788`
- **carrot_seed_oil** / `cui` (resolved_to_disease_or_syndrome): current=`C0007788`
- **cassava** / `cui` (no_token_overlap_with_iqm_name): current=`C1141016`
- **cat_s_claw_bark** / `cui` (no_token_overlap_with_iqm_name): current=`C0949579`
- **catnip_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0949987`
- **cayenne_pepper** / `cui` (no_token_overlap_with_iqm_name): current=`C0006909`
- **celandine** / `cui` (no_token_overlap_with_iqm_name): current=`C0949680`
- **celastrus_paniculatus** / `cui` (no_token_overlap_with_iqm_name): current=`C0949670`
- **celery_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0007011`
- **ceylon_cinnamon** / `cui` (cui_not_found_in_umls): current=`C0008863`
- **chaga_mushroom_powder** / `cui` (cui_not_found_in_umls): current=`C1089270`
- **chanca_piedra** / `cui` (no_token_overlap_with_iqm_name): current=`C0949896`
- **chaste_tree** / `cui` (no_token_overlap_with_iqm_name): current=`C0042640`
- **chebulic_myrobalan** / `cui` (no_token_overlap_with_iqm_name): current=`C0950307`
- **chia_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0950198`
- **chickweed_herb** / `cui` (no_token_overlap_with_iqm_name): current=`C0331139`
- **chicory_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0008080`
- **chili_pepper** / `cui` (no_token_overlap_with_iqm_name): current=`C0006909`
- **chinese_dodder_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0949729`
- **chinese_licorice** / `cui` (no_token_overlap_with_iqm_name): current=`C0949837`
- **chlorella_powder** / `cui` (no_token_overlap_with_iqm_name): current=`C0008088`
- **chokeberry** / `cui` (no_token_overlap_with_iqm_name): current=`C0949547`
- **cilantro** / `cui` (no_token_overlap_with_iqm_name): current=`C0331198`
- **cinnamon_bark** / `cui` (cui_not_found_in_umls): current=`C0008863`
- **cleavers_herb** / `cui` (no_token_overlap_with_iqm_name): current=`C0949810`
- **cloves** / `cui` (no_token_overlap_with_iqm_name): current=`C0330581`
- **cnidium** / `cui` (no_token_overlap_with_iqm_name): current=`C0949701`
- **codonopsis** / `cui` (no_token_overlap_with_iqm_name): current=`C0949702`
- **coleus_forskohlii_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949706`
- **coptis_rhizome** / `cui` (no_token_overlap_with_iqm_name): current=`C0949717`
- **cordyceps** / `cui` (no_token_overlap_with_iqm_name): current=`C0949718`
- **cordyceps_mushroom_powder** / `cui` (no_token_overlap_with_iqm_name): current=`C0949718`
- **coriander** / `cui` (no_token_overlap_with_iqm_name): current=`C0331198`
- **couch_grass** / `cui` (cui_not_found_in_umls): current=`C0950342`
- **cowslip** / `cui` (no_token_overlap_with_iqm_name): current=`C0949616`
- **cramp_bark** / `cui` (no_token_overlap_with_iqm_name): current=`C0949597`
- **cranberry** / `cui` (resolved_to_disease_or_syndrome): current=`C0010074`
- **cranberry_fruit** / `cui` (resolved_to_disease_or_syndrome): current=`C0010074`
- **cranesbill** / `cui` (no_token_overlap_with_iqm_name): current=`C0949814`
- **cumin_seed** / `cui` (resolved_to_disease_or_syndrome): current=`C0010481`
- **cutch_tree** / `cui` (no_token_overlap_with_iqm_name): current=`C0949533`
- **cyperus** / `cui` (no_token_overlap_with_iqm_name): current=`C0949733`
- **dandelion** / `cui` (no_token_overlap_with_iqm_name): current=`C0011131`
- **dandelion_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0011131`
- **danshen** / `cui` (no_token_overlap_with_iqm_name): current=`C0036098`
- **dark_sweet_cherry** / `cui` (no_token_overlap_with_iqm_name): current=`C0330505`
- **date** / `cui` (cui_not_found_in_umls): current=`C0011136`
- **devils_claw_tuber** / `cui` (no_token_overlap_with_iqm_name): current=`C0018263`
- **dgl_deglycyrrhizinated_licorice** / `cui` (resolved_to_disease_or_syndrome): current=`C0023351`
- **dill_weed** / `cui` (cui_not_found_in_umls): current=`C0011224`
- **dong_quai** / `cui` (no_token_overlap_with_iqm_name): current=`C0002836`
- **echinacea_angustifolia** / `cui` (cui_not_found_in_umls): current=`C0013479`
- **echinacea_purpurea_aerial** / `cui` (no_token_overlap_with_iqm_name): current=`C0330464`
- **echinacea_purpurea_herb** / `cui` (no_token_overlap_with_iqm_name): current=`C0330464`
- **echinacea_purpurea_root_extract** / `cui` (no_token_overlap_with_iqm_name): current=`C0330464`
- **elder_blossom** / `cui` (cui_not_found_in_umls): current=`C0036195`
- **elderberries** / `cui` (cui_not_found_in_umls): current=`C0036195`
- **eleuthero_stem** / `cui` (no_token_overlap_with_iqm_name): current=`C0013849`
- **eucalyptus** / `cui` (cui_not_found_in_umls): current=`C0015143`
- **eucalyptus_leaf_oil** / `cui` (cui_not_found_in_umls): current=`C0015143`
- **european_ash_seed_fruit** / `cui` (no_token_overlap_with_iqm_name): current=`C0949800`
- **evening_primrose_seed_oil** / `cui` (no_token_overlap_with_iqm_name): current=`C0014895`
- **evodia_fruit** / `cui` (no_token_overlap_with_iqm_name): current=`C0950325`
- **eyebright** / `cui` (no_token_overlap_with_iqm_name): current=`C0949777`
- **false_unicorn** / `cui` (no_token_overlap_with_iqm_name): current=`C0949787`
- **fenugreek_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0015594`
- **feverfew** / `cui` (cui_not_found_in_umls): current=`C0015636`
- **fig** / `cui` (no_token_overlap_with_iqm_name): current=`C0015766`
- **forsythia_suspensa** / `cui` (no_token_overlap_with_iqm_name): current=`C0949793`
- **frangula_bark** / `cui` (no_token_overlap_with_iqm_name): current=`C0949793`
- **fringe_tree** / `cui` (no_token_overlap_with_iqm_name): current=`C0949688`
- **galega_officinalis** / `cui` (no_token_overlap_with_iqm_name): current=`C0949808`
- **gardenia** / `cui` (no_token_overlap_with_iqm_name): current=`C0949811`
- **garlic_bulb** / `cui` (cui_not_found_in_umls): current=`C0993243`
- **ginger_extract** / `cui` (cui_not_found_in_umls): current=`C0017149`
- **ginger_root** / `cui` (cui_not_found_in_umls): current=`C0017149`
- **ginkgo_biloba_leaf** / `cui` (cui_not_found_in_umls): current=`C0017578`
- **ginseng_root_panax** / `cui` (no_token_overlap_with_iqm_name): current=`C0017648`
- **glehnia** / `cui` (no_token_overlap_with_iqm_name): current=`C0949816`
- **globe_artichoke** / `cui` (cui_not_found_in_umls): current=`C0003785`
- **goats_rue** / `cui` (no_token_overlap_with_iqm_name): current=`C0949808`
- **goji_berry** / `cui` (no_token_overlap_with_iqm_name): current=`C0330505`
- **goldenrod** / `cui` (resolved_to_disease_or_syndrome): current=`C0038534`
- **goldenseal** / `cui` (cui_not_found_in_umls): current=`C0330520`
- **goldenseal** / `rxcui` (rxcui_not_found_in_rxnav): current=`253171`
- **gotu_kola** / `cui` (cui_not_found_in_umls): current=`C0007037`
- **grape** / `cui` (no_token_overlap_with_iqm_name): current=`C0018208`
- **grape_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0018208`
- **gravel_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949778`
- **graviola** / `cui` (no_token_overlap_with_iqm_name): current=`C1002484`
- **green_bean** / `cui` (no_token_overlap_with_iqm_name): current=`C0016968`
- **green_bell_pepper** / `cui` (no_token_overlap_with_iqm_name): current=`C0006909`
- **guava** / `cui` (no_token_overlap_with_iqm_name): current=`C0018338`
- **guggul** / `cui` (no_token_overlap_with_iqm_name): current=`C0949715`
- **gymnema_sylvestre** / `cui` (no_token_overlap_with_iqm_name): current=`C0949826`
- **gynostemma** / `cui` (cui_not_found_in_umls): current=`C0949828`
- **hawthorn_flowering_tops** / `cui` (no_token_overlap_with_iqm_name): current=`C0010196`
- **hesperidin** / `cui` (no_token_overlap_with_iqm_name): current=`C0019593`
- **holy_basil_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0950004`
- **horehound** / `cui` (cui_not_found_in_umls): current=`C0024879`
- **horny_goat_weed** / `cui` (no_token_overlap_with_iqm_name): current=`C0949767`
- **horse_chestnut_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0001443`
- **horseradish** / `cui` (cui_not_found_in_umls): current=`C0020424`
- **horsetail_aerial_parts** / `cui` (cui_not_found_in_umls): current=`C0014825`
- **hydrangea_root** / `cui` (resolved_to_disease_or_syndrome): current=`C0949855`
- **hyssop** / `cui` (resolved_to_disease_or_syndrome): current=`C0020443`
- **indian_kino_tree** / `cui` (no_token_overlap_with_iqm_name): current=`C0949602`
- **indian_madder** / `cui` (no_token_overlap_with_iqm_name): current=`C0950179`
- **indian_tinospora** / `cui` (no_token_overlap_with_iqm_name): current=`C0950313`
- **ivy** / `cui` (no_token_overlap_with_iqm_name): current=`C0949841`
- **jambolan_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0330680`
- **japanese_honeysuckle** / `cui` (no_token_overlap_with_iqm_name): current=`C0949893`
- **japanese_knotweed** / `cui` (no_token_overlap_with_iqm_name): current=`C0331260`
- **java_tea** / `cui` (no_token_overlap_with_iqm_name): current=`C0950018`
- **jiaogulan_leaf** / `cui` (cui_not_found_in_umls): current=`C0949828`
- **jujube** / `cui` (no_token_overlap_with_iqm_name): current=`C0949612`
- **juniper** / `cui` (no_token_overlap_with_iqm_name): current=`C0022563`
- **kelp_powder** / `cui` (no_token_overlap_with_iqm_name): current=`C0022628`
- **kola_nut** / `cui` (no_token_overlap_with_iqm_name): current=`C0022651`
- **lavender** / `cui` (no_token_overlap_with_iqm_name): current=`C0023082`
- **lemon** / `cui` (no_token_overlap_with_iqm_name): current=`C0023053`
- **lemon_balm_leaf** / `cui` (cui_not_found_in_umls): current=`C0025083`
- **lemongrass** / `cui` (no_token_overlap_with_iqm_name): current=`C0330621`
- **licorice_root** / `cui` (resolved_to_disease_or_syndrome): current=`C0023351`
- **ligustrum** / `cui` (no_token_overlap_with_iqm_name): current=`C0949889`
- **lime** / `cui` (resolved_to_disease_or_syndrome): current=`C0023529`
- **linden** / `cui` (cui_not_found_in_umls): current=`C0040232`
- **lingonberry** / `cui` (no_token_overlap_with_iqm_name): current=`C0330749`
- **lions_mane_mushroom_powder** / `cui` (no_token_overlap_with_iqm_name): current=`C0949842`
- **long_pepper** / `cui` (no_token_overlap_with_iqm_name): current=`C0330582`
- **maca_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949879`
- **mace** / `cui` (no_token_overlap_with_iqm_name): current=`C0280578`
- **maitake** / `cui` (no_token_overlap_with_iqm_name): current=`C0949824`
- **mango** / `cui` (no_token_overlap_with_iqm_name): current=`C0024778`
- **mango_leaf_extract** / `cui` (no_token_overlap_with_iqm_name): current=`C0024778`
- **mangosteen** / `cui` (resolved_to_disease_or_syndrome): current=`C0024793`
- **marigold** / `cui` (cui_not_found_in_umls): current=`C0938046`
- **marshmallow_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0024866`
- **meadowsweet_herb** / `cui` (no_token_overlap_with_iqm_name): current=`C0949788`
- **milk_thistle** / `cui` (no_token_overlap_with_iqm_name): current=`C0037144`
- **milk_thistle_seed** / `cui` (no_token_overlap_with_iqm_name): current=`C0037144`
- **moringa_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0330514`
- **motherwort_herb** / `cui` (cui_not_found_in_umls): current=`C0023111`
- **mucuna_pruriens** / `cui` (no_token_overlap_with_iqm_name): current=`C0330541`
- **mugwort** / `cui` (no_token_overlap_with_iqm_name): current=`C0003764`
- **mullein** / `cui` (no_token_overlap_with_iqm_name): current=`C0042658`
- **myrrh_resin** / `cui` (cui_not_found_in_umls): current=`C0027171`
- **myrrh_resin_extract** / `cui` (cui_not_found_in_umls): current=`C0027171`
- **nettle_leaf** / `cui` (cui_not_found_in_umls): current=`C0028402`
- **nettle_root** / `cui` (cui_not_found_in_umls): current=`C0028402`
- **nigella** / `cui` (no_token_overlap_with_iqm_name): current=`C0950001`
- **noni** / `cui` (no_token_overlap_with_iqm_name): current=`C0330544`
- **oat_bran** / `cui` (cui_not_found_in_umls): current=`C0004756`
- **oat_generic** / `cui` (cui_not_found_in_umls): current=`C0004756`
- **oat_straw** / `cui` (cui_not_found_in_umls): current=`C0004756`
- **olive_leaf_powder** / `cui` (no_token_overlap_with_iqm_name): current=`C0028791`
- **orange** / `cui` (no_token_overlap_with_iqm_name): current=`C0028765`
- **oregano_herb** / `cui` (cui_not_found_in_umls): current=`C0028780`
- **oregon_grape** / `cui` (no_token_overlap_with_iqm_name): current=`C0949897`
- **paeonia_lactiflora** / `cui` (no_token_overlap_with_iqm_name): current=`C0950031`
- **papaya_fruit_powder** / `cui` (cui_not_found_in_umls): current=`C0030513`
- **parsley** / `cui` (no_token_overlap_with_iqm_name): current=`C0030697`
- **parsnip** / `cui` (no_token_overlap_with_iqm_name): current=`C0030667`
- **passion_flower** / `cui` (resolved_to_disease_or_syndrome): current=`C0030524`
- **passionflower_herb** / `cui` (resolved_to_disease_or_syndrome): current=`C0030524`
- **pau_darco_bark** / `cui` (no_token_overlap_with_iqm_name): current=`C0949831`
- **pea** / `cui` (no_token_overlap_with_iqm_name): current=`C0030821`
- **peach** / `cui` (cui_not_found_in_umls): current=`C0030792`
- **pear** / `cui` (cui_not_found_in_umls): current=`C0030836`
- **peony** / `cui` (no_token_overlap_with_iqm_name): current=`C0950031`
- **peppermint** / `cui` (cui_not_found_in_umls): current=`C0025757`
- **peppermint_leaf** / `cui` (cui_not_found_in_umls): current=`C0025757`
- **perilla_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0950041`
- **phellodendron_bark** / `cui` (no_token_overlap_with_iqm_name): current=`C0950042`
- **picrorhiza_kurroa** / `cui` (no_token_overlap_with_iqm_name): current=`C0950050`
- **picrorhiza_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0950050`
- **plantain** / `cui` (no_token_overlap_with_iqm_name): current=`C0032173`
- **plum** / `cui` (cui_not_found_in_umls): current=`C0032223`
- **polypodium_vulgare** / `cui` (no_token_overlap_with_iqm_name): current=`C0032276`
- **pomegranate** / `cui` (resolved_to_disease_or_syndrome): current=`C0032230`
- **poria_cocos** / `cui` (no_token_overlap_with_iqm_name): current=`C0949607`
- **prickly_ash** / `cui` (no_token_overlap_with_iqm_name): current=`C0949611`
- **prune** / `cui` (cui_not_found_in_umls): current=`C0032223`
- **psyllium_husk** / `cui` (no_token_overlap_with_iqm_name): current=`C0033068`
- **pumpkin** / `cui` (cui_not_found_in_umls): current=`C0032880`
- **quassia** / `cui` (no_token_overlap_with_iqm_name): current=`C0949614`
- **radish** / `cui` (cui_not_found_in_umls): current=`C0034275`
- **raspberry_seed** / `cui` (cui_not_found_in_umls): current=`C0034310`
- **rauwolfia_vomitoria** / `cui` (no_token_overlap_with_iqm_name): current=`C0034551`
- **red_clover** / `cui` (cui_not_found_in_umls): current=`C0040718`
- **red_clover_flower** / `cui` (cui_not_found_in_umls): current=`C0040718`
- **red_raspberry_fruit** / `cui` (cui_not_found_in_umls): current=`C0034310`
- **red_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949669`
- **reishi_mushroom** / `cui` (no_token_overlap_with_iqm_name): current=`C0017644`
- **rhodiola_rosea_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949608`
- **rhubarb** / `cui` (resolved_to_disease_or_syndrome): current=`C0035436`
- **rose_hips** / `cui` (cui_not_found_in_umls): current=`C0035738`
- **rue** / `cui` (cui_not_found_in_umls): current=`C0035944`
- **sage_leaf_extract** / `cui` (no_token_overlap_with_iqm_name): current=`C0036100`
- **saw_palmetto_berry** / `cui` (no_token_overlap_with_iqm_name): current=`C0036524`
- **schisandra_berry** / `cui` (no_token_overlap_with_iqm_name): current=`C0036728`
- **schizonepeta** / `cui` (no_token_overlap_with_iqm_name): current=`C0949609`
- **sea_buckthorn** / `cui` (no_token_overlap_with_iqm_name): current=`C0950378`
- **shatavari_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949556`
- **sheep_sorrel** / `cui` (no_token_overlap_with_iqm_name): current=`C0035943`
- **shiitake_mushroom** / `cui` (cui_not_found_in_umls): current=`C0023144`
- **sichuan_lovage** / `cui` (no_token_overlap_with_iqm_name): current=`C0949890`
- **skullcap** / `cui` (no_token_overlap_with_iqm_name): current=`C0036763`
- **solomons_seal_root** / `cui` (resolved_to_disease_or_syndrome): current=`C0032286`
- **spirulina_powder** / `cui` (cui_not_found_in_umls): current=`C0037123`
- **squaw_vine** / `cui` (no_token_overlap_with_iqm_name): current=`C0949983`
- **st_john_s_wort** / `cui` (no_token_overlap_with_iqm_name): current=`C0020027`
- **star_anise** / `cui` (resolved_to_disease_or_syndrome): current=`C0038017`
- **stoneroot** / `cui` (no_token_overlap_with_iqm_name): current=`C0949706`
- **strawberry** / `cui` (resolved_to_disease_or_syndrome): current=`C0038218`
- **sweet_potato** / `cui` (no_token_overlap_with_iqm_name): current=`C0038432`
- **sweet_wormwood_herb** / `cui` (no_token_overlap_with_iqm_name): current=`C0003763`
- **sweet_wormwood_leaf_oil** / `cui` (no_token_overlap_with_iqm_name): current=`C0003763`
- **tamarind** / `cui` (cui_not_found_in_umls): current=`C0965568`
- **tangerine** / `cui` (cui_not_found_in_umls): current=`C0039439`
- **tart_cherry_fruit** / `cui` (cui_not_found_in_umls): current=`C0330504`
- **tea_tree** / `cui` (resolved_to_disease_or_syndrome): current=`C0032087`
- **thyme** / `cui` (cui_not_found_in_umls): current=`C0040081`
- **tomato** / `cui` (no_token_overlap_with_iqm_name): current=`C0040228`
- **tongkat_ali** / `cui` (no_token_overlap_with_iqm_name): current=`C0949773`
- **toothed_clubmoss** / `cui` (no_token_overlap_with_iqm_name): current=`C0949851`
- **tree_peony_root_bark** / `cui` (no_token_overlap_with_iqm_name): current=`C0950035`
- **tribulus_terrestris** / `cui` (resolved_to_disease_or_syndrome): current=`C0040820`
- **turkey_rhubarb_root** / `cui` (resolved_to_disease_or_syndrome): current=`C0035436`
- **turmeric** / `cui` (no_token_overlap_with_iqm_name): current=`C0041070`
- **turmeric_root_powder** / `cui` (no_token_overlap_with_iqm_name): current=`C0041070`
- **tylophora_leaf** / `cui` (cui_not_found_in_umls): current=`C0041148`
- **uva_ursi** / `cui` (no_token_overlap_with_iqm_name): current=`C0003755`
- **uva_ursi_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0003755`
- **valerian_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0042305`
- **vitex** / `cui` (no_token_overlap_with_iqm_name): current=`C0042640`
- **watercress_herb** / `cui` (no_token_overlap_with_iqm_name): current=`C0043088`
- **watermelon** / `cui` (no_token_overlap_with_iqm_name): current=`C0043159`
- **wheat_germ** / `cui` (cui_not_found_in_umls): current=`C0043178`
- **wheatgrass_powder** / `cui` (cui_not_found_in_umls): current=`C0043178`
- **white_grape** / `cui` (no_token_overlap_with_iqm_name): current=`C0018208`
- **white_oak** / `cui` (no_token_overlap_with_iqm_name): current=`C0034499`
- **white_willow_bark** / `cui` (resolved_to_disease_or_syndrome): current=`C0036093`
- **wild_indigo_root** / `cui` (no_token_overlap_with_iqm_name): current=`C0949560`
- **wild_lettuce** / `cui` (no_token_overlap_with_iqm_name): current=`C0949875`
- **wild_yam_root** / `cui` (cui_not_found_in_umls): current=`C0012165`
- **winged_treebine** / `cui` (cui_not_found_in_umls): current=`C0949693`
- **wintergreen_leaf** / `cui` (cui_not_found_in_umls): current=`C0017062`
- **witch_hazel_leaf** / `cui` (cui_not_found_in_umls): current=`C0018545`
- **woad** / `cui` (no_token_overlap_with_iqm_name): current=`C0949868`
- **wood_betony** / `cui` (no_token_overlap_with_iqm_name): current=`C0949619`
- **wormwood_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0003762`
- **yarrow_aerial_parts** / `cui` (cui_not_found_in_umls): current=`C0000479`
- **yellow_dock_root** / `cui` (cui_not_found_in_umls): current=`C0035944`
- **yerba_mate_leaf** / `cui` (no_token_overlap_with_iqm_name): current=`C0024949`
- **yucca** / `cui` (no_token_overlap_with_iqm_name): current=`C0043408`
- **zhu_ling** / `cui` (no_token_overlap_with_iqm_name): current=`C0949605`

## Outputs

- `findings.jsonl` — every non-clean finding, one JSON per line, sorted seed→severity→canonical_id
- `queue.csv` — high-severity findings (incl. seeds) ready for clinician review
- `per_parent/<canonical_id>.json` — full audit record per IQM parent with `iqm_snapshot_sha256`
- `_cache/` — raw authority API response snapshots (UMLS / PubChem / GSRS / RxNav)

## Next step

Clinician walks `queue.csv` and authorizes corrections per row. This sweep writes nothing to `scripts/data/`. The follow-up workflow per spec §'Do NOT auto-fix' takes one finding at a time with a failing-test-first guard.
