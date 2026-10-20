#!/usr/bin/env python3
"""One structure card per Level-2 module and shell entry point, for the structural read.

A card is what the auditor reads before deciding whether a module needs the full ten-point
protocol: header line, size, classes with method counts, top-level functions (all of them for
small modules, the >100-line ones plus a prefix histogram for large ones), the production modules
it imports (top-level and lazy), and the modules that import it. Reuses census.py's graph code so
the two never disagree.

    $PG_PYTHON probes/structure_cards.py            # writes probes/cards.md from ../census.json
"""
from __future__ import annotations

import ast
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import census  # noqa: E402

REPO = census.REPO


def header_line(text: str, tree: ast.Module) -> str:
    doc = ast.get_docstring(tree)
    if doc:
        return doc.strip().splitlines()[0][:110]
    for line in text.splitlines()[:12]:
        if line.startswith("#") and not line.startswith("#!"):
            return line.lstrip("# ").strip()[:110] + " (comment)"
        if line.startswith(('"""', "'''")):
            return line.strip('"\' ')[:110] + " (bare string)"
    return "no docstring"


def py_card(path: str, importers: dict[str, list[str]], edges_by_src: dict[str, list[dict]]) -> list[str]:
    text = (REPO / path).read_text(errors="replace")
    tree = ast.parse(text)
    name = census.module_name(path)
    funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    loc = text.count("\n")
    out = [f"### {path.replace('scripts/', '')} — {loc:,} LOC", "", f"- header: {header_line(text, tree)}"]
    for c in classes:
        methods = [m for m in c.body if isinstance(m, ast.FunctionDef)]
        out.append(f"- class `{c.name}` L{c.lineno}-{c.end_lineno}: {len(methods)} methods"
                   + (f"; longest `{max(methods, key=lambda m: (m.end_lineno or 0) - m.lineno).name}`" if methods else ""))
    def length(n: ast.AST) -> int:
        return (n.end_lineno or n.lineno) - n.lineno + 1
    if len(funcs) <= 25:
        out.append("- functions: " + ", ".join(f"`{f.name}`({length(f)})" for f in funcs) if funcs else "- functions: none at module level")
    else:
        hist = collections.Counter(f.name.lstrip("_").split("_")[0] for f in funcs)
        out.append(f"- {len(funcs)} module-level functions; prefixes: " + ", ".join(f"{k} {v}" for k, v in hist.most_common(10)))
        big = [f for f in funcs if length(f) > 100]
        if big:
            out.append("- functions over 100 lines: " + ", ".join(f"`{f.name}`({length(f)}) L{f.lineno}" for f in sorted(big, key=length, reverse=True)))
    top = sorted({e["dst"] for e in edges_by_src.get(name, []) if not e["lazy"]})
    lazy = sorted({e["dst"] for e in edges_by_src.get(name, []) if e["lazy"]})
    out.append(f"- imports (top-level): {', '.join(top) or 'none from scripts/'}")
    if lazy:
        out.append(f"- imports (lazy, in functions): {', '.join(lazy)}")
    out.append(f"- imported by: {len(importers.get(name, []))}" + (f" — {', '.join(importers[name][:8])}{' …' if len(importers[name]) > 8 else ''}" if importers.get(name) else ""))
    out.append("")
    return out


def sh_card(path: str) -> list[str]:
    text = (REPO / path).read_text(errors="replace")
    funcs = re.findall(r"^(?:function\s+)?([A-Za-z_][\w]*)\s*\(\)\s*\{", text, re.M)
    pythons = re.findall(r"(?:\$PYTHON|\$PG_PYTHON|\"\$PG_PYTHON\"|python3?)\s+\"?\$?\{?[\w/]*\}?/?([\w/]+\.py)", text)
    steps = re.findall(r'^\s*(?:echo|log|step|info)\b[^"\']*["\']\s*(?:=+\s*)?(STEP[^"\']{0,60}|Step [^"\']{0,60}|\[[0-9]+/[0-9]+\][^"\']{0,60})', text, re.M)
    out = [f"### {path} — {text.count(chr(10)):,} LOC (shell)", "",
           f"- functions ({len(funcs)}): " + (", ".join(f"`{f}`" for f in funcs[:40]) or "none"),
           f"- python entry points invoked ({len(set(pythons))}): " + (", ".join(sorted(set(pythons))[:40]) or "none"),]
    if steps:
        out.append(f"- labelled steps ({len(steps)}): " + "; ".join(s.strip()[:50] for s in steps[:20]))
    out.append("")
    return out


def main() -> int:
    data = json.loads((HERE.parent / "census.json").read_text())
    production = sorted(data["modules"])
    known = {census.module_name(p) for p in production}
    edges = []
    for path in production:
        text = (REPO / path).read_text(encoding="utf-8", errors="replace")
        edges.extend(census.import_edges(path, ast.parse(text), text, known))
    edges_by_src = collections.defaultdict(list)
    importers = collections.defaultdict(list)
    for e in edges:
        edges_by_src[e["src"]].append(e)
        if e["src"] not in importers[e["dst"]]:
            importers[e["dst"]].append(e["src"])
    for v in importers.values():
        v.sort()
    lines = [f"# Structure cards — Level-2 modules at `{data['pin']['head'][:9]}`", "",
             "Generated by probes/structure_cards.py from census.json. One card per promoted module, plus every shell entry point.", ""]
    for row in data["level2"]:
        lines.append(f"<!-- reasons: {'; '.join(row['reasons'])} -->")
        lines += py_card(row["path"], importers, edges_by_src)
    lines += ["## Shell entry points", ""]
    for row in data["shell"]:
        lines += sh_card(row["path"])
    (HERE / "cards.md").write_text("\n".join(lines) + "\n")
    print(f"cards.md: {len(data['level2'])} module cards + {len(data['shell'])} shell cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
