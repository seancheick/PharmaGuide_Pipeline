#!/usr/bin/env python3
"""Regression pins for verified other_ingredients CUI corrections."""

import json
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "other_ingredients.json"


def _rows_by_id() -> dict[str, dict]:
    rows = json.loads(DATA_PATH.read_text())["other_ingredients"]
    return {row["id"]: row for row in rows}


def test_verified_other_ingredients_chemistry_cuis():
    rows = _rows_by_id()

    assert rows["PII_AMMONIUM_HYDROXIDE"].get("cui") == "C0051719"
    assert rows["NHA_AMMONIUM_MOLYBDATE"].get("cui") == "C0051721"
    assert rows["OI_ANNATTO_EXTRACT"].get("cui") == "C0051928"
    assert rows["PII_ARABINOSE"].get("cui") == "C0003682"
    assert rows["PII_BEESWAX"].get("cui") == "C0004924"
    assert rows["OI_BISMUTH_CITRATE"].get("cui") == "C0106550"
    assert rows["NHA_CALCIUM_GLYCEROPHOSPHATE"].get("cui") == "C0006700"
    assert rows["NHA_CALCIUM_CASEINATE"].get("cui") == "C0301465"
    assert rows["OI_CALCIUM_D_GLUCARATE"].get("cui") == "C0006698"
    assert rows["NHA_CALCIUM_HYDROXIDE"].get("cui") == "C0006701"


def test_verified_other_ingredients_followup_cuis_and_decouplings():
    rows = _rows_by_id()

    assert rows["PII_BEE_POLLEN"].get("cui") == "C0795585"
    assert rows["NHA_CALCIUM_CAPRYLATE"].get("cui") == "C0892093"
    assert rows["PII_CARBOMER"].get("cui") == "C0770624"
    assert rows["PII_CYCLODEXTRIN"].get("cui") == "C0010558"
    assert rows["PII_DICALCIUM_PHOSPHATE"].get("cui") == "C0795598"

    cmc = rows["PII_CARBOXYMETHYL_CELLULOSE"]
    cmc_ext = cmc.get("external_ids") or {}
    assert cmc.get("cui") == "C0007068"
    assert cmc_ext.get("pubchem_cid") in (None, "")

    hydrolysate = rows["NHA_CASEIN_HYDROLYSATE"]
    hydrolysate_ext = hydrolysate.get("external_ids") or {}
    assert hydrolysate.get("cui") == "C0054845"
    assert hydrolysate_ext.get("unii") in (None, "")
    assert hydrolysate_ext.get("cas") in (None, "")
    assert hydrolysate_ext.get("pubchem_cid") in (None, "")
    assert hydrolysate.get("rxcui") in (None, "")
    assert hydrolysate.get("gsrs") is None


def test_verified_other_ingredients_exact_compound_cuis():
    rows = _rows_by_id()

    assert rows["OI_DIOSMIN"].get("cui") == "C0012498"
    assert rows["PII_DISODIUM_PHOSPHATE"].get("cui") == "C0772024"
    assert rows["NHA_ERYTHRODIOL"].get("cui") == "C0655327"
    assert rows["NHA_ETHYL_MALTOL"].get("cui") == "C0059773"
    assert rows["PII_ETHYL_OLEATE"].get("cui") == "C0059779"


def test_verified_other_ingredients_additional_exact_cuis():
    rows = _rows_by_id()

    assert rows["PII_FLAXSEED_OIL"].get("cui") == "C0023754"
    assert rows["PII_GALACTOMANNAN"].get("cui") == "C0060961"
    assert rows["PII_GUM_GHATTI"].get("cui") == "C0606577"


def test_verified_other_ingredients_egg_albumin_cui():
    rows = _rows_by_id()

    assert rows["NHA_EGG_ALBUMIN"].get("cui") == "C0981815"


def test_verified_other_ingredients_exact_batch_2026_03_25():
    rows = _rows_by_id()

    assert rows["OI_10_UNDECENOIC_ACID"].get("cui") == "C0041660"
    assert rows["PII_CROSCARMELLOSE"].get("cui") == "C0010353"
    assert rows["OI_DIMETHYLGLYCINE"].get("cui") == "C0058265"
    assert rows["NHA_DIOSMETIN"].get("cui") == "C0114217"
    assert rows["NHA_KAOLIN"].get("cui") == "C0022499"
    assert rows["NHA_L_ASPARAGINE"].get("cui") == "C0003995"
    assert rows["NHA_MAGNESIUM_STEARATE"].get("cui") == "C0126791"
    assert rows["NHA_MAGNESIUM_TRISILICATE"].get("cui") == "C0065533"
    assert rows["NHA_PHOSPHORIC_ACID"].get("cui") == "C0031700"
    assert rows["PII_TRIETHYL_CITRATE"].get("cui") == "C0609416"
    assert rows["PII_CORN_OIL"].get("cui") == "C0010029"
    assert rows["PII_GLYCEROL_MONOSTEARATE"].get("cui") == "C0061579"


def test_verified_other_ingredients_exact_batch_2_materials():
    """12-row exact CUI batch: discrete chemicals and materials with verified UMLS concepts."""
    rows = _rows_by_id()

    assert rows["NHA_ACACIA_GUM"].get("cui") == "C0018389"               # Gum Arabic
    assert rows["PII_CORN_STARCH"].get("cui") == "C1384515"              # corn starch
    assert rows["NHA_MICROCRYSTALLINE_CELLULOSE"].get("cui") == "C0669247"  # microcrystalline cellulose
    assert rows["NHA_SARCOSINE"].get("cui") == "C0036228"                # sarcosine
    assert rows["PII_SAFFLOWER_OIL"].get("cui") == "C0036048"            # safflower oil
    assert rows["PII_SUNFLOWER_OIL"].get("cui") == "C0075639"            # sunflower oil
    assert rows["NHA_PHLORIDZIN"].get("cui") == "C0031562"               # phlorhizin
    assert rows["PII_SHELLAC"].get("cui") == "C0074445"                  # shellac
    assert rows["PII_TARTARIC_ACID"].get("cui") == "C0075821"            # tartaric acid
    assert rows["NHA_CAFFEIC_ACID"].get("cui") == "C0054433"             # caffeic acid
    assert rows["PII_TAPIOCA_STARCH"].get("cui") == "C2726216"           # starch, tapioca
    assert rows["NHA_OLEAMIDE"].get("cui") == "C5886810"                 # oleamide


def test_verified_other_ingredients_decoupling_batch_1():
    """5-row decoupling batch: wrong external_ids cleaned, CUIs fixed, GSRS verified."""
    rows = _rows_by_id()

    # Xanthan Gum: CUI fix + CAS/CID decoupled (were xanthene, not xanthan gum)
    xg = rows["NHA_XANTHAN_GUM"]
    xg_ext = xg.get("external_ids") or {}
    assert xg.get("cui") == "C0078596"                   # xanthan gum (was C0078544 = WS 9659 B)
    assert xg_ext.get("unii") == "TTV12P4NEE"        # correct GSRS UNII
    assert xg_ext.get("cas") == "11138-66-2"          # correct CAS (was 92-83-1 = xanthene)
    assert xg_ext.get("pubchem_cid") in (None, "")    # cleared (PubChem has no xanthan gum)

    # Dextrin: CUI fix + GSRS decoupled (was DEXTRATES, not dextrin)
    dx = rows["PII_DEXTRIN"]
    dx_ext = dx.get("external_ids") or {}
    assert dx.get("cui") == "C0054527"                    # dextrin (was C0011529 = Deoxyribonucleotides)
    assert dx_ext.get("cas") == "9004-53-9"           # correct CAS, kept
    assert dx_ext.get("pubchem_cid") == 62698         # correct CID, kept
    dx_gsrs = dx.get("gsrs") or {}
    assert dx_gsrs.get("substance_name") != "DEXTRATES"  # old wrong GSRS cleared

    # Beta-Ecdysterone: CUI fix + GSRS filled from 20-hydroxyecdysone
    be = rows["NHA_BETA_ECDYSTERONE"]
    be_ext = be.get("external_ids") or {}
    assert be.get("cui") == "C0013495"                    # Ecdysterone (was C0013539 = Medicine, Eclectic)
    assert be_ext.get("cas") == "5289-74-7"           # correct CAS, kept
    assert be_ext.get("pubchem_cid") == 5459840       # correct CID, kept

    # Glycerin Fatty Acid Ester: full decoupling — mixture, no single identity
    gfae = rows["NHA_GLYCERIN_FATTY_ACID_ESTER"]
    gfae_ext = gfae.get("external_ids") or {}
    assert gfae.get("cui") is None                        # no single UMLS concept
    assert gfae_ext.get("unii") in (None, "")         # cleared (was isopropyl behenate)
    assert gfae.get("gsrs") is None                   # cleared (was isopropyl behenate)
    assert gfae.get("rxcui") in (None, "")            # cleared

    # Glyceryl Behenate: CUI fix, keep PubChem, no GSRS (copolymer mismatch)
    gb = rows["PII_GLYCERYL_BEHENATE"]
    assert gb.get("cui") == "C0253029"                    # glyceryl behenate (was C0525041)
    gb_ext = gb.get("external_ids") or {}
    assert gb_ext.get("cas") == "18641-57-1"          # correct CAS, kept
    assert gb_ext.get("pubchem_cid") == 62726         # correct CID, kept


def test_verified_other_ingredients_exact_batch_3_excipients():
    """12-row exact CUI batch: excipients, cellulose derivatives, flavonoids, enzymes."""
    rows = _rows_by_id()

    assert rows["PII_HYDROXYPROPYL_CELLULOSE"].get("cui") == "C4276010"     # hydroxypropyl cellulose
    assert rows["PII_HPMC"].get("cui") == "C0063242"                        # hypromellose
    assert rows["OI_IPRIFLAVONE"].get("cui") == "C0123903"                  # ipriflavone
    assert rows["NHA_ISOVITEXIN"].get("cui") == "C0628325"                  # isovitexin
    assert rows["NHA_L_ARABINOSE"].get("cui") == "C0003682"                 # Arabinose
    assert rows["NHA_PALATINOSE"].get("cui") == "C0064002"                  # isomaltulose
    assert rows["NHA_PAEONIFLORIN"].get("cui") == "C0070320"                # peoniflorin
    assert rows["PII_PEPSIN"].get("cui") == "C0030909"                      # pepsin A
    assert rows["NHA_PEPTONE"].get("cui") == "C0030966"                     # peptones
    assert rows["PII_MEDIUM_CHAIN_TRIGLYCERIDES"].get("cui") == "C0724624"  # MCT
    assert rows["PII_SODIUM_STARCH_GLYCOLATE"].get("cui") == "C0142927"     # sodium starch glycolate
    assert rows["NHA_SODIUM_CITRATE"].get("cui") == "C0142825"              # sodium citrate


def test_verified_other_ingredients_exact_batch_4_oils_starches_dyes():
    """12-row exact CUI batch: oils, starches, dyes, salts, flavonoids."""
    rows = _rows_by_id()

    assert rows["NHA_TRI_SODIUM_CITRATE"].get("cui") == "C0795671"         # trisodium citrate
    assert rows["NHA_SYRINGIC_ACID"].get("cui") == "C0075709"              # syringic acid
    assert rows["PII_LECITHIN_SOY"].get("cui") == "C0872912"               # soybean lecithin
    assert rows["PII_GLYCERYL_MONOOLEATE"].get("cui") == "C0066771"        # monoolein
    assert rows["NHA_MALATE_GENERIC"].get("cui") == "C0220873"             # malate
    assert rows["NHA_DIATOMACEOUS_EARTH"].get("cui") == "C0022683"         # diatomaceous earth
    assert rows["PII_EXTRA_VIRGIN_OLIVE_OIL"].get("cui") == "C0069449"     # olive oil
    assert rows["NHA_FDC_BLUE_1"].get("cui") == "C0772270"                 # brilliant blue FCF
    assert rows["NHA_FLAVANOLS"].get("cui") == "C2348678"                  # Flavanol
    assert rows["PII_RICE_FLOUR"].get("cui") == "C1509548"                 # Rice Flour
    assert rows["OI_WHEAT_BRAN"].get("cui") == "C0043138"                  # Wheat Bran
    assert rows["PII_WHEAT_STARCH"].get("cui") == "C0772389"               # starch, wheat


def test_verified_other_ingredients_exact_batch_5_botanicals_polymers():
    """12-row exact CUI batch: botanicals, polymers, starches, enzymes."""
    rows = _rows_by_id()

    assert rows["NHA_PVP"].get("cui") == "C0032856"                        # povidone
    assert rows["PII_POLYOXYL_CASTOR_OIL"].get("cui") == "C1509464"        # polyoxyl 40 castor oil
    assert rows["NHA_SODIUM_POTASSIUM_TARTRATE"].get("cui") == "C0770985"  # potassium sodium tartrate
    assert rows["NHA_STEVIA"].get("cui") == "C1018894"                     # Stevia rebaudiana
    assert rows["NHA_MONK_FRUIT"].get("cui") == "C0696858"                 # Siraitia grosvenorii
    assert rows["NHA_LEMON_BALM_EXTRACT"].get("cui") == "C1008143"         # Melissa officinalis
    assert rows["NHA_CHAMOMILE_EXTRACT"].get("cui") == "C0439963"          # chamomile extract
    assert rows["NHA_QUILLAJA_EXTRACT"].get("cui") == "C3489509"           # Quillaja Saponaria
    assert rows["NHA_VEG_MAGNESIUM_SILICATE"].get("cui") == "C0851342"     # magnesium silicate
    assert rows["OI_ARROWROOT"].get("cui") == "C0452676"                   # Arrowroot
    assert rows["PII_POTATO_STARCH"].get("cui") == "C0772411"              # potato starch
    assert rows["PII_TRIACETIN"].get("cui") == "C0040853"                  # triacetin


def test_verified_other_ingredients_exact_batch_6_invalid_cui_fixes():
    """12-row batch: INVALID_CUI entries replaced with verified UMLS concepts."""
    rows = _rows_by_id()

    assert rows["NHA_BLACK_STRAP_MOLASSES"].get("cui") == "C0458181"       # Blackstrap molasses
    assert rows["OI_CELLULOSE_GUM"].get("cui") == "C0037487"              # carboxymethylcellulose sodium
    assert rows["NHA_GAMMA_BUTYROBETAINE_HCL"].get("cui") == "C0061030"   # gamma-butyrobetaine
    assert rows["NHA_HYPROMELLOSE_PHTHALATE"].get("cui") == "C1453005"    # hypromellose phthalate
    assert rows["PII_INTRINSIC_FACTOR"].get("cui") == "C0021918"          # intrinsic factor
    assert rows["PII_MUCIN"].get("cui") == "C0026682"                     # mucins
    assert rows["PII_OXALOACETATE"].get("cui") == "C0600556"              # oxaloacetic acid
    assert rows["PII_POLYVINYL_ALCOHOL"].get("cui") == "C0032623"         # polyvinyl alcohol
    assert rows["PII_PROPOLIS"].get("cui") == "C0033488"                  # propolis
    assert rows["OI_PULLULAN"].get("cui") == "C0072595"                   # pullulan
    assert rows["PII_ROYAL_JELLY"].get("cui") == "C0073603"               # royal jelly
    assert rows["NHA_RUTAECARPINE"].get("cui") == "C0073716"              # rutecarpine


def test_verified_other_ingredients_final_batch_7_fixes_and_nulls():
    """Final batch: 12 CUI fixes + 6 null-outs for mixtures/classes with no single concept."""
    rows = _rows_by_id()

    # CUI fixes
    assert rows["NHA_SODIUM_ACID_SULFATE"].get("cui") == "C0392144"           # sodium bisulfate
    assert rows["PII_SODIUM_ALGINATE"].get("cui") == "C0142791"               # sodium alginate
    assert rows["PII_SODIUM_CARBOXYMETHYLCELLULOSE"].get("cui") == "C0037487" # CMC sodium
    assert rows["NHA_CHLOROPHYLLIN"].get("cui") == "C0055435"                 # chlorophyllin
    assert rows["NHA_THYROID_SUBSTANCE"].get("cui") == "C3163618"             # Thyroid Extract
    assert rows["OI_TOCOPHEROL_PRESERVATIVE"].get("cui") == "C3255108"        # tocopherol
    assert rows["NHA_WHITE_THYME_OIL"].get("cui") == "C0304119"              # thyme oil
    assert rows["NHA_YLANG_YLANG_OIL"].get("cui") == "C0439966"              # Cananga oil
    assert rows["OI_GALACTOSE"].get("cui") == "C0016945"                     # galactose
    assert rows["OI_HPMC_COMPOSITE"].get("cui") == "C0063242"                # hypromellose
    assert rows["PII_KOLLIDON"].get("cui") == "C0032856"                     # povidone
    assert rows["NHA_MONO_DIGLYCERIDES"].get("cui") == "C0026481"            # Monoglycerides

    # Null-outs (no single UMLS concept)
    assert rows["PII_BEEF_TISSUE"].get("cui") is None
    assert rows["NHA_CONJUGATED_BILE_ACID"].get("cui") is None
    assert rows["NHA_GLYCERIN_ESTERS"].get("cui") is None
    assert rows["PII_MICELLAR_CASEIN"].get("cui") is None
    assert rows["NHA_VEGETABLE_GLYCERIDES"].get("cui") is None
    assert rows["PII_XYLANASE"].get("cui") is None


def test_verified_other_ingredients_missing_cui_exact_fills():
    """27 MISSING_CUI entries filled with verified exact UMLS concepts."""
    rows = _rows_by_id()

    assert rows["OI_AND_AS_MAGNESIUM_CITRATE"].get("cui") == "C0126774"
    assert rows["PII_BETAINE_MONOHYDRATE"].get("cui") == "C0005304"
    assert rows["NHA_CAROTENE_NATURAL"].get("cui") == "C0053396"
    assert rows["PII_CLOVE_POWDER"].get("cui") == "C0009076"
    assert rows["PII_EXTRA_VIRGIN_COCONUT_OIL"].get("cui") == "C0056060"
    assert rows["NHA_GAMMA_GLUTAMYLCYSTEINES"].get("cui") == "C0061060"
    assert rows["PII_LECITHIN_OIL"].get("cui") == "C0031617"
    assert rows["NHA_LEMON_FLAVOR_OIL"].get("cui") == "C0304108"
    assert rows["PII_LYSINE_MONOHYDROCHLORIDE"].get("cui") == "C0024340"
    assert rows["PII_MEDIUM_CHAIN_FATTY_ACIDS"].get("cui") == "C0522094"
    assert rows["PII_OAT_OIL"].get("cui") == "C3255784"
    assert rows["OI_OMEGA3_TRIGLYCERIDES_CARRIER"].get("cui") == "C0354657"
    assert rows["NHA_RICE_WAX"].get("cui") == "C5448451"
    assert rows["NHA_SUMALATE"].get("cui") == "C2341740"
    assert rows["OI_CLA_OIL_INACTIVE"].get("cui") == "C0050156"
    assert rows["PII_SOYBEAN_OR_SAFFLOWER_OIL"].get("cui") == "C0037732"
    assert rows["OI_CORN_PROTEIN"].get("cui") == "C0043458"
    assert rows["PII_ETHYL_ACRYLATE_COPOLYMER"].get("cui") == "C4310562"
    assert rows["OI_BONE_MARROW_CONCENTRATE"].get("cui") == "C0005953"
    assert rows["PII_CURCUMA_OIL"].get("cui") == "C2954886"
    assert rows["NHA_COCONUT_GRANULATED"].get("cui") == "C1135796"
    assert rows["NHA_NATURAL_GRAPE_FLAVOR"].get("cui") == "C1365537"
    assert rows["NHA_LEMON_NATURAL"].get("cui") == "C0475657"
    assert rows["NHA_PEACH_NATURAL"].get("cui") == "C1337216"
    assert rows["OI_NATURAL_BERRY_FLAVOR"].get("cui") == "C0982158"
    assert rows["NHA_NATURAL_BERRY_FLAVORS"].get("cui") == "C0982158"
    assert rows["NHA_POLYGLYCERYL_ESTER"].get("cui") == "C0982350"


def test_verified_other_ingredients_missing_cui_null_outs():
    """29 MISSING_CUI entries confirmed as no-single-concept (null CUI)."""
    rows = _rows_by_id()

    null_ids = [
        "NHA_AGAVE_FIBER", "NHA_AVOCADO_SOY_UNSAPONIFIABLES", "OI_BEET_FIBER",
        "OI_BIO_ENHANCED", "PII_BONE_BROTH", "NHA_CORAL_MINERALS",
        "PII_DERMAVAL_BRANDED_BLEND", "PII_FORTIFY_OPTIMA_BRANDED_BLEND",
        "NHA_GKG", "NHA_MOBILEE", "PII_NATURAL_COLORING",
        "NHA_NATURAL_SWEETENER", "PII_PROTEIN_COATING",
        "PII_SPECTRA_BRANDED_BLEND", "PII_SPRING_WATER",
        "NHA_STRAWBERRY_PUREE", "NHA_SUCROSE_FATTY_ACID_ESTER",
        "NHA_SUNFLOWER_OIL_ESTERS", "OI_TOTAL_CULTURES",
        "NHA_UNIVESTIN", "PII_VEGETABLE_AND_FRUIT_JUICES",
        "OI_VITAMIN_PREMIX", "OI_WHOLE_ADRENAL", "OI_WHOLE_FOOD_BASE",
    ]
    for eid in null_ids:
        assert rows[eid].get("cui") is None, f"{eid} should have null CUI"


def test_verified_other_ingredients_gsrs_unii_fills():
    """4 UNII fills confirmed by CAS cross-validation against live GSRS.

    NHA_MALATE_GENERIC was previously pinned to UNII 817L1N4CKP (MALIC ACID)
    + CAS 6915-15-7, but Sprint 2-prep triage (2026-05-14, commit 3106050)
    governed-null'd both because 'Malate' as a generic descriptor is
    ambiguous between malate ions, calcium/magnesium/sodium/potassium
    malate salts, AND the acid form. FDA cache has no generic-malate UNII.
    Per docs/UNII_TRIAGE_2026_05_14.md and the pre-Sprint-1 blocker rule,
    tagging the generic descriptor with the acid-form's identifiers would
    mis-anchor every label-disclosed 'Malate' to malic acid once UNII-first
    matching ships. Specific malate compounds (NHA_MALIC_ACID for the acid,
    per-salt entries) keep their correct UNIIs.
    """
    rows = _rows_by_id()

    malate_ext = (rows["NHA_MALATE_GENERIC"].get("external_ids") or {})
    assert malate_ext.get("unii") is None, (
        "NHA_MALATE_GENERIC must NOT carry a UNII (governed_null per "
        "Sprint 2-prep triage). Generic 'Malate' is ambiguous between "
        "ion/salt/acid forms; specific malate compounds carry their own UNIIs."
    )
    assert malate_ext.get("cas") is None, (
        "NHA_MALATE_GENERIC must NOT carry CAS 6915-15-7 (L-malic acid). "
        "Generic descriptor — no single CAS applies."
    )
    assert rows["NHA_MALATE_GENERIC"].get("cui_status") == "governed_null"

    oaa_ext = (rows["PII_OXALOACETATE"].get("external_ids") or {})
    assert oaa_ext.get("unii") == "2F399MM81J"           # oxaloacetic acid, CAS 328-42-7
    assert oaa_ext.get("cas") == "328-42-7"

    paeo_ext = (rows["NHA_PAEONIFLORIN"].get("external_ids") or {})
    assert paeo_ext.get("unii") == "21AIQ4EV64"          # peoniflorin, CAS 23180-57-6
    assert paeo_ext.get("cas") == "23180-57-6"

    phlo_ext = (rows["NHA_PHLORIDZIN"].get("external_ids") or {})
    assert phlo_ext.get("unii") == "CU9S17279X"          # phlorizin, CAS 60-81-1
    assert phlo_ext.get("cas") == "60-81-1"

    citrate_ext = (rows["NHA_SODIUM_CITRATE"].get("external_ids") or {})
    assert citrate_ext.get("unii") == "1Q73Q2JULR"       # sodium citrate unspecified form


def test_verified_other_ingredients_critical_gsrs_fixes():
    """Critical GSRS fixes: PEG monomer contamination, cuprous oxide wrong CAS."""
    rows = _rows_by_id()

    # PEG must NOT have ethylene glycol GSRS/UNII
    peg = rows["PII_POLYETHYLENE_GLYCOL"]
    peg_ext = peg.get("external_ids") or {}
    assert peg.get("gsrs") is None                       # was ethylene glycol
    assert peg_ext.get("unii") in (None, "")             # cleared
    assert peg_ext.get("cas") == "25322-68-3"            # correct PEG CAS kept

    # Cuprous oxide CAS must be correct
    cu2o_ext = (rows["NHA_CUPROUS_OXIDE"].get("external_ids") or {})
    assert cu2o_ext.get("cas") == "1317-39-1"            # was 1308-76-5 (beryllium oxide)
