PY ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYBIN := $(VENV)/bin/python

.PHONY: all venv install install-ml install-all test lint clean sources probe run

all: install

$(VENV)/bin/activate:
	$(PY) -m venv $(VENV)
	$(PIP) install -U pip wheel

venv: $(VENV)/bin/activate

install: venv
	$(PIP) install -e .[dev]

install-ml: venv
	$(PIP) install -e .[dev,ml]

install-all: venv
	$(PIP) install -e .[dev,ml,streams]

test:
	$(PYBIN) -m pytest

lint:
	$(VENV)/bin/ruff check src tests

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache $(VENV)
	find . -name __pycache__ -type d -exec rm -rf {} +

sources:
	$(PYBIN) -m planetar_eo sources --config configs/sources.victoria.yaml

probe:
	$(PYBIN) -m planetar_eo probe --config configs/sources.victoria.yaml --source chek.shipspoint

run:
	$(PYBIN) -m planetar_eo run --config configs/sources.victoria.yaml --broker 127.0.0.1:12001
