"""Census of named salt/chelate aliases on authored unspecified forms (read-only).

A label that names a salt ("Manganese Fumarate") discloses a form. When that
name is an alias of the parent's unspecified form, the row scores as
nondisclosure (lowest eligible - 1). Some are deliberate (an ambiguous
oxidation state such as "iron sulfate", or a compound sold only as one salt
such as DMG HCl); the rest are curation candidates, reviewed one at a time.

Definition: aliases of scoring_reference_resolver.authored_unknown_form whose
text contains a salt or chelate word (SALT_WORDS, whole-word, case-insensitive).

    python scripts/audits/v41_recovery/unspecified_named_alias_census.py
"""
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from scoring_reference_resolver import authored_unknown_form  # noqa: E402

SALT_WORDS = ('chelate', 'glycinate', 'bisglycinate', 'citrate', 'malate', 'oxide', 'carbonate', 'sulfate',
              'chloride', 'gluconate', 'picolinate', 'ascorbate', 'borate', 'phosphate', 'aspartate', 'fumarate',
              'lactate', 'acetate', 'succinate', 'orotate', 'taurate', 'hydrochloride', 'hcl', 'selenite',
              'selenate', 'iodide', 'stearate', 'hyaluronate')
PATTERN = re.compile(r'\b(' + '|'.join(SALT_WORDS) + r')\b', re.IGNORECASE)


def census(iqm):
    rows = []
    for key, entry in iqm.items():
        if key == '_metadata' or not isinstance(entry, dict):
            continue
        authored = authored_unknown_form(entry)
        if not authored:
            continue
        for alias in authored[1].get('aliases') or []:
            if PATTERN.search(alias):
                rows.append((key, authored[0], authored[1].get('bio_score'), alias))
    return rows


if __name__ == '__main__':
    rows = census(json.loads((SCRIPTS / 'data' / 'ingredient_quality_map.json').read_text()))
    print(f'{len(rows)} aliases on {len({r[0] for r in rows})} parents')
    for key, form, bio, alias in rows:
        print(f'{key}\t{form}\t{bio}\t{alias}')
