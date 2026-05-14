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
    # PEG-creatine — polymer conjugate, distinct mechanism from salts
    ('peg-creatine system',                       0.80, 0.95, 'limited evidence; ergogenic-equiv at lower dose (Herda 2009 PMID:19387397)'),
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
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing from creatine notes: {missing}'
    )


def test_cee_creatinine_mechanism_documented(iqm):
    """CEE notes must mention creatinine conversion (pre-absorption hydrolysis)."""
    form = iqm['creatine_monohydrate']['forms']['creatine ethyl ester']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    assert 'creatinine' in text_lower, (
        f'CEE notes must mention creatinine conversion (the pre-absorption '
        f'hydrolysis product per Gufford 2013 / Giese 2009)'
    )


# ---------------------------------------------------------------------------
# Bucket-1 closure 2026-05-14 — PEG-Creatine gets a DEDICATED IQM form
# ---------------------------------------------------------------------------
# 14 GNC Amplified Creatine 189 / Creatine HCl 189 / Creatine Strength Support
# products (dsld_ids 4844, 4845, 5776, 5884, 18479, 25595, 30568, 31141, 42327,
# 67310, 69333, 74811, 74814, 210596) were excluded by the Batch 3 NOT_SCORED
# gate because their only active row in DSLD is `'PEG-Creatine System'` with
# ingredientGroup `'Creatine'`, and no IQM alias matched. Triage: see
# docs/handoff/2026-05-14_bucket_1_not_scored_triage.md (Cluster B-creatine).
#
# Resolution: create a DEDICATED `peg-creatine system` IQM form at
# bio_score 10 (class-equivalent to creatine salt forms HCl / citrate /
# nitrate). Taxonomy principle: distinct commercial/chemical identity →
# distinct form node, never alias across distinct compound classes.
#
# An earlier draft routed PEG-Creatine through the (unspecified) form at
# bio_score 6, which was rejected as too punitive (PEG-creatine has more
# evidence than "unknown form" and an actual published mechanism). An
# alternative draft proposed aliasing to creatine_hydrochloride to lift
# the score — also rejected as semantically sloppy (PEG-Creatine is NOT
# creatine HCl).
#
# Evidence base (all PMIDs WebFetch-verified 2026-05-14 via PubMed eutils):
#   - Herda 2009, PMID 19387397  — 30-day RCT, n=58, 4-arm; PEG 1.25-2.50 g/d
#     matched CM 5 g/d on 1RM bench + leg press
#   - Camic 2010, PMID 21068676  — 28-day RCT, n=22, PEG 5 g/d vs placebo
#   - Camic 2014, PMID 23897021  — 28-day RCT, n=77, PEG 1.25-2.50 g/d vs placebo
#
# Ghost reference caught + corrected: PMID 19164825 was cited in early draft
# but is a prostate-cancer study, not PEG-creatine. Removed pre-merge.


PEG_FORM = 'peg-creatine system'
PEG_VERIFIED_PMIDS = ['19387397', '21068676', '23897021']
PEG_GHOST_PMID = '19164825'  # prostate-cancer ghost reference; must NEVER appear


def test_peg_creatine_dedicated_form_exists(iqm):
    """A dedicated `peg-creatine system` form must exist under
    creatine_monohydrate.forms (taxonomy principle: distinct compound →
    distinct form node, not an alias on a different salt)."""
    forms = iqm['creatine_monohydrate']['forms']
    assert PEG_FORM in forms, (
        f"Dedicated {PEG_FORM!r} form missing. PEG-creatine MUST have its "
        "own form node — not be aliased to creatine_hydrochloride or any "
        "other salt (taxonomy principle: distinct chemical identity → "
        "distinct IQM form)."
    )


def test_peg_creatine_form_aliases_cover_dsld_label(iqm):
    """The dedicated form's aliases must include the exact DSLD label
    text `'PEG-Creatine System'` (lower-cased for matcher normalization),
    plus the bare `'peg-creatine'` and the formal chemical name variants."""
    aliases = iqm['creatine_monohydrate']['forms'][PEG_FORM].get('aliases') or []
    aliases_lower = {a.lower() for a in aliases}
    required = {
        'peg-creatine system',
        'peg-creatine',
        'polyethylene glycosylated creatine',
        'polyethylene-glycosylated creatine',
    }
    missing = required - aliases_lower
    assert not missing, f"Required PEG-creatine aliases missing: {missing}"


def test_peg_creatine_bio_score_in_salt_tier(iqm):
    """bio_score must be 10 — class-equivalent to creatine salt forms
    (HCl=10, citrate=10, nitrate=11). NOT 6 (would put it below CEE, a
    failed pro-drug), NOT 12-14 (would overstate vs limited evidence)."""
    form = iqm['creatine_monohydrate']['forms'][PEG_FORM]
    assert form.get('bio_score') == 10, (
        f"PEG-Creatine bio_score={form.get('bio_score')}, expected 10 "
        "(class-equivalent to creatine salt forms per limited but consistent "
        "ergogenic-equivalence evidence from Herda 2009 / Camic 2010 + 2014)."
    )
    assert form.get('score') == 10, "Top-level 'score' must mirror bio_score"


def test_peg_creatine_absorption_conservative(iqm):
    """absorption_structured.value must be conservative (≤ 0.95, not
    ≥ 0.99 like the salt forms) — the evidence base is limited (3 small
    short-duration RCTs, no muscle-creatine PK measurements)."""
    form = iqm['creatine_monohydrate']['forms'][PEG_FORM]
    s = form.get('absorption_structured') or {}
    val = s.get('value')
    assert val is not None and 0.80 <= val <= 0.95, (
        f"PEG-creatine absorption.value={val} outside conservative band "
        f"[0.80, 0.95]. Setting it ≥0.99 would claim parity with the salt "
        f"forms' class-equivalence-to-monohydrate evidence base, which "
        f"PEG-creatine does not yet have."
    )
    assert s.get('quality') == 'good', (
        f"absorption.quality={s.get('quality')!r}, expected 'good' (not "
        "'excellent') — limited evidence base."
    )


def test_peg_creatine_evidence_pmids_present(iqm):
    """All 3 WebFetch-verified PMIDs must appear in the form's notes."""
    notes = iqm['creatine_monohydrate']['forms'][PEG_FORM].get('notes') or ''
    missing = [p for p in PEG_VERIFIED_PMIDS if p not in notes]
    assert not missing, (
        f"PEG-creatine form notes missing verified PMIDs: {missing}. "
        "All three Herda 2009 / Camic 2010 / Camic 2014 must be cited "
        "(WebFetch-verified via PubMed eutils 2026-05-14)."
    )


def test_peg_creatine_no_ghost_citation(iqm):
    """The ghost-reference PMID 19164825 (prostate-cancer study, not
    PEG-creatine) must NEVER appear anywhere in the IQM. This catches
    regressions if anyone ever resurrects the bad citation."""
    iqm_text = json.dumps(iqm)
    assert PEG_GHOST_PMID not in iqm_text, (
        f"Ghost PMID {PEG_GHOST_PMID} (Crespo 2008, prostate-cancer "
        "mortality in Puerto Rican men) found in IQM — this was an "
        "incorrect citation for PEG-creatine in an early draft. The "
        "correct Herda 2009 PMID is 19387397."
    )


def test_peg_creatine_not_in_other_forms(iqm):
    """PEG aliases must live ONLY in the dedicated form. They must NOT
    appear in (unspecified), monohydrate, HCl, or any salt form
    (taxonomy isolation — prevents PEG products from accidentally
    routing to a different form)."""
    forms = iqm['creatine_monohydrate']['forms']
    peg_terms = {'peg-creatine system', 'peg-creatine',
                 'polyethylene glycosylated creatine',
                 'polyethylene-glycosylated creatine'}
    for fname, fdef in forms.items():
        if fname == PEG_FORM:
            continue
        aliases_lower = {a.lower() for a in (fdef.get('aliases') or [])}
        leaks = peg_terms & aliases_lower
        assert not leaks, (
            f"PEG-creatine terms {leaks} found in form {fname!r} — must "
            f"live ONLY in the dedicated {PEG_FORM!r} form per taxonomy "
            f"principle."
        )


def test_unspecified_form_aliases_unchanged_by_peg_work(iqm):
    """Confirm the (unspecified) creatine form's aliases were NOT
    polluted by the PEG-creatine work. Generic 'creatine' product names
    must still route to (unspecified), not to PEG-creatine."""
    unspec = iqm['creatine_monohydrate']['forms'][
        'creatine monohydrate ((unspecified))'
    ]
    aliases_lower = {a.lower() for a in (unspec.get('aliases') or [])}
    # Original generic-fallback aliases must still be present
    expected_generic = {
        'creatine',
        'creatine pyruvate',
        'creatine akg',
        'ot2 creatine',
    }
    missing = expected_generic - aliases_lower
    assert not missing, (
        f"(unspecified) form lost generic-fallback aliases: {missing}. "
        f"The PEG-creatine work must NOT remove pre-existing aliases."
    )
    # PEG aliases must NOT have leaked back here
    peg_leaks = {a for a in aliases_lower if 'peg' in a}
    assert not peg_leaks, (
        f"(unspecified) form has PEG-creatine aliases leaked back: {peg_leaks}. "
        f"PEG-creatine has its own dedicated form."
    )
