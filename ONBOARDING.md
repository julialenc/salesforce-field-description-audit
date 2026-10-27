# ONBOARDING.md

For a person picking up this project — a future maintainer, or Julia after a long break.

---

## What the project is

An open-source pipeline that audits Salesforce field descriptions at scale. A rule-based classifier sorts every description into one of four statuses; an LLM drafts improvements; an Admin approves, edits or rejects each one in Excel; only approved changes reach Salesforce.

Why it matters: Agentforce, Claude and other AI agents read field descriptions to understand an org. Missing, vague or stale descriptions make them guess. This tool fixes descriptions upstream, consistently and under human review, instead of leaving agents to guess at runtime.

## Where it stands

As of late October 2026:
- The pipeline runs end to end on the synthetic training set, on Groq's free tier and on Azure OpenAI
- Classifier: 279 of 288 training fields match their labels; the 9 accepted limits are listed in wiki 03
- Prompts: an automatic check scores every LLM suggestion; current pass rates are in wiki 03
- In progress: human review of a suggestion sample, model choice, the one-time test-set run, testing on a real Salesforce org, and a first release. Remaining work will be listed in `ROADMAP.md` and as GitHub issues

## Read in this order

1. `README.md` — what it does, architecture, quickstart (10 minutes)
2. `wiki/02_how_it_works.md` — classifier rules, LLM routing, review and write-back

The other wikis are reference: `01` problem and audience, `03` experiment method and results, `04` the Admin's review process, `05` architecture and what is safe to change, `06` lessons learned while building it (worth reading if you are new to building LLM pipelines).

## Key concepts

- **Statuses:** `FLAGGED` (clear failure, rules R1–R5) · `UNCERTAIN` (possible issue, R6–R9) · `REVIEWED` (no rule fired; the LLM decides whether to keep it) · `SKIPPED` (system field, untouched)
- **Prompts:** A rewrites FLAGGED fields, B fixes UNCERTAIN fields, C reviews the rest conservatively
- **Datasets:** a training set (288 fields) for development, and a test set (144 fields) run once for validation. Both are synthetic, for a fictional mountain-equipment retailer
- **Safety:** nothing is written to Salesforce without an explicit Approve or Edit decision in the review file

## Running it

Follow the README quickstart. You need Python 3.10+, Git, and an LLM API key:
- **Groq** (free) — open-weight models, no credit card, nothing to install. For the synthetic datasets
- **Azure OpenAI** (paid) or another company-approved provider — for anything involving a real org's metadata

For real-org use, also the Salesforce CLI and a sandbox or free Developer Edition org — never start on production.

## What is safe to change

- **Free to tune:** prompt wording, classifier patterns, batch size, model choice. After any change, run the checks below
- **Prompt examples** must be invented fields that appear in no dataset, or results stop meaning anything
- **Discuss before changing:** the four statuses, the R1–R9 rule set, the three-prompt routing — they are deliberate design decisions, explained in wiki 02 and 05

## Checking a change

None of these call an LLM:
```
python tests/test_classifier.py
python tests/test_cache.py
python tests/test_context.py
python tests/test_evaluate.py
python scripts/validate_classifier.py data/sf_metadata_raw_training.json
python scripts/evaluate_suggestions.py
```
The last one scores the most recent Script 1 run; add `--failures` to see each failed suggestion, or `--assumptions` to see what the model guessed or could not know.

The automatic check cannot tell whether a suggestion is true. For that, draw a human review sample from the latest review file, fill in the decisions in Excel, and score it:
```
python scripts/review_sample.py make
python scripts/review_sample.py score data/review_sample_<timestamp>.xlsx
```
After a prompt change, `python scripts/review_sample.py rereview <filled-in sample>` puts the same rows next to the newest review file and keeps the decisions of rows that did not change, so only the changed rows need a person again. If the run used an org context file, review with that file at hand.

Two optional inputs in `config.yml` give the model more to work from: `options.neighbour_fields` (other fields on the same object with a shared name word) and `options.org_context_file` (a short glossary the Admin writes once; `data/org_context_synthetic.md` is the example for the synthetic org). Both are off by default; wiki 03, "Day 6", has what they changed.

## Contact and licence

Created by Julia Lenc. Apache License 2.0 — keep `LICENSE` and `NOTICE` in any copy or fork. Contributions: see `CONTRIBUTING.md`.
