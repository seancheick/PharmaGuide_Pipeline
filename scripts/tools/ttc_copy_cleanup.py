#!/usr/bin/env python3
"""TTC batch copy cleanup per clinical team review.

TTC is a planning context, not pregnancy. Alerts should feel like
fertility-plan guidance, not pregnancy warnings.

Changes:
1. chasteberry + saw_palmetto: sex-neutral headline, body keeps pregnancy note
2. folate: "folic acid" wording, remove exact RR claim unless Cochrane verified
3. DHEA: stronger tone copy
4. wild_yam: soften mechanism
5. vitamin_d: lab-guided copy
6. coq10: evolving-evidence framing
7. inositol: clinician-guided plan copy
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def find_ttc_rule(canonical_id):
    """Return (rule_index, condition_rule_index) for the TTC sub-rule."""
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for j, cr in enumerate(r.get('condition_rules', [])):
                if isinstance(cr, dict) and cr.get('condition_id') == 'ttc':
                    return i, j
    raise KeyError(f'TTC rule not found for {canonical_id}')


def update(canonical_id, **fields):
    """Update specific fields on a TTC condition_rule."""
    ri, ci = find_ttc_rule(canonical_id)
    cr = rules[ri]['condition_rules'][ci]
    for k, v in fields.items():
        old = cr.get(k, '')
        if old != v:
            cr[k] = v
            changes.append(f'{canonical_id}.{k}: updated')


# ── 1. Chasteberry: sex-neutral headline ──
update('chasteberry',
    alert_headline='Hormone-active — discuss while TTC',
    alert_body=(
        'Chasteberry can affect prolactin and reproductive hormone signaling. '
        'If you are trying to conceive, use it with clinician guidance. '
        'If pregnancy is confirmed, ask your clinician whether to stop.'
    ),
)

# ── 2. Saw palmetto: sex-neutral headline ──
update('saw_palmetto',
    alert_headline='Hormone-active — discuss while TTC',
    alert_body=(
        'Saw palmetto may affect androgen pathways. If you are trying to conceive, '
        'review use with your clinician because fertility goals can differ by sex '
        'and treatment plan.'
    ),
)

# ── 3. DHEA: stronger tone copy ──
update('dhea',
    alert_headline='DHEA — fertility clinician only',
    alert_body=(
        'DHEA is hormone-active and has been studied in specific fertility-clinic '
        'settings. Do not use it casually while trying to conceive; use only with '
        'clinician monitoring.'
    ),
)

# ── 4. Folate: use "folic acid" wording ──
# Check if mechanism has exact RR 0.31 / 69% claim
ri, ci = find_ttc_rule('vitamin_b9_folate')
cr = rules[ri]['condition_rules'][ci]
mech = cr.get('mechanism', '')
# Remove exact RR claim if present — only keep if Cochrane PMID verified
if '0.31' in mech or '69%' in mech:
    # Soften to general statement
    mech = mech.replace(
        'reducing NTD incidence by approximately 69% (RR 0.31, 95% CI 0.17–0.58)',
        'substantially reducing NTD risk in multiple clinical trials'
    ).replace(
        'reducing NTD incidence by ~69% (RR 0.31)',
        'substantially reducing NTD risk in multiple clinical trials'
    )
    cr['mechanism'] = mech
    changes.append('vitamin_b9_folate.mechanism: removed exact RR claim')

update('vitamin_b9_folate',
    alert_headline='Folic acid is recommended preconception',
    alert_body=(
        'Folic acid before and during early pregnancy helps reduce neural tube '
        'defect risk. If you could become pregnant, aim for 400\u2013800 mcg/day '
        'unless your clinician recommends otherwise.'
    ),
)

# ── 5. Vitamin D: lab-guided copy ──
update('vitamin_d',
    alert_headline='Use labs to guide vitamin D',
    alert_body=(
        'Vitamin D status is often checked in preconception care. Use blood levels '
        'and clinician guidance to avoid under- or over-supplementing.'
    ),
)

# ── 6. CoQ10: evolving-evidence framing ──
update('coq10',
    alert_headline='Discuss CoQ10 with fertility clinician',
    alert_body=(
        'CoQ10 is commonly studied in fertility care, especially around oocyte '
        'mitochondrial function and ovarian aging. Evidence is still evolving, '
        'so use it as part of a clinician-guided plan.'
    ),
)

# ── 7. Inositol: clinician-guided plan ──
update('inositol',
    alert_headline='May support PCOS-related fertility',
    alert_body=(
        'Myo-inositol may support insulin signaling and ovulatory function in '
        'some people with PCOS. Ask your clinician whether the dose and '
        'formulation fit your fertility plan.'
    ),
)

# ── 8. Wild yam: soften mechanism + copy ──
update('wild_yam',
    alert_headline='Hormone claims are uncertain',
    alert_body=(
        'Wild yam is marketed for hormone support, but human fertility and '
        'pregnancy-safety data are limited. If you are trying to conceive, '
        'review use with your clinician.'
    ),
)
# Also soften the mechanism text
ri, ci = find_ttc_rule('wild_yam')
cr = rules[ri]['condition_rules'][ci]
old_mech = cr.get('mechanism', '')
if 'disrupt natural hormonal cycle regulation' in old_mech:
    cr['mechanism'] = (
        'Wild yam contains diosgenin, a steroidal saponin marketed as a '
        'natural hormone precursor. The human body does not convert diosgenin '
        'into progesterone. Fertility and pregnancy-safety data in humans are '
        'limited.'
    )
    changes.append('wild_yam.mechanism: softened — removed unproven disruption claim')

# ── 9. B12: no changes needed (already good) ──

# ── Validate lengths ──
for cid in ['chasteberry', 'saw_palmetto', 'dhea', 'vitamin_b9_folate',
            'vitamin_d', 'coq10', 'inositol', 'wild_yam']:
    ri, ci = find_ttc_rule(cid)
    cr = rules[ri]['condition_rules'][ci]
    hl = cr.get('alert_headline', '')
    ab = cr.get('alert_body', '')
    assert 20 <= len(hl) <= 60, f'{cid} headline len {len(hl)} out of [20,60]: "{hl}"'
    assert 60 <= len(ab) <= 200, f'{cid} alert_body len {len(ab)} out of [60,200]: "{ab}"'

# ── Write ──
with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} TTC copy changes:')
for c in changes:
    print(f'  ✓ {c}')
