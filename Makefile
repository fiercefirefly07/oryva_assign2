PYTHON ?= python3
SEED ?= 20261022
SCALE ?= starter
DATA_DIR ?= data

.PHONY: setup schema-info check-config generate-starter generate validate test repro docs report dashboard clean

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

schema-info:
	$(PYTHON) -m oryva_planning schema-info

check-config:
	$(PYTHON) -m oryva_planning check-config --scale $(SCALE) --seed $(SEED)

generate-starter:
	$(PYTHON) -m oryva_planning generate --scale starter --seed $(SEED) --output-dir $(DATA_DIR)

generate:
	$(PYTHON) -m oryva_planning generate --scale full --seed $(SEED) --output-dir $(DATA_DIR)

validate:
	$(PYTHON) -m oryva_planning validate --data-dir $(DATA_DIR)

test:
	$(PYTHON) -m pytest

repro:
	$(PYTHON) -m oryva_planning repro --scale $(SCALE) --seed $(SEED)

docs:
	$(PYTHON) -m oryva_planning export-docs --data-dir $(DATA_DIR) --docs-dir docs

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache data/repro_run_*

report:
	$(PYTHON) -m oryva_planning report --data-dir $(DATA_DIR) --output docs/planning_dashboard.html

dashboard:
	$(PYTHON) -m streamlit run src/oryva_planning/dashboard/app.py
