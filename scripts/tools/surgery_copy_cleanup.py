#!/usr/bin/env python3
"""Surgery batch cleanup per clinical team review."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')

with open(RULES_PATH) as f:
    data = json.load(f)

rules = data['interaction_rules']
changes = []


def update_surg(canonical_id, **fields):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            for cr in r.get('condition_rules', []):
                if cr.get('condition_id') == 'surgery_scheduled':
                    for k, v in fields.items():
                        if cr.get(k) != v:
                            cr[k] = v
                            changes.append(f'{canonical_id}.{k}')
                    return True
    return False


def remove_surg(canonical_id):
    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
        if cid == canonical_id:
            cr_list = r.get('condition_rules', [])
            for j, cr in enumerate(cr_list):
                if cr.get('condition_id') == 'surgery_scheduled':
                    cr_list.pop(j)
                    changes.append(f'{canonical_id}: REMOVED surgery rule (dedup)')
                    return True
    return False


# ── 1. Dedup omega-3/fish_oil: keep fish_oil[51], remove omega_3 + fish_oil[127] ──
remove_surg('omega_3')

# Remove the second fish_oil surgery rule
fish_oil_hits = []
for i, r in enumerate(rules):
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    if cid == 'fish_oil':
        for j, cr in enumerate(r.get('condition_rules', [])):
            if cr.get('condition_id') == 'surgery_scheduled':
                fish_oil_hits.append((i, j))
if len(fish_oil_hits) > 1:
    ri, ci = fish_oil_hits[-1]
    rules[ri]['condition_rules'].pop(ci)
    changes.append('fish_oil: REMOVED duplicate surgery rule')

update_surg('fish_oil',
    severity='monitor',
    evidence_level='probable',
    alert_headline='Review high-dose omega-3 before surgery',
    alert_body=(
        'High-dose EPA/DHA may affect platelet function, but large trials '
        'have not shown a clear increase in bleeding. Tell your surgical '
        'team about omega-3 use before a procedure.'
    ),
)

# ── 2. Dedup ginger: remove NHA_GINGER_EXTRACT, keep ginger ──
remove_surg('NHA_GINGER_EXTRACT')

update_surg('ginger',
    alert_headline='Concentrated ginger — pause before surgery',
    alert_body=(
        'Concentrated ginger supplements may affect platelet function. Tell '
        'your surgical team and pause before surgery if instructed. Normal '
        'food-level ginger is generally fine.'
    ),
)

# ── 3. Ginkgo — specific headline ──
update_surg('ginkgo',
    alert_headline='Ginkgo may increase surgical bleeding risk',
    alert_body=(
        'Ginkgo inhibits platelet-activating factor and may increase '
        'perioperative bleeding. Discontinue at least 2 weeks before '
        'scheduled surgery unless your surgical team advises otherwise.'
    ),
)

# ── 4. Garlic — specific headline ──
update_surg('garlic',
    alert_headline='Garlic supplements may increase bleeding',
    alert_body=(
        'Garlic supplements can affect platelet aggregation. Tell your '
        'surgical team and pause before surgery if instructed.'
    ),
)

# ── 5. White willow bark — specific headline ──
update_surg('white_willow_bark',
    alert_headline='Salicylate-like — stop before surgery',
    alert_body=(
        'White willow bark contains salicylate-like compounds that may '
        'affect platelet function. If surgery is scheduled, ask your '
        'surgical team when to stop it.'
    ),
)

# ── 6. Vitamin K — re-scope to warfarin, not generic surgery ──
# Change from surgery_scheduled condition to drug_class gate
for r in rules:
    sr = r.get('subject_ref', {})
    cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
    if cid == 'vitamin_k':
        cr_list = r.get('condition_rules', [])
        for j, cr in enumerate(cr_list):
            if cr.get('condition_id') == 'surgery_scheduled':
                cr['severity'] = 'monitor'
                cr['alert_headline'] = 'Vitamin K plan depends on warfarin care'
                cr['alert_body'] = (
                    'If you take warfarin and have surgery scheduled, follow '
                    'your anticoagulation plan from your surgical team. Do not '
                    'change vitamin K intake without guidance.'
                )
                changes.append('vitamin_k: severity avoid→monitor, warfarin-focused copy')
        break

# ── 7. Ginseng — specific headline ──
update_surg('ginseng',
    alert_headline='Ginseng may affect bleeding or glucose',
    alert_body=(
        'Ginseng may affect platelet function and blood sugar. Tell your '
        'surgical team before a procedure, especially if you use blood '
        'thinners or diabetes medication.'
    ),
)

# ── 8. Saw palmetto — case-report language ──
update_surg('saw_palmetto',
    alert_headline='Review saw palmetto before surgery',
    alert_body=(
        'Case reports have linked saw palmetto to intraoperative bleeding. '
        'Tell your surgical team and pause before surgery if instructed.'
    ),
)

# ── 9. Chondroitin — soften ──
update_surg('chondroitin',
    severity='monitor',
    alert_headline='Review if using blood thinners',
    alert_body=(
        'Chondroitin has weak structural similarity to heparin and case '
        'reports link it to altered INR with warfarin. Tell your surgical '
        'team if you take blood thinners.'
    ),
)

# Validate
for r in rules:
    for cr in r.get('condition_rules', []):
        if cr.get('condition_id') == 'surgery_scheduled':
            sr = r.get('subject_ref', {})
            cid = sr.get('canonical_id') if isinstance(sr, dict) else str(sr)
            hl = cr.get('alert_headline', '')
            ab = cr.get('alert_body', '')
            assert 20 <= len(hl) <= 60, f'{cid} hl len {len(hl)}: "{hl}"'
            assert 60 <= len(ab) <= 200, f'{cid} ab len {len(ab)}: "{ab}"'

remaining = sum(1 for r in rules for cr in r.get('condition_rules', [])
                if cr.get('condition_id') == 'surgery_scheduled')

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'Applied {len(changes)} changes. Surgery rules: 12 → {remaining}')
for c in changes: print(f'  \u2713 {c}')
