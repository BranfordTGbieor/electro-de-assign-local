PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
RUFF ?= .venv/bin/ruff

.PHONY: setup clean ingest incremental transform run run-incremental lint test dbt-run dbt-test

setup:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

clean:
	rm -rf .local outputs/*.csv outputs/*.json
	mkdir -p outputs .local

ingest:
	$(PYTHON) -m src.ingest --mode full --watermark-output outputs/watermark_run1.json

incremental:
	$(PYTHON) -m src.ingest --mode incremental --watermark-output outputs/watermark_run2.json

transform:
	$(PYTHON) -m src.transform

run:
	$(PYTHON) -m src.run_pipeline --mode full

run-incremental:
	$(PYTHON) -m src.run_pipeline --mode incremental

lint:
	$(RUFF) check src tests

test:
	$(PYTEST) -q

dbt-run:
	cd dbt && dbt run

dbt-test:
	cd dbt && dbt test
