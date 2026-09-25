"""Census of authored IQM unspecified forms against the lowest named form.

Read-only. For every parent with an authored unspecified form (the one
scoring_reference_resolver.authored_unknown_form picks) and at least one other
form, prints the gap unspecified bio_score - min(other bio_score), and counts
the parents whose unspecified form scores at or above their best other form. The minimum
here is literal: it still includes analogs, degraded and contaminant forms, so
it is a census, not the reviewed "lowest legitimate form" the policy uses.
Parents without an authored form take the derived lowest - 1 at runtime and
are counted separately.

    python scripts/audits/v41_recovery/unspecified_census.py [--parents]
"""
import collections
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from scoring_reference_resolver import authored_unknown_form  # noqa: E402

IQM = SCRIPTS / 'data' / 'ingredient_quality_map.json'


def census(iqm):
    rows, derived = [], 0
    for parent, entry in iqm.items():
        if not isinstance(entry, dict) or not isinstance(entry.get('forms'), dict):
            continue
        authored = authored_unknown_form(entry)
        if authored is None:
            derived += 1
            continue
        others = [f['bio_score'] for k, f in entry['forms'].items()
                  if k != authored[0] and isinstance(f.get('bio_score'), (int, float))]
        if others:
            rows.append((parent, authored[0], authored[1]['bio_score'], min(others), max(others)))
    return rows, derived


if __name__ == '__main__':
    rows, derived = census(json.loads(IQM.read_text()))
    gaps = collections.Counter(u - m for _, _, u, m, _ in rows)
    print(f'{len(rows)} parents with an authored unspecified form and another form; '
          f'{derived} parents without one (derived lowest - 1)')
    for gap in sorted(gaps):
        print(f'  gap {gap:+d}: {gaps[gap]}')
    print(f'{sum(u >= b for _, _, u, _, b in rows)} parents score the unspecified form at or above their best other form')
    if '--parents' in sys.argv:
        for parent, form, u, m, _ in sorted(rows):
            print(f'{parent}\t{form}\t{u}\t{m}\t{u - m:+d}')
