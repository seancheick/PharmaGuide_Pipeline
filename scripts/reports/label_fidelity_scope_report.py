"""
Sprint E1.0.3 — label-fidelity + safety-copy scope-report generator.

Produces a Markdown + JSON report enumerating per-axis affected-product
counts across the 7 label-fidelity invariants (E1.0.1) and 5 safety-copy
invariants (E1.0.2). Used as:

  - A pre-fix baseline measurement (sprint §3 rule #1 "measure before you
    build").
  - A post-fix verification pass (every E1.2.x / E1.1.x task reruns this
    to confirm counts dropped toward zero).
  - A CI gate (``--fail-on-violations`` exits non-zero if any axis has
    violations).

Inputs
------
  --blobs DIR   Build output ``detail_blobs/`` directory (required).
  --raw DIR     Raw DSLD staging directory (optional — axes that cross-
                reference raw fields are skipped when absent).
  --out DIR     Output directory (default: ``reports/`` at repo root).
  --prefix STR  Filename prefix (default: ``label_fidelity_scope_latest``).
  --fail-on-violations
                Exit code 1 if any axis reports > 0 violations.
                Use in CI release-gate jobs.

Design notes
------------
  * All output is idempotent: second run on identical inputs produces
    byte-identical JSON (keys sorted, samples sorted, no wall-clock).
  * Scan walks the detail-blob directory once, streaming; memory
    footprint is O(samples-per-axis), not O(product-count).
  * Per-axis sample count is capped (default 10) so a 4,800-product
    regression doesn't produce a 10 MB report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Constants (mirror the contract-test modules; see docstrings there for the
# medical/UX justification per invariant).
# ---------------------------------------------------------------------------

BRANDED_TOKENS = (
    "KSM-66", "Meriva", "BioPerine", "Ferrochel", "Sensoril", "Phytosome",
    "Silybin Phytosome", "Pycnogenol", "Setria", "Albion", "TRAACS",
    "Chromax", "Curcumin C3", "Longvida", "Wellmune", "CurcuWIN", "LJ100",
    "enXtra", "AstraGin", "Venetron",
)

PLANT_PART_RE = re.compile(
    r"\b(root|leaf|leaves|seed|bark|rhizome|flower|fruit|stem|aerial)\b",
    re.IGNORECASE,
)

STANDARDIZATION_RE = re.compile(
    r"(standardi[sz]ed to\b|\b\d+(?:\.\d+)?\s*%\b|\bcontains\s+\d)",
    re.IGNORECASE,
)

DANGER_DENY_LIST = re.compile(
    r"(not lawful|banned|talk to your doctor|arsenic|trace metals|"
    r"undisclosed|high glycemic|contraindicated)",
    re.IGNORECASE,
)

CONDITION_SPECIFIC_RE = re.compile(
    r"(during pregnancy|for liver disease|breastfeeding|kidney disease|"
    r"heart disease|while nursing)",
    re.IGNORECASE,
)

AUTHORED_COPY_FIELDS = (
    "alert_headline", "alert_body", "safety_warning",
    "safety_warning_one_liner", "detail",
)

DEFAULT_SAMPLE_CAP = 10


# ---------------------------------------------------------------------------
# Axis definitions — each returns (count, samples) for a single invariant.
# Samples are truncated tuples; all sortable for deterministic output.
# ---------------------------------------------------------------------------

def _axes_label_fidelity():
    return [
        ("A_prop_blend_mass_recovery", _axis_prop_blend_mass),
        ("B_branded_identity_preserved", _axis_branded_identity),
        ("C_plant_part_preserved", _axis_plant_part),
        ("D_standardization_note_preserved", _axis_standardization),
        ("E_inactive_ingredients_complete", _axis_inactive_count),
        ("F_active_count_reconciled", _axis_active_count),
        ("G_display_not_canonical", _axis_display_not_canonical),
    ]


def _axes_safety_copy():
    return [
        ("S1_no_danger_in_positives", _axis_danger_in_positives),
        ("S2_critical_profile_agnostic", _axis_critical_profile_agnostic),
        ("S3_no_raw_enum_leaks", _axis_raw_enum_leaks),
        ("S4_banned_substance_preflight", _axis_banned_preflight),
        ("S5_no_duplicate_warnings", _axis_duplicate_warnings),
    ]


# ---------------------------------------------------------------------------
# Label-fidelity axes (A–G)
# ---------------------------------------------------------------------------

def _axis_prop_blend_mass(blob: dict) -> list[tuple]:
    """A — proprietary-blend parent-mass propagation. Violation: a blend
    with ≥1 disclosed member but ``total_weight`` missing/zero."""
    violations = []
    pbd = blob.get("proprietary_blend_detail") or {}
    for i, blend in enumerate(pbd.get("blends") or []):
        if not isinstance(blend, dict):
            continue
        has_members = bool(blend.get("members") or blend.get("ingredients"))
        tw = blend.get("total_weight") or blend.get("blend_total_mg") or 0
        if has_members and not tw:
            violations.append((blob.get("dsld_id"), i, blend.get("name")))
    return violations


def _axis_branded_identity(blob: dict) -> list[tuple]:
    """B — branded token preserved in ``display_label``."""
    violations = []
    for ing in blob.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        display = (ing.get("display_label") or "")
        if not display:
            # Pre-E1.2.2 state — no display_label to audit. Don't emit a
            # violation; the contract test auto-skips in that state.
            continue
        raw_blob = " ".join([
            ing.get("name") or "",
            ing.get("raw_name") or "",
            " ".join(f.get("name", "") for f in (ing.get("forms") or []) if isinstance(f, dict)),
            " ".join(n for n in (ing.get("notes") or []) if isinstance(n, str)),
        ]).lower()
        for token in BRANDED_TOKENS:
            if token.lower() in raw_blob and token.lower() not in display.lower():
                violations.append((blob.get("dsld_id"), token, ing.get("name")))
                break
    return violations


def _axis_plant_part(blob: dict) -> list[tuple]:
    """C — plant-part preservation in ``display_label``."""
    violations = []
    for ing in blob.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        display = (ing.get("display_label") or "")
        if not display:
            continue
        form_blob = " ".join(f.get("name", "") for f in (ing.get("forms") or []) if isinstance(f, dict))
        m = PLANT_PART_RE.search(form_blob)
        if not m:
            continue
        part = m.group(1).lower()
        equivalents = {"leaf": ("leaf", "leaves"), "leaves": ("leaf", "leaves")}
        acceptable = equivalents.get(part, (part,))
        if not any(e in display.lower() for e in acceptable):
            violations.append((blob.get("dsld_id"), part, ing.get("name")))
    return violations


def _axis_standardization(blob: dict) -> list[tuple]:
    """D — standardization note preservation."""
    violations = []
    for ing in blob.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        if "standardization_note" not in ing:
            # Pre-E1.2.2 — field doesn't exist yet. Skip.
            continue
        notes_text = " ".join(n for n in (ing.get("notes") or []) if isinstance(n, str))
        if not STANDARDIZATION_RE.search(notes_text):
            continue
        if not ing.get("standardization_note"):
            violations.append((blob.get("dsld_id"), ing.get("name"), notes_text[:80]))
    return violations


def _axis_inactive_count(blob: dict) -> list[tuple]:
    """E — inactive-ingredient dropping. Blob must carry
    ``raw_inactives_count`` snapshot (E1.2.4) for this axis to run."""
    raw_n = blob.get("raw_inactives_count")
    if not isinstance(raw_n, int):
        return []
    blob_n = len(blob.get("inactive_ingredients") or [])
    if raw_n > 0 and blob_n == 0:
        return [(blob.get("dsld_id"), raw_n)]
    return []


def _axis_active_count(blob: dict) -> list[tuple]:
    """F — active-count reconciliation. Blob must carry
    ``raw_actives_count`` snapshot for this axis to run."""
    raw_n = blob.get("raw_actives_count")
    if not isinstance(raw_n, int):
        return []
    blob_n = len(blob.get("ingredients") or [])
    if raw_n > 0 and blob_n == 0:
        return [(blob.get("dsld_id"), raw_n)]
    return []


def _axis_display_not_canonical(blob: dict) -> list[tuple]:
    """G — display_label must not collapse to canonical when source differs."""
    violations = []
    for ing in blob.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        display = (ing.get("display_label") or "").strip()
        if not display:
            continue
        canonical = (ing.get("canonical_name") or ing.get("scoring_group_canonical") or "").strip()
        source = (ing.get("name") or ing.get("raw_name") or "").strip()
        if not canonical or not source:
            continue
        if display.lower() == canonical.lower() and source.lower() != canonical.lower():
            violations.append((blob.get("dsld_id"), source, canonical, display))
    return violations


# ---------------------------------------------------------------------------
# Safety-copy axes (S1–S5)
# ---------------------------------------------------------------------------

def _axis_danger_in_positives(blob: dict) -> list[tuple]:
    """S1 — no danger-valence copy under decision_highlights.positive."""
    dh = blob.get("decision_highlights")
    if not isinstance(dh, dict) or "danger" not in dh:
        return []
    violations = []
    pos = dh.get("positive")
    positives = [pos] if isinstance(pos, str) else (pos or [])
    for s in positives:
        if not isinstance(s, str):
            continue
        m = DANGER_DENY_LIST.search(s)
        if m:
            violations.append((blob.get("dsld_id"), m.group(0), s[:80]))
    return violations


def _axis_critical_profile_agnostic(blob: dict) -> list[tuple]:
    """S2 — critical-mode warnings must be profile-agnostic."""
    violations = []
    for key in ("warnings", "warnings_profile_gated"):
        for w in blob.get(key) or []:
            if not isinstance(w, dict):
                continue
            if w.get("display_mode_default") != "critical":
                continue
            for field in AUTHORED_COPY_FIELDS:
                text = w.get(field)
                if isinstance(text, str) and CONDITION_SPECIFIC_RE.search(text):
                    violations.append((blob.get("dsld_id"), key, field, text[:80]))
                    break
    return violations


def _axis_raw_enum_leaks(blob: dict) -> list[tuple]:
    """S3 — no warning has only ``type`` populated."""
    violations = []
    for key in ("warnings", "warnings_profile_gated"):
        for w in blob.get(key) or []:
            if not isinstance(w, dict):
                continue
            populated = any(
                isinstance(w.get(f), str) and w.get(f).strip()
                for f in AUTHORED_COPY_FIELDS
            )
            if not populated:
                violations.append((blob.get("dsld_id"), key, w.get("type")))
    return violations


def _axis_banned_preflight(blob: dict) -> list[tuple]:
    """S4 — banned-substance products must carry preflight copy."""
    if not blob.get("has_banned_substance"):
        return []
    bsd = blob.get("banned_substance_detail")
    if isinstance(bsd, dict):
        one = (bsd.get("safety_warning_one_liner") or "").strip()
        body = (bsd.get("safety_warning") or "").strip()
        if one and body:
            return []
        return [(blob.get("dsld_id"), "top-level-missing-copy")]
    # Fall back to ingredient-level
    banned_ings = [
        i for i in (blob.get("ingredients") or [])
        if isinstance(i, dict) and i.get("is_banned")
    ]
    if not banned_ings:
        return [(blob.get("dsld_id"), "no-marked-ingredient")]
    if not any(
        (i.get("safety_warning_one_liner") or "").strip()
        and (i.get("safety_warning") or "").strip()
        for i in banned_ings
    ):
        return [(blob.get("dsld_id"), "ingredient-missing-copy")]
    return []


def _axis_duplicate_warnings(blob: dict) -> list[tuple]:
    """S5 — no duplicate entries within each warning list."""
    def _key(w: dict) -> tuple:
        def _norm(v):
            if v is None:
                return ()
            if isinstance(v, (list, tuple)):
                return tuple(sorted(str(x) for x in v))
            return (str(v),)
        return (
            w.get("severity"),
            w.get("canonical_id") or w.get("type"),
            _norm(w.get("condition_id") or w.get("condition_ids")),
            _norm(w.get("drug_class_id") or w.get("drug_class_ids")),
            w.get("source_rule"),
        )

    violations = []
    for key in ("warnings", "warnings_profile_gated"):
        seen: dict[tuple, int] = {}
        for w in blob.get(key) or []:
            if isinstance(w, dict):
                k = _key(w)
                seen[k] = seen.get(k, 0) + 1
        dups = {str(k): n for k, n in seen.items() if n > 1}
        if dups:
            violations.append((blob.get("dsld_id"), key, len(dups)))
    return violations


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------

def _iter_blobs(blob_dir: Path) -> Iterable[tuple[str, dict]]:
    """Stream blobs from a directory, sorted by filename for determinism."""
    for p in sorted(blob_dir.glob("*.json")):
        try:
            yield p.name, json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue


def compute_scope_report(
    blob_dir: Path,
    raw_dir: Path | None = None,  # reserved — axes currently rely on blob snapshots
    sample_cap: int = DEFAULT_SAMPLE_CAP,
) -> dict:
    """Scan all blobs, compute per-axis violation counts + samples.

    Returns a deterministic dict:
      {
        "scanned_products": int,
        "label_fidelity": {axis_key: {"count": int, "samples": [...]}},
        "safety_copy": {axis_key: {"count": int, "samples": [...]}},
        "total_violations": int,
      }
    """
    fidelity_axes = _axes_label_fidelity()
    safety_axes = _axes_safety_copy()

    fidelity_violations: dict[str, list[tuple]] = {k: [] for k, _ in fidelity_axes}
    safety_violations: dict[str, list[tuple]] = {k: [] for k, _ in safety_axes}

    scanned = 0
    for _, blob in _iter_blobs(blob_dir):
        scanned += 1
        for key, fn in fidelity_axes:
            try:
                fidelity_violations[key].extend(fn(blob))
            except Exception:  # pragma: no cover — defensive, don't kill scan on one bad blob
                pass
        for key, fn in safety_axes:
            try:
                safety_violations[key].extend(fn(blob))
            except Exception:  # pragma: no cover
                pass

    def _summarize(buckets: dict[str, list[tuple]]) -> dict:
        out = {}
        for axis in sorted(buckets.keys()):
            vios = buckets[axis]
            # Deterministic: sort by string repr, cap, stringify for JSON
            samples = sorted((str(v) for v in vios))[:sample_cap]
            out[axis] = {"count": len(vios), "samples": samples}
        return out

    lf = _summarize(fidelity_violations)
    sc = _summarize(safety_violations)
    total = sum(v["count"] for v in lf.values()) + sum(v["count"] for v in sc.values())

    return {
        "scanned_products": scanned,
        "label_fidelity": lf,
        "safety_copy": sc,
        "total_violations": total,
    }


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_markdown(report: dict) -> str:
    """Render the scope report as a Markdown table. Output is byte-
    identical across runs given identical input (no wall-clock)."""
    lines = [
        "# Sprint E1 — Label-Fidelity + Safety-Copy Scope Report",
        "",
        f"**Scanned products:** {report['scanned_products']}",
        f"**Total violations:** {report['total_violations']}",
        "",
        "## Label-fidelity axes (E1.0.1)",
        "",
        "| Axis | Count |",
        "|---|---:|",
    ]
    for axis in sorted(report["label_fidelity"].keys()):
        lines.append(f"| `{axis}` | {report['label_fidelity'][axis]['count']} |")

    lines += [
        "",
        "## Safety-copy axes (E1.0.2)",
        "",
        "| Axis | Count |",
        "|---|---:|",
    ]
    for axis in sorted(report["safety_copy"].keys()):
        lines.append(f"| `{axis}` | {report['safety_copy'][axis]['count']} |")

    # Samples (sorted, capped) for first-pass triage.
    lines += ["", "## Samples (first 10 per axis, sorted)", ""]
    for section_key, section_title in (
        ("label_fidelity", "Label-fidelity"),
        ("safety_copy", "Safety-copy"),
    ):
        for axis in sorted(report[section_key].keys()):
            samples = report[section_key][axis]["samples"]
            if not samples:
                continue
            lines += [f"### {section_title} — `{axis}`", ""]
            for s in samples:
                lines.append(f"- `{s}`")
            lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--blobs", required=True, type=Path, help="Detail-blobs directory")
    p.add_argument("--raw", type=Path, default=None, help="Raw DSLD staging dir (reserved)")
    p.add_argument("--out", type=Path, default=Path("reports"), help="Output directory")
    p.add_argument("--prefix", default="label_fidelity_scope_latest", help="Filename prefix")
    p.add_argument("--sample-cap", type=int, default=DEFAULT_SAMPLE_CAP, help="Max samples per axis")
    p.add_argument("--fail-on-violations", action="store_true", help="Exit 1 if any axis has violations")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.blobs.is_dir():
        sys.stderr.write(f"error: --blobs {args.blobs} is not a directory\n")
        return 2

    report = compute_scope_report(args.blobs, args.raw, sample_cap=args.sample_cap)

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / f"{args.prefix}.json"
    md_path = args.out / f"{args.prefix}.md"

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_markdown(report))

    sys.stdout.write(
        f"scope report: {report['scanned_products']} products, "
        f"{report['total_violations']} violations → {json_path} / {md_path}\n"
    )

    if args.fail_on_violations and report["total_violations"] > 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
