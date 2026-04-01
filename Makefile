.PHONY: all install run test web

all: install test

install:
	poetry install
	poetry run playwright install chromium

run:
	poetry run local-llm

test:
	poetry run pytest tests/ -v

web:
	poetry run local-llm-web
