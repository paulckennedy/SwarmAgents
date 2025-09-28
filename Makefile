PYTHON := $(shell which python3 || which python)
DAYS ?= 30

.PHONY: list-runs list-last prune dry-prune

list-runs:
	$(PYTHON) scripts/list_runs.py --pattern job_

list-last:
	$(PYTHON) scripts/list_runs.py --pattern last_job_

prune:
	$(PYTHON) scripts/prune_runs.py --days $(DAYS)

dry-prune:
	$(PYTHON) scripts/prune_runs.py --days $(DAYS) --dry-run
