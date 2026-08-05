import pytest

from app.intelligence.snapshot_store import nfl_snapshot_store
from app.main import app


@pytest.fixture(autouse=True)
def reset_nfl_snapshot_store():
    original_settings = app.state.settings
    app.state.rate_limiter.clear()
    nfl_snapshot_store.clear_all()
    yield
    app.state.settings = original_settings
    app.state.rate_limiter.clear()
    nfl_snapshot_store.clear_all()
