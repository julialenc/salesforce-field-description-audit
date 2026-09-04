# CLAUDE.md

This file is read automatically by Claude Code at the start of every session in this folder. It is the project's working memory — read it before doing anything else.

---

## What this project is

A pipeline that audits Salesforce field descriptions at scale: classifies description quality with rule-based checks, uses an LLM to draft rewrites, presents them for human review in Excel, and writes approved changes back to Salesforce only after explicit Admin approval. Nothing touches Salesforce without a human decision.

Two scripts, five prompt files, synthetic training/test datasets. No web UI, no database — file-in, file-out pipeline.

---

## Read first, don't re-derive

Before proposing any architectural change, check these — the design decisions in them are settled, not open questions:

- `README.md` — architecture diagram, install, quick start
- `wiki/02_how_it_works.md` — full classifier logic, LLM routing, all 9 rules
- `wiki/03_experiment_and_validation.md` — training/test methodology, Definition of Done
- `wiki/05_architecture_and_reproducibility.md` — what's stable core vs. swappable seam

Do not restate their content back to the user unless asked — read them for context, not to summarize.

For where the project actually stands right now (last run, open threads, what's next), see the Live status note below — that detail lives in a separate file on purpose.

---

## Live status

Point-in-time state (what's been run, what's next, session log) lives in `PROGRESS.md` at repo root — not auto-loaded, kept light on purpose. When resuming work after a break, ask to have it read explicitly rather than assuming it's already in context.

---

## Architecture facts — do not get these wrong

**Four statuses only:** `FLAGGED`, `UNCERTAIN`, `REVIEWED`, `SKIPPED`. There is no `PASSED` status — it was renamed to `REVIEWED` during design. If you see `PASSED` anywhere in a file, that file is stale and needs updating, not the other way around.

**Nine rules, not ten.** R10 ("ambiguous") was deliberately removed from the classifier. Ambiguity judgment moved entirely to the LLM via Prompt C. Do not add an R10 rule back — this was a considered decision (a keyword-based ambiguity detector was tried and rejected as unreliable; see the reasoning trail in `wiki/02_how_it_works.md`).

**Two-step rule structure, strictly enforced:**
- Step 1, Rules R1–R5 → can only produce `FLAGGED`
- Step 2, Rules R6–R9 → can only produce `UNCERTAIN`
- First rule to fire wins; classifier stops immediately
- No rule fires → `REVIEWED`
- System field → `SKIPPED` (checked before any rule)

If you ever touch `_classify_one()` in `scripts/01_ingest_classify_send.py`, this invariant must hold. There's a inline assertion pattern used in testing (see Known Fixes below) — reuse it.

**Three-prompt LLM routing**, not two:
- `FLAGGED` → Prompt A → always rewrites, never evaluates
- `UNCERTAIN` → Prompt B → R6 shortens, R7–R9 rewrite
- `REVIEWED` → Prompt C → conservative, defaults to "keep," only rewrites when clearly inadequate
- `SKIPPED` → never reaches the LLM

**Two datasets, not one:** `data/sf_metadata_raw_training.json` (288 fields, iterate freely) and `data/sf_metadata_raw_test.json` (144 fields, run once, never tune against it). Each field carries `_expected_status` and `_expected_rule` — use these to validate classifier output, don't hand-check.

---

## Environment on this machine (Windows)

**Repo root:** `C:\Users\julia\salesforce-field-description-audit`

**Python:** 3.12, venv already created at `venv\`. When running Python yourself, prefer calling the venv's interpreter directly rather than relying on shell-specific activation syntax:
```
venv\Scripts\python.exe scripts\01_ingest_classify_send.py
venv\Scripts\pip.exe install <package>
```
This sidesteps CMD/PowerShell/Git-Bash activation differences entirely.

**When you give the user a command to type manually:** the user works in **CMD, not PowerShell**. Give CMD-flavored syntax (`&&` for chaining, `dir` not `ls`, `type` not `cat`). PowerShell-specific commands you propose will fail or behave unexpectedly in her terminal. This does not affect your own tool calls — those run through your own shell tooling independently of what the user's terminal is set to.

**Local LLM:** Ollama running at `http://localhost:11434`, model `llama3.2:3b`. Machine has limited RAM headroom — Ollama running alongside heavy work has caused system slowdown before. If output suggests Ollama is unresponsive or slow, that's a known resource issue, not necessarily a config or code bug.

**`config.yml` — never print its full contents in chat or commit it.** It is gitignored deliberately. It currently holds local Ollama settings (no real secret), but it will later hold a real Azure OpenAI API key when the user switches providers for further testing. Treat it as sensitive by default even when it isn't yet. If you need to check a value in it, read the specific key, don't cat the whole file into the conversation.

---

## Known fixes — do not revert these

Found and fixed during initial classifier testing (22/22 unit tests passing). If you're refactoring the classifier, these are load-bearing:

1. `"na"` was removed from `PLACEHOLDER_TOKENS` — it substring-matched inside `"inactive"`, `"international"`, etc. Do not re-add a bare `"na"` token.
2. Date/DateTime and Email "stores a range / list" patterns live in **R8** (contradictory config), not R3 (wrong type hint). R3 is for obvious type mismatches (Checkbox described as text entry); R8 is for subtler structural contradictions.
3. R2 (echo/too short) explicitly skips text that matches a placeholder pattern, so short placeholder text like `"TBD"` falls through to R5 instead of being caught by R2 first. Order matters here — don't reorder without re-running the unit tests.
4. `YYYY`, `MM`, `DD`, `HH`, `UTC`, `ISO` are in the R7 acronym allow-list — date format strings like `YYYY-MM-DD` should never trigger the jargon rule.

If you touch any of `_is_echo_or_too_short`, `_has_type_mismatch`, `_has_config_contradiction`, or `_has_unexplained_acronym`, re-run the classifier against the training set and confirm every field's `classifier_status` and `rule_triggered` still matches its `_expected_status` / `_expected_rule`.

---

## Guardrails — when to proceed vs. when to ask

**Proceed freely** when an action stays confined to the artifact currently being worked on: running scripts locally against the free local LLM (Ollama), editing the specific script/prompt/file under active discussion, running tests, reading files, inspecting output.

**Ask first** when an action would either:
- **Touch other artifacts** beyond the one currently in scope — e.g. a classifier fix in `scripts/01_ingest_classify_send.py` that also implies updating `wiki/02_how_it_works.md`, a prompt file, or a second script. Flag the ripple effect and confirm before making the cross-file change.
- **Cost money** — any action that calls a paid LLM provider (Azure OpenAI, or any other paid API once configured) instead of the free local Ollama setup. Confirm before running either script against a paid provider.

**Always ask, regardless of scope, for:**
- `git add` / `git commit` / `git push`
- Implementing the Salesforce Tooling API or Metadata API stubs (`_ingest_from_tooling_api()`, `_write_to_salesforce()`) — the bridge to a live org deserves a deliberate conversation, not an incidental implementation
- Changing the four-status model, the R1–R9 rule set, or the three-prompt routing — settled architectural decisions, not defaults to optimize away
- Modifying `LICENSE`, `NOTICE`, or the licensing lines in `README.md` / `CONTRIBUTING.md`
- Adding new dependencies to `requirements.txt` — experiment mode deliberately holds to three packages

---

## Typical session flow right now

1. Run Script 1 against the training set: `venv\Scripts\python.exe scripts\01_ingest_classify_send.py`
2. Inspect `data\sf_classified.json` — compare `classifier_status`/`rule_triggered` per field against `_expected_status`/`_expected_rule` in the training JSON
3. Open `data\review_queue_*.xlsx`, review Tab A / Tab B output quality against the criteria in `wiki/03_experiment_and_validation.md`
4. If classifier or prompt issues are found, fix, re-run, re-check
5. Once training set meets Definition of Done, switch `config.yml` to the test set and validate once (no tuning against it)
6. Report findings to the user in plain terms — where classifier accuracy stands, where prompt quality stands, what (if anything) still needs iteration

---

## Style note

The user (Julia) has been operating this project with precise, deliberate decisions at every step — rule numbering, status naming, licensing, dataset splits. Match that register: propose specific changes with reasoning, don't make silent judgment calls on ambiguous points, surface trade-offs rather than picking one silently.
