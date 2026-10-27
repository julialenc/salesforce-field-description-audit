# 06_lessons_learned

## Purpose of This Chapter

This chapter records what building and testing the pipeline taught. The other wikis describe the system as it is; this one explains the problems found along the way and the reasons behind the fixes.

It is written for anyone building a similar system, especially engineers new to putting an LLM inside a real workflow. None of the lessons are specific to Salesforce.

The chapter grows as the project moves forward.

---

## 1. Measure Before You Tune

**Write the check before changing anything.** The first classifier run matched only 119 of 288 labelled training fields (41%). Without a script that lists every mismatch (`validate_classifier.py`), it would have been tempting to tweak rules by feel. With the list, the mismatches fell into a few groups, and each fix could be checked in seconds: 119 → 136 → 248 → 259 → 270 → 279.

**Group failures before fixing them.** 128 of the first 169 mismatches came from a single cause (Rule 6 firing on length alone). Fixing the biggest group first is far cheaper than fixing failures one by one.

**Decide in advance what "good enough" means.** The remaining 9 mismatches were accepted and documented (wiki 03, "Known classifier limits") instead of fixed. Fixing them would have meant tuning keyword rules to individual sentences, which helps the score and hurts the tool on real data.

## 2. Labels Can Be Wrong Too

When a rule and a label disagree, either one can be wrong. 21 training labels were corrected during development, each because it contradicted the written rule definitions in wiki 02, and each correction was logged with its reason. The rule was not "change the label to match the code": the default was always to fix the code, and a label changed only when the specification said so.

## 3. Keep a Held-Out Test Set, and Protect It

The test set is run once, at the end. Any look at it during development weakens it. During development it was exposed once, in a simulation of a rule change. This is recorded and nothing was tuned on it. Being honest about exposure is part of the method.

## 4. Watch for Leaks Between Prompts and Data

**Few-shot examples are part of the input.** All twelve golden examples, and every example inside the prompts, had been taken from the training set: the golden ones word for word. A model shown the ideal answer for a field it is about to process can simply copy it. The score then measures memory, not quality, and anyone reviewing the design would rightly challenge it. One "good" example was even a field the dataset labels as flawed.

All examples were replaced with invented fields that appear in neither dataset, and the prompts were checked against both datasets for shared field names and long shared phrases. Any new dataset or new example must be checked the same way.

## 5. Build a Checker for LLM Output, and Treat It as a Proxy

LLM output cannot be unit-tested like code, but much of "good" can be checked mechanically. `evaluate_suggestions.py` runs every suggestion back through the classifier: a good rewrite should pass the same rules the original failed. It also checks length, banned vague terms, picklist values and the action each prompt asks for.

Lessons from building it:
- **A checker built on your classifier also tests the classifier.** The first "failures" included clearly good suggestions such as "Customer Satisfaction (CSAT) score". The rule only accepted the order "CSAT (Customer Satisfaction)", so the classifier was too strict. This is the real-world order too, and it was fixed.
- **Some quality rules cannot be checked by keywords.** The guidelines allow "used to …" when specific content follows. A keyword check cannot tell "used to route invoices to the ERP" from "used for various purposes". Counted as failures, they made the free model look like 39% instead of 77%. They are now reported as notes and left to human review.
- **The checker is a proxy.** It cannot tell whether a suggestion is true. Only a human reviewer can confirm that "updated nightly by the billing system" actually happens.

## 6. Prompt Iteration Plateaus Quickly

On the free open-weight model, three prompt iterations took the automatic pass rate for flagged fields from 86.5% to 95.9%, then stopped improving:

- Replacing leaked examples: small change in score, large gain in trust
- **A short "check before you answer" list at the end of the prompt** gave the biggest jump (89% → 96%). The same rules were already in the system prompt; repeating them as a final step is what worked
- Telling the model which instruction wins when two conflict (length limit versus "preserve all content") fixed one more field

After that, the remaining failures were long originals the model would not cut, acronyms it could not expand, and classifier keyword limits. More prompt wording would only have chased individual sentences. **When the remaining failures are no longer the same kind, stop iterating and look at them by hand.**

## 7. Free Tiers and Models Change Under You

- A model can disappear between two runs. Groq retired `llama-3.3-70b-versatile` without notice (HTTP 404 `model_not_found`). Check the provider's model list at the start of each session.
- On Azure, by October 2026 every gpt-4o and gpt-4.1 model was "Deprecated", which in Azure's terms means closed to subscriptions that never deployed them. Check the retirement schedule before naming a model in documentation.
- Free tiers limit more than requests per minute. Groq's free tier also caps the size of a single request (8,000 tokens), which a retry can never fix: the request has to get smaller. The fix was a smaller batch and splitting a batch in half on HTTP 413.
- Reasoning models (gpt-5 family, gpt-oss) spend output tokens on hidden reasoning. A reply cut off for length is usually reasoning that used up the budget, so set `reasoning_effort: low` for a task like this. They may also reject parameters such as `temperature`.

## 8. Caching: Key on Everything That Shapes the Answer

The first cache keyed answers on the description text only. After a prompt change, a model change or a routing change, re-runs silently returned old answers. Routing is the subtle one: a field whose description is unchanged but now goes to a different prompt must not reuse the old answer.

The second version hashed every prompt file. It was correct, but one edit to one prompt re-sent all 271 fields, about 160,000 tokens. That is close to a free tier's daily limit, so prompt iteration on the free tier was nearly impossible. The final key is per route: the description, status and rule, the shared system prompt and examples, the route's own prompt, and the provider, model and reasoning effort. Later iterations cost 54,000 and 19,000 tokens.

Test the cache with a mocked LLM call before spending real tokens. It proves hit and miss behaviour in seconds.

## 9. Cost: Measure, Then Trust the Bill

- Log token usage from every API response and estimate cost from configured prices. A per-field number (here about 480 input and 100 output tokens) makes any run's cost predictable before it starts.
- The script's estimate was 0.18 CHF; the bill was 0.13 CHF. The estimate ignores the discount on cached input (the system prompt repeated in every batch), so it is an upper bound. Check the provider's cost view after the first paid run and note the ratio.
- Keep a ledger of every paid run and set a budget alert in the provider's console. An alert does not stop spending; the ledger is the real control.

## 10. Two Models, Same Decisions

An open-weight model on a free tier (gpt-oss-120b on Groq) and a paid model (gpt-5.4-mini on Azure) chose the same action, rewrite, shorten or keep, for all 271 training fields. They differed in wording: the paid model followed the banned-term list more closely. For this task the routing and the prompts decide the outcome far more than the choice of model. That is the point of keeping a deterministic classifier in front of the LLM.

## 11. A Perfect Score Can Hide the Main Defect

Prompt C passed the automatic check 11 out of 11, and it looked like the task was to tune which fields it rewrites. Reading the rewrites one by one showed the real defect: they invented facts ("...triggers internal audit processes") that no rule could catch. Read a sample of the output yourself before you tune anything, even when, and especially when, the score is perfect.

## 12. One Example Outweighs One Rule

Prompt A said "do not invent business logic". Its only example rewrote a blank field as "Written nightly by the renewal forecasting model; a score above 70 creates a renewal review task", which is invented. The open-weight model copied the pattern almost word for word ("Calculated nightly by the churn prediction model; scores above 80 trigger a retention outreach task"). When an example and an instruction disagree, the model follows the example.

## 13. Prohibitions Overshoot; State the Boundary

After "do not invent" was strengthened, the model started deleting true facts from good descriptions, because it could not verify them either. The fix was one sentence saying what the rule is *not* about: claims already in the original are input, keep them. Every "do not" needs its "but do".

## 14. Make Uncertainty an Output Field

You cannot stop a model from guessing with an instruction alone, and a guess is invisible once it reads like fact. Asking for an `assumptions` list (what it guessed) and a `missing` list (what it could not know) turned the problem into two review columns and two numbers. Two models read the same rule differently: one left guesses out, the other wrote them and listed them. Both became traceable.

## 15. A Checker and a Human Measure Different Things

On the same suggestions, the automatic check passed 98.6% and a human approved 30%. The checker saw rule violations; the human saw unconfirmable guesses, dropped warnings, and questions that missed the point (asking who calculates a score instead of what its scale is). Neither number is wrong. Report both, and do not let the easy one stand in for the hard one.

## 16. The Prompt Cannot Supply What the Input Lacks

Many rejected suggestions had no prompt problem: the facts were not in the input. What a grade "A" means, or which scale an engagement score uses, is org knowledge; a notes field may only make sense next to its neighbouring fields. Before you rewrite a prompt again, ask whether the model had the information at all. If not, the fix is more context (metadata sent with the field, a short org glossary), not more instructions.

Then test the context claim too. With a full org context file, approval first rose only from 30% to 40%: the model used the glossary where a field matched it, but the remaining rejections were prompt faults (remarks to the Admin in the text, codes left unexplained although the glossary defined them). One more prompt iteration aimed at exactly those notes took the same context run to 70%. Context and instructions work together: context supplies the facts, the prompt has to say where they go. Neighbour fields cost little and added more guesses than answers.

## 17. A Rule That Removes a Problem Can Move It

Telling the model to ask instead of guess took the guesses out of the descriptions (rows with unverified claims fell from 46 to 7), and put the questions into the descriptions instead ("Checkbox flag on this record. What does checked mean?"), in about one row in twenty. Telling it to keep the original's caveats made the classifier re-flag them as placeholders. After every rule, read a handful of outputs for where the problem went, not only whether it left.

## 18. A Reviewer Must See What the Model Saw

The first score of the run with org context was 20%, lower than without it: the reviewer had the suggestions but not the context file, and could not confirm what it said. With the file next to the sample, four rows became approvals. If an experiment gives the model extra input, the review sample must give the reviewer the same input.

## 19. Synthetic Data Has Its Own Style

Synthetic data is only as realistic as whoever wrote it. In the training set, the "good" descriptions were long and followed one template. That produced a length-based rule that could not separate good from bad, and the rule had to be redefined. No description used the common "Full Name (ACRONYM)" order, so the classifier never saw it until an LLM wrote one. Before trusting a rule, ask whether the data that shaped it looks like a real org.
