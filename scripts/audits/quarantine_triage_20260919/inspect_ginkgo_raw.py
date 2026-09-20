#!/usr/bin/env python3
"""Read-only: raw quantity operators for the Ginkgo extract record (328464)."""
import sys

sys.path.insert(0, "scripts")
from dsld_api_client import DSLDApiClient, normalize_api_label  # noqa: E402

c = DSLDApiClient()
raw = normalize_api_label(c.fetch_label(328464))
for r in raw["ingredientRows"]:
    q = (r.get("quantity") or [{}])[0]
    print(
        r.get("name"), "| op:", q.get("operator"), "| qty:", q.get("quantity"),
        q.get("unit"), "| group:", r.get("ingredientGroup"),
        "| notes:", str(r.get("notes"))[:90],
    )
    for f in r.get("forms") or []:
        print("    form:", f.get("name"), "| prefix:", f.get("prefix"))
