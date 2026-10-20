#!/usr/bin/env python3
"""Pinned census for the architecture audit of 2026-10-17.

Every number AUDIT.md quotes comes from census.json, which this script rebuilds from the working
tree at the pinned revision. It refuses to run when a tracked production file is modified, so the
numbers always describe one commit. Inputs that live outside git (batch-run summaries, enrichment
summaries, the CI run) are recorded with their sha256 or run id, so a later re-run shows exactly
which input moved.

    $PG_PYTHON scripts/audits/architecture_audit_20261017/census.py               # census.json + census.md
    $PG_PYTHON scripts/audits/architecture_audit_20261017/census.py --check-refs AUDIT.md

Level-2 promotion criteria (from the approved plan): >800 LOC, a function >300 lines or nesting
>= 10, >= 30 commits since 2026-07-01, member of the lazy-import cycle, fan-in >= 15 or fan-out
>= 10, owner of >= 2 matrix concepts, or part of the release chain. Level 2 means the audit read
the source; Level 1 means these metrics only.
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRIPTS = REPO / "scripts"
PINNED_REV = "5fb2be1ca"
CHURN_SINCE = "2026-07-01"
CI_RUN_ID = "39070168203"  # latest green pipeline-tests run on the pinned revision
EXCLUDED_DIRS = {"tests", "audits", "archive", "__pycache__"}
MEGA_FILES = (
    "scripts/enrich_supplements_v3.py",
    "scripts/enhanced_normalizer.py",
    "scripts/build_final_db.py",
    "scripts/scoring_input_contract.py",
)
COCHANGE_FILES = MEGA_FILES + ("scripts/evidence_resolver.py", "scripts/supplement_taxonomy.py")
RELEASE_CHAIN = {
    "batch_run_all_datasets.sh",
    "scripts/release_full.sh",
    "scripts/rebuild_dashboard_snapshot.sh",
    "scripts/build_final_db.py",
    "scripts/sync_to_supabase.py",
    "scripts/release_catalog_artifact.py",
    "scripts/promote_release_artifacts.py",
    "scripts/release_interaction_artifact.py",
    "scripts/build_interaction_db.py",
}
L2 = {"loc": 800, "func_len": 300, "nesting": 10, "churn": 30, "fan_in": 15, "fan_out": 10, "concepts": 2}
BULK_COMMIT_FILES = 25  # commits touching more production files than this are sweeps, not co-change
LOGGER_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}
NESTING_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match, ast.AsyncFor, ast.AsyncWith)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def is_production(path: str) -> bool:
    if not path.startswith("scripts/") or not path.endswith(".py"):
        return False
    return not (set(path.split("/")[1:-1]) & EXCLUDED_DIRS)


def module_name(path: str) -> str:
    name = path[len("scripts/") : -3].replace("/", ".")
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


# --------------------------------------------------------------------------------------------
# pin


def pin(expected_rev: str) -> dict:
    head = git("rev-parse", "HEAD").strip()
    if not head.startswith(expected_rev):
        sys.exit(f"HEAD is {head[:9]}, census is pinned to {expected_rev}")
    dirty = [line for line in git("status", "--porcelain").splitlines() if line.strip()]
    modified_production = [
        line for line in dirty
        if not line.startswith("??") and (is_production(line[3:]) or line[3:].endswith(".sh"))
    ]
    if modified_production:
        sys.exit("tracked production files are modified; census refuses to run:\n" + "\n".join(modified_production))
    return {"head": head, "pinned_rev": expected_rev, "dirty_entries": sorted(dirty)}


# --------------------------------------------------------------------------------------------
# per-module metrics


def nesting(node: ast.AST, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        step = depth + 1 if isinstance(child, NESTING_NODES) else depth
        deepest = max(deepest, nesting(child, step))
    return deepest


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.FunctionDef | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = parents.get(current)
    return None


def is_broad_except(handler: ast.ExceptHandler) -> bool:
    kind = handler.type
    if kind is None:
        return True
    names = [kind] if not isinstance(kind, ast.Tuple) else list(kind.elts)
    return any(isinstance(n, ast.Name) and n.id in {"Exception", "BaseException"} for n in names)


def is_logger_call(call: ast.Call) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in LOGGER_METHODS:
        return False
    owner = func.value
    if isinstance(owner, ast.Name):
        return owner.id.lower() in {"logger", "logging", "log", "_log", "_logger"}
    return isinstance(owner, ast.Attribute) and owner.attr.lower() in {"logger", "log", "_logger"}


def function_record(path: str, node: ast.FunctionDef, parents: dict[ast.AST, ast.AST]) -> dict:
    length = (node.end_lineno or node.lineno) - node.lineno + 1
    owner = parents.get(node)
    qualname = f"{owner.name}.{node.name}" if isinstance(owner, ast.ClassDef) else node.name
    nested = [n for n in ast.walk(node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not node]
    self_attrs = {
        n.attr for n in ast.walk(node)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self"
    }
    branches = sum(isinstance(n, NESTING_NODES + (ast.ExceptHandler,)) for n in ast.walk(node))
    returns = sum(isinstance(n, ast.Return) for n in ast.walk(node))
    args = node.args
    annotated = node.returns is not None or any(
        a.annotation is not None for a in args.args + args.kwonlyargs + args.posonlyargs
    )
    return {
        "path": path,
        "name": qualname,
        "line": node.lineno,
        "length": length,
        "nesting": nesting(node),
        "params": len(args.args) + len(args.kwonlyargs) + len(args.posonlyargs),
        "nested_defs": len(nested),
        "self_attrs": len(self_attrs),
        "branches": branches,
        "returns": returns,
        "annotated": annotated,
    }


def module_metrics(path: str, tree: ast.Module, text: str) -> tuple[dict, list[dict]]:
    parents = parent_map(tree)
    functions = [
        function_record(path, n, parents)
        for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    lazy_imports = sum(
        1 for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom)) and enclosing_function(n, parents) is not None
    )
    broad = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and is_broad_except(n))
    prints = sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"
    )
    logger_calls = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call) and is_logger_call(n))
    longest = max(functions, key=lambda f: f["length"], default=None)
    metrics = {
        "loc": text.count("\n") + (0 if text.endswith("\n") else 1),
        "functions": len(functions),
        "classes": len(classes),
        "class_methods": {c.name: sum(isinstance(m, ast.FunctionDef) for m in c.body) for c in classes},
        "module_assignments": sum(isinstance(n, (ast.Assign, ast.AnnAssign)) for n in tree.body),
        "longest_function": {k: longest[k] for k in ("name", "line", "length", "nesting")} if longest else None,
        "max_nesting": max((f["nesting"] for f in functions), default=0),
        "functions_over_150": sum(f["length"] > 150 for f in functions),
        "functions_over_300": sum(f["length"] > 300 for f in functions),
        "lazy_imports": lazy_imports,
        "broad_excepts": broad,
        "print_calls": prints,
        "logger_calls": logger_calls,
        "globals": sum(isinstance(n, ast.Global) for n in ast.walk(tree)),
        "annotated_functions": sum(f["annotated"] for f in functions),
    }
    return metrics, functions


# --------------------------------------------------------------------------------------------
# import graph


def import_edges(path: str, tree: ast.Module, text: str, known: set[str]) -> list[dict]:
    name = module_name(path)
    pkg = name.rsplit(".", 1)[0] if "." in name else ""
    parents = parent_map(tree)
    lines = text.splitlines()

    def resolve(target: str) -> str | None:
        target = target[len("scripts."):] if target.startswith("scripts.") else target
        if target in known:
            return target
        head = target.split(".")[0]
        if head in known:
            return head
        if pkg and f"{pkg}.{head}" in known:
            return f"{pkg}.{head}"
        return None

    edges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg if node.level == 1 else ""
                targets = [f"{base}.{a.name}" if base else a.name for a in node.names] if not node.module \
                    else [f"{base}.{node.module}" if base else node.module]
            else:
                targets = [node.module or ""]
        else:
            continue
        func = enclosing_function(node, parents)
        context = " ".join(lines[max(0, node.lineno - 2): node.lineno]).lower()
        for target in targets:
            resolved = resolve(target)
            if resolved and resolved != name:
                edges.append({
                    "src": name,
                    "dst": resolved,
                    "line": node.lineno,
                    "lazy": func is not None,
                    "in_function": func.name if func else None,
                    "comment_hint": bool(re.search(r"lazy|circular|cycle|import.?time|avoid", context)),
                })
    return edges


def strongly_connected(adjacency: dict[str, set[str]]) -> list[list[str]]:
    sys.setrecursionlimit(20000)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    out: list[list[str]] = []
    counter = [0]

    def visit(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(adjacency.get(v, ())):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.append(w)
                if w == v:
                    break
            if len(component) > 1:
                out.append(sorted(component))

    for v in sorted(adjacency):
        if v not in index:
            visit(v)
    return sorted(out, key=lambda c: (-len(c), c))


def graph_summary(all_edges: list[dict]) -> dict:
    top = collections.defaultdict(set)
    both = collections.defaultdict(set)
    for e in all_edges:
        both[e["src"]].add(e["dst"])
        if not e["lazy"]:
            top[e["src"]].add(e["dst"])
    fan_in = collections.Counter()
    lazy_in = collections.Counter()
    for e in all_edges:
        (lazy_in if e["lazy"] else fan_in)[e["dst"]] += 1
    fan_out = {m: len(d) for m, d in top.items()}
    cycles_top = strongly_connected(top)
    cycles_lazy = strongly_connected(both)
    cycle_members = {m for c in cycles_lazy for m in c}
    cycle_edges = sorted(
        (e for e in all_edges if e["src"] in cycle_members and e["dst"] in cycle_members
         and any(e["src"] in c and e["dst"] in c for c in cycles_lazy)),
        key=lambda e: (e["src"], e["dst"], e["line"]),
    )
    return {
        "top_level_edges": sum(not e["lazy"] for e in all_edges),
        "lazy_edges": sum(e["lazy"] for e in all_edges),
        "fan_in_top": sorted(fan_in.items(), key=lambda kv: (-kv[1], kv[0]))[:25],
        "lazy_fan_in_top": sorted(lazy_in.items(), key=lambda kv: (-kv[1], kv[0]))[:15],
        "fan_out_top": sorted(fan_out.items(), key=lambda kv: (-kv[1], kv[0]))[:20],
        "cycles_top_level": cycles_top,
        "cycles_with_lazy": cycles_lazy,
        "cycle_edges": cycle_edges,
        "_fan_in": dict(fan_in),
        "_fan_out": fan_out,
        "_cycle_members": sorted(cycle_members),
    }


# --------------------------------------------------------------------------------------------
# duplication


class _Normalize(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = "_"
        node.annotation = None
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str) and node.value:
            return ast.copy_location(ast.Constant(value="s"), node)
        return node


def duplication(trees: dict[str, ast.Module]) -> dict:
    exact = collections.defaultdict(list)
    structural = collections.defaultdict(list)
    private_names = collections.defaultdict(set)
    for path, tree in trees.items():
        parents = parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") and not node.name.startswith("__"):
                private_names[node.name].add(path)
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length < 10:
                continue
            owner = parents.get(node)
            label = f"{owner.name}.{node.name}" if isinstance(owner, ast.ClassDef) else node.name
            body = ast.Module(body=node.body, type_ignores=[])
            entry = {"path": path, "name": label, "line": node.lineno, "length": length}
            exact[hashlib.md5(ast.dump(body).encode()).hexdigest()].append(entry)
            normalized = _Normalize().visit(ast.parse(ast.unparse(body)))
            structural[hashlib.md5(ast.dump(normalized).encode()).hexdigest()].append(entry)

    def groups(index: dict) -> list[dict]:
        rows = []
        for members in index.values():
            if len(members) < 2:
                continue
            files = {m["path"] for m in members}
            rows.append({
                "members": sorted(members, key=lambda m: (m["path"], m["line"])),
                "files": len(files),
                "length": max(m["length"] for m in members),
                "duplicated_lines": sum(m["length"] for m in members) - max(m["length"] for m in members),
            })
        return sorted(rows, key=lambda r: (-r["length"], r["members"][0]["path"]))

    exact_groups = groups(exact)
    structural_groups = groups(structural)
    return {
        "exact_groups": exact_groups,
        "structural_groups": structural_groups,
        "exact_cross_file_groups": sum(g["files"] >= 2 for g in exact_groups),
        "structural_cross_file_groups": sum(g["files"] >= 2 for g in structural_groups),
        "structural_cross_file_duplicated_lines": sum(g["duplicated_lines"] for g in structural_groups if g["files"] >= 2),
        "same_name_private_helpers": sorted(
            ({"name": n, "files": len(p), "examples": sorted(p)[:4]} for n, p in private_names.items() if len(p) >= 3),
            key=lambda r: (-r["files"], r["name"]),
        ),
    }


# --------------------------------------------------------------------------------------------
# churn and co-change


def churn(rev: str, production: set[str]) -> dict:
    raw = git("log", rev, f"--since={CHURN_SINCE}", "--name-only", "--pretty=format:__C__%h")
    commits: list[set[str]] = []
    for line in raw.splitlines():
        if line.startswith("__C__"):
            commits.append(set())
        elif line.strip() and commits:
            commits[-1].add(line.strip())
    per_file = collections.Counter(f for c in commits for f in c)
    tests = {f: n for f, n in per_file.items() if f.startswith("scripts/tests/")}
    data = {f: n for f, n in per_file.items() if f.startswith("scripts/data/")}
    prod = {f: n for f, n in per_file.items() if f in production or f.endswith(".sh")}

    def group(path: str) -> str | None:
        if path.startswith("scripts/scoring_v4/") and path.endswith(".py"):
            return "scripts/scoring_v4/*"
        return path if path in COCHANGE_FILES else None

    touching = []
    skipped_bulk = 0
    for c in commits:
        prod_files = {f for f in c if f in production}
        if len(prod_files) > BULK_COMMIT_FILES:
            skipped_bulk += 1
            continue
        groups = {g for g in map(group, c) if g}
        if groups:
            touching.append(groups)
    pairs = collections.Counter()
    for groups in touching:
        ordered = sorted(groups)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                pairs[(a, b)] += 1
    general_pairs = collections.Counter()
    for c in commits:
        prod_files = sorted(f for f in c if f in production)
        if 2 <= len(prod_files) <= BULK_COMMIT_FILES:
            for i, a in enumerate(prod_files):
                for b in prod_files[i + 1:]:
                    general_pairs[(a, b)] += 1
    monthly = collections.Counter()
    for line in git("log", rev, f"--since={CHURN_SINCE}", "--format=%cs", "--", MEGA_FILES[0]).splitlines():
        monthly[line[:7]] += 1
    return {
        "since": CHURN_SINCE,
        "commits": len(commits),
        "production_top": sorted(prod.items(), key=lambda kv: (-kv[1], kv[0]))[:40],
        "tests_top": sorted(tests.items(), key=lambda kv: (-kv[1], kv[0]))[:15],
        "data_top": sorted(data.items(), key=lambda kv: (-kv[1], kv[0]))[:12],
        "cochange": {
            "groups": sorted(set(COCHANGE_FILES) | {"scripts/scoring_v4/*"}),
            "commits_touching_any": len(touching),
            "touching_2_or_more": sum(len(g) >= 2 for g in touching),
            "touching_3_or_more": sum(len(g) >= 3 for g in touching),
            "bulk_commits_skipped": skipped_bulk,
            "pairs": [(list(k), v) for k, v in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[:15]],
        },
        "general_pairs_top": [(list(k), v) for k, v in sorted(general_pairs.items(), key=lambda kv: (-kv[1], kv[0]))[:20]],
        "enricher_commits_by_month": sorted(monthly.items()),
        "_per_file": prod,
    }


# --------------------------------------------------------------------------------------------
# tests


def test_inventory(production_paths: list[str], trees: dict[str, ast.Module]) -> dict:
    test_files = sorted(f for f in git("ls-files", "scripts/tests").splitlines() if re.search(r"/test_[^/]+\.py$", f))
    texts = {f: (REPO / f).read_text(errors="ignore") for f in test_files}
    words = {f: set(re.findall(r"[A-Za-z_]\w+", t)) for f, t in texts.items()}
    refs = {}
    for path in production_paths:
        stems = {Path(path).stem} | {n.name for n in trees[path].body if isinstance(n, ast.ClassDef)}
        refs[path] = sum(1 for f in test_files if words[f] & stems)
    marks = collections.Counter()
    for t in texts.values():
        marks.update(re.findall(r"pytest\.mark\.([a-z_]+)", t))
    profiles = subprocess.run(
        [sys.executable, "-c",
         "import json,test_profiles as t;print(json.dumps({k:len(getattr(t,k)) for k in "
         "('SLOW_TEST_FILES','LOCAL_ONLY_TEST_FILES','RELEASE_TEST_FILES','ARTIFACT_TEST_FILES') if hasattr(t,k)}))"],
        cwd=REPO, capture_output=True, text=True, env={"PYTHONPATH": str(SCRIPTS), "PATH": "/usr/bin:/bin"},
    )
    return {
        "files": len(test_files),
        "loc": sum(t.count("\n") for t in texts.values()),
        "fixture_files": len(list((SCRIPTS / "tests" / "fixtures").rglob("*"))) if (SCRIPTS / "tests" / "fixtures").exists() else 0,
        "marks": sorted(marks.items(), key=lambda kv: (-kv[1], kv[0])),
        "profiles": json.loads(profiles.stdout) if profiles.returncode == 0 else {"error": profiles.stderr.strip()[-300:]},
        "_refs": refs,
    }


# --------------------------------------------------------------------------------------------
# CI, batch summaries, enrichment summaries, matrix


def ci(run_id: str) -> dict:
    try:
        raw = subprocess.run(
            ["gh", "run", "view", run_id, "--json", "jobs,headSha,conclusion,headBranch,createdAt,updatedAt"],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
    except Exception as exc:  # gh may be offline; the census records that rather than guessing
        return {"run_id": run_id, "error": str(exc)[:200]}
    data = json.loads(raw)
    from datetime import datetime

    def seconds(a: str, b: str) -> int:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return int((datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds())

    jobs = []
    for job in data["jobs"]:
        fast = next((s for s in job["steps"] if s["name"] == "Fast rung"), None)
        jobs.append({
            "name": job["name"],
            "conclusion": job["conclusion"],
            "job_seconds": seconds(job["startedAt"], job["completedAt"]),
            "fast_rung_seconds": seconds(fast["startedAt"], fast["completedAt"]) if fast else None,
        })
    jobs.sort(key=lambda j: j["name"])
    return {
        "run_id": run_id,
        "head_sha": data["headSha"],
        "branch": data["headBranch"],
        "conclusion": data["conclusion"],
        "wall_seconds": seconds(data["createdAt"], data["updatedAt"]),
        "jobs": jobs,
    }


STAMP = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")


def batch_summaries() -> list[dict]:
    from datetime import datetime

    def ts(line: str) -> datetime | None:
        m = STAMP.match(line)
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None

    out = []
    for path in sorted((SCRIPTS / "products" / "reports").glob("batch_run_summary_*.txt")):
        lines = path.read_text(errors="replace").splitlines()
        brands: list[dict] = []
        cur: dict | None = None
        stamps = [t for t in (ts(l) for l in lines) if t]
        for line in lines:
            t = ts(line)
            m = re.search(r"Raw data: (\S+)$", line)
            if m:
                cur = {"brand": m.group(1).rstrip("/").split("/")[-1], "_t": {}}
                brands.append(cur)
                continue
            if cur is None or t is None:
                continue
            marks = cur["_t"]
            if "STAGE 1: CLEANING" in line:
                marks["clean"] = t
            elif "STAGE 2: ENRICHMENT" in line:
                marks["enrich"] = t
            elif "STAGE 2.4" in line:
                marks["gates"] = t
            elif "STAGE 2.5" in line and "gates" not in marks:
                marks["gates"] = t
            elif "STAGE 3: SCORING" in line:
                marks["score"] = t
            elif "PIPELINE COMPLETE" in line:
                marks["end"] = t
            elif "__main__ - INFO - Total duration:" in line:
                cur["reported_total_s"] = float(re.search(r"Total duration: ([\d.]+)s", line).group(1))
            elif "__main__ - INFO - Duration:" in line and "enrich" in marks and "reported_enrich_s" not in cur:
                cur["reported_enrich_s"] = float(re.search(r"Duration: ([\d.]+)s", line).group(1))
            elif "__main__ - INFO - Total products:" in line and "products" not in cur:
                cur["products"] = int(re.search(r"Total products: (\d+)", line).group(1))
            elif "dsld_cleaner - INFO - Total duration:" in line:
                h, mi, s = re.search(r"Total duration: (\d+):(\d\d):([\d.]+)", line).groups()
                cur["reported_clean_s"] = int(h) * 3600 + int(mi) * 60 + float(s)
            elif re.search(r"__main__ - INFO - Success: (True|False)", line):
                cur["success"] = line.rstrip().endswith("True")
        rows = []
        for b in brands:
            m = b.pop("_t")
            order = [k for k in ("clean", "enrich", "gates", "score", "end") if k in m]
            for a, z in zip(order, order[1:]):
                b[f"{a}_wall_s"] = int((m[z] - m[a]).total_seconds())
            b["complete"] = "end" in m
            rows.append(b)

        def agg(key: str) -> dict | None:
            vals = [r[key] for r in rows if key in r]
            if not vals:
                return None
            return {"n": len(vals), "sum_s": round(sum(vals)), "median_s": round(statistics.median(vals), 1), "max_s": round(max(vals))}

        out.append({
            "file": str(path.relative_to(REPO)),
            "sha256": sha256(path),
            "wall_seconds": int((stamps[-1] - stamps[0]).total_seconds()) if stamps else None,
            "brands": len(rows),
            "complete": sum(r["complete"] for r in rows),
            "succeeded": sum(r.get("success") is True for r in rows),
            "products": sum(r.get("products", 0) for r in rows),
            "stage_wall": {k: agg(f"{k}_wall_s") for k in ("clean", "enrich", "gates", "score")},
            "reported": {k: agg(f"reported_{k}_s") for k in ("clean", "enrich", "total")},
            "slowest_brands": sorted(
                ({k: r.get(k) for k in ("brand", "products", "clean_wall_s", "enrich_wall_s", "gates_wall_s", "score_wall_s", "reported_total_s")}
                 for r in rows if "reported_total_s" in r),
                key=lambda r: -r["reported_total_s"],
            )[:8],
        })
    return out


def enrichment_summaries() -> dict:
    rows = []
    for path in sorted(SCRIPTS.glob("products/*_enriched/reports/enrichment_summary.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        info = data.get("processing_info") or {}
        stats = data.get("stats") or {}
        rows.append({
            "brand": path.parts[-3].replace("output_", "").replace("_enriched", ""),
            "duration_s": info.get("duration_seconds"),
            "products": stats.get("total_products"),
            "timestamp": info.get("timestamp"),
            "sha256": sha256(path),
        })
    timed = [r for r in rows if isinstance(r["duration_s"], (int, float)) and r["products"]]
    return {
        "brands": len(rows),
        "sum_duration_s": round(sum(r["duration_s"] for r in timed)),
        "sum_products": sum(r["products"] for r in timed),
        "median_seconds_per_product": round(statistics.median(r["duration_s"] / r["products"] for r in timed), 3) if timed else None,
        "oldest_timestamp": min((r["timestamp"] for r in rows if r["timestamp"]), default=None),
        "newest_timestamp": max((r["timestamp"] for r in rows if r["timestamp"]), default=None),
        "rows": rows,
    }


def matrix() -> dict:
    data = json.loads((SCRIPTS / "contracts" / "source_of_truth_matrix.json").read_text())
    per_owner = collections.defaultdict(list)
    for concept in data["concepts"]:
        owner = concept.get("owner")
        owner = owner if isinstance(owner, str) else json.dumps(owner)
        per_owner[owner.split("::")[0]].append(concept["concept_id"])
    return {
        "schema_version": data["_metadata"].get("schema_version"),
        "concepts": len(data["concepts"]),
        "required_concepts": len(data.get("required_concepts", [])),
        "per_owner": sorted(({"owner": k, "concepts": sorted(v)} for k, v in per_owner.items()), key=lambda r: (-len(r["concepts"]), r["owner"])),
    }


# --------------------------------------------------------------------------------------------
# promotion and output


def promote(modules: dict[str, dict], functions: list[dict], graph: dict, churn_per_file: dict, matrix_owners: dict) -> list[dict]:
    by_path_funcs = collections.defaultdict(list)
    for f in functions:
        by_path_funcs[f["path"]].append(f)
    rows = []
    for path, m in modules.items():
        name = module_name(path)
        reasons = []
        if m["loc"] > L2["loc"]:
            reasons.append(f"loc {m['loc']}")
        big = [f for f in by_path_funcs[path] if f["length"] > L2["func_len"] or f["nesting"] >= L2["nesting"]]
        if big:
            worst = max(big, key=lambda f: (f["length"], f["nesting"]))
            reasons.append(f"function {worst['name']} {worst['length']}L nesting {worst['nesting']}")
        if churn_per_file.get(path, 0) >= L2["churn"]:
            reasons.append(f"churn {churn_per_file[path]}")
        if name in graph["_cycle_members"]:
            reasons.append("lazy-import cycle member")
        if graph["_fan_in"].get(name, 0) >= L2["fan_in"]:
            reasons.append(f"fan-in {graph['_fan_in'][name]}")
        if graph["_fan_out"].get(name, 0) >= L2["fan_out"]:
            reasons.append(f"fan-out {graph['_fan_out'][name]}")
        if matrix_owners.get(path, 0) >= L2["concepts"]:
            reasons.append(f"owns {matrix_owners[path]} matrix concepts")
        if path in RELEASE_CHAIN or path.startswith("scripts/release_safety/"):
            reasons.append("release chain")
        if reasons:
            rows.append({"path": path, "reasons": reasons})
    return sorted(rows, key=lambda r: r["path"])


def build(expected_rev: str, run_id: str) -> dict:
    pinned = pin(expected_rev)
    production = sorted(f for f in git("ls-files", "scripts").splitlines() if is_production(f))
    shells = sorted(f for f in git("ls-files").splitlines() if f.endswith(".sh") and f.count("/") <= 1)
    trees: dict[str, ast.Module] = {}
    texts: dict[str, str] = {}
    modules: dict[str, dict] = {}
    functions: list[dict] = []
    known = {module_name(p) for p in production}
    edges: list[dict] = []
    for path in production:
        text = (REPO / path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        texts[path], trees[path] = text, tree
        metrics, funcs = module_metrics(path, tree, text)
        modules[path] = metrics
        functions.extend(funcs)
        edges.extend(import_edges(path, tree, text, known))
    graph = graph_summary(edges)
    for path, m in modules.items():
        name = module_name(path)
        m["fan_in"] = graph["_fan_in"].get(name, 0)
        m["fan_out"] = graph["_fan_out"].get(name, 0)
    churn_data = churn(pinned["head"], set(production))
    for path, m in modules.items():
        m["commits_since"] = churn_data["_per_file"].get(path, 0)
    tests = test_inventory(production, trees)
    for path, m in modules.items():
        m["test_files_referencing"] = tests["_refs"][path]
    matrix_data = matrix()
    matrix_owners = {row["owner"]: len(row["concepts"]) for row in matrix_data["per_owner"]}
    for path, m in modules.items():
        m["matrix_concepts_owned"] = matrix_owners.get(path, 0)
    level2 = promote(modules, functions, graph, churn_data["_per_file"], matrix_owners)
    for path, m in modules.items():
        m["tier"] = "L2" if any(r["path"] == path for r in level2) else "L1"
    shell_rows = []
    for path in shells:
        text = (REPO / path).read_text(errors="replace")
        shell_rows.append({"path": path, "loc": text.count("\n"), "commits_since": churn_data["_per_file"].get(path, 0),
                           "release_chain": path in RELEASE_CHAIN})
    layers = collections.Counter()
    for path, m in modules.items():
        top = path.split("/")[1]
        layers["core" if top.endswith(".py") or top == "scoring_v4" else top] += m["loc"]
    overview = {
        "production_modules": len(production),
        "production_loc": sum(m["loc"] for m in modules.values()),
        "loc_by_layer": sorted(layers.items(), key=lambda kv: (-kv[1], kv[0])),
        "functions": len(functions),
        "functions_over_150": sum(f["length"] > 150 for f in functions),
        "functions_over_300": sum(f["length"] > 300 for f in functions),
        "annotated_function_share": round(sum(f["annotated"] for f in functions) / len(functions), 3),
        "broad_excepts": sum(m["broad_excepts"] for m in modules.values()),
        "print_calls": sum(m["print_calls"] for m in modules.values()),
        "logger_calls": sum(m["logger_calls"] for m in modules.values()),
        "lazy_imports": sum(m["lazy_imports"] for m in modules.values()),
        "level2_modules": len(level2),
        "shell_entry_points": len(shell_rows),
    }
    functions_sorted = sorted(functions, key=lambda f: (-f["length"], f["path"], f["line"]))
    result = {
        "pin": pinned,
        "overview": overview,
        "modules": modules,
        "shell": shell_rows,
        "functions_over_150": [f for f in functions_sorted if f["length"] > 150],
        "deepest_functions": sorted(functions, key=lambda f: (-f["nesting"], -f["length"]))[:20],
        "imports": {k: v for k, v in graph.items() if not k.startswith("_")},
        "duplication": duplication(trees),
        "churn": {k: v for k, v in churn_data.items() if not k.startswith("_")},
        "tests": {k: v for k, v in tests.items() if not k.startswith("_")},
        "ci": ci(run_id),
        "pipeline_timing": {"batch_summaries": batch_summaries(), "enrichment_summaries": enrichment_summaries()},
        "matrix": matrix_data,
        "level2": level2,
    }
    return result


def render_markdown(c: dict) -> str:
    o = c["overview"]
    lines = [
        f"# Census at `{c['pin']['head'][:9]}`", "",
        f"Production modules {o['production_modules']}, LOC {o['production_loc']:,}; functions {o['functions']:,} "
        f"({o['functions_over_150']} over 150 lines, {o['functions_over_300']} over 300); annotated {o['annotated_function_share']:.0%}; "
        f"broad excepts {o['broad_excepts']}; print {o['print_calls']} vs logger {o['logger_calls']}; lazy imports {o['lazy_imports']}; "
        f"Level-2 modules {o['level2_modules']}.", "",
        "## LOC by layer", "", "| layer | LOC |", "|---|---|",
        *[f"| {k} | {v:,} |" for k, v in o["loc_by_layer"]], "",
        "## Largest modules", "", "| module | LOC | funcs | longest | max nesting | lazy | broad except | commits | tests ref | tier |", "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for path, m in sorted(c["modules"].items(), key=lambda kv: -kv[1]["loc"])[:40]:
        lf = m["longest_function"]
        longest = f"{lf['name']} {lf['length']}L" if lf else "-"
        lines.append(f"| {path.replace('scripts/', '')} | {m['loc']:,} | {m['functions']} | {longest} | {m['max_nesting']} | "
                     f"{m['lazy_imports']} | {m['broad_excepts']} | {m['commits_since']} | {m['test_files_referencing']} | {m['tier']} |")
    lines += ["", "## Longest functions", "", "| function | lines | nesting | params | nested defs | self.* | branches |", "|---|---|---|---|---|---|---|"]
    for f in c["functions_over_150"][:30]:
        lines.append(f"| {f['path'].replace('scripts/', '')}:{f['line']} {f['name']} | {f['length']} | {f['nesting']} | {f['params']} | {f['nested_defs']} | {f['self_attrs']} | {f['branches']} |")
    g = c["imports"]
    lines += ["", "## Import graph", "", f"Top-level edges {g['top_level_edges']}, lazy edges {g['lazy_edges']}; top-level cycles {len(g['cycles_top_level'])}; "
              f"cycles once lazy imports count {len(g['cycles_with_lazy'])} (sizes {[len(x) for x in g['cycles_with_lazy']]}).", "",
              "| fan-in (top-level importers) | n |", "|---|---|", *[f"| {m} | {n} |" for m, n in g["fan_in_top"][:15]], "",
              "| fan-out | n |", "|---|---|", *[f"| {m} | {n} |" for m, n in g["fan_out_top"][:10]], "",
              "### Cycle edges", "", "| importer | imports | line | in function | comment hint |", "|---|---|---|---|---|"]
    for e in g["cycle_edges"]:
        lines.append(f"| {e['src']} | {e['dst']} | {e['line']} | {e['in_function'] or 'module level'} | {'yes' if e['comment_hint'] else ''} |")
    d = c["duplication"]
    lines += ["", "## Duplication", "", f"Exact cross-file groups {d['exact_cross_file_groups']}; structural cross-file groups {d['structural_cross_file_groups']} "
              f"(~{d['structural_cross_file_duplicated_lines']} duplicated lines).", "", "| structural group | files | lines |", "|---|---|---|"]
    for grp in [x for x in d["structural_groups"] if x["files"] >= 2][:20]:
        names = " ; ".join(f"{m['path'].replace('scripts/', '')}:{m['line']} {m['name']}" for m in grp["members"][:4])
        lines.append(f"| {names} | {grp['files']} | {grp['length']} |")
    lines += ["", "| same-name private helper | files |", "|---|---|", *[f"| {r['name']} | {r['files']} |" for r in d["same_name_private_helpers"][:15]]]
    ch = c["churn"]
    lines += ["", f"## Churn since {ch['since']} ({ch['commits']} commits)", "", "| file | commits |", "|---|---|",
              *[f"| {f} | {n} |" for f, n in ch["production_top"][:25]], "",
              f"Co-change: {ch['cochange']['commits_touching_any']} commits touch the watched files; {ch['cochange']['touching_2_or_more']} touch ≥2 groups, "
              f"{ch['cochange']['touching_3_or_more']} touch ≥3 ({ch['cochange']['bulk_commits_skipped']} bulk commits skipped).", "",
              "| pair | commits |", "|---|---|", *[f"| {a} + {b} | {n} |" for (a, b), n in ch["cochange"]["pairs"]]]
    t = c["tests"]
    lines += ["", "## Tests", "", f"{t['files']} files, {t['loc']:,} LOC, {t['fixture_files']} fixture files; profiles {t['profiles']}; marks {dict(t['marks'][:6])}."]
    ci_data = c["ci"]
    if "jobs" in ci_data:
        lines += ["", f"## CI run {ci_data['run_id']} ({ci_data['branch']} {ci_data['head_sha'][:9]}, {ci_data['conclusion']}, wall {ci_data['wall_seconds']}s)", "",
                  "| job | fast rung s | job s |", "|---|---|---|", *[f"| {j['name']} | {j['fast_rung_seconds']} | {j['job_seconds']} |" for j in ci_data["jobs"]]]
    lines += ["", "## Pipeline timing (existing logs only)", ""]
    for b in c["pipeline_timing"]["batch_summaries"]:
        lines.append(f"- `{b['file']}`: {b['brands']} brands ({b['complete']} complete, {b['succeeded']} succeeded), wall {b['wall_seconds']}s, products {b['products']}, "
                     f"stage wall sums clean/enrich/gates/score = "
                     + "/".join(str((b['stage_wall'][k] or {}).get('sum_s')) for k in ('clean', 'enrich', 'gates', 'score')) + " s")
    es = c["pipeline_timing"]["enrichment_summaries"]
    lines.append(f"- enrichment_summary.json: {es['brands']} brands, {es['sum_products']} products in {es['sum_duration_s']} s, median {es['median_seconds_per_product']} s/product, "
                 f"timestamps {es['oldest_timestamp']} .. {es['newest_timestamp']}")
    lines += ["", "## Matrix owners", "", "| owner | concepts |", "|---|---|", *[f"| {r['owner']} | {len(r['concepts'])} |" for r in c["matrix"]["per_owner"]]]
    lines += ["", f"## Level-2 modules ({len(c['level2'])})", "", "| module | reasons |", "|---|---|", *[f"| {r['path']} | {'; '.join(r['reasons'])} |" for r in c["level2"]]]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------------
# reference check


REF = re.compile(r"`?((?:scripts/)?[\w/.-]+\.py)::([A-Za-z_][\w.]*)`?")
PATH = re.compile(r"(?<![\w/])((?:scripts|docs|\.claude|\.github)/[\w/.-]+\.(?:py|sh|json|md|yml))(?![\w/])")


def check_refs(audit_md: Path) -> int:
    text = audit_md.read_text()
    misses = []
    for path, symbol in sorted(set(REF.findall(text))):
        file = REPO / (path if path.startswith("scripts/") else f"scripts/{path}")
        if not file.exists():
            misses.append(f"missing file for {path}::{symbol}")
            continue
        source = file.read_text(errors="ignore")
        leaf = symbol.split(".")[-1]
        if not re.search(rf"^\s*(?:async\s+def|def|class)\s+{re.escape(leaf)}\b", source, re.M) \
                and not re.search(rf"^{re.escape(leaf)}\s*[:=]", source, re.M):
            misses.append(f"{path}::{symbol} not defined")
    for path in sorted(set(PATH.findall(text))):
        if not (REPO / path).exists():
            misses.append(f"missing path {path}")
    print(f"checked {len(set(REF.findall(text)))} symbol refs and {len(set(PATH.findall(text)))} paths; {len(misses)} misses")
    for m in misses:
        print("  ", m)
    return 1 if misses else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rev", default=PINNED_REV)
    parser.add_argument("--ci-run", default=CI_RUN_ID)
    parser.add_argument("--out-dir", default=str(HERE))
    parser.add_argument("--check-refs", metavar="AUDIT_MD")
    args = parser.parse_args()
    if args.check_refs:
        given = Path(args.check_refs)
        target = given if given.is_absolute() or given.exists() else HERE / given
        return check_refs(target)
    census = build(args.rev, args.ci_run)
    out = Path(args.out_dir)
    (out / "census.json").write_text(json.dumps(census, indent=1, sort_keys=True) + "\n")
    (out / "census.md").write_text(render_markdown(census))
    o = census["overview"]
    print(f"census.json written: {o['production_modules']} modules, {o['production_loc']:,} LOC, {o['level2_modules']} Level-2 modules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
