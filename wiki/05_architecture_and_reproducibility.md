# 05_architecture_and_reproducibility

## Purpose of This Chapter

This chapter explains how the tool is structured technically, which parts of the pipeline are stable, which parts are intentionally replaceable, and how the same core design is meant to remain usable across **experiment**, **MVP**, and **production**.

It is written primarily for readers who want to understand the system as a whole: **Developers, Architects, advanced Admins**, and anyone evaluating whether the design is robust enough to move from local validation to production use.

It covers the project’s **architecture**:
- how the pipeline is structured end to end
- how experiment mode, MVP, and production relate to the same codebase
- how the human review step fits into the architecture rather than sitting outside it

It also covers **reproducibility**, including how the project is designed to remain inspectable and repeatable even though it includes LLM output and human judgment.

---

## One Pipeline, Three Operating Stages

This project is built as **one pipeline**, not as separate codebases for experiment, MVP, and production.

The same core scripts and decision logic are used throughout. What changes between stages is a small set of surrounding seams: where the input comes from, which LLM provider is called, whether write-back is simulated or real, and how the user interacts with the system.

### What Changes Between Stages

| Aspect | Experiment | MVP | Production |
|---|---|---|---|
| Purpose | Validate the pipeline safely | Prove the pipeline in a real org | Operate the same pipeline with a stronger operational shell |
| Data source | Synthetic or mock file such as `data/sf_metadata_raw.json` | Live Salesforce metadata via **Tooling API** | Live Salesforce metadata via **Tooling API** |
| LLM provider | Local or simulated provider, such as AOAI API Simulator or Ollama | Real provider, such as **Azure OpenAI** | Real provider, potentially with stronger enterprise controls |
| Write-back | Dry-run only — no live write to Salesforce | Live write-back via **Metadata API** | Live write-back via **Metadata API** |
| Runtime interface | Manual scripts, local configuration | Manual scripts, local configuration in `config.yml` | More user-friendly operating layer, such as CLI parameters, a service wrapper, or a simple web UI |
| Human review | Required | Required | Required |
| Core pipeline logic | Same | Same | Same |

### Experiment

The **experiment** is the safe validation stage. It is used to test the classifier, prompts, review flow, and reproducibility without touching a live Salesforce org.

### MVP

The **MVP** is the first real operational version of the project. It uses live Salesforce ingestion, real LLM calls, and real write-back, while keeping the same human review gate and the same core pipeline logic.

### Production

**Production** is not a new pipeline. It is the same pipeline with a more robust operational shell around it.

Typical production changes may include:
- replacing direct `config.yml` editing with a more user-friendly interface
- stronger authentication and secret handling
- more managed execution
- better logging and observability
- stricter access control and approval governance
- more structured storage and retention of review and audit artifacts
- stronger handling of retries, reruns, and partial failures

In other words, production changes the **operational shell**, not the **core decision logic**.

### What Stays the Same

Across experiment, MVP, and production, the stable core remains the same:
- the rule-based classifier
- the `FLAGGED` / `UNCERTAIN` / `PASSED` / `SKIPPED` model
- the prompt assembly and routing structure
- the review-first decision model
- the validation gate before write-back
- the audit trail created after deployment

This continuity is what makes the architecture coherent. Validation work done in experiment mode carries forward into MVP, and MVP carries forward into production.

### Configurable Seams

The differences between operating stages are expressed through a small number of **configurable seams**, rather than through different codebases.

These seams include:
- the **data source**
- the **LLM provider**
- the **write-back mode**
- the **runtime interface**

In the current implementation, these seams are controlled mainly through `config.yml`. Later, the same seams may be exposed through command-line parameters or a more user-friendly interface, while the underlying pipeline remains the same.

This project uses **one pipeline with swappable seams**, not separate tools for experiment and production.

---

## High-Level Architecture Overview

<pre>
╔════════════════════════════════════════════════════════════╗
║                         SCRIPT 1                           ║
║         ingest → classify → route → generate → merge       ║
╚════════════════════════════════════════════════════════════╝

        `config.yml`
             ↓
Salesforce metadata source
(experiment: `data/sf_metadata_raw.json`
 MVP / production: Tooling API)
             ↓
[1] Ingestion
    Extract field metadata for configured objects
             ↓
[2] Classification
    Apply 10 rule-based checks to each field description
             ↓
     ┌───────────────┬───────────────┬───────────────┬
     ↓               ↓               ↓               ↓
  FLAGGED         UNCERTAIN        PASSED          SKIPPED
(clear failure) (possible failure) (no issues)   (read-only /
                                                  not writable)
     ↓               ↓               ↓               ↓
     └───────────────┴───────────────┴───────────────┘
                             ↓
              `data/sf_classified.json`
         (single source of truth after classification)
                             ↓

                  Shared prompt context
          (assembled once per session for all LLM calls)
              ┌─────────────────────────────┐
              │ `system_prompt.md`          │
              │ universal rules for         │
              │ good field descriptions     │
              ├─────────────────────────────┤
              │ `golden_examples.json`      │
              │ curated high-quality        │
              │ examples for few-shot       │
              │ grounding                   │
              └─────────────────────────────┘
                             ↓

[3] Routing and LLM Processing
     ┌───────────────────────────┬───────────────────────────┬
     ↓                           ↓                           ↓
  FLAGGED                    UNCERTAIN                 PASSED + SKIPPED
     ↓                           ↓                           ↓
 Prompt A                    Prompt B                    No LLM call
"if missing, write          "is this description        PASSED carried forward;
 a new one from              good enough? if not,       SKIPPED logged only
 metadata; if unusable,      suggest an improvement"
 replace it"
     ↓                           ↓
Shared prompt context      Shared prompt context
 + Prompt A + fields        + Prompt B + fields
     ↓                           ↓
  LLM call                    LLM call
     └───────────────┬───────────┘
                     ↓
            `data/llm_response.json`
                     ↓

[4] Merge into review artifact
    Combine FLAGGED + UNCERTAIN + PASSED + SKIPPED
                     ↓
    `data/review_queue_{timestamp}.xlsx`
        Tab A — FLAGGED
        Tab B — UNCERTAIN
        Tab C — PASSED / SKIPPED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    HUMAN REVIEW LAYER

[5] Admin reviews Tab A and Tab B
    For each row:
    - Approve
    - Edit
    - Reject
                     ↓
[6] Admin saves completed review file

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╔════════════════════════════════════════════════════════════╗
║                         SCRIPT 2                           ║
║              validate → write back → audit log             ║
╚════════════════════════════════════════════════════════════╝

[7] Validation
    Check that:
    - every actionable row has a decision
    - every Edit row has an Admin Version
    - no description exceeds Salesforce limits
                     ↓
[8] Write-back
    experiment: dry-run only
    MVP / production: Metadata API
                     ↓
    Decision handling:
    - Approve → write LLM suggestion
    - Edit    → write Admin version
    - Reject  → skip
    - Tab C   → never written
                     ↓
[9] Audit output
    `data/write_log_{timestamp}.xlsx`
    (record of attempted writes and outcomes)

</pre>

#### Important notes

- **Script 1** prepares proposals but cannot modify Salesforce
- **Human review** layer is the approval gate
- **Script 2** validates and executes only approved outcomes ---> the only live write happens at the Metadata API step

---

## Main Architectural Components

The system can be understood as a small set of architectural layers. Each layer has a defined responsibility and a clear handoff to the next one.

### Configuration Layer

The **configuration layer** defines the runtime scope of the pipeline.

In the current implementation, runtime configuration is stored in `config.yml`, created locally from `config.example.yml`. The scripts always read from `config.yml`, not from the template file. This layer controls which Salesforce objects are processed, which operating mode is active, and which provider settings are used.

Its architectural role is to separate runtime settings from pipeline logic.

### Data Input Layer

The **data input layer** supplies raw field metadata to the pipeline.

This layer is intentionally designed as a seam:
- in **experiment**, it reads from `data/sf_metadata_raw.json`
- in **MVP** and **production**, it reads from Salesforce through the **Tooling API**

As long as the input structure remains consistent, the downstream pipeline does not need to change.

### Classification Layer

The **classification layer** is the deterministic control layer of the system.

It applies the 10 rule-based checks and assigns each field exactly one status:
- `FLAGGED`
- `UNCERTAIN`
- `PASSED`
- `SKIPPED`

Its output is stored in `data/sf_classified.json`, which acts as the persisted handoff between rule-based processing and the LLM layer.

### Prompt and LLM Layer

The **prompt and LLM layer** generates suggestions only where the classifier says they are needed.

It combines:
- a **shared session context** assembled once per session
- a **task-specific prompt** selected by classification bucket

The shared session context consists of:
- `system_prompt.md`
- `golden_examples.json`

The task-specific prompts are:
- `prompt_a_flagged_fields.md`
- `prompt_b_uncertain_fields.md`

This keeps the LLM in a narrow role: grounded suggestion generation under explicit routing rules.

### Review Artifact Layer

The **review artifact layer** transforms internal pipeline output into a structured human review object.

After LLM processing, Script 1 merges `FLAGGED`, `UNCERTAIN`, `PASSED`, and `SKIPPED` into:

`data/review_queue_{timestamp}.xlsx`

This file is the formal handoff between machine processing and human review. It contains:
- **Tab A** — `FLAGGED`
- **Tab B** — `UNCERTAIN`
- **Tab C** — `PASSED / SKIPPED`

### Human Decision Layer

The **human decision layer** is the approval gate of the architecture.

The Admin reviews the spreadsheet and assigns one of three decisions to each actionable row:
- **Approve**
- **Edit**
- **Reject**

This layer is where final authority sits. The machine prepares proposals; the human reviewer authorizes outcomes.

### Deployment Layer

The **deployment layer** turns reviewed decisions into controlled write actions.

Implemented by `02_deploy_approved.py`, it:
- reads the completed review file
- validates that it is complete and internally consistent
- maps decisions to write actions
- executes only permitted changes

This layer is also a seam:
- in **experiment**, it runs as a dry-run
- in **MVP** and **production**, it writes through the **Metadata API**

It is the only layer that can modify Salesforce.

### Audit and Logging Layer

The **audit and logging layer** records what the system did and what happened as a result.

Its primary output is:

`data/write_log_{timestamp}.xlsx`

This log records the attempted write, the decision behind it, and the success or failure of each operation.

More broadly, the architecture persists key artifacts across the run:
- raw metadata
- classified output
- raw LLM output
- review queue
- write log

That is what makes the pipeline inspectable rather than opaque.

---

## Stable Core vs Swappable Seams

The architecture is built around a simple principle: the **core pipeline stays stable**, while a small number of **external seams remain replaceable**.

This is what allows the project to evolve across experiment, MVP, and production without becoming a different tool at each stage.

### Stable Core

The following elements are intended to remain stable across all operating stages:

- **classifier logic**
- **status model** — `FLAGGED`, `UNCERTAIN`, `PASSED`, `SKIPPED`
- **prompt assembly structure**
- **batching logic**
- **review queue structure**
- **Admin decision model** — **Approve**, **Edit**, **Reject**
- **validation rules**
- **write log structure**

Together, these elements define the project’s core decision logic: how fields are evaluated, how suggestions are prepared, how review is performed, and what is allowed to be written back.

### Why the Stable Core Matters

The stable core is what makes the architecture coherent over time.

It ensures that:
- experiment validates the same logic later used in MVP
- MVP uses the same decision model later retained in production
- improvements to rules, prompts, and review design carry forward instead of being discarded at the next stage

Without a stable core, each stage would become its own disconnected implementation. With it, the system remains one pipeline that matures over time.

### Swappable Seams

Around that stable core sit a small number of seams that can change without redesigning the pipeline:

- **data source**
- **LLM provider**
- **write-back target**
- **runtime interface**

These seams determine how the pipeline is connected and operated in a given stage, while leaving the core decision logic unchanged.

### Why the Swappable Seams Matter

The swappable seams are what make the architecture adaptable.

They allow the same pipeline to:
- run safely in experiment mode
- operate for real in MVP
- become more usable and robust in production

without changing its underlying logic.

---

## MVP Workflow vs Production Workflow

This chapter focuses on **how the pipeline is operated**, not on how its core logic changes.

The move from MVP to production should not change the underlying decision model. It changes the operating layer around that model.

### MVP Workflow

In the current **MVP workflow**, the pipeline is operated locally and directly.

The flow is simple:
- configuration is stored locally in `config.yml`
- the scripts are run manually from the terminal
- the Admin reviews a local Excel file
- deployment is triggered manually after review is complete

This workflow is intentionally lightweight. It is sufficient to prove that the pipeline works end to end against a real Salesforce org while keeping the implementation small and inspectable.

At this stage, the pipeline is already real:
- live ingestion through the **Tooling API**
- real LLM calls
- human review in the spreadsheet
- real write-back through the **Metadata API**

### Production Workflow

In **production**, the same pipeline remains in place, but it is operated through a more robust shell.

Typical production changes may include:
- replacing direct `config.yml` editing with **CLI parameters**, a **service wrapper**, or a **simple web UI**
- moving from manual terminal runs to **scheduled** or **managed execution**
- stronger secret handling
- more formal authentication
- more structured monitoring and operational control

The point is not that all of these features already exist. The point is that the architecture is compatible with them.

Production is therefore not a rewrite of the project. It is the same pipeline operated with stronger interfaces and tighter controls.

---

## Reproducibility by Design

Reproducibility is a design goal of this project.

The pipeline is designed so that another person can inspect the repository, run the same stages in the same order, and review the artifacts produced at each step. In this sense, reproducibility comes from three design choices:
- an explicit repository structure
- prompt assets stored as files
- persisted intermediate artifacts across the pipeline

### Explicit Repository Structure

The repository is organized so that each major part of the system has a visible place:

- `scripts/` contains the execution logic
- `prompts/` contains the LLM prompt assets
- `data/` contains input, intermediate, and output artifacts
- `wiki/` documents the design, workflow, and validation logic

This makes the system easier to inspect, explain, and reproduce.

### Prompt Assets Stored as Files

The LLM layer is not assembled from hidden strings inside the code. Its prompt assets are stored explicitly in `prompts/`, including:

- `system_prompt.md`
- `golden_examples.json`
- `prompt_a_flagged_fields.md`
- `prompt_b_uncertain_fields.md`

This makes prompt behavior visible and reviewable rather than implicit.

### Synthetic Dataset for Experiment Mode

In experiment mode, the pipeline uses a synthetic metadata dataset rather than a live Salesforce org.

This makes the experiment safe to run publicly, independent of credentials, and repeatable across environments without risk to real metadata.

### Persisted Intermediate Artifacts

The pipeline stores artifacts at each major stage instead of collapsing everything into a single final output.

The main persisted artifacts are:

- `sf_metadata_raw.json`
- `sf_classified.json`
- `llm_response.json`
- `review_queue_{timestamp}.xlsx`
- `write_log_{timestamp}.xlsx`

These files make the system inspectable stage by stage, from raw input to classification, generation, review, and deployment outcome.

### What Reproducibility Means Here

In this project, reproducibility does **not** mean that every run produces identical wording.

The **classifier** is deterministic, but the **LLM** is not fully deterministic, and the **human review step** is intentionally judgment-based. For that reason, reproducibility here means that the system preserves the same:
- structure
- rules
- prompt assets
- intermediate artifacts
- review workflow

With those elements held constant, repeated runs should lead to **comparable outcomes**, even if the exact wording of suggestions is not identical every time.

That is the standard this architecture is designed to support: not perfect textual sameness, but a process that remains inspectable, repeatable, and auditable.

---

## Error Handling and Safe Failure

The system is designed to **fail safely**.

Because this pipeline can eventually write to live Salesforce metadata, failure handling must be controlled and visible. Errors should result in a stop, a skip, or a logged failure — never in silent write-back or ambiguous system state.

### No Silent Write-Back

No change reaches Salesforce unless all of the following are true:

- the field has passed through Script 1
- the field appears in the review artifact
- a human reviewer has made an explicit decision
- Script 2 has validated the review file
- the write attempt is executed through the write-back layer

There is no direct path from LLM output to Salesforce. Human review and validation sit between generation and deployment by design.

### Validation Blocks Incomplete Review Files

Before Script 2 can write anything, it validates the completed review file.

At minimum, the validation step checks that:
- every actionable row has a decision
- every row marked **Edit** contains an **Admin Version**
- no description exceeds Salesforce limits

If any of these checks fail, Script 2 stops and nothing is written.

### Failed Field Writes Are Logged

If an individual field write fails, that failure is recorded rather than hidden.

The system keeps a traceable record of:
- which field was attempted
- what decision led to the attempt
- what text the system tried to write
- whether the attempt succeeded or failed

This record is stored in `data/write_log_{timestamp}.xlsx`.

### Partial Write Failure Does Not Corrupt the Rest of the Run

A failed field update does not invalidate the rest of the deployment.

If the Metadata API rejects an individual field update, that field is logged as failed and the pipeline continues with the remaining approved rows. A single write error does not corrupt earlier successes or silently terminate the run.

### Experiment Mode Avoids Live Risk Entirely

The safest failure mode is to avoid live write-back during validation.

That is the purpose of **experiment mode**. In experiment mode:
- input comes from synthetic metadata
- the same core pipeline still runs
- Script 2 validates and logs decisions
- no call is made to the Salesforce Metadata API

This allows classifier logic, prompt behavior, review flow, and artifact generation to be tested without risk to a live org.

---

## Authentication and Secret Handling

Authentication and secret handling should be understood differently in **MVP** and in a future **enterprise production** rollout.

This section does not define a final enterprise authentication model. It states the current assumptions for MVP and the likely direction for a more robust production design.

### MVP Assumption: Local Trusted Execution

The current MVP assumes **local trusted execution**.

In practical terms, this means:
- the pipeline is run manually by a trusted Admin or developer
- configuration is local
- execution is script-driven
- the operating environment is controlled by the user running the tool

This is acceptable for MVP because the immediate goal is to prove the real pipeline against a live org, not yet to solve enterprise-scale identity and access management.

### Credentials Must Never Live in Committed Files

Even in MVP, credentials and secrets must not be stored in committed project files.

In particular:
- credentials should not be stored in source code
- credentials should not be committed to the repository
- `config.example.yml` must remain a template only
- any real secrets used during execution must remain local and uncommitted

### Enterprise Rollout Requires Stronger Authentication and Secret Handling

For an enterprise production rollout, stronger authentication and secret handling will be required.

That future state is not yet defined as a hard commitment, but it will likely involve:
- proper OAuth-based Salesforce authentication
- stronger separation between local configuration and secrets
- managed secret storage rather than local file-based handling
- closer review of the integration user and its permissions

The exact implementation should be defined with the architect at enterprise rollout stage, not assumed prematurely in this wiki.

### Current Architectural Position

At this stage, the architecture can state the following clearly:

- MVP assumes trusted local execution
- secrets must never be committed
- the future enterprise model will require stronger authentication and secret management
- the production-grade design should be confirmed with the architect before rollout

---

## Future Evolution Without Rewriting the Core

The architecture is intentionally designed so that the system can evolve without replacing the core pipeline.

Its main strength is that future improvements can be made around the core rather than through a redesign of the core itself.

Examples of future evolution include:

- **different providers**  
  The pipeline can switch between LLM providers without changing the underlying classification, routing, review, or validation model.

- **more metadata signals**  
  Additional field context can be introduced at ingestion time, such as richer configuration details, formula definitions, relationship targets, or other metadata that improves prompt quality.

- **UI instead of configuration editing**  
  The current local `config.yml` model can later be replaced by command-line options, a wrapper application, or a simple web UI.

- **better authentication and secret handling**  
  The security model can mature from local trusted execution toward stronger enterprise authentication and managed secret storage.

- **stronger orchestration**  
  Script execution can move from manual terminal runs to more structured job management, scheduled execution, or service-based operation.

- **richer audit and reporting**  
  The existing review queue and write log can be extended with better reporting, monitoring, summaries, and operational traceability.

The key architectural point is that these changes improve the **operational shell** of the project, not the **core decision logic**.

This is the intended long-term shape of the system: a stable core surrounded by replaceable and improvable edges.

---
