"""Preflight must fail closed for required or corrupt inputs (G2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import preflight


def _write_required_data(data_dir: Path, *, corrupt: str | None = None) -> None:
    data_dir.mkdir(parents=True)
    for filename, _description in preflight.CRITICAL_DATA_FILES:
        (data_dir / filename).write_text(
            "{" if filename == corrupt else json.dumps({"_metadata": {}}),
            encoding="utf-8",
        )


def test_quick_mode_blocks_corrupt_critical_json(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    _write_required_data(data_dir, corrupt="allergens.json")
    monkeypatch.setattr(preflight, "DATA_DIR", data_dir)

    result = preflight.run_preflight(quick=True)

    assert result["summary"]["json_valid"] is False
    assert result["summary"]["all_ok"] is False
    assert result["summary"]["exit_code"] == 1


def test_full_mode_blocks_missing_required_config_script_and_schema(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    scripts_dir = tmp_path / "scripts"
    _write_required_data(data_dir)
    config_dir.mkdir()
    scripts_dir.mkdir()
    monkeypatch.setattr(preflight, "DATA_DIR", data_dir)
    monkeypatch.setattr(preflight, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(preflight, "SCRIPTS_DIR", scripts_dir)
    monkeypatch.setattr(preflight, "IMPORTANT_DATA_FILES", [])
    monkeypatch.setattr(preflight, "OPTIONAL_DATA_FILES", [])
    monkeypatch.setattr(preflight, "validate_database_schema", lambda: {"ok": False})
    monkeypatch.setattr(preflight, "validate_iqm_br_collision", lambda: {"ok": True})

    result = preflight.run_preflight()

    assert result["summary"]["configs_ok"] is False
    assert result["summary"]["scripts_ok"] is False
    assert result["summary"]["schema_v5_ok"] is False
    assert result["summary"]["all_ok"] is False
    assert result["summary"]["exit_code"] == 1


def test_preflight_does_not_require_deleted_temporary_configs() -> None:
    assert all("tmp" not in filename for filename, _ in preflight.CONFIG_FILES)


def test_cleaning_config_uses_portable_stage_root() -> None:
    config = json.loads((preflight.CONFIG_DIR / "cleaning_config.json").read_text())

    assert not config["paths"]["input_directory"].startswith("/Users/")
    assert Path(config["paths"]["output_directory"]).name != "cleaned"
