.PHONY: all install run test

all: install test

install:
	poetry install

run:
	poetry run local-llm

test:
	poetry run pytest
