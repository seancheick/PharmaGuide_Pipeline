"""Exercise real Streamlit caches, isolated from dashboard UI mocks."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("scenario", [
    "replacement", "expiry", "creation", "promotion", "during_read",
    "rollback", "reuse", "close", "close_on_failure", "unstable", "manifest",
])
def test_dashboard_catalog_cache_and_connection_lifetime(tmp_path, scenario):
    script = r'''
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.runtime.caching import cache_utils
from scripts.dashboard import data_loader as loader
from scripts.dashboard.config import DashboardConfig

root, scenario = Path(sys.argv[1]), sys.argv[2]
scan, build = root / 'scan', root / 'build'
scan.mkdir()
build.mkdir()
config = DashboardConfig(scan_dir=scan, build_root=build)
clock = [1000.0]
cache_utils.TTLCACHE_TIMER = lambda: clock[0]

def write_catalog(directory, score):
    directory.mkdir(exist_ok=True)
    with sqlite3.connect(directory / 'pharmaguide_core.db') as conn:
        conn.execute('CREATE TABLE products_core (quality_score_status TEXT, '
                     'product_safety_status TEXT, quality_score_v4_100 REAL, '
                     'mapped_coverage REAL, v4_config_fingerprint TEXT)')
        conn.execute("INSERT INTO products_core VALUES ('scored', 'no_known_catalog_concern', ?, 1, NULL)", (score,))
    conn.close()
    (directory / 'export_manifest.json').write_text(json.dumps({'product_count': 1, 'test_score': score}))
    (directory / 'detail_index.json').write_text('{}')

opened = []
original_connect = sqlite3.connect
class TrackedConnection(sqlite3.Connection):
    closed = False
    def close(self):
        self.closed = True
        super().close()
def connect(*args, **kwargs):
    conn = original_connect(*args, **kwargs, factory=TrackedConnection)
    opened.append(conn)
    return conn

if scenario != 'creation':
    write_catalog(build, 10)
candidate = root / 'candidate'
write_catalog(candidate, 90)

def load():
    return loader.load_dashboard_data(config)

with patch.object(loader.sqlite3, 'connect', connect):
    if scenario == 'close_on_failure':
        with patch.object(loader, '_load_scoring_config_snapshot', side_effect=ValueError('probe')):
            try:
                load()
            except ValueError as exc:
                assert str(exc) == 'probe'
            else:
                raise AssertionError('expected load failure')
        assert opened and all(conn.closed for conn in opened), 'failed load leaked a SQLite connection'
    elif scenario in ('during_read', 'unstable'):
        original_json = loader.safe_load_json
        promoted = []
        def read_and_promote(path):
            value = original_json(path)
            if path == build / 'export_manifest.json':
                if scenario == 'unstable':
                    promoted.append(True)
                    path.write_text(json.dumps({'test_score': len(promoted)}))
                elif not promoted:
                    promoted.append(True)
                    os.replace(build, root / 'old')
                    os.replace(candidate, build)
            return value
        with patch.object(loader, 'safe_load_json', read_and_promote):
            if scenario == 'unstable':
                try:
                    load()
                except RuntimeError as exc:
                    assert 'changed repeatedly' in str(exc)
                else:
                    raise AssertionError('returned a changing catalog')
                assert len(opened) == 3, 'promotion retries must be bounded'
            else:
                result = load()
                assert result.export_manifest['test_score'] == 90, 'returned mixed/retired catalog snapshot'
                assert result.shared_metrics['average_score'] == 90
        assert all(conn.closed for conn in opened)
    else:
        first = load()
        if scenario == 'close':
            assert opened and all(conn.closed for conn in opened), 'cached data retained a live SQLite connection'
        elif scenario == 'reuse':
            count = len(opened)
            assert load() is first
            assert len(opened) == count, 'unchanged catalog reopened its database'
        elif scenario == 'manifest':
            os.replace(candidate / 'export_manifest.json', build / 'export_manifest.json')
            result = load()
            assert result.export_manifest['test_score'] == 90
            assert result.shared_metrics['average_score'] == 10
        else:
            if scenario in ('promotion', 'rollback', 'creation'):
                os.replace(build, root / 'old')
                os.replace(candidate, build)
            else:
                os.replace(candidate / 'pharmaguide_core.db', build / 'pharmaguide_core.db')
                os.replace(candidate / 'export_manifest.json', build / 'export_manifest.json')
            if scenario == 'expiry':
                clock[0] += 301
            result = load()
            assert result.shared_metrics['average_score'] == 90, 'catalog replacement reused retired database data'
            assert result.export_manifest['test_score'] == 90
            if scenario == 'rollback':
                os.replace(build, root / 'rejected')
                os.replace(root / 'old', build)
                restored = load()
                assert restored.shared_metrics['average_score'] == 10
                assert restored.export_manifest['test_score'] == 10
st.cache_resource.clear()
'''
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), scenario],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
