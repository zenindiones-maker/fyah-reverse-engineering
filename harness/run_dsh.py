#!/usr/bin/env python3
"""Roda DeepSeek Harness headless contra llama.cpp local (placeholder LOCAL_LLM_KEY)."""
from __future__ import annotations

import argparse, json, os, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--file-url", default="")
    ap.add_argument("--workspace", default=str(REPO))
    ap.add_argument("--dsh-home", default=str(pathlib.Path.home() / ".er-dsh-home"))
    ap.add_argument("--out", default="out/harness.json")
    a = ap.parse_args()

    # Placeholder — NÃO é chave de nuvem; llama.cpp ignora Authorization.
    os.environ.setdefault("LOCAL_LLM_KEY", "local-no-cloud-key")
    # Evita qualquer fallback para api.deepseek.com
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("DEEPSEEK_BASE_URL", None)

    from tools.catalog import list_for_prompt
    system = (ROOT / "prompts" / "system.txt").read_text() + "\n" + list_for_prompt()
    os.environ["DSH_SYSTEM_PROMPT"] = system
    os.environ["DSH_CONTEXT_WINDOW"] = "8192"

    task = a.task
    if a.file_url:
        task += f"\n\nArquivo de entrada (URL): {a.file_url}\nBaixe com curl se precisar e rode a ferramenta adequada via python -m tools run …"

    patch = str((ROOT / "patches" / "local-llm.patch.yml").resolve())
    workspace = pathlib.Path(a.workspace).resolve()
    dsh_home = pathlib.Path(a.dsh_home).resolve()
    dsh_home.mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)

    try:
        from deepseek_harness import DeepSeekHarness
    except ImportError:
        out.write_text(json.dumps({
            "ok": False,
            "error": "deepseek-harness-sdk não instalado",
            "hint": "pip install deepseek-harness-sdk deepseek-harness-runtime-bin",
        }, indent=2))
        return 2

    result_payload = {"ok": False, "provider": "local-llamacpp", "model": "qwen2.5-0.5b"}
    try:
        with DeepSeekHarness(
            provider="local-llamacpp",
            model="qwen2.5-0.5b",
            max_tokens=1024,
            cwd=str(workspace),
            dsh_home=str(dsh_home),
            profile="sdk-minimal",
            patches=(patch,),
            api_key="local-no-cloud-key",  # placeholder exigido pelo cliente OpenAI-compat do pi-ai
            base_url="http://127.0.0.1:8080/v1",  # pode ser ignorado se o patch llm-pi-ai mandar
        ) as harness:
            result = harness.run(task, session_id="fyah-er-001")
        result_payload.update({
            "ok": True,
            "final_response": getattr(result, "final_response", str(result))[:8000],
        })
    except Exception as e:  # noqa: BLE001
        result_payload["ok"] = False
        result_payload["error"] = f"{type(e).__name__}: {e}"
        # Diagnóstico crítico para a regra do Luiz
        msg = str(e).lower()
        if "missing_credential" in msg or "api key" in msg or "apikey" in msg:
            result_payload["blocker"] = (
                "DSH/pi-ai exige um valor de credencial (apiKeyEnv) mesmo para servidor local "
                "OpenAI-compatible; usamos o placeholder LOCAL_LLM_KEY=local-no-cloud-key "
                "(não é chave de nuvem). Se ainda falhou, o patch llm-pi-ai pode não estar "
                "disponível no wheel sdk-minimal (só llm-deepseek Anthropic-Messages)."
            )
        if "unknown_model" in msg or "duplicate" in msg or "not found" in msg or "cannot find" in msg:
            result_payload["blocker"] = result_payload.get("blocker") or (
                "sdk-minimal embute só @deepseek-ai/dsh-llm-deepseek-api-key (protocolo Anthropic Messages). "
                "llama.cpp fala OpenAI Chat Completions — é preciso montar llm-pi-ai via patch; "
                "se o pacote não vier no runtime wheel, DSH não consegue usar endpoint OpenAI-compat local."
            )

    out.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False))
    print(out.read_text()[:2000])
    return 0 if result_payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
