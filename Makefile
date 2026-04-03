.PHONY: all install run test smoke web

all: install test smoke

install:
	poetry install
	poetry run playwright install chromium

run:
	poetry run local-llm

test:
	poetry run pytest tests/ -v -m "not smoke"

smoke:
	poetry run pytest tests/e2e/ -v -m smoke

web:
	poetry run local-llm-web
