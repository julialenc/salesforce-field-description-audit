# Review evidence

The four review workbooks behind the approval rates in the main README and in `wiki/03_experiment_and_validation.md`. Each holds a fixed 40-field sample (`scripts/03_b_review_sample.py`): 20 rows in Tab A (FLAGGED fields, 4 per rule R1–R5), 12 in Tab B (R6–R9 and the descriptions Prompt C proposed to rewrite) and 8 in Tab C (descriptions the LLM kept).

| File | Data | Setup | Tab A approved as written |
|---|---|---|---|
| `01_training_first_sample_30pct.xlsx` | training set | gpt-5.4-mini, first prompts with Unverified and Missing, no org context (Day 5) | 6/20 (30%) |
| `02_training_final_mini_80pct.xlsx` | training set | gpt-5.4-mini, reasoning effort medium, final prompts, org context: the recommended setup | 16/20 (80%) |
| `03_training_sol_85pct.xlsx` | training set | gpt-6.1-sol, reasoning effort medium, same prompts and context: the stronger-model test | 17/20 (85%) |
| `04_test_set_60pct.xlsx` | test set, run once | as file 02 | 12/20 (60%) |

## How the decisions were made

The samples were reviewed against the project owner's written rubric with an AI assistant, and checked by the project owner. They are not the decisions of an independent Salesforce Admin.

- **Approve:** the description would be written to Salesforce exactly as suggested. A Missing question that would only add precision does not block approval.
- **Edit:** the direction is right, but a correction or an essential answer is needed first (a guess to remove, an opaque code to define, a lost fact to restore).
- **Reject:** wrong, or no improvement over the current description.
- **Tab C, Agree / Disagree:** whether keeping the current description was right.

The **Note** column says why, row by row.

## Columns

`Current_Description` is the original, `LLM_Suggestion` the proposed text, `Unverified` the claims the model could not confirm from its input, `Missing` the facts it would need, as questions. `Picklist_Values` comes from the dataset. Files 02 and 03 were made with `03_b_review_sample.py rereview`, which carries over decisions for rows whose suggestion did not change: `Changed`, `Previous_Suggestion`, `Previous_Decision` and `Previous_Note` show the earlier round.

To recompute a rate: `python scripts/03_b_review_sample.py score data/review_evidence/<file>`.

All fields are synthetic (a fictional outdoor-equipment retailer). No real org data.
