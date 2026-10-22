# CLAUDE.md

Read automatically by Claude Code at the start of every session in this folder. Stable facts only — current status lives in `PROGRESS.md`, the work plan in `PLAN.md`.

---

## What this project is

A pipeline that audits Salesforce field descriptions at scale: classifies description quality with rule-based checks, uses an LLM to draft rewrites, presents them for human review in Excel, and writes approved changes back only after explicit Admin approval. File-in, file-out; no UI, no database.

## Start of every session

1. Read `PROGRESS.md` (current day, last session, open items, Azure spend)
2. Read the current day's section of `PLAN.md`
3. State in one or two lines what this session will do, then start

## End of every session

Update `PROGRESS.md`: tick finished items in `PLAN.md`, add a session-log entry (what was done, what was decided and why, what's next), and add any paid run to the cost ledger. Then propose a commit message — do not commit without being asked.

---

## Architecture facts — do not get these wrong

- **Four statuses:** `FLAGGED`, `UNCERTAIN`, `REVIEWED`, `SKIPPED`. There is no `PASSED`; any file using it is stale.
- **Nine rules, R1–R9.** R10 ("ambiguous") was removed on purpose — ambiguity is judged by the LLM via Prompt C. Do not add it back. Reasoning: end of `wiki/02_how_it_works.md`.
- **Two steps:** SKIPPED check first → R1–R5 can only give `FLAGGED` → R6–R9 can only give `UNCERTAIN` → nothing fired gives `REVIEWED`. First rule to fire wins.
- **Three prompts:** `FLAGGED` → Prompt A (always rewrite) · `UNCERTAIN` → Prompt B (R6 shortens, R7–R9 rewrite) · `REVIEWED` → Prompt C (conservative, default keep) · `SKIPPED` → no LLM.
- **Review file tabs:** Tab A = FLAGGED · Tab B = UNCERTAIN plus REVIEWED fields the LLM proposes to rewrite · Tab C = reference (REVIEWED kept, SKIPPED).
- **Two datasets:** `data/sf_metadata_raw_training.json` (288 fields, iterate freely) and `data/sf_metadata_raw_test.json` (144 fields, run once, never tune on it). `_expected_status` / `_expected_rule` in each field are the ground truth.

Design reasoning: `wiki/02_how_it_works.md`, `wiki/03_experiment_and_validation.md`, `wiki/05_architecture_and_reproducibility.md`. Read them for context; don't restate them.

---

## Known classifier fixes — do not revert

1. No bare `"na"` in `PLACEHOLDER_TOKENS` (it matched inside "inactive", "international").
2. Date/DateTime "range" and Email "list" patterns belong to R8, not R3.
3. R2 skips placeholder text so `"TBD"` reaches R5.
4. `YYYY`, `MM`, `DD`, `HH`, `UTC`, `ISO` are on the R7 allow-list.

After touching any rule function, re-run the classifier validator and unit tests.

## Known open bugs (Day 1 and Day 3)

- **Field-name collisions:** LLM results are keyed by `field_api_name` alone. Fields with the same name on different objects (e.g. `Description` on Account and Opportunity in the test set) overwrite each other. Key by `object.field_api_name` everywhere.
- **Deduplication loses results:** `sort_and_deduplicate()` drops duplicate fields from the map that `save_llm_response()` uses to copy results back, so duplicates end up with no suggestion.
- **Rate limits:** an HTTP 429 currently marks the whole batch as `llm_error`. Wait and retry instead.
- **Leftover provider names:** Script 1 still defaults to `aoai_simulator` and accepts `ollama`. Both are dropped; default is `openai`.
- **Stale cache (Day 3):** the cache key is the description hash only, so after a prompt or model change, re-runs return old answers. Add a hash of the prompt files and the model name.

---

## Environment (Julia's Windows machine)

- **Repo root:** `C:\Users\julia\salesforce-field-description-audit`
- **Python 3.12, venv at `venv\`.** Call the venv interpreter directly: `venv\Scripts\python.exe scripts\01_ingest_classify_send.py`
- **Julia's terminal is CMD, not PowerShell.** Commands you give her to type must be CMD syntax (`type`, `dir`, `copy`, `&&`).
- **Limited disk space** — no local LLMs, no large downloads.
- **Free LLM: Groq free tier.** OpenAI-compatible: `provider: openai`, `endpoint: https://api.groq.com/openai`, an open-weight model from Groq's model list. Limited requests and tokens per minute and per day: on HTTP 429 wait and retry, or lower `llm_batch_size`.
- **Paid LLM: Azure OpenAI** (`provider: azure_openai`), configured in `config.yml` when needed.
- **Salesforce CLI** (`sf`) and a free Developer Edition org with alias `sfdesc-dev` from Day 7 on. Login happens in the browser; no passwords in config.
- **`config.yml` is secret.** Never print it whole, never commit it. Read single keys if needed.

---

## Guardrails

**Proceed freely:** runs on the Groq free tier with synthetic data, editing the file in scope, running tests and validators, reading files, inspecting output.

**Ask first when an action would:**
- **Touch other files** beyond the one in scope (e.g. a classifier fix that also needs a wiki change) — name the ripple, confirm, then do it
- **Cost money** — any Azure run. Before asking, state: model, number of fields and batches, estimated cost, and remaining budget from the ledger
- **Change a Salesforce org** `[ORG-WRITE]` — any deploy, including seeding the demo org and write-back. Show what will change first

**Always ask:**
- `git add` / `git commit` / `git push`
- Changing the four statuses, the R1–R9 rule set or the three-prompt routing
- Changing a dataset label (`_expected_status` / `_expected_rule`) — log the reason in `PROGRESS.md`
- `LICENSE`, `NOTICE`, or the licence lines in `README.md` / `CONTRIBUTING.md`
- New dependencies in `requirements.txt` (experiment mode stays at `pyyaml`, `requests`, `openpyxl`; the Salesforce CLI is called as a subprocess, not via a Python package)

**Hard limits:**
- Azure budget is **20 CHF total**. Stop at 15 CHF spent and ask how to use the rest
- **Never send real org metadata to Groq** or any other free tier — real org data goes to Azure only
- Never deploy to any org other than `sfdesc-dev` unless Julia names it explicitly

---

## Style

Julia makes precise, deliberate decisions and wants trade-offs surfaced, not decided silently. Be concise. Propose specific changes with a one-line reason. Report results as numbers (accuracy, pass rate, cost), not impressions.
