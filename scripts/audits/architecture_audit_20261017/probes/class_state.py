#!/usr/bin/env python3
"""Shared-state map of one class: which instance attributes each method reads and writes.

This is the check the September 2026 mega-file audit skipped: a method is only "extractable with
explicit inputs" if its `self.*` reads are load-once reference indexes and it writes no per-product
state. The probe lists, per method, the attributes read, the attributes written (assignment,
subscript assignment, or a mutating call such as append/update/clear/add/pop/setdefault), the other
methods it calls on self, and the module-level names it reads; and, per attribute, where it is
written. Reproducible from the pinned revision; AUDIT.md cites it by method name.

    $PG_PYTHON probes/class_state.py scripts/enrich_supplements_v3.py SupplementEnricherV3 --prefix _collect_ --prefix _match_ --prefix _build_ --prefix enrich_product
    $PG_PYTHON probes/class_state.py scripts/enhanced_normalizer.py EnhancedDSLDNormalizer --prefix _process_ --prefix normalize_product
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MUTATORS = {"append", "extend", "update", "clear", "add", "pop", "setdefault", "insert", "remove", "discard", "popitem"}


def self_attr(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return node.attr
    return None


def analyse(path: Path, class_name: str, prefixes: list[str]) -> dict:
    tree = ast.parse(path.read_text())
    module_names = {n.id for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
                    for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    module_names |= {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    method_names = {m.name for m in methods}
    writers: dict[str, set[str]] = collections.defaultdict(set)
    readers: dict[str, set[str]] = collections.defaultdict(set)
    per_method = {}
    for m in methods:
        reads, writes, calls, globals_read = set(), set(), set(), set()
        for node in ast.walk(m):
            if isinstance(node, ast.Attribute):
                attr = self_attr(node)
                if attr is None:
                    continue
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    writes.add(attr)
                elif attr in method_names:
                    calls.add(attr)
                else:
                    reads.add(attr)
            elif isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
                target = node.value
                while isinstance(target, ast.Subscript):
                    target = target.value
                attr = self_attr(target)
                if attr:
                    writes.add(attr)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in MUTATORS:
                target = node.func.value
                while isinstance(target, ast.Subscript):
                    target = target.value
                attr = self_attr(target)
                if attr:
                    writes.add(attr)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in module_names:
                globals_read.add(node.id)
        reads -= writes
        for a in writes:
            writers[a].add(m.name)
        for a in reads:
            readers[a].add(m.name)
        per_method[m.name] = {
            "line": m.lineno,
            "length": (m.end_lineno or m.lineno) - m.lineno + 1,
            "params": len(m.args.args) - 1,
            "reads": sorted(reads),
            "writes": sorted(writes),
            "calls": sorted(calls),
            "module_globals": sorted(globals_read),
        }
    init_written = writers.get("__init__", set())
    attrs = {}
    for attr in sorted(set(writers) | set(readers)):
        w = sorted(writers.get(attr, ()))
        attrs[attr] = {
            "written_in": w,
            "read_in": len(readers.get(attr, ())),
            "class": ("load_once" if w == ["__init__"] else "never_written_here" if not w
                      else "init_and_rebuilt" if "__init__" in w else "per_run_mutable"),
        }
    selected = {k: v for k, v in per_method.items() if any(k.startswith(p) for p in prefixes)} if prefixes else per_method
    return {"path": str(path.relative_to(REPO)), "class": class_name, "methods": len(methods), "attributes": attrs,
            "selected_methods": selected, "all_methods": per_method}


def closures(result: dict, peer_prefix: str = "_collect_") -> dict:
    """Transitive self-call closure per selected method, and pairwise overlap between them.

    A collector whose closure is disjoint from the others is a candidate owner module; closures
    that share most of their helpers point at one shared core (identity/matching) instead.
    Exclusivity and the shared core are computed among the *peer* methods only (those whose name
    starts with ``peer_prefix``): an orchestrator such as ``enrich_product`` reaches everything and
    would otherwise make every helper non-exclusive.
    """
    methods = result["all_methods"]
    out = {}
    for name in result["selected_methods"]:
        seen, frontier = set(), [name]
        while frontier:
            current = frontier.pop()
            for callee in methods.get(current, {}).get("calls", []):
                if callee not in seen and callee != name:
                    seen.add(callee)
                    frontier.append(callee)
        members = [name] + sorted(seen)
        reads = set().union(*(set(methods[m]["reads"]) for m in members))
        writes = set().union(*(set(methods[m]["writes"]) for m in members))
        glob = set().union(*(set(methods[m]["module_globals"]) for m in members))
        out[name] = {
            "closure_methods": len(seen),
            "closure_members": sorted(seen),
            "closure_loc": sum(methods[m]["length"] for m in members),
            "transitive_reads": sorted(reads),
            "transitive_writes": sorted(writes),
            "transitive_module_globals": sorted(glob),
            "_members": set(members),
        }
    names = sorted(out, key=lambda n: -out[n]["closure_loc"])
    overlap = {}
    for a in names:
        row = {}
        for b in names:
            if a != b:
                shared = out[a]["_members"] & out[b]["_members"]
                if shared:
                    row[b] = len(shared)
        overlap[a] = row
    # Exclusive helpers (reached by no other peer) and the shared core (reached by >= 3 peers), the
    # two numbers a decomposition design rests on. Both are derived from closure_members over peers.
    peers = {n for n in out if n.startswith(peer_prefix)} or set(out)
    helper_users = collections.Counter()
    for n in peers:
        for m in out[n]["closure_members"]:
            helper_users[m] += 1
    for name, v in out.items():
        if name in peers:
            exclusive = sorted(m for m in v["closure_members"] if helper_users[m] == 1)
        else:
            exclusive = []
        v["exclusive_helpers"] = exclusive
        v["exclusive_loc"] = sum(methods[m]["length"] for m in exclusive)
    union = set(helper_users)
    shared_core = sorted(m for m in union if helper_users[m] >= 3)
    summary = {
        "peer_prefix": peer_prefix,
        "peers": len(peers),
        "union_helpers": len(union),
        "union_helper_loc": sum(methods[m]["length"] for m in union),
        "shared_core_helpers": shared_core,
        "shared_core_loc": sum(methods[m]["length"] for m in shared_core),
    }
    for v in out.values():
        v.pop("_members")
    return {"per_method": out, "shared_helper_counts": overlap, "summary": summary}


def render(result: dict) -> str:
    attrs = result["attributes"]
    kinds = collections.Counter(a["class"] for a in attrs.values())
    lines = [f"# {result['class']} state map ({result['path']})", "",
             f"{result['methods']} methods; {len(attrs)} instance attributes: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())), "",
             "| method | line | len | params | self reads | self writes | self calls | module globals |", "|---|---|---|---|---|---|---|---|"]
    for name, m in sorted(result["selected_methods"].items(), key=lambda kv: -kv[1]["length"]):
        writes = ", ".join(m["writes"][:6]) + (" …" if len(m["writes"]) > 6 else "")
        lines.append(f"| {name} | {m['line']} | {m['length']} | {m['params']} | {len(m['reads'])} | {len(m['writes'])}: {writes} | {len(m['calls'])} | {len(m['module_globals'])} |")
    if result.get("closures"):
        per = result["closures"]["per_method"]
        shared = result["closures"]["shared_helper_counts"]
        summary = result["closures"]["summary"]
        lines += ["", "## Transitive helper closure per selected method", "",
                  f"Peers (prefix `{summary['peer_prefix']}`): {summary['peers']} methods reach {summary['union_helpers']} helpers "
                  f"({summary['union_helper_loc']:,} LOC); shared core (helpers reached by ≥3 peers) "
                  f"{len(summary['shared_core_helpers'])} helpers, {summary['shared_core_loc']:,} LOC: "
                  + ", ".join(summary["shared_core_helpers"][:12]) + (" …" if len(summary["shared_core_helpers"]) > 12 else ""), "",
                  "| method | closure methods | closure LOC | exclusive helpers | exclusive LOC | transitive self reads | transitive writes | module globals | most-shared-with (shared helpers) |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for name, c in sorted(per.items(), key=lambda kv: -kv[1]["closure_loc"]):
            top = sorted(shared.get(name, {}).items(), key=lambda kv: -kv[1])[:3]
            lines.append(f"| {name} | {c['closure_methods']} | {c['closure_loc']:,} | {len(c['exclusive_helpers'])} | {c['exclusive_loc']:,} | "
                         f"{len(c['transitive_reads'])} | {', '.join(c['transitive_writes'][:5]) or '-'} | {len(c['transitive_module_globals'])} | "
                         + ", ".join(f"{b} ({n})" for b, n in top) + " |")
    lines += ["", "## Per-run mutable attributes (written outside __init__)", "", "| attribute | written in | read in (methods) |", "|---|---|---|"]
    for attr, a in sorted(attrs.items(), key=lambda kv: (-len(kv[1]["written_in"]), kv[0])):
        if a["class"] in {"per_run_mutable", "init_and_rebuilt"}:
            lines.append(f"| {attr} | {', '.join(a['written_in'][:5])}{' …' if len(a['written_in']) > 5 else ''} | {a['read_in']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path")
    parser.add_argument("class_name")
    parser.add_argument("--prefix", action="append", default=[])
    parser.add_argument("--peer-prefix", default="_collect_",
                        help="methods whose names start with this form the peer group for exclusivity and the shared core")
    args = parser.parse_args()
    result = analyse(REPO / args.path, args.class_name, args.prefix)
    result["closures"] = closures(result, args.peer_prefix)
    stem = HERE / f"{args.class_name}_state"
    stem.with_suffix(".json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    stem.with_suffix(".md").write_text(render(result))
    kinds = collections.Counter(a["class"] for a in result["attributes"].values())
    print(f"{args.class_name}: {result['methods']} methods, {len(result['attributes'])} attributes {dict(kinds)} -> {stem}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
