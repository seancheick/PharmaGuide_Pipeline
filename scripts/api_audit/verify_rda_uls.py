#!/usr/bin/env python3
"""
RDA / AI / UL verification tool for PharmaGuide rda_optimal_uls.json.

Verifies the nutrient recommendations in rda_optimal_uls.json against
authoritative DRI (Dietary Reference Intake) values from the National
Academies of Sciences, Engineering, and Medicine (2023-2024 tables).

Additionally uses the USDA FoodData Central API to validate nutrient
name-to-ID mappings for cross-reference integrity.

Usage:
    # Verify all entries (dry-run, report only)
    python3 scripts/api_audit/verify_rda_uls.py

    # Verify a single nutrient
    python3 scripts/api_audit/verify_rda_uls.py --nutrient "Vitamin A"

    # Apply safe fixes (unit normalization, highest_ul corrections)
    python3 scripts/api_audit/verify_rda_uls.py --apply

    # Validate nutrient names against USDA FoodData Central API
    python3 scripts/api_audit/verify_rda_uls.py --usda-check

Environment:
    USDA_API_KEY or FDC_API_KEY — required only for --usda-check
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import env_loader  # noqa: F401

# ---------------------------------------------------------------------------
# Authoritative DRI Reference Table
# Source: National Academies DRI Tables (2023-2024 consolidated)
# https://nap.nationalacademies.org/resource/dri-tables/
#
# Each entry: {unit, groups: {(sex, age_range): (rda_or_ai, ul)}}
# rda_or_ai: RDA value (or AI if no RDA established, marked with *)
# ul: Tolerable Upper Intake Level (None = not established)
#
# Groups follow the same structure as rda_optimal_uls.json:
#   Male/Female 14-18, 19-30, 31-50, 51-70, 71+
#   Pregnancy/Lactation 14-18, 19-30, 31-50
# ---------------------------------------------------------------------------

DRI_REFERENCE = {
    "Vitamin A": {
        "unit": "mcg RAE",
        "groups": {
            ("Male", "14-18"): (900, 2800),
            ("Male", "19-30"): (900, 3000),
            ("Male", "31-50"): (900, 3000),
            ("Male", "51-70"): (900, 3000),
            ("Male", "71+"): (900, 3000),
            ("Female", "14-18"): (700, 2800),
            ("Female", "19-30"): (700, 3000),
            ("Female", "31-50"): (700, 3000),
            ("Female", "51-70"): (700, 3000),
            ("Female", "71+"): (700, 3000),
            ("Pregnancy", "14-18"): (750, 2800),
            ("Pregnancy", "19-30"): (770, 3000),
            ("Pregnancy", "31-50"): (770, 3000),
            ("Lactation", "14-18"): (1200, 2800),
            ("Lactation", "19-30"): (1300, 3000),
            ("Lactation", "31-50"): (1300, 3000),
        },
    },
    "Vitamin C": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (75, 1800),
            ("Male", "19-30"): (90, 2000),
            ("Male", "31-50"): (90, 2000),
            ("Male", "51-70"): (90, 2000),
            ("Male", "71+"): (90, 2000),
            ("Female", "14-18"): (65, 1800),
            ("Female", "19-30"): (75, 2000),
            ("Female", "31-50"): (75, 2000),
            ("Female", "51-70"): (75, 2000),
            ("Female", "71+"): (75, 2000),
            ("Pregnancy", "14-18"): (80, 1800),
            ("Pregnancy", "19-30"): (85, 2000),
            ("Pregnancy", "31-50"): (85, 2000),
            ("Lactation", "14-18"): (115, 1800),
            ("Lactation", "19-30"): (120, 2000),
            ("Lactation", "31-50"): (120, 2000),
        },
    },
    "Vitamin D": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (15, 100),
            ("Male", "19-30"): (15, 100),
            ("Male", "31-50"): (15, 100),
            ("Male", "51-70"): (15, 100),
            ("Male", "71+"): (20, 100),
            ("Female", "14-18"): (15, 100),
            ("Female", "19-30"): (15, 100),
            ("Female", "31-50"): (15, 100),
            ("Female", "51-70"): (15, 100),
            ("Female", "71+"): (20, 100),
            ("Pregnancy", "14-18"): (15, 100),
            ("Pregnancy", "19-30"): (15, 100),
            ("Pregnancy", "31-50"): (15, 100),
            ("Lactation", "14-18"): (15, 100),
            ("Lactation", "19-30"): (15, 100),
            ("Lactation", "31-50"): (15, 100),
        },
    },
    "Vitamin E": {
        "unit": "mg",  # alpha-tocopherol
        "groups": {
            ("Male", "14-18"): (15, 800),
            ("Male", "19-30"): (15, 1000),
            ("Male", "31-50"): (15, 1000),
            ("Male", "51-70"): (15, 1000),
            ("Male", "71+"): (15, 1000),
            ("Female", "14-18"): (15, 800),
            ("Female", "19-30"): (15, 1000),
            ("Female", "31-50"): (15, 1000),
            ("Female", "51-70"): (15, 1000),
            ("Female", "71+"): (15, 1000),
            ("Pregnancy", "14-18"): (15, 800),
            ("Pregnancy", "19-30"): (15, 1000),
            ("Pregnancy", "31-50"): (15, 1000),
            ("Lactation", "14-18"): (19, 800),
            ("Lactation", "19-30"): (19, 1000),
            ("Lactation", "31-50"): (19, 1000),
        },
    },
    "Vitamin K": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (75, None),
            ("Male", "19-30"): (120, None),
            ("Male", "31-50"): (120, None),
            ("Male", "51-70"): (120, None),
            ("Male", "71+"): (120, None),
            ("Female", "14-18"): (75, None),
            ("Female", "19-30"): (90, None),
            ("Female", "31-50"): (90, None),
            ("Female", "51-70"): (90, None),
            ("Female", "71+"): (90, None),
            ("Pregnancy", "14-18"): (75, None),
            ("Pregnancy", "19-30"): (90, None),
            ("Pregnancy", "31-50"): (90, None),
            ("Lactation", "14-18"): (75, None),
            ("Lactation", "19-30"): (90, None),
            ("Lactation", "31-50"): (90, None),
        },
    },
    "Thiamin": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (1.2, None),
            ("Male", "19-30"): (1.2, None),
            ("Male", "31-50"): (1.2, None),
            ("Male", "51-70"): (1.2, None),
            ("Male", "71+"): (1.2, None),
            ("Female", "14-18"): (1.0, None),
            ("Female", "19-30"): (1.1, None),
            ("Female", "31-50"): (1.1, None),
            ("Female", "51-70"): (1.1, None),
            ("Female", "71+"): (1.1, None),
            ("Pregnancy", "14-18"): (1.4, None),
            ("Pregnancy", "19-30"): (1.4, None),
            ("Pregnancy", "31-50"): (1.4, None),
            ("Lactation", "14-18"): (1.4, None),
            ("Lactation", "19-30"): (1.4, None),
            ("Lactation", "31-50"): (1.4, None),
        },
    },
    "Riboflavin": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (1.3, None),
            ("Male", "19-30"): (1.3, None),
            ("Male", "31-50"): (1.3, None),
            ("Male", "51-70"): (1.3, None),
            ("Male", "71+"): (1.3, None),
            ("Female", "14-18"): (1.0, None),
            ("Female", "19-30"): (1.1, None),
            ("Female", "31-50"): (1.1, None),
            ("Female", "51-70"): (1.1, None),
            ("Female", "71+"): (1.1, None),
            ("Pregnancy", "14-18"): (1.4, None),
            ("Pregnancy", "19-30"): (1.4, None),
            ("Pregnancy", "31-50"): (1.4, None),
            ("Lactation", "14-18"): (1.6, None),
            ("Lactation", "19-30"): (1.6, None),
            ("Lactation", "31-50"): (1.6, None),
        },
    },
    "Niacin": {
        "unit": "mg NE",
        "groups": {
            ("Male", "14-18"): (16, 30),
            ("Male", "19-30"): (16, 35),
            ("Male", "31-50"): (16, 35),
            ("Male", "51-70"): (16, 35),
            ("Male", "71+"): (16, 35),
            ("Female", "14-18"): (14, 30),
            ("Female", "19-30"): (14, 35),
            ("Female", "31-50"): (14, 35),
            ("Female", "51-70"): (14, 35),
            ("Female", "71+"): (14, 35),
            ("Pregnancy", "14-18"): (18, 30),
            ("Pregnancy", "19-30"): (18, 35),
            ("Pregnancy", "31-50"): (18, 35),
            ("Lactation", "14-18"): (17, 30),
            ("Lactation", "19-30"): (17, 35),
            ("Lactation", "31-50"): (17, 35),
        },
    },
    "Vitamin B6": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (1.3, 80),
            ("Male", "19-30"): (1.3, 100),
            ("Male", "31-50"): (1.3, 100),
            ("Male", "51-70"): (1.7, 100),
            ("Male", "71+"): (1.7, 100),
            ("Female", "14-18"): (1.2, 80),
            ("Female", "19-30"): (1.3, 100),
            ("Female", "31-50"): (1.3, 100),
            ("Female", "51-70"): (1.5, 100),
            ("Female", "71+"): (1.5, 100),
            ("Pregnancy", "14-18"): (1.9, 80),
            ("Pregnancy", "19-30"): (1.9, 100),
            ("Pregnancy", "31-50"): (1.9, 100),
            ("Lactation", "14-18"): (2.0, 80),
            ("Lactation", "19-30"): (2.0, 100),
            ("Lactation", "31-50"): (2.0, 100),
        },
    },
    "Folate": {
        "unit": "mcg DFE",
        # UL stored as DFE equivalents because the pipeline converts folic acid → DFE
        # before UL comparison. Authoritative UL: 1000 mcg folic acid × 1.667 = 1667 DFE
        # (14-18: 800 mcg folic acid × 1.667 = 1334 DFE)
        "groups": {
            ("Male", "14-18"): (400, 1334),
            ("Male", "19-30"): (400, 1667),
            ("Male", "31-50"): (400, 1667),
            ("Male", "51-70"): (400, 1667),
            ("Male", "71+"): (400, 1667),
            ("Female", "14-18"): (400, 1334),
            ("Female", "19-30"): (400, 1667),
            ("Female", "31-50"): (400, 1667),
            ("Female", "51-70"): (400, 1667),
            ("Female", "71+"): (400, 1667),
            ("Pregnancy", "14-18"): (600, 1334),
            ("Pregnancy", "19-30"): (600, 1667),
            ("Pregnancy", "31-50"): (600, 1667),
            ("Lactation", "14-18"): (500, 1334),
            ("Lactation", "19-30"): (500, 1667),
            ("Lactation", "31-50"): (500, 1667),
        },
    },
    "Vitamin B12": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (2.4, None),
            ("Male", "19-30"): (2.4, None),
            ("Male", "31-50"): (2.4, None),
            ("Male", "51-70"): (2.4, None),
            ("Male", "71+"): (2.4, None),
            ("Female", "14-18"): (2.4, None),
            ("Female", "19-30"): (2.4, None),
            ("Female", "31-50"): (2.4, None),
            ("Female", "51-70"): (2.4, None),
            ("Female", "71+"): (2.4, None),
            ("Pregnancy", "14-18"): (2.6, None),
            ("Pregnancy", "19-30"): (2.6, None),
            ("Pregnancy", "31-50"): (2.6, None),
            ("Lactation", "14-18"): (2.8, None),
            ("Lactation", "19-30"): (2.8, None),
            ("Lactation", "31-50"): (2.8, None),
        },
    },
    "Biotin": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (25, None),
            ("Male", "19-30"): (30, None),
            ("Male", "31-50"): (30, None),
            ("Male", "51-70"): (30, None),
            ("Male", "71+"): (30, None),
            ("Female", "14-18"): (25, None),
            ("Female", "19-30"): (30, None),
            ("Female", "31-50"): (30, None),
            ("Female", "51-70"): (30, None),
            ("Female", "71+"): (30, None),
            ("Pregnancy", "14-18"): (30, None),
            ("Pregnancy", "19-30"): (30, None),
            ("Pregnancy", "31-50"): (30, None),
            ("Lactation", "14-18"): (35, None),
            ("Lactation", "19-30"): (35, None),
            ("Lactation", "31-50"): (35, None),
        },
    },
    "Pantothenic Acid": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (5, None),
            ("Male", "19-30"): (5, None),
            ("Male", "31-50"): (5, None),
            ("Male", "51-70"): (5, None),
            ("Male", "71+"): (5, None),
            ("Female", "14-18"): (5, None),
            ("Female", "19-30"): (5, None),
            ("Female", "31-50"): (5, None),
            ("Female", "51-70"): (5, None),
            ("Female", "71+"): (5, None),
            ("Pregnancy", "14-18"): (6, None),
            ("Pregnancy", "19-30"): (6, None),
            ("Pregnancy", "31-50"): (6, None),
            ("Lactation", "14-18"): (7, None),
            ("Lactation", "19-30"): (7, None),
            ("Lactation", "31-50"): (7, None),
        },
    },
    "Choline": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (550, 3000),
            ("Male", "19-30"): (550, 3500),
            ("Male", "31-50"): (550, 3500),
            ("Male", "51-70"): (550, 3500),
            ("Male", "71+"): (550, 3500),
            ("Female", "14-18"): (400, 3000),
            ("Female", "19-30"): (425, 3500),
            ("Female", "31-50"): (425, 3500),
            ("Female", "51-70"): (425, 3500),
            ("Female", "71+"): (425, 3500),
            ("Pregnancy", "14-18"): (450, 3000),
            ("Pregnancy", "19-30"): (450, 3500),
            ("Pregnancy", "31-50"): (450, 3500),
            ("Lactation", "14-18"): (550, 3000),
            ("Lactation", "19-30"): (550, 3500),
            ("Lactation", "31-50"): (550, 3500),
        },
    },
    "Calcium": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (1300, 3000),
            ("Male", "19-30"): (1000, 2500),
            ("Male", "31-50"): (1000, 2500),
            ("Male", "51-70"): (1000, 2000),
            ("Male", "71+"): (1200, 2000),
            ("Female", "14-18"): (1300, 3000),
            ("Female", "19-30"): (1000, 2500),
            ("Female", "31-50"): (1000, 2500),
            ("Female", "51-70"): (1200, 2000),
            ("Female", "71+"): (1200, 2000),
            ("Pregnancy", "14-18"): (1300, 3000),
            ("Pregnancy", "19-30"): (1000, 2500),
            ("Pregnancy", "31-50"): (1000, 2500),
            ("Lactation", "14-18"): (1300, 3000),
            ("Lactation", "19-30"): (1000, 2500),
            ("Lactation", "31-50"): (1000, 2500),
        },
    },
    "Magnesium": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (410, 350),
            ("Male", "19-30"): (400, 350),
            ("Male", "31-50"): (420, 350),
            ("Male", "51-70"): (420, 350),
            ("Male", "71+"): (420, 350),
            ("Female", "14-18"): (360, 350),
            ("Female", "19-30"): (310, 350),
            ("Female", "31-50"): (320, 350),
            ("Female", "51-70"): (320, 350),
            ("Female", "71+"): (320, 350),
            ("Pregnancy", "14-18"): (400, 350),
            ("Pregnancy", "19-30"): (350, 350),
            ("Pregnancy", "31-50"): (360, 350),
            ("Lactation", "14-18"): (360, 350),
            ("Lactation", "19-30"): (310, 350),
            ("Lactation", "31-50"): (320, 350),
        },
    },
    "Iron": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (11, 45),
            ("Male", "19-30"): (8, 45),
            ("Male", "31-50"): (8, 45),
            ("Male", "51-70"): (8, 45),
            ("Male", "71+"): (8, 45),
            ("Female", "14-18"): (15, 45),
            ("Female", "19-30"): (18, 45),
            ("Female", "31-50"): (18, 45),
            ("Female", "51-70"): (8, 45),
            ("Female", "71+"): (8, 45),
            ("Pregnancy", "14-18"): (27, 45),
            ("Pregnancy", "19-30"): (27, 45),
            ("Pregnancy", "31-50"): (27, 45),
            ("Lactation", "14-18"): (10, 45),
            ("Lactation", "19-30"): (9, 45),
            ("Lactation", "31-50"): (9, 45),
        },
    },
    "Zinc": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (11, 34),
            ("Male", "19-30"): (11, 40),
            ("Male", "31-50"): (11, 40),
            ("Male", "51-70"): (11, 40),
            ("Male", "71+"): (11, 40),
            ("Female", "14-18"): (9, 34),
            ("Female", "19-30"): (8, 40),
            ("Female", "31-50"): (8, 40),
            ("Female", "51-70"): (8, 40),
            ("Female", "71+"): (8, 40),
            ("Pregnancy", "14-18"): (12, 34),
            ("Pregnancy", "19-30"): (11, 40),
            ("Pregnancy", "31-50"): (11, 40),
            ("Lactation", "14-18"): (13, 34),
            ("Lactation", "19-30"): (12, 40),
            ("Lactation", "31-50"): (12, 40),
        },
    },
    "Copper": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (890, 8000),
            ("Male", "19-30"): (900, 10000),
            ("Male", "31-50"): (900, 10000),
            ("Male", "51-70"): (900, 10000),
            ("Male", "71+"): (900, 10000),
            ("Female", "14-18"): (890, 8000),
            ("Female", "19-30"): (900, 10000),
            ("Female", "31-50"): (900, 10000),
            ("Female", "51-70"): (900, 10000),
            ("Female", "71+"): (900, 10000),
            ("Pregnancy", "14-18"): (1000, 8000),
            ("Pregnancy", "19-30"): (1000, 10000),
            ("Pregnancy", "31-50"): (1000, 10000),
            ("Lactation", "14-18"): (1300, 8000),
            ("Lactation", "19-30"): (1300, 10000),
            ("Lactation", "31-50"): (1300, 10000),
        },
    },
    "Selenium": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (55, 400),
            ("Male", "19-30"): (55, 400),
            ("Male", "31-50"): (55, 400),
            ("Male", "51-70"): (55, 400),
            ("Male", "71+"): (55, 400),
            ("Female", "14-18"): (55, 400),
            ("Female", "19-30"): (55, 400),
            ("Female", "31-50"): (55, 400),
            ("Female", "51-70"): (55, 400),
            ("Female", "71+"): (55, 400),
            ("Pregnancy", "14-18"): (60, 400),
            ("Pregnancy", "19-30"): (60, 400),
            ("Pregnancy", "31-50"): (60, 400),
            ("Lactation", "14-18"): (70, 400),
            ("Lactation", "19-30"): (70, 400),
            ("Lactation", "31-50"): (70, 400),
        },
    },
    "Iodine": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (150, 900),
            ("Male", "19-30"): (150, 1100),
            ("Male", "31-50"): (150, 1100),
            ("Male", "51-70"): (150, 1100),
            ("Male", "71+"): (150, 1100),
            ("Female", "14-18"): (150, 900),
            ("Female", "19-30"): (150, 1100),
            ("Female", "31-50"): (150, 1100),
            ("Female", "51-70"): (150, 1100),
            ("Female", "71+"): (150, 1100),
            ("Pregnancy", "14-18"): (220, 900),
            ("Pregnancy", "19-30"): (220, 1100),
            ("Pregnancy", "31-50"): (220, 1100),
            ("Lactation", "14-18"): (290, 900),
            ("Lactation", "19-30"): (290, 1100),
            ("Lactation", "31-50"): (290, 1100),
        },
    },
    "Chromium": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (35, None),
            ("Male", "19-30"): (35, None),
            ("Male", "31-50"): (35, None),
            ("Male", "51-70"): (30, None),
            ("Male", "71+"): (30, None),
            ("Female", "14-18"): (24, None),
            ("Female", "19-30"): (25, None),
            ("Female", "31-50"): (25, None),
            ("Female", "51-70"): (20, None),
            ("Female", "71+"): (20, None),
            ("Pregnancy", "14-18"): (29, None),
            ("Pregnancy", "19-30"): (30, None),
            ("Pregnancy", "31-50"): (30, None),
            ("Lactation", "14-18"): (44, None),
            ("Lactation", "19-30"): (45, None),
            ("Lactation", "31-50"): (45, None),
        },
    },
    "Manganese": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (2.2, 9),
            ("Male", "19-30"): (2.3, 11),
            ("Male", "31-50"): (2.3, 11),
            ("Male", "51-70"): (2.3, 11),
            ("Male", "71+"): (2.3, 11),
            ("Female", "14-18"): (1.6, 9),
            ("Female", "19-30"): (1.8, 11),
            ("Female", "31-50"): (1.8, 11),
            ("Female", "51-70"): (1.8, 11),
            ("Female", "71+"): (1.8, 11),
            ("Pregnancy", "14-18"): (2.0, 9),
            ("Pregnancy", "19-30"): (2.0, 11),
            ("Pregnancy", "31-50"): (2.0, 11),
            ("Lactation", "14-18"): (2.6, 9),
            ("Lactation", "19-30"): (2.6, 11),
            ("Lactation", "31-50"): (2.6, 11),
        },
    },
    "Molybdenum": {
        "unit": "mcg",
        "groups": {
            ("Male", "14-18"): (43, 1700),
            ("Male", "19-30"): (45, 2000),
            ("Male", "31-50"): (45, 2000),
            ("Male", "51-70"): (45, 2000),
            ("Male", "71+"): (45, 2000),
            ("Female", "14-18"): (43, 1700),
            ("Female", "19-30"): (45, 2000),
            ("Female", "31-50"): (45, 2000),
            ("Female", "51-70"): (45, 2000),
            ("Female", "71+"): (45, 2000),
            ("Pregnancy", "14-18"): (50, 1700),
            ("Pregnancy", "19-30"): (50, 2000),
            ("Pregnancy", "31-50"): (50, 2000),
            ("Lactation", "14-18"): (50, 1700),
            ("Lactation", "19-30"): (50, 2000),
            ("Lactation", "31-50"): (50, 2000),
        },
    },
    "Phosphorus": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (1250, 4000),
            ("Male", "19-30"): (700, 4000),
            ("Male", "31-50"): (700, 4000),
            ("Male", "51-70"): (700, 4000),
            ("Male", "71+"): (700, 3000),
            ("Female", "14-18"): (1250, 4000),
            ("Female", "19-30"): (700, 4000),
            ("Female", "31-50"): (700, 4000),
            ("Female", "51-70"): (700, 4000),
            ("Female", "71+"): (700, 3000),
            ("Pregnancy", "14-18"): (1250, 3500),
            ("Pregnancy", "19-30"): (700, 3500),
            ("Pregnancy", "31-50"): (700, 3500),
            ("Lactation", "14-18"): (1250, 4000),
            ("Lactation", "19-30"): (700, 4000),
            ("Lactation", "31-50"): (700, 4000),
        },
    },
    "Fluoride": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (3, 10),
            ("Male", "19-30"): (4, 10),
            ("Male", "31-50"): (4, 10),
            ("Male", "51-70"): (4, 10),
            ("Male", "71+"): (4, 10),
            ("Female", "14-18"): (3, 10),
            ("Female", "19-30"): (3, 10),
            ("Female", "31-50"): (3, 10),
            ("Female", "51-70"): (3, 10),
            ("Female", "71+"): (3, 10),
            ("Pregnancy", "14-18"): (3, 10),
            ("Pregnancy", "19-30"): (3, 10),
            ("Pregnancy", "31-50"): (3, 10),
            ("Lactation", "14-18"): (3, 10),
            ("Lactation", "19-30"): (3, 10),
            ("Lactation", "31-50"): (3, 10),
        },
    },
    "Boron": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (None, 17),
            ("Male", "19-30"): (None, 20),
            ("Male", "31-50"): (None, 20),
            ("Male", "51-70"): (None, 20),
            ("Male", "71+"): (None, 20),
            ("Female", "14-18"): (None, 17),
            ("Female", "19-30"): (None, 20),
            ("Female", "31-50"): (None, 20),
            ("Female", "51-70"): (None, 20),
            ("Female", "71+"): (None, 20),
            ("Pregnancy", "14-18"): (None, 17),
            ("Pregnancy", "19-30"): (None, 20),
            ("Pregnancy", "31-50"): (None, 20),
            ("Lactation", "14-18"): (None, 17),
            ("Lactation", "19-30"): (None, 20),
            ("Lactation", "31-50"): (None, 20),
        },
    },
    "Vanadium": {
        "unit": "mcg",  # Our file uses mcg; DRI reference is 1.8 mg = 1800 mcg
        "groups": {
            ("Male", "19-30"): (None, 1800),
            ("Male", "31-50"): (None, 1800),
            ("Male", "51-70"): (None, 1800),
            ("Male", "71+"): (None, 1800),
            ("Female", "19-30"): (None, 1800),
            ("Female", "31-50"): (None, 1800),
            ("Female", "51-70"): (None, 1800),
            ("Female", "71+"): (None, 1800),
        },
    },
    "Potassium": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (3000, None),
            ("Male", "19-30"): (3400, None),
            ("Male", "31-50"): (3400, None),
            ("Male", "51-70"): (3400, None),
            ("Male", "71+"): (3400, None),
            ("Female", "14-18"): (2300, None),
            ("Female", "19-30"): (2600, None),
            ("Female", "31-50"): (2600, None),
            ("Female", "51-70"): (2600, None),
            ("Female", "71+"): (2600, None),
            ("Pregnancy", "14-18"): (2600, None),
            ("Pregnancy", "19-30"): (2900, None),
            ("Pregnancy", "31-50"): (2900, None),
            ("Lactation", "14-18"): (2500, None),
            ("Lactation", "19-30"): (2800, None),
            ("Lactation", "31-50"): (2800, None),
        },
    },
    "Sodium": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (1500, None),
            ("Male", "19-30"): (1500, None),
            ("Male", "31-50"): (1500, None),
            ("Male", "51-70"): (1500, None),
            ("Male", "71+"): (1500, None),
            ("Female", "14-18"): (1500, None),
            ("Female", "19-30"): (1500, None),
            ("Female", "31-50"): (1500, None),
            ("Female", "51-70"): (1500, None),
            ("Female", "71+"): (1500, None),
            ("Pregnancy", "14-18"): (1500, None),
            ("Pregnancy", "19-30"): (1500, None),
            ("Pregnancy", "31-50"): (1500, None),
            ("Lactation", "14-18"): (1500, None),
            ("Lactation", "19-30"): (1500, None),
            ("Lactation", "31-50"): (1500, None),
        },
    },
    "Chloride": {
        "unit": "mg",
        "groups": {
            ("Male", "14-18"): (2300, 3600),
            ("Male", "19-30"): (2300, 3600),
            ("Male", "31-50"): (2300, 3600),
            ("Male", "51-70"): (2000, 3600),
            ("Male", "71+"): (1800, 3600),
            ("Female", "14-18"): (2300, 3600),
            ("Female", "19-30"): (2300, 3600),
            ("Female", "31-50"): (2300, 3600),
            ("Female", "51-70"): (2000, 3600),
            ("Female", "71+"): (1800, 3600),
            ("Pregnancy", "14-18"): (2300, 3600),
            ("Pregnancy", "19-30"): (2300, 3600),
            ("Pregnancy", "31-50"): (2300, 3600),
            ("Lactation", "14-18"): (2300, 3600),
            ("Lactation", "19-30"): (2300, 3600),
            ("Lactation", "31-50"): (2300, 3600),
        },
    },
}

# Nutrients in rda_optimal_uls.json that have NO National Academies DRI
# (supplements-market compounds with literature-based ranges, not official DRIs)
NO_DRI_NUTRIENTS = {
    "Inositol", "Omega-3 Fatty Acids", "Coenzyme Q10", "Alpha-Lipoic Acid",
    "Taurine", "Lutein", "Zeaxanthin", "Lycopene", "Creatine",
    "L-Carnitine", "Acetyl-L-Carnitine", "Alpha-GPC", "Glutathione",
    "Nickel", "Silicon", "Sulfate",
}

# USDA FoodData Central nutrient IDs for cross-reference
USDA_NUTRIENT_IDS = {
    "Vitamin A": 1106,   # Vitamin A, RAE
    "Vitamin C": 1162,
    "Vitamin D": 1114,   # Vitamin D (D2 + D3)
    "Vitamin E": 1109,   # Vitamin E (alpha-tocopherol)
    "Vitamin K": 1185,   # Vitamin K (phylloquinone)
    "Thiamin": 1165,
    "Riboflavin": 1166,
    "Niacin": 1167,
    "Vitamin B6": 1175,
    "Folate": 1190,      # Folate, DFE
    "Vitamin B12": 1178,
    "Calcium": 1087,
    "Magnesium": 1090,
    "Iron": 1089,
    "Zinc": 1095,
    "Copper": 1098,
    "Selenium": 1103,
    "Iodine": 1100,
    "Manganese": 1101,
    "Molybdenum": 1102,
    "Phosphorus": 1091,
    "Potassium": 1092,
    "Sodium": 1093,
    "Fluoride": 1099,
    "Chromium": 1096,
}


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def normalize_unit(unit: str) -> str:
    """Normalize unit strings for comparison."""
    u = unit.lower().strip()
    u = u.replace("alpha-tocopherol", "").replace("rae", "").replace("dfe", "").replace("ne", "")
    u = u.strip()
    return u


def units_compatible(local_unit: str, ref_unit: str) -> bool:
    """Check if units are compatible (same base unit)."""
    lu = normalize_unit(local_unit)
    ru = normalize_unit(ref_unit)
    return lu == ru


def verify_nutrient(name: str, local_entry: Dict, ref_entry: Dict) -> List[Dict]:
    """Verify a single nutrient entry against DRI reference.

    Returns list of issues found.
    """
    issues = []

    # Check unit compatibility
    if not units_compatible(local_entry.get("unit", ""), ref_entry["unit"]):
        # Special case: Vitamin E uses "mg alpha-tocopherol" vs "mg"
        if "mg" in local_entry.get("unit", "") and "mg" in ref_entry["unit"]:
            pass  # Compatible
        # Special case: Vanadium — our file says mcg, DRI says mg
        elif normalize_unit(local_entry.get("unit", "")) != normalize_unit(ref_entry["unit"]):
            issues.append({
                "type": "UNIT_MISMATCH",
                "nutrient": name,
                "local": local_entry.get("unit"),
                "reference": ref_entry["unit"],
            })

    # Check highest_ul against reference
    ref_uls = [ul for (rda, ul) in ref_entry["groups"].values() if ul is not None]
    if ref_uls:
        ref_highest_ul = max(ref_uls)
        local_highest_ul = local_entry.get("highest_ul")
        if local_highest_ul is not None and local_highest_ul != ref_highest_ul:
            issues.append({
                "type": "HIGHEST_UL_MISMATCH",
                "nutrient": name,
                "local": local_highest_ul,
                "reference": ref_highest_ul,
            })
        elif local_highest_ul is None and ref_highest_ul > 0:
            issues.append({
                "type": "MISSING_UL",
                "nutrient": name,
                "reference": ref_highest_ul,
            })

    # Check per-group RDA/AI and UL values
    local_data = {(d["group"], d["age_range"]): d for d in local_entry.get("data", [])}

    for (group, age), (ref_rda, ref_ul) in ref_entry["groups"].items():
        local_row = local_data.get((group, age))
        if not local_row:
            issues.append({
                "type": "MISSING_GROUP",
                "nutrient": name,
                "group": group,
                "age": age,
            })
            continue

        local_rda = local_row.get("rda_ai")
        local_ul = local_row.get("ul")

        if ref_rda is not None and local_rda is not None:
            if abs(float(local_rda) - float(ref_rda)) > 0.01:
                issues.append({
                    "type": "RDA_MISMATCH",
                    "nutrient": name,
                    "group": group,
                    "age": age,
                    "local": local_rda,
                    "reference": ref_rda,
                })

        if ref_ul is not None and local_ul is not None:
            if abs(float(local_ul) - float(ref_ul)) > 0.01:
                issues.append({
                    "type": "UL_MISMATCH",
                    "nutrient": name,
                    "group": group,
                    "age": age,
                    "local": local_ul,
                    "reference": ref_ul,
                })
        elif ref_ul is not None and local_ul is None:
            issues.append({
                "type": "MISSING_UL_GROUP",
                "nutrient": name,
                "group": group,
                "age": age,
                "reference": ref_ul,
            })

    return issues


def verify_all(rda_data: Dict) -> Tuple[List[Dict], Dict]:
    """Verify all nutrients in rda_optimal_uls.json.

    Returns (issues, summary).
    """
    recs = rda_data.get("nutrient_recommendations", [])
    all_issues = []
    verified = 0
    no_dri = 0
    not_in_ref = 0

    for entry in recs:
        name = entry.get("standard_name", "")

        if name in NO_DRI_NUTRIENTS:
            no_dri += 1
            continue

        ref = DRI_REFERENCE.get(name)
        if ref is None:
            not_in_ref += 1
            all_issues.append({
                "type": "NOT_IN_REFERENCE",
                "nutrient": name,
                "note": "Nutrient has no entry in DRI_REFERENCE table — may need to be added",
            })
            continue

        issues = verify_nutrient(name, entry, ref)
        all_issues.extend(issues)
        verified += 1

    # Check for DRI nutrients missing from local file
    local_names = {e.get("standard_name") for e in recs}
    for ref_name in DRI_REFERENCE:
        if ref_name not in local_names:
            all_issues.append({
                "type": "MISSING_FROM_LOCAL",
                "nutrient": ref_name,
                "note": "DRI reference nutrient not found in rda_optimal_uls.json",
            })

    summary = {
        "total_local": len(recs),
        "verified_against_dri": verified,
        "no_dri_available": no_dri,
        "not_in_reference_table": not_in_ref,
        "total_issues": len(all_issues),
        "issue_types": {},
    }
    for issue in all_issues:
        t = issue["type"]
        summary["issue_types"][t] = summary["issue_types"].get(t, 0) + 1

    return all_issues, summary


# ---------------------------------------------------------------------------
# USDA FoodData Central API check
# ---------------------------------------------------------------------------

def usda_check_nutrient(name: str, nutrient_id: int, api_key: str) -> Optional[Dict]:
    """Validate nutrient name against USDA FDC API."""
    import ssl
    import urllib.request
    import urllib.error

    url = f"https://api.nal.usda.gov/fdc/v1/food/2346405?api_key={api_key}&nutrients={nutrient_id}"

    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read())
            nutrients = data.get("foodNutrients", [])
            for n in nutrients:
                if n.get("nutrient", {}).get("id") == nutrient_id:
                    return {
                        "name": name,
                        "usda_id": nutrient_id,
                        "usda_name": n["nutrient"]["name"],
                        "usda_unit": n["nutrient"]["unitName"],
                        "match": True,
                    }
            return {
                "name": name,
                "usda_id": nutrient_id,
                "usda_name": None,
                "usda_unit": None,
                "match": False,
            }
    except Exception as e:
        return {"name": name, "usda_id": nutrient_id, "error": str(e)}


def run_usda_check(api_key: str) -> List[Dict]:
    """Validate all mapped nutrients against USDA FDC API."""
    results = []
    for name, nid in sorted(USDA_NUTRIENT_IDS.items()):
        result = usda_check_nutrient(name, nid, api_key)
        results.append(result)
        time.sleep(0.2)  # Rate limit courtesy
    return results


# ---------------------------------------------------------------------------
# Apply fixes
# ---------------------------------------------------------------------------

def apply_fixes(rda_data: Dict, issues: List[Dict]) -> int:
    """Apply safe fixes to rda_optimal_uls.json data.

    Only fixes highest_ul mismatches and missing UL values in group data.
    Returns number of fixes applied.
    """
    recs = rda_data.get("nutrient_recommendations", [])
    idx = {e["standard_name"]: e for e in recs}
    fixes = 0

    for issue in issues:
        name = issue.get("nutrient", "")
        entry = idx.get(name)
        if not entry:
            continue

        if issue["type"] == "HIGHEST_UL_MISMATCH":
            old = entry.get("highest_ul")
            entry["highest_ul"] = issue["reference"]
            print(f"  Fixed {name} highest_ul: {old} -> {issue['reference']}")
            fixes += 1

        elif issue["type"] == "RDA_MISMATCH":
            group, age = issue["group"], issue["age"]
            for d in entry.get("data", []):
                if d["group"] == group and d["age_range"] == age:
                    old = d.get("rda_ai")
                    d["rda_ai"] = issue["reference"]
                    print(f"  Fixed {name} [{group} {age}] rda_ai: {old} -> {issue['reference']}")
                    fixes += 1
                    break

        elif issue["type"] == "UL_MISMATCH":
            group, age = issue["group"], issue["age"]
            for d in entry.get("data", []):
                if d["group"] == group and d["age_range"] == age:
                    old = d.get("ul")
                    d["ul"] = issue["reference"]
                    print(f"  Fixed {name} [{group} {age}] ul: {old} -> {issue['reference']}")
                    fixes += 1
                    break

    return fixes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Verify rda_optimal_uls.json against National Academies DRI values"
    )
    parser.add_argument("--nutrient", help="Verify a single nutrient by name")
    parser.add_argument("--apply", action="store_true", help="Apply safe fixes")
    parser.add_argument("--usda-check", action="store_true",
                        help="Validate nutrient names against USDA FoodData Central API")
    parser.add_argument("--file", default=str(SCRIPTS_ROOT / "data" / "rda_optimal_uls.json"),
                        help="Path to rda_optimal_uls.json")
    args = parser.parse_args()

    # Load data
    with open(args.file, "r", encoding="utf-8") as f:
        rda_data = json.load(f)

    print(f"Loaded {args.file}")
    recs = rda_data.get("nutrient_recommendations", [])
    print(f"  Nutrients: {len(recs)}")
    print(f"  DRI reference: {len(DRI_REFERENCE)} nutrients")
    print(f"  No-DRI supplements: {len(NO_DRI_NUTRIENTS)} nutrients")
    print()

    # Single nutrient mode
    if args.nutrient:
        entry = None
        for r in recs:
            if r["standard_name"].lower() == args.nutrient.lower():
                entry = r
                break
        if not entry:
            print(f"Nutrient '{args.nutrient}' not found in file.")
            sys.exit(1)

        name = entry["standard_name"]
        if name in NO_DRI_NUTRIENTS:
            print(f"{name}: No National Academies DRI (supplement-market compound)")
            sys.exit(0)

        ref = DRI_REFERENCE.get(name)
        if not ref:
            print(f"{name}: Not in DRI reference table")
            sys.exit(1)

        issues = verify_nutrient(name, entry, ref)
        if not issues:
            print(f"{name}: All values match DRI reference")
        else:
            for issue in issues:
                print(f"  {issue['type']}: {issue}")
        sys.exit(0)

    # Full verification
    issues, summary = verify_all(rda_data)

    print("=== Verification Summary ===")
    print(f"  Total nutrients in file:     {summary['total_local']}")
    print(f"  Verified against DRI:        {summary['verified_against_dri']}")
    print(f"  No DRI available:            {summary['no_dri_available']}")
    print(f"  Not in reference table:      {summary['not_in_reference_table']}")
    print(f"  Total issues found:          {summary['total_issues']}")
    print()

    if summary["issue_types"]:
        print("Issue breakdown:")
        for itype, count in sorted(summary["issue_types"].items()):
            print(f"  {itype}: {count}")
        print()

    if issues:
        print("=== Issues ===")
        for issue in issues:
            if issue["type"] == "RDA_MISMATCH":
                print(f"  {issue['nutrient']} [{issue['group']} {issue['age']}]: "
                      f"RDA local={issue['local']} ref={issue['reference']}")
            elif issue["type"] == "UL_MISMATCH":
                print(f"  {issue['nutrient']} [{issue['group']} {issue['age']}]: "
                      f"UL local={issue['local']} ref={issue['reference']}")
            elif issue["type"] == "HIGHEST_UL_MISMATCH":
                print(f"  {issue['nutrient']}: highest_ul local={issue['local']} ref={issue['reference']}")
            elif issue["type"] == "UNIT_MISMATCH":
                print(f"  {issue['nutrient']}: unit local='{issue['local']}' ref='{issue['reference']}'")
            else:
                print(f"  {issue['type']}: {issue.get('nutrient', '?')} — {issue.get('note', '')}")
        print()

    # Apply fixes
    if args.apply and issues:
        print("=== Applying Fixes ===")
        fix_count = apply_fixes(rda_data, issues)
        if fix_count > 0:
            with open(args.file, "w", encoding="utf-8") as f:
                json.dump(rda_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"\n{fix_count} fixes applied and saved.")
        else:
            print("No auto-fixable issues found.")
    elif args.apply:
        print("No issues to fix.")

    # USDA check
    if args.usda_check:
        api_key = os.environ.get("USDA_API_KEY") or os.environ.get("FDC_API_KEY")
        if not api_key:
            print("ERROR: USDA_API_KEY or FDC_API_KEY not set in environment.")
            sys.exit(1)

        print("\n=== USDA FoodData Central Nutrient ID Validation ===")
        results = run_usda_check(api_key)
        for r in results:
            if r.get("error"):
                print(f"  {r['name']}: ERROR — {r['error']}")
            elif r.get("match"):
                print(f"  {r['name']}: OK (USDA ID {r['usda_id']} = {r['usda_name']}, {r['usda_unit']})")
            else:
                print(f"  {r['name']}: NOT FOUND at USDA ID {r['usda_id']}")

    # Exit code
    if summary["total_issues"] > 0 and not args.apply:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
