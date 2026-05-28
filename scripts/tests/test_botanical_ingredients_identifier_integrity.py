"""Per-entry identifier integrity tests for botanical_ingredients.json.

Pattern mirrors the IQM / banned_recalled / harmful_additives /
other_ingredients integrity tests: one assertion per Wave 9.F correction,
content-verified against live UMLS / RxNav / FDA GSRS / PubChem before the
entry is written.

Wave 9.F.2 — Retired-CUI propagation. A cluster of stored CUIs in
botanical_ingredients.json no longer resolve in live UMLS (retired/merged
concepts). The correct, currently-resolving concept already existed in the
sibling standardized_botanicals.json (locked by
test_standardized_botanicals_cui_remediation.py) but was never propagated to
the botanical_ingredients.json copy when the MO move-out batches ran. Each
replacement below was confirmed live on 2026-05-28: the old CUI returns
NOT FOUND from the UMLS /CUI/<id> endpoint, and the new CUI resolves to the
correct botanical concept (semantic type Plant or extract-substance).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_PATH = REPO_ROOT / "scripts" / "data" / "botanical_ingredients.json"


@pytest.fixture(scope="module")
def botanicals() -> list[dict]:
    payload = json.loads(BOT_PATH.read_text())
    return payload["botanical_ingredients"]


def _find(entries: list[dict], entry_id: str) -> dict:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    raise AssertionError(f"botanical_ingredients.json missing {entry_id}")


# --------------------------------------------------------------------------- #
# Wave 9.F.2 — Retired CUI → verified resolving concept (11 entries)
# --------------------------------------------------------------------------- #
#
# (entry_id, retired_cui, correct_cui, umls_name)
_WAVE_9F2_RETIRED_CUI = [
    ("echinacea_angustifolia", "C0013479", "C0697080", "Echinacea angustifolia (Plant)"),
    ("eucalyptus", "C0015143", "C0015148", "Eucalyptus (Plant)"),
    ("feverfew", "C0015636", "C0697198", "Tanacetum parthenium (Plant)"),
    ("ginger_extract", "C0017149", "C1879327", "Zingiber officinale (Plant)"),
    ("goldenseal", "C0330520", "C3500453", "Hydrastis canadensis whole preparation"),
    ("gotu_kola", "C0007037", "C2948088", "Centella asiatica extract"),
    ("gynostemma", "C0949828", "C0950016", "Gynostemma pentaphyllum (Plant)"),
    ("marigold", "C0938046", "C1000850", "Tagetes erecta (Plant)"),
    ("peppermint", "C0025757", "C0697157", "Mentha piperita (Plant)"),
    ("red_clover", "C0040718", "C0330783", "Trifolium pratense (Plant)"),
    ("thyme", "C0040081", "C0697238", "Thymus vulgaris (Plant)"),
    # Sibling plant-part / oil entries that carried the SAME retired CUI as
    # their parent species entry above. Each fixed to the matching verified
    # concept (leaf/root/flower → species Plant CUI; the globulus oil entry
    # → its own species concept C1005038).
    ("eucalyptus_leaf_oil", "C0015143", "C1005038", "Eucalyptus globulus (Plant)"),
    ("ginger_root", "C0017149", "C1879327", "Zingiber officinale (Plant)"),
    ("jiaogulan_leaf", "C0949828", "C0950016", "Gynostemma pentaphyllum (Plant)"),
    ("peppermint_leaf", "C0025757", "C0697157", "Mentha piperita (Plant)"),
    ("red_clover_flower", "C0040718", "C0330783", "Trifolium pratense (Plant)"),
]


@pytest.mark.parametrize("entry_id,retired_cui,correct_cui,umls_name", _WAVE_9F2_RETIRED_CUI)
def test_wave_9f2_retired_cui_replaced(
    botanicals, entry_id, retired_cui, correct_cui, umls_name
):
    """The retired CUI (UMLS /CUI/<id> → NOT FOUND on 2026-05-28) is replaced
    with the currently-resolving concept that already exists in
    standardized_botanicals.json for the same botanical."""
    e = _find(botanicals, entry_id)
    assert e.get("cui") == correct_cui, (
        f"{entry_id}.cui must be {correct_cui} (UMLS '{umls_name}'), not the "
        f"retired {retired_cui} which no longer resolves in UMLS."
    )


# --------------------------------------------------------------------------- #
# Wave 9.F.3 - Corrupt-CUI re-resolution via live UMLS exact-name match (286)
# --------------------------------------------------------------------------- #
#
# The 9.F.1 sweep found roughly half of botanical CUIs were corrupt: dead
# (retired) or resolving to entirely unrelated concepts (e.g. beet_root ->
# "barium", apricot -> "Apotransketolase", amla_fruit -> "Feline Sarcoma
# Virus"). Each entry below was re-resolved by botanical_cui_resolver.py, which
# performs a live UMLS exact-name search on the entry's own latin_name (species
# binomial) and accepts ONLY a concept whose normalized name exactly matches
# that Latin name (or the common standard_name) AND carries a Plant / Fungus /
# Alga / Eukaryote / substance semantic type. The CUI is therefore whatever
# UMLS authoritatively returns for the exact species name - no hallucination.
# 264 replace a wrong/dead CUI; 22 backfill a previously-null CUI.
#
# (entry_id, correct_cui, umls_name)
_WAVE_9F3_RERESOLVED_CUI = [
    ('acerola_cherry', 'C1072665', 'Malpighia emarginata'),
    ('adzuki_bean', 'C0996863', 'Vigna angularis'),
    ('african_geranium', 'C3779996', 'Pelargonium sidoides'),
    ('amaranth_grain', 'C0330370', 'Amaranthus'),
    ('amla_fruit', 'C2365082', 'PHYLLANTHUS EMBLICA'),
    ('angelica_archangelica', 'C0877891', 'Angelica archangelica'),
    ('angelica_gigas', 'C1086570', 'Angelica gigas'),
    ('apocynum_venetum_leaf', 'C1930159', 'Apocynum venetum'),
    ('apricot', 'C0949825', 'Prunus armeniaca'),
    ('asparagus', 'C0946575', 'Asparagus officinalis'),
    ('astragalus_root', 'C5848530', 'Astragalus membranaceus'),
    ('atractylodes', 'C1500734', 'Atractylodes macrocephala'),
    ('bacopa', 'C1653429', 'Bacopa monnieri'),
    ('barberry_root', 'C1631178', 'Berberis vulgaris'),
    ('beet_root', 'C0330391', 'Beta vulgaris'),
    ('beetroot', 'C0330391', 'Beta vulgaris'),
    ('belleric_myrobalan', 'C1193060', 'Terminalia bellirica'),
    ('betel_leaf', 'C1000595', 'Piper betle'),
    ('bilberry_fruit', 'C0795673', 'Vaccinium myrtillus'),
    ('bitter_melon_fruit', 'C0330482', 'Momordica charantia'),
    ('black_bean', 'C1510487', 'Phaseolus vulgaris'),
    ('black_cherry', 'C0330655', 'Prunus serotina'),
    ('black_garlic', 'C0017102', 'Allium sativum'),
    ('black_ginger', 'C1044695', 'Kaempferia parviflora'),
    ('black_pepper', 'C0453397', 'Piper nigrum'),
    ('black_raspberry', 'C1031004', 'Rubus occidentalis'),
    ('blackcurrant', 'C1033165', 'Ribes nigrum'),
    ('blue_cohosh', 'C0330273', 'Caulophyllum thalictroides'),
    ('blue_flag_root', 'C0331689', 'Iris versicolor'),
    ('blue_vervain', 'C2617660', 'Verbena hastata'),
    ('blueberry_fruit', 'C1027331', 'Vaccinium corymbosum'),
    ('boldo_leaf', 'C1024397', 'Peumus boldus'),
    ('boneset_herb', 'C0331332', 'Eupatorium perfoliatum'),
    ('boswellia_serrata_resin', 'C2608032', 'Boswellia serrata'),
    ('broccoli_sprout', 'C5703430', 'Brassica oleracea var. italica'),
    ('buchu_leaf', 'C5124405', 'Agathosma betulina'),
    ('buckthorn_bark', 'C0330640', 'Rhamnus cathartica'),
    ('buckwheat_seed', 'C1304558', 'Fagopyrum esculentum'),
    ('bupleurum_root', 'C1016673', 'Bupleurum chinense'),
    ('burdock_root_powder', 'C0996995', 'Arctium lappa'),
    ('butchers_broom_root', 'C1021283', 'Ruscus aculeatus'),
    ('california_poppy', 'C0995189', 'Eschscholzia californica'),
    ('caralluma', 'C1058113', 'Caralluma'),
    ('cardamom', 'C0453247', 'Elettaria cardamomum'),
    ('carob', 'C1001098', 'Ceratonia siliqua'),
    ('carrot', 'C0242773', 'Daucus carota'),
    ('carrot_seed_oil', 'C0242773', 'Daucus carota'),
    ('cassava', 'C0007335', 'Manihot esculenta'),
    ('catnip_leaf', 'C1135185', 'Nepeta cataria'),
    ('cayenne_pepper', 'C0522463', 'Capsicum annuum'),
    ('celandine', 'C0330281', 'Chelidonium majus'),
    ('celastrus_paniculatus', 'C3132145', 'Celastrus paniculatus'),
    ('celery_seed', 'C0446301', 'Apium graveolens'),
    ('ceylon_cinnamon', 'C0008802', 'Cinnamomum verum'),
    ('chaga_mushroom_powder', 'C1079248', 'Inonotus obliquus'),
    ('chanca_piedra', 'C1688110', 'Phyllanthus niruri'),
    ('chaste_tree', 'C0752339', 'Vitex agnus-castus'),
    ('chebulic_myrobalan', 'C1193061', 'Terminalia chebula'),
    ('chia_seed', 'C1014490', 'Salvia hispanica'),
    ('chickweed_herb', 'C0697228', 'Stellaria media'),
    ('chicory_root', 'C1145671', 'Cichorium intybus'),
    ('chili_pepper', 'C0522463', 'Capsicum annuum'),
    ('chinese_dodder_seed', 'C1475832', 'Cuscuta chinensis'),
    ('chinese_licorice', 'C0936179', 'Glycyrrhiza uralensis'),
    ('chlorella_powder', 'C0996438', 'Chlorella vulgaris'),
    ('cilantro', 'C0946611', 'Coriandrum sativum'),
    ('cinnamon_bark', 'C1057194', 'Cinnamomum cassia'),
    ('cleavers_herb', 'C1002845', 'Galium aparine'),
    ('cloves', 'C1658087', 'Syzygium aromaticum'),
    ('cnidium', 'C1042483', 'Cnidium monnieri'),
    ('codonopsis', 'C1038274', 'Codonopsis pilosula'),
    ('coleus_forskohlii_root', 'C1382883', 'Coleus forskohlii'),
    ('coptis_rhizome', 'C1883784', 'Coptis chinensis'),
    ('cordyceps', 'C0319852', 'Cordyceps militaris'),
    ('cordyceps_mushroom_powder', 'C0319852', 'Cordyceps militaris'),
    ('coriander', 'C0946611', 'Coriandrum sativum'),
    ('couch_grass', 'C1016475', 'Elymus repens'),
    ('cowslip', 'C1253907', 'Primula veris'),
    ('cramp_bark', 'C1037325', 'Viburnum opulus'),
    ('cranberry', 'C0969740', 'Vaccinium macrocarpon'),
    ('cranberry_fruit', 'C0969740', 'Vaccinium macrocarpon'),
    ('cranesbill', 'C0330887', 'Geranium maculatum'),
    ('cumin_seed', 'C0949872', 'Cuminum cyminum'),
    ('curry_leaf', 'C1095616', 'Murraya koenigii'),
    ('cutch_tree', 'C1135823', 'Acacia catechu'),
    ('cyperus', 'C2310499', 'Cyperus rotundus'),
    ('dandelion', 'C0877851', 'Taraxacum officinale'),
    ('dandelion_root', 'C0877851', 'Taraxacum officinale'),
    ('danshen', 'C0696940', 'Salvia miltiorrhiza'),
    ('dark_sweet_cherry', 'C0946748', 'Prunus avium'),
    ('date', 'C0599067', 'Phoenix dactylifera'),
    ('devils_claw_tuber', 'C1109161', 'Harpagophytum procumbens'),
    ('dgl_deglycyrrhizinated_licorice', 'C0697105', 'Glycyrrhiza glabra'),
    ('dill_weed', 'C1457892', 'Anethum graveolens'),
    ('dong_quai', 'C0950081', 'Angelica sinensis'),
    ('echinacea_purpurea_aerial', 'C0886513', 'Echinacea purpurea'),
    ('echinacea_purpurea_herb', 'C0886513', 'Echinacea purpurea'),
    ('echinacea_purpurea_root_extract', 'C0886513', 'Echinacea purpurea'),
    ('ecklonia_radiata', 'C1681373', 'Ecklonia radiata'),
    ('elder_blossom', 'C0331059', 'Sambucus nigra'),
    ('elderberries', 'C0331059', 'Sambucus nigra'),
    ('eleuthero_stem', 'C1035215', 'Eleutherococcus senticosus (plant)'),
    ('european_ash_seed_fruit', 'C1007824', 'Fraxinus excelsior'),
    ('evening_primrose_seed_oil', 'C0996876', 'Oenothera biennis'),
    ('eyebright', 'C1656361', 'Euphrasia officinalis'),
    ('false_unicorn', 'C1053429', 'Chamaelirium luteum'),
    ('fenugreek_seed', 'C0060207', 'Trigonella foenum-graecum'),
    ('fig', 'C0946644', 'Ficus carica'),
    ('forsythia_suspensa', 'C1060911', 'Forsythia suspensa'),
    ('frangula_bark', 'C0330641', 'Rhamnus frangula'),
    ('fringe_tree', 'C1060867', 'Chionanthus virginicus'),
    ('galega_officinalis', 'C0950058', 'Galega officinalis'),
    ('garbanzo_bean', 'C0950051', 'Cicer arietinum'),
    ('gardenia', 'C1089114', 'Gardenia jasminoides'),
    ('garlic_bulb', 'C0017102', 'Allium sativum'),
    ('ginkgo_biloba_leaf', 'C0330206', 'Ginkgo biloba'),
    ('ginseng_root_panax', 'C0949314', 'Panax ginseng'),
    ('glehnia', 'C1083053', 'Glehnia littoralis'),
    ('globe_artichoke', 'C1021820', 'Cynara scolymus'),
    ('goats_rue', 'C0950058', 'Galega officinalis'),
    ('goji_berry', 'C1088997', 'Lycium barbarum'),
    ('goldenrod', 'C1441204', 'Solidago virgaurea'),
    ('grape', 'C0682492', 'Vitis vinifera'),
    ('grape_seed', 'C0682492', 'Vitis vinifera'),
    ('gravel_root', 'C1088095', 'Eutrochium purpureum'),
    ('graviola', 'C2723348', 'ANNONA MURICATA'),
    ('green_bell_pepper', 'C0522463', 'Capsicum annuum'),
    ('guava', 'C0553399', 'Psidium guajava'),
    ('guggul', 'C0949993', 'Commiphora wightii'),
    ('gymnema_sylvestre', 'C0996922', 'Gymnema sylvestre'),
    ('hawthorn_flowering_tops', 'C1068317', 'Crataegus monogyna'),
    ('hesperidin', 'C0019392', 'hesperidin'),
    ('holy_basil_leaf', 'C1483721', 'Ocimum tenuiflorum'),
    ('horny_goat_weed', 'C1474116', 'Epimedium brevicornu'),
    ('horse_chestnut_seed', 'C0331000', 'Aesculus hippocastanum'),
    ('horseradish', 'C1110641', 'Armoracia rusticana'),
    ('horsetail_aerial_parts', 'C0331746', 'Equisetum arvense'),
    ('hydrangea_root', 'C0330864', 'Hydrangea arborescens'),
    ('hyssop', 'C1008132', 'Hyssopus officinalis'),
    ('indian_kino_tree', 'C3381192', 'Pterocarpus marsupium'),
    ('indian_madder', 'C1258046', 'Rubia cordifolia'),
    ('indian_tinospora', 'C1501208', 'Tinospora cordifolia'),
    ('ivy', 'C0331030', 'Hedera helix'),
    ('jambolan_seed', 'C1504074', 'Syzygium cumini'),
    ('japanese_honeysuckle', 'C1049240', 'Lonicera japonica'),
    ('japanese_knotweed', 'C2314887', 'Japanese knotweed'),
    ('java_tea', 'C1497960', 'Orthosiphon stamineus'),
    ('jujube', 'C1647171', 'Ziziphus jujuba'),
    ('juniper', 'C0330155', 'Juniperus communis'),
    ('kelp_powder', 'C1017040', 'Ascophyllum nodosum'),
    ('king_trumpet', 'C0997569', 'Pleurotus eryngii'),
    ('kola_nut', 'C0678440', 'Cola nitida'),
    ('kombu', 'C0696815', 'Laminaria japonica'),
    ('laminaria_digitata', 'C1034152', 'Laminaria digitata'),
    ('lantana_camara', 'C0331282', 'Lantana camara'),
    ('lavandin', 'C3572835', 'Lavandula x intermedia'),
    ('lavender', 'C1623196', 'Lavandula angustifolia'),
    ('lemon', 'C0440283', 'Citrus limon'),
    ('lemon_balm_leaf', 'C1008143', 'Melissa officinalis'),
    ('lemongrass', 'C1167626', 'Cymbopogon citratus'),
    ('licorice_root', 'C0697105', 'Glycyrrhiza glabra'),
    ('ligustrum', 'C1258043', 'Ligustrum lucidum'),
    ('lime', 'C0946608', 'Citrus aurantiifolia (plant)'),
    ('linden', 'C2780181', 'Tilia x europaea'),
    ('lingonberry', 'C0950038', 'Vaccinium vitis-idaea'),
    ('lions_mane_mushroom_powder', 'C1041215', 'Hericium erinaceus'),
    ('long_pepper', 'C1014694', 'Piper longum'),
    ('mace', 'C0949745', 'Myristica fragrans'),
    ('maitake', 'C0319804', 'Grifola frondosa'),
    ('mango', 'C0330955', 'Mangifera indica'),
    ('mango_leaf_extract', 'C0330955', 'Mangifera indica'),
    ('mangosteen', 'C0950008', 'Garcinia mangostana'),
    ('marshmallow_root', 'C1070218', 'Althaea officinalis'),
    ('meadowsweet_herb', 'C1020462', 'Filipendula ulmaria'),
    ('milk_thistle', 'C0331428', 'Milk Thistle'),
    ('moringa_leaf', 'C0949952', 'Moringa oleifera'),
    ('motherwort_herb', 'C0697143', 'Leonurus cardiaca'),
    ('mucuna_pruriens', 'C1193630', 'Mucuna pruriens'),
    ('mugwort', 'C0524798', 'Artemisia vulgaris'),
    ('mullein', 'C1008177', 'Verbascum thapsus'),
    ('myrrh_resin', 'C1536360', 'Commiphora myrrha'),
    ('myrrh_resin_extract', 'C1536360', 'Commiphora myrrha'),
    ('navy_bean', 'C1510487', 'Phaseolus vulgaris'),
    ('nettle_leaf', 'C0600609', 'Urtica dioica'),
    ('nettle_root', 'C0600609', 'Urtica dioica'),
    ('nigella', 'C1140702', 'Nigella sativa'),
    ('noni', 'C1010822', 'Morinda citrifolia'),
    ('oat_bran', 'C1141017', 'Avena sativa'),
    ('oat_generic', 'C1141017', 'Avena sativa'),
    ('oat_straw', 'C1141017', 'Avena sativa'),
    ('olive_leaf_powder', 'C1122969', 'Olea europaea'),
    ('orange', 'C0522462', 'Citrus sinensis'),
    ('oregano_herb', 'C0946715', 'Origanum vulgare'),
    ('oregon_grape', 'C1138387', 'Mahonia aquifolium'),
    ('paeonia_lactiflora', 'C1005921', 'Paeonia lactiflora'),
    ('papaya_fruit_powder', 'C0453135', 'Carica papaya'),
    ('parsley', 'C0446307', 'Petroselinum crispum'),
    ('parsnip', 'C1260949', 'Pastinaca sativa'),
    ('passion_flower', 'C0697176', 'Passiflora incarnata'),
    ('passionflower_herb', 'C0697176', 'Passiflora incarnata'),
    ('pau_darco_bark', 'C2276328', 'Handroanthus impetiginosus'),
    ('pea', 'C1262903', 'Pisum sativum'),
    ('peach', 'C0330659', 'Prunus persica'),
    ('pear', 'C0330664', 'Pyrus communis'),
    ('peony', 'C1005921', 'Paeonia lactiflora'),
    ('perilla_leaf', 'C0331304', 'Perilla frutescens'),
    ('phellodendron_bark', 'C1027031', 'Phellodendron amurense'),
    ('plantain', 'C0032094', 'Plantago major'),
    ('plum', 'C0330660', 'Prunus domestica'),
    ('polypodium_vulgare', 'C1020561', 'Polypodium vulgare'),
    ('pomegranate', 'C1001173', 'Punica granatum'),
    ('poria_cocos', 'C1034610', 'Wolfiporia extensa'),
    ('prickly_ash', 'C1907725', 'Zanthoxylum americanum'),
    ('prune', 'C0330660', 'Prunus domestica'),
    ('psyllium_husk', 'C1209192', 'Plantago ovata'),
    ('pumpkin', 'C0487824', 'Cucurbita pepo'),
    ('quassia', 'C1010968', 'Quassia amara'),
    ('quinoa', 'C0453354', 'Chenopodium quinoa'),
    ('radish', 'C0996771', 'Raphanus sativus'),
    ('raspberry_seed', 'C1004027', 'Rubus idaeus'),
    ('rauwolfia_vomitoria', 'C2271732', 'Rauvolfia vomitoria'),
    ('red_raspberry_fruit', 'C1004027', 'Rubus idaeus'),
    ('red_root', 'C1018254', 'Ceanothus americanus'),
    ('reishi_mushroom', 'C0752326', 'Reishi mushroom'),
    ('rhodiola_rosea_root', 'C0950014', 'Rhodiola rosea'),
    ('rhubarb', 'C1090801', 'Rheum palmatum'),
    ('rose_hips', 'C1030673', 'Rosa canina'),
    ('rue', 'C0330929', 'Ruta graveolens'),
    ('russian_tarragon', 'C0453266', 'Artemisia dracunculus'),
    ('saccharina_latissima', 'C1645239', 'Saccharina latissima'),
    ('sacha_inchi', 'C1640937', 'Plukenetia volubilis'),
    ('sage_leaf_extract', 'C0453265', 'Salvia officinalis'),
    ('schisandra_berry', 'C0696946', 'Schisandra chinensis'),
    ('schizonepeta', 'C1065232', 'Schizonepeta tenuifolia'),
    ('sea_buckthorn', 'C1215783', 'Hippophae rhamnoides'),
    ('shatavari_root', 'C1672151', 'Asparagus racemosus'),
    ('sheep_sorrel', 'C0947421', 'Rumex acetosella'),
    ('shiitake_mushroom', 'C0752328', 'Lentinula edodes'),
    ('sichuan_lovage', 'C1014724', 'Ligusticum chuanxiong'),
    ('skullcap', 'C1466210', 'Scutellaria lateriflora (plant)'),
    ('solomons_seal_root', 'C1011932', 'Polygonatum multiflorum'),
    ('spirulina_powder', 'C1188555', 'Arthrospira platensis'),
    ('squaw_vine', 'C1011812', 'Mitchella repens'),
    ('st_john_s_wort', 'C0936242', 'Hypericum perforatum'),
    ('star_anise', 'C0949939', 'Star Anise'),
    ('stoneroot', 'C0697062', 'Collinsonia canadensis'),
    ('strawberry', 'C1138844', 'Fragaria x ananassa'),
    ('sweet_clover', 'C0065919', 'Melilotus officinalis'),
    ('sweet_orange', 'C0522462', 'Citrus sinensis'),
    ('sweet_potato', 'C0331252', 'Ipomoea batatas'),
    ('sweet_wormwood_herb', 'C0686899', 'Artemisia annua'),
    ('sweet_wormwood_leaf_oil', 'C0686899', 'Artemisia annua'),
    ('tangerine', 'C0884217', 'Citrus reticulata'),
    ('tart_cherry_fruit', 'C0330657', 'Prunus cerasus'),
    ('tea_tree', 'C1078317', 'Melaleuca alternifolia'),
    ('tongkat_ali', 'C1258070', 'Eurycoma longifolia'),
    ('tree_peony_root_bark', 'C1011804', 'Paeonia suffruticosa'),
    ('tribulus_terrestris', 'C0330899', 'Tribulus terrestris'),
    ('turkey_rhubarb_root', 'C1090801', 'Rheum palmatum'),
    ('turmeric', 'C0950101', 'Curcuma longa'),
    ('turmeric_root_powder', 'C0950101', 'Curcuma longa'),
    ('tylophora_leaf', 'C1024211', 'Tylophora indica'),
    ('uva_ursi', 'C4724782', 'Arctostaphylos uva-ursi'),
    ('uva_ursi_leaf', 'C4724782', 'Arctostaphylos uva-ursi'),
    ('valerian_root', 'C0993600', 'Valeriana officinalis'),
    ('vitex', 'C0752339', 'Vitex agnus-castus'),
    ('watermelon', 'C0946607', 'Citrullus lanatus'),
    ('wheat_germ', 'C1123020', 'Triticum aestivum'),
    ('wheatgrass_powder', 'C1123020', 'Triticum aestivum'),
    ('white_grape', 'C0682492', 'Vitis vinifera'),
    ('white_oak', 'C0487892', 'Quercus alba'),
    ('white_willow_bark', 'C1031389', 'Salix alba'),
    ('wild_indigo_root', 'C1014887', 'Baptisia tinctoria'),
    ('wild_lettuce', 'C1031540', 'Lactuca virosa'),
    ('wild_yam_root', 'C0697076', 'Dioscorea villosa'),
    ('winged_treebine', 'C1078516', 'Cissus quadrangularis'),
    ('wintergreen_leaf', 'C1075187', 'Gaultheria procumbens'),
    ('witch_hazel_leaf', 'C0697110', 'Hamamelis virginiana'),
    ('woad', 'C5958586', 'Isatis tinctoria'),
    ('wormwood_leaf', 'C0524796', 'Artemisia absinthium'),
    ('wrightia_tinctoria', 'C2785511', 'Wrightia tinctoria'),
    ('yarrow_aerial_parts', 'C1148469', 'Achillea millefolium'),
    ('yellow_dock_root', 'C1200905', 'Rumex crispus'),
    ('yucca', 'C1640544', 'Yucca schidigera'),
    ('zhu_ling', 'C1193742', 'Polyporus umbellatus'),
    ('zucchini', 'C0487824', 'Cucurbita pepo'),
]


@pytest.mark.parametrize("entry_id,correct_cui,umls_name", _WAVE_9F3_RERESOLVED_CUI)
def test_wave_9f3_corrupt_cui_reresolved(botanicals, entry_id, correct_cui, umls_name):
    """Each previously-corrupt or null CUI now holds the live-UMLS exact-match
    concept for the entry's own Latin binomial (verified 2026-05-28)."""
    e = _find(botanicals, entry_id)
    assert e.get("cui") == correct_cui, (
        f"{entry_id}.cui must be {correct_cui} (UMLS '{umls_name}', exact "
        f"Latin-name match)."
    )
