"""Label-fragment artifacts must not be treated as scorable ingredients (2026-06).

From the BulkSupplements unmapped triage:
  - 'Essential Amino Acids' is a blend HEADER (a class of EAAs that carries a
    total, not a per-active dose) -> BLEND_HEADER_EXACT_NAMES.
  - 'containing the Omega 3 Fatty Acids' is a label sentence fragment, not an
    ingredient -> EXCLUDED_LABEL_PHRASES.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from constants import BLEND_HEADER_EXACT_NAMES, EXCLUDED_LABEL_PHRASES


def test_essential_amino_acids_is_blend_header():
    assert "essential amino acids" in BLEND_HEADER_EXACT_NAMES


def test_omega3_label_fragment_excluded():
    assert "containing the omega 3 fatty acids" in EXCLUDED_LABEL_PHRASES
