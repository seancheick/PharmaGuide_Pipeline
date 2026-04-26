"""Regression test: omega-3 form bioavailability evidence integrity.

Per IQM audit 2026-04-25 Step 4 Batch 9: 19 of 22 omega-3 forms across 4
parents (fish_oil, dha, epa, cod_liver_oil) had null struct.value despite
bio_scores 9-14. Research subagent established framework: omega-3 absolute
oral F is class-HIGH (~0.70-0.97) across all chemical forms when
co-ingested with dietary fat.

Verified PMIDs RETAINED from existing IQM:
  PMID:20638827  Dyerberg 2010 — primary form-comparison reference
                  (rTG=124%, TG=100%, FFA=91%, EE=73% relative to CLO)
  PMC3168413     Schuchardt 2011 — krill PL vs fish oil
  PMID:41096614  Algal DHA — flagged for re-verification

Agent suggested 8 NEW PMIDs (Arterburn 2007, Köhler 2015, Neubronner 2011,
Ramprasath 2013, Yurko-Mauro 2015, Laidlaw 2014, Schuchardt PMID:21854650,
Arterburn 2008) — NOT introduced this batch; require live PubMed
verification per project anti-hallucination policy.
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
OMEGA3_EVIDENCE_BANDS = [
    # FISH_OIL
    ('fish_oil', 'triglyceride (rTG) form',                0.85, 0.97, 'rTG: highest plasma rise per Dyerberg 2010'),
    ('fish_oil', 'natural triglyceride',                   0.78, 0.92, 'TG-class reference'),
    ('fish_oil', 'ethyl ester',                            0.60, 0.80, 'EE: -27% short-term per Dyerberg 2010'),
    ('fish_oil', 'molecularly distilled',                  0.78, 0.92, 'TG-class default'),
    ('fish_oil', 'fish liver oil',                         0.78, 0.92, 'TG-class CLO-equivalent'),
    ('fish_oil', 'fish oil phospholipid',                  0.80, 0.95, 'PL: marginal advantage per Schuchardt 2011'),
    ('fish_oil', 'fish oil (unspecified)',                 0.65, 0.90, 'mixed TG/EE class'),
    # DHA
    ('dha',      'algal triglyceride',                     0.78, 0.92, 'algal DHA-TG class-equivalent'),
    ('dha',      'DHA fish oil ethyl ester',               0.60, 0.80, 'DHA-EE per Dyerberg 2010'),
    ('dha',      'DHA fish oil triglyceride',              0.78, 0.92, 'DHA-TG reference'),
    ('dha',      'DHA krill phospholipid',                 0.80, 0.95, 'DHA-PL marginal advantage'),
    ('dha',      'dha (unspecified)',                      0.65, 0.90, 'unknown form'),
    ('dha',      'DHA fish oil rTG',                       0.85, 0.97, 'DHA-rTG concentrated'),
    # EPA
    ('epa',      'EPA fish oil ethyl ester',               0.60, 0.80, 'EPA-EE per Dyerberg 2010'),
    ('epa',      'EPA fish oil triglyceride',              0.78, 0.92, 'EPA-TG reference'),
    ('epa',      'EPA krill phospholipid',                 0.80, 0.95, 'EPA-PL marginal advantage'),
    ('epa',      'epa (unspecified)',                      0.65, 0.90, 'unknown form'),
    ('epa',      'EPA fish oil rTG',                       0.85, 0.97, 'EPA-rTG concentrated'),
    # COD_LIVER_OIL
    ('cod_liver_oil', 'fermented',                          0.70, 0.90, 'TG-class assumed; no human PK'),
    ('cod_liver_oil', 'virgin/cold-processed',              0.78, 0.92, 'TG-class virgin'),
    ('cod_liver_oil', 'cod liver oil molecular distilled',  0.75, 0.90, 'TG-class MD'),
    ('cod_liver_oil', 'cod liver oil (unspecified)',        0.70, 0.90, 'TG-class default'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', OMEGA3_EVIDENCE_BANDS)
def test_omega3_value_in_evidence_band(iqm, pid, fname, vmin, vmax, basis):
    """Each omega-3 form's struct.value must sit in evidence-supported band."""
    form = iqm.get(pid, {}).get('forms', {}).get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


def test_omega3_form_ranking_consistent(iqm):
    """Form ranking by struct.value must follow Dyerberg 2010 evidence:
    rTG > TG ≈ PL > EE.
    """
    for pid in ('fish_oil', 'dha', 'epa'):
        forms = iqm[pid]['forms']
        def v(name):
            f = forms.get(name)
            if not f:
                return None
            return (f.get('absorption_structured') or {}).get('value')
        # Find the rTG, TG, EE, PL forms (names vary slightly per parent)
        rtg_keys = [k for k in forms if 'rtg' in k.lower() or 'rTG' in k]
        tg_keys = [k for k in forms if k.endswith('triglyceride') or 'natural triglyceride' in k.lower()
                   or 'fish oil triglyceride' in k.lower() or 'algal triglyceride' in k.lower()]
        ee_keys = [k for k in forms if 'ethyl ester' in k.lower() or 'fish oil ethyl ester' in k.lower()]

        rtg_vals = [v(k) for k in rtg_keys if v(k) is not None]
        tg_vals = [v(k) for k in tg_keys if v(k) is not None and k not in rtg_keys]
        ee_vals = [v(k) for k in ee_keys if v(k) is not None]

        if rtg_vals and tg_vals:
            assert max(rtg_vals) >= max(tg_vals), (
                f'{pid}: rTG ({rtg_vals}) should rank ≥ TG ({tg_vals}) per Dyerberg 2010'
            )
        if tg_vals and ee_vals:
            assert max(tg_vals) > max(ee_vals), (
                f'{pid}: TG ({tg_vals}) should rank > EE ({ee_vals}) per Dyerberg 2010'
            )


def test_dyerberg_2010_pmid_cited(iqm):
    """Dyerberg 2010 (PMID:20638827) is the primary reference for omega-3
    form comparison. It must appear in ≥6 forms across the 4 omega-3 parents.
    """
    parents = ('fish_oil', 'dha', 'epa', 'cod_liver_oil')
    hits = 0
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            if 'PMID:20638827' in text or 'Dyerberg 2010' in text:
                hits += 1
    assert hits >= 6, (
        f'Dyerberg 2010 (PMID:20638827) should be cited in ≥6 omega-3 forms '
        f'(primary form-comparison reference). Found in {hits}'
    )


def test_no_unverified_pmids_introduced(iqm):
    """Per project anti-hallucination policy, agent-suggested NEW PMIDs
    that were not live-verified must NOT appear in the IQM. These were
    flagged for verification before introduction in next session.
    """
    unverified = [
        'PMID:17413132',  # Arterburn 2007 — not yet verified
        'PMID:18689564',  # Arterburn 2008 — not yet verified
        'PMID:22113870',  # Neubronner 2011 — not yet verified
        'PMID:25510778',  # Köhler 2015 — not yet verified
        'PMID:24373555',  # Ramprasath 2013 — not yet verified
        'PMID:21854650',  # Schuchardt PMID form (vs PMC) — not yet verified
        'PMID:26561784',  # Yurko-Mauro 2015 — not yet verified
        'PMID:24344723',  # Laidlaw 2014 — not yet verified
    ]
    parents = ('fish_oil', 'dha', 'epa', 'cod_liver_oil')
    violations = []
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
            for pmid in unverified:
                if pmid in text:
                    violations.append((pid, fname, pmid))
    # Allowed if it appears in audit-trail under "REQUIRES VERIFICATION" or in metadata
    # but should not appear in form-level notes/absorption fields as a live citation
    assert not violations, (
        f'Agent-suggested NEW PMIDs introduced without live verification: '
        f'{violations}. Per project policy, verify via PubMed efetch first.'
    )


def test_fermented_clo_flagged_for_review(iqm):
    """Fermented cod liver oil should flag absence of human PK in any of:
    form.notes, form.absorption, or absorption_structured.notes.
    """
    form = iqm['cod_liver_oil']['forms']['fermented']
    notes = (form.get('notes') or '').lower()
    absorption = (form.get('absorption') or '').lower()
    struct_notes = ((form.get('absorption_structured') or {}).get('notes') or '').lower()
    combined = notes + ' ' + absorption + ' ' + struct_notes
    flag_phrases = ('no human pk', 'no published human pk',
                    'no human pharmacokinetic')
    assert any(p in combined for p in flag_phrases), (
        f'cod_liver_oil::fermented should flag absence of human PK data '
        f'(currently bio=14 marketing-driven) in form.notes, absorption, '
        f'or absorption_structured.notes. Combined: {combined[:300]}'
    )


def test_omega3_class_high_framework_documented(iqm):
    """Framework note about omega-3 absolute F being class-HIGH should
    appear in ≥10 omega-3 forms.
    """
    parents = ('fish_oil', 'dha', 'epa', 'cod_liver_oil')
    hits = 0
    for pid in parents:
        for fname, form in iqm[pid]['forms'].items():
            notes = (form.get('notes') or '').lower()
            if ('class-high' in notes or 'class high' in notes
                    or '0.70-0.97' in notes or '~0.70' in notes):
                hits += 1
    assert hits >= 10, (
        f'Omega-3 class-HIGH framework note (Batch 9) should appear in ≥10 '
        f'forms; found in {hits}'
    )
