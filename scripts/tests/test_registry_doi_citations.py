"""LEDGER Q57 (2026-10-02): registry DOI citations are content-checked.

No verifier read DOIs, and 127 DOI citations in three registries resolved to an
unrelated paper (e.g. DMAA -> Moscow theatre siege casualties, yohimbe -> facial
soft-tissue thickness) or to nothing. Each was checked on Crossref and PubMed and
its citing text read; receipts: scripts/audits/pending_items_20260926/research.md Q57.
The verifier now reads DOIs (test_verify_all_citations_content.py), so the release
gate catches the next one; this file pins the batch itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api_audit"))

import verify_all_citations_content as vac  # noqa: E402

# (file, entry id) -> DOIs removed: they resolve to an unrelated paper or to nothing.
REMOVED = {
    ("banned_recalled_ingredients.json", "ADD_HORDENINE"): ["10.1016/j.fct.2019.110676"],
    ("banned_recalled_ingredients.json", "ADD_RED3"): ["10.1016/j.fct.2007.09.001"],
    ("banned_recalled_ingredients.json", "ADULTERANT_RIMONABANT"): ["10.1016/s0140-6736(07)61684-8"],
    ("banned_recalled_ingredients.json", "BANNED_14_BUTANEDIOL"): ["10.1016/j.forsciint.2003.08.001", "10.1093/jat/24.2.83"],
    ("banned_recalled_ingredients.json", "BANNED_7_HYDROXYMITRAGYNINE"): ["10.1124/jpet.116.232215"],
    ("banned_recalled_ingredients.json", "BANNED_ADD_PHTHALATES"): ["10.1016/j.envint.2020.105881", "10.1021/acs.est.4c01234", "10.1289/ehp10857"],
    ("banned_recalled_ingredients.json", "BANNED_ADD_SYNTHETIC_ESTROGENS"): ["10.1016/j.envint.2019.105267"],
    ("banned_recalled_ingredients.json", "BANNED_ADD_SYNTHETIC_FOOD_ACIDS"): ["10.1016/j.foodchem.2020.127556", "10.3390/foods9020178"],
    ("banned_recalled_ingredients.json", "BANNED_ARISTOLOCHIC_ACID"): ["10.1093/jnci/djr085"],
    ("banned_recalled_ingredients.json", "BANNED_BMPEA"): ["10.1016/j.drugalcdep.2015.01.027"],
    ("banned_recalled_ingredients.json", "BANNED_COMFREY_INTERNAL"): ["10.1002/hep.1840190107", "10.1093/jat/25.6.456"],
    ("banned_recalled_ingredients.json", "BANNED_DMAA"): ["10.1016/j.drugalcdep.2012.12.011", "10.1093/jat/bks078"],
    ("banned_recalled_ingredients.json", "BANNED_DMHA"): ["10.1016/j.drugalcdep.2019.01.026"],
    ("banned_recalled_ingredients.json", "BANNED_EPHEDRA"): ["10.1056/nejmoa032648", "10.7326/0003-4819-140-8-200404200-00006"],
    ("banned_recalled_ingredients.json", "BANNED_FASORACETAM"): ["10.1177/2045125316672135"],
    ("banned_recalled_ingredients.json", "BANNED_FDC_RED_2_AMARANTH"): ["10.1016/0278-6915(94)90034-5"],
    ("banned_recalled_ingredients.json", "BANNED_HIGENAMINE"): ["10.1016/j.fct.2013.07.080"],
    ("banned_recalled_ingredients.json", "BANNED_IBOTENIC_ACID"): ["10.1016/j.toxlet.2021.08.012"],
    ("banned_recalled_ingredients.json", "BANNED_IGF1"): ["10.1210/jc.2009-0491"],
    ("banned_recalled_ingredients.json", "BANNED_MUSCIMOL"): ["10.1016/j.toxlet.2021.08.012"],
    ("banned_recalled_ingredients.json", "BANNED_PHENIBUT"): ["10.1016/j.ajem.2019.03.029", "10.15585/mmwr.mm6843a6"],
    ("banned_recalled_ingredients.json", "BANNED_S23"): ["10.1210/endo.140.12.7163"],
    ("banned_recalled_ingredients.json", "BANNED_SR9009"): ["10.1038/nature11704"],
    ("banned_recalled_ingredients.json", "BANNED_TIANEPTINE"): ["10.15585/mmwr.mm7316a4"],
    ("banned_recalled_ingredients.json", "BANNED_YELLOW_OLEANDER_RECENT"): ["10.1016/j.toxicon.2018.11.434"],
    ("banned_recalled_ingredients.json", "HIGH_RISK_CHAPARRAL"): ["10.1001/jama.1992.03490220089034"],
    ("banned_recalled_ingredients.json", "HIGH_RISK_PENNYROYAL"): ["10.1016/s0140-6736(96)01471-5"],
    ("banned_recalled_ingredients.json", "HM_ARSENIC"): ["10.1289/ehp.1104494"],
    ("banned_recalled_ingredients.json", "HM_CADMIUM"): ["10.1016/j.fct.2013.12.005"],
    ("banned_recalled_ingredients.json", "HM_LEAD"): ["10.1016/s0140-6736(18)31310-2"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_9MEBC"): ["10.1016/j.neuropharm.2015.08.025"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_ADRAFINIL"): ["10.1016/s0149-2918(99)80048-1"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_ANIRACETAM"): ["10.1007/s002130050622"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_BROMANTANE"): ["10.1007/s11055-013-9858-1"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_FLMODAFINIL"): ["10.1021/jm00346a004"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_MODAFINIL"): ["10.1001/jama.2017.3085"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_OMBERACETAM"): ["10.1007/s11055-008-0025-6"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_PHENYLPIRACETAM"): ["10.1007/s11055-007-0078-x"],
    ("banned_recalled_ingredients.json", "NOOTROPIC_PIRACETAM"): ["10.1002/hup.2656"],
    ("banned_recalled_ingredients.json", "PEPTIDE_MELANOTAN_II"): ["10.1111/bjd.13316"],
    ("banned_recalled_ingredients.json", "PHARMA_LORCASERIN"): ["10.1056/nejmoa1908681"],
    ("banned_recalled_ingredients.json", "RC_CARDARINE_ANALOGS"): ["10.1093/toxsci/kfm226"],
    ("banned_recalled_ingredients.json", "RECALLED_HYDROXYCUT"): ["10.1002/hep.23393"],
    ("banned_recalled_ingredients.json", "RECALLED_JACK3D"): ["10.1016/j.drugalcdep.2015.01.011"],
    ("banned_recalled_ingredients.json", "RECALLED_OXYELITE_PRO"): ["10.1001/jama.2013.281632"],
    ("banned_recalled_ingredients.json", "RISK_BITTER_ORANGE"): ["10.1002/mnfr.201100409", "10.1016/j.ijcard.2012.09.001"],
    ("banned_recalled_ingredients.json", "RISK_GERMANIUM"): ["10.1093/ndt/13.10.2427"],
    ("banned_recalled_ingredients.json", "RISK_GREEN_TEA_EXTRACT_HIGH"): ["10.1016/j.fct.2016.12.033"],
    ("banned_recalled_ingredients.json", "RISK_KAVA"): ["10.1002/hep.20662", "10.1111/j.1365-2125.2007.02958.x"],
    ("banned_recalled_ingredients.json", "RISK_KRATOM_NATURAL"): ["10.1002/hep.30612"],
    ("banned_recalled_ingredients.json", "RISK_YOHIMBE"): ["10.1016/j.forsciint.2012.02.015"],
    ("banned_recalled_ingredients.json", "SARM_ANDARINE"): ["10.1210/en.2007-0814"],
    ("banned_recalled_ingredients.json", "SARM_CARDARINE"): ["10.1093/toxsci/kfn160"],
    ("banned_recalled_ingredients.json", "SARM_LIGANDROL"): ["10.1210/jc.2013-2271"],
    ("banned_recalled_ingredients.json", "SARM_OSTARINE"): ["10.1002/hep.29466"],
    ("banned_recalled_ingredients.json", "SARM_RAD140"): ["10.14309/crj.0000000000000518"],
    ("banned_recalled_ingredients.json", "SCHED_AMANITA_MUSCARIA"): ["10.1016/j.toxlet.2021.08.012"],
    ("banned_recalled_ingredients.json", "SCHED_PSILOCIN"): ["10.1177/0269881118767697"],
    ("banned_recalled_ingredients.json", "SCHED_PSILOCYBIN"): ["10.1177/0269881118767697"],
    ("banned_recalled_ingredients.json", "STIM_METHYLHEXANAMINE_ANALOGS"): ["10.1016/j.drugalcdep.2015.01.011"],
    ("harmful_additives.json", "ADD_ANTIMONY"): ["10.1016/j.envint.2009.02.003"],
    ("harmful_additives.json", "ADD_BHA"): ["10.1016/j.fct.2020.111535", "10.1093/jnci/djh184"],
    ("harmful_additives.json", "ADD_BHT"): ["10.1016/j.fct.2020.111535"],
    ("harmful_additives.json", "ADD_BISPHENOL_F"): ["10.1016/j.envint.2020.105914", "10.1289/ehp2716"],
    ("harmful_additives.json", "ADD_BISPHENOL_S"): ["10.1016/j.envint.2020.105914", "10.1289/ehp2716"],
    ("harmful_additives.json", "ADD_CASSAVA_DEXTRIN"): ["10.1093/ajcn/86.4.895"],
    ("harmful_additives.json", "ADD_CORN_SYRUP_SOLIDS"): ["10.1016/j.numecd.2019.05.062", "10.1093/ajcn/86.4.895"],
    ("harmful_additives.json", "ADD_CROSCARMELLOSE_SODIUM"): ["10.1016/j.ijpharm.2016.11.018"],
    ("harmful_additives.json", "ADD_CROSPOVIDONE"): ["10.1016/j.ijpharm.2016.11.018"],
    ("harmful_additives.json", "ADD_ERYTHRITOL"): ["10.1161/atvbaha.123.319909"],
    ("harmful_additives.json", "ADD_FRUCTOSE"): ["10.1016/j.jhep.2013.11.014", "10.1210/jc.2012-2750"],
    ("harmful_additives.json", "ADD_HFCS"): ["10.1016/j.jhep.2013.11.014", "10.1210/jc.2012-2750"],
    ("harmful_additives.json", "ADD_HYDROGENATED_STARCH_HYDROLYSATE"): ["10.1111/j.1365-2036.2012.05044.x"],
    ("harmful_additives.json", "ADD_ISOMALTOOLIGOSACCHARIDE"): ["10.1093/jn/nxy151"],
    ("harmful_additives.json", "ADD_MAGNESIUM_STEARATE"): ["10.1016/j.ejpb.2008.09.017"],
    ("harmful_additives.json", "ADD_MSG"): ["10.1016/j.lfs.2020.117659"],
    ("harmful_additives.json", "ADD_PALM_OIL"): ["10.3390/nu12051347"],
    ("harmful_additives.json", "ADD_POLYETHYLENE_GLYCOL"): ["10.1002/jps.23963", "10.1016/j.jaci.2016.02.010"],
    ("harmful_additives.json", "ADD_POLYVINYLPYRROLIDONE"): ["10.1002/jps.24274", "10.1016/j.toxlet.2020.12.019"],
    ("harmful_additives.json", "ADD_POTASSIUM_NITRATE"): ["10.1093/jnci/djq516"],
    ("harmful_additives.json", "ADD_POTASSIUM_NITRITE"): ["10.1093/jnci/djq516"],
    ("harmful_additives.json", "ADD_PROPYLPARABEN"): ["10.1016/j.fct.2013.07.016", "10.1093/humrep/det428"],
    ("harmful_additives.json", "ADD_SHELLAC"): ["10.1016/j.foodchem.2018.03.037"],
    ("harmful_additives.json", "ADD_SILICON_DIOXIDE"): ["10.1016/j.fct.2020.111617", "10.3390/nano12030457"],
    ("harmful_additives.json", "ADD_SODIUM_CASEINATE"): ["10.1016/j.foodchem.2018.12.057"],
    ("harmful_additives.json", "ADD_SODIUM_HEXAMETAPHOSPHATE"): ["10.1053/j.ajkd.2013.08.005"],
    ("harmful_additives.json", "ADD_SODIUM_NITRATE"): ["10.1093/jnci/djq516"],
    ("harmful_additives.json", "ADD_SODIUM_NITRITE"): ["10.1093/jnci/djq516"],
    ("harmful_additives.json", "ADD_SODIUM_TRIPOLYPHOSPHATE"): ["10.1016/j.kint.2017.04.046", "10.1093/ndt/gfr268"],
    ("harmful_additives.json", "ADD_SORBIC_ACID"): ["10.1016/j.fct.2017.04.024"],
    ("harmful_additives.json", "ADD_STEARIC_ACID"): ["10.1002/jps.24274", "10.1016/j.imlet.2012.11.006"],
    ("harmful_additives.json", "ADD_SUCRALOSE"): ["10.1016/j.scitotenv.2023.168233"],
    ("harmful_additives.json", "ADD_SYNTHETIC_ANTIOXIDANTS"): ["10.1016/j.fct.2020.111535"],
    ("harmful_additives.json", "ADD_SYNTHETIC_VITAMINS"): ["10.1093/ajcn/84.1.18", "10.3945/ajcn.114.089284"],
    ("harmful_additives.json", "ADD_SYRUPS"): ["10.1093/ajcn/86.4.895"],
    ("harmful_additives.json", "ADD_TBHQ"): ["10.1016/j.fct.2018.09.045"],
    ("harmful_additives.json", "ADD_TETRASODIUM_DIPHOSPHATE"): ["10.1007/s00394-019-01961-2", "10.3390/nu12092798"],
    ("harmful_additives.json", "ADD_TIN"): ["10.2903/j.efsa.2016.4444"],
    ("harmful_additives.json", "ADD_YELLOW5"): ["10.1016/j.fct.2012.06.052"],
    ("harmful_additives.json", "ADD_YELLOW6"): ["10.1016/j.fct.2012.06.052"],
    ("other_ingredients.json", "NHA_L_ARABINOSE"): ["10.1017/s0007114510002060"],
    ("other_ingredients.json", "NHA_MIRTOGENOL"): ["10.1159/000268121"],
    ("other_ingredients.json", "NHA_SOLUBLE_CORN_FIBER"): ["10.1017/s0007114512001560"],
}

# Mistyped DOI of the document the entry names -> the verified DOI of that document.
CORRECTED = [
    ("harmful_additives.json", "ADD_CANOLA_OIL", "10.2903/j.efsa.2010.1459", "10.2903/j.efsa.2010.1461"),
    ("harmful_additives.json", "ADD_CORN_OIL", "10.2903/j.efsa.2010.1459", "10.2903/j.efsa.2010.1461"),
    ("harmful_additives.json", "ADD_FATTY_ACID_POLYGLYCEROL_ESTERS", "10.2903/j.efsa.2017.4743", "10.2903/j.efsa.2017.5089"),
    ("harmful_additives.json", "ADD_NICKEL", "10.2903/j.efsa.2015.4007", "10.2903/j.efsa.2015.4002"),
    ("harmful_additives.json", "ADD_SODIUM_NITRITE", "10.2903/j.efsa.2017.4787", "10.2903/j.efsa.2017.4786"),
    ("harmful_additives.json", "ADD_UNSPECIFIED_COLORS", "10.2903/j.efsa.2015.4037", "10.2903/j.efsa.2015.4288"),
]


def _claims(file: str, entry_id: str) -> str:
    """An entry's claim-side text: everything but history (change logs)."""
    config = next(c for c in vac.FILE_CONFIGS if c["file"] == file)
    data = json.loads((ROOT / "data" / file).read_text())
    entry = next(e for e in vac.entries_of(data, config) if vac.entry_id_of(e, config) == entry_id)
    return json.dumps({k: v for k, v in entry.items() if k not in vac.HISTORY_KEYS and k != "review"}).lower()


@pytest.mark.parametrize("file, entry_id", sorted(REMOVED))
def test_wrong_and_unresolvable_dois_are_gone(file, entry_id):
    text = _claims(file, entry_id)
    assert [doi for doi in REMOVED[(file, entry_id)] if doi in text] == []


@pytest.mark.parametrize("file, entry_id, mistyped, verified", CORRECTED)
def test_mistyped_efsa_dois_point_at_the_named_opinion(file, entry_id, mistyped, verified):
    text = _claims(file, entry_id)
    assert mistyped not in text
    assert verified in text


def test_ostarine_cites_the_ostarine_liver_injury_case_not_rad140():
    # PMID 34368386 (Bedi 2021, enobosarm DILI) was filed under SARM_RAD140.
    assert "pubmed.ncbi.nlm.nih.gov/34368386" in _claims("banned_recalled_ingredients.json", "SARM_OSTARINE")
    assert "0000000000000518" not in _claims("banned_recalled_ingredients.json", "SARM_RAD140")
