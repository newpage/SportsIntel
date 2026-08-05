import pytest

from app.intelligence.snapshot_store import nfl_snapshot_store


@pytest.fixture(autouse=True)
def reset_nfl_snapshot_store():
    nfl_snapshot_store.clear_all()
    yield
    nfl_snapshot_store.clear_all()
