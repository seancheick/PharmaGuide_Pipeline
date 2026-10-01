"""D26 P-arm counterfactual (measurement only, never committed): remove the three
retained exposure stand-ins in a scratch detached worktree.

usage: counterfactual_patch.py <scratch worktree at the candidate commit>
"""
import sys

p = sys.argv[1] + "/scripts/scoring_v4/modules/generic_evidence.py"
s = open(p).read()
reps = [
    # floor + recovery stand-ins
    ('PRIMARY_MASS_FRACTION = _EM["primary_mass_fraction"]',
     'PRIMARY_MASS_FRACTION = 0.0  # D26 P-arm counterfactual (measurement only)'),
    # authority stand-in: any owner essential with its own (non-lent) amount
    ('''    best_row: Optional[Dict[str, Any]] = None
    best_cid: Optional[str] = None
    best_mass = 0.0
    for row in _competing_active_rows(product):
        if not isinstance(row, dict):
            continue
        canonical = str(row.get("canonical_id") or "").strip().lower()
        if owner_canonicals is not None and canonical not in owner_canonicals:
            continue
        mass = _mass_mg(row) or 0.0
        if mass > best_mass:
            best_mass = mass
            best_cid = canonical
            best_row = row
    if best_row is not None and is_lent_blend_mass(best_row):
        return None
    if best_mass > 0 and best_cid in DRI_ESSENTIAL_NUTRIENTS:
        return best_cid
    return None''',
     '''    # D26 P-arm counterfactual (measurement only): no mass-dominance check.
    best_cid: Optional[str] = None
    best_mass = 0.0
    for row in _competing_active_rows(product):
        if not isinstance(row, dict) or is_lent_blend_mass(row):
            continue
        canonical = str(row.get("canonical_id") or "").strip().lower()
        if owner_canonicals is not None and canonical not in owner_canonicals:
            continue
        if canonical not in DRI_ESSENTIAL_NUTRIENTS:
            continue
        mass = _mass_mg(row) or 0.0
        if mass > best_mass:
            best_mass = mass
            best_cid = canonical
    return best_cid if best_mass > 0 else None'''),
]
for a, b in reps:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(p, "w").write(s)
print("patched")
