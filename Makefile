.PHONY: install run test test-live lint format openapi clean

VENV = .venv
PYTHON = $(VENV)/bin/python
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff
UVICORN = $(VENV)/bin/uvicorn

install:
	uv venv $(VENV)
	uv pip install -e ".[test]"

run:
	$(PYTHON) -m uvicorn src.urja_api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(PYTEST) -v

test-live:
	ENABLE_LIVE_PORTAL_TESTS=true $(PYTEST) tests/test_live_smoke.py -v

lint:
	$(RUFF) check src tests
	$(RUFF) format --check src tests

format:
	$(RUFF) format src tests
	$(RUFF) check --fix src tests

openapi:
	$(PYTHON) scripts/export_openapi.py

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info urja_local.db
