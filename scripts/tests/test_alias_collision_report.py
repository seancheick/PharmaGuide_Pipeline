from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reports.alias_collision_report import (  # noqa: E402
    compute_alias_collision_report,
    main,
    render_markdown,
)


def test_report_detects_current_collision_classes() -> None:
    report = compute_alias_collision_report()

    assert report["summary"]["exact_alias_duplicates"] > 0
    assert report["summary"]["alias_vs_standard_collisions"] > 0
    assert report["summary"]["critical"] == 0

    labels = {item["label"] for item in report["alias_vs_standard_collisions"]}
    assert "cellulose gum" in labels
    assert "caramel color" in labels


def test_render_markdown_mentions_summary_and_known_label() -> None:
    report = compute_alias_collision_report()
    markdown = render_markdown(report)

    assert "# Alias Collision Report" in markdown
    assert "Exact alias duplicates" in markdown
    assert "Critical Alias-vs-Standard Collisions" in markdown
    assert "- None" in markdown
    assert "e967" in markdown


def test_report_severity_distinguishes_cross_db_overlap_from_same_db_ambiguity() -> None:
    report = compute_alias_collision_report()
    collisions = {item["label"]: item for item in report["alias_vs_standard_collisions"]}

    assert collisions["silicon dioxide"]["severity"] == "medium"
    assert collisions["shellac"]["severity"] == "medium"
    assert collisions["povidone"]["severity"] == "medium"
    assert "natural coloring" not in collisions


def test_cli_writes_deterministic_artifacts_and_fail_on_critical(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"

    rc = main(["--out", str(out_dir), "--prefix", "alias_test"])
    assert rc == 0

    json_path = out_dir / "alias_test.json"
    md_path = out_dir / "alias_test.md"
    assert json_path.exists()
    assert md_path.exists()

    first_json = json.loads(json_path.read_text(encoding="utf-8"))
    first_md = md_path.read_text(encoding="utf-8")

    rc_fail = main(["--out", str(out_dir), "--prefix", "alias_test", "--fail-on-critical"])
    assert rc_fail == 0

    second_json = json.loads(json_path.read_text(encoding="utf-8"))
    second_md = md_path.read_text(encoding="utf-8")

    assert first_json == second_json
    assert first_md == second_md
