PYTHON ?= python3

.PHONY: install lint test run-api run-dashboard

install:
	$(PYTHON) -m pip install -e .[dev]

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m mypy src

test:
	$(PYTHON) -m pytest --maxfail=1 --disable-warnings

run-api:
	$(PYTHON) -m uvicorn b3_quant_platform.api.main:app --host 0.0.0.0 --port 8080 --reload

run-dashboard:
	$(PYTHON) -m streamlit run src/b3_quant_platform/dashboard/app.py
