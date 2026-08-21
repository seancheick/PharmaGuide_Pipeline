#!/usr/bin/env python3
"""Generate/check Flutter's products_core read projection from the export model."""

from __future__ import annotations

import argparse
from pathlib import Path

from core_export_model import APP_CORE_COLUMNS, build_projection_manifest


def render_dart_projection(*, export_schema_version: str) -> str:
    manifest = build_projection_manifest(
        export_schema_version=export_schema_version
    )
    columns = "\n".join(f"  '{column}'," for column in APP_CORE_COLUMNS)
    return f"""// GENERATED FILE — DO NOT EDIT.
// Source: PharmaGuide_Pipeline/scripts/core_export_model.py
// App projection for export schema {export_schema_version}.

const String appCoreProjectionModelVersion = '{manifest['model_version']}';
const String appCoreProjectionModelSha256 =
    '{manifest['model_sha256']}';
const Set<String> appCoreProjectionColumns = <String>{{
{columns}
}};
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-schema-version", default="2.4.0")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    expected = render_dart_projection(
        export_schema_version=args.export_schema_version
    )
    if args.check:
        if not args.output.exists() or args.output.read_text(
            encoding="utf-8"
        ) != expected:
            parser.error(
                f"{args.output} is stale; regenerate it from core_export_model.py"
            )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
