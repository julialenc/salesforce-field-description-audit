# Contributing

Contributions are welcome. This document explains how to contribute effectively.

---

## Before You Start

Read the wiki before opening an issue or submitting a pull request:

- `wiki/02_how_it_works.md` — pipeline logic and classifier rules
- `wiki/03_experiment_and_validation.md` — how to validate changes using the training and test sets
- `wiki/05_architecture_and_reproducibility.md` — what is stable core vs swappable seam

Understanding the design intent will save you time and make your contribution easier to review.

---

## What Contributions Are Welcome

**Most welcome:**
- Improvements to classifier rules (R1–R9) — better precision, fewer false positives
- Improvements to prompt quality (Prompt A, B, C) — higher Admin approval rate
- Additional LLM provider implementations (Bedrock, Vertex AI stubs are ready for completion)
- Salesforce Tooling API and Metadata API implementation (stubs with guidance are in the scripts)
- Bug fixes
- Documentation improvements

**Not in scope (for now):**
- Changing the core status model (FLAGGED / UNCERTAIN / REVIEWED / SKIPPED)
- Changing the two-script pipeline structure
- Adding a UI or web interface (planned for a future stage)
- Adding dependencies beyond the minimal set in `requirements.txt`

---

## How to Contribute

### 1. Open an issue first

For anything beyond a small bug fix, open an issue before writing code. Describe what you want to change and why. This avoids wasted effort if the change is out of scope or conflicts with planned work.

### 2. Fork and branch

Fork the repository and create a branch from `main`. Use a descriptive branch name:

```
classifier/fix-r7-false-positive-on-common-acronyms
prompts/improve-prompt-c-keep-threshold
providers/implement-bedrock
```

### 3. Make your changes

Keep changes focused. One logical change per pull request.

If you change the classifier, validate it against the training set:
- Run Script 1 with `data/sf_metadata_raw_training.json`
- Check `data/sf_classified.json` against the `_expected_status` and `_expected_rule` fields
- All training set fields must classify correctly before submitting

If you change a prompt, evaluate LLM output quality against the criteria in `wiki/03_experiment_and_validation.md`.

### 4. Do not commit secrets

`config.yml` is in `.gitignore`. Never commit credentials, API keys, or Salesforce authentication details. If you add new configuration keys, add them to `config.example.yml` with placeholder values and clear comments.

### 5. Submit a pull request

Open a pull request against `main`. In the description, explain:
- What you changed and why
- How you validated the change (classifier test results, prompt evaluation, etc.)
- Any known limitations or trade-offs

---

## Code Style

- Python 3.10+
- No external dependencies beyond those in `requirements.txt` unless strictly necessary
- Functions should be small and named for what they do, not how they do it
- All classifier rule implementations go in `01_ingest_classify_send.py` alongside the existing rules
- All new prompt assets go in `prompts/` as Markdown or JSON files, not embedded in code

---

## Attribution

This project is licensed under the Apache License 2.0. See `LICENSE` and `NOTICE` for details.

By contributing, you agree that your contributions will be licensed under the same licence.
