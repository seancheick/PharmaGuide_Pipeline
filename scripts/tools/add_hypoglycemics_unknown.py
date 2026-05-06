#!/usr/bin/env python3
"""Add hypoglycemics_unknown as a third bucket for legacy/unrefined profiles.

Clinical rationale (from Dr. Pham review):
- Auto-mapping legacy → high_risk creates false precision
- Unknown users get caution (middle ground) until they refine
- Severity: min(high_risk_severity, 'caution') — never stricter than high_risk,
  but capped at caution since we don't know the actual risk class

Usage:
    python3 scripts/tools/add_hypoglycemics_unknown.py [--dry-run]
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

# Severity ordering for min()
SEV_ORDER = ['informational', 'monitor', 'caution', 'avoid', 'contraindicated']


def sev_min(a: str, b: str) -> str:
    """Return the less-severe of two severities."""
    return a if SEV_ORDER.index(a) <= SEV_ORDER.index(b) else b


def unknown_severity(high_risk_sev: str) -> str:
    """Unknown gets min(high_risk, caution) — never stricter, but capped."""
    return sev_min(high_risk_sev, 'caution')


def main():
    with open(RULES_PATH) as f:
        rules_data = json.load(f)
    with open(VOCAB_PATH) as f:
        vocab_data = json.load(f)
    with open(TAXONOMY_PATH) as f:
        tax_data = json.load(f)

    changes = []

    # ── 1. Add to drug_class_vocab.json ──
    vocab_ids = {d['id'] for d in vocab_data['drug_classes']}
    if 'hypoglycemics_unknown' not in vocab_ids:
        # Insert right after hypoglycemics_lower_risk
        new_classes = []
        for dc in vocab_data['drug_classes']:
            new_classes.append(dc)
            if dc['id'] == 'hypoglycemics_lower_risk':
                new_classes.append({
                    'id': 'hypoglycemics_unknown',
                    'name': 'Diabetes medication (not yet specified)',
                    'notes': 'You selected diabetes medication but haven\'t specified which type. Tap to refine — your warnings will be more accurate.',
                    'examples': ['Please select Insulin/Sulfonylureas or Metformin/GLP-1 RAs above'],
                    'rx_status': 'rx_only',
                    'user_selectable': True,
                })
        vocab_data['drug_classes'] = new_classes
        vocab_data['_metadata']['total_entries'] = len(new_classes)
        vocab_data['_metadata']['user_selectable_count'] = sum(
            1 for d in new_classes if d.get('user_selectable')
        )
        vocab_data['_metadata']['last_updated'] = '2026-05-06'
        changes.append('drug_class_vocab: added hypoglycemics_unknown')

    # ── 2. Add to clinical_risk_taxonomy.json ──
    tax_ids = {d.get('id') for d in tax_data.get('drug_classes', [])}
    if 'hypoglycemics_unknown' not in tax_ids:
        new_tax = []
        for dc in tax_data['drug_classes']:
            new_tax.append(dc)
            if dc.get('id') == 'hypoglycemics_lower_risk':
                new_tax.append({
                    **dc,
                    'id': 'hypoglycemics_unknown',
                    'label': 'Glucose-Lowering Medications (Unspecified)',
                })
        tax_data['drug_classes'] = new_tax
        changes.append('clinical_risk_taxonomy: added hypoglycemics_unknown')

    # ── 3. Add unknown drug_class_rules to each split rule ──
    rules = rules_data['interaction_rules']
    added = 0
    dt_added = 0

    for r in rules:
        # Check if this rule has high_risk but not unknown
        dcr = r.get('drug_class_rules', [])
        hr_rules = [d for d in dcr if d.get('drug_class_id') == 'hypoglycemics_high_risk']
        has_unknown = any(d.get('drug_class_id') == 'hypoglycemics_unknown' for d in dcr)

        if hr_rules and not has_unknown:
            for hr in hr_rules:
                unk = copy.deepcopy(hr)
                unk['drug_class_id'] = 'hypoglycemics_unknown'
                unk['severity'] = unknown_severity(hr['severity'])
                # Update profile_gate
                gate = unk.get('profile_gate', {})
                req = gate.get('requires', {})
                dca = req.get('drug_classes_any', [])
                for j, v in enumerate(dca):
                    if v == 'hypoglycemics_high_risk':
                        dca[j] = 'hypoglycemics_unknown'
                dcr.append(unk)
                added += 1

        # Same for dose_thresholds
        dts = r.get('dose_thresholds', [])
        hr_dts = [d for d in dts if d.get('target_id') == 'hypoglycemics_high_risk']
        has_unk_dt = any(d.get('target_id') == 'hypoglycemics_unknown' for d in dts)

        if hr_dts and not has_unk_dt:
            for hr in hr_dts:
                unk = copy.deepcopy(hr)
                unk['target_id'] = 'hypoglycemics_unknown'
                unk['severity_if_met'] = unknown_severity(hr['severity_if_met'])
                unk['severity_if_not_met'] = unknown_severity(hr['severity_if_not_met'])
                # Update profile_gate
                gate = unk.get('profile_gate', {})
                req = gate.get('requires', {})
                dca = req.get('drug_classes_any', [])
                for j, v in enumerate(dca):
                    if v == 'hypoglycemics_high_risk':
                        dca[j] = 'hypoglycemics_unknown'
                dose = gate.get('dose', {})
                if dose:
                    dose['severity_if_met'] = unk['severity_if_met']
                    dose['severity_if_not_met'] = unk['severity_if_not_met']
                dts.append(unk)
                dt_added += 1

    changes.append(f'interaction_rules: added {added} unknown drug_class_rules + {dt_added} dose_thresholds')

    # Update schema metadata
    rules_data['_metadata']['last_updated'] = '2026-05-06'

    # ── Write ──
    if DRY_RUN:
        print('DRY RUN — no files written')
    else:
        for path, data in [(RULES_PATH, rules_data), (VOCAB_PATH, vocab_data), (TAXONOMY_PATH, tax_data)]:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write('\n')

    print(f'\nApplied {len(changes)} changes:')
    for c in changes:
        print(f'  {"[DRY]" if DRY_RUN else "✓"} {c}')

    # Sanity check
    rules_body = json.dumps(rules_data['interaction_rules'])
    unk_count = rules_body.count('"hypoglycemics_unknown"')
    print(f'\n✓ hypoglycemics_unknown references: {unk_count}')

    # Verify severity: unknown should never be stricter than high_risk
    for r in rules:
        dcr = r.get('drug_class_rules', [])
        hr = {d['drug_class_id']: d['severity'] for d in dcr if d.get('drug_class_id') == 'hypoglycemics_high_risk'}
        unk = {d['drug_class_id']: d['severity'] for d in dcr if d.get('drug_class_id') == 'hypoglycemics_unknown'}
        if hr and unk:
            hr_idx = SEV_ORDER.index(hr['hypoglycemics_high_risk'])
            unk_idx = SEV_ORDER.index(unk['hypoglycemics_unknown'])
            if unk_idx > hr_idx:
                sr = r.get('subject_ref', {})
                cid = sr.get('canonical_id') if isinstance(sr, dict) else sr
                print(f'⚠ {cid}: unknown ({unk["hypoglycemics_unknown"]}) stricter than high_risk ({hr["hypoglycemics_high_risk"]})')
                sys.exit(1)
    print('✓ Unknown severity never exceeds high_risk severity')


if __name__ == '__main__':
    main()
