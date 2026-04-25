"""Regression test: creatine forms F-class collapse + CEE pro-drug.

Per IQM audit 2026-04-25 Step 4 Batch 14: 8 null-value forms with marketing
spread bio_scores 6-12. Research subagent USED WebFetch on PubMed eutils.

Two major findings:
  1. CREATINE SALTS ARE F-CLASS-EQUIVALENT to monohydrate (~99%). All
     dissociate to deliver identical creatine ion via SLC6A8/CRT
     transporter per Persky 2003 (PMID:12793840) and Jäger 2007
     (PMID:17997838). Counter-ions affect Cmax/Tmax/solubility, NOT
     absolute F.
  2. CREATINE ETHYL ESTER (CEE) HYDROLYZES TO CREATININE PRE-ABSORPTION.
     Three independent papers confirm (Gufford 2013, Giese 2009, Spillane
     2009). Near-zero functional F.

Verified PMIDs:
  PMID:22971354  Jagim 2012 — KA = CrM
  PMID:19228401  Spillane 2009 — CEE less effective in vivo
  PMID:14506619  Brilla 2003 — Mg-chelate (NOT F study)
  PMID:12793840  Persky 2003 — creatine PK review
  PMID:17997838  Jäger 2007 — citrate/pyruvate/CrM head-to-head
  PMID:23957855  Gufford 2013 — CEE pH stability
  PMID:19585404  Giese 2009 — CEE NMR plasma esterase
  PMID:29518030  Alraddadi 2018 — rat F dose-dependent

Misattributions caught:
  • "Schedel 2000 creatine PK" — DOES NOT EXIST → Persky 2003
  • "Greenwood 2003 creatine citrate" — DOES NOT EXIST → Jäger 2007
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


# (form_name, vmin, vmax, basis)
CREATINE_BANDS = [
    # All salts class-equivalent to monohydrate
    ('creatine monohydrate',                      0.95, 0.99, 'gold standard ~99%'),
    ('buffered creatine monohydrate',             0.95, 0.99, 'KA = CrM (Jagim 2012)'),
    ('creatine nitrate',                          0.95, 0.99, 'salt class-equivalent'),
    ('creatine hydrochloride',                    0.95, 0.99, 'HCl 40× soluble, same F'),
    ('creatine citrate',                          0.95, 0.99, 'citrate class-equivalent'),
    ('creatine magnesium chelate',                0.90, 0.99, 'chelate class-equivalent'),
    ('dicreatine malate',                         0.85, 0.99, 'theoretical class-equiv'),
    ('creatine monohydrate ((unspecified))',      0.85, 0.99, 'class-typical F assumed'),
    # CEE separate class — failed pro-drug
    ('creatine ethyl ester',                      0.0,  0.20, 'hydrolyzes to creatinine'),
]


@pytest.mark.parametrize('fname,vmin,vmax,basis', CREATINE_BANDS)
def test_creatine_value_in_band(iqm, fname, vmin, vmax, basis):
    """Each creatine form's struct.value must sit in evidence band."""
    form = iqm['creatine_monohydrate']['forms'].get(fname)
    assert form is not None, f'creatine_monohydrate::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'creatine_monohydrate::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'creatine_monohydrate::{fname}: struct.value={val} outside band '
        f'[{vmin}, {vmax}]. Basis: {basis}'
    )


def test_creatine_salts_class_equivalent(iqm):
    """All creatine salts (HCl, citrate, nitrate, Mg-chelate) and KA-buffered
    must have class-equivalent struct.value (within 0.05) to monohydrate per
    Persky 2003 (PMID:12793840) and Jäger 2007 (PMID:17997838).
    """
    forms = iqm['creatine_monohydrate']['forms']
    monohydrate = (forms['creatine monohydrate'].get('absorption_structured') or {}).get('value')
    salt_names = (
        'buffered creatine monohydrate',
        'creatine nitrate',
        'creatine hydrochloride',
        'creatine citrate',
        'creatine magnesium chelate',
    )
    salt_values = []
    for name in salt_names:
        v = (forms[name].get('absorption_structured') or {}).get('value')
        salt_values.append((name, v))
    for name, v in salt_values:
        assert v is not None and abs(v - monohydrate) <= 0.05, (
            f'{name} ({v}) must be class-equivalent (within 0.05) to '
            f'monohydrate ({monohydrate}) per Persky 2003 (PMID:12793840) — '
            f'all salts dissociate to deliver identical creatine ion'
        )


def test_cee_failed_prodrug(iqm):
    """Creatine ethyl ester must have struct.value ≤ 0.20 per Gufford 2013
    (PMID:23957855) + Giese 2009 (PMID:19585404) + Spillane 2009 (PMID:19228401)
    findings that CEE hydrolyzes to creatinine pre-absorption.
    """
    val = (iqm['creatine_monohydrate']['forms']['creatine ethyl ester']
           .get('absorption_structured') or {}).get('value')
    assert val is not None and val <= 0.20, (
        f'CEE value={val} must be ≤0.20 per Gufford 2013 / Giese 2009 / '
        f'Spillane 2009 — ester hydrolyzes to creatinine pre-absorption, '
        f'near-zero functional F'
    )


def test_no_phantom_schedel_2000_citation(iqm):
    """The non-existent "Schedel 2000" creatine PK citation must not appear
    as a live reference. Replaced with Persky 2003 (PMID:12793840).
    """
    parents = ('creatine_monohydrate',)
    live = re.compile(r'(?<![\"“])Schedel\s*20\d\d(?![\"”])', re.IGNORECASE)
    violations = []
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
            for m in live.finditer(text):
                start = max(0, m.start() - 1)
                end = min(len(text), m.end() + 1)
                window = text[start:end]
                if '"' in window or '“' in window or '”' in window:
                    continue
                violations.append((pid, fname, text[max(0, m.start()-15):m.end()+15]))
    assert not violations, (
        f'Live "Schedel 2000" citation present (DOES NOT EXIST in PubMed). '
        f'Use Persky 2003 (PMID:12793840). {violations}'
    )


def test_no_phantom_greenwood_2003_citrate(iqm):
    """The non-existent "Greenwood 2003 creatine citrate" citation must not
    appear as a live reference. Citrate head-to-head is Jäger 2007.
    """
    form = iqm['creatine_monohydrate']['forms']['creatine citrate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    live = re.compile(r'(?<![\"“])Greenwood\s*2003(?![\"”])', re.IGNORECASE)
    for m in live.finditer(text):
        start = max(0, m.start() - 1)
        end = min(len(text), m.end() + 1)
        window = text[start:end]
        if '"' in window or '“' in window or '”' in window:
            continue
        assert False, (
            f'creatine citrate cites "Greenwood 2003" (DOES NOT EXIST in '
            f'PubMed). Use Jäger 2007 (PMID:17997838). Context: '
            f'{text[max(0, m.start()-30):m.end()+30]}'
        )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM creatine notes."""
    expected_pmids = {
        'PMID:22971354': 'Jagim 2012',
        'PMID:19228401': 'Spillane 2009',
        'PMID:12793840': 'Persky 2003',
        'PMID:17997838': 'Jäger 2007',
        'PMID:23957855': 'Gufford 2013',
        'PMID:19585404': 'Giese 2009',
    }
    full_text = ''
    for form in iqm['creatine_monohydrate']['forms'].values():
        full_text += (form.get('notes') or '') + ' '
        full_text += (form.get('absorption') or '') + ' '
        full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing from creatine notes: {missing}'
    )


def test_cee_creatinine_mechanism_documented(iqm):
    """CEE notes must mention creatinine conversion (pre-absorption hydrolysis)."""
    form = iqm['creatine_monohydrate']['forms']['creatine ethyl ester']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    assert 'creatinine' in text_lower, (
        f'CEE notes must mention creatinine conversion (the pre-absorption '
        f'hydrolysis product per Gufford 2013 / Giese 2009)'
    )
