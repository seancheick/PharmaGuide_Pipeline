"""Regression test: Batch 20 — ceramides/silk/organ extracts integrity.

Per IQM audit 2026-04-25 Step 4 Batch 20: 11 forms across 3 specialty
parents. Three framework findings:

1. CERAMIDES — pre-absorption hydrolysis to sphingoid bases (Sugawara
   2022 PMID:35905137, Yamashita 2021 PMID:34208952). Intact ceramide F
   class-poor (<5%). Skin RCTs are PD endpoints not PK.

2. SILK PEPTIDES collapse to hydrolyzed silk class — delivered as amino
   acids (~95% F via PepT-1). "Peptide advantage" marketing.

3. ORGAN EXTRACTS — CATEGORY ERROR like manuka (Batch 18). Composite
   food with no unified F.

Verified PMIDs:
  PMID:20646083  Guillou 2011 — wheat ceramide RCT (PD endpoint)
  PMID:32020853  Heggar Venkataramana 2020 — konjac glycosylceramide
  PMID:35905137  Sugawara 2022 — sphingolipid review
  PMID:34208952  Yamashita 2021 — dietary sphingolipid review
  PMID:28357619  Morifuji 2017 — sphingomyelin RAT (NOT human F)

Misattributions caught:
  • "Bizot 2017 Lipowheat" — GHOST → use Guillou 2011 (PMID:20646083)
  • "Tomonaga 2017 silk peptide" — GHOST
  • PMID:447109 — author surname trap (Silk DB 1979 is fish protein,
    NOT silkworm fibroin)
  • Plus 4 wrong-topic PMIDs flagged
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


# (parent, form, vmin, vmax) — None vmin/vmax means must be null
B20_BANDS_VALUED = [
    # CERAMIDES — class-poor pre-absorption hydrolysis
    ('ceramides', 'phytoceramides (plant)',                   0.02, 0.10),
    ('ceramides', 'wheat-derived',                            0.02, 0.10),
    ('ceramides', 'synthetic',                                0.02, 0.10),
    ('ceramides', 'ceramides (unspecified)',                  0.02, 0.10),
    # SILK — class-equivalent AA F
    ('silk_amino_acids', 'hydrolyzed silk protein',           0.85, 0.99),
    ('silk_amino_acids', 'silk peptides',                     0.85, 0.99),
    ('silk_amino_acids', 'silk amino acids (unspecified)',    0.85, 0.99),
]

B20_NULL_FORMS = [
    # ORGAN EXTRACTS — category error, all null
    ('organ_extracts', 'grass-fed desiccated'),
    ('organ_extracts', 'freeze-dried'),
    ('organ_extracts', 'standard desiccated'),
    ('organ_extracts', 'organ extracts (unspecified)'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax', B20_BANDS_VALUED)
def test_b20_value_in_band(iqm, pid, fname, vmin, vmax):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]'
    )


@pytest.mark.parametrize('pid,fname', B20_NULL_FORMS)
def test_b20_organ_extract_value_null(iqm, pid, fname):
    """Organ extracts must have struct.value=null per category-error finding —
    composite food with no unified F.
    """
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, (
        f'{pid}::{fname} value={val} must be null — composite food has no '
        f'unified F (category-error like manuka, Batch 18)'
    )


def test_organ_extract_category_error_documented(iqm):
    """Organ extract notes must document the category-error (composite food,
    no unified F).
    """
    forms = iqm['organ_extracts']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('category error', 'composite food', 'no unified f',
                        'per-component', 'per-nutrient', 'nutrient density',
                        'manuka pattern')
        assert any(p in text_lower for p in flag_phrases), (
            f'organ_extracts::{fname} must document category-error in notes. '
            f'Text: {text[:300]}'
        )


def test_ceramides_pre_absorption_hydrolysis_qualified(iqm):
    """Ceramide notes must qualify pre-absorption hydrolysis (sphingoid
    bases / glucocerebrosidase / not intact F).
    """
    forms = iqm['ceramides']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('hydrolyzed', 'sphingoid', 'pre-absorption',
                        'pre absorption', 'pd endpoint', 'pd not pk')
        assert any(p in text_lower for p in flag_phrases), (
            f'ceramides::{fname} must qualify pre-absorption hydrolysis '
            f'mechanism. Text: {text[:300]}'
        )


def test_wheat_ceramide_backwards_claim_corrected(iqm):
    """Wheat-derived ceramide notes must NOT contain the BACKWARDS claim
    "glucosylceramides metabolized to ceramides in the gut" — that's the
    inverse direction. They are hydrolyzed PAST ceramide to sphingoid bases.
    """
    form = iqm['ceramides']['forms']['wheat-derived']
    text = form.get('notes') or ''
    bad_pattern = re.compile(
        r'glucosylceramides[^.]*?metabolized\s+to\s+ceramides',
        re.IGNORECASE,
    )
    assert not bad_pattern.search(text), (
        f'wheat-derived ceramide notes still contain BACKWARDS claim '
        f'"glucosylceramides metabolized to ceramides" — direction inverted. '
        f'Notes: {text[:300]}'
    )


def test_silk_peptide_collapsed_to_aa_class(iqm):
    """Silk peptides must have struct.value equal (within 0.05) to
    hydrolyzed silk protein — class-equivalent at amino acid level.
    """
    forms = iqm['silk_amino_acids']['forms']
    peptides = (forms['silk peptides'].get('absorption_structured') or {}).get('value')
    hydrolyzed = (forms['hydrolyzed silk protein'].get('absorption_structured') or {}).get('value')
    assert peptides is not None and hydrolyzed is not None
    assert abs(peptides - hydrolyzed) <= 0.05, (
        f'silk peptides ({peptides}) must equal hydrolyzed silk '
        f'({hydrolyzed}) within 0.05 — both delivered as amino acids; '
        f'no intact silk peptide reaches systemic circulation'
    )


def test_no_phantom_bizot_2017_citation(iqm):
    """The non-existent "Bizot 2017 Lipowheat" citation must not appear
    as live citation. Real reference is Guillou 2011 (PMID:20646083).
    """
    parents = ('ceramides',)
    live = re.compile(r'(?<![\"“])Bizot\s*20\d\d(?![\"”])', re.IGNORECASE)
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
                # Allow audit-trail context
                end80 = min(len(text), m.end() + 80)
                window80 = text[m.start():end80]
                if any(neg in window80.lower() for neg in
                       ('ghost', 'misattribut', 'not found', '0 pubmed', 'wrong')):
                    continue
                violations.append((pid, fname, text[max(0, m.start()-15):m.end()+15]))
    assert not violations, (
        f'Live "Bizot 2017" citation present (GHOST). Use Guillou 2011 '
        f'(PMID:20646083). {violations}'
    )


def test_no_phantom_tomonaga_silk_peptide_citation(iqm):
    """The non-existent "Tomonaga silk peptide" citation must not appear."""
    parents = ('silk_amino_acids',)
    live = re.compile(r'(?<![\"“])Tomonaga\s*20\d\d(?![\"”])', re.IGNORECASE)
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
            for m in live.finditer(text):
                end80 = min(len(text), m.end() + 80)
                window80 = text[m.start():end80]
                if any(neg in window80.lower() for neg in
                       ('ghost', 'misattribut', 'not found', '0 pubmed', 'wrong')):
                    continue
                assert False, (
                    f'silk_amino_acids::{fname} cites "Tomonaga 20XX" '
                    f'(GHOST). Context: {text[max(0, m.start()-30):m.end()+30]}'
                )


def test_silk_pmid_447109_qualified(iqm):
    """If PMID:447109 (Silk DB 1979, fish protein hydrolysate) is cited,
    must be qualified as fish protein NOT silk fibroin.
    """
    forms = iqm['silk_amino_acids']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        if '447109' in text:
            assert 'fish' in text.lower() or 'author' in text.lower() or 'NOT silkworm' in text or 'NOT silk fibroin' in text, (
                f'silk_amino_acids::{fname} cites PMID:447109 without '
                f'qualifying as fish protein hydrolysate (NOT silk fibroin). '
                f'Author surname trap. Text: {text[:300]}'
            )


def test_class_authority_pmids_introduced(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:20646083': 'Guillou 2011 wheat ceramide',
        'PMID:35905137': 'Sugawara 2022 sphingolipid',
        'PMID:34208952': 'Yamashita 2021 sphingolipid',
    }
    full_text = ''
    for pid in ('ceramides', 'silk_amino_acids', 'organ_extracts'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )
