"""Gate B — emitted form-note artifact contract."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_form_notes_export import check_row  # noqa: E402


NOTE = "First approved sentence. A later approved sentence."


def _row(**analysis_overrides):
    analysis = {
        "display_form_label": "Test form",
        "bio_score": 10.0,
        "form_note": NOTE,
        "form_note_preview": "First approved sentence.",
    }
    analysis.update(analysis_overrides)
    return {"display_name": "Test form", "score_included": True, "analysis": analysis}


def test_gate_b_requires_the_exact_first_sentence_as_preview():
    problems = check_row(_row(form_note_preview="First approved"))
    assert any("exact first sentence" in problem for problem in problems)


def test_gate_b_requires_score_included_for_a_form_note():
    row = _row()
    row["score_included"] = None
    problems = check_row(row)
    assert any("score_included" in problem for problem in problems)


def test_gate_b_validates_legacy_form_note_preview(tmp_path):
    from validate_form_notes_export import scan

    (tmp_path / "legacy.json").write_text(
        '{"ingredients": [{"display_label": "Test form", '
        '"form_note": "First neutral sentence. Follow-up sentence.", '
        '"form_note_preview": "First neutral"}]}'
    )

    _, _, violations = scan(tmp_path, limit=None)

    assert any("exact first sentence" in violation for violation in violations)


def test_gate_b_ignores_legacy_workspace_notes_without_form_note(tmp_path):
    """Legacy curation prose is not a consumer-copy field and must not trip Gate B."""
    from validate_form_notes_export import scan

    (tmp_path / "workspace-only.json").write_text(
        '{"ingredients": [{"display_label": "Test form", '
        '"notes": "Cited evidence: PMID:123. See scripts/audits/example.json."}]}'
    )

    scanned, notes, violations = scan(tmp_path, limit=None)

    assert scanned == 1
    assert notes == 0
    assert violations == []
