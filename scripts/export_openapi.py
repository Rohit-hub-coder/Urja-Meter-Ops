#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.urja_api.main import app

def generate_openapi():
    openapi_schema = app.openapi()
    output_path = ROOT / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, sort_keys=True)
    print(f"Generated {output_path} successfully ({len(openapi_schema.get('paths', {}))} paths).")

if __name__ == "__main__":
    generate_openapi()
