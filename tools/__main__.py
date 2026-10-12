"""CLI uniforme: list | run | smoke."""
from __future__ import annotations

import argparse, json, os, pathlib, shutil, subprocess, sys, tempfile, urllib.request, uuid
from datetime import datetime, timezone

from tools.contracts import artifact_metadata, build_receipt

from tools.catalog import CATALOG, by_name, list_for_prompt

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024
# Wikimedia rejects generic clients (HTTP 429). Identify the tool and a contact URL.
DOWNLOAD_USER_AGENT = (
    "fyah-re/0.0.1 (+https://github.com/zenindiones-maker/fyah-reverse-engineering)"
)

# Required dependencies are explicit so the catalog never implies that an
# optional tool is usable merely because its CLI entry exists.
DOCTOR_REQUIREMENTS = {
    "audio-full": {"modules": ["librosa", "numpy", "pyloudnorm", "soundfile", "demucs", "beat_this"], "commands": ["ffmpeg"]},
    "video-full": {"modules": ["scenedetect", "cv2", "av", "colour"], "commands": ["ffprobe"]},
    "apk-full": {"modules": ["androguard"], "commands": []},
    "binary-inspect": {"modules": ["magic"], "commands": []},
    "audio-profile": {"modules": ["librosa", "numpy", "pyloudnorm", "soundfile"], "commands": []},
    "compare": {"modules": ["librosa", "numpy", "pyloudnorm", "soundfile"], "commands": []},
    "media-inspect": {"modules": [], "commands": ["ffprobe"]},
    "cuts-pacing": {"modules": ["scenedetect"], "commands": []},
    "apk-inspect": {"modules": ["androguard"], "commands": []},
    "stems": {"modules": ["demucs"], "commands": ["ffmpeg"]},
    "silero-vad": {"modules": ["torch", "torchaudio"], "commands": []},
    "supervision-detect": {"modules": ["supervision"], "commands": []},
}
DOCTOR_OPTIONAL = {
    "media-inspect": {"modules": [], "commands": ["mediainfo"]},
    "video-full": {"modules": [], "commands": ["mediainfo"]},
    "apk-full": {"modules": [], "commands": ["jadx", "apktool", "d2j-dex2jar.sh", "quark"]},
    "binary-inspect": {"modules": ["r2pipe"], "commands": ["capa", "floss"]},
    "audio-full": {"modules": ["basic_pitch"], "commands": []},
}


class DownloadIntegrityError(RuntimeError):
    """Raised when an HTTP response ends before its declared body length."""


class DownloadRejected(RuntimeError):
    """The server refused the download. Do not retry around a rate limit."""

    def __init__(self, status: int, retry_after: str | None):
        detail = f" HTTP Retry-After={retry_after}" if retry_after else ""
        super().__init__(
            f"download rejeitado com HTTP {status}.{detail} "
            "Sem nova tentativa: não contornar limite do servidor."
        )
        self.status = status


class ToolResultNotSuccessful(RuntimeError):
    """Raised when a pipeline writes a diagnostic JSON but reports component failures."""


def _contains_component_errors(value) -> bool:
    if isinstance(value, dict):
        if any(key == "error" and item not in (None, "", False, [], {}) for key, item in value.items()):
            return True
        return any(_contains_component_errors(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_component_errors(item) for item in value)
    return False


def download(url: str, dest: pathlib.Path) -> pathlib.Path:
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": DOWNLOAD_USER_AGENT})
        written = 0
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                declared_header = response.headers.get("Content-Length")
                declared_size = None
                if declared_header is not None:
                    try:
                        declared_size = int(declared_header)
                    except (TypeError, ValueError) as exc:
                        raise DownloadIntegrityError("invalid Content-Length header") from exc
                    if declared_size < 0:
                        raise DownloadIntegrityError("negative Content-Length header")
                    if declared_size > MAX_DOWNLOAD_BYTES:
                        raise ValueError("download exceeds size limit")
                with dest.open("wb") as stream:
                    while True:
                        chunk = response.read(min(1024 * 1024, MAX_DOWNLOAD_BYTES - written + 1))
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > MAX_DOWNLOAD_BYTES:
                            raise ValueError("download exceeds size limit")
                        stream.write(chunk)
                if declared_size is not None and written != declared_size:
                    raise DownloadIntegrityError(
                        f"incomplete download: expected {declared_size} bytes, received {written}"
                    )
            return dest
        except urllib.error.HTTPError as exc:
            dest.unlink(missing_ok=True)
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                raise DownloadRejected(exc.code, retry_after) from exc
            raise
        except Exception:
            dest.unlink(missing_ok=True)
            raise
    p = pathlib.Path(url)
    if not p.exists():
        raise SystemExit(f"arquivo não encontrado: {url}")
    return p


def _run_tool_with_tmp(name: str, inputs: list[str], out: pathlib.Path, tmp: pathlib.Path) -> dict:
    if name not in by_name:
        raise SystemExit(f"ferramenta desconhecida: {name}")
    t = by_name[name]
    expected_inputs = t.get("inputs", 1)
    if len(inputs) != expected_inputs:
        if name == "compare":
            raise SystemExit("compare exige --input e --input2")
        raise SystemExit(f"{name} exige {expected_inputs} entrada(s); recebeu {len(inputs)}")
    if name == "supervision-detect":
        raise SystemExit(
            "supervision-detect bloqueado: supervision não fornece um modelo de inferência; "
            "configure um detector e pesos reais antes de anunciar detecções"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    paths = [download(u, tmp / f"in{i}") for i, u in enumerate(inputs)]
    kind = t.get("kind") or "module"

    if kind == "shell" and name == "media-inspect":
        r = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(paths[0])],
                           capture_output=True, text=True, check=True)
        data = {"schema": "fyah-re/media-inspect@1", "ok": True, "ffprobe": json.loads(r.stdout)}
        if shutil.which("mediainfo"):
            mi = subprocess.run(["mediainfo", "--Output=JSON", str(paths[0])], capture_output=True, text=True)
            if mi.returncode == 0:
                data["mediainfo"] = json.loads(mi.stdout)
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return data

    if kind == "stems":
        wav = tmp / "a.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(paths[0]), str(wav)], check=True)
        odir = out.parent / "stems"
        subprocess.run([sys.executable, "-m", "demucs", "-n", "htdemucs", "-o", str(odir), "--mp3", str(wav)], check=True)
        files = sorted(str(p) for p in odir.rglob("*.mp3"))
        data = {"schema": "fyah-re/stems@1", "ok": True, "stems": files}
        out.write_text(json.dumps(data, indent=2)); return data

    if kind == "silero_vad":
        import torch, torchaudio
        model, utils = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True)
        (get_speech_timestamps, _, read_audio, *_) = utils
        wav = read_audio(str(paths[0]), sampling_rate=16000)
        ts = get_speech_timestamps(wav, model, sampling_rate=16000)
        data = {"schema": "fyah-re/silero-vad@1", "ok": True, "segments": len(ts), "timestamps": ts[:50]}
        out.write_text(json.dumps(data, indent=2)); return data

    if t.get("module") == "pipelines":
        pipeline_command = [sys.executable, "-m", "pipelines", *t["argv"], str(paths[0]), "--out", str(out.parent)]
        venvs = os.environ.get("FYAH_RE_VENVS")
        if venvs:
            pipeline_command.extend(["--venvs", venvs])
        subprocess.run(pipeline_command, check=True)
        produced = out.parent / (name.replace("-", "_") + ".json")
        if produced.exists():
            data = json.loads(produced.read_text())
            data["ok"] = data.get("ok", True) is not False and not _contains_component_errors(data)
            out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        raise SystemExit("pipeline sem JSON de saída")

    cmd = [sys.executable, "-m", t["module"], *[str(p) for p in paths], "--out", str(out)]
    if name == "compare":
        cmd.extend(["--md", str(out.with_suffix(".md"))])
    subprocess.run(cmd, check=True)
    data = json.loads(out.read_text())
    data.setdefault("ok", True)
    return data




def _run_tool(name: str, inputs: list[str], out: pathlib.Path) -> dict:
    """Run a catalog tool in a temporary workspace that is always removed."""
    with tempfile.TemporaryDirectory(prefix="fyah-tool-") as temporary:
        return _run_tool_with_tmp(name, inputs, out, pathlib.Path(temporary))



def _module_available(name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def doctor_report() -> dict:
    """Report dependency readiness for every catalog tool without running workloads."""
    import shutil
    reports = []
    for tool in CATALOG:
        name = tool["name"]
        requirements = DOCTOR_REQUIREMENTS.get(name, {"modules": [], "commands": []})
        missing_modules = [module for module in requirements["modules"] if not _module_available(module)]
        missing_commands = [command for command in requirements["commands"] if shutil.which(command) is None]
        if name == "binary-inspect" and shutil.which("rz-bin") is None and shutil.which("r2") is None:
            missing_commands.append("rz-bin|r2")
        optional = DOCTOR_OPTIONAL.get(name, {"modules": [], "commands": []})
        missing_optional_modules = [module for module in optional["modules"] if not _module_available(module)]
        missing_optional_commands = [command for command in optional["commands"] if shutil.which(command) is None]
        if name == "supervision-detect":
            status = "blocked_unconfigured_model"
            reason = "supervision não fornece inferência; detector e pesos reais não estão configurados"
        elif missing_modules or missing_commands:
            status = "blocked_missing_dependency"
            if "rz-bin|r2" in missing_commands:
                reason = (
                    "rizin/radare2 ausente. O pacote apt rizin não instala no runner gratuito; "
                    "o caminho reproduzível é scripts/er_releases.sh com o release oficial rizinorg/rizin"
                )
            else:
                reason = "instale as dependências ausentes listadas neste relatório"
        else:
            status = "dependencies_ready"
            reason = "dependências obrigatórias encontradas; execução ainda pode falhar por entrada/modelo"
        reports.append({
            "name": name,
            "area": tool["area"],
            "status": status,
            "missing_required_modules": missing_modules,
            "missing_required_commands": missing_commands,
            "missing_optional_modules": missing_optional_modules,
            "missing_optional_commands": missing_optional_commands,
            "reason": reason,
        })
    return {"schema": "fyah-re/doctor@1", "tools_checked": len(reports), "tools": reports}

def _receipt_input(value: str) -> dict:
    """Describe an input without persisting credentials or absolute local paths."""
    if value.startswith(("http://", "https://")):
        return {"kind": "url", "source": value}
    path = pathlib.Path(value)
    if path.is_file():
        try:
            metadata = artifact_metadata(path, root=path.resolve().parent)
            return {"kind": "file", **metadata}
        except (OSError, ValueError):
            return {"kind": "file", "exists": True, "hash_status": "unavailable"}
    return {"kind": "path", "exists": path.exists()}


def _write_receipt(receipt_path: pathlib.Path, receipt) -> None:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")


def run_tool(name: str, inputs: list[str], out: pathlib.Path) -> dict:
    """Execute one catalog tool and persist a versioned receipt for success or failure."""
    started = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex
    tool_version = str(by_name.get(name, {}).get("version", "unknown"))
    receipt_path = out.with_name(out.name + ".receipt.json")
    try:
        data = _run_tool(name, inputs, out)
        if not out.is_file():
            raise RuntimeError("tool completed without writing its output artifact")
        if data.get("ok") is False:
            raise ToolResultNotSuccessful("pipeline produced diagnostics with component errors; inspect the JSON artifact")
        ended = datetime.now(timezone.utc)
        outputs = [artifact_metadata(out, root=out.parent)] if out.is_file() else []
        markdown = out.with_suffix(".md")
        if markdown.is_file() and markdown != out:
            outputs.append(artifact_metadata(markdown, root=out.parent))
        receipt = build_receipt(
            run_id=run_id, tool_name=name, tool_version=tool_version, status="success",
            exit_code=0, started_at=started, ended_at=ended,
            input_metadata=[_receipt_input(value) for value in inputs],
            output_artifacts=outputs,
            provenance={
                "executor": "fyah-re",
                "commit": os.environ.get("GITHUB_SHA") or os.environ.get("FYAH_RE_COMMIT"),
                "python": sys.version.split()[0],
            },
        )
        _write_receipt(receipt_path, receipt)
        return data
    except ToolResultNotSuccessful as exc:
        ended = datetime.now(timezone.utc)
        outputs = [artifact_metadata(out, root=out.parent)] if out.is_file() else []
        receipt = build_receipt(
            run_id=run_id, tool_name=name, tool_version=tool_version, status="failed",
            exit_code=1, started_at=started, ended_at=ended,
            input_metadata=[_receipt_input(value) for value in inputs],
            output_artifacts=outputs,
            provenance={"executor": "fyah-re", "python": sys.version.split()[0]},
            error_category=type(exc).__name__,
        )
        _write_receipt(receipt_path, receipt)
        raise SystemExit(1) from exc
    except SystemExit as exc:
        ended = datetime.now(timezone.utc)
        code = exc.code if type(exc.code) is int and exc.code != 0 else 2
        receipt = build_receipt(
            run_id=run_id, tool_name=name, tool_version=tool_version, status="blocked",
            exit_code=code, started_at=started, ended_at=ended,
            input_metadata=[_receipt_input(value) for value in inputs],
            output_artifacts=[],
            provenance={"executor": "fyah-re", "python": sys.version.split()[0]},
            error_category="input_or_policy_rejection",
        )
        _write_receipt(receipt_path, receipt)
        raise
    except Exception as exc:
        ended = datetime.now(timezone.utc)
        code = exc.returncode if isinstance(exc, subprocess.CalledProcessError) and exc.returncode else 1
        receipt = build_receipt(
            run_id=run_id, tool_name=name, tool_version=tool_version, status="failed",
            exit_code=code, started_at=started, ended_at=ended,
            input_metadata=[_receipt_input(value) for value in inputs],
            output_artifacts=[],
            provenance={"executor": "fyah-re", "python": sys.version.split()[0]},
            error_category=type(exc).__name__,
        )
        _write_receipt(receipt_path, receipt)
        raise

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fyah-re")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("prompt")
    sub.add_parser("doctor")
    r = sub.add_parser("run")
    r.add_argument("name"); r.add_argument("--input", required=True); r.add_argument("--input2")
    r.add_argument("--out", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--file", required=True)
    p.add_argument("--workspace", required=True)
    s = sub.add_parser("smoke"); s.add_argument("--name", default="media-inspect")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        print(json.dumps(CATALOG, indent=2, ensure_ascii=False)); return 0
    if a.cmd == "prompt":
        print(list_for_prompt()); return 0
    if a.cmd == "doctor":
        print(json.dumps(doctor_report(), indent=2, ensure_ascii=False)); return 0
    if a.cmd == "plan":
        from tools.plan import PlanFailed, execute_plan, load_plan_file
        try:
            result = execute_plan(
                load_plan_file(a.file),
                workspace=pathlib.Path(a.workspace),
                run_tool=run_tool,
            )
        except PlanFailed as exc:
            print(json.dumps(exc.result, indent=2, ensure_ascii=False))
            return 1
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if a.cmd == "smoke":
        if a.name not in by_name:
            raise SystemExit(f"ferramenta desconhecida: {a.name}")
        if a.name == "media-inspect":
            url = "https://upload.wikimedia.org/wikipedia/commons/4/40/Toreador_song_cleaned.ogg"
            with tempfile.TemporaryDirectory(prefix="fyah-smoke-") as temporary:
                out = pathlib.Path(temporary) / "smoke.json"
                d = run_tool(a.name, [url], out)
                print(json.dumps({"ok": d.get("ok", True), "name": a.name, "keys": list(d)[:8]}))
            return 0
        print(json.dumps({"ok": True, "name": a.name, "skipped": "no default sample"})); return 0
    inputs = [a.input] + ([a.input2] if a.input2 else [])
    d = run_tool(a.name, inputs, pathlib.Path(a.out))
    print(json.dumps({"ok": d.get("ok", True), "out": a.out, "receipt": str(pathlib.Path(a.out).with_name(pathlib.Path(a.out).name + ".receipt.json")), "schema": d.get("schema")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
