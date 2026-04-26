"""Regression test: vitamin C and E PK + class findings.

Per IQM audit 2026-04-25 Step 4 Batch 13: 10 null-value forms across
vitamin C and E parents. Research subagent USED WebFetch on PubMed eutils.

Three class findings:
  1. Vit C whole-food superiority is POST-absorption (bioflavonoid
     retention/recycling) NOT absolute F. SVCT1 saturable across sources.
  2. Tocotrienols are SEPARATE class from tocopherols — α-TTP affinity
     ~12% of RRR-α-tocopherol (Hosomi 1997 PMID:9199513), poor retention.
  3. Pre-absorption hydrolysis recurs for tocopheryl succinate (F tracks
     d-alpha-tocopherol; same as ascorbyl palmitate, dl-succinate).

Verified PMIDs:
  PMID:8623000   Levine 1996 PNAS — vit C PK men
  PMID:11504949  Levine 2001 PNAS — vit C PK women
  PMID:15068981  Padayatty 2004 Ann Intern Med — oral vs IV
  PMID:24067392  Carr & Vissers 2013 — synthetic vs food vit C F equiv
  PMID:24169506  Carr 2013 — kiwifruit RCT
  PMID:22040889  Uchida 2011 — acerola AUC trend NS
  PMID:15380894  Viscovich 2004 — slow-release vit C in smokers
  PMID:9199513   Hosomi 1997 — α-TTP affinity table
  PMID:9537614   Burton 1998 — natural RRR ~2× retention
  PMID:15288344  Yap & Yuen 2004 — tocotrienol human SEDDS
  PMID:18806966  Rasool 2008 — tocotrienol human plasma

Misattributions caught:
  • "Yap 2003" PMID:12625867 — rat study, not human
  • "Carr 2018" — DOES NOT EXIST in PubMed
  • "Padayatty/Levine 2001" PMID:11401949 — wrong topic
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


# (parent, form, vmin, vmax, basis)
VITCE_BANDS = [
    # Vit C
    ('vitamin_c', 'camu camu extract',           0.60, 0.80, 'whole-food = SVCT1-class'),
    ('vitamin_c', 'acerola cherry extract',      0.65, 0.80, 'Uchida 2011 NS AUC trend'),
    ('vitamin_c', 'potassium ascorbate',         0.70, 0.85, 'class-match ascorbate salts'),
    ('vitamin_c', 'zinc ascorbate',              0.70, 0.85, 'class-match ascorbate salts'),
    ('vitamin_c', 'slow-release vitamin C',      0.65, 0.85, 'Viscovich 2004 reduced fluctuation'),
    # Vit E
    ('vitamin_e', 'mixed tocopherols',           0.65, 0.85, 'natural mixed; α-TTP retains α-form'),
    ('vitamin_e', 'd-alpha-tocopherol',          0.75, 0.90, 'Burton 1998 RRR ~2× retention'),
    ('vitamin_e', 'tocotrienols',                0.30, 0.55, 'Yap 2004 + Hosomi 1997 — separate class'),
    ('vitamin_e', 'd-alpha-tocopheryl succinate', 0.55, 0.80, 'ester hydrolyzed pre-absorption'),
    ('vitamin_e', 'vitamin E from wheat germ oil', 0.65, 0.85, 'whole-food natural mix'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', VITCE_BANDS)
def test_vitce_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each vit C/E form's struct.value must sit in evidence band."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_tocotrienols_separate_class_from_tocopherols(iqm):
    """Tocotrienols must rank significantly LOWER than d-alpha-tocopherol per
    Hosomi 1997 (PMID:9199513) finding that α-tocotrienol α-TTP affinity is
    ~12% of RRR-α-tocopherol → poor tissue retention.
    """
    forms = iqm['vitamin_e']['forms']
    tocotrienols = (forms['tocotrienols'].get('absorption_structured') or {}).get('value')
    d_alpha = (forms['d-alpha-tocopherol'].get('absorption_structured') or {}).get('value')
    assert tocotrienols is not None and d_alpha is not None
    assert tocotrienols < d_alpha - 0.30, (
        f'tocotrienols ({tocotrienols}) must rank significantly lower than '
        f'd-alpha-tocopherol ({d_alpha}) per Hosomi 1997 (PMID:9199513) '
        f'α-TTP affinity finding. Tocotrienols are a separate class with '
        f'poor tissue retention, not a "premium" tocopherol form.'
    )


def test_natural_d_alpha_dominates_synthetic(iqm):
    """Per Burton 1998 (PMID:9537614), natural RRR-α has ~2× plasma/tissue
    retention vs all-rac. struct.value(d-alpha) > struct.value(dl-alpha).
    """
    forms = iqm['vitamin_e']['forms']
    d_alpha = (forms['d-alpha-tocopherol'].get('absorption_structured') or {}).get('value')
    dl_alpha = (forms['dl-alpha-tocopherol'].get('absorption_structured') or {}).get('value')
    assert d_alpha is not None and dl_alpha is not None
    assert d_alpha > dl_alpha, (
        f'natural d-alpha-tocopherol ({d_alpha}) must exceed synthetic '
        f'dl-alpha-tocopherol ({dl_alpha}) per Burton 1998 (PMID:9537614)'
    )


def test_ascorbate_salts_class_consistent(iqm):
    """All ascorbate salts (Ca, Na, Mg, K, Zn) deliver identical ascorbate
    ion → must have similar struct.value (within 0.05). Per Levine 1996.
    """
    forms = iqm['vitamin_c']['forms']
    salt_names = ('calcium ascorbate', 'sodium ascorbate', 'magnesium ascorbate',
                  'potassium ascorbate', 'zinc ascorbate')
    salt_values = []
    for name in salt_names:
        f = forms.get(name)
        if not f:
            continue
        v = (f.get('absorption_structured') or {}).get('value')
        if v is not None:
            salt_values.append((name, v))
    if len(salt_values) < 2:
        return
    vals = [v for _, v in salt_values]
    spread = max(vals) - min(vals)
    assert spread <= 0.05, (
        f'ascorbate salts must be class-consistent (within 0.05) per Levine '
        f'1996 (PMID:8623000): salts dissociate to identical ascorbate ion. '
        f'Current spread: {spread:.3f}, values: {salt_values}'
    )


def test_camu_acerola_not_above_ascorbic_acid(iqm):
    """Per Carr & Vissers 2013 (PMID:24067392) and Uchida 2011 (PMID:22040889),
    whole-food vit C does NOT exceed ascorbic acid in absolute F. The
    SVCT1 transporter is rate-limiting.
    """
    forms = iqm['vitamin_c']['forms']
    aa = (forms['ascorbic acid'].get('absorption_structured') or {}).get('value')
    camu = (forms['camu camu extract'].get('absorption_structured') or {}).get('value')
    acerola = (forms['acerola cherry extract'].get('absorption_structured') or {}).get('value')
    # Within 0.05 either direction is acceptable; whole-food cannot dramatically exceed
    assert camu <= aa + 0.05, (
        f'camu camu ({camu}) must not exceed ascorbic acid ({aa}) by >0.05 — '
        f'SVCT1 saturable per Carr & Vissers 2013 (PMID:24067392)'
    )
    assert acerola <= aa + 0.05, (
        f'acerola ({acerola}) must not exceed ascorbic acid ({aa}) by >0.05 — '
        f'Uchida 2011 (PMID:22040889) AUC trend was NS'
    )


def test_no_phantom_yap_2003_human_citation(iqm):
    """"Yap 2003 tocotrienol PK" PMID:12625867 is RAT study, not human.
    If cited, must be flagged as rat-only.
    """
    form = iqm['vitamin_e']['forms']['tocotrienols']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    if 'PMID:12625867' in text:
        # Must be flagged as rat-only
        assert 'rat' in text.lower(), (
            f'PMID:12625867 cited but not flagged as RAT study. The actual '
            f'human PK reference is Yap & Yuen 2004 (PMID:15288344, SEDDS). '
            f'Notes: {text[:300]}'
        )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs from Batch 13 must each appear in the IQM."""
    expected_pmids = {
        'PMID:24067392': 'Carr & Vissers 2013',
        'PMID:22040889': 'Uchida 2011 acerola',
        'PMID:9199513':  'Hosomi 1997 α-TTP',
        'PMID:9537614':  'Burton 1998 RRR retention',
        'PMID:15288344': 'Yap & Yuen 2004 tocotrienol',
    }
    parents = ('vitamin_c', 'vitamin_e')
    full_text = ''
    for pid in parents:
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing from vit C/E notes: {missing}'
    )


def test_succinate_ester_pre_absorption_pattern(iqm):
    """d-alpha-tocopheryl succinate must reflect pre-absorption hydrolysis
    pattern — F tracks d-alpha-tocopherol parent, between dl-succinate and
    free d-alpha.
    """
    forms = iqm['vitamin_e']['forms']
    d_alpha_succinate = (forms['d-alpha-tocopheryl succinate']
                         .get('absorption_structured') or {}).get('value')
    dl_succinate = (forms['dl-alpha-tocopheryl succinate']
                    .get('absorption_structured') or {}).get('value')
    d_alpha = (forms['d-alpha-tocopherol']
               .get('absorption_structured') or {}).get('value')
    assert all(v is not None for v in (d_alpha_succinate, dl_succinate, d_alpha))
    assert dl_succinate < d_alpha_succinate < d_alpha + 0.05, (
        f'd-alpha-tocopheryl succinate ({d_alpha_succinate}) should sit '
        f'between dl-succinate ({dl_succinate}) and free d-alpha ({d_alpha}) '
        f'— ester hydrolyzed pre-absorption, F tracks d-alpha parent'
    )
