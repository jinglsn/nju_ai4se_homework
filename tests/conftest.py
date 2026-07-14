import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "src").mkdir()
        (workspace / "tests").mkdir()
        yield workspace


@pytest.fixture
def temp_harness_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        harness_dir = Path(tmpdir) / ".harness"
        harness_dir.mkdir()
        yield harness_dir