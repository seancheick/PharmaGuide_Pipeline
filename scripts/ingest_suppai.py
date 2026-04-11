"""Ingest the supp.ai evidence corpus into a compact research_pairs JSON.

Reads the 5-file supp.ai dump (cui_metadata / sentence_dict / paper_metadata
+ interaction_id_dict + meta), filters pairs to only those where at least
one side resolves to a canonical supplement from ingredient_quality_map.json
or a known drug CUI, keeps the top-N most informative non-retracted
sentences per pair, and emits a deterministic JSON artifact under
``scripts/interaction_db_output/research_pairs.json``.

The artifact is the Tier 2 feed for ``build_interaction_db.py`` which ships
it into the ``research_pairs`` SQLite table (see §11.2, §11.3 of
INTERACTION_DB_SPEC.md). Shape is stable and byte-identical across runs
for the same inputs and ``--build-time`` argument.

Style notes:
- Stdlib only (``json`` / ``argparse`` / ``pathlib`` / ``dataclasses``).
- Pure functions with explicit inputs so tests can hand in fakes.
- Paper metadata is **never** shipped verbatim; we retain only
  ``{pmid, year, clinical_study, human_study}`` per sentence to protect
  bundle size and avoid leaking author/title data that is not needed for
  the consumer app UX.
- Retracted papers are hard-filtered — they never appear in output.
- Output ordering is fully deterministic: rows are sorted by
  ``(cui_a, cui_b)``; sentences within a row are sorted by
  ``(-score, pmid, uid)``.

Run:
    python3 scripts/ingest_suppai.py \\
        --suppai-dir "/Users/seancheick/Downloads/Supp ai DB/" \\
        --iqm scripts/data/ingredient_quality_map.json \\
        --drug-classes scripts/data/drug_classes.json \\
        --output scripts/interaction_db_output/research_pairs.json \\
        --report scripts/interaction_db_output/ingest_suppai_report.json \\
        --build-time 2026-04-11T00:00:00Z
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SCHEMA_VERSION = "1.0.0"
DEFAULT_MAX_SENTENCES_PER_PAIR = 3
DEFAULT_SUPPAI_DIR = Path("/Users/seancheick/Downloads/Supp ai DB/")
BOILERPLATE_LEN_THRESHOLD = 40  # sentences shorter than this are deprioritized
SENTENCE_MAX_SCORE_LEN = 400  # long-sentence bonus caps here


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #


@dataclass
class PairAnchor:
    """Anchors for deciding if a supp.ai pair is worth keeping.

    A pair is kept when **at least one** of its CUIs appears in either
    ``supplement_cuis`` (IQM mapping) or ``known_drug_cuis`` (mapped drug CUI
    set — supp.ai uses CUIs for drugs too, and we accept those even when we
    have no canonical_id yet).
    """

    supplement_cuis: set[str]
    known_drug_cuis: set[str] = field(default_factory=set)


# --------------------------------------------------------------------------- #
# Pair helpers
# --------------------------------------------------------------------------- #


def parse_pair_id(pair_id: str) -> tuple[str, str]:
    """Split a supp.ai pair id ``Cxxxx-Cyyyy`` into two CUIs.

    Enforces that both sides look like UMLS CUIs (leading ``C`` followed by
    digits). Tolerates any length to keep forward-compatible with CUI
    expansions, but rejects free-form strings.
    """
    if not isinstance(pair_id, str) or "-" not in pair_id:
        raise ValueError(f"malformed pair_id: {pair_id!r}")
    a, _, b = pair_id.partition("-")
    if not _looks_like_cui(a) or not _looks_like_cui(b):
        raise ValueError(f"malformed pair_id: {pair_id!r}")
    return a, b


def _looks_like_cui(token: str) -> bool:
    return bool(token) and token[0] == "C" and token[1:].isdigit()


def sort_pair_key(a: str, b: str) -> tuple[str, str]:
    """Lex-sort two CUIs so pair keys are direction-independent."""
    return (a, b) if a <= b else (b, a)


# --------------------------------------------------------------------------- #
# Anchor index builders
# --------------------------------------------------------------------------- #


def build_cui_to_canonical_index(iqm: dict[str, Any]) -> dict[str, str]:
    """Return ``{cui → canonical_id}`` for every IQM entry that has a CUI.

    First-wins if two canonical_ids somehow share a CUI (shouldn't happen but
    we defend against it).
    """
    idx: dict[str, str] = {}
    for canonical_id, entry in iqm.items():
        if canonical_id.startswith("_") or not isinstance(entry, dict):
            continue
        cui = entry.get("cui")
        if not cui or not isinstance(cui, str):
            continue
        idx.setdefault(cui, canonical_id)
    return idx


def build_known_supplement_cuis(iqm: dict[str, Any]) -> set[str]:
    return set(build_cui_to_canonical_index(iqm).keys())


def build_known_drug_rxcuis(drug_classes: dict[str, Any]) -> set[str]:
    """Return the set of every RxCUI referenced in drug_classes.json."""
    out: set[str] = set()
    for cls in drug_classes.get("classes", {}).values():
        for rxcui in cls.get("member_rxcuis", []):
            if isinstance(rxcui, str) and rxcui:
                out.add(rxcui)
    return out


def build_rxcui_to_cui_crosswalk(iqm: dict[str, Any]) -> dict[str, str]:
    """Crosswalk ``rxcui → cui`` from IQM for supp.ai curated auto-enrichment.

    Used only by ``enrich_curated_with_suppai``. The supp.ai corpus keys
    everything by CUI, so to match a curated row (which stores an RxCUI for
    drugs) we need to map rxcui → cui first.
    """
    out: dict[str, str] = {}
    for canonical_id, entry in iqm.items():
        if canonical_id.startswith("_") or not isinstance(entry, dict):
            continue
        rx = entry.get("rxcui")
        cui = entry.get("cui")
        if isinstance(rx, str) and rx and isinstance(cui, str) and cui:
            out.setdefault(rx, cui)
    return out


# --------------------------------------------------------------------------- #
# Pair anchoring
# --------------------------------------------------------------------------- #


def pair_is_anchored(
    pair_id: str,
    anchor: PairAnchor,
    cui_metadata: dict[str, Any],
) -> bool:
    """Decide if the pair is relevant to our bundle."""
    try:
        a, b = parse_pair_id(pair_id)
    except ValueError:
        return False
    if a in anchor.supplement_cuis or b in anchor.supplement_cuis:
        return True
    if a in anchor.known_drug_cuis or b in anchor.known_drug_cuis:
        return True
    return False


def _default_known_drug_cuis(cui_metadata: dict[str, Any]) -> set[str]:
    """Drug-side anchor set for the default ingest run.

    Intentionally empty in Phase 1. The §11.3 bundle-size control is
    "at least one CUI maps to a canonical_id in ingredient_quality_map.json",
    i.e. the supplement side must be something we already track. Anchoring
    on "any drug in supp.ai" explodes the output to ~55 k pairs (we tested
    this on the real dump: 59 096 → 54 497). Curated drug anchors via a
    UMLS-backed ``rxcui→cui`` crosswalk can be added later without changing
    the public API — pass them in via ``PairAnchor(known_drug_cuis=...)``.
    """
    return set()


# --------------------------------------------------------------------------- #
# Sentence scoring
# --------------------------------------------------------------------------- #


def score_sentence(
    sentence_record: dict[str, Any],
    paper_meta: dict[str, Any],
) -> tuple[int, int, int, int, int]:
    """Return a tuple key ranking a sentence from most to least informative.

    Key fields (higher is better):
        0. retraction penalty — retracted papers score first-field = -1 so
           they always sink below any clean paper.
        1. clinical_study bonus
        2. human_study bonus (minus animal_study penalty)
        3. year (recency)
        4. sentence length (capped so noise doesn't dominate)

    Ties break on pmid/uid in the caller (see select_top_sentences).
    """
    paper = paper_meta.get(sentence_record.get("paper_id", "")) or {}
    retracted = 0 if not paper.get("retraction", False) else -1
    clinical = 1 if paper.get("clinical_study") else 0
    human = 1 if paper.get("human_study") else 0
    animal = 1 if paper.get("animal_study") else 0
    study_type = human - animal
    year = int(paper.get("year") or 0)
    sentence = sentence_record.get("sentence") or ""
    length_score = min(len(sentence), SENTENCE_MAX_SCORE_LEN)
    return (retracted, clinical, study_type, year, length_score)


def select_top_sentences(
    sentences: list[dict[str, Any]],
    paper_meta: dict[str, Any],
    n: int = DEFAULT_MAX_SENTENCES_PER_PAIR,
) -> list[dict[str, Any]]:
    """Return up to ``n`` sentences, retraction-filtered, highest score first."""
    cleaned: list[dict[str, Any]] = []
    for s in sentences:
        paper = paper_meta.get(s.get("paper_id", "")) or {}
        if paper.get("retraction", False):
            continue
        cleaned.append(s)

    # Sort descending by score; break ties deterministically by pmid then uid.
    def _sort_key(rec: dict[str, Any]) -> tuple:
        score = score_sentence(rec, paper_meta)
        # Negate numeric score components so we can sort ascending overall,
        # then break ties on (pmid, uid) ascending for byte-identity.
        return (
            tuple(-x for x in score),
            str(rec.get("paper_id", "")),
            int(rec.get("uid", 0)),
        )

    cleaned.sort(key=_sort_key)
    return cleaned[:n]


# --------------------------------------------------------------------------- #
# Compression
# --------------------------------------------------------------------------- #


def compress_paper_meta(
    pmid: str,
    paper_meta: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a 4-field shallow copy of a paper. Used for inline embedding.

    Deliberately drops title/authors/doi/venue to keep the bundle small and
    avoid shipping anything unnecessary.
    """
    paper = paper_meta.get(pmid)
    if not isinstance(paper, dict):
        return None
    return {
        "pmid": paper.get("pmid") if isinstance(paper.get("pmid"), int) else _safe_int(pmid),
        "year": paper.get("year"),
        "clinical_study": bool(paper.get("clinical_study", False)),
        "human_study": bool(paper.get("human_study", False)),
    }


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Row builder
# --------------------------------------------------------------------------- #


def build_research_pair_row(
    pair_id: str,
    sentences: list[dict[str, Any]],
    paper_meta: dict[str, Any],
    cui_to_canonical: dict[str, str],
    cui_metadata: dict[str, Any],
    max_sentences: int = DEFAULT_MAX_SENTENCES_PER_PAIR,
) -> dict[str, Any] | None:
    """Construct one output row from a pair's raw sentence list.

    Returns ``None`` if every sentence is retracted (nothing to ship).
    """
    try:
        raw_a, raw_b = parse_pair_id(pair_id)
    except ValueError:
        return None
    cui_a, cui_b = sort_pair_key(raw_a, raw_b)

    top = select_top_sentences(sentences, paper_meta, n=max_sentences)
    if not top:
        return None

    # Unique non-retracted papers contributing to this pair, for display.
    non_retracted_pmids: list[str] = []
    seen: set[str] = set()
    for s in sentences:
        pmid = str(s.get("paper_id", ""))
        if not pmid or pmid in seen:
            continue
        paper = paper_meta.get(pmid) or {}
        if paper.get("retraction", False):
            continue
        seen.add(pmid)
        non_retracted_pmids.append(pmid)
    non_retracted_pmids.sort()
    paper_count = len(non_retracted_pmids)

    meta_a = cui_metadata.get(cui_a) or {}
    meta_b = cui_metadata.get(cui_b) or {}

    # Build the compressed top_sentences shape
    top_sentences_out: list[dict[str, Any]] = []
    top_pmids: list[str] = []
    top_papers: list[dict[str, Any]] = []
    seen_pmids: set[str] = set()
    for s in top:
        pmid = str(s.get("paper_id", ""))
        top_sentences_out.append(
            {
                "pmid": pmid,
                "sentence": s.get("sentence", ""),
                "uid": int(s.get("uid", 0)),
            }
        )
        if pmid and pmid not in seen_pmids:
            seen_pmids.add(pmid)
            top_pmids.append(pmid)
            compressed = compress_paper_meta(pmid, paper_meta)
            if compressed is not None:
                top_papers.append(compressed)
    top_pmids.sort()
    top_papers.sort(key=lambda p: str(p.get("pmid", "")))

    return {
        "cui_a": cui_a,
        "cui_b": cui_b,
        "canonical_id_a": cui_to_canonical.get(cui_a),
        "canonical_id_b": cui_to_canonical.get(cui_b),
        "ent_type_a": meta_a.get("ent_type"),
        "ent_type_b": meta_b.get("ent_type"),
        "display_name_a": meta_a.get("preferred_name"),
        "display_name_b": meta_b.get("preferred_name"),
        "paper_count": paper_count,
        "top_sentences": top_sentences_out,
        "top_pmids": top_pmids,
        "top_papers": top_papers,
    }


# --------------------------------------------------------------------------- #
# Curated auto-enrichment
# --------------------------------------------------------------------------- #


def enrich_curated_with_suppai(
    curated: list[dict[str, Any]],
    research_pairs: list[dict[str, Any]],
    rxcui_to_cui: dict[str, str],
) -> list[dict[str, Any]]:
    """Append supp.ai PMIDs to curated entries where a matching research pair
    exists. Dedupes. Non-destructive — returns new dicts, doesn't mutate
    input in place.

    Matching rule: normalize curated agent IDs to CUIs where possible
    (RxCUIs become CUIs via ``rxcui_to_cui``; CUIs pass through; classes are
    skipped because research_pairs are concrete pairs, not class aggregates).
    """
    pair_index: dict[tuple[str, str], list[str]] = {}
    for rp in research_pairs:
        key = sort_pair_key(rp["cui_a"], rp["cui_b"])
        pair_index.setdefault(key, []).extend(rp.get("top_pmids", []))

    out: list[dict[str, Any]] = []
    for entry in curated:
        copy = dict(entry)
        copy["source_pmids"] = list(copy.get("source_pmids", []))

        a_id = str(copy.get("agent1_id", ""))
        b_id = str(copy.get("agent2_id", ""))
        a_cui = _agent_to_cui(a_id, rxcui_to_cui)
        b_cui = _agent_to_cui(b_id, rxcui_to_cui)
        if a_cui and b_cui:
            key = sort_pair_key(a_cui, b_cui)
            for pmid in pair_index.get(key, []):
                if pmid not in copy["source_pmids"]:
                    copy["source_pmids"].append(pmid)
        out.append(copy)
    return out


def _agent_to_cui(agent_id: str, rxcui_to_cui: dict[str, str]) -> str | None:
    if not agent_id:
        return None
    if agent_id.startswith("class:"):
        return None
    if agent_id.startswith("C") and agent_id[1:].isdigit():
        return agent_id
    if agent_id.isdigit():
        return rxcui_to_cui.get(agent_id)
    return None


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #


def load_suppai_dump(
    suppai_dir: Path,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Return ``(cui_metadata, sentence_dict, paper_metadata)``."""
    if not suppai_dir.is_dir():
        raise FileNotFoundError(f"supp.ai dump directory not found: {suppai_dir}")

    def _load(name: str) -> Any:
        path = suppai_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing supp.ai file: {path}")
        with path.open() as fh:
            return json.load(fh)

    cui_metadata = _load("cui_metadata.json")
    sentence_dict = _load("sentence_dict.json")
    paper_metadata = _load("paper_metadata.json")
    return cui_metadata, sentence_dict, paper_metadata


def load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #


def row_has_human_study(row: dict[str, Any]) -> bool:
    """True if any retained paper in the row is a human study."""
    return any(p.get("human_study") for p in row.get("top_papers", []))


def run_ingest(
    suppai_dir: Path,
    iqm: dict[str, Any],
    drug_classes: dict[str, Any],
    max_sentences: int,
    min_paper_count: int = 1,
    require_human_study: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pure pipeline: dump directory + indexes → rows + report.

    Separated from ``main`` so tests can call it directly.
    """
    cui_metadata, sentence_dict, paper_metadata = load_suppai_dump(suppai_dir)
    return run_ingest_from_dicts(
        cui_metadata=cui_metadata,
        sentence_dict=sentence_dict,
        paper_metadata=paper_metadata,
        iqm=iqm,
        drug_classes=drug_classes,
        max_sentences=max_sentences,
        min_paper_count=min_paper_count,
        require_human_study=require_human_study,
    )


def run_ingest_from_dicts(
    *,
    cui_metadata: dict[str, Any],
    sentence_dict: dict[str, list[dict[str, Any]]],
    paper_metadata: dict[str, Any],
    iqm: dict[str, Any],
    drug_classes: dict[str, Any],
    max_sentences: int,
    min_paper_count: int = 1,
    require_human_study: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the full ingest pipeline from in-memory dicts."""
    cui_to_canonical = build_cui_to_canonical_index(iqm)
    supplement_cuis = set(cui_to_canonical.keys())
    known_drug_cuis = _default_known_drug_cuis(cui_metadata)
    anchor = PairAnchor(
        supplement_cuis=supplement_cuis,
        known_drug_cuis=known_drug_cuis,
    )

    rows: list[dict[str, Any]] = []
    dropped_unanchored = 0
    dropped_all_retracted = 0
    dropped_low_papers = 0
    dropped_no_human = 0
    for pair_id, sentences in sentence_dict.items():
        if not pair_is_anchored(pair_id, anchor, cui_metadata):
            dropped_unanchored += 1
            continue
        row = build_research_pair_row(
            pair_id=pair_id,
            sentences=sentences,
            paper_meta=paper_metadata,
            cui_to_canonical=cui_to_canonical,
            cui_metadata=cui_metadata,
            max_sentences=max_sentences,
        )
        if row is None:
            dropped_all_retracted += 1
            continue
        if row["paper_count"] < min_paper_count:
            dropped_low_papers += 1
            continue
        if require_human_study and not row_has_human_study(row):
            dropped_no_human += 1
            continue
        rows.append(row)

    # Deterministic row ordering.
    rows.sort(key=lambda r: (r["cui_a"], r["cui_b"]))

    report = {
        "total_pairs_in_dump": len(sentence_dict),
        "kept": len(rows),
        "dropped_unanchored": dropped_unanchored,
        "dropped_all_retracted": dropped_all_retracted,
        "dropped_low_papers": dropped_low_papers,
        "dropped_no_human_study": dropped_no_human,
        "supplement_anchors": len(supplement_cuis),
        "drug_anchors": len(known_drug_cuis),
        "known_drug_rxcuis": len(build_known_drug_rxcuis(drug_classes)),
        "min_paper_count": min_paper_count,
        "require_human_study": require_human_study,
    }
    return rows, report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _default_iqm_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "ingredient_quality_map.json"


def _default_drug_classes_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "drug_classes.json"


def _default_output_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "interaction_db_output"
        / "research_pairs.json"
    )


def _default_report_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "interaction_db_output"
        / "ingest_suppai_report.json"
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest supp.ai dump into research_pairs.json"
    )
    parser.add_argument(
        "--suppai-dir",
        type=Path,
        default=DEFAULT_SUPPAI_DIR,
        help=f"Path to supp.ai dump (default: {DEFAULT_SUPPAI_DIR})",
    )
    parser.add_argument(
        "--iqm",
        type=Path,
        default=_default_iqm_path(),
        help="ingredient_quality_map.json path",
    )
    parser.add_argument(
        "--drug-classes",
        type=Path,
        default=_default_drug_classes_path(),
        help="drug_classes.json path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Output research_pairs.json path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=_default_report_path(),
        help="Ingest summary report path",
    )
    parser.add_argument(
        "--max-sentences-per-pair",
        type=int,
        default=DEFAULT_MAX_SENTENCES_PER_PAIR,
        help=f"Max sentences per pair (default: {DEFAULT_MAX_SENTENCES_PER_PAIR})",
    )
    parser.add_argument(
        "--build-time",
        type=str,
        default=None,
        help="Override last_updated timestamp (ISO 8601) for deterministic builds",
    )
    parser.add_argument(
        "--min-paper-count",
        type=int,
        default=1,
        help=(
            "Drop research pairs supported by fewer than N non-retracted papers. "
            "Production builds use 2 to meet §11.3 bundle-size target."
        ),
    )
    parser.add_argument(
        "--require-human-study",
        action="store_true",
        help=(
            "Only keep pairs where at least one retained paper is a human study. "
            "Combined with --min-paper-count 2 yields ~7.7k rows from full dump."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but do not write output files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    iqm = load_json(args.iqm)
    drug_classes = load_json(args.drug_classes)

    rows, report = run_ingest(
        suppai_dir=args.suppai_dir,
        iqm=iqm,
        drug_classes=drug_classes,
        max_sentences=args.max_sentences_per_pair,
        min_paper_count=args.min_paper_count,
        require_human_study=args.require_human_study,
    )

    build_time = args.build_time or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")

    payload = {
        "_metadata": {
            "schema_version": SCHEMA_VERSION,
            "source": "supp.ai",
            "last_updated": build_time,
            "total_pairs": len(rows),
            "max_sentences_per_pair": args.max_sentences_per_pair,
            "min_paper_count": args.min_paper_count,
            "require_human_study": args.require_human_study,
            "filter_rule": (
                "≥1 side ∈ IQM canonical supplements; paper_count ≥ min_paper_count; "
                "optional human-study requirement"
            ),
        },
        "research_pairs": rows,
    }
    report["build_time"] = build_time
    report["output_path"] = str(args.output)

    print(
        f"ingest_suppai: kept={report['kept']} "
        f"dropped_unanchored={report['dropped_unanchored']} "
        f"dropped_all_retracted={report['dropped_all_retracted']} "
        f"dropped_low_papers={report['dropped_low_papers']} "
        f"dropped_no_human_study={report['dropped_no_human_study']} "
        f"supplement_anchors={report['supplement_anchors']} "
        f"drug_anchors={report['drug_anchors']} "
        f"min_paper_count={report['min_paper_count']} "
        f"require_human_study={report['require_human_study']}",
        file=sys.stderr,
    )

    if args.dry_run:
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
