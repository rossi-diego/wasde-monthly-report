# tests/unit/test_config.py
"""Tests for config module."""

from __future__ import annotations

from pathlib import Path


def test_settings_defaults():
    from wasde.config import Settings

    s = Settings(usda_psd_key="test_key")
    assert s.app_name == "WASDE Dashboard"
    assert s.log_level == "INFO"
    assert s.data_dir == Path("data")


def test_settings_derived_paths():
    from wasde.config import Settings

    s = Settings(usda_psd_key="", data_dir=Path("/tmp/test"))
    assert s.bronze_dir == Path("/tmp/test/bronze")
    assert s.silver_dir == Path("/tmp/test/silver")
    assert s.duckdb_path == Path("/tmp/test/wasde.duckdb")


def test_configure_logging_runs():
    from wasde.config import configure_logging

    configure_logging()  # Should not raise


def test_settings_manifest_path():
    from wasde.config import Settings

    s = Settings(usda_psd_key="")
    assert "manifest" in str(s.wasde_manifest_path)
