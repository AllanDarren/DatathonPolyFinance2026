# Minimal bootstrap by role A (A0). Role B owns this file and will extend it
# (dev, deploy, deploy-web, destroy, smoke).
PY ?= python3

.PHONY: test lint contracts examples validate-rules

test:
	$(PY) -m tools.export_schemas --check
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check core agents services tools tests ingest

contracts:
	$(PY) -m tools.export_schemas

examples:
	$(PY) -m tools.build_examples

validate-rules:
	$(PY) -m tools.validate_rules
