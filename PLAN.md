# PLAN.md — Plan to a Handoff-Ready Project

**Goal:** someone with a Salesforce sandbox and basic Python can clone the repo and run the full pipeline against their own org, with very little left to build.

**Finished means:**
- Runs end to end on synthetic data, on a free open-weight model (Groq) and on Azure
- Classifier and prompts meet the Definition of Done in `wiki/03_experiment_and_validation.md`, with results published
- Tested against a real Salesforce org (free Developer Edition): read-only ingestion and write-back
- One setup check, simple commands, no passwords in `config.yml`
- Docs match the code; the README quickstart works from a fresh clone

**How to use this file:** one Day = one Claude Code session (roughly 2–4 hours). Days are sequential, but there is no deadline. Tick boxes as work is done. `PROGRESS.md` records the current day, the session log and the Azure cost ledger.

**Tags:** `[FREE]` no cost (local work or Groq free tier) · `[PAID ~x CHF]` Azure calls · `[MANUAL]` Julia does this outside Claude Code · `[ORG-WRITE]` changes a Salesforce org — always confirm first

**LLM providers:**
- **Groq free tier** — open-weight models (e.g. Llama 3.3 70B), free key, no credit card, nothing to install. The reproducible default: anyone can rerun the experiment. Rate-limited per minute and per day. Synthetic data only.
- **Azure OpenAI** — paid, company-approved. Used for model comparison, cost measurement and any run on real org metadata.

---

## Azure budget: 20 CHF

| Allocation | CHF |
|---|---|
| Day 3 — calibration run | 1 |
| Days 4–5 — prompt iteration | 8 |
| Day 6 — model comparison + test set | 5 |
| Day 8 — run on real org data | 2 |
| Reserve | 4 |
| **Total** | **20** |

Rough expectation: one full training-set run (about 270 fields sent to the LLM) costs cents on a small model and well under 1 CHF on a large one. Day 3 replaces this guess with a measured number, and the table is adjusted then. Prompt iteration can also be done on Groq for free, which stretches the budget further.

`[MANUAL]` In Azure Cost Management, set budget alerts at 15 and 20 CHF. These are alerts, not a hard stop — the ledger in `PROGRESS.md` is the real control.

---

## Day 1 — First end-to-end run `[FREE]`

- [ ] `[MANUAL]` Create a free Groq key at console.groq.com; put it in `config.yml` (provider `openai`, endpoint `https://api.groq.com/openai`, an open-weight model from Groq's list)
- [ ] Fix two bugs already found by reading the code (details in `CLAUDE.md`, "Known open bugs"): LLM results keyed by field name only; deduplicated fields losing their result
- [ ] Remove leftover `ollama` / `aoai_simulator` provider names from Script 1; default provider becomes `openai`
- [ ] Handle rate limits: on HTTP 429, wait and retry instead of marking the whole batch as failed
- [ ] Run Script 1 on the training set; fix whatever else breaks. If rate limits keep hitting, lower `llm_batch_size` (try 15)
- [ ] Add `scripts/validate_classifier.py`: compares `sf_classified.json` with `_expected_status` / `_expected_rule`, prints accuracy per rule and lists every mismatch
- [ ] Move the 22 classifier unit tests into `tests/test_classifier.py`, runnable with plain `python` (no new dependency)

**Done when:** Script 1 completes and produces all three outputs, and the mismatch list exists.

## Day 2 — Classifier to Definition of Done `[FREE]`

- [ ] Work through mismatches one by one. Default is to fix the classifier. Change a dataset label only when it contradicts the rule definitions in `wiki/02_how_it_works.md` — ask first, and log each label change with its reason in `PROGRESS.md`
- [ ] Re-run the validator and unit tests after every classifier change
- [ ] Fill a few rows of the review queue by hand (Approve / Edit / Reject) and run Script 2 to prove the second half works

**Done when:** 100% classifier match on the training set (or each remaining mismatch documented and accepted), and Script 2 produces a write log.

## Day 3 — Cost tracking, cache fix, first Azure run `[PAID ~1 CHF]`

- [ ] Fix the cache key. Today it uses only the description hash, so after a prompt or model change, re-runs silently return old LLM answers. Include a hash of the prompt files and the model name
- [ ] Log token usage per batch from the API response; save totals in `llm_response.json`; print a run summary with estimated cost (per-1M-token prices set in `config.yml`)
- [ ] Before every run, print how many fields and batches will be sent to the LLM
- [ ] `[MANUAL]` Create Azure deployments for one small and one large model; put endpoint and key in `config.yml` (never commit)
- [ ] One training-set run with the small model; record it in the cost ledger

**Done when:** measured cost per 1,000 fields is in `PROGRESS.md`, and the budget table is adjusted if needed.

## Day 4 — Automatic quality check for suggestions `[FREE build, PAID ~3 CHF runs]`

- [ ] Add `scripts/evaluate_suggestions.py`. It runs every LLM suggestion back through the classifier — a good suggestion should come out `REVIEWED` — plus the checks in wiki 03: 30–255 characters, no forbidden terms, all picklist values present, R6 output actually shorter. Report pass rate per prompt (A / B / C) and per rule
- [ ] Iterate on Prompt A and Prompt B until the pass rate stops improving. Use Groq for most iterations (free), Azure to confirm

**Done when:** the pass rate per prompt is recorded for each iteration in `PROGRESS.md`.

## Day 5 — Prompt C and human review `[PAID ~5 CHF]`

- [ ] Iterate on Prompt C (keep vs. rewrite). Track how many `REVIEWED` fields it rewrites — it should stay conservative, and still catch the subtly vague descriptions in the dataset
- [ ] `[MANUAL]` Review a 40-field sample in Excel across all tabs; compute the approval rate

**Done when:** Phase 1 Definition of Done in wiki 03 is met (at least 80% of Tab A suggestions approvable without editing).

## Day 6 — Model choice and test set `[PAID ~5 CHF]`

- [ ] Run the final prompts on 2–3 models, including one free open-weight model on Groq so anyone reproducing without Azure knows what to expect. Table: automatic pass rate, sample approval rate, cost per 1,000 fields, run time
- [ ] Pick the default Azure model and the recommended Groq model; record why
- [ ] Run the test set **once** with the chosen setup — no tuning afterwards
- [ ] Fill in the Training Set Results and Test Set Results sections of wiki 03

**Done when:** results are published in wiki 03 and the recommended models are in `config.example.yml`.

## Day 7 — Free Salesforce org and demo data `[FREE]` `[ORG-WRITE]`

- [ ] `[MANUAL]` Sign up for a Developer Edition at developer.salesforce.com/signup (personal email; Company: "Personal"). Install the Salesforce CLI. Run `sf org login web --alias sfdesc-dev`
- [ ] Add `scripts/seed_demo_org.py`: generates Salesforce metadata for the training set's custom fields, including their deliberately messy descriptions, and deploys them with the CLI. Skip standard and system fields. Handle types that need extra settings (formulas, lookups, picklists)
- [ ] Deploy to the dev org — confirm first
- [ ] Spot-check a few fields in Setup. Also check the real maximum length of a field description; if it isn't 255, update docs and validation

**Done when:** the seeded fields are visible in the dev org.

## Day 8 — Read-only ingestion from a real org `[FREE, optional PAID ~2 CHF]`

- [ ] At the start, agree the config shape. Proposal: `source: file | org` and `write_back: off | export | deploy` replace the mixed `mode` setting; `salesforce.target_org: sfdesc-dev` replaces username, password and token
- [ ] Implement ingestion by calling the Salesforce CLI from Python (no new Python dependency): descriptions, field types, picklist values, formulas, lookup targets
- [ ] Parity test: classification from the org must match classification from the training JSON for every seeded field
- [ ] One full run on org data with a small Azure model (org metadata does not go to free tiers)

**Done when:** the parity test passes.

## Day 9 — Write-back `[FREE]` `[ORG-WRITE]`

- [ ] `write_back: export` (default): Script 2 writes approved descriptions to a CSV the Admin can apply by hand
- [ ] `write_back: deploy` (opt-in): retrieve each field's metadata, change only the description, deploy — confirm before deploying
- [ ] Test on the dev org: approve 5–10 changes, deploy, check them in Setup and in the write log. Also test that a failure (e.g. a field that no longer exists) is logged and does not stop the run
- [ ] Add a way to reset the demo org to the original messy descriptions, so the demo can be re-run

**Done when:** approved descriptions are verified in the org, and the reset works.

## Day 10 — Make it easy to run `[FREE]`

- [ ] Add `scripts/check_setup.py`: checks Python version, packages, config, LLM connection, CLI installed and logged in — with a plain-English fix for each failure
- [ ] Friendly error messages in both scripts; no raw tracebacks for common mistakes
- [ ] Simplify `config.example.yml`: only LLM settings and target org need filling in; everything else has defaults
- [ ] Trim `requirements.txt`: drop `simple-salesforce`; keep cloud SDKs as clearly optional
- [ ] Mark Bedrock and Vertex AI clearly as not implemented, or remove them

**Done when:** from a fresh clone on your machine, `check_setup` passes in under 15 minutes.

## Day 11 — Docs and handoff package `[FREE]`

- [ ] Update README and all wikis to match what was built (CLI login, export/deploy, demo org, results)
- [ ] README: honest status, "Try it in 10 minutes on a free org" quickstart, results, cost per 1,000 fields; remove the WIP banner
- [ ] Final `ONBOARDING.md` for the next maintainer
- [ ] `ROADMAP.md` and 4–6 GitHub issues for what's left
- [ ] Replace stale placeholder outputs in `data/` with a clean sample run from the demo org

**Done when:** no document contradicts the code.

## Day 12 — Fresh-clone rehearsal and release `[FREE]`

- [ ] Clone into a new folder, follow the README only, time each step, fix any friction
- [ ] Tag release `v0.1.0`
- [ ] Mark the repo "seeking maintainer"; post once in Salesforce communities with the results

**Done when:** a stranger could follow the README without asking anything.

---

## Deliberately left for the next maintainer

Web UI or AppExchange package · Bedrock and Vertex AI providers · scheduled runs · performance on very large orgs
