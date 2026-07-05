import logging

import clean_dsld_data
from clean_dsld_data import DSLDCleaningPipeline
from enhanced_normalizer import EnhancedDSLDNormalizer
from preflight import validate_iqm_br_collision


def test_clean_pipeline_logger_does_not_propagate_and_duplicate_handlers():
    pipeline = DSLDCleaningPipeline.__new__(DSLDCleaningPipeline)
    pipeline.config = {
        "logging": {
            "level": "INFO",
            "log_to_console": True,
            "log_to_file": False,
        },
        "paths": {
            "log_directory": "logs",
        },
    }

    logger = pipeline._setup_logging()
    logger = pipeline._setup_logging()

    try:
        assert logger.propagate is False
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1
        assert len(logger.handlers) == 1
    finally:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()


def test_normalizer_builds_fast_lookups_once_during_init(monkeypatch):
    calls = {"count": 0}

    def count_only(self):
        calls["count"] += 1

    monkeypatch.setattr(EnhancedDSLDNormalizer, "_build_fast_lookups_impl", count_only)
    monkeypatch.setattr(
        EnhancedDSLDNormalizer,
        "_preflight_iqm_banned_collision_check",
        lambda self: None,
    )

    EnhancedDSLDNormalizer()

    assert calls["count"] == 1


def test_preflight_iqm_banned_collision_guard_has_no_hard_collisions():
    result = validate_iqm_br_collision()

    assert result["ok"] is True
    assert result["collisions"] == []


def test_clean_pipeline_fails_when_processing_summary_is_incomplete(tmp_path, monkeypatch):
    pipeline = DSLDCleaningPipeline.__new__(DSLDCleaningPipeline)
    pipeline.config = {
        "paths": {
            "input_directory": str(tmp_path),
            "output_directory": str(tmp_path / "out"),
        },
        "validation": {"min_success_rate": 95.0},
    }
    pipeline.logger = logging.getLogger("test_clean_pipeline_incomplete_summary")

    input_file = tmp_path / "product.json"
    input_file.write_text("{}", encoding="utf-8")

    class FakeProcessor:
        def __init__(self, config):
            self.config = config

        def get_input_files(self, input_dir):
            return [input_file]

        def process_all_files(self, files, resume=False):
            return {
                "processing_complete": False,
                "total_files": 100,
                "success_rate": 99.0,
                "results": {
                    "cleaned": 99,
                    "needs_review": 0,
                    "incomplete": 0,
                    "errors": 1,
                },
                "unmapped_ingredients": 0,
                "output_write_failures": 1,
            }

    monkeypatch.setattr(pipeline, "validate_config", lambda: True)
    monkeypatch.setattr(clean_dsld_data, "BatchProcessor", FakeProcessor)

    assert pipeline.run() is False
