# 05_architecture_and_reproducibility

## Purpose of This Chapter

The previous chapters explain the project from four different angles: what problem it solves, how the pipeline works, how the experiment is validated, and how the Admin reviews and deploys approved changes. This chapter brings those pieces together and explains the system as an architecture.

Its purpose is to show how the tool is put together technically, which parts of the pipeline are stable, which parts are intentionally replaceable, and how the same core design is expected to remain usable across **experiment**, **MVP**, and **production**.

In other words, this is the chapter that holds the project together.

It explains:
- how the pipeline is structured end to end
- how experiment mode and production mode relate to the same codebase
- how the human review step fits into the architecture rather than sitting outside it
- how the project is designed to remain reproducible even though it includes LLM output and human judgment

This chapter is written primarily for readers who want to understand the system as a whole: developers, architects, technically curious Admins, and anyone evaluating whether the design is robust enough to move from local validation to production use.

The key idea is that this project is **one pipeline with swappable seams**, not separate tools for experiment and production. The surrounding interfaces may evolve, but the core logic remains the same.

---

## One Pipeline, Three Operating Stages

This project is built as **one pipeline**, not as separate experimental and production codebases.

The same core scripts and the same core logic are used throughout. What changes between stages is not the pipeline itself, but a small number of surrounding seams: where the input comes from, which LLM provider is called, whether write-back is simulated or real, and how the user interacts with the system.

This is a deliberate design choice. It means the experiment is not a toy version, the MVP is not a rewrite, and production is not a different product. All three are operating stages of the same pipeline.

### Experiment

The **experiment** is the current validation stage.

In this stage, the pipeline is run safely without touching a live Salesforce org. The purpose is to test the classifier, prompts, review flow, and end-to-end reproducibility before enabling real ingestion or real deployment.

In experiment mode:
- input comes from a synthetic or mock raw metadata file such as `data/sf_metadata_raw.json`
- LLM calls go to a local or simulated provider, such as the AOAI API Simulator or Ollama
- Script 2 runs in dry-run mode and does not write anything to Salesforce
- the same scripts still exist and the same core pipeline still runs

The goal of this stage is to prove that the pipeline works as designed and produces suggestions a human reviewer can meaningfully evaluate.

### MVP

The **MVP** is the first real operational version of the project.

At this stage, the pipeline stops being a safe simulation and starts operating against a real Salesforce org. The purpose of MVP is to prove that the same pipeline can solve the real problem in a live environment while still keeping human approval fully in control.

In MVP:
- ingestion happens through the Salesforce **Tooling API**
- LLM calls go to a real provider, such as **Azure OpenAI**
- approved descriptions are written back through the Salesforce **Metadata API**
- the Admin still runs the scripts manually
- configuration is still handled through `config.yml`
- the spreadsheet review step remains unchanged

MVP is therefore not a separate product. It is the same validated pipeline, now connected to real systems.

### Production

**Production** is not a new pipeline. It is the same pipeline with a more robust operational shell around it.

The purpose of production is not to change the decision logic. It is to make the system easier to use, safer to operate, and more maintainable in an enterprise setting.

In production, the core logic should remain the same:
- the classifier still assigns `FLAGGED`, `UNCERTAIN`, `PASSED`, and `SKIPPED`
- the LLM still generates suggestions only where appropriate
- the Admin or designated reviewer still approves, edits, or rejects before deployment
- nothing is written back to Salesforce without explicit human approval

What changes in production is the operating layer around that core:

- `config.yml` editing may be replaced by a more user-friendly interface, such as command-line parameters or a simple web UI
- authentication and secret handling are likely to become more robust
- execution may move from local terminal runs to a more managed form of operation
- logging and observability may become more structured
- access control and approval governance may become stricter
- storage and retention of review files and audit logs may become more managed
- reruns, retries, and partial failures may be handled with stronger operational safeguards

In other words, production changes the **operational shell**, not the **core decision logic**.

### What Stays the Same

Across experiment, MVP, and production, the core pipeline remains the same:

- ingest metadata
- classify descriptions
- route fields according to status
- generate suggestions where needed
- assemble the review file
- require human review
- validate decisions
- write back only what has been explicitly approved
- record the outcome in an audit log

This continuity is what makes the architecture strong. Validation work done in experiment mode carries forward into MVP, and MVP carries forward into production.

### Why This Matters

This distinction is important because it explains how the project evolves without losing coherence.

- **Experiment** proves the pipeline safely
- **MVP** proves the pipeline in a real org
- **Production** makes the same pipeline operationally robust

That is why this project should be understood as one pipeline with swappable seams, not as separate tools built for different phases.

---

### High-Level Architecture

At a high level, the system is designed as a **single supervised pipeline** with two script-driven stages separated by a deliberate human control point.

- **Script 1** prepares the work: ingestion, classification, LLM routing, and assembly of the review artifact
- **Human review** provides the approval gate: the Admin decides what should happen to each proposed change
- **Script 2** executes only approved outcomes: validation, write-back, and audit logging

This structure connects the process flow described in `02_how_it_works.md` with the operational Admin workflow described in `04_human_review_process.md`.

### High-Level Architecture Overview

<pre>
╔════════════════════════════════════════════════════════════╗
║                         SCRIPT 1                           ║
║        ingest → classify → route → generate → merge        ║
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

### Script 1 — Preparation Layer

The first script is responsible for preparing a complete and reviewable proposal set. It does not write to Salesforce. Its job is to turn raw metadata into a structured review artifact.

#### Ingestion

The pipeline starts with **ingestion**.

In experiment mode, the input is a synthetic metadata file such as `data/sf_metadata_raw.json`. In MVP and production, the same ingestion step pulls live metadata from Salesforce through the **Tooling API**.

In both cases, the goal of ingestion is the same: collect the metadata needed for downstream evaluation, including field label, API name, type, current description, and other relevant field properties such as picklist values.

Architecturally, this is the input boundary of the system.

#### Classification

After ingestion, the pipeline performs **classification**.

This is a deterministic Python layer that applies the project’s 10 rule-based checks and assigns each field exactly one status:

- `FLAGGED`
- `UNCERTAIN`
- `PASSED`
- `SKIPPED`

This step is important because it determines whether a field should be routed to the LLM, carried forward unchanged, or excluded from write-back entirely.

The output of classification is persisted as `data/sf_classified.json`, which serves as the internal handoff artifact between rule-based analysis and LLM processing.

#### Routing to Prompt A / Prompt B / No LLM

Once fields have been classified, Script 1 performs **routing**.

Routing is status-driven:

- `FLAGGED` → Prompt A
- `UNCERTAIN` → Prompt B
- `PASSED` → no LLM call
- `SKIPPED` → no LLM call

Before any routed batch is sent to the LLM, the script assembles a shared prompt context for the session:

- `system_prompt.md` — universal quality rules for good field descriptions
- `golden_examples.json` — curated examples used for few-shot grounding

This shared context is combined with the task-specific prompt (`prompt_a_flagged_fields.md` or `prompt_b_uncertain_fields.md`) and the batch of fields being processed.

Architecturally, this is an important control point. The LLM is not asked to interpret all fields freely. It is invoked selectively, under explicit routing rules, and with stable session-level grounding.

#### Merge into Review Queue

After LLM responses are received, Script 1 merges all four streams back together:

- `FLAGGED`
- `UNCERTAIN`
- `PASSED`
- `SKIPPED`

The result is a single human-readable review artifact:

`data/review_queue_{timestamp}.xlsx`

This spreadsheet is the handoff object between the machine-driven part of the architecture and the human-controlled part. It contains three tabs:

- **Tab A** — `FLAGGED`
- **Tab B** — `UNCERTAIN`
- **Tab C** — `PASSED / SKIPPED`

This merge step is what converts internal pipeline outputs into an operational review interface.

### Human Review — Control Layer

The **human review layer** is the architectural approval gate.

The Admin opens the review queue and works through **Tab A** and **Tab B** row by row. For every proposed change, the Admin makes one of three decisions:

- **Approve**
- **Edit**
- **Reject**

This stage is not an external manual workaround. It is a core design feature of the system. The tool can identify problems and prepare suggestions, but it does not have authority to decide what becomes live metadata.

That authority stays with the human reviewer.

### Script 2 — Execution Layer

The second script is responsible for turning reviewed decisions into controlled deployment actions.

#### Validation

Before any write-back is attempted, Script 2 performs **validation** on the completed review file.

This validation step checks that:

- every actionable row has a decision
- every row marked **Edit** contains an **Admin Version**
- no description exceeds Salesforce limits

This is the final control barrier before the system is allowed to modify Salesforce. It prevents incomplete review states or malformed outputs from becoming live changes.

#### Write-Back

If validation succeeds, Script 2 proceeds to **write-back**.

In experiment mode, this remains a dry run. In MVP and production, write-back is performed through the Salesforce **Metadata API**.

The deployment logic follows the Admin’s decisions exactly:

- **Approve** → write the LLM suggestion
- **Edit** → write the Admin version
- **Reject** → skip
- **Tab C** → never write

This is the only point in the entire architecture where Salesforce can be changed.

#### Write Log

After write-back, Script 2 records the outcome in:

`data/write_log_{timestamp}.xlsx`

This file is the final audit artifact of the run. It captures what the system attempted to write, which decision justified that action, and whether the attempt succeeded or failed.

Architecturally, the write log closes the loop: the pipeline does not end with an update, but with a traceable record of that update.

### Architectural Summary

The architecture can be understood as a controlled flow of responsibility:

- **Script 1** prepares
- **the Admin** decides
- **Script 2** validates and executes

That separation is the central architectural principle of the project. It keeps the pipeline automatable without making it autonomous, and it allows the same core structure to remain valid across experiment, MVP, and production.

---

## Main Architectural Components

The system is easiest to understand as a small set of architectural layers. Each layer has a narrow responsibility, produces a defined output, and passes that output to the next layer. This separation is what makes the pipeline inspectable, adaptable, and reproducible across experiment, MVP, and production.

### Configuration Layer

The **configuration layer** defines the runtime scope of the pipeline.

In the current MVP-style implementation, the runtime configuration is stored in `config.yml`, which is created locally from `config.example.yml`. The scripts always read from `config.yml`, not from the template file. This layer defines which Salesforce objects are processed and which provider settings are used for the LLM and runtime mode. In the current design, it is the main entry point for adapting the pipeline to a different org or operating stage without changing Python code.

Architecturally, this layer separates **runtime settings** from **pipeline logic**. That separation is important for both portability and future evolution toward command-line parameters or a user-facing interface.

### Data Input Layer

The **data input layer** is responsible for supplying raw field metadata to the pipeline.

This layer is intentionally designed as a seam:

- in **experiment**, it reads from `data/sf_metadata_raw.json`
- in **MVP** and **production**, it reads from Salesforce through the **Tooling API**

The downstream pipeline does not need to care where the metadata came from, as long as the input structure is consistent. That is what allows the same scripts to run across stages.

This layer defines the architectural boundary between the external metadata source and the internal pipeline.

### Classification Layer

The **classification layer** is the deterministic control layer of the system.

It applies the project’s 10 rule-based checks and assigns every field exactly one status:

- `FLAGGED`
- `UNCERTAIN`
- `PASSED`
- `SKIPPED`

This layer decides which fields require LLM involvement, which can pass through unchanged, and which cannot be written back at all. Its output is stored in `data/sf_classified.json`, which acts as the persisted handoff between rule-based processing and the LLM layer.

Architecturally, this layer is important because it keeps the LLM from becoming the first decision-maker. The first routing decision is made by deterministic logic, not by generative output.

### Prompt and LLM Layer

The **prompt and LLM layer** is responsible for generating suggestions only where the classifier says they are needed.

This layer has two parts:

- a **shared session context**, assembled once per session
- a **task-specific routing context**, selected per classification bucket

The shared session context consists of:
- `system_prompt.md`
- `golden_examples.json`

The task-specific context consists of:
- `prompt_a_flagged_fields.md` for `FLAGGED`
- `prompt_b_uncertain_fields.md` for `UNCERTAIN`

This means the LLM does not receive raw fields alone. Each call is grounded by stable quality rules and curated examples, then given the specific task instruction for that bucket.

Architecturally, this layer is both **selective** and **constrained**:
- `FLAGGED` fields go to Prompt A
- `UNCERTAIN` fields go to Prompt B
- `PASSED` fields do not go to the LLM
- `SKIPPED` fields do not go to the LLM

This keeps the LLM inside a narrow role: suggestion generation under controlled conditions.

### Review Artifact Layer

The **review artifact layer** transforms internal pipeline output into a structured human review object.

After LLM processing, Script 1 merges all four streams — `FLAGGED`, `UNCERTAIN`, `PASSED`, and `SKIPPED` — into:

`data/review_queue_{timestamp}.xlsx`

This file is the operational handoff object between machine processing and human review. It provides:
- **Tab A** for `FLAGGED`
- **Tab B** for `UNCERTAIN`
- **Tab C** for `PASSED / SKIPPED`

Architecturally, this layer matters because it turns a multi-stage backend process into a single reviewable artifact. It is the formal interface between automated suggestion generation and human decision-making.

### Human Decision Layer

The **human decision layer** is the approval gate of the architecture.

The Admin reviews the spreadsheet and assigns one of three decisions to each actionable row:

- **Approve**
- **Edit**
- **Reject**

This layer is not a manual workaround for an incomplete system. It is a core design feature. The architecture assumes that semantic correctness cannot be delegated entirely to rules or to an LLM, especially when descriptions may depend on internal business meaning.

Architecturally, this layer is where **authority** sits. The machine can prepare, but the human reviewer authorizes.

### Deployment Layer

The **deployment layer** is responsible for turning reviewed decisions into controlled write actions.

This layer is implemented by `02_deploy_approved.py`. Its job is not to generate suggestions or reinterpret meaning. Its role is to:
- read the completed review file
- validate that it is complete and internally consistent
- map decisions to write actions
- execute only the permitted changes

This layer is also a seam:

- in **experiment**, it runs as a dry-run and does not call Salesforce
- in **MVP** and **production**, it writes through the **Metadata API**

Architecturally, this is the only layer that can modify Salesforce.

### Audit and Logging Layer

The **audit and logging layer** records what the system did and what happened as a result.

Its primary output is:

`data/write_log_{timestamp}.xlsx`

This log records the write attempt, the chosen source text, the Admin’s decision, and the success or failure of each attempted update.

More broadly, the architecture is designed to persist key intermediate artifacts across the run:
- raw metadata
- classified output
- raw LLM output
- review queue
- write log

This is what makes the pipeline inspectable rather than opaque. At each major stage, the system leaves behind evidence of what it received, decided, generated, reviewed, and attempted to write.

### Component Summary

Taken together, these layers create a tightly controlled architecture:

- the **configuration layer** defines runtime scope
- the **data input layer** supplies metadata
- the **classification layer** makes deterministic routing decisions
- the **prompt and LLM layer** generates constrained suggestions
- the **review artifact layer** prepares a human-readable handoff
- the **human decision layer** authorizes outcomes
- the **deployment layer** validates and executes approved changes
- the **audit and logging layer** records the run

This component structure is what allows the project to remain one coherent pipeline across experiment, MVP, and production, even as the surrounding operational shell becomes more sophisticated.

---

## Stable Core vs Swappable Seams

The architecture is designed around a simple principle: the **core pipeline stays stable**, while a small number of **external seams can be swapped** depending on whether the system is running in experiment, MVP, or production.

This is what allows the project to evolve without becoming a different tool at each stage.

### Stable Core

The following parts of the system are intended to remain stable across experiment, MVP, and production:

- **classifier logic** — the same rule-based checks determine how field descriptions are evaluated
- **status model** — the same four statuses are used throughout: `FLAGGED`, `UNCERTAIN`, `PASSED`, and `SKIPPED`
- **prompt assembly structure** — the LLM layer is built in the same way: shared session context plus task-specific prompt plus field batch
- **batching logic** — fields are grouped and sent to the LLM in the same batch-based pattern
- **review queue structure** — the output remains the same review artifact with Tab A, Tab B, and Tab C
- **Admin decision model** — the reviewer still decides row by row using **Approve**, **Edit**, or **Reject**
- **validation rules** — the same pre-write checks apply before anything can be deployed
- **write log structure** — the system still records the outcome of write attempts in a traceable audit artifact

These stable elements form the **decision logic** of the project. They define how the pipeline thinks, how it presents work for review, and how it decides what is allowed to be written.

### Why the Stable Core Matters

The stable core is what makes the architecture coherent across stages.

It means:
- the experiment validates the same logic that the MVP will use
- the MVP uses the same decision model that production will use
- improvements to prompts, classifier rules, or review design carry forward instead of being discarded at the next stage

Without this stable core, each stage would become its own disconnected tool. With it, the project remains one pipeline that matures over time.

### Swappable Seams

Around that stable core sit a small number of seams that can be changed without redesigning the pipeline.

#### Data Source

The **data source seam** determines where raw field metadata comes from.

- in **experiment**, the source is a synthetic file such as `data/sf_metadata_raw.json`
- in **MVP** and **production**, the source is Salesforce via the **Tooling API**

The pipeline downstream of ingestion does not need to change as long as the metadata structure stays consistent.

#### LLM Provider

The **LLM provider seam** determines which model endpoint the pipeline calls.

- in **experiment**, this may be a simulator or a local model such as AOAI API Simulator or Ollama
- in **MVP**, this may be a real enterprise provider such as Azure OpenAI
- in **production**, the same provider may remain, or another enterprise provider may be used

Because the prompt assembly and routing logic stay the same, the provider can change without changing the rest of the architecture.

#### Write-Back Target

The **write-back seam** determines whether Script 2 performs a dry run or a real deployment.

- in **experiment**, Script 2 validates and logs decisions but does not write to Salesforce
- in **MVP** and **production**, Script 2 writes approved descriptions through the **Metadata API**

This seam is what makes safe validation possible before enabling live change.

#### Runtime Interface

The **runtime interface seam** determines how the user interacts with the pipeline.

- in the current **experiment** and **MVP**, the pipeline is run manually through scripts and local configuration in `config.yml`
- in **production**, this may evolve into a more user-friendly interface such as command-line arguments, a wrapper application, or a simple web UI

This seam changes how the system is operated, but not how the core pipeline behaves.

### Why the Swappable Seams Matter

The swappable seams are what make the architecture adaptable.

They allow the project to:
- run safely in experiment mode
- operate for real in MVP
- become more usable and robust in production

without changing the central workflow:

- ingest
- classify
- route
- generate
- review
- validate
- write back
- log

### Architectural Summary

The stable core defines **what the system is**. The swappable seams define **how the system is connected and operated** in a given stage.

This is the bridge between them: the core stays stable, while the seams around it evolve.

---

## MVP Workflow vs Production Workflow

The move from MVP to production does not change the core pipeline. It changes how that pipeline is operated.

This distinction matters. The architecture is designed so that the same decision logic can remain in place while the surrounding operating layer becomes more robust, more secure, and easier to use.

### MVP Workflow

In the current **MVP workflow**, the pipeline is operated locally and directly.

The flow is simple:

- configuration is stored locally in `config.yml`
- the scripts are run manually from the terminal
- the Admin reviews a local Excel file
- deployment is triggered manually after review is complete

This workflow is intentionally lightweight. It is enough to prove that the pipeline works end to end against a real Salesforce org while keeping the implementation small and inspectable.

From an architectural perspective, MVP is the first real operating form of the system:
- live ingestion through the **Tooling API**
- real LLM calls
- human review in the spreadsheet
- real write-back through the **Metadata API**

The operating model is still manual, but the pipeline itself is real.

### Production Workflow

In **production**, the same pipeline logic should remain in place.

The classifier still evaluates descriptions in the same way. The same status model still applies. The LLM is still called only where appropriate. The same review gate still exists. Nothing is written to Salesforce without explicit human approval.

What changes in production is the **operational shell** around that core.

That shell may evolve in several ways:

- local `config.yml` editing may be replaced by **CLI parameters**, a **service wrapper**, or a **simple web UI**
- script execution may move from manual terminal runs to **scheduled** or **managed execution**
- secret handling may become stronger and more centralized
- authentication may move toward enterprise-grade patterns
- operational monitoring and control may become more structured

The point is not that all of these production features already exist. The point is that the architecture is compatible with them.

### What Does Not Change

The following elements should remain unchanged between MVP and production:

- the core pipeline structure
- the rule-based classifier
- the `FLAGGED` / `UNCERTAIN` / `PASSED` / `SKIPPED` model
- the prompt assembly logic
- the review-first decision model
- the validation gate before write-back
- the principle that human approval is mandatory

This is what keeps the system coherent as it matures.

### Why This Distinction Matters

Making the MVP-to-production transition explicit helps prevent a common misunderstanding.

Production is not a future rewrite of the project. It is not a different tool with different logic. It is the same pipeline, operated with a stronger interface and tighter controls.

That is why the path forward is concrete without pretending that the full production shell is already built.

- **MVP** proves that the real pipeline works
- **production** makes that same pipeline easier to operate, safer to manage, and more suitable for enterprise use.

---

## Reproducibility by Design

A key design goal of this project is **reproducibility**.

The pipeline is not intended to behave like a black box that produces suggestions and then disappears. It is designed so that another person can inspect the repository, understand how the system is assembled, run the same stages in the same order, and review the artifacts produced at each step.

Reproducibility in this project comes from three main design choices:
- an explicit repository structure
- versioned prompt assets stored as files
- persisted intermediate artifacts at every major stage of the pipeline

### Explicit Repository Structure

The repository is organized so that each major part of the system has a visible place:

- `scripts/` contains the execution logic
- `prompts/` contains the prompt assets used by the LLM layer
- `data/` contains input, intermediate, and output artifacts generated by the pipeline
- `wiki/` documents the design, workflow, and validation logic

This structure makes the project easier to inspect, explain, and reproduce. A new reader does not have to infer where prompts live, where output files are created, or where the main scripts begin and end.

### Prompt Files Stored in `prompts/`

The LLM layer is not assembled from hidden strings inside the code. Its prompt assets are stored explicitly in the `prompts/` directory.

These include:
- `system_prompt.md`
- `golden_examples.json`
- `prompt_a_flagged_fields.md`
- `prompt_b_uncertain_fields.md`

This matters for reproducibility because prompt behavior is part of the system design, not an invisible implementation detail. Another person can inspect the same files, understand the same instruction set, and run the same prompt architecture.

### Synthetic Dataset for Experiment Mode

In experiment mode, the pipeline uses a synthetic metadata dataset rather than a live Salesforce org.

This makes the experiment:
- safe to run publicly
- independent of credentials
- repeatable across environments
- suitable for testing classifier behavior and prompt quality without risk to real metadata

Because the dataset is synthetic and shareable, experiment runs can be repeated by other users without needing access to the original org.

### Persisted Intermediate Artifacts

The pipeline stores artifacts at each major stage instead of collapsing everything into a single final output.

The main persisted artifacts are:

- `sf_metadata_raw.json` — raw metadata input for the run
- `sf_classified.json` — classifier output with one status per field
- `llm_response.json` — raw LLM output before human review
- `review_queue_{timestamp}.xlsx` — the review artifact presented to the Admin
- `write_log_{timestamp}.xlsx` — the audit artifact created after Script 2

These files make the system inspectable stage by stage.

A reviewer can see:
- what metadata entered the system
- how that metadata was classified
- what the LLM returned
- what the human reviewer approved, edited, or rejected
- what was ultimately written, or attempted, during deployment

This is what makes the pipeline reproducible by design rather than only by intention.

### What Reproducibility Means Here

In this project, reproducibility does **not** mean that every run produces identical wording.

That would be the wrong standard, because the system combines three different kinds of behavior:

- the **classifier** is deterministic
- the **LLM** is not fully deterministic
- the **human review step** is intentionally judgment-based

For that reason, reproducibility here should be understood more carefully.

It means that the system preserves the same:
- structure
- rules
- prompt assets
- intermediate artifacts
- review workflow

And because those elements remain stable, repeated runs should lead to **comparable outcomes**, even if the exact wording of LLM suggestions is not identical every time.

This distinction matters. It keeps the standard realistic while still demanding discipline in the design. The goal is not perfect textual sameness. The goal is that another person can inspect the same components, run the same pipeline, and understand how a comparable result was produced.

### Why This Matters

Because the system includes both LLM output and human review, reproducibility cannot rely on code alone. It also depends on preserving the context, inputs, and outputs of each stage.

By storing prompt assets explicitly and persisting intermediate artifacts, the project makes it possible to:
- rerun the same pipeline structure
- inspect the source of a result
- compare runs over time
- review how a given output was produced

In that sense, reproducibility here means more than “the scripts run again.” It means the pipeline leaves behind enough structure and evidence for another person to understand, evaluate, and validate what happened.

---

## Error Handling and Safe Failure

The system is designed to **fail safely**.

That principle matters because this pipeline can eventually write to live Salesforce metadata. A safe failure model means that errors do not result in silent write-back, incomplete deployment, or ambiguous system state. Instead, the pipeline is designed to stop, log, or skip in a way that remains visible to the operator. :contentReference[oaicite:0]{index=0}

### No Silent Write-Back

The architecture does not allow hidden or implicit writes.

No change reaches Salesforce unless all of the following are true:

- the field has passed through Script 1
- the field appears in the review artifact
- a human reviewer has made an explicit decision
- Script 2 has validated the review file
- the write attempt is executed through the write-back layer

This means there is no path from LLM output directly to Salesforce. Human review and validation sit between generation and deployment by design.

### Validation Blocks Incomplete Review Files

Before Script 2 can write anything, it validates the completed review file.

At minimum, the validation step checks that:
- every actionable row has a decision
- every row marked **Edit** contains an **Admin Version**
- no description exceeds Salesforce limits

If any of these checks fail, Script 2 stops and nothing is written.

This is one of the most important safety controls in the system. It prevents incomplete review states from becoming partial or accidental metadata updates. :contentReference[oaicite:1]{index=1}

### Failed Field Writes Are Logged

If a write attempt fails for an individual field, that failure is recorded rather than hidden.

The system is designed to keep a traceable record of:
- which field was attempted
- what decision led to the attempt
- what text the system tried to write
- whether the attempt succeeded or failed

This record is stored in `data/write_log_{timestamp}.xlsx`.

The write log is therefore not only an audit artifact. It is also part of the failure model: it makes unsuccessful writes visible and reviewable. :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

### Partial Write Failure Does Not Corrupt the Rest of the Run

The system is designed so that one failed field does not invalidate the rest of the deployment.

If the Metadata API rejects an individual field update, that field is logged as failed and the pipeline continues with the remaining approved rows. A single write error does not corrupt the review file, erase earlier successes, or silently stop the run without trace.

This behaviour is important in real orgs, where occasional field-level failures may happen because of permissions, write restrictions, or org-specific constraints. The architecture is designed to isolate those failures rather than turn them into opaque run-level outcomes. :contentReference[oaicite:4]{index=4}

### Experiment Mode Avoids Live Risk Entirely

The safest failure mode is to avoid live write-back entirely when validating the pipeline.

That is the purpose of **experiment mode**. In experiment mode:
- input comes from synthetic metadata
- the same core pipeline still runs
- Script 2 validates and logs decisions
- no call is made to the Salesforce Metadata API

This makes it possible to test classification, prompting, review flow, and artifact generation without any risk to a live org. It also means that early failures in prompt design or review workflow can be surfaced before enabling real deployment. :contentReference[oaicite:5]{index=5}

### Safe Failure as an Architectural Principle

Safe failure in this project does not mean that errors never occur. It means errors are handled in a controlled and visible way.

In practice, that means:
- no silent write-back
- incomplete review files are blocked before deployment
- failed field writes are logged
- partial failures do not corrupt the rest of the run
- experiment mode provides a zero-risk validation path

That combination is what makes the pipeline suitable for gradual maturation from experiment to MVP and then toward production.

---

## Authentication and Secret Handling

Authentication and secret handling should be understood differently in **MVP** and in a future **enterprise production** rollout.

This section does not define the final enterprise authentication design. Instead, it sets out the current assumptions for MVP and the direction of travel for a more robust production model. That distinction is important because the project is still evolving from a locally operated pipeline toward a more production-ready operating shell. :contentReference[oaicite:6]{index=6}

### MVP Assumption: Local Trusted Execution

The current MVP assumes **local trusted execution**.

In practical terms, this means:
- the pipeline is run manually by a trusted Admin or developer
- configuration is local
- execution is script-driven
- the operating environment is controlled by the user running the tool

This is acceptable for an MVP because the goal at this stage is to prove the real pipeline against a live org, not yet to solve enterprise-scale identity and access management.

### Credentials Must Never Live in Committed Files

Even in MVP, credentials and secrets must not be stored in committed project files.

In particular:
- credentials should not be stored in source code
- credentials should not be committed to the repository
- `config.example.yml` should remain a template only
- any real secrets used during execution must remain local and uncommitted

This aligns with the broader architectural principle that the repository should remain safe to share publicly while local runtime configuration remains environment-specific.

### Enterprise Rollout Requires Proper OAuth and Secret Handling

For an enterprise production rollout, stronger authentication and secret handling will be required.

That future state is not yet defined as a hard commitment, but it will likely involve:
- proper OAuth-based Salesforce authentication
- stronger separation between local configuration and secrets
- managed secret storage rather than local file-based handling
- closer review of the integration user and its permissions

The exact implementation should be defined with the architect at enterprise rollout stage, not assumed prematurely in the wiki. :contentReference[oaicite:7]{index=7}

### Why This Is Framed Carefully

It would be misleading to present a final enterprise authentication model as if it were already settled.

At this stage, the architecture can honestly say:

- MVP assumes trusted local execution
- secrets must never be committed
- the future enterprise model will require stronger authentication and secret management
- that production-grade design should be confirmed with the architect before rollout

This keeps the documentation accurate without overstating what has already been implemented.

### Architectural Summary

Authentication and secret handling are part of the **operational shell**, not the core pipeline logic.

That means the core architecture can remain stable while the security model matures over time:

- **experiment** avoids live secrets entirely where possible
- **MVP** operates locally in a trusted environment
- **enterprise production** will require formal authentication and secret-handling design

This is consistent with the broader architecture of the project: the pipeline logic remains stable, while the seams around execution and deployment become more robust as the system moves toward production.

---

## Future Evolution Without Rewriting the Core

The architecture is intentionally designed so that the system can evolve without replacing the core pipeline.

That is one of its main strengths. The central logic of the project — ingest, classify, route, generate, review, validate, write back, and log — is meant to remain stable even as the surrounding operating layer becomes more capable.

This means future improvements can be made as extensions around the core rather than as a redesign of the core itself.

Examples of future evolution include:

- **different providers**  
  The pipeline can switch between LLM providers without changing the underlying classification, routing, review, or validation model.

- **more metadata signals**  
  Additional field context can be introduced at ingestion time, such as richer configuration details, formula definitions, relationship targets, or other metadata that improves prompt quality.

- **UI instead of configuration editing**  
  The current local `config.yml` model can later be replaced by command-line options, a wrapper application, or a simple web UI without changing the decision logic of the pipeline.

- **better authentication and secret handling**  
  The security model can mature from local trusted execution toward stronger enterprise authentication and managed secret storage.

- **stronger orchestration**  
  Script execution can move from manual terminal runs to more structured job management, scheduled execution, or service-based operation.

- **richer audit and reporting**  
  The existing review queue and write log can be extended with better reporting, monitoring, summaries, and operational traceability.

The important architectural point is that these changes improve the **operational shell** of the project, not the **core logic**.

That is why the system can mature over time without turning into a different tool. The same pipeline that is validated in experiment mode, exercised for real in MVP, and hardened in production can remain recognizably the same system throughout.

This is the intended long-term shape of the project: a stable core surrounded by replaceable and improvable edges.
