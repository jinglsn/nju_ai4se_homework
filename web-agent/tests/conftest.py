import pytest
from pathlib import Path
import tempfile


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "src").mkdir(exist_ok=True)
        (ws / "tests").mkdir(exist_ok=True)
        yield ws


@pytest.fixture
def temp_harness_dir():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / ".harness").mkdir(exist_ok=True)
        yield p