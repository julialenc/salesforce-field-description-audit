# 04_human_review_process

## Purpose of This Chapter

This chapter is written for the **Salesforce Admin** who operates the tool in practice. 

The Admin is responsible for **selecting the objects in scope, running the scripts, reviewing the generated spreadsheet, deciding which suggestions should be accepted, edited, or rejected, and triggering deployment only after review is complete.**

The tool can do the heavy lifting. It scans field metadata, identifies descriptions that are missing or not usable, generates suggested improvements with an LLM, and prepares those suggestions in a structured review file. But it does not make the final decision.

That decision belongs to the Admin.

The Admin is the final quality gate between AI-generated suggestions and the live Salesforce org. Only the Admin can confirm whether a proposed description is accurate, specific, aligned with the field type, and appropriate for the org’s business language and standards.

This is a deliberate design choice. Field descriptions can affect admins, developers, integrations, and AI systems such as Agentforce. Because of that, the final decision must stay with a human who understands the org.

For that reason, nothing is written back to Salesforce without explicit human approval. The review step is a critical part of the workflow, not an optional one.

---

## What the Admin Does

The Admin has three jobs in this process:

1. Run Script 1 to generate the review file
2. Review the proposed descriptions in Excel and decide what should happen to each field
3. Run Script 2 to deploy only the descriptions that were approved or edited

That is the entire human workflow.

The Admin does not need to read or modify Python code. The Admin interacts only with:
- `config.yml`
- the terminal commands that start the scripts
- the Excel review file

---

## Important Note on `config.yml`

At the **MVP stage**, the Admin needs to update `config.yml` before running the tool. This is currently the place where the scope of the run is defined, such as which Salesforce objects should be processed.

This is an implementation detail of the MVP, not a permanent requirement of the product design. In production, the same choice could be handled through command-line arguments or a simple web UI instead.

---

## Why Human Review Is Required

The tool can identify fields with missing, vague, stale, or otherwise unusable descriptions, and it can generate suggested replacements using an LLM. But it does not know enough to make the final decision on its own.

A field may look obvious from the metadata but still have business meaning that only the Admin understands. A generated description may be accurate, partly accurate, or too generic. Some fields may also need wording that matches internal governance or naming standards.

For that reason, the human review step is not a safety add-on. It is part of the core design.

The AI prepares suggestions.  
The Admin decides whether those suggestions should be accepted, changed, or rejected.

---

## Step 1 — Choose Which Objects to Scan

Before running the tool, the Admin opens `config.yml` and confirms which Salesforce objects should be included in the scan.

In normal use, this means objects such as `Account`, `Contact`, or `Case`, but the list depends on the org.

The Admin does not need to change the code. The object list is controlled through configuration.

### Why this step exists

The tool should only scan the objects that are in scope for the current review cycle.

### How the Admin does it

Open `config.yml` in a plain text editor and confirm the object names.

---

## Step 2 — Run Script 1 to Generate the Review File

Once the object list is confirmed, the Admin opens a terminal window, goes to the project folder, and runs Script 1:

`python scripts/01_ingest_classify_send.py`

Script 1:

extracts field metadata
classifies the descriptions
sends the relevant fields to the LLM
creates the Excel review file

The output is a timestamped spreadsheet stored in the data/ folder:

`data/review_queue_{timestamp}.xlsx`

The timestamp matters because every run creates a separate review file. No earlier review file is overwritten.

### Why this step exists

The Admin needs a reviewable, human-readable file before any decision can be made.

### How the Admin does it

Run the first script from the terminal and wait for the spreadsheet to be created.

---

## Step 3 — Open the Spreadsheet and Understand the Tabs

The Admin then opens the generated Excel file `data/review_queue_{timestamp}.xlsx`. 

The spreadsheet is the main review interface for the tool. It contains one row per field and is split into three tabs:

- **Tab A — FLAGGED**: fields whose descriptions are missing or clearly unusable, with an AI-written replacement
- **Tab B — UNCERTAIN**: fields whose descriptions may be problematic, with an AI suggestion where appropriate
- **Tab C — PASSED / SKIPPED**: fields that need no action, included only for visibility

The Admin works only in **Tab A** and **Tab B**.

**Tab C** is reference-only and is never deployed.

### Why this step exists

The Admin needs to see the proposals in a format that supports judgment and manual control.

### How the Admin does it

Open the Excel file and focus on Tab A and Tab B. Use Tab C only for context.

---

## Step 4 — Review and Approve, Edit, or Reject

For every row in **Tab A** and **Tab B**, the Admin reviews the proposed description one field at a time.

For each row, the Admin reads:
- the object and field
- the current description, if one exists
- the AI suggestion
- any supporting metadata shown in the file

The Admin’s task is not to write every description from scratch unless needed.

The Admin’s task is to judge whether the AI suggestion is:
- accurate
- specific
- written for systems rather than end users
- aligned with the field type
- acceptable for the org’s business language and standards

Every row in **Tab A** and **Tab B** must then receive one of three decisions:

### Approve

The Admin accepts the AI suggestion exactly as written.

Script 2 will later write that description to Salesforce.

### Edit

The Admin accepts the idea but not the exact wording.

The Admin writes a corrected version in the **Admin Version** column. Script 2 will use the Admin’s version instead of the LLM suggestion.

### Reject

The Admin decides that no change should be made.

The field will be skipped during deployment.

Every row must have a decision before deployment can begin. If even one row is left blank, Script 2 stops and refuses to proceed.

### Why this step exists

Only a human reviewer can confirm whether the wording matches the real business meaning of the field.

This is the core human action in the whole pipeline. The design ensures that nothing reaches Salesforce without explicit human intent.

### How the Admin does it

Read each row, compare the suggestion with the field context, and enter **Approve**, **Edit**, or **Reject** directly in the spreadsheet.

---

## Step 5 — Save the Completed Review File

After all rows in **Tab A** and **Tab B** have been reviewed, the Admin saves the spreadsheet.

The filename should not be changed. Script 2 expects the file naming convention to remain intact so it can identify the correct review file for that run.

### Why this step exists

The spreadsheet becomes the formal record of the Admin’s decisions.

### How the Admin does it

Save the file normally in Excel without renaming it.

---

## Step 6 — Run Script 2 to Deploy Approved Changes

Once the review file is complete, the Admin returns to the terminal and runs Script 2:

`python scripts/02_deploy_approved.py`

Script 2 does not blindly deploy everything. It first validates the spreadsheet.

It checks that:
- every row in **Tab A** and **Tab B** has a decision
- every row marked **Edit** has text in **Admin Version**
- no description exceeds Salesforce’s 255-character limit

If any of these checks fail, the script stops and nothing is written.

Only when validation succeeds does Script 2 begin writing approved descriptions back to Salesforce.

The deployment logic is simple:

- **Approve** → write the LLM suggestion
- **Edit** → write the Admin version
- **Reject** → skip the field

Fields in **Tab C** are never written.

### Why this step exists

Deployment must reflect the Admin’s reviewed decisions, not the raw AI output.

### How the Admin does it

Run Script 2 from the terminal after the spreadsheet is complete.

---

## Step 7 — Keep the Write Log as the Audit Trail

After deployment, Script 2 creates a write log:

`data/write_log_{timestamp}.xlsx`

This log records each attempted update, including:
- the old description
- the new description
- the Admin’s decision
- whether the update succeeded or failed
- the timestamp of the write attempt

This file should be kept as the audit trail for the run.

### Why this step exists

The org needs a record of what changed, when, and how the decision was made.

### How the Admin does it

Store the log file after deployment and use it for traceability or troubleshooting.

---
