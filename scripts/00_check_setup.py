# Copyright 2025 Julia Lenc
# Licensed under the Apache License, Version 2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""
00_check_setup.py

Checks everything the pipeline needs before a first run and says how to fix
what is missing: Python version, packages, config.yml, the input file, the
LLM connection (one tiny request, a few tokens) and, when config.yml uses a
Salesforce org, the Salesforce CLI and its login.

  python scripts/00_check_setup.py           all checks
  python scripts/00_check_setup.py --no-llm  skip the LLM request

Exit code 0 when every check passes.
"""

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
PLACEHOLDERS = ("YOUR_", "PASTE_", "your_username")

results: list[tuple[bool, str, str]] = []      # (ok, what was checked, how to fix it)


def check(ok: bool, what: str, fix: str = "") -> bool:
    results.append((ok, what, fix))
    return ok


def check_python() -> None:
    v = sys.version_info
    check(v >= (3, 10), f"Python {v.major}.{v.minor}",
          "Install Python 3.10 or newer from python.org and create the venv again.")


def check_packages() -> None:
    for module, package in (("yaml", "PyYAML"), ("requests", "requests"), ("openpyxl", "openpyxl")):
        try:
            importlib.import_module(module)
            check(True, f"Package {package}")
        except ImportError:
            check(False, f"Package {package}", "Run: pip install -r requirements.txt (inside the venv).")


def load_config() -> dict | None:
    if not check(CONFIG_PATH.exists(), "config.yml exists",
                 "Copy config.example.yml to config.yml (CMD: copy config.example.yml config.yml), "
                 "then fill in the llm section."):
        return None
    import yaml
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        check(False, "config.yml is valid YAML",
              f"Fix the line near {mark.line + 1 if mark else '?'}: often a missing '#' or a wrong indent.")
        return None
    check(True, "config.yml is valid YAML")
    return cfg


def check_config(cfg: dict) -> None:
    llm = cfg.get("llm") or {}
    if not check(bool(llm), "config.yml has an llm section", "Copy the llm section from config.example.yml."):
        return
    provider = llm.get("provider", "openai")
    check(provider in ("openai", "azure_openai"), f"llm.provider: {provider}",
          "Use openai (any OpenAI-compatible API) or azure_openai. Bedrock and Vertex AI are not implemented.")
    for key in ("endpoint", "model", "api_key"):
        value = str(llm.get(key) or "")
        check(bool(value) and not any(p in value for p in PLACEHOLDERS), f"llm.{key} is filled in",
              f"Set llm.{key} in config.yml (see the comments in config.example.yml).")

    source = cfg.get("source") or {"production": "org"}.get(cfg.get("mode"), "file")
    check(source in ("file", "org"), f"source: {source}", "Set source: file or source: org.")
    write_back = cfg.get("write_back", "export")
    write_back = "off" if write_back is False else write_back
    check(write_back in ("off", "export", "deploy"), f"write_back: {write_back}",
          'Set write_back: "off", export or deploy (quote "off").')

    if source == "file":
        path = Path((cfg.get("data_source") or {}).get("experiment_file", "data/sf_metadata_raw_training.json"))
        path = path if path.is_absolute() else ROOT / path
        check(path.exists(), f"Input file {path.name}", "Check data_source.experiment_file in config.yml.")
    ctx = (cfg.get("options") or {}).get("org_context_file")
    if ctx:
        path = Path(ctx) if Path(ctx).is_absolute() else ROOT / ctx
        check(path.exists(), f"Org context file {path.name}", "Check options.org_context_file, or set it to null.")
    if source == "org":
        endpoint = str(llm.get("endpoint", ""))
        free = any(h in endpoint for h in ("groq.com", "cerebras.ai", "openrouter.ai"))
        check(not free or (cfg.get("options") or {}).get("allow_free_tier_with_org"),
              "Org metadata goes to an approved LLM provider",
              "source: org sends your org's metadata to the LLM. Use Azure OpenAI or another approved "
              "provider, not a free tier.")


def check_llm(cfg: dict) -> None:
    """One tiny chat request: proves endpoint, key and model work. A few tokens."""
    import requests
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("script1", ROOT / "scripts" / "01_ingest_classify_send.py")
    script1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script1)
    llm = cfg.get("llm") or {}
    try:
        call = script1._call_azure_openai if llm.get("provider") == "azure_openai" else script1._call_openai_compatible
        reply = call("Reply with the single word OK.", "Say OK.", {**cfg, "options": {"llm_max_retries": 1}})
        check(bool(reply.strip()), f"LLM answers ({llm.get('model')})", "The LLM sent an empty reply. Try again.")
    except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
        check(False, f"LLM answers ({llm.get('model')})", script1.llm_error_hint(e, cfg) or str(e)[:200])


def check_salesforce(cfg: dict) -> None:
    source     = cfg.get("source") or {"production": "org"}.get(cfg.get("mode"), "file")
    write_back = cfg.get("write_back", "export")
    if source != "org" and write_back != "deploy":
        return                                  # the CLI is only needed when an org is used
    sf = shutil.which("sf") or shutil.which("sf.cmd")
    if not check(bool(sf), "Salesforce CLI (sf) installed",
                 "Install it from https://developer.salesforce.com/tools/salesforcecli (Windows installer), "
                 "then open a new terminal."):
        return
    org = (cfg.get("salesforce") or {}).get("target_org")
    if not check(bool(org), "salesforce.target_org is set",
                 "Log in with: sf org login web --alias <alias>, then put the alias in salesforce.target_org."):
        return
    proc = subprocess.run([sf, "org", "display", "--target-org", org, "--json"],
                          capture_output=True, text=True, encoding="utf-8")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {}
    connected = data.get("status") == 0 and (data.get("result") or {}).get("connectedStatus") == "Connected"
    check(connected, f"Logged in to the org '{org}'",
          f"Run: sf org login web --alias {org} (a browser opens; sign in to the org).")


def main() -> int:
    check_python()
    check_packages()
    cfg = load_config()
    if cfg is not None:
        check_config(cfg)
        if "--no-llm" not in sys.argv and all(ok for ok, _, _ in results):
            check_llm(cfg)
        check_salesforce(cfg)

    for ok, what, fix in results:
        print(f"  {'OK  ' if ok else 'FAIL'}  {what}" + ("" if ok else f"\n        Fix: {fix}"))
    failed = sum(not ok for ok, _, _ in results)
    print("\nAll checks passed. Next: python scripts/01_ingest_classify_send.py" if not failed
          else f"\n{failed} check(s) failed. Fix them and run this check again.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
