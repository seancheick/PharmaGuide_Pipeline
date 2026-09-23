"""No pipeline class or module defines the same function name twice.

A later ``def`` silently replaces the earlier one. On 2026-09-22 a new helper
reused an existing enricher method name; every product's enrichment raised
inside ``enrich_product`` and was recorded as ``enrichment_status: failed`` with
empty ingredients instead of stopping anything. This guard makes that class of
defect fail at test time.
"""
import ast
import collections
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
_ALLOWED_DECORATORS = {'setter', 'getter', 'deleter', 'overload', 'register'}


def _shadowed(tree):
    found = []
    scopes = [('<module>', tree.body)] + [(n.name, n.body) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for scope, body in scopes:
        names = collections.Counter()
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = {getattr(d, 'attr', getattr(d, 'id', None)) for d in node.decorator_list}
                # ``_`` is a deliberate throwaway for decorator registration.
                if not decorators & _ALLOWED_DECORATORS and node.name != '_':
                    names[node.name] += 1
        found += [(scope, name) for name, count in names.items() if count > 1]
    return found


def test_guard_detects_a_shadowed_method():
    source = 'class A:\n    def f(self, x): pass\n    def g(self): pass\n    def f(self): pass\n'
    assert _shadowed(ast.parse(source)) == [('A', 'f')]


def test_no_shadowed_definitions_in_pipeline_code():
    offenders = []
    for path in SCRIPTS.rglob('*.py'):
        if 'tests' in path.parts:
            continue
        offenders += [(str(path.relative_to(SCRIPTS)), scope, name)
                      for scope, name in _shadowed(ast.parse(path.read_text()))]
    assert not offenders, offenders


def test_enrichment_run_stops_when_products_fail_systemically(tmp_path, monkeypatch):
    # A systemic defect fails every product with the same caught exception;
    # the run must stop instead of publishing a 0% success rate.
    import json
    import pytest
    from enrich_supplements_v3 import SupplementEnricherV3
    enricher = SupplementEnricherV3()
    source = tmp_path / 'in'
    source.mkdir()
    (source / 'batch.json').write_text(json.dumps([{'id': '1'}]))
    monkeypatch.setattr(enricher, 'process_batch',
                        lambda *a, **k: {'total_products': 10, 'successful': 0, 'failed': 10, 'with_issues': 10})
    with pytest.raises(RuntimeError, match='enrichment success rate'):
        enricher.process_all(str(source), str(tmp_path / 'out'))
    monkeypatch.setattr(enricher, 'process_batch',
                        lambda *a, **k: {'total_products': 10, 'successful': 10, 'failed': 0, 'with_issues': 0})
    enricher.process_all(str(source), str(tmp_path / 'out2'))
