set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

check: lint validate audit-seed test

lint:
    uv run --locked ruff check src tests/test_native.py tests/test_seed_evidence.py

validate:
    uv run --locked cofactormech validate

validate-schema:
    uv run --locked cofactormech validate-schema

validate-data: validate

validate-all: validate

test:
    uv run --locked pytest -q

check-vendored:
    bash scripts/check_vendored_sync.sh

new-history *args:
    uv run --locked cofactormech new-history {{args}}

validate-history:
    uv run --locked cofactormech validate

audit-seed:
    uv run --locked python -m cofactormech.seed_audit
