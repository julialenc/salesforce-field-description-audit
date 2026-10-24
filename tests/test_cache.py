# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
Unit tests for the description cache key in Script 1.

Run with plain Python (no pytest needed):
  python tests/test_cache.py

A cached LLM answer may only be reused when the description, the route
(status + rule), every prompt file, the provider, the model and
reasoning_effort are all unchanged.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec    = importlib.util.spec_from_file_location("script1", ROOT / "scripts" / "01_ingest_classify_send.py")
script1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script1)

PROMPTS = {k: f"text of {k}" for k in script1.PROMPT_FILES}
CFG     = {"llm": {"provider": "openai", "model": "model-a", "reasoning_effort": "low"}}
FIELD   = {"object": "Account", "field_api_name": "Tier__c", "description": "Commercial tier.",
           "classifier_status": "UNCERTAIN", "rule_triggered": "R7"}
RESULT  = {"field_api_name": "Tier__c", "action": "keep", "suggested_description": "Commercial tier."}


def is_hit(field: dict, prompts: dict, cfg: dict) -> bool:
    """Cache built with PROMPTS/CFG/FIELD; is `field` under `prompts`/`cfg` served from it?"""
    cache = {}
    script1.update_cache(cache, [dict(FIELD)], {script1.field_key(FIELD): RESULT},
                         script1.run_fingerprint(PROMPTS, CFG))
    _, cached = script1.apply_cache([dict(field)], cache, script1.run_fingerprint(prompts, cfg))
    return bool(cached)


def with_llm(**kw) -> dict:
    return {"llm": {**CFG["llm"], **kw}}


CASES = [
    ("nothing changed -> hit",            FIELD, PROMPTS, CFG, True),
    ("description changed -> miss",       {**FIELD, "description": "Tier set by finance."}, PROMPTS, CFG, False),
    ("status changed -> miss",            {**FIELD, "classifier_status": "REVIEWED", "rule_triggered": None}, PROMPTS, CFG, False),
    ("rule changed -> miss",              {**FIELD, "rule_triggered": "R9"}, PROMPTS, CFG, False),
    ("prompt C edited -> miss",           FIELD, {**PROMPTS, "prompt_c": "edited"}, CFG, False),
    ("golden examples edited -> miss",    FIELD, {**PROMPTS, "examples": "edited"}, CFG, False),
    ("model changed -> miss",             FIELD, PROMPTS, with_llm(model="model-b"), False),
    ("provider changed -> miss",          FIELD, PROMPTS, with_llm(provider="azure_openai"), False),
    ("reasoning_effort changed -> miss",  FIELD, PROMPTS, with_llm(reasoning_effort="medium"), False),
    ("temperature changed -> hit",        FIELD, PROMPTS, with_llm(temperature=0.7), True),
]


def main() -> int:
    script1.save_cache = lambda cache: None    # never touch data/description_cache.json
    failures = 0
    for name, field, prompts, cfg, expected in CASES:
        got = is_hit(field, prompts, cfg)
        if got == expected:
            print(f"PASS  {name}")
        else:
            failures += 1
            print(f"FAIL  {name}: expected {'hit' if expected else 'miss'}, got {'hit' if got else 'miss'}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
