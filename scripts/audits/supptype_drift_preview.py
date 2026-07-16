#!/usr/bin/env python3
"""TEMPORARY migration harness — supplement-type consolidation drift preview.

READ-ONLY. It never chooses a shipped result and never writes pipeline output.
DELETE THIS FILE at cutover acceptance (consolidation Phase 5), together with
``scripts/tests/test_supptype_drift_preview_harness.py`` and
``scripts/tests/test_supptype_preview_exact_path_canary.py``.

WHY THIS EXISTS
    A full pipeline run costs ~1 hour and the release gates are sequential and
    fail-closed, so a classifier change is discovered one layer at a time. The
    supp-type consolidation re-routes a material slice of the catalog, so
    iterating against the pipeline would mean many hour-long rounds.

    This harness answers, in minutes and off the pipeline:
      * which products change classification, and why
      * the old -> new confusion matrix
      * which SCORES move, and — the part that actually matters — which
        verdicts/statuses FLIP
      * which of the frozen scoring-snapshot fixtures will drift

WHAT MAKES IT TRUSTWORTHY (plan §8 contract)
    * It scores a defensive copy carrying the taxonomy recomputed by CURRENT
      code, projected through the SAME production seam the pipeline uses
      (`SupplementEnricherV3.apply_taxonomy_projection`) — never a harness-local
      mirror of that algorithm.
    * Its score preview is the real production assembly: the v3 scaffolding,
      then the v4 export adapter, then the export-only banned hard block —
      exactly what `build_final_db.py` does.
    * It selects affected products by EVERY declared classification fact plus a
      digest of the taxonomy-derived projections, not by `primary_type` alone.
    * It infers nothing about single-ness; it reports the canonical fact.
    * It fails closed on unreadable input, malformed batches, duplicate IDs,
      corpus drift, and scoring errors.

USAGE
    source scripts/python_env.sh
    $PG_PYTHON scripts/audits/supptype_drift_preview.py baseline --score
    # ... one RED-first implementation slice ...
    $PG_PYTHON scripts/audits/supptype_drift_preview.py compare --score \
        --json-out /tmp/ledger.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))


def _pin_hash_seed() -> None:
    """Re-exec under PYTHONHASHSEED=0 so the harness's own runs are reproducible.

    `scoring_input_contract._botanical_child_identity` picks the first matching
    entry out of an unordered `variants` SET, so when a blend child name matches
    more than one lookup variant the winning identity — and therefore whether a
    `blend_anchor_mass` evidence row exists at all — depends on the interpreter's
    string-hash seed. Measured 2026-07-15: 2/14,193 products (28986, 70066)
    flip; 0 change primary_type.

    That is a real production defect, tracked separately: it lives in the
    mapped_coverage owner, which the consolidation plan gates behind an explicit
    Phase 3 checkpoint. This harness must not "fix" it by accident, but it also
    must not let it masquerade as classifier drift — a baseline and a compare
    run would otherwise disagree on those products at random. Pinning the seed
    makes baseline-vs-compare an honest code-vs-code diff.

    Consequence to keep in mind: for those 2 products the preview reflects the
    seed-0 outcome, while a real pipeline run gets whichever outcome its random
    seed produces.
    """
    if os.environ.get("PYTHONHASHSEED") == "0":
        return
    os.execve(
        sys.executable,
        [sys.executable, os.path.abspath(__file__), *sys.argv[1:]],
        {**os.environ, "PYTHONHASHSEED": "0"},
    )

PRODUCTS_DIR = SCRIPTS_DIR / "products"
FIXTURES_DIR = SCRIPTS_DIR / "tests" / "fixtures" / "contract_snapshots"
DEFAULT_BASELINE = SCRIPTS_DIR / "products" / "reports" / "supptype_baseline.json"

# Bump when the captured fact/score vocabulary changes. A baseline written by a
# different schema is rejected rather than silently compared.
SCHEMA_VERSION = "2"


class HarnessError(RuntimeError):
    """Any condition that makes the preview untrustworthy. Always fatal."""


# ---------------------------------------------------------------------------
# Captured vocabulary
# ---------------------------------------------------------------------------

# Read verbatim off the taxonomy. Keys the classifier does not emit yet (they
# arrive in consolidation Phase 0a/0d) are captured as None — truthfully absent
# rather than inferred. Every key here drives affected-product selection.
CLASSIFICATION_FACT_KEYS: Tuple[str, ...] = (
    "primary_type",
    "secondary_type",
    "percentile_category",
    "classification_confidence",
    "classification_reasons",
    "classification_reason_codes",      # Phase 0a — structured evidence contract
    "classification_input_source",
    "classification_input_contract",    # Phase 0a — stable contract-level id
    "classification_contract_version",  # Phase 0a
    "quantified_active_count",
    "quantified_label_active_count",    # Phase 0d — classification population
    "scorable_active_count",            # Phase 0d — score-eligible population
    "is_single_scorable_active",        # Phase 0d — the canonical single fact
    "unresolved_quantified_active_count",  # Phase 0a — dosed but unresolved
    "non_quantified_base_count",
    "category_breakdown",
    "dsld_product_type",
)

# Taxonomy-derived, score-driving projections that are not scalar taxonomy
# fields. `product_scoring_evidence` gates probiotic CFU evidence on
# primary_type; `product_scoring_classification` is the native classification
# contract. Compared as a digest so any change selects the product without
# bloating the human-readable ledger.
DERIVED_PROJECTION_KEYS: Tuple[str, ...] = (
    "product_scoring_evidence",
    "product_scoring_classification",
    "supplement_type",  # Phase 2 — the mechanical compatibility mirror
)

# The shipped contract, as `build_final_db.py` writes it to products_core.
PREVIEW_SCORE_KEYS: Tuple[str, ...] = (
    "_v4_quality_score_100",
    "_v4_quality_status",
    "_v4_quality_tier",
    "_v4_suppressed_reason",
    "_v4_raw_score_100",
    "_v4_module",
    "_v4_confidence",
    "verdict",
    "safety_verdict",
    "grade",
    "blocking_reason",
    "safety_signal_reason",
    "mapped_coverage",
    "score_100_equivalent",
    "display_100",
    "scoring_status",
    "score_basis",
)

# Taxonomy fields that actually decide product behaviour. Drift in these
# between an artifact and current code means the artifact was written by a
# different classifier; drift confined to the others (e.g. prose reason text)
# is cosmetic and can be accepted with a written justification.
_DECISION_FIELDS = frozenset({
    "primary_type",
    "secondary_type",
    "percentile_category",
    "classification_confidence",
    "quantified_active_count",
    "quantified_label_active_count",
    "scorable_active_count",
    "is_single_scorable_active",
    "unresolved_quantified_active_count",
    "non_quantified_base_count",
    "category_breakdown",
})

# Safety-critical fields: any change here is reviewed individually (plan §11).
SAFETY_CRITICAL_KEYS: Tuple[str, ...] = (
    "verdict",
    "safety_verdict",
    "_v4_quality_status",
    "_v4_suppressed_reason",
    "blocking_reason",
    "mapped_coverage",
)

_HASH_EXCLUDED = frozenset({"generated_at", "content_hash"})


# ---------------------------------------------------------------------------
# Corpus loading — fail closed
# ---------------------------------------------------------------------------


def iter_batch_files(products_dir: Path = PRODUCTS_DIR) -> List[Path]:
    """Every enriched batch file, sorted for determinism.

    Dot-prefixed files (`.stage_manifest.json`) are pipeline bookkeeping, not
    product batches. They are excluded by name — explicitly, so a genuinely
    unreadable product batch can still fail closed.
    """
    files: List[Path] = []
    for brand_dir in sorted(products_dir.glob("output_*_enriched")):
        for path in sorted((brand_dir / "enriched").glob("*.json")):
            if path.name.startswith("."):
                continue
            files.append(path)
    return files


def load_batch(path: Path) -> List[Dict[str, Any]]:
    """Parse one batch file. Any defect is fatal — never skip-and-continue."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"unreadable batch {path}: {exc}") from exc

    if isinstance(payload, dict):
        items: List[Any] = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        raise HarnessError(
            f"malformed batch shape in {path}: expected object or array, "
            f"got {type(payload).__name__}"
        )

    products: List[Dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise HarnessError(
                f"malformed batch shape in {path}[{index}]: expected object, "
                f"got {type(item).__name__}"
            )
        if item.get("dsld_id") is None:
            raise HarnessError(f"product without dsld_id in {path}[{index}]")
        products.append(item)
    return products


def load_corpus(products_dir: Path = PRODUCTS_DIR) -> Dict[str, Dict[str, Any]]:
    """dsld_id -> product for the whole enriched corpus. Duplicates are fatal."""
    corpus: Dict[str, Dict[str, Any]] = {}
    origin: Dict[str, Path] = {}
    for path in iter_batch_files(products_dir):
        for product in load_batch(path):
            pid = str(product["dsld_id"])
            if pid in corpus:
                raise HarnessError(
                    f"duplicate product id {pid}: {origin[pid]} and {path}"
                )
            corpus[pid] = product
            origin[pid] = path
    if not corpus:
        raise HarnessError(f"no enriched products found under {products_dir}")
    return corpus


def reconcile_ids(base_ids: Iterable[str], new_ids: Iterable[str]) -> None:
    """Exact product-ID parity or bust (plan §10)."""
    base, new = set(base_ids), set(new_ids)
    missing = sorted(base - new)
    added = sorted(new - base)
    problems = []
    if missing:
        problems.append(f"missing from current corpus: {len(missing)} ({missing[:5]})")
    if added:
        problems.append(f"added since baseline: {len(added)} ({added[:5]})")
    if problems:
        raise HarnessError("corpus drift — " + "; ".join(problems))


# ---------------------------------------------------------------------------
# Production seams
# ---------------------------------------------------------------------------


def make_enricher():
    from enrich_supplements_v3 import SupplementEnricherV3

    return SupplementEnricherV3()


def make_scorer():
    from score_supplements import SupplementScorer

    return SupplementScorer()


def project_current_taxonomy(product: Dict[str, Any], enricher) -> Dict[str, Any]:
    """Recompute the taxonomy and every field derived from it, on a copy.

    Uses the production seam so the preview cannot drift from the pipeline.
    """
    projected = copy.deepcopy(product)
    enricher.apply_taxonomy_projection(projected)
    return projected


def preview_scored(projected: Dict[str, Any], scorer, strict: bool = True) -> Dict[str, Any]:
    """The real production score assembly, in-process.

    Mirrors `build_final_db.py`: v3 scaffolding -> v4 export adapter -> the
    export-only banned-substance hard block. Scoring errors propagate; the
    harness must never turn a crash into a data row.
    """
    from build_final_db import has_banned_substance
    from scoring_v4.export_adapter import overlay_v4_scored, suppress_v4_for_hard_block

    if strict and not isinstance(projected, dict):
        raise HarnessError(f"not a product: {type(projected).__name__}")
    if strict and projected.get("dsld_id") is None:
        raise HarnessError("not a product: missing dsld_id")

    scored_v3 = scorer.score_product(copy.deepcopy(projected))
    scored = overlay_v4_scored(projected, scored_v3)
    if has_banned_substance(projected):
        scored = suppress_v4_for_hard_block(scored, reason="banned_substance")
    return scored


# ---------------------------------------------------------------------------
# Fact capture
# ---------------------------------------------------------------------------


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def classification_facts(projected: Dict[str, Any]) -> Dict[str, Any]:
    """Every declared classification fact, read verbatim. No inference."""
    taxonomy = projected.get("supplement_taxonomy")
    taxonomy = taxonomy if isinstance(taxonomy, dict) else {}
    facts: Dict[str, Any] = {key: taxonomy.get(key) for key in CLASSIFICATION_FACT_KEYS}
    facts["derived_digest"] = _digest(
        {key: projected.get(key) for key in DERIVED_PROJECTION_KEYS}
    )
    # Per-row evidence is the SoT gate's input, so a change to it must select
    # the product — but it is far too bulky to inline in a 14k-product ledger.
    facts["row_evidence_digest"] = _digest(taxonomy.get("classification_row_evidence"))
    return facts


def score_facts(scored: Dict[str, Any]) -> Dict[str, Any]:
    facts: Dict[str, Any] = {key: scored.get(key) for key in PREVIEW_SCORE_KEYS}
    facts["pillars"] = scored.get("_v4_pillars")
    strict_contract = scored.get("strict_scoring_contract")
    facts["strict_scoring_contract"] = (
        strict_contract if isinstance(strict_contract, dict) else None
    )
    return facts


# ---------------------------------------------------------------------------
# Selection + ledger
# ---------------------------------------------------------------------------


def select_affected(
    base_rows: Dict[str, Dict[str, Any]], new_rows: Dict[str, Dict[str, Any]]
) -> Set[str]:
    """Every product whose classification behaviour can have changed.

    Compares all captured facts, not `primary_type` alone: a change to
    `is_single_scorable_active` (or to a taxonomy-derived projection) moves the
    score while leaving the type name stable.
    """
    affected: Set[str] = set()
    for pid, new in new_rows.items():
        base = base_rows.get(pid)
        if base is None or _comparable(base) != _comparable(new):
            affected.add(pid)
    return affected


def _comparable(row: Dict[str, Any]) -> Dict[str, Any]:
    """Facts only — presentation fields (brand/name) never drive selection."""
    return {k: v for k, v in row.items() if k not in {"brand", "name"}}


def build_ledger(
    base_rows: Dict[str, Dict[str, Any]],
    new_rows: Dict[str, Dict[str, Any]],
    affected: Iterable[str],
    base_scores: Dict[str, Any],
    new_scores: Dict[str, Any],
) -> Dict[str, Any]:
    """Complete per-product ledger. Never truncated (plan §8, §11)."""
    ledger: Dict[str, Any] = {}
    for pid in sorted(affected):
        old_facts = base_rows.get(pid, {})
        new_facts = new_rows.get(pid, {})
        entry: Dict[str, Any] = {
            "old": old_facts,
            "new": new_facts,
            "changed_facts": sorted(
                key
                for key in set(_comparable(old_facts)) | set(_comparable(new_facts))
                if old_facts.get(key) != new_facts.get(key)
            ),
            "reason_codes": new_facts.get("classification_reason_codes")
            or new_facts.get("classification_reasons")
            or [],
        }
        old_score, new_score = base_scores.get(pid), new_scores.get(pid)
        if old_score is not None or new_score is not None:
            old_score = old_score or {}
            new_score = new_score or {}
            deltas = {
                key: {"old": old_score.get(key), "new": new_score.get(key)}
                for key in set(old_score) | set(new_score)
                if old_score.get(key) != new_score.get(key)
            }
            entry["score_deltas"] = deltas
            entry["safety_critical"] = sorted(set(deltas) & set(SAFETY_CRITICAL_KEYS))
        ledger[pid] = entry
    return ledger


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(SCRIPTS_DIR),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def content_hash_of(payload: Dict[str, Any]) -> str:
    material = {k: v for k, v in payload.items() if k not in _HASH_EXCLUDED}
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def build_baseline_payload(
    rows: Dict[str, Dict[str, Any]], scores: Dict[str, Any]
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "baseline_commit": _git_commit(),
        "corpus_count": len(rows),
        "product_ids": sorted(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "types": rows,
        "scores": scores,
    }
    payload["content_hash"] = content_hash_of(payload)
    return payload


def load_baseline(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise HarnessError(f"no baseline at {path}. Run `baseline` first.")
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"unreadable baseline {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HarnessError(f"malformed baseline {path}")

    found = payload.get("schema_version")
    if found != SCHEMA_VERSION:
        raise HarnessError(
            f"baseline schema mismatch: file has {found!r}, harness expects "
            f"{SCHEMA_VERSION!r}. Regenerate the baseline explicitly."
        )
    if payload.get("content_hash") and payload["content_hash"] != content_hash_of(payload):
        raise HarnessError(f"baseline {path} content hash mismatch — file was edited")
    return payload


# ---------------------------------------------------------------------------
# Corpus pass (parallel)
# ---------------------------------------------------------------------------

_WORKER: Dict[str, Any] = {}


def _worker_init() -> None:
    _WORKER["enricher"] = make_enricher()
    _WORKER["scorer"] = make_scorer()


def _process_files(args: Tuple[List[str], bool, Optional[List[str]]]) -> Dict[str, Any]:
    paths, do_score, only_ids = args
    enricher = _WORKER.get("enricher") or make_enricher()
    scorer = _WORKER.get("scorer") or make_scorer()
    wanted = set(only_ids) if only_ids is not None else None

    out: Dict[str, Any] = {}
    for raw in paths:
        for product in load_batch(Path(raw)):
            pid = str(product["dsld_id"])
            if wanted is not None and pid not in wanted:
                continue
            projected = project_current_taxonomy(product, enricher)
            row: Dict[str, Any] = {
                "facts": classification_facts(projected),
                "brand": product.get("brand_name") or "",
                "name": (product.get("product_name") or product.get("fullName") or "")[:70],
                "embedded_drift": _embedded_drift_fields(product, projected),
            }
            if do_score:
                row["scores"] = score_facts(preview_scored(projected, scorer))
            out[pid] = row
    return out


def _embedded_drift_fields(product: Dict[str, Any], projected: Dict[str, Any]) -> List[str]:
    """Which taxonomy fields did CURRENT code fail to reproduce from the artifact?

    Empty list == parity. Naming the fields (rather than a bare bool) is what
    makes the baseline-drift gate actionable: 'only classification_reasons
    drifted' is a very different decision from 'primary_type drifted'.
    """
    embedded = product.get("supplement_taxonomy")
    recomputed = projected.get("supplement_taxonomy")
    if not isinstance(embedded, dict) or not isinstance(recomputed, dict):
        return [] if embedded == recomputed else ["supplement_taxonomy"]
    return sorted(
        key for key in set(embedded) | set(recomputed)
        if embedded.get(key) != recomputed.get(key)
    )


def run_corpus(
    do_score: bool,
    only_ids: Optional[Set[str]] = None,
    products_dir: Path = PRODUCTS_DIR,
    workers: Optional[int] = None,
) -> Dict[str, Any]:
    """Project (and optionally score) the corpus. Duplicates are fatal."""
    files = [str(p) for p in iter_batch_files(products_dir)]
    if not files:
        raise HarnessError(f"no enriched batches under {products_dir}")

    workers = workers or max(1, min(8, (os.cpu_count() or 2) - 2))
    id_list = sorted(only_ids) if only_ids is not None else None
    chunks = [([f], do_score, id_list) for f in files]

    merged: Dict[str, Any] = {}
    if workers == 1:
        _worker_init()
        results = [_process_files(chunk) for chunk in chunks]
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init) as pool:
            results = list(pool.map(_process_files, chunks))

    for result in results:
        for pid, row in result.items():
            if pid in merged:
                raise HarnessError(f"duplicate product id {pid} across batches")
            merged[pid] = row
    return merged


def _split(rows: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    facts = {}
    scores = {}
    for pid, row in rows.items():
        entry = dict(row["facts"])
        entry["brand"] = row.get("brand", "")
        entry["name"] = row.get("name", "")
        facts[pid] = entry
        if "scores" in row:
            scores[pid] = row["scores"]
    return facts, scores


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def frozen_fixture_ids() -> Set[str]:
    if not FIXTURES_DIR.exists():
        return set()
    return {p.stem for p in FIXTURES_DIR.glob("*.json") if not p.stem.startswith("_")}


def cmd_baseline(args: argparse.Namespace) -> int:
    started = time.time()
    print(f"Projecting corpus with CURRENT code (score={args.score})...")
    rows = run_corpus(do_score=args.score, workers=args.workers)
    facts, scores = _split(rows)

    # Baseline parity gate (plan §8/§10): the embedded taxonomy in the enriched
    # artifact must match what current code recomputes, or every mismatch is
    # recorded and the baseline is refused.
    drifted = sorted(pid for pid, row in rows.items() if row["embedded_drift"])
    print(f"\nembedded-vs-recomputed taxonomy parity: "
          f"{len(rows) - len(drifted)}/{len(rows)} identical")
    if drifted:
        field_counts = Counter(
            field for pid in drifted for field in rows[pid]["embedded_drift"]
        )
        print("  drifting fields:")
        for field, count in field_counts.most_common():
            decisive = " <-- DECISION FIELD" if field in _DECISION_FIELDS else ""
            print(f"    {count:6d}  {field}{decisive}")

        ledger_path = args.baseline.parent / "supptype_baseline_drift.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(
            {pid: {"drifting_fields": rows[pid]["embedded_drift"],
                   "facts": rows[pid]["facts"]}
             for pid in drifted}, indent=2, sort_keys=True))
        print(f"\n! {len(drifted)} products drift from their embedded taxonomy.",
              file=sys.stderr)
        print(f"! baseline-drift ledger: {ledger_path}", file=sys.stderr)
        if not args.allow_baseline_drift:
            print("! refusing to freeze a baseline that mixes fresh code with "
                  "stale enriched taxonomy. Resolve, or pass "
                  "--allow-baseline-drift with justification.", file=sys.stderr)
            return 1

    payload = build_baseline_payload(facts, scores)
    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"\nBaseline written: {args.baseline}")
    print(f"  schema={payload['schema_version']} commit={payload['baseline_commit']} "
          f"count={payload['corpus_count']}")
    print(f"  content_hash={payload['content_hash'][:16]}...")

    dist = Counter(row["primary_type"] or "(empty)" for row in facts.values())
    print("\nprimary_type distribution:")
    for name, count in dist.most_common():
        print(f"  {count:6d}  {count / len(facts) * 100:5.1f}%  {name}")
    print(f"\nelapsed: {time.time() - started:.1f}s")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    started = time.time()
    base = load_baseline(args.baseline)
    base_facts = base["types"]
    base_scores = base.get("scores") or {}

    print("Re-projecting corpus with current code...")
    rows = run_corpus(do_score=False, workers=args.workers)
    new_facts, _ = _split(rows)

    reconcile_ids(base_facts, new_facts)

    affected = select_affected(base_facts, new_facts)
    total = len(new_facts)
    print(f"\n{'=' * 66}\nCLASSIFICATION DRIFT: {len(affected)}/{total} products "
          f"({len(affected) / total * 100:.2f}%)\n{'=' * 66}")

    type_changed = {
        pid for pid in affected
        if base_facts[pid].get("primary_type") != new_facts[pid].get("primary_type")
    }
    print(f"  primary_type changes : {len(type_changed)}")
    print(f"  fact-only changes    : {len(affected) - len(type_changed)}"
          f"   <-- invisible to a primary_type-only diff")

    matrix = Counter(
        (base_facts[pid].get("primary_type") or "(empty)",
         new_facts[pid].get("primary_type") or "(empty)")
        for pid in type_changed
    )
    if matrix:
        print("\nconfusion matrix (old -> new, top 25):")
        for (old, new), count in matrix.most_common(25):
            print(f"  {count:6d}  {old:24s} -> {new}")

    fixtures = frozen_fixture_ids()
    fixture_hits = sorted(fixtures & affected)
    print(f"\nfrozen fixtures affected: {len(fixture_hits)}/{len(fixtures)}")
    for pid in fixture_hits:
        print(f"  {pid}  {base_facts[pid].get('primary_type')} -> "
              f"{new_facts[pid].get('primary_type')}  ({new_facts[pid].get('name')})")

    new_scores: Dict[str, Any] = {}
    if args.score:
        if not base_scores:
            print("\n! baseline has no scores; re-run `baseline --score`.", file=sys.stderr)
            return 1
        missing_base = sorted(affected - set(base_scores))
        if missing_base:
            print(f"\n! {len(missing_base)} affected products have no baseline score "
                  f"({missing_base[:5]})", file=sys.stderr)
            return 1
        print(f"\nRe-scoring {len(affected)} affected products...")
        scored_rows = run_corpus(do_score=True, only_ids=affected, workers=args.workers)
        _, new_scores = _split(scored_rows)

        flips: Dict[str, List[Tuple[str, Any, Any]]] = {k: [] for k in SAFETY_CRITICAL_KEYS}
        moved = 0
        for pid in affected:
            old, new = base_scores.get(pid, {}), new_scores.get(pid, {})
            if old != new:
                moved += 1
            for key in SAFETY_CRITICAL_KEYS:
                if old.get(key) != new.get(key):
                    flips[key].append((pid, old.get(key), new.get(key)))
        print(f"\n{'=' * 66}\nSCORE IMPACT (affected products)\n{'=' * 66}")
        print(f"  products with any score-surface change: {moved}")
        for key in SAFETY_CRITICAL_KEYS:
            hits = flips[key]
            marker = "   <-- review each" if hits else ""
            print(f"  {key:24s}: {len(hits)}{marker}")
            for pid, old, new in hits[:10]:
                print(f"     {pid}: {old} -> {new}  ({new_facts[pid].get('name')})")

    ledger = build_ledger(base_facts, new_facts, affected, base_scores, new_scores)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(ledger, indent=2, sort_keys=True))
        print(f"\nper-product ledger ({len(ledger)} entries): {args.json_out}")
    elif affected:
        print("\n! no --json-out given; the machine-readable ledger was not written.",
              file=sys.stderr)

    print(f"\nelapsed: {time.time() - started:.1f}s")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("baseline", "compare"):
        sp = sub.add_parser(name)
        sp.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
        sp.add_argument("--score", action="store_true",
                        help="also capture/diff the production v4 score preview")
        sp.add_argument("--workers", type=int, default=None)
        if name == "baseline":
            sp.add_argument("--allow-baseline-drift", action="store_true",
                            help="freeze even if embedded taxonomy != recomputed "
                                 "(requires written justification in the plan)")
        else:
            sp.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        return cmd_baseline(args) if args.cmd == "baseline" else cmd_compare(args)
    except HarnessError as exc:
        print(f"\nHARNESS ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    _pin_hash_seed()  # must precede any classification work; may re-exec
    raise SystemExit(main())
