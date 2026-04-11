
## How the Tool Works

### High-Level Process Overview

<pre>
Salesforce Org
      ↓
[1] Extract field metadata — Tooling API
      ↓
[2] Classify the description of every field — 10 rule-based checks
      ↓                          ↓                        ↓                        ↓
  FLAGGED                   UNCERTAIN                  PASSED                  SKIPPED
(clear failure)         (possible failure)           (no issues)          (system fields —
                                                                          read-only, cannot
                                                                          be overwritten)
      ↓                          ↓                        ↓                        ↓
  Prompt A                   Prompt B                 No LLM                   No LLM
"This description        "Is this description        Field is kept            Field is kept
is bad. Write            good enough?                as-is. No AI             as-is. Logged
a better one."           If not, suggest             involved.                for visibility
                         an improvement."                                     only.
      ↓                          ↓
   Sent to AI              Sent to AI
      ↓                          ↓
   AI writes a             AI evaluates and
   new description         suggests a revision
      ↓                          ↓
      └──────────┬───────────────┘
                 ↓
[3] Merge all results — FLAGGED + UNCERTAIN + PASSED + SKIPPED
                 ↓
[4] review_queue_{timestamp}.xlsx — three tabs, one row per field
                 ↓
         ── HUMAN STEP ──
[5] Admin opens the spreadsheet and reviews Tab A and Tab B
    For every row: Approve / Edit / Reject the AI suggestion
                 ↓
[6] Admin saves the completed file and triggers Script 2
                 ↓
[7] Script 2 reads decisions and writes approved descriptions
    back to Salesforce — Metadata API
                 ↓
         write_log_{timestamp}.xlsx
         (record of every change made)
</pre>
