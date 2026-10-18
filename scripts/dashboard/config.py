from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DashboardConfig:
    scan_dir: Path          # default: scripts/products/
    build_root: Path        # default: scripts/dist/
    dataset_root: Path | None = None
    flutter_repo: Path | None = None   # app checkout; default: $FLUTTER_REPO, else unset

def get_config() -> DashboardConfig:
    parser = argparse.ArgumentParser(description="PharmaGuide Dashboard Config")
    parser.add_argument("--scan-dir", type=str, default="scripts/products/", help="Directory to scan for pipeline reports")
    parser.add_argument("--build-root", type=str, default="scripts/dist/", help="Directory containing the final DB and manifest")
    parser.add_argument("--dataset-root", type=str, default=None, help="Optional specific dataset root")
    parser.add_argument(
        "--flutter-repo",
        type=str,
        default=os.environ.get("FLUTTER_REPO"),
        help="Flutter app checkout whose assets/reference_data the Clinical Copy view compares "
             "with pipeline data (default: $FLUTTER_REPO; unset leaves that comparison off)",
    )

    # Streamlit passes args after `--` in `streamlit run app.py -- --scan-dir=...`
    # However, if we just want to parse what's passed, we can handle both.
    # When running via `streamlit run`, sys.argv[0] is often `streamlit` or the script path.
    # To be safe, we parse everything after the script name if it exists.
    args, unknown = parser.parse_known_args()

    return DashboardConfig(
        scan_dir=Path(args.scan_dir).resolve(),
        build_root=Path(args.build_root).resolve(),
        dataset_root=Path(args.dataset_root).resolve() if args.dataset_root else None,
        flutter_repo=Path(args.flutter_repo).resolve() if args.flutter_repo else None,
    )

if __name__ == "__main__":
    # For quick testing: python3 scripts/dashboard/config.py
    print(get_config())
