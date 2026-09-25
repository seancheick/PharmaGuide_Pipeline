"""Census of parent-identity aliases on specific IQM forms (read-only).

A label that names only the ingredient ("HMB") discloses no form. When that
name is an alias of a specific form, the row is scored as that form
(HMB -> HMB-Ca). This lists every such alias so each entry can be reviewed.

Definition:
- Parents with at least two forms (source preparations excluded); the
  parent's authored unspecified form is not a specific form.
- Identity names: the parent key, its standard name and each parenthetical
  part of it, and its parent-level aliases, normalized to lowercase
  alphanumerics.
- ``exact``: a specific form's name or alias equals an identity name.
- ``parent_like``: equal after removing packaging words (PACKAGING_WORDS).
- Impact (--corpus DIR): frozen enriched rows whose matched form is that form
  and whose matched alias is that alias.

Chemically single-form identities (plain "leucine" is L-leucine) are
legitimate; aliases that pick one of several real forms invent a form.

    python scripts/audits/v41_recovery/bare_alias_census.py [--corpus DIR]
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from scoring_reference_resolver import authored_unknown_form  # noqa: E402

IQM = SCRIPTS / 'data' / 'ingredient_quality_map.json'
PACKAGING_WORDS = {'supplement', 'supplements', 'powder', 'capsule', 'capsules', 'tablet',
                   'tablets', 'pure', 'standard', 'softgel', 'softgels'}


def norm(value):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower())).strip()


def strip_packaging(value):
    return ' '.join(w for w in norm(value).split() if w not in PACKAGING_WORDS)


def identity_names(key, entry):
    standard = str(entry.get('standard_name') or '')
    names = {norm(key.replace('_', ' ')), norm(standard)}
    names.update(norm(part) for part in re.split(r'[()]', standard))
    names.update(norm(alias) for alias in entry.get('aliases') or [])
    return {name for name in names if name}


def census(iqm):
    rows = []
    for key, entry in iqm.items():
        if key == '_metadata' or not isinstance(entry, dict):
            continue
        forms = {n: f for n, f in (entry.get('forms') or {}).items()
                 if isinstance(f, dict) and f.get('alias_identity_scope') != 'source_preparation'}
        if len(forms) < 2:
            continue
        authored = authored_unknown_form(entry)
        names = identity_names(key, entry)
        for form_name, form in forms.items():
            if authored and form_name == authored[0]:
                continue
            for alias in [form_name] + list(form.get('aliases') or []):
                if norm(alias) in names:
                    rows.append((key, form_name, alias, 'exact'))
                elif strip_packaging(alias) and strip_packaging(alias) in names:
                    rows.append((key, form_name, alias, 'parent_like'))
    return rows


def impact(corpus, rows):
    wanted = {(k, f, norm(a)) for k, f, a, _ in rows}
    counts = collections.Counter()
    for path in glob.glob(f'{corpus}/*/enriched/enriched_cleaned_batch_*.json'):
        for product in json.load(open(path)):
            for row in (product.get('ingredient_quality_data') or {}).get('ingredients') or []:
                hit = (row.get('canonical_id'), row.get('form_id'), norm(row.get('matched_alias')))
                if hit in wanted:
                    counts[hit] += 1
    return counts


if __name__ == '__main__':
    rows = census(json.loads(IQM.read_text()))
    parents = {k for k, *_ in rows}
    print(f'{len(rows)} aliases on {len(parents)} multi-form parents '
          f'({sum(t == "exact" for *_, t in rows)} exact, {sum(t == "parent_like" for *_, t in rows)} parent_like)')
    counts = impact(sys.argv[sys.argv.index('--corpus') + 1], rows) if '--corpus' in sys.argv else {}
    for key, form, alias, tier in sorted(rows, key=lambda r: (-counts.get((r[0], r[1], norm(r[2])), 0), r)):
        print(f'{counts.get((key, form, norm(alias)), 0)}\t{tier}\t{key}\t{form}\t{alias}')
