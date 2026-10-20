"""Batch C: integrator-audit leftovers in records batches A/B already touched (no determination change).

F1 chitosan studied_dose_exposure: the Cochrane review gives no dose.
F2 applicability thresholds no cited study sets -> the studied daily regimen; SDE in one basis.
F3 applicability_status "applicable_reviewed_trials" left on records now unestablished or pending.
"""
D = "__DELETE__"
UNEST = "applicability_unestablished"

SPEC = {
    "chitosan": {"record": {"studied_dose_exposure": {}}},
    "coleus_forskohlii_root": {"record": {
        "studied_dose_exposure": {"values": [500], "unit": "mg", "basis": "daily_intake"},
        "applicability_decision": "250 mg of a 10% forskolin root extract twice daily (500 mg/day) for 12 weeks decreased body fat percentage and fat mass versus placebo in 30 overweight and obese men; lean body mass only trended up."}},
    "nad": {"record": {
        "studied_dose_exposure": {"values": [1000], "unit": "mg", "basis": "daily_intake"},
        "applicability_decision": "500 mg nicotinamide riboside twice daily (1,000 mg/day) for 6 weeks raised PBMC NAD+ about 60% versus placebo in a crossover trial of 30 healthy middle-aged and older adults."}},
    "cayenne_pepper": {"record": {"applicability_decision": "A meta-analysis of capsaicinoid trials reports that at least 2 mg capsaicinoids taken before a meal was needed to reduce ad libitum energy intake; a respiration-chamber study gave 2.56 mg capsaicin per meal. Crude ground pepper without a capsaicinoid declaration does not establish that exposure."}},
    "capsaicin": {"record": {"applicability_decision": "In a 36-hour respiration-chamber study in negative energy balance, 2.56 mg capsaicin with every meal counteracted the fall in diet-induced thermogenesis and resting energy expenditure and raised fat oxidation; no daily dose threshold is established."}},
    "atp": {"record": {
        "studied_dose_exposure": {"values": [400], "unit": "mg", "basis": "daily_intake"},
        "applicability_decision": "400 mg/day disodium ATP for 2 weeks prevented post-exercise falls in ATP and muscle excitability and raised later-bout Wingate peak power in 42 healthy men."}},
    "activated_charcoal": {"record": {
        "studied_dose_exposure": {},
        "applicability_decision": "In a double-blind trial in 99 adults (US and India), activated charcoal lowered breath hydrogen and bloating and cramp symptoms after lactulose versus placebo; the abstract gives no dose."}},
    "milk_basic_protein": {"record": {
        "studied_dose_exposure": {"values": [40], "unit": "mg", "basis": "daily_intake"},
        "applicability_decision": "40 mg/day milk basic protein for 6 months raised lumbar (L2-L4) BMD versus placebo in 35 healthy young women."}},
    "mastic_gum": {"record": {"applicability_decision": "Chios mastic gum 350 mg three times daily (1,050 mg/day) for 3 weeks improved functional dyspepsia symptoms versus placebo in 148 patients (77% vs 40% marked improvement)."}},
    **{c: {"record": {"applicability_status": UNEST}} for c in (
        "olive_fruit_extract", "black_garlic", "superoxide_dismutase", "schisandra",
        "shiitake_mushroom", "fucoxanthin", "perilla_oil", "undecylenic_acid")},
}
