"""Regression test: vitamin B12, D, K bioavailability + citation integrity.

Per IQM audit 2026-04-25 Step 4 Batch 10: 31 vitamin forms across 3 parents
were null-value despite high bio_scores. Research subagent USED WebFetch
on PubMed eutils API and discovered ALL 5 supplied "well-known" PMIDs
were misattributions:

| Supplied | Actual content (verified) |
|---|---|
| PMID:18065595 | Newby 2007 whole grains (NOT Carmel B12) |
| PMID:11144476 | Zerahn 2000 cardiac imaging (NOT Heaney D2/D3) |
| PMID:23682915 | Castagnone-Sereno 2013 nematode genomics (NOT Shieh) |
| PMID:22516125 | Qu 2012 iron DFT (NOT Sato MK-7) |
| PMID:17906277 | Pearson 2007 nutrition review (NOT Schurgers MK-7) |

Verified replacement PMIDs (all confirmed via PubMed efetch):
  PMID:18709891  Carmel R 2008 — B12 absorption review
  PMID:28187226  Shieh A 2017 — calcidiol +25.5 vs D3 +13.8 ng/mL (P=0.001)
  PMID:23140417  Sato T 2012 — MK-4 at 420 μg undetectable in serum
  PMID:17158229  Schurgers LJ 2007 Blood — MK-7 7-8x vs K1
  PMID:11356998  Schurgers LJ 2000 — natto K2 ~10x vs spinach K1
  PMID:37865222  van den Heuvel 2024 — D2 raises 25(OH)D 10.39 nmol/L (40%)
                  less than D3 daily-dose (verified: NOT 15.69 nmol/L)
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


# (parent, form, vmin, vmax, basis)  vmin/vmax=None means value should be None
BDK_EVIDENCE_BANDS = [
    # B12 (passive ~1-2%, sublingual ~10-30%)
    ('vitamin_b12_cobalamin', 'methylcobalamin sublingual',     0.10, 0.40, 'sublingual bypass IF'),
    ('vitamin_b12_cobalamin', 'methylcobalamin',                0.01, 0.05, 'passive ~1-2%'),
    ('vitamin_b12_cobalamin', 'adenosylcobalamin',              0.01, 0.05, 'passive ~1-2%'),
    ('vitamin_b12_cobalamin', 'hydroxocobalamin',               0.01, 0.05, 'passive ~1-3%'),
    ('vitamin_b12_cobalamin', 'cyanocobalamin sublingual',      0.10, 0.30, 'sublingual'),
    ('vitamin_b12_cobalamin', 'cyanocobalamin',                 0.01, 0.05, 'passive ~1-2%'),
    ('vitamin_b12_cobalamin', 'b12 (unspecified)',              0.01, 0.05, 'unspecified passive'),
    # D (fat-soluble, meal-dependent)
    ('vitamin_d', 'cholecalciferol (D3)',                        0.50, 0.80, 'D3 with fat meal'),
    ('vitamin_d', 'calcidiol (25-hydroxy D3)',                   0.65, 0.90, 'pre-hydroxylated; Shieh 2017'),
    ('vitamin_d', 'micellized D3',                               0.60, 0.85, 'micellar'),
    ('vitamin_d', 'liposomal D3',                                0.55, 0.80, 'liposomal'),
    ('vitamin_d', 'microencapsulated D3',                        0.50, 0.75, 'microencap'),
    ('vitamin_d', 'vitamin D3 from lichen',                      0.50, 0.80, 'vegan D3'),
    ('vitamin_d', 'ergocalciferol (D2)',                         0.35, 0.60, 'D2 ~40% less than D3'),
    ('vitamin_d', 'vitamin D2 (unspecified source)',             0.30, 0.55, 'D2 unspec'),
    ('vitamin_d', 'vitamin D2 from UV-treated mushrooms',        0.30, 0.55, 'mushroom D2'),
    # K (highly variable by form)
    ('vitamin_k', 'menaquinone-7 (MK-7)',                         0.60, 0.85, 'MK-7 long t½'),
    ('vitamin_k', 'menaquinone-7 all-trans',                      0.65, 0.90, 'all-trans MK-7'),
    ('vitamin_k', 'menaquinone-4 (MK-4)',                         0.01, 0.15, 'Sato 2012 undetectable'),
    ('vitamin_k', 'phylloquinone (K1)',                           0.10, 0.25, 'K1 short t½'),
    ('vitamin_k', 'vitamin K1 synthetic',                         0.15, 0.30, 'synthetic K1'),
    ('vitamin_k', 'vitamin K2 from natto',                        0.70, 0.90, 'natto MK-7'),
    ('vitamin_k', 'vitamin K2 from cheese',                       0.40, 0.65, 'cheese MK-8/9'),
    ('vitamin_k', 'vitamin K2 from yeast',                        0.30, 0.55, 'yeast MK'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', BDK_EVIDENCE_BANDS)
def test_bdk_value_in_evidence_band(iqm, pid, fname, vmin, vmax, basis):
    """Each B12/D/K form's struct.value must sit in evidence band."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_no_misattributed_pmids_introduced(iqm):
    """The 5 misattributed PMIDs caught in Batch 10 must NOT appear as live
    citations (allowed only inside audit-trail under "supposed" or "supplied").
    """
    misattributed = [
        ('PMID:18065595', 'Newby 2007 whole grains, NOT Carmel'),
        ('PMID:11144476', 'Zerahn 2000 cardiac, NOT Heaney'),
        ('PMID:23682915', 'Castagnone 2013 nematode, NOT Shieh'),
        ('PMID:22516125', 'Qu 2012 iron DFT, NOT Sato'),
        ('PMID:17906277', 'Pearson 2007, NOT Schurgers'),
    ]
    parents = ('vitamin_b12_cobalamin', 'vitamin_d', 'vitamin_k')
    violations = []
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            for pmid, what in misattributed:
                if pmid in text:
                    # Allow if surrounded by audit-trail context
                    idx = text.find(pmid)
                    window = text[max(0, idx-80):idx]
                    if any(marker in window.lower()
                           for marker in ('supposed', 'supplied', 'misattribut',
                                          'caught', 'wrong', 'not ', 'phantom')):
                        continue
                    violations.append((pid, fname, pmid, what))
    assert not violations, (
        f'Misattributed PMIDs introduced as live citations: {violations}. '
        f'Use verified replacements: PMID:18709891 (Carmel), 28187226 (Shieh), '
        f'23140417 (Sato), 17158229 (Schurgers 2007), 11356998 (Schurgers 2000)'
    )


def test_d2_correction_15_69_to_10_39(iqm):
    """The "15.69 nmol/L D3>D2" claim must NOT remain as a live citation.
    Verified value per van den Heuvel 2024 (PMID:37865222) is 10.39 nmol/L.
    """
    parents = ('vitamin_d',)
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            assert '15.69 nmol/L' not in text or 'NOT 15.69' in text or 'corrected' in text.lower(), (
                f'{pid}::{fname} still claims "15.69 nmol/L" — verified value '
                f'per PMID:37865222 (van den Heuvel 2024) is 10.39 nmol/L'
            )


def test_microencap_d3_no_25percent_marketing_claim(iqm):
    """The "25% better" microencapsulated D3 claim was unverifiable per
    Batch 10 research; must not appear as a live claim.
    """
    form = iqm['vitamin_d']['forms']['microencapsulated D3']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    # Allow "25%" only if surrounded by qualifier ("no peer-reviewed", "claim", etc.)
    if '25%' in text:
        idx = text.find('25%')
        window = text[max(0, idx-80):idx+30]
        assert any(neg in window.lower() for neg in
                   ('no peer-reviewed', 'unverified', 'claim',
                    'could not be traced', 'flagged', 'not')), (
            f'microencapsulated D3 still claims "25%" without qualification. '
            f'Window: {window!r}'
        )


def test_verified_pmids_introduced(iqm):
    """The 6 verified replacement PMIDs from Batch 10 should each appear in
    relevant forms.
    """
    expected_citations = {
        'PMID:18709891': ('vitamin_b12_cobalamin', 'methylcobalamin'),  # Carmel B12
        'PMID:28187226': ('vitamin_d', 'calcidiol (25-hydroxy D3)'),     # Shieh
        'PMID:23140417': ('vitamin_k', 'menaquinone-4 (MK-4)'),          # Sato
        'PMID:17158229': ('vitamin_k', 'menaquinone-7 (MK-7)'),          # Schurgers 2007
        'PMID:11356998': ('vitamin_k', 'vitamin K2 from natto'),         # Schurgers 2000
        'PMID:37865222': ('vitamin_d', 'ergocalciferol (D2)'),           # van den Heuvel
    }
    for pmid, (pid, fname) in expected_citations.items():
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        assert pmid in text, (
            f'Verified citation {pmid} should be cited in {pid}::{fname}'
        )


def test_b12_active_form_oral_F_class_consistent(iqm):
    """Per Carmel 2008 (PMID:18709891) and B12 absorption physiology, oral F
    is identical (~1-2% passive at supplemental doses) across active forms.
    methylcobalamin / adenosylcobalamin / hydroxocobalamin / cyanocobalamin
    must all have struct.value in the 0.01-0.05 band when given orally.
    Sublingual forms are exempt (10-40% via mucosa).
    """
    forms = iqm['vitamin_b12_cobalamin']['forms']
    oral_forms = ('methylcobalamin', 'adenosylcobalamin', 'hydroxocobalamin',
                  'cyanocobalamin', 'b12 (unspecified)')
    violations = []
    for fname in oral_forms:
        form = forms.get(fname)
        if not form:
            continue
        val = (form.get('absorption_structured') or {}).get('value')
        if val is None:
            continue
        if not (0.01 <= val <= 0.05):
            violations.append((fname, val))
    assert not violations, (
        f'B12 oral forms must have struct.value in [0.01, 0.05] band per '
        f'Carmel 2008 (PMID:18709891) — passive ~1-2%. Violations: {violations}'
    )


def test_mk7_dominates_mk4(iqm):
    """Per Sato 2012 (PMID:23140417), MK-7 absorption >> MK-4 at nutritional
    doses. struct.value(MK-7) must be at least 4x struct.value(MK-4).
    """
    forms = iqm['vitamin_k']['forms']
    mk7 = (forms['menaquinone-7 (MK-7)'].get('absorption_structured') or {}).get('value')
    mk4 = (forms['menaquinone-4 (MK-4)'].get('absorption_structured') or {}).get('value')
    assert mk7 is not None and mk4 is not None
    assert mk7 >= 4 * mk4, (
        f'MK-7 ({mk7}) must be ≥ 4× MK-4 ({mk4}) per Sato 2012 PMID:23140417 '
        f'finding that MK-4 at 420 μg is undetectable in serum while MK-7 '
        f'is well-absorbed.'
    )


def test_natto_k2_top_ranking(iqm):
    """Per Schurgers 2000 (PMID:11356998), natto-derived K2 should rank highest
    among K2 source forms (natto > cheese > yeast).
    """
    forms = iqm['vitamin_k']['forms']
    def v(name):
        return (forms[name].get('absorption_structured') or {}).get('value') or 0
    natto = v('vitamin K2 from natto')
    cheese = v('vitamin K2 from cheese')
    yeast = v('vitamin K2 from yeast')
    assert natto > cheese > yeast, (
        f'K2 source ranking should be natto ({natto}) > cheese ({cheese}) > '
        f'yeast ({yeast}) per Schurgers 2000 (PMID:11356998)'
    )


def test_d2_inferior_to_d3(iqm):
    """Per van den Heuvel 2024 (PMID:37865222), D2 raises 25(OH)D 40% less
    than D3 daily-dose. struct.value(D2) must be < struct.value(D3).
    """
    forms = iqm['vitamin_d']['forms']
    d3 = (forms['cholecalciferol (D3)'].get('absorption_structured') or {}).get('value')
    d2 = (forms['ergocalciferol (D2)'].get('absorption_structured') or {}).get('value')
    assert d3 is not None and d2 is not None
    assert d2 < d3, (
        f'D2 ({d2}) must be < D3 ({d3}) per van den Heuvel 2024 (PMID:37865222)'
    )
