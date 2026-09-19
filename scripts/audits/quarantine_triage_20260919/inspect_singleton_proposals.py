#!/usr/bin/env python3
"""Read-only: print the triage proposal for each singleton conflict group."""
import re

md = open("reports/quarantine_triage_2026_09_19/PHASE3_TRIAGE.md").read()
TERMS = ["Germanium", "EpiCor", "Miroestrol", "Withaferin", "Silver",
         "Ginkgolic", "Litesse", "Maltodextrin", "7-KETO"]
for term in TERMS:
    for m in re.finditer(r"### (\d+) — (.+?)\n((?:- .*\n)+)", md):
        pid, name, body = m.groups()
        if term not in body:
            continue
        if term == "Maltodextrin" and "Powder" in name:
            continue
        f = dict(re.findall(r"- \*\*(\w+)\*\*: (.*)", body))
        print(f"[{term}] {pid} {name}")
        print(f"   gate:      {f.get('gate')}")
        print(f"   proposal:  {f.get('proposal')}")
        print(f"   rationale: {f.get('rationale')}")
        print(f"   risk:      {f.get('risk')}")
        break
