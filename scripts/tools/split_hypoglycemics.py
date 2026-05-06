#!/usr/bin/env python3
"""Split the broad 'hypoglycemics' drug class into two risk-stratified subclasses.

Usage:
    python3 scripts/tools/split_hypoglycemics.py [--dry-run]

What it does:
1. Expands drug_class_vocab.json: replaces 'hypoglycemics' (user_selectable=true)
   with 'hypoglycemics_high_risk' + 'hypoglycemics_lower_risk'.
2. Expands clinical_risk_taxonomy.json drug_classes[] similarly.
3. For each interaction rule with drug_class_rules targeting 'hypoglycemics':
   - Creates TWO drug_class_rule entries (one per subclass)
   - Applies severity remapping per clinical category:
     * monitor rules: both subclasses stay monitor
     * caution rules: high_risk=caution, lower_risk=monitor
     * avoid rules:   high_risk=avoid,   lower_risk=caution
     * niacin (raises glucose): both stay caution
   - Duplicates dose_thresholds for both subclasses
4. Bumps schema 6.0.3 → 6.1.0 (breaking change: new drug_class IDs).

Clinical rationale:
- Insulin, sulfonylureas, meglitinides cause glucose-independent insulin
  release → real hypoglycemia risk when combined with glucose-lowering supps.
- Metformin, GLP-1 RAs, SGLT2i, DPP-4i work via glucose-dependent mechanisms
  → rarely cause hypoglycemia alone → lower interaction risk.
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, 'data', 'ingredient_interaction_rules.json')
VOCAB_PATH = os.path.join(ROOT, 'data', 'drug_class_vocab.json')
TAXONOMY_PATH = os.path.join(ROOT, 'data', 'clinical_risk_taxonomy.json')

DRY_RUN = '--dry-run' in sys.argv

# ── Severity remap table ──
# key = canonical_id, value = (high_risk_severity, lower_risk_severity)
# DEFAULT: if not in table, use the split logic below.
SEVERITY_OVERRIDES = {
    # Niacin RAISES glucose — equally bad for all diabetes meds
    'vitamin_b3_niacin': ('caution', 'caution'),
    # Berberine is potent enough that even metformin users should be cautious
    'berberine_supplement': ('avoid', 'caution'),
}

# For dose_thresholds, same override logic
DOSE_THRESHOLD_OVERRIDES = {
    'berberine_supplement': {
        'severity_if_met':     ('avoid',   'caution'),
        'severity_if_not_met': ('caution', 'monitor'),
    },
    'vanadyl_sulfate': {
        'severity_if_met':     ('caution', 'monitor'),
        'severity_if_not_met': ('monitor', 'monitor'),
    },
    'olive_leaf': {
        'severity_if_met':     ('caution', 'monitor'),
        'severity_if_not_met': ('monitor', 'monitor'),
    },
}


def default_severity_split(severity: str) -> tuple:
    """Default split: high_risk keeps severity, lower_risk drops one tier."""
    MAP = {
        'contraindicated': ('contraindicated', 'avoid'),
        'avoid':           ('avoid',   'caution'),
        'caution':         ('caution', 'monitor'),
        'monitor':         ('monitor', 'monitor'),
        'informational':   ('informational', 'informational'),
    }
    return MAP.get(severity, (severity, severity))


def split_drug_class_rule(rule: dict, canonical_id: str) -> list:
    """Split one drug_class_rule dict into two (high_risk + lower_risk)."""
    sev = rule['severity']
    if canonical_id in SEVERITY_OVERRIDES:
        hr_sev, lr_sev = SEVERITY_OVERRIDES[canonical_id]
    else:
        hr_sev, lr_sev = default_severity_split(sev)

    hr = copy.deepcopy(rule)
    hr['drug_class_id'] = 'hypoglycemics_high_risk'
    hr['severity'] = hr_sev

    lr = copy.deepcopy(rule)
    lr['drug_class_id'] = 'hypoglycemics_lower_risk'
    lr['severity'] = lr_sev

    # Update profile_gate.requires.drug_classes_any
    for r in (hr, lr):
        gate = r.get('profile_gate', {})
        req = gate.get('requires', {})
        dca = req.get('drug_classes_any', [])
        if 'hypoglycemics' in dca:
            dca[dca.index('hypoglycemics')] = r['drug_class_id']

    return [hr, lr]


def split_dose_threshold(dt: dict, canonical_id: str) -> list:
    """Split one dose_threshold dict into two for the subclasses."""
    hr = copy.deepcopy(dt)
    lr = copy.deepcopy(dt)

    hr['target_id'] = 'hypoglycemics_high_risk'
    lr['target_id'] = 'hypoglycemics_lower_risk'

    if canonical_id in DOSE_THRESHOLD_OVERRIDES:
        ovr = DOSE_THRESHOLD_OVERRIDES[canonical_id]
        hr['severity_if_met'] = ovr['severity_if_met'][0]
        lr['severity_if_met'] = ovr['severity_if_met'][1]
        hr['severity_if_not_met'] = ovr['severity_if_not_met'][0]
        lr['severity_if_not_met'] = ovr['severity_if_not_met'][1]
    else:
        hr_met, lr_met = default_severity_split(dt.get('severity_if_met', 'caution'))
        hr_nmet, lr_nmet = default_severity_split(dt.get('severity_if_not_met', 'monitor'))
        hr['severity_if_met'] = hr_met
        lr['severity_if_met'] = lr_met
        hr['severity_if_not_met'] = hr_nmet
        lr['severity_if_not_met'] = lr_nmet

    # Update profile_gate.requires.drug_classes_any
    for r in (hr, lr):
        gate = r.get('profile_gate', {})
        req = gate.get('requires', {})
        dca = req.get('drug_classes_any', [])
        if 'hypoglycemics' in dca:
            dca[dca.index('hypoglycemics')] = r['target_id']
        # Also update dose block inside gate if present
        dose = gate.get('dose', {})
        if dose:
            if 'severity_if_met' in dose:
                dose['severity_if_met'] = r['severity_if_met']
            if 'severity_if_not_met' in dose:
                dose['severity_if_not_met'] = r['severity_if_not_met']

    return [hr, lr]


def main():
    # ── Load files ──
    with open(RULES_PATH) as f:
        rules_data = json.load(f)
    with open(VOCAB_PATH) as f:
        vocab_data = json.load(f)
    with open(TAXONOMY_PATH) as f:
        tax_data = json.load(f)

    changes = []

    # ── 1. Expand drug_class_vocab.json ──
    new_classes = []
    for dc in vocab_data['drug_classes']:
        if dc['id'] == 'hypoglycemics':
            new_classes.append({
                'id': 'hypoglycemics_high_risk',
                'name': 'Diabetes meds — Insulin, Sulfonylureas, Meglitinides',
                'notes': 'These medications push blood sugar down regardless of current glucose level, creating real hypoglycemia risk when combined with glucose-lowering supplements.',
                'examples': ['insulin (all types)', 'glipizide (Glucotrol)', 'glyburide (Micronase)', 'glimepiride (Amaryl)', 'repaglinide (Prandin)', 'nateglinide (Starlix)'],
                'rx_status': 'rx_only',
                'user_selectable': True,
            })
            new_classes.append({
                'id': 'hypoglycemics_lower_risk',
                'name': 'Diabetes meds — Metformin, GLP-1 RAs, SGLT2i, DPP-4i',
                'notes': 'These medications work via glucose-dependent mechanisms and rarely cause hypoglycemia alone. Lower interaction risk with glucose-lowering supplements.',
                'examples': ['metformin (Glucophage)', 'semaglutide (Ozempic, Wegovy)', 'liraglutide (Victoza)', 'empagliflozin (Jardiance)', 'dapagliflozin (Farxiga)', 'sitagliptin (Januvia)', 'linagliptin (Tradjenta)'],
                'rx_status': 'rx_only',
                'user_selectable': True,
            })
            changes.append('drug_class_vocab: replaced hypoglycemics with hypoglycemics_high_risk + hypoglycemics_lower_risk')
        else:
            new_classes.append(dc)
    vocab_data['drug_classes'] = new_classes
    vocab_data['_metadata']['total_entries'] = len(new_classes)
    vocab_data['_metadata']['user_selectable_count'] = sum(1 for d in new_classes if d.get('user_selectable'))
    vocab_data['_metadata']['last_updated'] = '2026-05-06'

    # ── 2. Expand clinical_risk_taxonomy.json ──
    tax_dc = tax_data.get('drug_classes', [])
    new_tax_dc = []
    for dc in tax_dc:
        if dc.get('id') == 'hypoglycemics':
            new_tax_dc.append({**dc, 'id': 'hypoglycemics_high_risk', 'label': 'Glucose-Lowering Medications (High-Risk)'})
            new_tax_dc.append({**dc, 'id': 'hypoglycemics_lower_risk', 'label': 'Glucose-Lowering Medications (Lower-Risk)'})
            changes.append('clinical_risk_taxonomy: split hypoglycemics into 2 subclasses')
        else:
            new_tax_dc.append(dc)
    tax_data['drug_classes'] = new_tax_dc

    # ── 3. Split interaction rules ──
    rules = rules_data['interaction_rules']
    rule_changes = 0
    dt_changes = 0

    for r in rules:
        sr = r.get('subject_ref', {})
        cid = sr.get('canonical_id') if isinstance(sr, dict) else sr

        # Split drug_class_rules
        new_dcr = []
        for dr in r.get('drug_class_rules', []):
            if isinstance(dr, dict) and dr.get('drug_class_id') == 'hypoglycemics':
                new_dcr.extend(split_drug_class_rule(dr, cid))
                rule_changes += 1
            else:
                new_dcr.append(dr)
        r['drug_class_rules'] = new_dcr

        # Split dose_thresholds
        new_dt = []
        for dt in r.get('dose_thresholds', []):
            if isinstance(dt, dict) and dt.get('target_id') == 'hypoglycemics':
                new_dt.extend(split_dose_threshold(dt, cid))
                dt_changes += 1
            else:
                new_dt.append(dt)
        r['dose_thresholds'] = new_dt

    changes.append(f'interaction_rules: split {rule_changes} drug_class_rules + {dt_changes} dose_thresholds')

    # ── 4. Schema bump ──
    rules_data['_metadata']['schema_version'] = '6.1.0'
    rules_data['_metadata']['flutter_schema_version'] = '6.1.0'
    rules_data['_metadata']['last_updated'] = '2026-05-06'
    rules_data['_metadata']['migration']['completed_migrations'].append({
        'from': '6.0.3',
        'to': '6.1.0',
        'date': '2026-05-06',
        'summary': f'Hypoglycemics drug-class split: replaced single "hypoglycemics" with '
                   f'"hypoglycemics_high_risk" (insulin/sulfonylureas/meglitinides) and '
                   f'"hypoglycemics_lower_risk" (metformin/GLP-1 RAs/SGLT2i/DPP-4i). '
                   f'Split {rule_changes} drug_class_rules + {dt_changes} dose_thresholds. '
                   f'Lower-risk subclass gets reduced severity on most rules.'
    })
    changes.append('schema: 6.0.3 → 6.1.0')

    # ── Write ──
    if DRY_RUN:
        print('DRY RUN — no files written')
    else:
        for path, data in [(RULES_PATH, rules_data), (VOCAB_PATH, vocab_data), (TAXONOMY_PATH, tax_data)]:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write('\n')

    # ── Report ──
    print(f'\nApplied {len(changes)} changes:')
    for c in changes:
        print(f'  {"[DRY]" if DRY_RUN else "✓"} {c}')

    # ── Sanity checks ──
    # No orphan "hypoglycemics" in rules
    rules_body = json.dumps(rules_data['interaction_rules'])
    # The string "hypoglycemics" appears inside "hypoglycemics_high_risk" etc, so check for standalone
    import re
    orphans = re.findall(r'"drug_class_id":\s*"hypoglycemics"(?!_)', rules_body)
    orphans += re.findall(r'"target_id":\s*"hypoglycemics"(?!_)', rules_body)
    if orphans:
        print(f'\n⚠ WARNING: {len(orphans)} orphan "hypoglycemics" references remain!')
        sys.exit(1)
    else:
        print('\n✓ No orphan "hypoglycemics" references in rules')

    # Count new entries
    hr_count = rules_body.count('"hypoglycemics_high_risk"')
    lr_count = rules_body.count('"hypoglycemics_lower_risk"')
    print(f'✓ hypoglycemics_high_risk references: {hr_count}')
    print(f'✓ hypoglycemics_lower_risk references: {lr_count}')


if __name__ == '__main__':
    main()
