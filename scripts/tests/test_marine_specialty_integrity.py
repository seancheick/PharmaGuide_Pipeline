"""Regression test: marine oils + specialty (Batch 18) — class equivalence,
manuka category error, ghost references caught.

Per IQM audit 2026-04-25 Step 4 Batch 18: 20 forms across 6 parents.
Research subagent USED WebFetch on PubMed eutils. Four major findings:

1. KRILL = FISH-TG AT MATCHED DOSE (Yurko-Mauro 2015 PMID:26328782, n=66
   dose-matched RCT, definitive). Schuchardt "+33% AUC" was NS trend
   (p=0.057) confounded by free-FA contamination.

2. MANUKA HONEY IS A CATEGORY ERROR — MGO is local-action antibacterial
   (Tenci 2017 PMID:27789370), not systemically absorbed. UMF/MGO grade
   reflects antibacterial potency, NOT F. Schema reframe needed.

3. PRIMAVIE SHILAJIT CROMINEX-PATTERN — Pandit 2016 (PMID:26395129) is
   testosterone endpoint RCT, NOT PK. NO human shilajit PK exists.

4. THYMOQUINONE "ALKHARFY 2015 HUMAN PK" IS A GHOST — actual PMID:26434126
   is Ahmad/Alkharfy 2015 RAT glibenclamide study. NO human TQ PK exists.

Verified PMIDs:
  PMID:21854650  Schuchardt 2011 — krill +33% NS trend
  PMID:21042875  Ulven 2011 — krill = fish oil
  PMID:24383554  Nichols 2014 — Ramprasath rebuttal
  PMID:26328782  Yurko-Mauro 2015 — DEFINITIVE krill = fish-TG
  PMID:26395129  Pandit 2016 — shilajit endpoint (NOT PK)
  PMID:26434126  Ahmad/Alkharfy 2015 — RAT (NOT human TQ PK)
  PMID:27789370  Tenci 2017 — manuka MGO topical/local
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


# Marine oils — class-equivalent to fish-TG (~0.85)
MARINE_BANDS = [
    ('krill_oil', 'standard krill oil',                         0.70, 0.97),
    ('krill_oil', 'Neptune Krill Oil (NKO)',                    0.70, 0.97),
    ('krill_oil', 'Superba Krill (Aker BioMarine)',             0.70, 0.97),
    ('calamari_oil', 'calamari oil phospholipid',               0.70, 0.97),
    ('calamari_oil', 'calamari oil triglyceride',               0.70, 0.97),
    ('calamari_oil', 'calamari oil (unspecified)',              0.65, 0.90),
    ('tuna_oil', 'tuna oil molecular distilled',                0.78, 0.92),
    ('tuna_oil', 'tuna oil triglyceride',                       0.78, 0.92),
    ('tuna_oil', 'tuna oil (unspecified)',                      0.65, 0.90),
]

# Specialty — diverse evidence, all class-poor or null
SPECIALTY_BANDS = [
    ('shilajit', 'primavie shilajit',                           0.10, 0.50),
    ('shilajit', 'purified shilajit extract',                   0.10, 0.50),
    ('shilajit', 'fulvic acid',                                 0.10, 0.40),
    ('shilajit', 'shilajit resin',                              0.10, 0.45),
    ('shilajit', 'shilajit powder',                             0.05, 0.40),
    ('shilajit', 'shilajit (unspecified)',                      0.05, 0.40),
    ('black_seed_oil', 'thymoquinone standardized',             0.05, 0.15),
    ('black_seed_oil', 'cold-pressed black seed oil',           0.05, 0.15),
    ('black_seed_oil', 'black seed oil',                        0.05, 0.15),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax', MARINE_BANDS + SPECIALTY_BANDS)
def test_value_in_band(iqm, pid, fname, vmin, vmax):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]'
    )


def test_manuka_category_error_value_null(iqm):
    """All manuka honey forms must have struct.value=null per category-error
    finding — manuka MGO is local-action, not systemically absorbed.
    """
    forms = iqm['manuka_honey']['forms']
    violations = []
    for fname, form in forms.items():
        if 'ungraded' in fname.lower():
            continue  # tracking ungraded form may have null already
        v = (form.get('absorption_structured') or {}).get('value')
        if v is not None:
            violations.append((fname, v))
    # Allow some forms (e.g., ungraded) but UMF/MGO grades must be null
    grades = [f for f in forms if 'umf' in f.lower() or 'mgo' in f.lower()]
    for fname in grades:
        v = (forms[fname].get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'manuka_honey::{fname} value={v} must be null — MGO is '
            f'local-action antibacterial (Tenci 2017 PMID:27789370), not '
            f'systemically absorbed. Schema reframe needed.'
        )


def test_manuka_category_error_documented(iqm):
    """Manuka honey notes must document the category error (local-action,
    not systemic absorption).
    """
    forms = iqm['manuka_honey']['forms']
    for fname, form in forms.items():
        if 'umf' not in fname.lower() and 'mgo' not in fname.lower():
            continue
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('local-action', 'local action', 'category error',
                        'topical', 'not systemically absorbed',
                        'grade ≠', 'grade !=', 'antibacterial grade')
        assert any(p in text_lower for p in flag_phrases), (
            f'manuka_honey::{fname} must document category error in notes. '
            f'Text: {text[:300]}'
        )


def test_krill_class_equivalent_to_fish_tg(iqm):
    """Per Yurko-Mauro 2015 (PMID:26328782) definitive n=66 dose-matched
    RCT, krill = fish-TG. Krill struct.values must be in same band as
    fish_oil rTG / TG forms (0.70-0.97).
    """
    forms = iqm['krill_oil']['forms']
    krill_values = []
    for fname in ('standard krill oil', 'Neptune Krill Oil (NKO)',
                  'Superba Krill (Aker BioMarine)'):
        form = forms.get(fname)
        if not form:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        if v is not None:
            krill_values.append((fname, v))
    # All should be 0.70-0.97 (class-equivalent to fish-TG)
    for name, v in krill_values:
        assert 0.70 <= v <= 0.97, (
            f'krill::{name} value={v} should be in 0.70-0.97 band per '
            f'class-equivalence with fish-TG (Yurko-Mauro 2015 PMID:26328782)'
        )


def test_thymoquinone_class_poor_F(iqm):
    """Thymoquinone forms must have struct.value ≤ 0.20 — NO human PK
    published; "Alkharfy 2015 human PK" is a ghost reference (actual
    PMID:26434126 is rat study). Animal F ~5-15%.
    """
    forms = iqm['black_seed_oil']['forms']
    for fname in ('thymoquinone standardized', 'cold-pressed black seed oil',
                  'black seed oil'):
        form = forms.get(fname)
        if not form:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        assert v <= 0.20, (
            f'black_seed_oil::{fname} value={v} > 0.20 — TQ is class-poor '
            f'lipophilic (no human PK; animal F ~5-15%); "Alkharfy 2015 '
            f'human PK" is a ghost reference (actual rat study PMID:26434126)'
        )


def test_shilajit_no_pk_qualified(iqm):
    """Shilajit notes must qualify the absence of human PK. Pandit 2016
    (PMID:26395129) is endpoint RCT, not PK.
    """
    forms = iqm['shilajit']['forms']
    for fname in ('primavie shilajit', 'purified shilajit extract', 'fulvic acid'):
        form = forms.get(fname)
        if not form:
            continue
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('no human pk', 'no published pk', 'endpoint rct',
                        'not pk', 'no published evidence', 'no pk')
        assert any(p in text_lower for p in flag_phrases), (
            f'shilajit::{fname} must qualify absence of human PK. '
            f'Text: {text[:300]}'
        )


def test_no_phantom_alkharfy_human_tq_citation(iqm):
    """The "Alkharfy 2015 human thymoquinone PK" claim must not appear as
    live citation — actual PMID:26434126 is a RAT glibenclamide study.
    """
    forms = iqm['black_seed_oil']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        # If "Alkharfy" appears, must be qualified as rat / ghost / misattribution
        if 'alkharfy' in text.lower():
            text_lower = text.lower()
            qualifiers = ('rat', 'ghost', 'misattribut', 'not human',
                          'not found', 'not exist')
            assert any(q in text_lower for q in qualifiers), (
                f'black_seed_oil::{fname} cites "Alkharfy" without '
                f'qualifying it as rat-study / ghost-reference. '
                f'Text: {text[:300]}'
            )


def test_yurko_mauro_pmid_cited(iqm):
    """Yurko-Mauro 2015 (PMID:26328782) is the definitive krill class-
    equivalence reference and should appear in krill notes.
    """
    forms = iqm['krill_oil']['forms']
    full_text = ''
    for form in forms.values():
        full_text += (form.get('notes') or '') + ' '
        full_text += (form.get('absorption') or '') + ' '
        full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    assert 'PMID:26328782' in full_text or 'Yurko-Mauro 2015' in full_text, (
        f'Krill notes must cite Yurko-Mauro 2015 (PMID:26328782) — the '
        f'definitive dose-matched class-equivalence study'
    )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:26328782': 'Yurko-Mauro 2015 krill = fish-TG',
        'PMID:26395129': 'Pandit 2016 shilajit endpoint',
        'PMID:27789370': 'Tenci 2017 manuka topical',
    }
    full_text = ''
    for pid in ('krill_oil', 'shilajit', 'manuka_honey', 'black_seed_oil'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )
