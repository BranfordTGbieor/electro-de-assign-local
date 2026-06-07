PYTHON ?= .venv/bin/python

.PHONY: setup reset-venv clean ingest incremental transform run run-incremental lint test dbt-run dbt-test

setup:
	python3 -m venv --clear .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

reset-venv: setup

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
	$(PYTHON) -m ruff check src tests

test:
	$(PYTHON) -m pytest -q

dbt-run:
	cd dbt && dbt run

dbt-test:
	cd dbt && dbt test
