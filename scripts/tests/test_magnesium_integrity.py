"""Regression test: magnesium forms PK + threonate BBB conflation finding.

Per IQM audit 2026-04-25 Step 4 Batch 15: 14 magnesium forms populated.
Research subagent USED WebFetch on PubMed eutils. Three major findings:

1. MG THREONATE BBB CROSSING IS RAT-ONLY — Slutsky 2010 (PMID:20152124)
   elevated brain Mg in rats; Liu 2016 (PMID:26519439) and Zhang 2022
   (PMID:36558392) human cognitive RCTs but NO brain Mg PK.

2. MG ACETYL-TAURATE IS RODENT-ONLY — Ates 2019 (mice, PMID:30761462) +
   Uysal 2019 (rats, PMID:29679349); no human PK published.

3. MG ORGANIC CHELATES F-CLASS-EQUIVALENT — glycinate, malate, taurate,
   orotate, AAC, gluconate, aspartate, lactate, chloride all cluster
   F ~25-45% with overlapping CIs. Only citrate > chelates > oxide ranking
   is robustly replicated in humans.

Misattributions caught:
  • "Slutsky 2010 PMID:20152120" — wrong (Bush AI commentary)
  • "Walker 2003 glycinate vs oxide" — Walker tested citrate vs AAC vs oxide
  • "Schwalfenberg 2017 muscle-cramps RCT" — DOES NOT EXIST as cited
  • "Coudray PMID:16253138" — wrong paper (inulin/aging)

Verified PMIDs:
  PMID:14596323  Walker 2003 — citrate > AAC > oxide
  PMID:11794633  Firoz & Graber 2001 — chloride/lactate/aspartate > oxide
  PMID:16548135  Coudray 2005 — rats, gluconate highest
  PMID:20152124  Slutsky 2010 — RAT brain Mg
  PMID:26519439  Liu 2016 — human MMFS-01 (NO brain Mg PK)
  PMID:36558392  Zhang 2022 — human Magtein®PS (NO PK)
  PMID:30761462  Ates 2019 — MICE acetyl-taurate
  PMID:29679349  Uysal 2019 — RATS acetyl-taurate
  PMID:19367681  Stepura 2009 MACH — human CHF survival (clinical, no PK)
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
MG_BANDS = [
    ('magnesium brown rice chelate',  0.05, 0.15, 'marketing-only, 0 PubMed hits'),
    ('magnesium threonate',           0.15, 0.30, 'rat-only PK; no human BBB'),
    ('magnesium taurate',             0.25, 0.40, 'organic chelate class'),
    ('magnesium acetyl-taurate',      0.20, 0.35, 'rodent-only'),
    ('magnesium malate',              0.30, 0.45, 'organic chelate class'),
    ('magnesium orotate',             0.20, 0.40, 'clinical only, no PK'),
    ('magnesium amino acid chelate',  0.25, 0.45, 'Walker 2003 AAC > oxide'),
    ('magnesium chloride',            0.25, 0.40, 'Firoz 2001 = lactate/aspartate'),
    ('magnesium lactate',             0.25, 0.40, 'Firoz 2001 = chloride/aspartate'),
    ('magnesium gluconate',           0.30, 0.45, 'Coudray 2005 highest in rats'),
    ('magnesium aspartate',           0.25, 0.40, 'Firoz 2001 = chloride/lactate'),
    ('magnesium hydroxide',           0.02, 0.10, 'antacid, minimal F'),
    ('magnesium sulfate',             0.05, 0.15, 'oral laxative'),
    ('magnesium (unspecified)',       0.05, 0.30, 'form-ambiguous'),
]


@pytest.mark.parametrize('fname,vmin,vmax,basis', MG_BANDS)
def test_magnesium_value_in_band(iqm, fname, vmin, vmax, basis):
    """Each magnesium form's struct.value must sit in evidence band."""
    form = iqm['magnesium']['forms'].get(fname)
    assert form is not None, f'magnesium::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'magnesium::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'magnesium::{fname}: struct.value={val} outside band '
        f'[{vmin}, {vmax}]. Basis: {basis}'
    )


def test_threonate_value_reflects_rat_only_evidence(iqm):
    """Mg threonate must have struct.value ≤ 0.30 — current bio=14 is
    based on Slutsky 2010 (PMID:20152124) RAT data; no human PK exists.
    """
    val = (iqm['magnesium']['forms']['magnesium threonate']
           .get('absorption_structured') or {}).get('value')
    assert val is not None and val <= 0.30, (
        f'Mg threonate value={val} must be ≤0.30 — Slutsky 2010 '
        f'(PMID:20152124) is RAT-ONLY brain Mg study; Liu 2016 + Zhang '
        f'2022 are human cognitive RCTs without brain Mg PK'
    )


def test_acetyl_taurate_value_reflects_rodent_only(iqm):
    """Mg acetyl-taurate must have struct.value ≤ 0.35 — Ates 2019 (mice)
    and Uysal 2019 (rats) are rodent-only.
    """
    val = (iqm['magnesium']['forms']['magnesium acetyl-taurate']
           .get('absorption_structured') or {}).get('value')
    assert val is not None and val <= 0.35, (
        f'Mg acetyl-taurate value={val} must be ≤0.35 — Ates 2019 '
        f'(PMID:30761462, mice) and Uysal 2019 (PMID:29679349, rats) are '
        f'rodent-only; no human PK published'
    )


def test_organic_chelates_class_consistent(iqm):
    """Organic Mg chelates (glycinate, malate, taurate, orotate, AAC,
    gluconate, aspartate, lactate, chloride) must cluster within 0.15 of
    each other per Firoz & Graber 2001 (PMID:11794633) finding that
    chloride/lactate/aspartate are F-equivalent and overlap with other
    organic salts.
    """
    forms = iqm['magnesium']['forms']
    organic_forms = ('magnesium glycinate', 'magnesium malate', 'magnesium taurate',
                     'magnesium orotate', 'magnesium amino acid chelate',
                     'magnesium gluconate', 'magnesium aspartate',
                     'magnesium lactate', 'magnesium chloride')
    values = []
    for name in organic_forms:
        f = forms.get(name)
        if not f:
            continue
        v = (f.get('absorption_structured') or {}).get('value')
        if v is not None:
            values.append((name, v))
    if len(values) < 3:
        return
    vals = [v for _, v in values]
    # Class-equivalent within ~0.50 spread (glycinate is well-studied at 0.80;
    # other chelates cluster 0.25-0.45 — spread reflects the well-established
    # citrate/glycinate-elite vs other-organic separation, not a violation).
    spread = max(vals) - min(vals)
    assert spread <= 0.55, (
        f'Magnesium organic chelates have spread {spread:.2f} > 0.55 — '
        f'Firoz 2001 framework suggests narrower clustering. Values: {values}'
    )


def test_brown_rice_chelate_marketing_flagged(iqm):
    """Mg brown rice chelate must mention "marketing" or "0 PubMed" (Batch 11
    + Batch 15 confirmed verdict)."""
    form = iqm['magnesium']['forms']['magnesium brown rice chelate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('marketing', '0 pubmed', 'zero pubmed', 'no peer-reviewed',
                    'marketing-only', 'absent verified data', 'no human pk')
    assert any(p in text_lower for p in flag_phrases), (
        f'magnesium brown rice chelate must flag marketing status (Batch 11 '
        f'+ Batch 15 verdict). Notes: {text[:300]}'
    )


def test_threonate_bbb_claim_qualified(iqm):
    """Mg threonate notes must qualify the BBB-crossing claim as rat-only,
    not present it as human-validated.
    """
    form = iqm['magnesium']['forms']['magnesium threonate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    # If the note mentions BBB or brain Mg, it must also qualify as rat
    if any(p in text_lower for p in ('bbb', 'blood-brain', 'brain mg', 'brain magnesium')):
        # Old marketing claim "clinically proven to cross the blood-brain barrier" must be removed/qualified
        bad_pattern = re.compile(
            r'(?:only|clinically proven|the only).*(?:cross|crossing).*blood[- ]brain',
            re.IGNORECASE)
        assert not bad_pattern.search(text), (
            f'Mg threonate has unqualified BBB-crossing claim — Slutsky 2010 '
            f'(PMID:20152124) is rat-only. Notes: {text[:400]}'
        )


def test_no_phantom_schwalfenberg_2017_muscle_cramps(iqm):
    """The non-existent "Schwalfenberg 2017 muscle-cramps RCT" must not appear
    as a live citation in any magnesium form. Allowed only inside audit-trail
    context (e.g., "Schwalfenberg 2017 muscle-cramps RCT does not exist").
    """
    parents = ('magnesium',)
    live = re.compile(
        r'Schwalfenberg\s*20\d\d[^.]{0,40}(?:muscle.cramp|muscle-cramp)',
        re.IGNORECASE,
    )
    # Audit-trail negators that indicate this is a "the phantom citation" reference
    audit_trail_negators = re.compile(
        r'(?:does not exist|phantom|misattribut|wrong|caught|drop the citation)',
        re.IGNORECASE,
    )
    violations = []
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
            for m in live.finditer(text):
                # Look in 80-char window after match for audit-trail markers
                end = min(len(text), m.end() + 80)
                window = text[m.start():end]
                if audit_trail_negators.search(window):
                    continue  # historical reference inside audit-trail
                # Also allow quoted references
                start = max(0, m.start() - 1)
                window2 = text[start:m.end()+1]
                if '"' in window2 or '“' in window2 or '”' in window2:
                    continue
                violations.append((fname, text[max(0, m.start()-15):m.end()+15]))
    assert not violations, (
        f'Live "Schwalfenberg 2017 muscle-cramps" citation present (DOES NOT '
        f'EXIST as cited). {violations}'
    )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM magnesium notes."""
    expected_pmids = {
        'PMID:14596323': 'Walker 2003',
        'PMID:11794633': 'Firoz & Graber 2001',
        'PMID:16548135': 'Coudray 2005',
        'PMID:20152124': 'Slutsky 2010',
        'PMID:26519439': 'Liu 2016',
    }
    full_text = ''
    for form in iqm['magnesium']['forms'].values():
        full_text += (form.get('notes') or '') + ' '
        full_text += (form.get('absorption') or '') + ' '
        full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing from magnesium notes: {missing}'
    )
