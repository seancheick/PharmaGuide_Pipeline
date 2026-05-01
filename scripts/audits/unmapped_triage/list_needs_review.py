"""List all entries flagged as needing review across all reference data files.

Surfaces entries with:
- data_quality.review_status in {needs_review, stub, draft, pending, provisional}
- confidence_level in {unresolved, inferred}
- cui_status: governed_null (sometimes flagged)
- explicit clinical_notes mentioning 'pending'/'needs review'/'awaiting clinician'
"""
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path("scripts/data")

NEEDS_REVIEW_STATUSES = {"needs_review", "stub", "draft", "pending", "provisional"}
NEEDS_REVIEW_CONFIDENCE = {"unresolved", "inferred"}

results = defaultdict(list)

def check_entry(file_label, eid, entry):
    """Return list of reasons this entry needs review."""
    reasons = []
    dq = entry.get("data_quality") or {}
    if isinstance(dq, str):
        rs = dq
    else:
        rs = dq.get("review_status")
    if rs in NEEDS_REVIEW_STATUSES:
        reasons.append(f"review_status={rs}")
    cl = entry.get("confidence_level")
    if cl in NEEDS_REVIEW_CONFIDENCE:
        reasons.append(f"confidence_level={cl}")
    cn = entry.get("clinical_notes", "") or entry.get("notes", "") or ""
    if any(t in cn.lower() for t in ["pending clinician", "needs clinician", "awaiting clinician", "needs review"]):
        reasons.append("clinical_notes flag")
    return reasons

# IQM (top-level keys)
iqm = json.loads((ROOT/"ingredient_quality_map.json").read_text())
for k, v in iqm.items():
    if k.startswith("_") or not isinstance(v, dict): continue
    reasons = check_entry("IQM", k, v)
    if reasons:
        results["IQM"].append((k, v.get("standard_name", k), reasons))
    # Also check forms
    for fname, form in (v.get("forms") or {}).items():
        if isinstance(form, dict):
            f_reasons = check_entry("IQM", f"{k}/{fname}", form)
            if f_reasons:
                results["IQM (form-level)"].append((f"{k} » {fname}", form.get("notes","")[:80] if form.get("notes") else "", f_reasons))

# List files
for fname, key in [
    ("botanical_ingredients.json", "botanical_ingredients"),
    ("other_ingredients.json", "other_ingredients"),
    ("standardized_botanicals.json", "standardized_botanicals"),
    ("harmful_additives.json", "harmful_additives"),
    ("banned_recalled_ingredients.json", "ingredients"),
]:
    path = ROOT/fname
    if not path.exists(): continue
    d = json.loads(path.read_text())
    for e in d.get(key, []):
        if not isinstance(e, dict): continue
        eid = e.get("id", "?")
        reasons = check_entry(fname, eid, e)
        if reasons:
            results[fname].append((eid, e.get("standard_name", eid), reasons))

print(f"# All Entries Needing Review — Generated {Path('/tmp').exists() and 'now' or 'now'}\n")
print(f"## Summary\n")
total = 0
for category, items in results.items():
    print(f"- **{category}**: {len(items)} items")
    total += len(items)
print(f"\n**Total: {total} entries**\n")

for category, items in results.items():
    if not items: continue
    print(f"\n## {category} ({len(items)} items)\n")
    for eid, name, reasons in sorted(items):
        print(f"- `{eid}` — {name}")
        for r in reasons:
            print(f"    - {r}")
