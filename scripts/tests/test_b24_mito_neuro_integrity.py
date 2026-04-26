"""Regression test: Batch 24 — mitochondrial / neuro / category errors.

Per IQM audit 2026-04-25 Step 4 Batch 24: 26 forms across 12 parents.
Six framework findings:

1. PSYLLIUM = 5TH CATEGORY ERROR. Soluble fiber not systemically
   absorbed. Marlett 2003 (PMID:12749348) — gel fraction RESISTS
   fermentation; mechanism is bile-acid binding + gel formation.

2. SUPEROXIDE DISMUTASE = 6TH CATEGORY ERROR — NEW PATTERN: protein
   digestion barrier. Vouldoukis 2004 (PMID:15742357): GliSODin animal
   data only; unprotected SOD digested by gastric pepsin. Pattern
   applies broadly to oral protein/enzyme supplements.

3. GABA BBB BARRIER PATTERN — NEW. Boonstra 2015 (PMID:26500584):
   BBB crossing unproven. New forms set to PK-strict 0.05; companions
   pending Dr Pham E1.

4. I3C → DIM CLASS-EQUIVALENCE. Reed 2006 (PMID:17164373): I3C
   undetectable in plasma; only DIM detected. Sanderson 2001
   (PMID:11294972): acid-condensation in stomach.

5. SILYCHRISTIN/SILYDIANIN ↔ SILYBIN CLASS-EQUIVALENCE. Calani 2012
   (PMID:23072776): silymarin total F 0.45±0.28% across all flavanolignans.

6. LIPOSOMAL EVIDENCE-THIN APPLIED 5×: ALA, L-carnitine, melatonin, GABA.

GHOST PMIDS CAUGHT (9):
  • DeMuro melatonin: 10843432 (mustard allergy) → 10883420
  • Boonstra GABA:    26617552 (belief networks) → 26500584
  • Vouldoukis SOD:   14975508 (odontogenic carcinoma) → 15742357
  • Reed DIM:         18483339 (aspirin/NSAIDs) → 18843002
  • Lee EGCG:         11935256 (nNOS in ALS mice) → Chow 11205489
  • Chow EGCG:        11489775 (biventricular repair) → 11205489
  • Wenzel silymarin: 12888381 (colon-cancer staging) → 23072776
  • Eriksen phycocyanin: 18509687 (apoC-I) → Donadio 34836173
  • Anderton I3C:     15470159 (cigarette eNOS) — fabricated
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
B24_BANDS_VALUED = [
    # alpha_lipoic_acid
    ('alpha_lipoic_acid', 'granulated alpha-lipoic acid',          0.25, 0.35, 'Teichert 2003'),
    ('alpha_lipoic_acid', 'alpha lipoic acid (unspecified)',       0.20, 0.35, 'racemic baseline'),
    # l_carnitine
    ('l_carnitine', 'l-carnitine (unspecified)',                   0.14, 0.18, 'Rebouche 2004'),
    # alpha_ketoglutarate
    ('alpha_ketoglutarate', 'alpha-ketoglutarate (unspecified)',   0.15, 0.30, 'Mittal 2010'),
    ('alpha_ketoglutarate', 'ornithine alpha-ketoglutarate',       0.20, 0.35, 'Le Bricon 1996'),
    # melatonin
    ('melatonin', 'melatonin (unspecified)',                       0.10, 0.20, 'DeMuro 2000'),
    # gaba — PK-strict
    ('gaba', 'gaba (gamma-aminobutyric acid) (unspecified)',       0.02, 0.10, 'Boonstra 2015 BBB'),
    # green_tea_extract
    ('green_tea_extract', 'matcha powder',                         0.005, 0.02, 'Henning 2004'),
    ('green_tea_extract', 'green tea extract (unspecified)',       0.005, 0.02, 'Chow 2001'),
    # milk_thistle
    ('milk_thistle', 'milk thistle (unspecified)',                 0.001, 0.01, 'Calani 2012'),
    ('milk_thistle', 'silychristin (minor flavonolignan)',         0.001, 0.01, 'Calani 2012'),
    ('milk_thistle', 'silydianin (minor flavonolignan)',           0.001, 0.01, 'Calani 2012'),
    # diindolylmethane
    ('diindolylmethane', 'diindolylmethane (dim)',                 0.03, 0.10, 'Reed 2008'),
    ('diindolylmethane', 'indole-3-carbinol (i3c)',                0.03, 0.10, 'I3C→DIM class'),
    # spirulina
    ('spirulina', 'phycocyanin extract (spirulina)',               0.05, 0.15, 'Donadio 2021'),
]

B24_NULL_FORMS = [
    # liposomal evidence-thin (4)
    ('alpha_lipoic_acid', 'liposomal alpha-lipoic acid',                       'liposomal-thin'),
    ('l_carnitine', 'liposomal l-carnitine',                                   'liposomal-thin'),
    ('melatonin', 'liposomal melatonin',                                       'liposomal-thin'),
    ('gaba', 'liposomal gaba',                                                 'liposomal-thin+BBB'),
    # 5th category error: psyllium (2)
    ('psyllium', 'psyllium seed',                                              '5th category-error'),
    ('psyllium', 'psyllium (unspecified)',                                     '5th category-error'),
    # 6th category error: SOD protein digestion (2)
    ('superoxide_dismutase', 'sod supplement',                                 '6th category-error'),
    ('superoxide_dismutase', 'superoxide dismutase (sod) (unspecified)',       '6th category-error'),
    # framework mismatch: digestive_enzymes (2)
    ('digestive_enzymes', 'oxidized enzymes',                                  'oxidation-deactivated'),
    ('digestive_enzymes', 'digestive enzymes (unspecified)',                   'framework-mismatch'),
    # composite food pending: spirulina (1)
    ('spirulina', 'spirulina (unspecified)',                                   'composite-food-pending'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B24_BANDS_VALUED)
def test_b24_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname,reason', B24_NULL_FORMS)
def test_b24_null_form(iqm, pid, fname, reason):
    """Each null form must have struct.value=null per its framework reason."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, (
        f'{pid}::{fname} value={val} must be null — reason: {reason}'
    )


def test_psyllium_5th_category_error_documented(iqm):
    """Psyllium null forms must document 5th category-error / fiber mechanism."""
    forms = [
        ('psyllium', 'psyllium seed'),
        ('psyllium', 'psyllium (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('category error', 'category_error', '5th category',
                        'fiber', 'bile-acid', 'gel-forming', 'not systemically',
                        '12749348', 'marlett')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} must document 5th category-error / fiber '
            f'mechanism. Text: {text[:300]}'
        )


def test_sod_6th_category_error_documented(iqm):
    """SOD null forms must document 6th category-error (NEW protein-digestion
    barrier pattern).
    """
    forms = [
        ('superoxide_dismutase', 'sod supplement'),
        ('superoxide_dismutase', 'superoxide dismutase (sod) (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('category error', 'category_error', '6th category',
                        'protein digestion', 'pepsin', 'gliadin',
                        'enzyme protein', '15742357', 'vouldoukis')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} must document 6th category-error / protein '
            f'digestion barrier. Text: {text[:300]}'
        )


def test_i3c_dim_class_equivalence(iqm):
    """I3C and DIM must be class-equivalent (within 0.05) per Reed 2006
    (PMID:17164373) — I3C undetectable in plasma; only DIM detected.
    """
    forms = iqm['diindolylmethane']['forms']
    dim = (forms['diindolylmethane (dim)'].get('absorption_structured') or {}).get('value')
    i3c = (forms['indole-3-carbinol (i3c)'].get('absorption_structured') or {}).get('value')
    assert dim is not None and i3c is not None
    assert abs(dim - i3c) <= 0.05, (
        f'I3C ({i3c}) must equal DIM ({dim}) within 0.05 — I3C undetectable '
        f'in plasma; only DIM detected as systemic species '
        f'(PMID:17164373, PMID:11294972 acid-condensation in stomach).'
    )


def test_silychristin_silydianin_class_equivalent_to_silybin(iqm):
    """silychristin/silydianin must be class-equivalent (within 0.02) per
    Calani 2012 (PMID:23072776) — silymarin total F 0.45±0.28% across all
    flavanolignans including silybin.
    """
    forms = iqm['milk_thistle']['forms']
    silybin = (forms['silybin (isolated)'].get('absorption_structured') or {}).get('value')
    silychristin = (forms['silychristin (minor flavonolignan)'].get('absorption_structured') or {}).get('value')
    silydianin = (forms['silydianin (minor flavonolignan)'].get('absorption_structured') or {}).get('value')
    assert silybin is not None
    for nm, v in [('silychristin', silychristin), ('silydianin', silydianin)]:
        assert v is not None, f'{nm} struct.value should be populated'
        assert abs(v - silybin) <= 0.02, (
            f'{nm} ({v}) must be class-equivalent to silybin ({silybin}) '
            f'within 0.02 — same poor-F flavanolignan class '
            f'(PMID:23072776).'
        )


def test_liposomal_evidence_thin_documented_b24(iqm):
    """Batch 24 liposomal forms must document evidence-thin status."""
    liposomal_forms = [
        ('alpha_lipoic_acid', 'liposomal alpha-lipoic acid'),
        ('l_carnitine', 'liposomal l-carnitine'),
        ('melatonin', 'liposomal melatonin'),
        ('gaba', 'liposomal gaba'),
    ]
    for pid, fname in liposomal_forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('evidence-thin', 'no human pk', 'no head-to-head',
                        'no published', 'unsupported', 'no comparator',
                        'liposomal-thin', 'liposomal evidence')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} liposomal must document evidence-thin status. '
            f'Text: {text[:300]}'
        )


def test_no_phantom_demuro_10843432(iqm):
    """Wrong "DeMuro 2000 PMID:10843432" must not appear as live citation —
    actually mustard allergy in children paper. Correct: PMID:10883420.
    """
    form = iqm['melatonin']['forms']['melatonin (unspecified)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    # Must cite correct DeMuro PMID
    assert '10883420' in text, (
        f'melatonin (unspecified) must cite DeMuro 2000 PMID:10883420. '
        f'Text: {text[:400]}'
    )
    # If wrong PMID present, must be flagged
    if 'PMID:10843432' in text or '10843432' in text:
        assert any(neg in text.lower() for neg in
                   ('not demuro', 'mustard', 'ghost', 'misattribut', 'wrong',
                    'is not')), (
            f'PMID:10843432 cited without ghost-trap qualification. '
            f'Use 10883420.'
        )


def test_no_phantom_boonstra_26617552(iqm):
    """Wrong "Boonstra 2015 PMID:26617552" must not appear as live citation —
    actually belief networks. Correct: PMID:26500584.
    """
    form = iqm['gaba']['forms']['gaba (gamma-aminobutyric acid) (unspecified)']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    assert '26500584' in text, (
        f'gaba (unspecified) must cite Boonstra 2015 PMID:26500584. '
        f'Text: {text[:400]}'
    )
    if 'PMID:26617552' in text or '26617552' in text:
        assert any(neg in text.lower() for neg in
                   ('not boonstra', 'belief', 'ghost', 'misattribut', 'wrong',
                    'is not')), (
            f'PMID:26617552 cited without ghost-trap qualification.'
        )


def test_class_authority_pmids_introduced_b24(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:14551180': 'Teichert 2003 ALA',
        'PMID:15591001': 'Rebouche 2004 carnitine',
        'PMID:10883420': 'DeMuro 2000 melatonin',
        'PMID:26500584': 'Boonstra 2015 GABA',
        'PMID:23072776': 'Calani 2012 silymarin',
        'PMID:17164373': 'Reed 2006 I3C',
        'PMID:12749348': 'Marlett 2003 psyllium',
        'PMID:15742357': 'Vouldoukis 2004 SOD',
    }
    full_text = ''
    for pid in ('alpha_lipoic_acid', 'l_carnitine', 'melatonin', 'gaba',
                'milk_thistle', 'diindolylmethane', 'psyllium',
                'superoxide_dismutase', 'green_tea_extract',
                'alpha_ketoglutarate', 'spirulina', 'digestive_enzymes'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_sixth_category_error_pattern(iqm):
    """Six category-error parent groups now established: manuka (B18),
    organ extracts (B20), prebiotics (B22), slippery elm (B23), psyllium
    (B24), SOD (B24 — new protein-digestion pattern).
    """
    category_error_forms = [
        ('manuka_honey', 'umf 15+ / mgo 514+'),
        ('organ_extracts', 'grass-fed desiccated'),
        ('inulin', 'inulin (unspecified)'),
        ('larch_arabinogalactan', 'larch arabinogalactan powder'),
        ('slippery_elm', 'standardized extract (mucilage)'),
        ('psyllium', 'psyllium seed'),
        ('psyllium', 'psyllium (unspecified)'),
        ('superoxide_dismutase', 'sod supplement'),
        ('superoxide_dismutase', 'superoxide dismutase (sod) (unspecified)'),
    ]
    for pid, fname in category_error_forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'{pid}::{fname} value={v} should be null per category-error.'
        )


def test_pending_dr_pham_review_documented(iqm):
    """Forms held pending Dr Pham review (E1/E2/E3) must reference the
    review document so it's clear they're awaiting medical signoff.
    """
    pending_forms = [
        ('gaba', 'gaba (gamma-aminobutyric acid) (unspecified)'),
        ('spirulina', 'spirulina (unspecified)'),
        ('digestive_enzymes', 'digestive enzymes (unspecified)'),
    ]
    for pid, fname in pending_forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('dr pham', 'pending', 'review', 'e1', 'e2', 'e3')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} should reference Dr Pham review (E1/E2/E3). '
            f'Text: {text[:300]}'
        )
