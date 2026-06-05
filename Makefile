VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PGA ?= $(VENV)/bin/pga
ARTEMIS ?= $(VENV)/bin/artemis
BOOTSTRAP_PYTHON ?= python3
TICKET ?= T-0019
CONTEXT_OUT ?= /tmp/artemis_$(TICKET)_context.json

.PHONY: bootstrap test validate validate-registries validate-work-items validate-kb validate-config validate-skills validate-views validate-data-sources capabilities validate-artemis work-context agent-capabilities agent-doctor vcs-ready release-check clean-local reset-venv

bootstrap:
	./scripts/bootstrap_dev.sh

test: bootstrap
	$(PYTHON) -m pytest -q

validate-registries: bootstrap
	$(PGA) validate-registries

validate-work-items: bootstrap
	$(PGA) validate-work-items

validate-kb: bootstrap
	$(PGA) validate-kb

validate-config: bootstrap
	$(ARTEMIS) config validate

validate-skills: bootstrap
	$(ARTEMIS) skill validate

validate-views: bootstrap
	$(ARTEMIS) views validate

validate-data-sources: bootstrap
	$(ARTEMIS) data-sources validate

capabilities: bootstrap
	$(ARTEMIS) capabilities

validate-artemis: validate-config validate-skills validate-views validate-data-sources capabilities

validate: bootstrap
	$(ARTEMIS) validate

work-context: bootstrap
	$(PGA) work-context --ticket $(TICKET) --output $(CONTEXT_OUT)

agent-capabilities: bootstrap
	$(PGA) agent-capabilities

agent-doctor: bootstrap
	$(PGA) agent-doctor

vcs-ready: bootstrap
	$(PGA) vcs-ready --ticket $(TICKET)

release-check: bootstrap
	$(PGA) release-check --ticket $(TICKET)

clean-local:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

reset-venv:
	rm -rf $(VENV)
	$(MAKE) bootstrap
