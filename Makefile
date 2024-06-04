.PHONY: format check-formatting check-types lint

format:
	poetry run black babies

check-formatting:
	poetry run black --check .

check-types:
	poetry run mypy --check-untyped-defs --ignore-missing-imports babies

lint:
	poetry run flake8 babies
