# Makefile for aws-auth
# Provides unified commands for development, testing, security scanning, and building.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Detect virtual environment or system Python
VENV ?= venv
ifeq ($(wildcard $(VENV)/bin/python),)
    PYTHON ?= python3
    PIP ?= pip3
    PYTEST ?= pytest
    BANDIT ?= bandit
    PIP_AUDIT ?= pip-audit
else
    PYTHON ?= $(VENV)/bin/python
    PIP ?= $(VENV)/bin/pip
    PYTEST ?= $(VENV)/bin/pytest
    BANDIT ?= $(VENV)/bin/bandit
    PIP_AUDIT ?= $(VENV)/bin/pip-audit
endif

.PHONY: help
help: ## Display this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: ## Create virtual environment and install all dependencies
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip setuptools wheel
	$(VENV)/bin/pip install -r requirements.txt -r requirements-dev.txt
	$(VENV)/bin/pip install -e .
	$(VENV)/bin/python scripts/check_credentials.py --install-hook
	@echo "✅ Virtual environment created. Activate with: source $(VENV)/bin/activate"

.PHONY: install-dev
install-dev: ## Install package in editable mode with development dependencies and git hooks
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	$(PIP) install -e .
	$(PYTHON) scripts/check_credentials.py --install-hook
	@echo "✅ Development dependencies and git hooks installed."

.PHONY: test
test: ## Run unit tests with pytest
	$(PYTEST) -v

.PHONY: check-secrets
check-secrets: ## Scan entire repository for credentials, secrets, and policy violations
	$(PYTHON) scripts/check_credentials.py --all

.PHONY: check-commits
check-commits: ## Inspect recent commit messages and diffs for secrets/blocked terms
	$(PYTHON) scripts/check_credentials.py --check-commits 5

.PHONY: lint
lint: ## Run Bandit SAST security analyzer on source files
	$(BANDIT) -r aws_auth scripts -ll

.PHONY: audit
audit: ## Audit dependencies for known vulnerabilities (pip-audit)
	$(PIP_AUDIT) -r requirements.txt -r requirements-dev.txt --desc on

.PHONY: check
check: check-secrets lint audit test ## Run full quality suite (secrets, SAST lint, audit, tests)
	@echo "🛡️  All quality, security, and test checks passed successfully!"

.PHONY: build
build: ## Compile PyInstaller standalone binary and update system install
	./install.sh

.PHONY: clean
clean: ## Remove build artifacts, distribution packages, and python caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "🧹 Clean completed."
