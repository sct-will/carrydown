# Workflow files waiting to be moved

These two files are GitHub Actions workflows. They belong in `.github/workflows/`, where GitHub runs them.

- `ci.yml` runs `python3 scripts/selftest.py` on every push and pull request. It checks the sample against its plan and runs every script's `--help` and dry run. It needs no token.
- `prose.yml` runs `python3 scripts/lint_prose.py` on every push and pull request. It checks for dashes, credit lines and vendor names outside the install instructions.

They sit here because the token that published this repository could not create files under `.github/workflows/`. The owner should move them with a token or a browser session that has the `workflow` permission:

```bash
mkdir -p .github/workflows
git mv docs/workflows/ci.yml docs/workflows/prose.yml .github/workflows/
git rm docs/workflows/README.md
```

Then delete the sentence about this folder from the Contributing section of the main README.
