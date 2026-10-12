"""Workflow adapter: route every er-analyze request through the shared tools CLI."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from urllib.parse import urlsplit


def _is_http_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
        return parts.scheme in {"http", "https"} and bool(parts.netloc)
    except ValueError:
        return False


def _summary(tool: str, result: subprocess.CompletedProcess, output: pathlib.Path) -> str:
    lines = [f"## Fyah E.R. — {tool}", ""]
    receipt_path = output.with_name(output.name + ".receipt.json")
    receipt = {}
    data = {}
    if output.is_file():
        try:
            data = json.loads(output.read_text())
        except (OSError, json.JSONDecodeError):
            lines.append("Saída JSON: inválida ou ilegível.")
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text())
        except (OSError, json.JSONDecodeError):
            lines.append("Recibo: inválido ou ilegível.")
    status = receipt.get("status", "unknown")
    lines += [f"- **Status:** {status}", f"- **Exit code:** {receipt.get('exit_code', result.returncode)}"]
    if data:
        lines += [f"- **Schema:** {data.get('schema', 'não declarado')}", f"- **Resultado ok:** {data.get('ok', 'não declarado')}"]
        if tool == "audio-profile":
            lines.append(f"- **Áudio:** {data.get('tempo_bpm')} BPM · {data.get('key', {}).get('tonic')} {data.get('key', {}).get('mode')} · {data.get('duration_s')} s")
        elif tool == "media-inspect":
            ffprobe = data.get("ffprobe", {})
            fmt = ffprobe.get("format", {})
            lines.append(f"- **Mídia:** {fmt.get('format_long_name', 'formato não identificado')} · {fmt.get('duration', '?')} s · {len(ffprobe.get('streams', []))} stream(s)")
        elif tool == "cuts-pacing":
            lines.append(f"- **Edição:** {data.get('cuts', '?')} cortes · {data.get('cuts_per_minute', '?')} cortes/min")
        elif tool in {"audio-full", "video-full", "apk-full", "binary-inspect"}:
            errors = []
            def collect(value, path=""):
                if isinstance(value, dict):
                    for key, item in value.items():
                        next_path = f"{path}.{key}" if path else key
                        if key == "error" and item:
                            errors.append(f"{next_path}: {str(item)[:180]}")
                        else:
                            collect(item, next_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        collect(item, f"{path}[{i}]")
            collect(data)
            if errors:
                lines += ["", "**Componentes com falha:**"] + [f"- {error}" for error in errors[:10]]
    if result.returncode != 0 and result.stderr.strip():
        lines += ["", "**Erro do executor:**", "text:", result.stderr.strip()[-1800:]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        print("uso: er_analyze.py FERRAMENTA URL URL2 (URL2 vazio exceto para compare)", file=sys.stderr)
        return 2
    tool, source, source2 = args
    if not _is_http_url(source):
        print("a entrada principal deve ser uma URL HTTP(S)", file=sys.stderr)
        return 2
    if tool == "compare" and not _is_http_url(source2):
        print("compare exige duas URLs HTTP(S)", file=sys.stderr)
        return 2

    out_dir = pathlib.Path(os.environ.get("FYAH_RE_OUT_DIR", "out")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{tool.replace('-', '_')}.json"
    command = [sys.executable, "-m", "tools", "run", tool, "--input", source, "--out", str(output)]
    if tool == "compare":
        command.extend(["--input2", source2])

    env = os.environ.copy()
    env.setdefault("FYAH_RE_VENVS", str(pathlib.Path.home() / ".er-venvs"))
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", os.devnull)
    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write(_summary(tool, result, output))
        summary.write("\n")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
