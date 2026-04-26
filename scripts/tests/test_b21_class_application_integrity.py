"""Regression test: Batch 21 class-application from Batches 1-20.

Per IQM audit 2026-04-25 Step 4 Batch 21: 28 forms across 7 class-equivalent
groups. NO new research — applies findings from prior 20 batches:
  • Liposomal forms (Batch 6/10/15: evidence-thin pattern)
  • Brown rice chelate (Batch 11: 0 PubMed hits, marketing)
  • Branded clinical-only (Batches 16-19: Crominex pattern)
  • Active coenzyme P5P (Batch 12: dephosphorylation pre-absorption)
  • Phytosome / EMIQ (Batch 19: bioflavonoid class-poor + SGLT1 exception)
  • Probiotic strains (Batch 18: manuka category-error / live organism)
  • PS branded forms (Batch 20: ceramide pre-absorption hydrolysis)

Plus 8 architectural duplicates flagged for separate review.
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


# Class-equivalent groups (parent, form, vmin, vmax, framework_batch)
B21_BANDS = [
    # GROUP 1: LIPOSOMAL — evidence-thin
    ('berberine_supplement', 'liposomal berberine',                   0.05, 0.30, 'B6/10/15 liposomal'),
    ('ginkgo', 'liposomal ginkgo',                                    0.15, 0.50, 'B6/10/15 liposomal'),
    ('glutathione', 'liposomal glutathione',                          0.10, 0.40, 'B6/10/15 liposomal'),
    ('glutathione', 's-acetyl glutathione',                           0.15, 0.50, 'acetyl protected'),
    ('saw_palmetto', 'liposomal saw palmetto',                        0.30, 0.70, 'lipid baseline + carrier'),
    ('nad_precursors', 'liposomal nmn / nr',                          0.05, 0.30, 'B6/10/15 liposomal + dupe flag'),
    # GROUP 2: BROWN RICE CHELATE
    ('boron', 'boron brown rice chelate',                             0.70, 0.95, 'B11 marketing'),
    ('potassium', 'potassium brown rice chelate',                     0.80, 0.95, 'B11 marketing'),
    # GROUP 3: BRANDED CLINICAL-ONLY (Crominex pattern)
    ('black_cohosh', 'remifemin',                                     0.05, 0.30, 'Crominex pattern'),
    ('chasteberry', 'vitex standardized extract',                     0.10, 0.40, 'Crominex pattern'),
    ('citrus_bergamot', 'bergamot bpf',                               0.05, 0.20, 'Crominex + bioflav'),
    ('coenzymated_complex', 'coenzymated',                            0.15, 0.60, 'B12 dephosphorylation'),
    ('phosphatidylserine', 'Actiserine (enhanced PS blend)',          0.15, 0.50, 'B20 PS hydrolysis'),
    ('phosphatidylserine', 'sharp-ps gold (PS-DHA conjugate)',        0.20, 0.60, 'B20 PS-DHA'),
    ('pqq', 'microactive PQQ',                                        0.15, 0.50, 'Crominex pattern'),
    ('pqq', 'lifepqq',                                                0.15, 0.50, 'Crominex pattern'),
    # GROUP 4: ACTIVE COENZYME (B12 framework)
    ('vitamin_b6_pyridoxine', 'pyridoxal-5-phosphate (P5P)',          0.70, 0.95, 'B12 dephosphorylation'),
    ('vitamin_b6_pyridoxine', 'pyridoxamine',                         0.70, 0.95, 'B6 class'),
    # GROUP 5: PHYTOSOME / EMIQ
    ('quercetin', 'quercetin phytosome',                              0.05, 0.20, 'B19 bioflav phytosome'),
    ('quercetin', 'isoquercetin (EMIQ)',                              0.10, 0.35, 'EMIQ SGLT1 exception'),
    ('grape_seed_extract', 'grape seed phytosome',                    0.05, 0.20, 'B19 OPC phytosome'),
    # GROUP 6: PROBIOTIC STRAINS (live organism)
    ('bifidobacterium_lactis', 'bifidobacterium lactis (unspecified)', 0.05, 0.20, 'B18 live organism'),
    ('bifidobacterium_longum', 'bifidobacterium longum infantis 35624', 0.05, 0.20, 'B18 live organism'),
    ('bifidobacterium_longum', 'bifidobacterium longum r0175',         0.05, 0.20, 'B18 live organism'),
    ('lactobacillus_plantarum', 'lactobacillus plantarum (unspecified)', 0.05, 0.20, 'B18 live organism'),
    ('lactobacillus_plantarum', 'lactobacillus plantarum l-137 (heat-killed/postbiotic)', 0.10, 0.40, 'postbiotic'),
    ('lactobacillus_rhamnosus', 'lactobacillus rhamnosus (unspecified)', 0.05, 0.20, 'B18 live organism'),
    ('lactobacillus_salivarius', 'lactobacillus salivarius ha-118',   0.05, 0.20, 'B18 live organism'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,framework', B21_BANDS)
def test_b21_class_application_in_band(iqm, pid, fname, vmin, vmax, framework):
    """Each form's struct.value must sit in band derived from prior batch
    framework application.
    """
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Framework: {framework}'
    )


def test_p5p_class_equivalent_to_pyridoxine_class(iqm):
    """P5P struct.value must be ≥ 0.70 per Batch 12 active-coenzyme finding —
    P5P dephosphorylated to pyridoxal pre-absorption; F is class-equivalent
    to pyridoxine (~95%).
    """
    val = (iqm['vitamin_b6_pyridoxine']['forms']['pyridoxal-5-phosphate (P5P)']
           .get('absorption_structured') or {}).get('value')
    assert val is not None and val >= 0.70, (
        f'P5P value={val} should be ≥0.70 — dephosphorylated pre-absorption '
        f'per Batch 12 active-coenzyme finding'
    )


def test_emiq_higher_than_quercetin_phytosome(iqm):
    """EMIQ (SGLT1-absorbed) should rank higher than quercetin phytosome
    (lipid carrier on still-poor base) per Batch 19 exception.
    """
    forms = iqm['quercetin']['forms']
    emiq = (forms['isoquercetin (EMIQ)'].get('absorption_structured') or {}).get('value')
    phytosome = (forms['quercetin phytosome'].get('absorption_structured') or {}).get('value')
    assert emiq is not None and phytosome is not None
    assert emiq >= phytosome, (
        f'EMIQ ({emiq}) should be ≥ quercetin phytosome ({phytosome}) — '
        f'EMIQ has SGLT1-mediated absorption per Murota et al.'
    )


def test_probiotic_strains_class_equivalent(iqm):
    """All standard probiotic strains must cluster in 0.05-0.20 band per
    Batch 18 live-organism category framework.
    """
    probiotic_forms = [
        ('bifidobacterium_lactis', 'bifidobacterium lactis (unspecified)'),
        ('bifidobacterium_longum', 'bifidobacterium longum infantis 35624'),
        ('bifidobacterium_longum', 'bifidobacterium longum r0175'),
        ('lactobacillus_plantarum', 'lactobacillus plantarum (unspecified)'),
        ('lactobacillus_rhamnosus', 'lactobacillus rhamnosus (unspecified)'),
        ('lactobacillus_salivarius', 'lactobacillus salivarius ha-118'),
    ]
    for pid, fname in probiotic_forms:
        form = iqm[pid]['forms'][fname]
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is not None and 0.05 <= v <= 0.20, (
            f'{pid}::{fname} value={v} outside live-organism class band [0.05, 0.20]'
        )


def test_brown_rice_chelate_class_F_applied(iqm):
    """Brown rice chelate forms must use parent mineral class F (boron ~85%,
    potassium ~90%) since brown rice marketing has 0 PubMed hits per Batch 11.
    """
    boron = (iqm['boron']['forms']['boron brown rice chelate']
             .get('absorption_structured') or {}).get('value')
    potassium = (iqm['potassium']['forms']['potassium brown rice chelate']
                 .get('absorption_structured') or {}).get('value')
    assert boron >= 0.70, f'boron BR chelate value={boron} should be ≥0.70 (B class F)'
    assert potassium >= 0.80, f'potassium BR chelate value={potassium} should be ≥0.80 (K class F)'


def test_branded_extracts_class_poor(iqm):
    """Branded clinical-only extracts (Crominex pattern) must reflect
    class-poor F — clinical RCTs ≠ PK evidence.
    """
    branded_low_F = [
        ('black_cohosh', 'remifemin'),
        ('chasteberry', 'vitex standardized extract'),
        ('citrus_bergamot', 'bergamot bpf'),
    ]
    for pid, fname in branded_low_F:
        v = (iqm[pid]['forms'][fname].get('absorption_structured') or {}).get('value')
        assert v is not None and v <= 0.40, (
            f'{pid}::{fname} value={v} should be ≤0.40 — Crominex pattern '
            f'(clinical RCTs ≠ PK evidence)'
        )


def test_liposomal_evidence_thin_documented(iqm):
    """Liposomal forms must document evidence-thin status (no human PK)."""
    liposomal_forms = [
        ('berberine_supplement', 'liposomal berberine'),
        ('ginkgo', 'liposomal ginkgo'),
        ('glutathione', 'liposomal glutathione'),
        ('saw_palmetto', 'liposomal saw palmetto'),
        ('nad_precursors', 'liposomal nmn / nr'),
    ]
    for pid, fname in liposomal_forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text_lower = text.lower()
        flag_phrases = ('evidence-thin', 'no human pk', 'no dedicated',
                        'mechanistic', 'no published', 'no comparator')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} liposomal form must document evidence-thin '
            f'status (Batch 6/10/15 framework). Text: {text[:300]}'
        )
