"""Regression test: poorly-absorbed botanical extracts must NOT claim high F.

Per IQM audit 2026-04-24 Step 4 Batch 2: pine bark procyanidins, eleutheroside
saponins, centella triterpene glycosides, and grape seed OPCs are not
systemically bioavailable as parent compounds. Only monomers, aglycones, or
microbial metabolites reach plasma at single-digit percent F.

Verified PubMed evidence:
  PMID:38757126  Bayer 2024 — Pycnogenol/procyanidin systemic F review
  PMID:23369882  Ma 2013 — eleutheroside B/E rat PK
  PMID:35204098  Wright 2022 — asiaticoside human Phase 1 (parent not detected)
  PMID:12064339  Donovan 2002 — grape seed procyanidin rat PK (dimers absent)
  PMID:15901750  Woelkart 2005 — echinacea alkamide human PK
  PMID:15919096  Matthias 2005 — echinacea tablet alkamide human PK

This test guards against regression to marketing-inflation language ("~50-85%
absorbed" style claims) that contradicts the published evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'

# Forms where evidence says systemic F is <20% for the PARENT compound.
# Format: (parent_id, form_name, max_allowed_pct)
# Caps reflect the HIGHEST legitimate number that can appear in an evidence
# citation (e.g., "monomers ~10-30%" or "Rg1 ~18%" are legit sub-compound F
# mentions even though the *overall* form F is single-digit). Caps 30-35%
# allow those specific-compound callouts while still catching "~50%+" marketing
# inflation.
LOW_F_BOTANICAL_FORMS = [
    # Procyanidin / OPC extracts — parent oligomers NOT absorbed, monomers are
    ('pine_bark_extract', 'generic pine bark extract',               15),
    ('pine_bark_extract', 'pycnogenol',                               15),
    ('grape_seed_extract', 'whole grape extract',                     15),
    # 95% OPC string mentions "monomers ~10-30%" — allow monomer callout
    ('grape_seed_extract', 'grape seed extract (95% proanthocyanidins)', 30),
    # Saponin / triterpene glycoside extracts — parent saponins minimal plasma
    ('ginseng', 'siberian ginseng (eleuthero)',                       5),
    # Panax string cites "Rg1 ~18%" (specific ginsenoside F) — allow
    ('ginseng', 'panax ginseng extract (4–7% ginsenosides)',          20),
    ('ginseng', 'american ginseng (panax quinquefolius)',             10),
    ('gotu_kola', 'gotu kola aerial extract',                          5),
]

# Echinacea alkamides genuinely absorb — tighter upper bound (50%) instead of 15%
MODERATE_F_FORMS = [
    ('echinacea', 'echinacea angustifolia',                          50),
    ('echinacea', 'echinacea purpurea extract (4% phenolics)',       50),
]


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


def _max_pct_claim(absorption_str: str) -> int | None:
    """Extract the largest percent number that appears to be a systemic F claim.

    Skips fold-change patterns ("115x"), "X hours", "X mg", and dose-response
    descriptors. Returns None if no explicit % found.
    """
    if not absorption_str:
        return None
    # Remove fold-change like "115x" or "115×"
    s = re.sub(r'\d+(?:\.\d+)?\s*[x×]', '', absorption_str)
    # Remove dose mentions like "10g"
    s = re.sub(r'\d+\s*(?:mg|g)\b', '', s, flags=re.IGNORECASE)
    # Remove hours
    s = re.sub(r'\d+\s*h(?:ours?)?\b', '', s, flags=re.IGNORECASE)
    # Now find percents
    pcts = [int(m) for m in re.findall(r'(\d+(?:\.\d+)?)\s*%', s)
            if float(m) == int(float(m))]  # integer-ish
    if not pcts:
        # Try float
        pcts = [int(float(m)) for m in re.findall(r'(\d+(?:\.\d+)?)\s*%', s)]
    return max(pcts) if pcts else None


@pytest.mark.parametrize('parent_id,form_name,max_pct', LOW_F_BOTANICAL_FORMS)
def test_low_f_botanical_string_not_inflated(iqm, parent_id, form_name, max_pct):
    """No low-F botanical form should claim >max_pct% systemic F."""
    form = iqm.get(parent_id, {}).get('forms', {}).get(form_name)
    assert form is not None, (
        f'{parent_id}::{form_name} missing from IQM — if intentionally removed, '
        f'update this regression test.'
    )
    absorption_str = form.get('absorption') or ''
    claimed = _max_pct_claim(absorption_str)
    if claimed is None:
        return  # no % claim — acceptable
    assert claimed <= max_pct, (
        f'{parent_id}::{form_name}: absorption string claims ~{claimed}% '
        f'(max allowed {max_pct}%). Current string: {absorption_str!r}. '
        f'Evidence (PMIDs 38757126, 23369882, 35204098, 12064339) shows '
        f'parent compound F is in single-digit percent range.'
    )


@pytest.mark.parametrize('parent_id,form_name,max_pct', MODERATE_F_FORMS)
def test_moderate_f_botanical_string_not_over_50(iqm, parent_id, form_name, max_pct):
    """Echinacea alkamides absorb rapidly, but "~50-65%" overstated — cap at 50%."""
    form = iqm.get(parent_id, {}).get('forms', {}).get(form_name)
    assert form is not None, f'{parent_id}::{form_name} missing from IQM'
    absorption_str = form.get('absorption') or ''
    claimed = _max_pct_claim(absorption_str)
    if claimed is None:
        return
    assert claimed <= max_pct, (
        f'{parent_id}::{form_name}: absorption string claims ~{claimed}% '
        f'(max allowed {max_pct}%). Current: {absorption_str!r}. Evidence '
        f'(PMIDs 15901750, 15919096) supports alkamide absorption but not >50%.'
    )


def test_struct_values_consistent_with_botanical_evidence(iqm):
    """absorption_structured.value for these botanical forms must stay conservative.

    Specifically: OPC/procyanidin forms ≤ 0.15, saponin forms ≤ 0.20,
    triterpene-glycoside forms ≤ 0.10. Echinacea alkamides ≤ 0.50.
    """
    caps = {
        ('pine_bark_extract', 'generic pine bark extract'):          0.15,
        ('pine_bark_extract', 'pycnogenol'):                          0.15,
        ('grape_seed_extract', 'whole grape extract'):                0.15,
        ('grape_seed_extract', 'grape seed extract (95% proanthocyanidins)'): 0.15,
        ('ginseng', 'siberian ginseng (eleuthero)'):                  0.05,
        ('ginseng', 'panax ginseng extract (4–7% ginsenosides)'):     0.10,
        ('ginseng', 'american ginseng (panax quinquefolius)'):        0.10,
        ('gotu_kola', 'gotu kola aerial extract'):                    0.10,
        ('echinacea', 'echinacea angustifolia'):                      0.50,
        ('echinacea', 'echinacea purpurea extract (4% phenolics)'):   0.50,
    }
    violations = []
    for (pid, fname), cap in caps.items():
        form = iqm.get(pid, {}).get('forms', {}).get(fname)
        if not form:
            continue
        val = (form.get('absorption_structured') or {}).get('value')
        if val is None:
            continue
        if val > cap:
            violations.append((pid, fname, val, cap))
    assert not violations, (
        f'absorption_structured.value exceeds evidence-supported cap: {violations}'
    )
