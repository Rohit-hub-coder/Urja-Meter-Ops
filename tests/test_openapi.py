import json
from pathlib import Path

from src.urja_api.main import app

ROOT = Path(__file__).resolve().parent.parent


def test_committed_openapi_matches_app_schema():
    """Ensures committed openapi.json is never stale or out of sync with current app code."""
    openapi_file = ROOT / "openapi.json"
    assert openapi_file.exists(), "openapi.json does not exist. Run scripts/export_openapi.py."

    with open(openapi_file, "r", encoding="utf-8") as f:
        committed_schema = json.load(f)

    current_schema = app.openapi()
    # Compare canonical sorted JSON strings
    assert json.dumps(committed_schema, sort_keys=True) == json.dumps(current_schema, sort_keys=True), (
        "Committed openapi.json is out of date. Run 'python scripts/export_openapi.py' to regenerate."
    )
