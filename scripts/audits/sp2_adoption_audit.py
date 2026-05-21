"""SP-2 adoption audit — enumerates every consumer of legacy classification
fields (`supplement_type`, `primary_category`, `category_breakdown`) in the
v4 surface + shadow scorer + build_final_db.

Produces a deterministic list of (file, line, snippet) for the regression
test in `scripts/tests/test_v4_taxonomy_adoption.py`. Any new legacy read
added to the v4 surface without updating the allowlist fails the regression
test.

Source of truth: `scripts/audits/sp2_adoption/INVENTORY.md`.

Run standalone:
    python3 scripts/audits/sp2_adoption_audit.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"

# Files in SP-2 scope (v4 + shadow + final_db). v3 score_supplements.py is
# deliberately excluded — that scope is deferred (see INVENTORY.md
# "Deferred" section).
SCOPED_FILES = [
    SCRIPTS_ROOT / "scoring_v4" / "router.py",
    SCRIPTS_ROOT / "scoring_v4" / "confidence.py",
    SCRIPTS_ROOT / "scoring_v4" / "modules" / "generic_helpers.py",
    SCRIPTS_ROOT / "scoring_v4" / "modules" / "generic_trust.py",
    SCRIPTS_ROOT / "scoring_v4" / "modules" / "generic_transparency.py",
    SCRIPTS_ROOT / "score_supplements_v4_shadow.py",
    SCRIPTS_ROOT / "build_final_db.py",
]

# Legacy-classification patterns we flag.
LEGACY_PATTERNS = (
    re.compile(r"\bsupplement_type\b"),
    re.compile(r"\bprimary_category\b"),
    re.compile(r"\bcategory_breakdown\b"),
)


@dataclass(frozen=True)
class Hit:
    file: str  # relative path from REPO_ROOT
    line: int
    snippet: str  # trimmed line content


def _is_pure_comment_or_docstring_text(line: str) -> bool:
    """Heuristic: line is documentation, not code.

    Returns True for:
      - Lines starting with `#` after whitespace (pure comment)
      - Lines where every occurrence of a legacy pattern is wrapped in
        backticks (markdown code-span inside a docstring)
      - Lines that look like prose (no `=`, `(`, `.`, `[`, `:` operators
        adjacent to the pattern)

    This keeps the count tracking real code reads, not documentation that
    describes the legacy fields.
    """
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    # Backtick-wrapped occurrence — pure documentation
    for pattern_re in LEGACY_PATTERNS:
        for match in pattern_re.finditer(line):
            start, end = match.span()
            before = line[max(0, start - 1):start]
            after = line[end:end + 1]
            if before == "`" or after == "`":
                # This match is in backticks; check if ALL matches are
                continue
            return False
        # If all matches were backtick-wrapped, this pattern is doc-only
    # All patterns came back doc-only (or no match)
    return all(
        all(
            (line[max(0, m.start() - 1):m.start()] == "`"
             or line[m.end():m.end() + 1] == "`")
            for m in pattern_re.finditer(line)
        )
        for pattern_re in LEGACY_PATTERNS
        if pattern_re.search(line)
    )


def _scan_file(path: Path) -> List[Hit]:
    """Walk a file line by line, tracking triple-quote state, and emit a
    Hit for each legacy-classification read that is real code (not a
    comment, not inside a docstring).
    """
    hits: List[Hit] = []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return hits
    rel = str(path.relative_to(REPO_ROOT))

    in_triple = False  # True when we are inside a multi-line triple-quoted block
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()

        # Track triple-quote state. Handle the four cases:
        #   - line opens AND closes a docstring on the same line
        #   - line opens a docstring that continues
        #   - line is inside a continuing docstring
        #   - line closes a continuing docstring
        triple_count = raw.count('"""') + raw.count("'''")
        if in_triple:
            # We are inside a docstring. Skip this line entirely — even if
            # it contains the legacy pattern, it is documentation.
            if triple_count % 2 == 1:
                in_triple = False
            continue
        if triple_count % 2 == 1:
            # This line opens a docstring that continues. Skip — and remember
            # we are now inside one.
            in_triple = True
            continue
        # triple_count is 0 or even (line opens AND closes a docstring on
        # itself). For the even case, we still want to skip if the entire
        # remaining text after stripping triple-quote markers is just doc.
        # Pragmatic: if a line has `"""` AND a legacy pattern, treat the
        # legacy pattern as doc text on that line.
        if triple_count >= 2 and any(p.search(line) for p in LEGACY_PATTERNS):
            continue

        if not line:
            continue
        if not any(p.search(line) for p in LEGACY_PATTERNS):
            continue
        # Filter pure-comment lines + backtick-wrapped doc references.
        if _is_pure_comment_or_docstring_text(raw):
            continue
        hits.append(Hit(file=rel, line=idx, snippet=line[:160]))
    return hits


def enumerate_sp2_legacy_reads() -> List[Hit]:
    """Return every line in the SP-2 scoped files that reads a legacy
    classification field. Order is stable (sorted by file then line).
    """
    all_hits: List[Hit] = []
    for path in SCOPED_FILES:
        all_hits.extend(_scan_file(path))
    return sorted(all_hits, key=lambda h: (h.file, h.line))


def hits_grouped_by_file() -> dict[str, List[Hit]]:
    out: dict[str, List[Hit]] = {}
    for hit in enumerate_sp2_legacy_reads():
        out.setdefault(hit.file, []).append(hit)
    return out


def main() -> None:
    grouped = hits_grouped_by_file()
    total = sum(len(v) for v in grouped.values())
    print(f"SP-2 adoption audit — {total} legacy-classification reads "
          f"across {len(grouped)} files\n")
    for file, hits in grouped.items():
        print(f"## {file}  ({len(hits)} hits)")
        for hit in hits:
            print(f"  L{hit.line:>5}  {hit.snippet}")
        print()


if __name__ == "__main__":
    main()
