# PROGRESS.md

Lightweight running log of project status and session history. **Not auto-loaded by Claude Code** — kept separate from `CLAUDE.md` on purpose to save tokens. Ask Claude Code to read this explicitly when resuming work after a break ("read PROGRESS.md first").

---

## Current focus

Setting up the local environment and preparing to run Script 1 for the first time against the training set.

---

## Status snapshot

- Repo cloned locally to `C:\Users\julia\salesforce-field-description-audit`
- Python venv created, dependencies installed (`pyyaml`, `requests`, `openpyxl`)
- Ollama installed locally, model `llama3.2:3b` pulled
- `config.yml` created locally, set to `mode: experiment`, provider `ollama`, `experiment_file: data/sf_metadata_raw_training.json`
- `venv/` added to `.gitignore`
- **Script 1 has not been run yet.** No `sf_classified.json`, `llm_response.json`, or `review_queue_*.xlsx` exist yet.
- `CLAUDE.md` and this file created and committed to root

---

## Session log (most recent first)

### Setup session
- Cloned repo from GitHub to local machine
- Installed GitHub CLI, Git for Windows already present
- Created Python venv, installed the three experiment-mode dependencies
- Installed Ollama, worked through PATH issue (new terminal needed after winget install)
- Hit a machine slowdown running the full `llama3` (8B) model — switched to `llama3.2:3b` for local testing to keep resource usage manageable
- Installed Claude Code natively on Windows, resolved PATH issue with a permanent PATH addition
- Confirmed `config.yml` correctly gitignored; added missing `venv/` entry to `.gitignore` and committed that fix
- Created `CLAUDE.md` and `PROGRESS.md` for Claude Code sessions going forward

**Next session should start with:** running Script 1 against the training set, then working through classifier validation as described in `CLAUDE.md`'s "Typical session flow."
