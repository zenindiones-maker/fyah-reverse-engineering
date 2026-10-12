#!/usr/bin/env python3
"""Fail-closed DSH -> REA MCP adapter. The model proposes; policy executes."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--harness-result", required=True)
    p.add_argument("--rea-cli", required=True)
    p.add_argument("--fixture", required=True)
    p.add_argument("--receipt", required=True)
    a = p.parse_args()
    h = json.loads(Path(a.harness_result).read_text())
    # Only a successful Qwen3-30B-A3B DSH result can authorize evaluation.
    proposed = bool(re.search(r"\binspect_artifact\b", str(h.get("final_response", ""))))
    approved = h.get("ok") is True and h.get("model_preset") == "qwen3-30b-a3b" and proposed
    receipt = {"model": h.get("model_preset"), "model_proposed": proposed,
               "policy_approved": approved, "executed": False}
    if approved:
        workspace = Path.cwd().resolve()
        fixture = Path(a.fixture).resolve()
        if not fixture.is_file() or workspace not in fixture.parents:
            receipt["error"] = "fixture must be a file inside workspace"
        else:
            env = dict(os.environ, REA_MCP_FIXTURE=str(fixture))
            try:
                result = subprocess.run(
                    ["node", str(Path(__file__).with_name("rea_mcp_bridge.mjs")),
                     a.rea_cli, "inspect_artifact", "{}"],
                    env=env, capture_output=True, text=True, timeout=45, check=False)
                receipt["returncode"] = result.returncode
                if result.returncode == 0:
                    output = json.loads(result.stdout)
                    receipt["executed"] = output.get("status") == "PASS"
                    receipt["tool_receipt"] = output
                else:
                    receipt["error"] = result.stderr[-1000:]
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                receipt["error"] = str(exc)[:500]
    Path(a.receipt).parent.mkdir(parents=True, exist_ok=True)
    Path(a.receipt).write_text(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["executed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
