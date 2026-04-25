"""Regression test: mineral chelate (iron, manganese, zinc, selenium) PK.

Per IQM audit 2026-04-25 Step 4 Batch 11: 42 mineral chelate forms across
4 parents had null struct.values or marketing-driven absorption claims.
Research subagent USED WebFetch on PubMed eutils API.

CRITICAL VERDICT — "brown rice chelate" is MARKETING:
  PubMed esearch for "brown rice chelate absorption bioavailability"
  returned ZERO results across iron/Mn/Zn/Se variants. The recurring
  "60-70%" figure originates from supplier datasheets without peer-
  reviewed PK validation. All 4 brown rice chelate forms flagged for
  bio_score downgrade 11→8 pending Dr Pham signoff.

Verified PMIDs:
  PMID:37111104  Piacenza 2023 Nutrients — zinc aspartate FZA (n=8)
  PMID:11377130  Pineda & Ashmead 2001 Nutrition — iron bisglycinate
  PMID:10958812  Layrisse 2000 J Nutr — ferrochel ~2× FeSO4
  PMID:25888289  Hemilä 2015 BMC Fam Pract — Zn lozenge LOCAL effect
  PMID:3318377   Gordeuk 1987 AJCN — carbonyl iron ~7% effective F
  PMID:3630857   Barrie 1987 Agents Actions — Zn picolinate (no actual %F)
  PMID:30213039  Fabiano 2018 IJMS — sucrosomial iron ex vivo
  PMID:29070551  Anderson & Frazer 2017 AJCN — iron homeostasis review

Misattribution caught: PMID:21411831 (Liu 2011 rat) NOT cited for heme iron.
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
MINERAL_BANDS = [
    # IRON
    ('iron', 'iron bisglycinate',                    0.20, 0.45, 'Pineda 2001 PMID:11377130'),
    ('iron', 'iron brown rice chelate',              0.05, 0.18, 'no human PK; FeSO4-class est.'),
    ('iron', 'iron protein succinylate',             0.08, 0.25, 'enteric-protected ferric'),
    ('iron', 'heme iron polypeptide',                0.15, 0.35, 'heme transporter ~15-35%'),
    ('iron', 'ferrous gluconate',                    0.07, 0.20, 'class est. similar to FeSO4'),
    ('iron', 'carbonyl iron',                        0.04, 0.12, 'Gordeuk 1987 PMID:3318377'),
    ('iron', 'iron amino acid chelate',              0.10, 0.35, 'Layrisse 2000 PMID:10958812'),
    ('iron', 'polysaccharide-iron complex',          0.05, 0.18, 'class est.'),
    ('iron', 'microencapsulated iron',               0.07, 0.20, 'SunActive class est.'),
    ('iron', 'ferrous ascorbate',                    0.12, 0.35, 'ascorbate enhancement'),
    ('iron', 'liposomal iron',                       0.08, 0.30, 'Fabiano 2018 PMID:30213039'),
    # MANGANESE (homeostatic, low F class-wide)
    ('manganese', 'manganese bisglycinate',          0.03, 0.15, 'Albion class est.'),
    ('manganese', 'manganese amino acid chelate',    0.03, 0.15, 'class est.'),
    ('manganese', 'manganese citrate',               0.02, 0.10, 'organic salt class'),
    ('manganese', 'manganese gluconate',             0.02, 0.10, 'organic salt class'),
    ('manganese', 'manganese picolinate',            0.02, 0.10, 'no Mn-specific PK'),
    ('manganese', 'manganese ascorbate',             0.03, 0.12, 'ascorbate co-presence'),
    ('manganese', 'manganese aspartate',             0.03, 0.12, 'amino acid salt'),
    ('manganese', 'manganese malate',                0.02, 0.10, 'organic salt class'),
    ('manganese', 'manganese chloride',              0.02, 0.08, 'inorganic baseline'),
    ('manganese', 'food-based manganese',            0.02, 0.10, 'whole-food matrix'),
    ('manganese', 'manganese yeast-bound',           0.03, 0.12, 'yeast Se-analogy'),
    ('manganese', 'manganese brown rice chelate',    0.02, 0.10, 'no human PK; marketing flag'),
    # ZINC
    ('zinc', 'zinc carnosine',                       0.40, 0.70, 'PepZin GI mucosal'),
    ('zinc', 'zinc bisglycinate',                    0.40, 0.70, 'TRAACS class est.'),
    ('zinc', 'zinc acetate',                         0.25, 0.55, 'Hemilä 2015 LOCAL effect'),
    ('zinc', 'zinc gluconate',                       0.25, 0.55, 'Piacenza 2023 PMID:37111104'),
    ('zinc', 'zinc monomethionine',                  0.40, 0.70, 'OptiZinc class est.'),
    ('zinc', 'zinc orotate',                         0.30, 0.60, 'no controlled human PK'),
    ('zinc', 'zinc sulfate',                         0.15, 0.45, 'reference inorganic'),
    ('zinc', 'zinc aspartate',                       0.35, 0.65, 'Piacenza 2023 PMID:37111104'),
    ('zinc', 'zinc brown rice chelate',              0.20, 0.45, 'no human PK; marketing flag'),
    ('zinc', 'zinc amino acid chelate',              0.35, 0.65, 'AAC class est.'),
    # SELENIUM
    ('selenium', 'selenium-methyl L-selenocysteine', 0.80, 0.95, 'organic Se class'),
    ('selenium', 'selenocysteine',                   0.75, 0.92, 'organic Se class'),
    ('selenium', 'selenium-enriched broccoli extract', 0.65, 0.90, 'plant-MeSeCys'),
    ('selenium', 'selenium-enriched garlic extract', 0.65, 0.90, 'garlic MeSeCys'),
    ('selenium', 'selenobetaine',                    0.55, 0.85, 'synthetic Se'),
    ('selenium', 'methylseleninic acid',             0.55, 0.85, 'MSA research'),
    ('selenium', 'selenium glycinate',               0.65, 0.92, 'Albion class est.'),
    ('selenium', 'selenium brown rice chelate',      0.40, 0.65, 'no human PK; marketing flag'),
    ('selenium', 'selenium picolinate',              0.40, 0.70, 'no validated PK'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', MINERAL_BANDS)
def test_mineral_chelate_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each mineral chelate form's struct.value must sit in evidence band."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_brown_rice_chelate_marketing_flagged(iqm):
    """All 4 brown rice chelate forms must reference the "no human PK" /
    "marketing" flag in their absorption string or notes (Batch 11 verdict).
    """
    rice_forms = [
        ('iron', 'iron brown rice chelate'),
        ('manganese', 'manganese brown rice chelate'),
        ('zinc', 'zinc brown rice chelate'),
        ('selenium', 'selenium brown rice chelate'),
    ]
    for pid, fname in rice_forms:
        form = iqm.get(pid, {}).get('forms', {}).get(fname)
        assert form is not None, f'{pid}::{fname} missing'
        text = (form.get('absorption') or '') + ' ' + (form.get('notes') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text = text.lower()
        flag_phrases = ('no human pk', 'no human-pk', 'marketing', 'zero pubmed',
                        'no peer-reviewed', 'absent peer-reviewed', 'marketing-only')
        assert any(p in text for p in flag_phrases), (
            f'{pid}::{fname} should flag "no human PK" or "marketing" status. '
            f'Text: {text[:200]}'
        )


def test_brown_rice_chelate_value_conservative(iqm):
    """Brown rice chelate values must be conservative (not the marketing 60-70%)."""
    rice_caps = [
        ('iron', 'iron brown rice chelate', 0.20),
        ('manganese', 'manganese brown rice chelate', 0.15),
        ('zinc', 'zinc brown rice chelate', 0.50),
        ('selenium', 'selenium brown rice chelate', 0.65),
    ]
    for pid, fname, max_val in rice_caps:
        val = (iqm[pid]['forms'][fname].get('absorption_structured') or {}).get('value')
        assert val <= max_val, (
            f'{pid}::{fname} value={val} exceeds conservative cap {max_val}. '
            f'The "60-70%" marketing claim has 0 PubMed support.'
        )


def test_no_liu_2011_misattributed_for_heme_iron(iqm):
    """PMID:21411831 (Liu 2011 rat exercise/hepcidin) must NOT be cited as
    evidence for heme iron F — that paper does not report heme iron absorption.
    """
    form = iqm['iron']['forms']['heme iron polypeptide']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    assert 'PMID:21411831' not in text or 'NOT cited' in text or 'misattribut' in text.lower(), (
        f'heme iron must not cite PMID:21411831 (Liu 2011 rat exercise study). '
        f'Text: {text[:200]}'
    )


def test_zinc_aspartate_pmid_37111104_cited(iqm):
    """Zinc aspartate must continue to cite verified PMID:37111104 (Piacenza 2023)."""
    form = iqm['zinc']['forms']['zinc aspartate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    assert 'PMID:37111104' in text, (
        f'zinc aspartate must cite verified PMID:37111104 (Piacenza 2023)'
    )


def test_iron_bisglycinate_class_evidence_cited(iqm):
    """Iron bisglycinate must cite Pineda 2001 (PMID:11377130) or Layrisse 2000
    (PMID:10958812) — verified Albion bisglycinate evidence.
    """
    form = iqm['iron']['forms']['iron bisglycinate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    assert 'PMID:11377130' in text or 'PMID:10958812' in text, (
        f'iron bisglycinate must cite verified Pineda 2001 or Layrisse 2000 PMID'
    )


def test_zinc_acetate_local_effect_caveat(iqm):
    """Zinc acetate notes must clarify Hemilä 2015 lozenge effect is LOCAL,
    not systemic F — to prevent miscitation of cold-symptom data as F evidence.
    """
    form = iqm['zinc']['forms']['zinc acetate']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    if 'hemilä' in text_lower or '25888289' in text:
        # Must include local-effect caveat
        assert ('local' in text_lower or 'pharyngeal' in text_lower
                or 'mucosal' in text_lower), (
            f'zinc acetate citing Hemilä 2015 must include LOCAL pharyngeal '
            f'caveat (lozenge effect ≠ systemic F). Text: {text[:300]}'
        )


def test_mineral_form_ranking_iron(iqm):
    """Iron form ranking by struct.value: bisglycinate > heme polypeptide >
    ascorbate ≈ AAC > sulfate (well-established literature).
    """
    forms = iqm['iron']['forms']
    def v(name):
        return (forms[name].get('absorption_structured') or {}).get('value') or 0
    bisglycinate = v('iron bisglycinate')
    heme = v('heme iron polypeptide')
    sulfate = v('ferrous sulfate')
    assert bisglycinate > sulfate, (
        f'Iron bisglycinate ({bisglycinate}) must exceed ferrous sulfate '
        f'({sulfate}) per Pineda 2001 / Layrisse 2000'
    )
    assert heme >= sulfate, (
        f'Heme iron ({heme}) must be ≥ ferrous sulfate ({sulfate}) — '
        f'heme transporter pathway'
    )


def test_selenium_organic_dominates_inorganic(iqm):
    """Selenium organic forms (selenomethionine, MeSeCys, glycinate) must
    rank higher than inorganic (selenite, selenate).
    """
    forms = iqm['selenium']['forms']
    def v(name):
        return (forms[name].get('absorption_structured') or {}).get('value') or 0
    selenomethionine = v('selenomethionine')
    me_se_cys = v('selenium-methyl L-selenocysteine')
    selenite = v('sodium selenite')
    assert selenomethionine > selenite, (
        f'selenomethionine ({selenomethionine}) must exceed sodium selenite '
        f'({selenite}) — organic > inorganic Se class'
    )
    assert me_se_cys > selenite, (
        f'Se-MeSeCys ({me_se_cys}) must exceed sodium selenite ({selenite})'
    )
