set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

check: lint validate test

lint:
    uv run --locked ruff check src tests/test_native.py scripts/check_review_event_base.py tests/test_review_event_base.py

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

check-review-event-base:
    uv run --locked python scripts/check_review_event_base.py
