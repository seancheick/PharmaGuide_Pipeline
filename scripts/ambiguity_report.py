#!/usr/bin/env python3
"""
Ambiguity Report Generator
==========================
Scans enriched outputs and flags ambiguous ingredient matches based on
quality map alias collisions at the same precedence level.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'β-(glucan|carotene|sitosterol|alanine|hydroxy|cryptoxanthin)',
                  r'beta-\1', text)
    text = re.sub(r'\bβ\b', 'beta', text)
    text = re.sub(r'β glucan', 'beta glucan', text)
    text = re.sub(r'µg\b', 'mcg', text)
    text = re.sub(r'µgram', 'mcgram', text)
    text = re.sub(r'[—–]', '-', text)
    text = re.sub(r'\s*/\s*', ' ', text)
    text = re.sub(r'[,\u00B7]', ' ', text)
    text = re.sub(r'[™®©]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def find_matching_alias(
    ing_norm: str,
    std_norm: str,
    target_name: str,
    aliases: List[str],
) -> Tuple[Optional[str], int]:
    target_norm = normalize_text(target_name)
    if ing_norm == target_norm or std_norm == target_norm:
        return target_name, len(target_norm)
    for alias in aliases:
        alias_norm = normalize_text(alias)
        if ing_norm == alias_norm or std_norm == alias_norm:
            return alias, len(alias_norm)
    return None, 0


def build_alias_index(quality_map: Dict) -> Dict[str, List[Dict]]:
    alias_index: Dict[str, List[Dict]] = {}
    for parent_key, parent_data in quality_map.items():
        if parent_key.startswith("_") or not isinstance(parent_data, dict):
            continue
        forms = parent_data.get("forms", {})
        parent_std_name = parent_data.get("standard_name", "")
        parent_aliases = parent_data.get("aliases", [])

        for form_name, form_data in forms.items():
            form_aliases = form_data.get("aliases", [])
            form_candidates = [form_name] + list(form_aliases)
            for alias in form_candidates:
                alias_norm = normalize_text(alias)
                if not alias_norm:
                    continue
                alias_index.setdefault(alias_norm, []).append({
                    "parent_key": parent_key,
                    "form_name": form_name,
                    "matched_alias": alias,
                    "precedence": 1,
                    "alias_length": len(alias_norm),
                })

        parent_candidates = [parent_std_name] + list(parent_aliases)
        for alias in parent_candidates:
            alias_norm = normalize_text(alias)
            if not alias_norm:
                continue
            alias_index.setdefault(alias_norm, []).append({
                "parent_key": parent_key,
                "form_name": None,
                "matched_alias": alias,
                "precedence": 2,
                "alias_length": len(alias_norm),
            })
    return alias_index


def collect_candidates(
    ing_name: str,
    std_name: str,
    alias_index: Dict[str, List[Dict]],
) -> List[Tuple[int, int, str, Dict]]:
    ing_norm = normalize_text(ing_name)
    std_norm = normalize_text(std_name)
    candidates = []

    for key in {ing_norm, std_norm}:
        if not key:
            continue
        for match in alias_index.get(key, []):
            candidates.append((
                match["precedence"],
                -match["alias_length"],
                match["parent_key"],
                match,
            ))

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    return candidates


def load_enriched_products(paths: List[Path]) -> List[Dict]:
    products: List[Dict] = []
    for path in paths:
        if path.is_file():
            with open(path, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                products.extend(data)
            else:
                products.append(data)
        elif path.is_dir():
            for file_path in sorted(path.glob("*.json")):
                with open(file_path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    products.extend(data)
                else:
                    products.append(data)
    return products


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ambiguity report from enriched outputs")
    parser.add_argument("--input", "-i", action="append", required=True,
                        help="Enriched file or directory (can be provided multiple times)")
    parser.add_argument("--output", "-o", default="reports/ambiguity_report.json",
                        help="Output JSON report path")
    parser.add_argument("--quality-map", default="data/ingredient_quality_map.json",
                        help="Path to ingredient_quality_map.json")

    args = parser.parse_args()

    inputs = [Path(p) for p in args.input]
    products = load_enriched_products(inputs)
    if not products:
        print("No enriched products found.")
        return 1

    with open(args.quality_map, "r") as f:
        quality_map = json.load(f)
    alias_index = build_alias_index(quality_map)

    ambiguous = {}
    raw_samples = {}

    for product in products:
        quality = product.get("ingredient_quality_data", {})
        for ing in quality.get("ingredients_scorable", []):
            ing_name = ing.get("name", "")
            std_name = ing.get("standard_name", ing_name)
            candidates = collect_candidates(ing_name, std_name, alias_index)
            if not candidates:
                continue
            best = candidates[0]
            same = [c for c in candidates if c[0] == best[0] and c[1] == best[1]]
            parent_keys = sorted({c[3]["parent_key"] for c in same})
            if len(parent_keys) <= 1:
                continue

            norm_key = normalize_text(ing_name)
            entry = ambiguous.setdefault(norm_key, {
                "normalized_input": norm_key,
                "candidates": [],
                "winner": best[3]["parent_key"],
                "precedence": best[3]["precedence"],
                "alias_length": best[3]["alias_length"],
                "count": 0,
            })
            entry["count"] += 1
            entry["candidates"] = [{
                "parent_key": c[3]["parent_key"],
                "form_name": c[3]["form_name"],
                "matched_alias": c[3]["matched_alias"],
                "precedence": c[3]["precedence"],
                "alias_length": c[3]["alias_length"],
            } for c in same]

            samples = raw_samples.setdefault(norm_key, set())
            if len(samples) < 5 and ing_name:
                samples.add(ing_name)

    report = {
        "total_ambiguous": len(ambiguous),
        "by_frequency": sorted(
            [{**v, "raw_samples": sorted(raw_samples.get(k, []))}
             for k, v in ambiguous.items()],
            key=lambda x: (-x["count"], x["normalized_input"])
        ),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote ambiguity report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
