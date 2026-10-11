#!/usr/bin/env python3
"""Roda DeepSeek Harness headless contra llama.cpp local (placeholder LOCAL_LLM_KEY)."""
from __future__ import annotations

import argparse, json, os, pathlib, re, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
REGS = json.loads((ROOT / "models.json").read_text())


def wait_server(url: str, timeout: float = 180) -> None:
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception as e:
            last = str(e)
            time.sleep(1)
    raise TimeoutError(f"llama-server não respondeu em {url}: {last}")


def score_tool_use(text: str, workspace: pathlib.Path) -> dict:
    """Detect whether DSH actually invoked the expected tools (not invented names)."""
    t = text or ""
    low = t.lower()
    media_cmd = bool(re.search(r"python\s+-m\s+tools\s+run\s+media-inspect", low))
    audio_cmd = bool(re.search(r"python\s+-m\s+tools\s+run\s+audio-full", low))
    # Artifacts written during the session (before workflow fallback)
    media_json = workspace / "out" / "media-inspect.json"
    audio_json = workspace / "out" / "audio-full.json"
    media_exists = media_json.is_file() and media_json.stat().st_size > 20
    audio_exists = audio_json.is_file() and audio_json.stat().st_size > 20
    # Heuristic: bash/tool markers in DSH transcript
    bash_markers = len(re.findall(r"\bbash\b|tool_call|function_call|run_terminal", low))
    invented = bool(re.search(r"media.inspect.*(not found|missing|não exist|unknown)", low))
    return {
        "mentioned_media_inspect_cmd": media_cmd,
        "mentioned_audio_full_cmd": audio_cmd,
        "media_inspect_json_present": media_exists,
        "audio_full_json_present": audio_exists,
        "bash_or_tool_markers": bash_markers,
        "likely_invented_missing_tool": invented,
        "tool_use_score": int(media_cmd) + int(audio_cmd) + int(media_exists) + int(audio_exists),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--file-url", default="")
    ap.add_argument("--workspace", default=str(REPO))
    ap.add_argument("--dsh-home", default=str(pathlib.Path.home() / ".er-dsh-home"))
    ap.add_argument("--out", default="out/harness.json")
    ap.add_argument("--model-preset", default=os.environ.get("MODEL_PRESET", "fast"),
                    choices=sorted(REGS))
    a = ap.parse_args()

    meta = REGS[a.model_preset]
    model_id = meta["id"]

    os.environ.setdefault("LOCAL_LLM_KEY", "local-no-cloud-key")
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("DEEPSEEK_BASE_URL", None)

    from tools.catalog import list_for_prompt
    system = (ROOT / "prompts" / "system.txt").read_text() + "\n" + list_for_prompt()
    # Qwen3 base (non-Instruct-2507) may think; Instruct-2507 usually won't need this.
    if meta.get("no_think"):
        system = "/no_think\n" + system
    os.environ["DSH_SYSTEM_PROMPT"] = system
    os.environ["DSH_CONTEXT_WINDOW"] = str(meta["ctx"])

    task = a.task
    if a.file_url:
        task += (
            f"\n\nInput URL: {a.file_url}\n"
            "Use bash to run media-inspect then audio-full on that URL (see system prompt)."
        )

    patch = str((ROOT / "patches" / "local-llm.patch.yml").resolve())
    workspace = pathlib.Path(a.workspace).resolve()
    dsh_home = pathlib.Path(a.dsh_home).resolve()
    dsh_home.mkdir(parents=True, exist_ok=True)
    (workspace / "out").mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Clear prior tool artifacts so score reflects this DSH run only
    for p in (workspace / "out" / "media-inspect.json", workspace / "out" / "audio-full.json"):
        if p.exists():
            p.unlink()

    result_payload = {
        "ok": False,
        "provider": "local-llamacpp",
        "model_preset": a.model_preset,
        "model": model_id,
        "model_name": meta["name"],
        "license": meta.get("license"),
    }
    try:
        from deepseek_harness import DeepSeekHarness
    except ImportError:
        result_payload.update({
            "error": "deepseek-harness-sdk não instalado",
            "hint": "pip install deepseek-harness-sdk deepseek-harness-runtime-bin",
        })
        out.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False))
        return 2

    t0 = time.time()
    try:
        with DeepSeekHarness(
            provider="local-llamacpp",
            model=model_id,
            max_tokens=int(meta["max_tokens"]),
            cwd=str(workspace),
            dsh_home=str(dsh_home),
            profile="sdk-minimal",
            patches=(patch,),
            api_key="local-no-cloud-key",
            base_url="http://127.0.0.1:8080/v1",
        ) as harness:
            result = harness.run(task, session_id=f"fyah-er-{a.model_preset}")
        elapsed = round(time.time() - t0, 2)
        final = getattr(result, "final_response", str(result))[:8000]
        # Also scrape session dir for command traces
        session_blob = ""
        for p in sorted(dsh_home.rglob("*"))[:200]:
            if p.is_file() and p.suffix in {".json", ".jsonl", ".log", ".txt", ".md"} and p.stat().st_size < 2_000_000:
                try:
                    session_blob += "\n" + p.read_text(errors="ignore")[:50_000]
                except Exception:
                    pass
        combined = final + "\n" + session_blob
        score = score_tool_use(combined, workspace)
        # Persist raw events for tool-call diagnosis
        events = getattr(result, "events", []) or []
        notes = []
        for n in (getattr(result, "notifications", []) or [])[:200]:
            try:
                notes.append({"method": n.method, "payload": n.payload})
            except Exception:
                notes.append({"raw": str(n)[:500]})
        (workspace / "out" / "dsh_events.json").write_text(
            json.dumps({"events": events, "notifications": notes}, indent=2, ensure_ascii=False, default=str)[:2_000_000]
        )
        result_payload.update({
            "ok": True,
            "elapsed_sec": elapsed,
            "final_response": final,
            "finish_reason": getattr(result, "finish_reason", None),
            "n_events": len(events),
            "event_types": [e.get("type") for e in events if isinstance(e, dict)][:80],
            "tool_use": score,
        })
    except Exception as e:  # noqa: BLE001
        elapsed = round(time.time() - t0, 2)
        result_payload["ok"] = False
        result_payload["elapsed_sec"] = elapsed
        result_payload["error"] = f"{type(e).__name__}: {e}"
        result_payload["tool_use"] = score_tool_use("", workspace)
        msg = str(e).lower()
        if "missing_credential" in msg or "api key" in msg or "apikey" in msg:
            result_payload["blocker"] = (
                "DSH/pi-ai exige placeholder LOCAL_LLM_KEY=local-no-cloud-key "
                "(não é chave de nuvem)."
            )
        if "unknown_model" in msg or "duplicate" in msg or "not found" in msg or "cannot find" in msg:
            result_payload["blocker"] = result_payload.get("blocker") or (
                "Modelo não registrado no patch llm-pi-ai ou alias llama-server divergente."
            )

    out.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False))
    print(out.read_text()[:3000])
    return 0 if result_payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
