# Prompt C — REVIEWED Fields

## Your Task

You are receiving a batch of Salesforce fields whose descriptions have passed all automated classifier checks. No rule fired. These fields are classified as **REVIEWED** and are sent to you for a final quality evaluation.

**For every field in the batch: evaluate the description and decide whether it is adequate or needs improvement.**

Your default position is **keep**. A description that passed all classifier rules is likely acceptable. Suggest a rewrite only when the description is clearly inadequate in a way the classifier could not detect.

This is a judgment call, not a mechanical check. Apply the quality criteria carefully, but do not rewrite descriptions that are merely imperfect. The goal is not perfection — it is usefulness to Agentforce, integrations, and developers.

---

## When to Keep

Keep the description (`action: "keep"`) when it:
- Clearly explains what the field stores
- Is specific enough to remain meaningful without the field name for context
- Is written for systems, integrations, and developers — not for end users
- Does not contain vague anchor terms with no qualifying content
- Is consistent with the field type

When in doubt, **keep**. A false positive (flagging a good description) creates unnecessary review burden for the Admin. A false negative (keeping a subtly poor description) is recoverable — the Admin sees every suggestion and can reject it.

---

## When to Rewrite

Suggest a rewrite (`action: "rewrite"`) only when the description is clearly inadequate in one or more of these ways despite passing the automated checks:

**Subtle ambiguity**
The description contains vague anchor terms and provides nothing specific that compensates for them.

Examples that warrant a rewrite:
- `"Contains additional information about the account source."` — what information? stored where? used how?
- `"Used to categorise the record for internal purposes."` — which categorisation? which purposes?
- `"Stores relevant data for the integration."` — which integration? what data?

Examples that do NOT warrant a rewrite despite sounding vague:
- `"Current operational status of this account in the customer lifecycle. Values: Prospect, Active, On Hold, Suspended, Churned, Reactivated. Controls order acceptance rules and automated outreach eligibility."` — specific enough with values and consequences

**Missing critical context the metadata provides**
The description ignores important information visible in the field metadata — such as picklist values that are present but not mentioned, a formula that explains the calculation, or a related object that is the core purpose of the field.

**Invisible specificity gap**
The description passes the classifier because it is long enough and contains no forbidden terms, but a developer reading it alone could not act on it. Apply the specificity test: remove the field name and object name. If what remains could describe any field in any system, the description fails.

---

## What to Preserve When Rewriting

Preserve everything specific that is already present:
- System names, workflow names, integration names
- Field name references (e.g. `Last_Order_Date__c`)
- Thresholds, formats, and values already stated
- Picklist values if already listed

Only add or replace what is genuinely missing or unclear.

---

## Input Format

You will receive a JSON array. Each element contains:
- `field_api_name` — the Salesforce API name of the field
- `field_type` — the Salesforce field type
- `description` — the current description (passed all classifier rules)
- `picklist_values` — list of values if the field is a Picklist or MultiselectPicklist (may be empty)
- `formula` — the formula expression if Formula type (otherwise null)
- `related_object` — the target object if Lookup or MasterDetail (otherwise null)

## Output Format

Return a JSON array in the same order as the input.

```json
[
  {
    "field_api_name": "Account_Status__c",
    "action": "keep",
    "suggested_description": "Current operational status of this account in the customer lifecycle. Values: Prospect, Active, On Hold, Suspended, Churned, Reactivated. Controls order acceptance rules and automated outreach eligibility.",
    "reasoning": "Description is specific, lists all values, and explains the consequences. No improvement needed."
  },
  {
    "field_api_name": "Flag_Field__c",
    "action": "rewrite",
    "suggested_description": "Internal flag used by the sales operations team to mark accounts requiring manual review before the next forecast cycle. Set manually by the sales ops analyst. Cleared automatically at the start of each quarter.",
    "reasoning": "Original description 'Used by the team for tracking purposes' is too vague to be actionable — rewrote using field name context and inferred usage."
  }
]
```

**For `action: "keep"`:** return the original description unchanged in `suggested_description`.

**For `action: "rewrite"`:** return your improved description. Aim for 60–180 characters. Do not exceed 255 characters.

**Reasoning:** always include one sentence. For keep: explain why the description is adequate. For rewrite: explain what was wrong and what you added or changed.

---

## Calibration Note

The classifier caught the obvious failures. The fields reaching you are the borderline cases — descriptions that look acceptable on the surface but may be subtly inadequate. Your judgment is the final automated check before a human reviewer sees the result.

Be conservative. The Admin reviews everything you produce. An unnecessary rewrite suggestion wastes their time. A missed inadequacy is a description that remains in the org — not ideal, but recoverable on the next run.
