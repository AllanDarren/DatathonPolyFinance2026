# AlphaForge AI - owned by role B. Targets from role A kept as they were (contracts, examples, eval...).
# Windows without make: run the python commands shown on each line directly.
PY ?= python3

.PHONY: help dev test test-api lint contracts examples validate-rules eval classify ingest \
        check-aws build-lambda deploy upload-data deploy-web outputs smoke smoke-local destroy

help:
	@echo "dev | test | validate-rules | check-aws | deploy | deploy-web | smoke | destroy"

# --- local -------------------------------------------------------------------
dev:            ## local API on http://127.0.0.1:8000 (LLM_PROVIDER=mock, DATA_DIR=data)
	$(PY) -m api.local_server

test:           ## contracts up to date + backend tests + API tests (offline)
	$(PY) -m tools.export_schemas --check
	$(PY) -m pytest -q tests api/tests

test-api:
	$(PY) -m pytest -q api/tests

lint:
	$(PY) -m ruff check core agents services tools tests ingest api infra scripts

contracts:
	$(PY) -m tools.export_schemas

examples:
	$(PY) -m tools.build_examples

validate-rules:
	$(PY) -m tools.validate_rules

eval:
	$(PY) -m tools.run_eval

classify:
	$(PY) -m agents.classify_batch

ingest:
	$(PY) -m ingest.run --google

smoke-local:    ## against make dev
	$(PY) scripts/smoke_test.py --base-url http://127.0.0.1:8000

# --- AWS (role B deploys) ----------------------------------------------------
check-aws:      ## B0 audit: identity, Bedrock models, Converse test, service access
	$(PY) infra/scripts/check_bedrock.py

build-lambda:
	$(PY) scripts/build_lambda.py

deploy:         ## build zip + deploy stack + upload data/ to S3
	$(PY) scripts/deploy.py deploy

upload-data:    ## refresh starter data and snapshots on S3 (no redeploy)
	$(PY) scripts/deploy.py upload-data

deploy-web:     ## build web/ with VITE_API_URL, sync to S3, invalidate CloudFront
	$(PY) scripts/deploy.py deploy-web

outputs:
	$(PY) scripts/deploy.py outputs

smoke:          ## smoke test of the deployed API (with the CloudFront origin for CORS)
	$(PY) scripts/deploy.py outputs
	$(PY) scripts/smoke_test.py --deployed

destroy:        ## asks to type the stack name before deleting anything
	$(PY) scripts/deploy.py destroy
