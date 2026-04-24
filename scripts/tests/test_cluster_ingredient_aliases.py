#!/usr/bin/env python3
"""Governance tests for ``scripts/data/cluster_ingredient_aliases.json``.

The alias map is consumed by ``enrich_supplements_v3.py::_collect_synergy_data``
to bridge canonical cluster ingredients (e.g. ``coq10``) to label-form variants
(e.g. ``coenzyme q10``). These tests pin two non-negotiables:

1.  **No ambiguity**: an alias string MUST belong to AT MOST ONE canonical key.
    Without this guard, well-intentioned alias additions silently corrupt
    downstream matching. The canonical example of dangerous overloading is
    ``ALA`` — alpha-lipoic-acid AND alpha-linolenic-acid. Both are real
    nutrients with different goal mappings.

2.  **Aliases must be biochem variants, not marketing terms**: rejects
    generic words like 'support', 'complex', 'blend' that would cause runaway
    false matches.
"""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'data' / 'cluster_ingredient_aliases.json'

# Marketing/composition words that must NEVER appear as full aliases — they
# are too generic and would pull in unrelated products.
FORBIDDEN_GENERIC_TERMS = {
    'support', 'complex', 'blend', 'formula', 'boost', 'matrix',
    'system', 'pack', 'bundle', 'kit', 'supplement', 'extract',
    'concentrate', 'powder', 'capsule', 'tablet',
}


def _load():
    return json.loads(DATA.read_text())


def test_top_level_structure():
    data = _load()
    assert '_metadata' in data
    assert 'aliases' in data
    assert isinstance(data['aliases'], dict)
    assert data['_metadata']['schema_version'] == '1.0.0'


def test_metadata_total_entries_matches_actual():
    data = _load()
    declared = data['_metadata']['total_entries']
    actual = len(data['aliases'])
    assert declared == actual, (
        f'_metadata.total_entries={declared} but found {actual} canonical entries'
    )


def test_alias_values_are_lists_of_strings():
    data = _load()
    for canon, variants in data['aliases'].items():
        assert isinstance(canon, str) and canon.strip(), (
            f'canonical key must be non-empty string, got {canon!r}'
        )
        assert isinstance(variants, list), (
            f'aliases[{canon!r}] must be a list, got {type(variants).__name__}'
        )
        assert variants, f'aliases[{canon!r}] must not be empty'
        for v in variants:
            assert isinstance(v, str) and v.strip(), (
                f'aliases[{canon!r}] contains non-string entry: {v!r}'
            )


def test_no_alias_overloading_across_canonicals():
    """An alias string may belong to AT MOST ONE canonical key.

    Catches the ``ALA`` problem and prevents future accidental overloading
    when contributors add aliases without seeing the full map.
    """
    data = _load()
    alias_to_canon: dict = {}
    conflicts = []
    for canon, variants in data['aliases'].items():
        for v in variants:
            v_norm = v.lower().strip()
            if v_norm in alias_to_canon and alias_to_canon[v_norm] != canon:
                conflicts.append(
                    f'{v!r} belongs to both {alias_to_canon[v_norm]!r} and {canon!r}'
                )
            alias_to_canon[v_norm] = canon
    assert not conflicts, (
        'Alias overloading detected (ambiguity bug):\n  ' + '\n  '.join(conflicts)
    )


def test_no_canonical_appears_as_its_own_alias():
    """Catches accidental self-listing — wastes resolver time and signals
    sloppy authoring."""
    data = _load()
    bad = []
    for canon, variants in data['aliases'].items():
        canon_norm = canon.lower().strip()
        for v in variants:
            if v.lower().strip() == canon_norm:
                bad.append(f'{canon!r} lists itself as alias')
    assert not bad, '\n  '.join(bad)


def test_aliases_are_not_generic_marketing_terms():
    """Guard against contributors adding 'support', 'complex' etc. as aliases.

    A single bare 'support' alias would match every "Immune Support" /
    "Joint Support" / "Energy Support" product and explode false-positive
    cluster matches across the catalog.
    """
    data = _load()
    bad = []
    for canon, variants in data['aliases'].items():
        for v in variants:
            v_norm = v.lower().strip()
            tokens = v_norm.split()
            # Reject if the alias is JUST a generic word
            if v_norm in FORBIDDEN_GENERIC_TERMS:
                bad.append(f'{canon}: alias {v!r} is a forbidden generic term')
            # Reject if the alias is just a single generic word with one prefix
            if len(tokens) == 1 and tokens[0] in FORBIDDEN_GENERIC_TERMS:
                bad.append(f'{canon}: alias {v!r} is a single generic word')
    assert not bad, '\n  '.join(bad)


def test_aliases_have_minimum_length():
    """1-char and 2-char aliases would substring-match too aggressively.
    Even biochem abbreviations (DHA, EPA, NAC, MK7) are 3+ characters."""
    data = _load()
    bad = []
    for canon, variants in data['aliases'].items():
        for v in variants:
            if len(v.strip()) < 3:
                bad.append(f'{canon}: alias {v!r} too short (< 3 chars)')
    assert not bad, '\n  '.join(bad)


def test_canonical_keys_are_lowercase():
    """Canonical keys MUST match the lowercase normalized form used by the
    cluster matcher (``self._normalize_text(cluster_ing)``). Mixed-case keys
    silently miss alias lookups."""
    data = _load()
    bad = [k for k in data['aliases'] if k != k.lower()]
    assert not bad, f'Non-lowercase canonical keys: {bad}'
