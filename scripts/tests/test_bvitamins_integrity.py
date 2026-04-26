"""Regression test: B-vitamin (B1/B2/B3/B5/B9) PK + active-coenzyme finding.

Per IQM audit 2026-04-25 Step 4 Batch 12: 24 B-vitamin forms across 5 parents
were null-value. Research subagent USED WebFetch on PubMed eutils. Two major
class findings:

1. ACTIVE COENZYME FORMS (FMN, FAD, TPP, pantethine) are dephosphorylated/
   hydrolyzed in gut lumen BEFORE absorption — systemic F equals parent
   vitamin F. Bio_scores 13-14 are NOT justified by oral PK.

2. INOSITOL HEXANICOTINATE has NO measurable bioavailability (Keenan 2013
   PMID:23351578) — current bio=12 severely misleading; recommend 4.

Verified PMIDs:
  PMID:8929745   Loew 1996 — benfotiamine Cmax 5x/AUC 3.6x (NOT absolute F=5x)
  PMID:9587048   Greb & Bitsch 1998 — benfotiamine > TTFD orally
  PMID:22305197  Smithline 2012 — thiamine HCl saturable PK
  PMID:33812058  Watanabe 2021 — TTFD [11C] human PET
  PMID:8604671   Zempleni 1996 — riboflavin oral/IV PK
  PMID:4056044   Wittwer 1985 — pantethine hydrolyzed pre-absorption
  PMID:23351578  Keenan 2013 — IHN NO measurable bioavailability
  PMID:22646128  MacKay 2012 — niacin chemical forms review
  PMID:20608755  Pietrzik 2010 — FA vs L-5-MTHF review
  PMID:16825690  Lamers 2006 — RBC folate higher with [6S]-5-MTHF
  PMID:19917061  Prinz-Langenohl 2009 — 5-MTHF AUC ~2x FA; UMFA only after FA
  PMID:33255787  Obeid 2020 — Na/Ca salt 5-MTHF AUC ratio ~2.25 vs FA
  PMID:20573790  Bailey 2010 NHANES — UMFA in 38% adults ≥60
  PMID:24944062  Patanwala 2014 — folic acid portal vein handling

Misattributions caught:
  • "Norris 2006 inositol hexanicotinate" — DOES NOT EXIST → Keenan 2013
  • "Wittwer 1989 pantethine" — wrong year → 1985
  • "Patanwala 2014 bioequivalence" → portal-vein handling study
  • "Loew 1996 5x better F" → actually Cmax 5x / AUC 3.6x
  • "Quatrefolic 9.7x AUC" → Miraglia 2016 RAT only
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
BVITAMIN_BANDS = [
    # B1
    ('vitamin_b1_thiamine', 'benfotiamine',                                0.30, 0.70, 'Loew 1996 Cmax 5x/AUC 3.6x'),
    ('vitamin_b1_thiamine', 'thiamine mononitrate',                        0.05, 0.55, 'Smithline 2012 saturable'),
    ('vitamin_b1_thiamine', 'thiamine hydrochloride',                      0.05, 0.55, 'Smithline 2012 saturable'),
    ('vitamin_b1_thiamine', 'allithiamine',                                0.40, 0.65, 'limited human PK'),
    ('vitamin_b1_thiamine', 'thiamine pyrophosphate (TPP)',                0.30, 0.55, 'TPP dephosphorylated pre-absorption'),
    ('vitamin_b1_thiamine', 'thiamine tetrahydrofurfuryl disulfide (TTFD)', 0.40, 0.75, 'Greb 1998 < benfotiamine'),
    ('vitamin_b1_thiamine', "thiamine from brewer's yeast",                0.30, 0.50, 'food matrix'),
    ('vitamin_b1_thiamine', 'thiamine disulfide',                          0.20, 0.45, 'Greb 1998 lowest of class'),
    # B2
    ('vitamin_b2_riboflavin', 'riboflavin-5-phosphate',                    0.85, 0.95, 'FMN dephosphorylated to riboflavin'),
    ('vitamin_b2_riboflavin', 'riboflavin',                                0.30, 0.95, 'Zempleni 1996 saturable'),
    ('vitamin_b2_riboflavin', 'riboflavin from yeast',                     0.30, 0.60, 'food matrix'),
    ('vitamin_b2_riboflavin', 'flavin adenine dinucleotide (FAD)',         0.85, 0.95, 'FAD hydrolyzed pre-absorption'),
    # B3
    ('vitamin_b3_niacin', 'inositol hexanicotinate',                       0.0,  0.10, 'Keenan 2013 no bioavailability'),
    ('vitamin_b3_niacin', 'niacinamide',                                   0.85, 0.95, 'rapid passive'),
    ('vitamin_b3_niacin', 'niacinamide ascorbate (b3)',                    0.70, 0.90, 'salt class est.'),
    ('vitamin_b3_niacin', 'nicotinic acid',                                0.70, 0.95, 'rapid F via GPR109A'),
    ('vitamin_b3_niacin', 'tryptophan_derived_niacin',                     0.01, 0.02, 'mass-equivalent ~60:1'),
    # B5
    ('vitamin_b5_pantothenic', 'calcium pantothenate',                     0.40, 0.60, 'saturable SMVT'),
    ('vitamin_b5_pantothenic', 'pantethine',                               0.40, 0.60, 'Wittwer 1985 hydrolyzed pre-absorption'),
    ('vitamin_b5_pantothenic', 'pantothenic acid',                         0.40, 0.60, 'free acid SMVT'),
    ('vitamin_b5_pantothenic', 'sodium pantothenate',                      0.40, 0.60, 'salt class est.'),
    ('vitamin_b5_pantothenic', 'panthenol (pro-vitamin B5)',               0.30, 0.50, 'pro-vitamin'),
    # B9
    ('vitamin_b9_folate', '5-methyltetrahydrofolate (5-MTHF)',             0.80, 0.95, 'Prinz-Langenohl 2009 AUC ~2x FA'),
    ('vitamin_b9_folate', 'calcium folinate',                              0.85, 0.95, 'reduced folate'),
    ('vitamin_b9_folate', 'quatrefolic',                                   0.80, 0.95, 'human PK = generic 5-MTHF'),
    ('vitamin_b9_folate', 'metafolin',                                     0.80, 0.95, 'Obeid 2020 AUC ~2.25x FA'),
    ('vitamin_b9_folate', 'folic acid',                                    0.80, 0.95, 'F ~85% but UMFA controversy'),
    ('vitamin_b9_folate', 'food folate (polyglutamate)',                   0.50, 0.80, 'polyglutamate gut conjugase'),
    ('vitamin_b9_folate', 'folate from yeast',                             0.50, 0.80, 'mixed natural folates'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', BVITAMIN_BANDS)
def test_bvitamin_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each B-vitamin form's struct.value must sit in evidence band."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_ihn_value_near_zero(iqm):
    """Inositol hexanicotinate must have struct.value ≤ 0.10 per Keenan 2013
    (PMID:23351578) finding of NO measurable bioavailability.
    """
    val = (iqm['vitamin_b3_niacin']['forms']['inositol hexanicotinate']
           .get('absorption_structured') or {}).get('value')
    assert val is not None and val <= 0.10, (
        f'IHN value={val} should be ≤0.10 per Keenan 2013 (PMID:23351578) — '
        f'IHN has NO measurable bioavailability at 1500 mg/day x 6 weeks'
    )


def test_active_coenzyme_F_equals_parent(iqm):
    """Active coenzyme forms (FMN, FAD, TPP, pantethine) must have struct.value
    in the SAME band as their parent vitamin per class finding that they are
    dephosphorylated/hydrolyzed pre-absorption.
    """
    forms_b1 = iqm['vitamin_b1_thiamine']['forms']
    forms_b2 = iqm['vitamin_b2_riboflavin']['forms']
    forms_b5 = iqm['vitamin_b5_pantothenic']['forms']

    def v(parent_forms, name):
        return (parent_forms[name].get('absorption_structured') or {}).get('value') or 0

    # FMN should be in same band as riboflavin (~0.90)
    fmn = v(forms_b2, 'riboflavin-5-phosphate')
    riboflavin = v(forms_b2, 'riboflavin')
    fad = v(forms_b2, 'flavin adenine dinucleotide (FAD)')
    assert abs(fmn - riboflavin) <= 0.10, (
        f'FMN ({fmn}) should equal riboflavin ({riboflavin}) — dephosphorylated pre-absorption'
    )
    assert abs(fad - riboflavin) <= 0.10, (
        f'FAD ({fad}) should equal riboflavin ({riboflavin}) — hydrolyzed pre-absorption'
    )

    # TPP should be in same band as thiamine
    tpp = v(forms_b1, 'thiamine pyrophosphate (TPP)')
    thiamine = v(forms_b1, 'thiamine hydrochloride')
    assert abs(tpp - thiamine) <= 0.15, (
        f'TPP ({tpp}) should equal thiamine HCl ({thiamine}) — dephosphorylated pre-absorption'
    )

    # Pantethine should be in same band as pantothenate
    pantethine = v(forms_b5, 'pantethine')
    pantothenate = v(forms_b5, 'calcium pantothenate')
    assert abs(pantethine - pantothenate) <= 0.10, (
        f'Pantethine ({pantethine}) should equal pantothenate ({pantothenate}) — '
        f'hydrolyzed pre-absorption per Wittwer 1985 (PMID:4056044)'
    )


def test_5mthf_dominates_folic_acid(iqm):
    """Per Prinz-Langenohl 2009 (PMID:19917061), 5-MTHF AUC ~2x folic acid in
    humans. Both should have similar % F (~85%) — but 5-MTHF avoids UMFA.
    The struct.value bands should overlap; the differentiator is documented
    in notes (UMFA, MTHFR variants).
    """
    forms = iqm['vitamin_b9_folate']['forms']
    mthf = (forms['5-methyltetrahydrofolate (5-MTHF)'].get('absorption_structured') or {}).get('value')
    fa = (forms['folic acid'].get('absorption_structured') or {}).get('value')
    # Both should be in evidence-supported high range
    assert mthf is not None and 0.80 <= mthf <= 0.95
    assert fa is not None and 0.80 <= fa <= 0.95
    # 5-MTHF should be ≥ folic acid (or at least equal — Prinz-Langenohl shows
    # AUC differential, not absolute F differential)
    assert mthf >= fa - 0.05, (
        f'5-MTHF ({mthf}) should be >= folic acid ({fa}) per Prinz-Langenohl 2009'
    )


def test_no_phantom_norris_2006_ihn_citation(iqm):
    """The non-existent "Norris 2006" inositol hexanicotinate citation must
    not appear as a live citation. Keenan 2013 PMID:23351578 is the verified
    replacement.
    """
    parents = ('vitamin_b3_niacin',)
    live = re.compile(r'(?<![\"“])Norris\s*2006(?![\"”])', re.IGNORECASE)
    violations = []
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            for m in live.finditer(text):
                start = max(0, m.start() - 1)
                end = min(len(text), m.end() + 1)
                window = text[start:end]
                if '"' in window or '“' in window or '”' in window:
                    continue
                violations.append((pid, fname, text[max(0, m.start()-15):m.end()+15]))
    assert not violations, (
        f'Live "Norris 2006" citation present (DOES NOT EXIST in PubMed). '
        f'Use Keenan 2013 (PMID:23351578) instead. {violations}'
    )


def test_no_phantom_wittwer_1989_citation(iqm):
    """The "Wittwer 1989" pantethine citation has wrong year — actual is 1985
    PMID:4056044. Live citations must use 1985 or PMID:4056044.
    """
    form = iqm['vitamin_b5_pantothenic']['forms']['pantethine']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    live = re.compile(r'(?<![\"“])Wittwer\s*1989(?![\"”])', re.IGNORECASE)
    for m in live.finditer(text):
        start = max(0, m.start() - 1)
        end = min(len(text), m.end() + 1)
        window = text[start:end]
        if '"' in window or '“' in window or '”' in window:
            continue
        assert False, (
            f'pantethine still cites "Wittwer 1989" (wrong year). '
            f'Correct: Wittwer 1985 (PMID:4056044, J Clin Invest). '
            f'Context: {text[max(0, m.start()-30):m.end()+30]}'
        )


def test_keenan_2013_ihn_cited(iqm):
    """Inositol hexanicotinate must cite verified Keenan 2013 (PMID:23351578)."""
    form = iqm['vitamin_b3_niacin']['forms']['inositol hexanicotinate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    assert ('PMID:23351578' in text or 'Keenan 2013' in text), (
        f'IHN must cite verified Keenan 2013 (PMID:23351578) — IHN has NO '
        f'measurable bioavailability finding'
    )


def test_class_authority_pmids_introduced(iqm):
    """Multiple verified class-authority PMIDs from Batch 12 must appear in IQM."""
    expected_pmids = {
        'PMID:8929745':  'Loew 1996 benfotiamine',
        'PMID:8604671':  'Zempleni 1996 riboflavin',
        'PMID:4056044':  'Wittwer 1985 pantethine',
        'PMID:23351578': 'Keenan 2013 IHN',
        'PMID:19917061': 'Prinz-Langenohl 2009 5-MTHF',
        'PMID:20573790': 'Bailey 2010 UMFA NHANES',
    }
    parents = ('vitamin_b1_thiamine', 'vitamin_b2_riboflavin', 'vitamin_b3_niacin',
               'vitamin_b5_pantothenic', 'vitamin_b9_folate')
    full_text = ''
    for pid in parents:
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing from B-vitamin notes: {missing}'
    )


def test_benfotiamine_string_no_5x_F_claim(iqm):
    """Benfotiamine must not claim "5x better bioavailability" or similar
    absolute F language. Loew 1996 reports Cmax 5x and AUC 3.6x — neither
    is absolute F=5x.
    """
    form = iqm['vitamin_b1_thiamine']['forms']['benfotiamine']
    s = form.get('absorption') or ''
    bad_patterns = [
        r'5x?\s*better\s*(?:absorbed|absorption|bioavailability)\b',
        r'5x?\s*more\s*bioavailable',
        r'5\s*-?\s*fold\s*higher\s*F\b',
    ]
    for pat in bad_patterns:
        if re.search(pat, s, re.IGNORECASE):
            assert False, (
                f'benfotiamine still claims "5x better F" — that conflates Cmax '
                f'(relative metric) with absolute F. Loew 1996 (PMID:8929745) '
                f'reports Cmax 5x / AUC 3.6x. String: {s!r}'
            )
