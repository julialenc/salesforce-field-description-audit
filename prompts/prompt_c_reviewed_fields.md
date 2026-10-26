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
- `"Current hold state of this account's orders. Values: None, Credit Hold, Compliance Hold, Customer Request. Any value other than None stops order release in the ERP."` — specific enough with values and consequences

**Missing critical context the metadata provides**
The description ignores important information visible in the field metadata — such as picklist values that are present but not mentioned, a formula that explains the calculation, or a related object that is the core purpose of the field.

**Invisible specificity gap**
The description passes the classifier because it is long enough and contains no forbidden terms, but a developer reading it alone could not act on it. Apply the specificity test: remove the field name and object name. If what remains could describe any field in any system, the description fails.

---

## What to Preserve When Rewriting

Preserve everything specific that is already present:
- System names, workflow names, integration names
- Field name references (e.g. `Last_Invoice_Date__c`)
- Thresholds, formats, and values already stated
- Picklist values if already listed

Only add or replace what is genuinely missing or unclear.

---

## Do Not Invent

This rule is about what you add, never about what is already there. Everything the original description states counts as confirmed input: do not remove it, and do not rewrite a description only to make it shorter or more cautious. A description that passes the "When to Keep" test is kept, even if you cannot verify its claims.

A rewrite may only state facts that the original description or the metadata supports: the field name, type, picklist values, formula and related object. Do not add who populates the field, which process or system reads it, or what it triggers, unless the input says so. An invented consequence reads as fact to Agentforce and to an Admin approving in bulk, and is worse than a short description.

When the original is vague and the metadata cannot fill the gap (for example a checkbox described only as "used for tracking"), still rewrite: state plainly what the field name and type confirm, keep it short, and list the facts the Admin must add in `missing` as questions ("What does checked mean?", "Which process reads it?"). If you include a likely detail anyway, list it in `assumptions`.

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
    "field_api_name": "Order_Hold_Status__c",
    "action": "keep",
    "suggested_description": "Current hold state of this account's orders. Values: None, Credit Hold, Compliance Hold, Customer Request. Any value other than None stops order release in the ERP.",
    "reasoning": "Description is specific, lists all values, and explains the consequences. No improvement needed.",
    "assumptions": [],
    "missing": []
  },
  {
    "field_api_name": "Net_Margin_Pct__c",
    "action": "rewrite",
    "suggested_description": "Net margin of this order as a percentage, calculated by formula as (Amount__c - Cost__c) / Amount__c. Read-only; recalculated whenever either amount changes.",
    "reasoning": "Original 'Margin figure kept for internal purposes and analysis.' named no calculation; rewrote from the formula provided in the metadata.",
    "assumptions": [],
    "missing": []
  }
]
```

**For `action: "keep"`:** return the original description unchanged in `suggested_description`.

**For `action: "rewrite"`:** return your improved description. Aim for 60–180 characters. Do not exceed 255 characters.

**Reasoning:** always include one sentence. For keep: explain why the description is adequate. For rewrite: explain what was wrong and what you added or changed.

---

## Check Before You Answer

Read each rewritten `suggested_description` once more and fix it if any of these fail:
1. **Length:** at most 255 characters, counted including spaces. If it is longer, cut process detail, not values.
2. **Acronyms and abbreviations:** every acronym or short form is written out on first use, e.g. "Ops" becomes "Operations". Picklist values are written exactly as given. Do not add acronyms that are not in the input.
3. **Forbidden terms:** none of "relevant", "applicable", "various", "related to", "for tracking", "for reporting", "for reference", "internal use". Name the specific report, team, rule or system if the input gives it; otherwise leave the clause out.
4. **Picklist values:** every value from `picklist_values` appears, spelled exactly as given.
5. **No invented facts:** every process, team, system or consequence named is in the original or the metadata. If you kept a likely but unconfirmed detail, it is listed in `assumptions`.

---

## Calibration Note

The classifier caught the obvious failures. The fields reaching you are the borderline cases — descriptions that look acceptable on the surface but may be subtly inadequate. Your judgment is the final automated check before a human reviewer sees the result.

Be conservative. The Admin reviews everything you produce. An unnecessary rewrite suggestion wastes their time. A missed inadequacy is a description that remains in the org — not ideal, but recoverable on the next run.
