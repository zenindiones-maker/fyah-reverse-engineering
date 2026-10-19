"""Artefato de conflito: allowlist docs/memory + varredura de segredos."""
from __future__ import annotations

import json, os, pathlib, subprocess, sys

from tests.p0a.helpers import CODE, PY, git, make_remote, overlay_code


def test_artefato_bloqueado_se_contem_token_falso(tmp_path):
    """Injeta ghp_ falso no working tree de memória; _preserve deve falhar e limpar o patch."""
    sys.path.insert(0, str(CODE))
    for m in [x for x in sys.modules if x == "aimem" or x.startswith("aimem.")]:
        del sys.modules[m]
    from aimem import gitsync

    remote = make_remote(tmp_path)
    w = tmp_path / "w"
    git(tmp_path, "clone", "-q", str(remote), str(w))
    git(w, "config", "user.name", "t"); git(w, "config", "user.email", "t@x")
    overlay_code(w)
    (w / "docs/memory/handoffs/fila").mkdir(parents=True, exist_ok=True)
    # handoff com token falso no summary (simula vazamento)
    fake = "ghp_" + ("A" * 36)
    item = {
        "schema": "fyah-handoff@1", "id": "leak-test", "state": "pending",
        "summary": f"não vazear {fake}", "next_steps": [], "open_questions": [],
        "files_touched": [],
        "origin": {"workflow": "t", "run_id": "1", "run_attempt": "1",
                   "sha": None, "session": "s", "agent": "a", "created_utc": "2026-10-18T23:00:00Z"},
        "consumer": None, "consumed": None, "attempts": 0, "max_attempts": 3,
        "history": [{"at": "2026-10-18T23:00:00Z", "from": None, "to": "pending",
                     "by": "t:1", "reason": "criado"}],
    }
    (w / "docs/memory/handoffs/fila/leak-test.json").write_text(
        json.dumps(item, indent=2, ensure_ascii=False) + "\n")
    git(w, "add", "docs/memory/handoffs/fila/leak-test.json")
    git(w, "commit", "-qm", "leak")
    # chamar _preserve no repo w
    env = {**os.environ, "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    script = tmp_path / "run.py"
    script.write_text(
        "import os, sys\\n"
        f"sys.path.insert(0, {str(CODE)!r})\\n"
        f"os.chdir({str(w)!r})\\n"
        "from aimem import gitsync\\n"
        "try:\\n"
        "    gitsync._preserve('teste-segredo')\\n"
        "    print('UNEXPECTED_OK')\\n"
        "    sys.exit(0)\\n"
        "except gitsync.ArtifactSecretError as e:\\n"
        "    print('BLOCKED', e)\\n"
        "    sys.exit(3)\\n"
    )
    # fix escapes
    script.write_text(
        "import os, sys\n"
        f"sys.path.insert(0, {str(CODE)!r})\n"
        f"os.chdir({str(w)!r})\n"
        "from aimem import gitsync\n"
        "try:\n"
        "    gitsync._preserve('teste-segredo')\n"
        "    print('UNEXPECTED_OK')\n"
        "    sys.exit(0)\n"
        "except gitsync.ArtifactSecretError as e:\n"
        "    print('BLOCKED', e)\n"
        "    sys.exit(3)\n"
    )
    r = subprocess.run([PY, str(script)], capture_output=True, text=True, env=env)
    assert r.returncode == 3, (r.returncode, r.stdout, r.stderr)
    assert "BLOCKED" in r.stdout
    # diretórios de conflito: se existir, não deve ter .patch/.bundle com o token
    conf = w / "out/aimem/conflito"
    if conf.is_dir():
        for f in conf.rglob("*"):
            if f.is_file() and f.name not in ("reason.txt", "BLOCKED.txt", "README.md"):
                # após bloqueio, conteúdo sensível deve ter sido removido
                assert f.suffix not in (".patch", ".bundle") or fake not in f.read_text(errors="replace")
            if f.name == "BLOCKED.txt":
                assert "artefato bloqueado" in f.read_text()


def test_scan_artifact_rejeita_db_e_env(tmp_path):
    sys.path.insert(0, str(CODE))
    for m in [x for x in sys.modules if x == "aimem" or x.startswith("aimem.")]:
        del sys.modules[m]
    from aimem import gitsync
    d = tmp_path / "art"
    d.mkdir()
    (d / "reason.txt").write_text("x\n")
    (d / "ok.patch").write_text("diff --git a/docs/memory/x b/docs/memory/x\n")
    gitsync.scan_artifact(d)  # ok
    (d / "config.toml").write_text("[server]\ntoken=x\n")
    try:
        gitsync.scan_artifact(d)
        assert False, "deveria falhar"
    except gitsync.ArtifactSecretError as e:
        assert "arquivo_proibido" in str(e)
    (d / "config.toml").unlink()
    (d / "data.sqlite").write_bytes(b"SQLite")
    try:
        gitsync.scan_artifact(d)
        assert False
    except gitsync.ArtifactSecretError as e:
        assert "arquivo_proibido" in str(e)
