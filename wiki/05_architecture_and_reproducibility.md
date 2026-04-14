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

