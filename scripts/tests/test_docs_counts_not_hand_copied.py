#!/usr/bin/env python3
"""Guard against hand-copied entry counts drifting in the top-level docs.

CLAUDE.md's rule is "never hand-copy counts into docs — read
`_metadata.total_entries` from the data file". It was violated anyway: on
2026-09-18 README.md claimed ingredient_quality_map.json held 588 entries
(actual 632), banned_recalled_ingredients.json 143 (actual 171),
rda_optimal_uls.json 47 (actual 77), and "39 curated JSON databases" against
90 files on disk. Every number was stale by a month or more.

The counts were removed rather than refreshed, because refreshing only resets
the drift clock. This test makes reintroduction fail loudly: if someone writes
a count next to a data-file name, it must match the live `_metadata`.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "scripts" / "data"
DOCS = ("README.md", "AGENTS.md", "CLAUDE.md")

# A markdown table row whose cell immediately after the `<name>.json` cell is a
# bare integer -- the exact shape that rotted in README's reference table.
COUNT_ROW = re.compile(r"^\|\s*`([A-Za-z0-9_]+\.json)`\s*\|\s*([\d,]+)\s*\|", re.M)

# Prose of the form "39 curated JSON databases".
CORPUS_COUNT = re.compile(r"(\d+)\s+curated\s+JSON\s+databases", re.I)


def _docs():
    return [(name, (REPO_ROOT / name)) for name in DOCS if (REPO_ROOT / name).is_file()]


@pytest.mark.parametrize("doc_name", DOCS)
def test_no_stale_per_file_entry_counts(doc_name):
    doc = REPO_ROOT / doc_name
    if not doc.is_file():
        pytest.skip(f"{doc_name} not present")

    offenders = []
    for data_file, claimed_raw in COUNT_ROW.findall(doc.read_text()):
        path = DATA_DIR / data_file
        if not path.is_file():
            continue
        try:
            metadata = json.loads(path.read_text()).get("_metadata") or {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        actual = metadata.get("total_entries")
        if actual is None:
            continue
        claimed = int(claimed_raw.replace(",", ""))
        if claimed != actual:
            offenders.append(f"{data_file}: doc says {claimed}, _metadata says {actual}")

    assert not offenders, (
        f"{doc_name} hand-copies entry counts that no longer match the data files:\n  "
        + "\n  ".join(offenders)
        + "\n\nDo not refresh these numbers -- remove them and point readers at "
          "`_metadata.total_entries`. A number here is stale within weeks."
    )


@pytest.mark.parametrize("doc_name", DOCS)
def test_no_stale_corpus_file_count(doc_name):
    doc = REPO_ROOT / doc_name
    if not doc.is_file():
        pytest.skip(f"{doc_name} not present")

    actual = len(list(DATA_DIR.glob("*.json")))
    offenders = [
        int(claimed) for claimed in CORPUS_COUNT.findall(doc.read_text())
        if int(claimed) != actual
    ]

    assert not offenders, (
        f"{doc_name} claims {offenders} curated JSON databases; {DATA_DIR.name}/ holds "
        f"{actual}. Describe the corpus without a number."
    )
