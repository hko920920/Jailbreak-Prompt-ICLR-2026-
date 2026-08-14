.PHONY: test lint format smoke

test:
	pytest

lint:
	ruff check .
	mypy src/jbspan

format:
	ruff format .
	ruff check --fix .

smoke:
	python -m jbspan.cli smoke
