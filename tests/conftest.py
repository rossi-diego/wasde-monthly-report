from pathlib import Path

import pytest

from wasde.config import PROJECT_ROOT

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def config_dir() -> Path:
    return PROJECT_ROOT / "config"
