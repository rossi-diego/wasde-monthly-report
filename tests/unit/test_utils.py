# tests/unit/test_utils.py
"""Tests for utility modules."""

from __future__ import annotations

import logging


def test_get_logger_returns_logger():
    from wasde.utils.logging import get_logger

    log = get_logger("test_module")
    assert isinstance(log, logging.Logger)
    assert log.name == "test_module"


def test_get_logger_returns_same_instance():
    from wasde.utils.logging import get_logger

    log1 = get_logger("same_name")
    log2 = get_logger("same_name")
    assert log1 is log2
