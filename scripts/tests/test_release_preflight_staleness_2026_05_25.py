"""Wave 6.Z release-hardening test: verify scripts/test.sh release prepends
an actionable staleness preflight check.

The preflight detects 4 stale-pipeline layers and emits a clear "fix:"
command for each, then exits non-zero. Layer 1 compares the content fingerprint
stamped by enrichment, so an iCloud/git mtime change cannot falsely block a
release; layers 2-4 retain their downstream artifact timestamp checks.

Tests use synthetic tmpdir layouts with controlled content and mtimes — no real
artifact is touched.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline_freshness import (
    REFERENCE_FINGERPRINT_KEY,
    enrichment_reference_fingerprint,
)
from stage_manifest import write_stage_manifest


def _stamp_reference_inputs(repo_dir: Path) -> None:
    fingerprint = enrichment_reference_fingerprint(repo_dir)
    for output in repo_dir.glob(
        "scripts/products/output_*_enriched/enriched/*.json"
    ):
        manifest = output.parent / ".stage_manifest.json"
        if manifest.exists():
            continue
        write_stage_manifest(
            output.parent,
            "enrich",
            [output],
            input_fingerprints={REFERENCE_FINGERPRINT_KEY: fingerprint},
        )


def _run_preflight(repo_dir: Path, flutter_dir: Path) -> tuple[int, str, str]:
    """Invoke the preflight logic (mirrors scripts/test.sh).
    Returns (exit_code, stdout, stderr)."""
    _stamp_reference_inputs(repo_dir)
    py = r'''
import sys, os, glob
from pathlib import Path

REPO = Path(os.environ.get("REPO_ROOT", "."))
FLUTTER = Path(os.environ.get("FLUTTER_REPO", "/Users/seancheick/PharmaGuide ai"))
sys.path.insert(0, os.environ["PIPELINE_SCRIPTS"])

from pipeline_freshness import enrichment_reference_freshness_issues

def newest(paths):
    mtimes = [Path(p).stat().st_mtime for p in paths if Path(p).exists()]
    return max(mtimes) if mtimes else 0

stale = []

enriched = glob.glob(str(REPO / "scripts/products/output_*_enriched/enriched/*.json"))
if enrichment_reference_freshness_issues(REPO):
    print("STALE: data_vs_enriched", file=sys.stderr)
    stale.append("data_vs_enriched")

scored = glob.glob(str(REPO / "scripts/products/output_*_scored/scored/*.json"))
if enriched and scored:
    if newest(enriched) > newest(scored):
        print("STALE: enriched_vs_scored", file=sys.stderr)
        stale.append("enriched_vs_scored")

catalog_db = REPO / "scripts/dist/pharmaguide_core.db"
if scored and catalog_db.exists():
    if newest(scored) > catalog_db.stat().st_mtime:
        print("STALE: scored_vs_dist", file=sys.stderr)
        stale.append("scored_vs_dist")

flutter_db = FLUTTER / "assets/db/pharmaguide_core.db"
if catalog_db.exists() and flutter_db.exists():
    if catalog_db.stat().st_mtime > flutter_db.stat().st_mtime:
        print("STALE: dist_vs_flutter", file=sys.stderr)
        stale.append("dist_vs_flutter")

if stale:
    sys.exit(1)
print("OK", file=sys.stderr)
sys.exit(0)
'''
    env = os.environ.copy()
    env["REPO_ROOT"] = str(repo_dir)
    env["FLUTTER_REPO"] = str(flutter_dir)
    env["PIPELINE_SCRIPTS"] = str(SCRIPTS_DIR)
    r = subprocess.run(
        [sys.executable, "-c", py],
        env=env, capture_output=True, text=True,
    )
    return r.returncode, r.stdout, r.stderr


def _touch(path: Path, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    os.utime(path, (mtime, mtime))


@pytest.fixture
def tmplayout(tmp_path):
    """Synthetic repo + Flutter layouts with controlled mtimes."""
    repo = tmp_path / "repo"
    flutter = tmp_path / "flutter"
    (repo / "scripts/data").mkdir(parents=True)
    (repo / "scripts/dist").mkdir(parents=True)
    (repo / "scripts/products/output_Test_enriched/enriched").mkdir(parents=True)
    (repo / "scripts/products/output_Test_scored/scored").mkdir(parents=True)
    (flutter / "assets/db").mkdir(parents=True)
    return repo, flutter


def test_all_in_sync_returns_zero(tmplayout):
    repo, flutter = tmplayout
    t = 1000000.0  # Jan 12 1970, anchor
    _touch(repo / "scripts/data/x.json", t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t + 10)
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t + 20)
    _touch(repo / "scripts/dist/pharmaguide_core.db", t + 30)
    _touch(flutter / "assets/db/pharmaguide_core.db", t + 40)
    code, _, err = _run_preflight(repo, flutter)
    assert code == 0, f"in-sync layout should pass; stderr:\n{err}"
    assert "OK" in err


def test_data_content_change_after_enrichment_flags_layer1(tmplayout):
    repo, flutter = tmplayout
    t = 1000000.0
    _touch(repo / "scripts/data/x.json", t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t)
    _stamp_reference_inputs(repo)
    _touch(repo / "scripts/data/x.json", t + 100)
    (repo / "scripts/data/x.json").write_text('{"changed": true}')
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t)
    _touch(repo / "scripts/dist/pharmaguide_core.db", t)
    _touch(flutter / "assets/db/pharmaguide_core.db", t)
    code, _, err = _run_preflight(repo, flutter)
    assert code == 1
    assert "data_vs_enriched" in err


def test_data_mtime_only_change_does_not_flag_layer1(tmplayout):
    repo, flutter = tmplayout
    t = 1000000.0
    data_file = repo / "scripts/data/x.json"
    _touch(data_file, t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t + 10)
    _stamp_reference_inputs(repo)
    os.utime(data_file, (t + 100, t + 100))
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t + 20)
    _touch(repo / "scripts/dist/pharmaguide_core.db", t + 30)
    _touch(flutter / "assets/db/pharmaguide_core.db", t + 40)

    code, _, err = _run_preflight(repo, flutter)

    assert code == 0, f"mtime-only changes must not look stale; stderr:\n{err}"


def test_enriched_newer_than_scored_flags_layer2(tmplayout):
    repo, flutter = tmplayout
    t = 1000000.0
    _touch(repo / "scripts/data/x.json", t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t + 100)
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t)  # older
    _touch(repo / "scripts/dist/pharmaguide_core.db", t + 200)
    _touch(flutter / "assets/db/pharmaguide_core.db", t + 200)
    code, _, err = _run_preflight(repo, flutter)
    assert code == 1
    assert "enriched_vs_scored" in err


def test_scored_newer_than_dist_flags_layer3(tmplayout):
    repo, flutter = tmplayout
    t = 1000000.0
    _touch(repo / "scripts/data/x.json", t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t + 10)
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t + 100)
    _touch(repo / "scripts/dist/pharmaguide_core.db", t)  # older
    _touch(flutter / "assets/db/pharmaguide_core.db", t)
    code, _, err = _run_preflight(repo, flutter)
    assert code == 1
    assert "scored_vs_dist" in err


def test_dist_newer_than_flutter_flags_layer4(tmplayout):
    repo, flutter = tmplayout
    t = 1000000.0
    _touch(repo / "scripts/data/x.json", t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t + 10)
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t + 20)
    _touch(repo / "scripts/dist/pharmaguide_core.db", t + 100)
    _touch(flutter / "assets/db/pharmaguide_core.db", t)  # older
    code, _, err = _run_preflight(repo, flutter)
    assert code == 1
    assert "dist_vs_flutter" in err


def test_multiple_stale_layers_reported_together(tmplayout):
    repo, flutter = tmplayout
    t = 1000000.0
    # Layers 1, 2, 3 all stale simultaneously
    _touch(repo / "scripts/data/x.json", t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t + 50)
    _stamp_reference_inputs(repo)
    (repo / "scripts/data/x.json").write_text('{"changed": true}')
    os.utime(repo / "scripts/data/x.json", (t + 100, t + 100))
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t)
    _touch(repo / "scripts/dist/pharmaguide_core.db", t)
    _touch(flutter / "assets/db/pharmaguide_core.db", t + 200)
    code, _, err = _run_preflight(repo, flutter)
    assert code == 1
    assert "data_vs_enriched" in err
    # Note: depending on values, enriched_vs_scored may or may not fire
    # because data_files newest > enriched newest doesn't mean enriched > scored.
    # Test layer 1 fires; broader detection covered by individual tests.


def test_missing_flutter_db_does_not_false_positive(tmplayout):
    """Layer 4 (dist vs flutter) only fires if BOTH files exist. A fresh
    checkout without Flutter mounted should pass."""
    repo, flutter = tmplayout
    t = 1000000.0
    _touch(repo / "scripts/data/x.json", t)
    _touch(repo / "scripts/products/output_Test_enriched/enriched/y.json", t + 10)
    _touch(repo / "scripts/products/output_Test_scored/scored/z.json", t + 20)
    _touch(repo / "scripts/dist/pharmaguide_core.db", t + 30)
    # No flutter db
    code, _, err = _run_preflight(repo, flutter)
    assert code == 0, f"should pass when Flutter db absent; stderr:\n{err}"


def test_skip_env_var_bypass_present_in_test_sh():
    """SKIP_STALENESS_CHECK=1 must bypass even when stale. This is the
    documented escape hatch for emergency releases. Verified at the
    source level — the function's first executable line must check
    the env var and early-return.

    (Behavioral test via 'source scripts/test.sh' isn't viable because
    sourcing re-enters the case dispatch and triggers pytest in a
    loop. The function's bypass logic is 3 lines and self-evident.)
    """
    text = (REPO_ROOT / "scripts/test.sh").read_text()
    # Locate the function body
    fn_start = text.find("release_preflight_staleness_check() {")
    assert fn_start >= 0, "preflight function missing from test.sh"
    fn_body = text[fn_start:fn_start + 800]
    # First executable check after the opening brace must be the SKIP guard
    assert 'SKIP_STALENESS_CHECK' in fn_body
    assert 'return 0' in fn_body
    # Ensure the SKIP check appears BEFORE the python heredoc that does
    # the actual staleness work (otherwise the bypass is too late).
    skip_idx = fn_body.find('SKIP_STALENESS_CHECK')
    py_idx = fn_body.find('<<\'PY\'')
    assert skip_idx < py_idx, (
        f"SKIP_STALENESS_CHECK must short-circuit BEFORE the Python heredoc. "
        f"Got skip_idx={skip_idx}, py_idx={py_idx}"
    )
