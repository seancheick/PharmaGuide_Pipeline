"""
Phase 0 — IQM Alias Audit: Identity vs Bioactivity Split

Scans scripts/data/ingredient_quality_map.json for source-botanical names
registered as aliases under marker canonicals (vitamin_c, curcumin, sulforaphane,
capsaicin, lycopene, quercetin, aescin, resveratrol). Categorizes each offending
alias as MOVE / QUALIFY / DELETE and produces:

  - REPORT.md                       human-readable summary
  - proposed_alias_migration.json   machine-readable migration plan

Read-only. Does not modify ingredient_quality_map.json.

Run: python3 scripts/audits/identity_bioactivity_split/run_audit.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
IQM_PATH = REPO_ROOT / "scripts" / "data" / "ingredient_quality_map.json"
BOTANICAL_INGREDIENTS_PATH = REPO_ROOT / "scripts" / "data" / "botanical_ingredients.json"
STANDARDIZED_BOTANICALS_PATH = REPO_ROOT / "scripts" / "data" / "standardized_botanicals.json"
PRODUCTS_ROOT = REPO_ROOT / "scripts" / "products"
OUTPUT_DIR = REPO_ROOT / "scripts" / "audits" / "identity_bioactivity_split"
REPORT_PATH = OUTPUT_DIR / "REPORT.md"
MIGRATION_PATH = OUTPUT_DIR / "proposed_alias_migration.json"

# 8 marker IQM canonicals carrying source-botanical aliases.
MARKER_CANONICALS = [
    "vitamin_c",
    "curcumin",
    "sulforaphane",
    "capsaicin",
    "lycopene",
    "quercetin",
    "aescin",
    "resveratrol",
]

# Source-botanical detection patterns.
# Each tuple: (botanical_canonical_id, source_db, detection_regex)
# detection_regex matches the source botanical name in a form_name or alias string.
SOURCE_BOTANICAL_PATTERNS = [
    ("acerola_cherry", "botanical_ingredients", re.compile(r"\bacerola\b", re.I)),
    ("camu_camu", "standardized_botanicals", re.compile(r"\bcamu[\s_-]?camu\b", re.I)),
    ("turmeric", "botanical_ingredients", re.compile(r"\bturmeric\b|\bcurcuma\s+longa\b", re.I)),
    ("broccoli_sprout", "MISSING_NEEDS_CREATION", re.compile(r"\bbroccoli\s+sprout|\bbroccoli\s+seed|\bbrassica\s+oleracea\b", re.I)),
    ("tomato", "botanical_ingredients", re.compile(r"\btomato\b|\bsolanum\s+lycopersicum\b", re.I)),
    ("cayenne_pepper", "botanical_ingredients", re.compile(r"\bcayenne\b|\bcapsicum(?!\s+chinense|\s+frutescens)\b|\bred\s+pepper\b", re.I)),
    ("sophora_japonica", "botanical_ingredients", re.compile(r"\bsophora\s+japonica\b|\bjapanese\s+pagoda\s+tree\b", re.I)),
    ("horse_chestnut_seed", "botanical_ingredients", re.compile(r"\bhorse\s*chestnut\b|\baesculus\s+hippocastanum\b", re.I)),
    ("japanese_knotweed", "botanical_ingredients", re.compile(r"\bpolygonum\s+cuspidatum\b|\bjapanese\s+knotweed\b|\bfallopia\s+japonica\b", re.I)),
]

# Standardization predicates: if present in form_name/alias, categorize as QUALIFY
# (keep under marker but require label to declare standardization).
STANDARDIZATION_PATTERNS = re.compile(
    r"\b\d+\s*%|\bstd\.?\b|\bstandardi[sz]ed\b|\bcurcuminoid|\bsulforaphane\b(?=.*\b(?:std|standardi|content|mg|%))|"
    r"\bcontaining\b|\bextract\s+\d+\s*[:x]\b|\bmin\.?\s+\d+\s*%",
    re.I,
)


def load_iqm() -> dict:
    with IQM_PATH.open() as f:
        return json.load(f)


def load_botanical_canonicals() -> dict[str, str]:
    """Returns mapping of botanical_id -> source_db file basename for existence check."""
    botanicals: dict[str, str] = {}
    with BOTANICAL_INGREDIENTS_PATH.open() as f:
        for entry in json.load(f).get("botanical_ingredients", []):
            botanicals[entry["id"]] = "botanical_ingredients"
    with STANDARDIZED_BOTANICALS_PATH.open() as f:
        for entry in json.load(f).get("standardized_botanicals", []):
            botanicals.setdefault(entry["id"], "standardized_botanicals")
    return botanicals


def detect_source_botanical(text: str) -> tuple[str, str] | None:
    """Return (botanical_canonical_id, source_db) if text matches a source botanical, else None."""
    for botanical_id, source_db, pattern in SOURCE_BOTANICAL_PATTERNS:
        if pattern.search(text):
            return botanical_id, source_db
    return None


def categorize(text: str, has_standardization: bool, botanical_id: str | None) -> str:
    """MOVE / QUALIFY / DELETE."""
    if botanical_id is None:
        return "KEEP"  # not a source botanical at all — leave alone
    if has_standardization:
        return "QUALIFY"
    return "MOVE"


def has_standardization_predicate(text: str) -> bool:
    return bool(STANDARDIZATION_PATTERNS.search(text))


def count_corpus_hits(needles: set[str]) -> dict[str, int]:
    """Scan enriched products for ingredient strings matching each needle (case-insensitive substring)."""
    counts: dict[str, int] = defaultdict(int)
    if not PRODUCTS_ROOT.exists():
        return dict(counts)

    needle_patterns = {n: re.compile(re.escape(n), re.I) for n in needles}

    # Enriched files live at scripts/products/output_<vendor>_enriched/enriched/enriched_*.json
    enriched_files = list(PRODUCTS_ROOT.glob("**/enriched/enriched_*.json"))
    for fpath in enriched_files:
        try:
            with fpath.open() as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        # Each file is a list of product records
        records = data if isinstance(data, list) else [data]
        for rec in records:
            if not isinstance(rec, dict):
                continue
            iqd = rec.get("ingredient_quality_data", {}) or {}
            ingredients = iqd.get("ingredients", []) if isinstance(iqd, dict) else []
            for ing in ingredients or []:
                if not isinstance(ing, dict):
                    continue
                blob = " ".join(
                    str(ing.get(k, "") or "")
                    for k in (
                        "name",
                        "raw_source_text",
                        "standard_name",
                        "matched_form",
                        "matched_alias",
                        "canonical_id",
                        "original_label",
                    )
                ).lower()
                for needle, pat in needle_patterns.items():
                    if pat.search(blob):
                        counts[needle] += 1
    return dict(counts)


def audit() -> dict:
    iqm = load_iqm()
    botanical_canonicals = load_botanical_canonicals()

    findings: list[dict] = []
    needles: set[str] = set()

    for marker in MARKER_CANONICALS:
        entry = iqm.get(marker)
        if not entry:
            continue
        forms = entry.get("forms") or {}
        if not isinstance(forms, dict):
            continue

        for form_name, form_data in forms.items():
            form_aliases = list(form_data.get("aliases", []) or [])
            # We audit BOTH the form_name itself AND each alias under it.
            candidates: list[tuple[str, str]] = [(form_name, "form_name")]
            for a in form_aliases:
                candidates.append((a, "alias"))

            # Group by form so the migration plan can rewrite forms[] atomically.
            for text, source_field in candidates:
                if not isinstance(text, str) or not text.strip():
                    continue
                hit = detect_source_botanical(text)
                if hit is None:
                    continue
                botanical_id, expected_source_db = hit
                has_std = has_standardization_predicate(text)
                # Special rule: form_name itself never gets QUALIFY (form_name IS the form identity);
                # if the form_name is bare botanical and form_data has no standardization predicate
                # at the form-data level, MOVE the entire form to botanical canonical.
                category = categorize(text, has_std, botanical_id)

                # Check botanical canonical existence
                botanical_exists = botanical_id in botanical_canonicals
                source_db_actual = botanical_canonicals.get(botanical_id, expected_source_db)

                findings.append(
                    {
                        "marker_canonical": marker,
                        "form_name": form_name,
                        "source_field": source_field,
                        "offending_text": text,
                        "has_standardization_predicate": has_std,
                        "detected_botanical": botanical_id,
                        "botanical_canonical_exists": botanical_exists,
                        "botanical_source_db": source_db_actual,
                        "category": category,
                        "form_bio_score": form_data.get("bio_score"),
                    }
                )
                needles.add(text.lower())

    # Corpus hit counts
    corpus_counts = count_corpus_hits(needles)
    for f in findings:
        f["corpus_hits"] = corpus_counts.get(f["offending_text"].lower(), 0)

    # Build proposed migration JSON
    migration: dict = {
        "_metadata": {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_iqm_schema": iqm.get("_metadata", {}).get("schema_version"),
            "audit_script": "scripts/audits/identity_bioactivity_split/run_audit.py",
            "total_findings": len(findings),
        },
        "migrations": [],
    }
    for f in findings:
        action_target: dict
        if f["category"] == "MOVE":
            action_target = {
                "action": "MOVE",
                "to_canonical_id": f["detected_botanical"],
                "to_source_db": f["botanical_source_db"],
                "needs_new_botanical_entry": not f["botanical_canonical_exists"],
            }
        elif f["category"] == "QUALIFY":
            action_target = {
                "action": "QUALIFY",
                "keep_under_marker": f["marker_canonical"],
                "requires_predicate": "standardization_keyword_or_pct",
                "implementation_note": "Cleaner must require standardization keyword/pct in nearby label text before resolving this alias to marker canonical.",
            }
        else:
            action_target = {"action": "KEEP_UNCHANGED"}

        migration["migrations"].append(
            {
                "marker_canonical": f["marker_canonical"],
                "form_name": f["form_name"],
                "source_field": f["source_field"],
                "offending_text": f["offending_text"],
                "category": f["category"],
                "corpus_hits": f["corpus_hits"],
                "form_bio_score": f["form_bio_score"],
                **action_target,
            }
        )

    return {
        "findings": findings,
        "migration": migration,
        "botanical_canonicals_known": botanical_canonicals,
    }


def write_report(audit_result: dict) -> None:
    findings = audit_result["findings"]
    migration = audit_result["migration"]
    known_botanicals = audit_result["botanical_canonicals_known"]

    by_marker: dict[str, list] = defaultdict(list)
    for f in findings:
        by_marker[f["marker_canonical"]].append(f)

    by_action: dict[str, list] = defaultdict(list)
    for f in findings:
        by_action[f["category"]].append(f)

    lines: list[str] = []
    lines.append("# Phase 0 — IQM Alias Audit Report")
    lines.append("")
    lines.append(f"_Generated: {migration['_metadata']['generated_at']}_")
    lines.append(f"_Source IQM schema: {migration['_metadata']['source_iqm_schema']}_")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total offending entries detected:** {len(findings)}")
    lines.append(f"- **Categorized MOVE:** {len(by_action['MOVE'])}")
    lines.append(f"- **Categorized QUALIFY:** {len(by_action['QUALIFY'])}")
    lines.append(f"- **Categorized DELETE:** {len(by_action['DELETE'])}")
    lines.append("")
    lines.append("### Per-marker breakdown")
    lines.append("")
    lines.append("| Marker Canonical | # Form Entries | # Aliases | Total Hits |")
    lines.append("| --- | --- | --- | --- |")
    for m in MARKER_CANONICALS:
        items = by_marker.get(m, [])
        forms_count = sum(1 for it in items if it["source_field"] == "form_name")
        aliases_count = sum(1 for it in items if it["source_field"] == "alias")
        lines.append(f"| `{m}` | {forms_count} | {aliases_count} | {len(items)} |")
    lines.append("")
    lines.append("### Botanical canonical home check")
    lines.append("")
    target_botanicals = sorted({bot for bot, _, _ in SOURCE_BOTANICAL_PATTERNS})
    lines.append("| Botanical Canonical | Exists? | Source DB |")
    lines.append("| --- | --- | --- |")
    for bot in target_botanicals:
        exists = bot in known_botanicals
        src = known_botanicals.get(bot, "**MUST CREATE**")
        lines.append(f"| `{bot}` | {'✅' if exists else '❌'} | {src} |")
    lines.append("")
    lines.append("## Detailed Findings (by marker)")
    lines.append("")
    for m in MARKER_CANONICALS:
        items = by_marker.get(m, [])
        if not items:
            continue
        lines.append(f"### `{m}` ({len(items)} entries)")
        lines.append("")
        lines.append("| Form | Field | Offending Text | Detected Botanical | Std? | Category | Corpus Hits |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for it in items:
            std_marker = "Y" if it["has_standardization_predicate"] else "—"
            lines.append(
                f"| `{it['form_name']}` "
                f"| {it['source_field']} "
                f"| `{it['offending_text']}` "
                f"| `{it['detected_botanical']}` "
                f"| {std_marker} "
                f"| **{it['category']}** "
                f"| {it['corpus_hits']} |"
            )
        lines.append("")
    lines.append("## Categorization Rules")
    lines.append("")
    lines.append("- **MOVE** — Source botanical name with no standardization predicate. Relocate alias to source botanical's own `aliases[]` in `botanical_ingredients.json` or `standardized_botanicals.json`. Remove from marker IQM forms.")
    lines.append("- **QUALIFY** — Source botanical name with standardization keyword/percentage. Keep under marker IQM but cleaner must require standardization predicate in nearby label text to resolve to marker.")
    lines.append("- **DELETE** — Wrong altogether (e.g., a vague generic term that should not alias anywhere). Reserved for manual review entries.")
    lines.append("- **KEEP_UNCHANGED** — Not a source botanical at all. No action needed.")
    lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    lines.append("1. Phase 1 — populate `scripts/data/botanical_marker_contributions.json` with USDA FDC / PubMed cited default contributions for detected botanicals.")
    lines.append("2. Phase 2 — execute `proposed_alias_migration.json`:")
    lines.append("   - MOVE entries: relocate aliases out of IQM into botanical canonicals.")
    lines.append("   - QUALIFY entries: rewrite cleaner to require standardization predicate.")
    lines.append("   - Pre-create any botanical canonical marked `needs_new_botanical_entry: true`.")
    lines.append("3. Bump IQM `_metadata.schema_version` to 5.4.0; archive 5.3.0 snapshot.")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = audit()
    write_report(result)
    MIGRATION_PATH.write_text(json.dumps(result["migration"], indent=2))

    print(f"=== Audit complete ===")
    print(f"Findings:    {len(result['findings'])}")
    by_action: dict[str, int] = defaultdict(int)
    for f in result["findings"]:
        by_action[f["category"]] += 1
    for k, v in sorted(by_action.items()):
        print(f"  {k:8s}: {v}")
    print(f"Report:      {REPORT_PATH}")
    print(f"Migration:   {MIGRATION_PATH}")


if __name__ == "__main__":
    main()
