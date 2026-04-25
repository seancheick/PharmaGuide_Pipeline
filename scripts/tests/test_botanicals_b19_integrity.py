"""Regression test: Batch 19 — fenugreek/SB/hemp/bioflavonoids PK integrity.

Per IQM audit 2026-04-25 Step 4 Batch 19: 17 forms across 4 botanical
parents. Research subagent USED WebFetch on PubMed eutils. Four major
findings:

1. SB BERRY OIL palmitoleic F UNSUPPORTED — Johansson 2000 (PMID:11120446)
   plasma FA UNCHANGED at 5g/4wk supplement dose
2. TESTOFEN Crominex-pattern repeat — Steels 2011 / Wankhede 2016 clinical
   only; Aswar 2010 RAT
3. BIOFLAVONOIDS class-poor F confirmed — Manach 2003 hesperidin 4.1-7.9%,
   Hollman 1995 rutin systemic 1-5%
4. HEMP ORGANIC ≡ COLD-PRESSED — same TG chemistry; certification ≠ F

Verified PMIDs:
  PMID:21312304  Steels 2011 — testofen libido (clinical, NOT PK)
  PMID:30356905  Wankhede 2016 — fenugreek RT (clinical)
  PMID:20878698  Aswar 2010 — furostanol RAT
  PMID:7491892   Hollman 1995 — quercetin ileostomy
  PMID:11151743  Erlund 2000 — quercetin/rutin PK
  PMID:12571654  Manach 2003 — hesperidin urinary 4-8%
  PMID:17103080  Schwab 2006 — hempseed plasma LA/GLA
  PMID:11120446  Johansson 2000 — SB berry oil plasma FA UNCHANGED
  PMID:16968106  Suomela 2006 — SB flavonols
  PMID:35426970  Ollinger 2022 — SB in-vitro
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


# (parent, form, vmin, vmax)
B19_BANDS = [
    # FENUGREEK — class-poor saponin F
    ('fenugreek', 'testofen',                                 0.02, 0.10),
    ('fenugreek', 'fenugreek standardized extract',           0.02, 0.08),
    ('fenugreek', 'fenugreek seed powder',                    0.01, 0.06),
    ('fenugreek', 'fenugreek (unspecified)',                  0.01, 0.06),
    ('fenugreek', 'testosurge extract',                       0.02, 0.08),
    # SEA BUCKTHORN
    ('sea_buckthorn', 'sea buckthorn seed oil',               0.70, 0.95),
    ('sea_buckthorn', 'sea buckthorn berry oil',              0.20, 0.60),
    ('sea_buckthorn', 'sea buckthorn extract',                0.02, 0.10),
    ('sea_buckthorn', 'sea buckthorn powder',                 0.10, 0.50),
    ('sea_buckthorn', 'sea buckthorn (unspecified)',          0.10, 0.50),
    # HEMP SEED OIL
    ('hemp_seed_oil', 'cold-pressed organic',                 0.80, 0.95),
    ('hemp_seed_oil', 'cold-pressed',                         0.80, 0.95),
    ('hemp_seed_oil', 'refined',                              0.65, 0.88),
    ('hemp_seed_oil', 'hemp seed oil (unspecified)',          0.65, 0.88),
    # BIOFLAVONOIDS — CLASS-POOR
    ('bioflavonoids', 'citrus complex',                        0.03, 0.10),
    ('bioflavonoids', 'hesperidin-rich',                       0.04, 0.08),
    ('bioflavonoids', 'rutin complex',                         0.01, 0.07),
    ('bioflavonoids', 'bioflavonoids (unspecified)',           0.01, 0.10),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax', B19_BANDS)
def test_b19_value_in_band(iqm, pid, fname, vmin, vmax):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]'
    )


def test_bioflavonoids_class_poor_F(iqm):
    """All bioflavonoid forms must have struct.value ≤ 0.10 — class-poor F
    per Manach 2003 (PMID:12571654, hesperidin 4-8%) and Hollman 1995
    (PMID:7491892, rutin systemic 1-5%).
    """
    forms = iqm['bioflavonoids']['forms']
    violations = []
    for fname, form in forms.items():
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        if v > 0.10:
            violations.append((fname, v))
    assert not violations, (
        f'Bioflavonoid forms with struct.value > 0.10 violate class-poor '
        f'F evidence: {violations}'
    )


def test_fenugreek_class_poor_saponin_F(iqm):
    """All fenugreek forms must have struct.value ≤ 0.10 — class-poor
    furostanol saponin F (~1-5% per saponin biology). NO human PK exists.
    """
    forms = iqm['fenugreek']['forms']
    violations = []
    for fname, form in forms.items():
        v = (form.get('absorption_structured') or {}).get('value')
        if v is None:
            continue
        if v > 0.10:
            violations.append((fname, v))
    assert not violations, (
        f'Fenugreek forms with struct.value > 0.10 violate class-poor '
        f'saponin F: {violations}'
    )


def test_sb_berry_oil_palmitoleic_qualified(iqm):
    """SB berry oil notes must qualify the palmitoleic claim per Johansson
    2000 (PMID:11120446) finding that plasma FA UNCHANGED at 5g/4wk.
    """
    form = iqm['sea_buckthorn']['forms']['sea buckthorn berry oil']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('plasma fa unchanged', 'plasma fatty acids unchanged',
                    'plasma 16:1n-7 unchanged', 'unchanged at 5g',
                    'johansson 2000', '11120446', 'overstated', 'composition not')
    assert any(p in text_lower for p in flag_phrases), (
        f'SB berry oil must qualify palmitoleic claim per Johansson 2000 '
        f'(PMID:11120446). Text: {text[:300]}'
    )


def test_hemp_organic_equivalent_to_cold_pressed(iqm):
    """Hemp organic and cold-pressed must have equal struct.value per
    class-equivalence (same TG chemistry; certification ≠ F).
    """
    forms = iqm['hemp_seed_oil']['forms']
    organic = (forms['cold-pressed organic'].get('absorption_structured') or {}).get('value')
    cold_pressed = (forms['cold-pressed'].get('absorption_structured') or {}).get('value')
    assert organic == cold_pressed, (
        f'hemp organic ({organic}) must equal cold-pressed ({cold_pressed}) — '
        f'same TG chemistry; certification is not a F differentiator'
    )


def test_testofen_no_pk_qualified(iqm):
    """Testofen notes must qualify absence of human PK (Crominex-pattern).
    Steels 2011 / Wankhede 2016 are clinical-endpoint trials; Aswar 2010 is RAT.
    """
    form = iqm['fenugreek']['forms']['testofen']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('no pk', 'not pk', 'clinical endpoint', 'no human pk',
                    'no published pk', 'crominex pattern')
    assert any(p in text_lower for p in flag_phrases), (
        f'testofen must qualify absence of human PK. Text: {text[:300]}'
    )


def test_aswar_2010_rat_qualified(iqm):
    """Any reference to Aswar 2010 (PMID:20878698) must be qualified as
    RAT-only.
    """
    forms = iqm['fenugreek']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        if 'aswar 2010' in text_lower or 'pmid:20878698' in text_lower:
            assert 'rat' in text_lower, (
                f'fenugreek::{fname} cites Aswar 2010 without qualifying '
                f'as RAT-only. Text: {text[:300]}'
            )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must appear in IQM notes."""
    expected_pmids = {
        'PMID:11120446': 'Johansson 2000 SB berry oil',
        'PMID:12571654': 'Manach 2003 hesperidin',
        'PMID:7491892':  'Hollman 1995 rutin ileostomy',
    }
    full_text = ''
    for pid in ('fenugreek', 'sea_buckthorn', 'hemp_seed_oil', 'bioflavonoids'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )
