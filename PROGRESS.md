# PROGRESS.md

Current status, session log and Azure cost ledger. Read at the start of every Claude Code session; update at the end.

---

## Current position

- **Next:** Day 1 — first end-to-end run (see `PLAN.md`)
- **Azure spent:** 0.00 / 20 CHF
- **Blocking:** Groq API key not yet in `config.yml` (Day 1, manual step)

## Status snapshot

- Repo cloned to `C:\Users\julia\salesforce-field-description-audit`; venv with `pyyaml`, `requests`, `openpyxl`
- Free LLM is the **Groq free tier** (open-weight models). Ollama was installed but never used and is dropped — not enough disk space
- `config.yml` is local and still points to Ollama; switch it to Groq on Day 1 (see `config.example.yml`)
- Scripts, prompts, synthetic training and test sets, wikis, licence (Apache 2.0) all committed
- **Neither script has run yet.** Files in `data/` named `sf_classified.json`, `llm_response.json`, `review_queue_*`, `write_log_*` are placeholders
- Known bugs from code review, not yet fixed — see `CLAUDE.md`, "Known open bugs"

## Open decisions

- Config shape for real orgs (proposed: `source: file | org`, `write_back: off | export | deploy`, `salesforce.target_org`) — decide at the start of Day 8
- Default Azure model and recommended Groq model — decide on Day 6 from measured results

---

## Azure cost ledger

| Date | Day | Model | Dataset | Fields sent | Tokens in / out | Cost CHF | Running total |
|---|---|---|---|---|---|---|---|
| | | | | | | | 0.00 |

## Results log

Classifier accuracy and suggestion quality per iteration (filled from Day 1).

| Date | Provider / model | Change | Classifier match | Prompt A pass | Prompt B pass | Prompt C rewrites | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## Dataset label changes

Any change to `_expected_status` / `_expected_rule`, with reason.

| Date | Field | Old | New | Reason |
|---|---|---|---|---|
| | | | | |

---

## Session log (most recent first)

### 2026-10-22 — Groq replaces Ollama; docs aligned
- Ollama dropped for lack of disk space (never run). Free option is now the Groq free tier: open-weight models, OpenAI-compatible, no code change needed (`provider: openai`)
- AOAI API Simulator also dropped: it returns fake responses, so it can't be used to judge prompt quality
- Updated README, `config.example.yml`, `requirements.txt`, wikis 01/02/03/05, `CLAUDE.md`, `PLAN.md`, `ONBOARDING.md`
- Fixed stale architecture in wikis 01, 02, 03, 05: they still described `PASSED` and ten rules; now `REVIEWED`, nine rules, three prompts. Wiki 02 now explains why there is no ambiguity rule
- Fixed `config.example.yml`: the OpenAI endpoint example would have produced `/v1/v1/...`
- Fixed `.gitignore`: the `venv/` line had been written in UTF-16 and was ignored by Git; added `data/description_cache.json`
- `ONBOARDING_Johann.md` removed; `ONBOARDING.md` replaces it

### 2026-10-22 — Planning
- Decided to finish the project to a handoff-ready state before withdrawing from the Salesforce space
- Real-org testing will use a free Salesforce Developer Edition org (personal sign-up), which covers both read-only ingestion and write-back
- Wrote `PLAN.md` (12 days); updated `CLAUDE.md`, `ONBOARDING.md` and this file for Claude Code sessions
- Azure budget set at 20 CHF; budget alerts at 15 and 20 CHF to be set in Azure Cost Management
- Code review found bugs: field-name collisions, deduplication losing results, stale cache after prompt changes

### Setup session
- Cloned repo, installed GitHub CLI, created venv, installed dependencies
- Installed Ollama (later dropped) and Claude Code; added Claude Code to PATH
- Confirmed `config.yml` is ignored by Git
