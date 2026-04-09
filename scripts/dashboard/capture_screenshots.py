from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

DEFAULT_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
DEFAULT_OUTPUT = Path("docs/plans/dashboard-screenshots")
VIEW_SLUGS = [
    "product-inspector",
    "pipeline-health",
    "data-quality",
    "observability",
    "release-diff",
    "batch-diff",
    "intelligence",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture headless screenshots for each main dashboard view."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8599",
        help="Running dashboard URL. Default: %(default)s",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for PNG outputs. Default: %(default)s",
    )
    parser.add_argument(
        "--chrome-binary",
        type=Path,
        default=DEFAULT_CHROME,
        help="Path to Chrome or Chromium binary.",
    )
    parser.add_argument(
        "--window-size",
        default="1600,2600",
        help="Chrome window size as WIDTH,HEIGHT. Default: %(default)s",
    )
    return parser.parse_args()


def capture_view(chrome_binary: Path, base_url: str, output_dir: Path, window_size: str, view: str) -> None:
    screenshot_path = output_dir / f"{view}.png"
    user_data_dir = output_dir / f".chrome-profile-{view}"
    view_url = f"{base_url}/?view={urllib.parse.quote(view)}"
    cmd = [
        str(chrome_binary),
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--metrics-recording-only",
        "--no-first-run",
        "--disable-default-apps",
        "--hide-scrollbars",
        f"--user-data-dir={user_data_dir}",
        f"--window-size={window_size}",
        f"--screenshot={screenshot_path}",
        view_url,
    ]
    process = subprocess.Popen(cmd)
    deadline = time.time() + 30
    while time.time() < deadline:
        if screenshot_path.exists() and screenshot_path.stat().st_size > 0:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            return
        if process.poll() is not None:
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)
            if screenshot_path.exists() and screenshot_path.stat().st_size > 0:
                return
            raise RuntimeError(f"Chrome exited before writing screenshot: {view}")
        time.sleep(0.5)

    process.kill()
    process.wait(timeout=5)
    raise TimeoutError(f"Timed out waiting for screenshot: {view}")


def main() -> int:
    args = parse_args()
    if not args.chrome_binary.exists():
        print(f"Chrome binary not found: {args.chrome_binary}", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for view in VIEW_SLUGS:
        print(f"capturing {view}", flush=True)
        capture_view(args.chrome_binary, args.base_url.rstrip("/"), args.output_dir, args.window_size, view)
        print(f"captured {view}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
