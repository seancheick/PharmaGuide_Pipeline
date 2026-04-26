"""Regression test: Batch 23 — herbal extracts + marine oils.

Per IQM audit 2026-04-25 Step 4 Batch 23: 25 forms across 12 parents.
Five framework findings:

1. SLIPPERY ELM = CATEGORY ERROR (4th overall after manuka B18, organ
   extracts B20, prebiotics B22). Mucilage polysaccharides hydrate in GI
   lumen → topical demulcent. NOT systemically absorbed. NO PubMed PMID
   exists for slippery elm mucilage PK.

2. WHITE WILLOW SALICIN → SALICYLIC ACID — pre-absorption hydrolysis
   CONFIRMED. Schmid 2001 (PMID:11599656): 240 mg salicin → ~86% SA.

3. CALANUS WAX ESTER ≈ TG (Cook 2016 PMID:27604086) — wax-ester
   bottleneck hypothesis OVERTURNED. iAUC = ethyl ester reference.

4. OLIVE PHENOLICS — pre-absorption hydrolysis (oleuropein → HT) per
   García-Villalba 2014 (PMID:24158653).

5. VERBASCOSIDE = P-gp + BCRP + MRP2 substrate (Yang 2020 PMID:31778580).

Verified PMIDs:
  PMID:27355793 D'Antuono 2016 — olive Caco-2 1.86%
  PMID:24158653 García-Villalba 2014 — olive leaf oleuropein PK
  PMID:20878691 Anderson 2010 — valerenic acid PK
  PMID:31778580 Yang 2020 — verbascoside P-gp substrate
  PMID:11599656 Schmid 2001 — willow salicin → SA
  PMID:19269122 Gupta 2009 — goldenseal LC-MS/MS
  PMID:9684946  Biber 1998 — hyperforin (NOT 9684421)
  PMID:8878586  Kerb 1996 — hypericin/pseudohypericin F
  PMID:27604086 Cook 2016 — calanus oil iAUC
  PMID:12591004 Kurowska 2003 — perilla ALA PK
  PMID:12323085 Burdge 2002 — ALA conversion limited
  PMID:10588467 Conquer 1999 — seal oil EPA up 4.3x

Ghost references caught:
  • PMID:9684421 ≠ Biber 1998 (n-of-1 RCT editorial)
  • "Bos 1996" valerenic — no robust PMID
  • Slippery elm mucilage PK — none on PubMed
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


# (parent, form, vmin, vmax, basis)
B23_BANDS_VALUED = [
    # Olives — phenolic delivery
    ('olive_fruit_extract', 'olive fruit extract standardized',         0.40, 0.55, 'D\'Antuono 2016'),
    ('olive_leaf',          'olive leaf extract standardized',          0.45, 0.55, 'García-Villalba 2014'),
    # Valerian
    ('valerian', 'valerian standardized extract',                       0.30, 0.50, 'Anderson 2010'),
    ('valerian', 'valerian root powder',                                0.30, 0.50, 'class gradient'),
    ('valerian', 'valerian (unspecified)',                              0.20, 0.40, 'class floor'),
    # Guava — bioflavonoid class-poor
    ('guava_leaf', 'guava leaf extract',                                0.05, 0.10, 'bioflav class-poor'),
    ('guava_leaf', 'guava leaf powder',                                 0.03, 0.08, 'bioflav class-poor'),
    ('guava_leaf', 'guava (unspecified)',                               0.03, 0.10, 'bioflav class-poor'),
    # Mullein — verbascoside efflux
    ('mullein', 'standardized mullein (verbascoside)',                  0.10, 0.20, 'Yang 2020 P-gp'),
    ('mullein', 'mullein leaf extract',                                 0.05, 0.15, 'efflux+class-poor'),
    ('mullein', 'mullein (unspecified)',                                0.03, 0.10, 'class floor'),
    # White willow — pre-absorption hydrolysis
    ('white_willow_bark', 'white willow bark standardized',             0.50, 0.60, 'Schmid 2001'),
    # Goldenseal — berberine class-poor
    ('goldenseal', 'standardized goldenseal (berberine/hydrastine)',    0.05, 0.15, 'Gupta 2009'),
    ('goldenseal', 'goldenseal root powder',                            0.05, 0.10, 'class gradient'),
    ('goldenseal', 'goldenseal (unspecified)',                          0.03, 0.10, 'class floor'),
    # St. John's Wort
    ('st_johns_wort', "st john's wort standardized extract",            0.30, 0.50, 'Biber 1998'),
    ('st_johns_wort', "st john's wort powder",                          0.30, 0.50, 'class gradient'),
    ('st_johns_wort', "st john's wort (unspecified)",                   0.20, 0.40, 'class floor'),
    # Marine oils
    ('calanus_oil', 'calanus oil',                                      0.65, 0.75, 'Cook 2016'),
    ('perilla_oil', 'perilla seed oil',                                 0.70, 0.85, 'Kurowska 2003'),
    ('seal_oil',    'blubber oil',                                      0.80, 0.90, 'Conquer 1999'),
]

B23_NULL_FORMS = [
    # Slippery elm — CATEGORY ERROR (mucilage local action)
    ('slippery_elm', 'standardized extract (mucilage)'),
    ('slippery_elm', 'inner bark powder'),
    ('slippery_elm', 'bark powder (unspecified)'),
    ('slippery_elm', 'outer bark powder'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B23_BANDS_VALUED)
def test_b23_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname', B23_NULL_FORMS)
def test_b23_slippery_elm_category_error_null(iqm, pid, fname):
    """Slippery elm mucilage forms must have struct.value=null per category-
    error finding — polysaccharide local mucosal coating, not systemically
    absorbed. No PubMed PMID exists for mucilage PK.
    """
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, (
        f'{pid}::{fname} value={val} must be null — mucilage polysaccharide '
        f'acts topically on GI mucosa (4th category error after manuka, '
        f'organ extracts, prebiotics). No PubMed PMID for systemic absorption.'
    )


def test_slippery_elm_category_error_documented(iqm):
    """Slippery elm notes must document category-error / local-action."""
    forms = iqm['slippery_elm']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('category error', 'category_error', 'local action',
                        'local mucosal', 'demulcent', 'not systemically',
                        'topically', 'not systemic')
        assert any(p in text_lower for p in flag_phrases), (
            f'slippery_elm::{fname} must document category-error / local '
            f'mucosal action. Text: {text[:300]}'
        )


def test_white_willow_pre_absorption_hydrolysis_qualified(iqm):
    """White willow standardized notes must qualify salicin → salicylic
    acid pre-absorption hydrolysis per Schmid 2001 (PMID:11599656).
    """
    form = iqm['white_willow_bark']['forms']['white willow bark standardized']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('salicin', 'salicylic acid', 'pre-absorption',
                    'pre absorption', 'hydrolysis', '11599656')
    assert any(p in text_lower for p in flag_phrases), (
        f'white_willow_bark standardized must qualify salicin → salicylic '
        f'acid pre-absorption hydrolysis (PMID:11599656). Text: {text[:300]}'
    )


def test_calanus_wax_ester_iauc_qualified(iqm):
    """Calanus oil notes must reference Cook 2016 wax-ester iAUC = EE
    reference finding (PMID:27604086).
    """
    form = iqm['calanus_oil']['forms']['calanus oil']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('27604086', 'cook 2016', 'iauc', 'ethyl ester',
                    'wax ester', 'wax-ester', 'slow-release', 'slow release')
    assert any(p in text_lower for p in flag_phrases), (
        f'calanus_oil must reference Cook 2016 (PMID:27604086) wax-ester '
        f'iAUC = EE finding. Text: {text[:300]}'
    )


def test_st_johns_wort_biber_pmid_correct(iqm):
    """St. John's Wort standardized notes must cite correct Biber PMID
    9684946 — NOT the transposition trap PMID:9684421 (which is a Drug
    Ther Bull n-of-1 RCT editorial, not Biber 1998).
    """
    form = iqm['st_johns_wort']['forms']["st john's wort standardized extract"]
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    # Must cite correct Biber PMID
    assert '9684946' in text, (
        'st_johns_wort standardized must cite Biber 1998 PMID:9684946. '
        f'Text: {text[:400]}'
    )
    # If wrong PMID is present at all, it must be flagged as ghost trap
    if 'PMID:9684421' in text or '9684421' in text:
        assert any(neg in text.lower() for neg in
                   ('not biber', 'transposition', 'ghost', 'misattribut',
                    'is not', 'editorial')), (
            f'PMID:9684421 cited without ghost-trap qualification. Must '
            f'mark as transposition trap (correct = 9684946). Text: {text[:400]}'
        )


def test_olive_pre_absorption_hydrolysis_qualified(iqm):
    """Olive leaf standardized notes must qualify oleuropein → HT pre-
    absorption hydrolysis per García-Villalba 2014 (PMID:24158653).
    """
    form = iqm['olive_leaf']['forms']['olive leaf extract standardized']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('oleuropein', 'hydroxytyrosol', 'pre-absorption',
                    'pre absorption', 'hydrolysis', '24158653',
                    'garcía-villalba', 'garcia-villalba')
    assert any(p in text_lower for p in flag_phrases), (
        f'olive_leaf standardized must qualify oleuropein → HT pre-absorption '
        f'hydrolysis (PMID:24158653). Text: {text[:300]}'
    )


def test_verbascoside_efflux_substrate_qualified(iqm):
    """Mullein standardized verbascoside notes must qualify P-gp/BCRP/MRP2
    efflux per Yang 2020 (PMID:31778580).
    """
    form = iqm['mullein']['forms']['standardized mullein (verbascoside)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('p-gp', 'p gp', 'bcrp', 'mrp2', 'efflux',
                    '31778580', 'yang 2020', 'acteoside')
    assert any(p in text_lower for p in flag_phrases), (
        f'mullein standardized verbascoside must qualify P-gp/BCRP/MRP2 '
        f'efflux substrate status (PMID:31778580). Text: {text[:300]}'
    )


def test_goldenseal_berberine_class_extension(iqm):
    """Goldenseal standardized notes must reference berberine class-poor
    framework + verified Gupta 2009 PMID:19269122.
    """
    form = iqm['goldenseal']['forms']['standardized goldenseal (berberine/hydrastine)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('berberine', '19269122', 'gupta 2009', 'class-poor',
                    'class poor', 'hydrastine')
    assert any(p in text_lower for p in flag_phrases), (
        f'goldenseal standardized must qualify berberine class-poor + cite '
        f'Gupta 2009 (PMID:19269122). Text: {text[:300]}'
    )


def test_perilla_ala_class_equivalence(iqm):
    """Perilla seed oil notes must reference ALA absorption (Kurowska
    2003) AND limited EPA/DHA conversion (Burdge 2002).
    """
    form = iqm['perilla_oil']['forms']['perilla seed oil']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    # Must cite Kurowska or Burdge or ALA conversion
    flag_phrases = ('12591004', '12323085', 'kurowska', 'burdge',
                    'ala', 'conversion', 'epa/dha', 'epa + dha')
    matches = [p for p in flag_phrases if p in text_lower]
    assert len(matches) >= 2, (
        f'perilla_oil must reference both ALA absorption (Kurowska 2003 '
        f'PMID:12591004) and conversion limitation (Burdge 2002 '
        f'PMID:12323085). Found: {matches}. Text: {text[:400]}'
    )


def test_seal_oil_tg_class_equivalence(iqm):
    """Seal oil notes must reference Conquer 1999 PMID:10588467 + TG
    omega-3 class equivalence.
    """
    form = iqm['seal_oil']['forms']['blubber oil']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('10588467', 'conquer 1999', 'serum phospholipid',
                    'tg omega-3', 'tg omega', 'triglyceride', 'epa', 'dpa')
    matches = [p for p in flag_phrases if p in text_lower]
    assert len(matches) >= 2, (
        f'seal_oil must reference Conquer 1999 (PMID:10588467) and TG '
        f'omega-3 class. Found: {matches}. Text: {text[:400]}'
    )


def test_no_phantom_biber_9684421(iqm):
    """Wrong "Biber 1998 PMID:9684421" must not appear as live citation —
    actually n-of-1 RCT editorial. Correct: PMID:9684946.
    """
    forms = iqm['st_johns_wort']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        if 'PMID:9684421' in text or '9684421' in text:
            assert any(neg in text.lower() for neg in
                       ('not biber', 'transposition', 'ghost', 'misattribut',
                        'is not', 'editorial', 'wrong')), (
                f'st_johns_wort::{fname} cites PMID:9684421 (n-of-1 RCT '
                f'editorial) without ghost-trap qualification. Use PMID:9684946.'
            )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:11599656': 'Schmid 2001 white willow',
        'PMID:9684946':  'Biber 1998 hyperforin',
        'PMID:27604086': 'Cook 2016 calanus',
        'PMID:10588467': 'Conquer 1999 seal oil',
        'PMID:24158653': 'García-Villalba 2014 olive leaf',
        'PMID:31778580': 'Yang 2020 verbascoside',
    }
    full_text = ''
    for pid in ('white_willow_bark', 'st_johns_wort', 'calanus_oil',
                'seal_oil', 'olive_leaf', 'mullein', 'olive_fruit_extract',
                'valerian', 'goldenseal', 'perilla_oil'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_fourth_category_error_pattern(iqm):
    """Four category-error parent groups now established: manuka (B18),
    organ extracts (B20), prebiotics (B22), slippery elm (B23). All
    forms in these groups must have struct.value=null.
    """
    category_error_forms = [
        ('manuka_honey', 'umf 15+ / mgo 514+'),
        ('organ_extracts', 'grass-fed desiccated'),
        ('inulin', 'inulin (unspecified)'),
        ('larch_arabinogalactan', 'larch arabinogalactan powder'),
        ('slippery_elm', 'standardized extract (mucilage)'),
        ('slippery_elm', 'inner bark powder'),
    ]
    for pid, fname in category_error_forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'{pid}::{fname} value={v} should be null per category-error '
            f'(framework does not apply)'
        )
