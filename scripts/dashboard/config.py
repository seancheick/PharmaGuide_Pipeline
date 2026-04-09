from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DashboardConfig:
    scan_dir: Path          # default: scripts/products/
    build_root: Path        # default: scripts/final_db_output/
    dataset_root: Path | None = None

def get_config() -> DashboardConfig:
    parser = argparse.ArgumentParser(description="PharmaGuide Dashboard Config")
    parser.add_argument("--scan-dir", type=str, default="scripts/products/", help="Directory to scan for pipeline reports")
    parser.add_argument("--build-root", type=str, default="scripts/final_db_output/", help="Directory containing the final DB and manifest")
    parser.add_argument("--dataset-root", type=str, default=None, help="Optional specific dataset root")

    # Streamlit passes args after `--` in `streamlit run app.py -- --scan-dir=...`
    # However, if we just want to parse what's passed, we can handle both.
    # When running via `streamlit run`, sys.argv[0] is often `streamlit` or the script path.
    # To be safe, we parse everything after the script name if it exists.
    args, unknown = parser.parse_known_args()

    return DashboardConfig(
        scan_dir=Path(args.scan_dir).resolve(),
        build_root=Path(args.build_root).resolve(),
        dataset_root=Path(args.dataset_root).resolve() if args.dataset_root else None
    )

if __name__ == "__main__":
    # For quick testing: python3 scripts/dashboard/config.py
    print(get_config())
