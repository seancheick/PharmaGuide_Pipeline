#!/usr/bin/env python3
"""Six-brand shadow scoring comparison.

Runs the full pipeline (clean → enrich → score) on 200 products per brand,
then produces a comparative analysis report.
"""

import json
import os
import shutil
import subprocess
import sys
import random
import glob
from pathlib import Path
from collections import Counter

BRANDS = {
    "Thorne": "Thorne-2-17-26",
    "Nordic Naturals": "Nordic-Naturals-2-17-26-L511",
    "Garden of Life": "Garden-of-Life-2-17-26-L1132",
    "Nature Made": "Nature-Made-2-17-26-L827",
    "Olly": "Olly-2-17-26-L187",
    "Life Extension": "Life-Extension-2-17-26-L2052",
}

DATA_ROOT = "/Users/seancheick/Documents/DataSetDsld"
MAX_PER_BRAND = 200
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_DIR / "shadow_six_brand"


def sample_products(brand_dir: str, max_n: int) -> list:
    """Return up to max_n .json file paths from brand_dir."""
    all_files = sorted(glob.glob(os.path.join(brand_dir, "*.json")))
    if len(all_files) <= max_n:
        return all_files
    random.seed(42)  # Reproducible sampling
    return sorted(random.sample(all_files, max_n))


def copy_sample(brand_name: str, brand_folder: str) -> Path:
    """Copy sampled products into a working directory."""
    src_dir = os.path.join(DATA_ROOT, brand_folder)
    dest_dir = OUTPUT_ROOT / f"raw_{brand_name.replace(' ', '_')}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    files = sample_products(src_dir, MAX_PER_BRAND)
    for f in files:
        shutil.copy2(f, dest_dir / os.path.basename(f))

    print(f"  [{brand_name}] Copied {len(files)} products to {dest_dir}")
    return dest_dir


def run_pipeline(brand_name: str, raw_dir: Path) -> Path:
    """Run clean → enrich → score pipeline. Returns scored output dir."""
    tag = brand_name.replace(" ", "_")
    output_dir = OUTPUT_ROOT / f"output_{tag}"

    cmd = [
        sys.executable, str(SCRIPT_DIR / "run_pipeline.py"),
        "--raw-dir", str(raw_dir),
        "--output-prefix", str(output_dir),
    ]
    print(f"  [{brand_name}] Running pipeline...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  [{brand_name}] PIPELINE ERROR:")
        print(result.stderr[-500:] if result.stderr else "no stderr")
        return None

    # Pipeline creates: {output_prefix}_scored/scored/
    scored_dir = Path(str(output_dir) + "_scored") / "scored"
    if not scored_dir.exists():
        # Try alternate paths
        for candidate in [output_dir / "scored", Path(str(output_dir) + "_scored"), output_dir]:
            if candidate.exists() and list(candidate.glob("*.json")):
                scored_dir = candidate
                break

    print(f"  [{brand_name}] Pipeline complete → {scored_dir}")
    return scored_dir


def load_scored(scored_dir: Path) -> list:
    """Load all scored products from a directory."""
    products = []
    for f in sorted(scored_dir.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
            if isinstance(data, list):
                products.extend(data)
            else:
                products.append(data)
    return products


def analyze_brand(brand_name: str, products: list) -> dict:
    """Compute summary statistics for a brand."""
    n = len(products)
    if n == 0:
        return {"brand": brand_name, "n": 0}

    scores = [p.get("quality_score") or 0 for p in products]
    verdicts = Counter(p.get("verdict", "UNKNOWN") for p in products)
    grades = Counter(p.get("grade") or "N/A" for p in products)

    # Section averages
    section_sums = {"A": 0, "B": 0, "C": 0, "D": 0}
    for p in products:
        bd = p.get("breakdown", {})
        for sec in section_sums:
            sec_data = bd.get(sec, {})
            if isinstance(sec_data, dict):
                section_sums[sec] += sec_data.get("score", 0)
            elif isinstance(sec_data, (int, float)):
                section_sums[sec] += sec_data

    scored_products = [p for p in products if p.get("verdict") not in ("UNSAFE",)]
    scored_scores = [p.get("quality_score") or 0 for p in scored_products]

    return {
        "brand": brand_name,
        "n": n,
        "mean": round(sum(scores) / n, 2),
        "mean_excl_unsafe": round(sum(scored_scores) / max(len(scored_scores), 1), 2),
        "median": round(sorted(scores)[n // 2], 2),
        "min": round(min(scores), 2),
        "max": round(max(scores), 2),
        "std": round((sum((s - sum(scores)/n)**2 for s in scores) / n) ** 0.5, 2),
        "verdicts": dict(verdicts),
        "grades": dict(sorted(grades.items())),
        "section_avg": {
            sec: round(section_sums[sec] / n, 2)
            for sec in section_sums
        },
        "safe_pct": round(100 * verdicts.get("SAFE", 0) / n, 1),
        "unsafe_count": verdicts.get("UNSAFE", 0),
        "caution_count": verdicts.get("CAUTION", 0),
        "poor_count": verdicts.get("POOR", 0),
    }


def print_report(results: list):
    """Print comparative analysis."""
    print("\n" + "=" * 90)
    print("SIX-BRAND SHADOW SCORING COMPARISON")
    print("=" * 90)

    # Summary table
    print(f"\n{'Brand':<20} {'N':>4} {'Mean':>6} {'Mean*':>6} {'Med':>6} "
          f"{'Min':>5} {'Max':>5} {'SD':>5} {'SAFE%':>6} {'UNSAFE':>6} {'CAUT':>5} {'POOR':>5}")
    print("-" * 90)

    for r in sorted(results, key=lambda x: x.get("mean", 0), reverse=True):
        if r["n"] == 0:
            print(f"{r['brand']:<20} {'FAILED':>4}")
            continue
        print(f"{r['brand']:<20} {r['n']:>4} {r['mean']:>6.1f} {r['mean_excl_unsafe']:>6.1f} "
              f"{r['median']:>6.1f} {r['min']:>5.1f} {r['max']:>5.1f} {r['std']:>5.1f} "
              f"{r['safe_pct']:>5.1f}% {r['unsafe_count']:>6} {r['caution_count']:>5} {r['poor_count']:>5}")

    print(f"\n* Mean* = mean excluding UNSAFE products (score=0)")

    # Section breakdown
    print(f"\n{'Brand':<20} {'A/25':>7} {'B/30':>7} {'C/20':>7} {'D/5':>7} {'Total':>7}")
    print("-" * 60)
    for r in sorted(results, key=lambda x: x.get("mean", 0), reverse=True):
        if r["n"] == 0:
            continue
        sa = r["section_avg"]
        total = sum(sa.values())
        print(f"{r['brand']:<20} {sa['A']:>7.2f} {sa['B']:>7.2f} {sa['C']:>7.2f} {sa['D']:>7.2f} {total:>7.2f}")

    # Verdict distribution
    print(f"\n{'Brand':<20} {'SAFE':>6} {'POOR':>6} {'CAUTION':>8} {'UNSAFE':>7} {'NOT_SCORED':>11}")
    print("-" * 65)
    for r in sorted(results, key=lambda x: x.get("safe_pct", 0), reverse=True):
        if r["n"] == 0:
            continue
        v = r["verdicts"]
        print(f"{r['brand']:<20} {v.get('SAFE',0):>6} {v.get('POOR',0):>6} "
              f"{v.get('CAUTION',0):>8} {v.get('UNSAFE',0):>7} {v.get('NOT_SCORED',0):>11}")

    # Grade distribution
    print(f"\n{'Brand':<20} {'Exceptional':>12} {'Excellent':>10} {'Good':>6} {'Fair':>6} "
          f"{'Below Avg':>10} {'Low':>5} {'V.Poor':>7}")
    print("-" * 85)
    for r in sorted(results, key=lambda x: x.get("mean", 0), reverse=True):
        if r["n"] == 0:
            continue
        g = r["grades"]
        print(f"{r['brand']:<20} {g.get('Exceptional',0):>12} {g.get('Excellent',0):>10} "
              f"{g.get('Good',0):>6} {g.get('Fair',0):>6} {g.get('Below Average',0):>10} "
              f"{g.get('Low',0):>5} {g.get('Very Poor',0):>7}")

    print("\n" + "=" * 90)


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = []

    for brand_name, brand_folder in BRANDS.items():
        print(f"\n{'='*60}")
        print(f"Processing: {brand_name}")
        print(f"{'='*60}")

        raw_dir = copy_sample(brand_name, brand_folder)
        scored_dir = run_pipeline(brand_name, raw_dir)

        if scored_dir and scored_dir.exists():
            products = load_scored(scored_dir)
            stats = analyze_brand(brand_name, products)
            results.append(stats)
            print(f"  [{brand_name}] {stats['n']} products scored, mean={stats['mean']}")
        else:
            results.append({"brand": brand_name, "n": 0})
            print(f"  [{brand_name}] FAILED — no scored output")

    # Print comparative report
    print_report(results)

    # Save results JSON
    report_path = OUTPUT_ROOT / "shadow_comparison_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
