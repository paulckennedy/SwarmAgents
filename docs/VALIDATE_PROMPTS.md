# prompts.json validator

This project includes a small validator for `prompts.json` files. It is implemented in `scripts/validate_prompts.py` and can be run either as a module or as a script:

- Module form (requires `scripts` package):

```sh
PYTHONPATH=. python -m scripts.validate_prompts --paths prompts.json --report-json validation-report.json
```

- Script form (works regardless of package layout):

```sh
PYTHONPATH=. python scripts/validate_prompts.py --paths prompts.json --report-json validation-report.json
```

CI notes
- The GitHub Actions workflow `.github/workflows/ci.yml` runs the validator during the `test-and-validate` and `prompt-validation` jobs.
- The workflow caches pip packages using `actions/cache` for faster runs.
- During `prompt-validation` the job writes `validation-report.json` and uploads it only when validation fails.

Autofix
- The validator can attempt safe autofixes with `--autofix`. When autofix changes are made, the CI job will create a pull request with the fixes (using `peter-evans/create-pull-request`).

Local troubleshooting
- If imports fail when running tests locally, run:

```sh
export PYTHONPATH=.
python -m pytest -q
```

Contact
- If you prefer the validator to always be invoked as `python -m scripts.validate_prompts` instead of the script form, the repository includes an empty `scripts/__init__.py` to support module-style invocation.
