# ONBOARDING.md

For a person picking up this project — a future maintainer, or Julia after a long break. Claude Code sessions use `CLAUDE.md`, `PROGRESS.md` and `PLAN.md` instead.

---

## What the project is

An open-source pipeline that audits Salesforce field descriptions at scale. A rule-based classifier sorts every description into one of four statuses; an LLM drafts improvements; an Admin approves, edits or rejects each one in Excel; only approved changes reach Salesforce.

Why it matters: Agentforce, Claude and other AI agents read field descriptions to understand an org. Missing, vague or stale descriptions make them guess. This tool fixes descriptions upstream, consistently and under human review, instead of leaving agents to guess at runtime.

## Where it stands

See `PROGRESS.md` for the current day and status. In short, as of October 2026:
- Design, classifier, prompts, synthetic datasets and docs are complete
- The plan in `PLAN.md` takes it from "never run" to "tested end to end on a real Salesforce org, ready for someone else to adopt"

## Read in this order

1. `README.md` — what it does, architecture, quickstart (10 minutes)
2. `wiki/02_how_it_works.md` — classifier rules, LLM routing, review and write-back
3. `PROGRESS.md` — where things stand
4. `PLAN.md` — what's done and what's left

The other wikis are reference: `01` problem and audience, `03` experiment method and results, `04` the Admin's review process, `05` architecture and what is safe to change.

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

- **Free to tune:** prompt wording, classifier patterns (re-run the validator after), batch size, model choice
- **Discuss before changing:** the four statuses, the R1–R9 rule set, the three-prompt routing — they are deliberate design decisions, explained in wiki 02 and 05

## Contact and licence

Created by Julia Lenc. Apache License 2.0 — keep `LICENSE` and `NOTICE` in any copy or fork. Contributions: see `CONTRIBUTING.md`.
