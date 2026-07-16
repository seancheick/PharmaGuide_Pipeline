"""Determinism + precedence guard for botanical blend-child identity resolution.

THE BUG
    `scoring_input_contract._botanical_child_identity` built its candidate
    lookup keys as an unordered SET and returned the first one found in the
    lookup:

        variants = {text, _slug(text), <paren-stripped>, <blend-noise-stripped>, ...}
        for variant in variants:        # <-- set iteration order
            if variant in lookup:
                return lookup[variant]  # first match wins, chosen at random

    CPython randomizes string hashing per process, so when a child name matched
    MORE THAN ONE variant resolving to DIFFERENT identities, the winner depended
    on the interpreter's hash seed.

    Real case (found 2026-07-15 on the full 14,193-product corpus, dsld 28986
    "Refine"): the label reads "Cinnamon powder".

        "cinnamon powder"  -> cinnamon_bark   (a CURATED alias)
        "cinnamon"         -> cinnamon        (only after "powder" is stripped)

    `has_therapeutic_reference` is False for cinnamon_bark and True for
    cinnamon, and the caller emits a `blend_anchor_mass` row only on a
    therapeutic hit — so a coin flip decided whether the product gained a
    328.34mg dose-bearing evidence row. ~2/12 seeds emitted it; ~10/12 did not.
    Two products in the corpus were affected (28986, 70066); 0 changed
    primary_type, which is why it was invisible to type-level checks.

THE DESIGN DECISION THIS PINS
    Precedence is MOST SPECIFIC FIRST — the match that uses the most of the
    original label wins. Each successive transform discards label information
    (parentheticals, then blend-noise words like "powder"/"extract"/"bark"), so
    an earlier match is a stronger identity claim. Curated aliases exist
    precisely to be honoured over a generic stem match.

    This is deliberately NOT `sorted(variants)`: alphabetical order is arbitrary
    and would silently pick a different identity than the label supports.

    It is also the conservative direction. Emitting the row CREDITS the product
    (v4 dose pillar) by attributing a whole blend total to one child; honouring
    the curated alias declines that credit. Under-crediting on ambiguous
    evidence is the safer failure here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import scoring_input_contract as sic  # noqa: E402

# The real corpus case. "Cinnamon powder" is a curated alias of cinnamon_bark,
# and also reduces to the generic `cinnamon` once the strip regex removes
# "powder" — the two identities that were racing.
AMBIGUOUS_LABEL = "Cinnamon powder"

# One process-per-seed is slow, so keep the sweep tight but wide enough to
# actually catch the bug: with a small set, many seeds order identically. The
# original defect showed up on only 2 of 12 seeds — a 2-seed check reports a
# false negative.
_SEEDS = [str(i) for i in range(12)]

_CHILD = textwrap.dedent(
    """
    import json, sys
    sys.path.insert(0, {scripts!r})
    import scoring_input_contract as sic
    print("RESULT" + json.dumps(sic._botanical_child_identity(sys.argv[1])))
    """
)


def _identity_under_seed(name: str, seed: str):
    result = subprocess.run(
        [sys.executable, "-c", _CHILD.format(scripts=str(SCRIPTS_DIR)), name],
        capture_output=True,
        text=True,
        env=dict(os.environ, PYTHONHASHSEED=seed),
        cwd=str(SCRIPTS_DIR),
        check=True,
    )
    line = next(l for l in result.stdout.splitlines() if l.startswith("RESULT"))
    return json.loads(line[len("RESULT"):])


def test_ambiguous_label_resolves_identically_under_every_hash_seed():
    """The property the bug violated: same input, same answer, every run."""
    results = {
        json.dumps(_identity_under_seed(AMBIGUOUS_LABEL, seed), sort_keys=True)
        for seed in _SEEDS
    }
    assert len(results) == 1, (
        f"_botanical_child_identity({AMBIGUOUS_LABEL!r}) is hash-seed dependent; "
        f"got {len(results)} distinct identities across {len(_SEEDS)} seeds: {results}"
    )


def test_the_test_case_is_genuinely_ambiguous():
    """Guard the guard: if the data ever stops mapping this label to two
    different identities, the determinism test above goes vacuous and this
    fixture must be repointed at a live ambiguity."""
    lookup = sic._botanical_identity_lookup()
    assert lookup.get("cinnamon powder", {}).get("canonical_id") == "cinnamon_bark"
    assert lookup.get("cinnamon", {}).get("canonical_id") == "cinnamon"


def test_curated_alias_beats_the_stripped_stem():
    """The design decision: most specific (least transformed) match wins.

    "Cinnamon powder" is an explicit curated alias of cinnamon_bark. Stripping
    "powder" to reach the generic `cinnamon` throws away label information, so
    it must not win.
    """
    identity = sic._botanical_child_identity(AMBIGUOUS_LABEL)
    assert identity is not None
    assert identity["canonical_id"] == "cinnamon_bark", (
        "a blend-noise-stripped stem match outranked a curated alias"
    )


def test_variant_precedence_is_explicitly_ordered_and_deduped():
    variants = sic._botanical_child_variants(AMBIGUOUS_LABEL)

    assert isinstance(variants, list), "precedence must be an ordered sequence"
    assert len(variants) == len(set(variants)), "variants must be deduped"
    # Most specific first: the untouched normalized label.
    assert variants[0] == "cinnamon powder"
    # Least specific last: the blend-noise-stripped stem.
    assert variants.index("cinnamon") > variants.index("cinnamon powder")


def test_paren_stripped_form_ranks_between_text_and_noise_stripped():
    variants = sic._botanical_child_variants("Cinnamon (Cassia) Bark Extract")

    assert variants[0] == "cinnamon (cassia) bark extract"  # the label as written
    assert "cinnamon bark extract" in variants              # parentheticals dropped
    assert "cinnamon (cassia)" in variants                  # blend-noise dropped
    assert variants.index("cinnamon bark extract") < variants.index("cinnamon (cassia)")


def test_noise_stripping_does_not_also_drop_parentheticals():
    """Pins PRE-EXISTING behaviour, deliberately left unchanged.

    The noise-stripped variant is derived from the original text, not from the
    paren-free form, so a name carrying BOTH a parenthetical and noise words
    never reduces to its bare stem ("Cinnamon (Cassia) Bark Extract" yields
    "cinnamon (cassia)", never "cinnamon").

    Whether that gap should be closed is a separate identity-coverage question:
    adding the combined variant would make new names resolve to botanicals and
    would MOVE dose evidence for products that currently get none. This change
    is scoped to determinism, so the behaviour is preserved exactly and pinned
    here so a future reader sees it is a known choice, not an oversight.
    """
    variants = sic._botanical_child_variants("Cinnamon (Cassia) Bark Extract")
    assert "cinnamon" not in variants


@pytest.mark.parametrize(
    "label, expected",
    [
        # Real ambiguous blend-child names from the 14,193-product corpus. Each
        # was a hash-seed coin flip between a specific identity and a generic
        # stem; the precedence rule must pick the specific one every time.
        ("Cinnamon powder", "cinnamon_bark"),          # vs generic `cinnamon`
        ("Turmeric root powder", "turmeric_root_powder"),  # vs generic `turmeric`
        ("Turmeric (root) powder", "turmeric_root_powder"),
        ("Dandelion root powder", "dandelion_root"),   # vs generic `dandelion`
        ("Cranberry powder", "cranberry_fruit"),       # vs generic `cranberry`
        ("Uva Ursi leaf extract", "uva_ursi_leaf"),    # vs generic `uva_ursi`
        ("Grape leaf extract", "grape_leaf"),          # vs generic `grape`
        # `fruits` is a junk generic bucket — a specific identity must win.
        ("Papaya powder", "papaya_fruit_powder"),
        ("Echinacea purpurea root extract", "echinacea_purpurea_root_extract"),
    ],
)
def test_real_corpus_ambiguities_resolve_to_the_specific_identity(label, expected):
    identity = sic._botanical_child_identity(label)
    assert identity is not None, f"{label!r} no longer resolves to any botanical"
    assert identity["canonical_id"] == expected


def test_unmatched_name_still_falls_through_to_the_phrase_fallback():
    """The ordered lookup must not swallow the conservative phrase fallback."""
    identity = sic._botanical_child_identity("Milk thistle seed extract")
    assert identity is not None
    assert identity["canonical_id"]


def test_empty_and_none_names_are_safe():
    assert sic._botanical_child_identity("") is None
    assert sic._botanical_child_identity(None) is None


def test_no_bare_set_iteration_in_identity_resolution():
    """Source guard: a set comprehension re-introduces the defect silently."""
    source = (SCRIPTS_DIR / "scoring_input_contract.py").read_text()
    start = source.index("def _botanical_child_variants")
    end = source.index("def ", source.index("def _botanical_child_identity") + 1)
    body = source[start:end]
    assert "for variant in variants" not in body or "variants: List[str]" in body
    assert "variants = {" not in body, (
        "identity precedence must be an ordered list, not a set — set iteration "
        "order is hash-seed dependent"
    )
