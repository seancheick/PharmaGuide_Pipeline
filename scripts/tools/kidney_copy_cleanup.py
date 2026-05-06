#!/usr/bin/env python3
"""Kidney disease batch copy cleanup per clinical team review.

Key issues:
- 6/9 rules had a generic templated alert_body that was clinically wrong
  for the specific mechanism (not everything "accumulates in kidneys")
- Creatine copy should not imply kidney damage
- Propylene glycol headline too loud for excipient exposure
- Tribulus headline too technical/scary for case-report evidence
- Dandelion evidence overstated
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def find_kidney_rule(canonical_id):
    for i, r in enumerate(rules):
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for j, cr in enumerate(r.get('condition_rules', [])):
                if isinstance(cr, dict) and cr.get('condition_id') == 'kidney_disease':
                    return i, j
    raise KeyError(f'Kidney rule not found for {canonical_id}')


def update(canonical_id, **fields):
    ri, ci = find_kidney_rule(canonical_id)
    cr = rules[ri]['condition_rules'][ci]
    for k, v in fields.items():
        old = cr.get(k, '')
        if old != v:
            cr[k] = v
            changes.append(f'{canonical_id}.{k}: updated')


# ── 1. Potassium — keep strong, improve body copy ──
update('potassium',
    alert_headline='Hyperkalemia risk in CKD',
    alert_body=(
        'Potassium supplements can raise blood potassium dangerously when '
        'kidney function is reduced, especially with ACE inhibitors, ARBs, '
        'or potassium-sparing medicines. Use only with clinician guidance.'
    ),
)

# ── 2. Magnesium — keep strong, clarify supplemental sources ──
update('magnesium',
    alert_headline='Magnesium can accumulate in CKD',
    alert_body=(
        'Magnesium from supplements, laxatives, or antacids can accumulate '
        'when kidney function is reduced. If you have kidney disease, use '
        'magnesium-containing products only with clinician guidance.'
    ),
)

# ── 3. Creatine — do NOT imply kidney damage ──
update('creatine_monohydrate',
    alert_headline='May affect creatinine lab results',
    alert_body=(
        'Creatine can raise serum creatinine, which may complicate '
        'kidney-function interpretation. If you have kidney disease, use '
        'only with clinician guidance and lab monitoring.'
    ),
)

# ── 4. Licorice — mineralocorticoid effects, not accumulation ──
update('licorice_root',
    alert_headline='May affect fluid and potassium balance',
    alert_body=(
        'Licorice can raise blood pressure, promote fluid retention, and '
        'lower potassium. These effects can be more concerning when kidney '
        'function is reduced.'
    ),
)

# ── 5. Cascara sagrada — chronic laxative use, not accumulation ──
update('cascara_sagrada',
    alert_headline='Electrolyte loss with chronic use',
    alert_body=(
        'Chronic or high-dose stimulant laxative use can cause fluid and '
        'electrolyte shifts. If you have kidney disease, use only with '
        'clinician guidance, especially with diuretics or heart medicines.'
    ),
)

# ── 6. Senna — same pattern as cascara ──
update('senna',
    alert_headline='Electrolyte loss with chronic use',
    alert_body=(
        'Chronic or high-dose stimulant laxative use can cause fluid and '
        'electrolyte shifts. If you have kidney disease, use only with '
        'clinician guidance, especially with diuretics or heart medicines.'
    ),
)

# ── 7. Dandelion — diuretic, weaker evidence ──
update('dandelion',
    alert_headline='Diuretic herb — use caution in CKD',
    evidence_level='limited',
    alert_body=(
        'Dandelion may have diuretic effects. If you have kidney disease or '
        'take diuretics, ask your clinician before using concentrated '
        'dandelion supplements.'
    ),
)

# ── 8. Propylene glycol — soften headline ──
update('ADD_PROPYLENE_GLYCOL',
    alert_headline='High exposure may matter in CKD',
    alert_body=(
        'Propylene glycol is partly cleared by the kidneys. Large or '
        'repeated exposures may be more relevant when kidney function is '
        'reduced. Typical supplement excipient amounts are small.'
    ),
)

# ── 9. Tribulus — less scary headline ──
update('tribulus',
    alert_headline='Kidney safety data are limited',
    alert_body=(
        'Rare case reports have described kidney injury after tribulus use. '
        'If you have kidney disease, review use with your clinician and stop '
        'if kidney symptoms or abnormal labs occur.'
    ),
)

# ── Validate lengths ──
for cid in ['potassium', 'magnesium', 'creatine_monohydrate', 'licorice_root',
            'cascara_sagrada', 'senna', 'dandelion', 'ADD_PROPYLENE_GLYCOL', 'tribulus']:
    ri, ci = find_kidney_rule(cid)
    cr = rules[ri]['condition_rules'][ci]
    hl = cr.get('alert_headline', '')
    ab = cr.get('alert_body', '')
    assert 20 <= len(hl) <= 60, f'{cid} headline len {len(hl)}: "{hl}"'
    assert 60 <= len(ab) <= 200, f'{cid} alert_body len {len(ab)}: "{ab}"'

# ── Write ──
with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} kidney disease copy changes:')
for c in changes:
    print(f'  ✓ {c}')
