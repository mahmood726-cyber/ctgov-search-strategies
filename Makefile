.PHONY: install dev test lint typecheck format docs clean

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=. --cov-report=html

lint:
	flake8 *.py tests/

typecheck:
	mypy *.py --ignore-missing-imports

format:
	black *.py tests/
	isort *.py tests/

docs:
	mkdocs serve

docs-build:
	mkdocs build

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov .coverage *.egg-info build dist
