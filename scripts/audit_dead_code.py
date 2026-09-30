#!/usr/bin/env python3
"""Find production code nothing uses, so no agent mistakes a dead path for a live one.

Every finding is a candidate, never proof on its own. Removal needs one proof tag and the
proof-of-life checks in scripts/audits/closure_20260921/REMOVALS_AND_RETENTIONS_20260921.md.

  functions  Functions and classes under scripts/ (tests and dated audits excluded) that no
             other code names: "unreferenced", "tests_only" or "audits_only". Iterated to a
             fixpoint, so helpers reached only from dead code are listed too. Exits 1 on a
             finding missing from KEEP, or a KEEP entry that is no longer a finding (the
             fast-rung ratchet, scripts/tests/test_no_unreferenced_production_code.py).
  keys       Dict keys production code writes and no tracked file (nor the Flutter lib/)
             names again: a value computed and never read. Review list, never a gate.
  trace      Functions never entered while replay.py re-scores frozen raw labels
             (clean -> enrich -> score), limited to modules the run imported. Review list:
             a guard today's corpus does not trigger is dormant, not dead.

Usage:
    python3 scripts/audit_dead_code.py functions [--json]
    python3 scripts/audit_dead_code.py keys
    python3 scripts/audit_dead_code.py trace --products-root F --manifest F/manifest.json --out trace.json

What counts as a reference: an AST name, attribute, import or identifier inside a string
literal (docstrings and comments excluded) in the defining file, or in a file that names the
defining module; a method may be named from any file. Shell scripts, JSON/YAML config, SQL,
.claude skills and rules, and docs/runbooks count as live references (CLI and string
dispatch). Other Markdown only reports where a dead name still appears, so its docs leave
in the same commit.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve().relative_to(REPO).as_posix()
FLUTTER_LIB = Path("/Users/seancheick/PharmaGuide ai/lib")
TESTS = "scripts/tests/"
AUDITS = "scripts/audits/"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
OPS_SUFFIXES = {".sh", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".sql", ".js", ".html"}
OPS_MARKDOWN = (".claude/", "docs/runbooks/")
# Names a framework calls without the code ever naming them.
FRAMEWORK_HOOKS = {"main", "do_GET", "do_POST", "do_PUT", "do_DELETE", "do_HEAD", "do_OPTIONS",
                   "log_message", "generic_visit", "setUp", "tearDown",
                   "handle_starttag", "handle_endtag", "handle_startendtag", "handle_data"}
PLAIN_DECORATORS = {"staticmethod", "classmethod", "property", "lru_cache", "cache", "dataclass",
                    "wraps", "cached_property"}

# path::name -> why it stays. Each reason names the proof of life or the owner who decides.
_PENDING = "PENDING removal, batch 1 (scripts/audits/dead_code_20261001)"
_RELEASE = "release chain: test-only, removal is Sean's call (dead_code_20261001 ledger)"
KEEP: dict[str, str] = {
    # Test support: tests read a live object's state through it.
    "scripts/cert_resolver.py::recency_for": "cert-audit canary test reads registry recency through it",
    "scripts/identity_integrity.py::resolve_unambiguous": "identity-integrity tests pin alias ownership through it",
    "scripts/normalization.py::clear_caches": "resets the normalizer's lru caches between test cases",
    "scripts/normalization.py::validate_normalized_key": "provenance tests assert the key format of every cleaned row",
    "scripts/release_artifact_paths.py::catalog_dist_dir": "release tests locate candidate vs live artifacts through it",
    "scripts/release_artifact_paths.py::final_build_dir": "release tests locate candidate vs live artifacts through it",
    "scripts/submission_review/extraction/grounding.py::ungrounded": "grounding tests read the report through it",
    # Cross-repo reference implementations the app must match.
    "scripts/profile_gate_evaluator.py::evaluate_profile_gate": "reference evaluator; Flutter must match it on scripts/data/profile_gate_test_cases.json",
    "scripts/profile_gate_evaluator.py::validate_profile_gate": "reference validator; Flutter must match it on scripts/data/profile_gate_test_cases.json",
    "scripts/safety_alerts.py::applies_to": "reference of the device-side alert applicability the app implements",
    "scripts/export_schema.py::resolve_warning_rule_refs": "reference of schema-3 warning-ref rehydration (app: warning_rule_ref_resolver.dart)",
    # Owned elsewhere: another lane or Sean decides.
    "scripts/evidence_resolver.py::resolve_evidence_for_canonical": "lane 2A (evidence/owner-eligibility) edits this file; classify after it lands",
    "scripts/clinical_evidence_schema.py::validate_ingredient_context": "validator for ingredient-lane study contexts, not yet wired into a data gate (a wiring decision)",
    "scripts/submission_review/extraction/development.py::run_development_split": "submission-extraction lane owns the development harness",
    "scripts/cleanup_old_versions.py::list_version_directory": _RELEASE,
    "scripts/supabase_client.py::storage_object_exists": _RELEASE,
    "scripts/release_safety/blob_inventory.py::require_complete": _RELEASE,
    "scripts/release_safety/gates.py::failure_summary": _RELEASE,
    "scripts/release_safety/orphan_reconcile.py::total_objects_examined": _RELEASE,
    # Removed in this branch, one topic per commit.
    "scripts/unii_cache.py::lookup_for_iqm_entry": _PENDING,
    "scripts/unii_cache.py::bulk_lookup": _PENDING,
    "scripts/unii_cache.py::is_loaded": _PENDING,
    "scripts/api_audit/discover_clinical_evidence.py::candidate_to_clinical_entry": _PENDING,
    "scripts/ingest_suppai.py::build_known_supplement_cuis": _PENDING,
    "scripts/ingest_suppai.py::enrich_curated_with_suppai": _PENDING,
    "scripts/serving_frequency.py::daily_use_direction_state": _PENDING,
}


def tracked(*patterns: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "ls-files", "--", *patterns],
                         check=True, capture_output=True, text=True).stdout
    return [p for p in out.splitlines() if (REPO / p).is_file()]


def is_production(path: str) -> bool:
    return path.startswith("scripts/") and not path.startswith((TESTS, AUDITS))


def module_name(path: str) -> str:
    """The name an import uses: a package's __init__.py is imported by its directory."""
    p = Path(path)
    return p.parent.name if p.name == "__init__.py" else p.stem


def layer(path: str) -> str:
    return "test" if path.startswith(TESTS) else "audit" if path.startswith(AUDITS) else "prod"


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def references(tree: ast.AST, strings: bool = True) -> list[tuple[str, int]]:
    """(identifier, line) for every name the code uses; definitions and prose excluded."""
    docs = _docstring_ids(tree)
    refs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs.append((node.id, node.lineno))
        elif isinstance(node, ast.Attribute):
            refs.append((node.attr, node.lineno))
        elif isinstance(node, ast.alias):
            for name in (node.name, node.asname or ""):
                refs.extend((part, node.lineno) for part in name.split(".") if part)
        elif isinstance(node, ast.ImportFrom) and node.module:
            refs.extend((part, node.lineno) for part in node.module.split("."))
        elif strings and isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docs:
            refs.extend((tok, node.lineno) for tok in IDENT.findall(node.value))
    return refs


def _decorator_name(node: ast.expr) -> str:
    node = node.func if isinstance(node, ast.Call) else node
    return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")


def definitions(tree: ast.AST, path: str) -> list[dict]:
    defs = []

    def visit(node: ast.AST, in_class: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = child.name
                registered = any(_decorator_name(d) not in PLAIN_DECORATORS
                                 for d in child.decorator_list)
                if not (name.startswith("__") or name in FRAMEWORK_HOOKS
                        or name.startswith(("test_", "visit_")) or registered):
                    defs.append({"path": path, "name": name, "start": child.lineno,
                                 "end": child.end_lineno, "method": in_class,
                                 "kind": "class" if isinstance(child, ast.ClassDef) else "function"})
                visit(child, isinstance(child, ast.ClassDef))
            else:
                visit(child, in_class)

    visit(tree, False)
    return defs


def load_python() -> tuple[dict[str, ast.AST], list[str]]:
    trees, unparsable = {}, []
    for path in tracked("scripts/*.py"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                trees[path] = ast.parse((REPO / path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            unparsable.append(path)
    return trees, unparsable


def scan_functions() -> dict:
    trees, unparsable = load_python()
    defs = [d for path, tree in trees.items() if is_production(path)
            for d in definitions(tree, path)]
    wanted = {d["name"] for d in defs} | {module_name(p) for p in trees}
    uses: dict[str, list[tuple[str, int]]] = defaultdict(list)   # name -> (file, line)
    for path, tree in trees.items():
        # KEEP names every finding in string literals; naming is not using.
        for name, line in references(tree, strings=path != SELF):
            if name in wanted:
                uses[name].append((path, line))
    importers: dict[str, set[str]] = defaultdict(set)             # module path -> files naming it
    for path in trees:
        for other, _ in uses.get(module_name(path), ()):
            importers[path].add(other)

    ops_files = [p for p in tracked() if not p.endswith(".py")
                 and (Path(p).suffix in OPS_SUFFIXES
                      or (p.endswith(".md") and p.startswith(OPS_MARKDOWN)))
                 and not p.startswith(("scripts/data/", "scripts/tests/fixtures/", AUDITS))]
    doc_files = [p for p in tracked("*.md") if p not in ops_files]

    dead_spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
    findings: dict[tuple[str, str], dict] = {}
    changed = True
    while changed:
        changed = False
        for d in defs:
            key = (d["path"], d["name"])
            if key in findings:
                continue
            layers = set()
            for path, line in uses.get(d["name"], ()):
                if path == d["path"] and d["start"] <= line <= d["end"]:
                    continue
                if any(a <= line <= b for a, b in dead_spans.get(path, ())):
                    continue
                if path == d["path"] or d["method"] or path in importers[d["path"]]:
                    layers.add(layer(path))
            if "prod" in layers:
                continue
            bucket = "tests_only" if "test" in layers else "audits_only" if layers else "unreferenced"
            findings[key] = dict(d, bucket=bucket)
            if bucket == "unreferenced":
                # Only code nothing reaches stops vouching for its callees; code a test
                # reaches is still run, and its helpers surface once it is removed.
                dead_spans[d["path"]].append((d["start"], d["end"]))
                changed = True

    texts = {p: (REPO / p).read_text(encoding="utf-8", errors="ignore") for p in ops_files + doc_files}
    result = []
    for (path, name), finding in sorted(findings.items()):
        pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")
        ops = [p for p in ops_files if name in texts[p] and pattern.search(texts[p])]
        if ops:
            continue   # named by a shell script, config or skill: CLI or string dispatch
        finding["docs"] = [p for p in doc_files if name in texts[p] and pattern.search(texts[p])]
        finding["tests"] = sorted({p for p, _ in uses.get(name, ()) if p.startswith(TESTS)})
        finding["lines"] = finding["end"] - finding["start"] + 1
        finding["id"] = f"{path}::{name}"
        result.append(finding)

    orphan_files = []
    for path in trees:
        if not is_production(path) or path.endswith("__init__.py"):
            continue
        stem = Path(path).stem
        named = {layer(p) for p in importers[path]}
        if "prod" in named or any(stem in texts[p] for p in ops_files):
            continue
        # A CLI is an entry point: listed only when not even a test or a doc names it.
        cli = "__main__" in (REPO / path).read_text(encoding="utf-8")
        if cli and (named or any(stem in texts[p] for p in doc_files)):
            continue
        orphan_files.append({"path": path, "named_by": sorted(named), "cli": cli})
    return {"findings": result, "orphan_files": orphan_files, "unparsable": unparsable}


def scan_keys() -> list[dict]:
    trees, _ = load_python()
    written = []
    for path, tree in trees.items():
        if not is_production(path):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                written.extend((k.value, k.lineno, path) for k in node.keys
                               if isinstance(k, ast.Constant) and isinstance(k.value, str))
            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                written.extend((t.slice.value, t.lineno, path) for t in targets
                               if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                               and isinstance(t.slice.value, str))
    counts: dict[str, int] = defaultdict(int)
    sources = [REPO / p for p in tracked() if Path(p).suffix in OPS_SUFFIXES | {".py", ".md", ".dart"}]
    if FLUTTER_LIB.is_dir():
        sources += [p for p in FLUTTER_LIB.rglob("*.dart") if not p.name.endswith(".g.dart")]
    for source in sources:
        for tok in IDENT.findall(source.read_text(encoding="utf-8", errors="ignore")):
            counts[tok] += 1
    return [{"path": p, "line": line, "key": key} for key, line, p in sorted(written, key=lambda w: (w[2], w[1]))
            if IDENT.fullmatch(key) and counts[key] == 1]


def trace(products_root: str, manifest: str, out: str) -> dict:
    """Re-score frozen labels in this process and list production functions never entered."""
    import importlib.util
    entered: set[tuple[str, int]] = set()
    monitoring = sys.monitoring
    tool = monitoring.OPTIMIZER_ID

    def on_start(code, _offset):
        entered.add((code.co_filename, code.co_firstlineno))
        return monitoring.DISABLE

    spec = importlib.util.spec_from_file_location("replay", REPO / AUDITS / "quality_redesign/replay.py")
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    monitoring.use_tool_id(tool, "audit_dead_code")
    monitoring.register_callback(tool, monitoring.events.PY_START, on_start)
    monitoring.set_events(tool, monitoring.events.PY_START)
    try:
        replay.worker(argparse.Namespace(checkout=str(REPO), products_root=products_root,
                                         manifest=manifest, out=out + ".snapshot.jsonl", workers=1))
    finally:
        monitoring.set_events(tool, 0)
        monitoring.free_tool_id(tool)

    imported = {str(Path(m.__file__).resolve()) for m in list(sys.modules.values())
                if getattr(m, "__file__", None)}
    trees, _ = load_python()
    never = []
    for path, tree in trees.items():
        full = str((REPO / path).resolve())
        if not is_production(path) or full not in imported:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                if (full, first) not in entered:
                    never.append({"path": path, "name": node.name, "line": node.lineno,
                                  "lines": node.end_lineno - node.lineno + 1})
    report = {"products_root": products_root, "never_entered": never,
              "modules_imported": sum(1 for p in trees if str((REPO / p).resolve()) in imported)}
    Path(out).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("functions").add_argument("--json", action="store_true")
    subs.add_parser("keys")
    t = subs.add_parser("trace")
    for flag in ("products-root", "manifest", "out"):
        t.add_argument("--" + flag, required=True)
    args = parser.parse_args()

    if args.command == "keys":
        keys = scan_keys()
        by_file: dict[str, list[str]] = defaultdict(list)
        for k in keys:
            by_file[k["path"]].append(f'{k["key"]}:{k["line"]}')
        for path, items in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
            print(f"{len(items):5d}  {path}  {' '.join(items[:12])}")
        print(f"{len(keys)} keys written once and named nowhere else")
        return 0
    if args.command == "trace":
        report = trace(args.products_root, args.manifest, args.out)
        print(f"{len(report['never_entered'])} functions never entered in "
              f"{report['modules_imported']} imported production modules -> {args.out}")
        return 0

    scan = scan_functions()
    new = [f for f in scan["findings"] if f["id"] not in KEEP]
    stale = sorted(set(KEEP) - {f["id"] for f in scan["findings"]})
    if args.json:
        print(json.dumps(dict(scan, new=[f["id"] for f in new], stale_keep=stale), indent=2))
    else:
        for f in scan["findings"]:
            mark = "KEEP" if f["id"] in KEEP else "NEW "
            print(f'{mark} {f["bucket"]:12s} {f["path"]}:{f["start"]} {f["name"]} ({f["lines"]} lines)'
                  + (f'  tests={len(f["tests"])}' if f["tests"] else "")
                  + (f'  docs={",".join(f["docs"])}' if f["docs"] else ""))
        for o in scan["orphan_files"]:
            print(f'FILE {o["path"]} named_by={o["named_by"] or "nothing"} cli={o["cli"]}')
        for path in scan["unparsable"]:
            print(f"UNPARSABLE {path}")
        for key in stale:
            print(f"STALE KEEP {key}: no longer a finding; remove it from KEEP")
        print(f'{len(scan["findings"])} findings, {len(new)} not in KEEP, {len(stale)} stale KEEP entries')
    return 1 if new or stale else 0


if __name__ == "__main__":
    sys.exit(main())
