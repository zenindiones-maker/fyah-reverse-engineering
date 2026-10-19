#!/usr/bin/env python3
"""Manifesto + limpeza verificável dos artefatos da prova do er-memory-persist (v2).

Elegibilidade para exclusão vem SÓ do manifesto autorizado (hash conferido) + proveniência
verificável no git. Nunca de nomes de arquivo.

Subcomandos:
  snapshot  --ref R --out F
      Lê docs/memory na árvore de R e grava {path: {mode, sha256}} (byte a byte, via cat-file).
  registra  --job J --run-base SHA --antes F --ref R --out M [--anterior M0 --anterior-sha256 H]
      Depois do push do job: os caminhos novos em R (ausentes em --antes) cujo commit de criação
      (git log --diff-filter=A) tem os trailers deste workflow/run/attempt/job e descende de
      run-base. Grava o manifesto canônico e imprime o sha256.
  limpa     --manifest M --manifest-sha256 H --run-base SHA --ref R [--dry-run]
      Validação TOTAL antes de apagar. Qualquer falha: ::error::, rc=1, nada apagado.
  verifica  --antes F --manifest M --manifest-sha256 H --ref R
      Depois do push da limpeza: todo docs/memory fora do manifesto idêntico byte a byte a
      --antes, e os caminhos do manifesto ausentes. Qualquer diferença: rc=1.
workflow/run_id/run_attempt vêm de --workflow/--run-id/--attempt (padrão: GITHUB_WORKFLOW,
GITHUB_RUN_ID e GITHUB_RUN_ATTEMPT).
"""
from __future__ import annotations

import argparse, hashlib, json, os, pathlib, posixpath, re, subprocess, sys

SCHEMA = "fyah-prova-manifesto@1"
MEM = "docs/memory"
# allowlist estrita: diretório-pai EXATO do arquivo
SCOPE_DIRS = frozenset({
    "docs/memory/handoffs",
    "docs/memory/handoffs/fila",
    "docs/memory/handoffs/efeitos",
    "docs/memory/sessoes",
})
META_KEYS = {"schema", "workflow", "run_id", "run_attempt", "run_base", "entries"}
ENTRY_KEYS = {"path", "sha256", "sha256_criacao", "created_commit", "workflow", "run_id", "run_attempt", "job"}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
NUM = re.compile(r"^[0-9]+$")
JOBS = ("job-a", "job-b")


class Falha(Exception):
    pass


def git(*a, check=True, binary=False):
    r = subprocess.run(["git", *a], capture_output=True, text=not binary)
    if check and r.returncode:
        err = r.stderr if not binary else r.stderr.decode(errors="replace")
        raise Falha(f"git {' '.join(a)}: {err.strip()[-300:]}")
    return r


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def is_ancestor(a: str, b: str) -> bool:
    return git("merge-base", "--is-ancestor", a, b, check=False).returncode == 0


def snapshot(ref: str) -> dict:
    out = git("ls-tree", "-r", "-z", "--full-tree", ref, "--", MEM, binary=True).stdout
    snap = {}
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, typ, obj = meta.decode().split()
        blob = git("cat-file", typ, obj, binary=True).stdout if typ == "blob" else b""
        snap[path.decode()] = {"mode": mode, "sha256": sha256(blob)}
    return snap


def trailers(commit: str) -> dict | None:
    """Trailers Aimem-* do último parágrafo da mensagem; None se houver chave repetida."""
    msg = git("show", "-s", "--format=%B", commit).stdout.rstrip()
    last = re.split(r"\n\s*\n", msg)[-1]
    t = {}
    for line in last.splitlines():
        m = re.match(r"^(Aimem-[A-Za-z-]+): (.*)$", line)
        if m:
            if m.group(1) in t:
                return None
            t[m.group(1)] = m.group(2).strip()
    return t


def is_run_commit(commit: str, wf: str, rid: str, att: str, job: str | None = None) -> bool:
    t = trailers(commit)
    if not t:
        return False
    ok = (t.get("Aimem-Workflow"), t.get("Aimem-Run-Id"), t.get("Aimem-Run-Attempt")) == (wf, rid, att)
    return ok and (job is None or t.get("Aimem-Job") == job)


def adds(ref: str, path: str) -> list[str]:
    return git("log", "--diff-filter=A", "--format=%H", ref, "--", path).stdout.split()


def blob_at(commit: str, path: str) -> bytes:
    return git("show", f"{commit}:{path}", binary=True).stdout


def check_path(p) -> str | None:
    """Erro de escopo/forma do caminho, ou None se ok."""
    if not isinstance(p, str) or not p:
        return "caminho vazio/não-string"
    if p.startswith("/") or "\\" in p or "\0" in p:
        return f"caminho absoluto/inválido: {p!r}"
    parts = p.split("/")
    if any(x in ("", ".", "..") for x in parts) or posixpath.normpath(p) != p:
        return f"caminho não normalizado/traversal: {p!r}"
    parent, name = posixpath.split(p)
    if parent not in SCOPE_DIRS:
        return f"caminho fora do escopo permitido: {p!r}"
    if name.startswith(".") or not (name.endswith(".json") or name.endswith(".md")):
        return f"nome fora do escopo (.json/.md, sem dotfile): {p!r}"
    return None


def run_ids(a):
    wf = a.workflow or os.environ.get("GITHUB_WORKFLOW") or ""
    rid = a.run_id or os.environ.get("GITHUB_RUN_ID") or ""
    att = a.attempt or os.environ.get("GITHUB_RUN_ATTEMPT") or ""
    if not wf or not NUM.match(rid) or not NUM.match(att):
        raise Falha(f"workflow/run_id/run_attempt inválidos: {wf!r}/{rid!r}/{att!r}")
    return wf, rid, att


def load_manifest(path: str, expected_sha: str) -> dict:
    raw = pathlib.Path(path).read_bytes()
    if not HEX64.match(expected_sha or ""):
        raise Falha("sha256 do manifesto ausente/inválido")
    if sha256(raw) != expected_sha:
        raise Falha(f"manifesto adulterado: sha256 {sha256(raw)} != autorizado {expected_sha}")
    try:
        obj = json.loads(raw)
    except Exception as e:
        raise Falha(f"manifesto ilegível: {e}")
    if canonical(obj) != raw:
        raise Falha("manifesto não está na forma canônica")
    if not isinstance(obj, dict) or set(obj) != META_KEYS or obj.get("schema") != SCHEMA:
        raise Falha("manifesto com esquema inválido")
    if not isinstance(obj["entries"], list):
        raise Falha("manifesto: entries não é lista")
    return obj


def write_out(obj, out, gh_output):
    raw = canonical(obj)
    pathlib.Path(out).write_bytes(raw)
    h = sha256(raw)
    if gh_output:
        with open(gh_output, "a") as o:
            o.write(f"manifest={raw.decode()}\nmanifest_sha256={h}\n")
    print(json.dumps({"manifest_sha256": h, "n": len(obj["entries"]),
                      "paths": [e["path"] for e in obj["entries"]]}))


# ------------------------------------------------------------------ subcomandos
def cmd_snapshot(a):
    pathlib.Path(a.out).write_text(json.dumps(snapshot(a.ref), sort_keys=True, indent=1) + "\n")
    return 0


def cmd_registra(a):
    wf, rid, att = run_ids(a)
    if a.job not in JOBS:
        raise Falha(f"job não autorizado a registrar: {a.job!r}")
    base = git("rev-parse", "--verify", f"{a.run_base}^{{commit}}").stdout.strip()
    if not is_ancestor(base, a.ref):
        raise Falha("run-base não é ancestral do ref")
    antes = json.loads(pathlib.Path(a.antes).read_text())
    after = snapshot(a.ref)
    entries = {}
    if a.anterior:
        prev = load_manifest(a.anterior, a.anterior_sha256)
        if (prev["workflow"], prev["run_id"], prev["run_attempt"], prev["run_base"]) != (wf, rid, att, base):
            raise Falha("manifesto anterior é de outro run/attempt/base")
        for e in prev["entries"]:
            if e["path"] in entries:
                raise Falha(f"duplicidade no manifesto anterior: {e['path']}")
            if e["path"] not in after:
                raise Falha(f"arquivo do manifesto anterior sumiu do remoto: {e['path']}")
            entries[e["path"]] = dict(e, sha256=after[e["path"]]["sha256"])
    ignorados = []
    for p in sorted(set(after) - set(antes)):
        cs = adds(a.ref, p)
        ok = (len(cs) == 1 and cs[0] != base and is_ancestor(base, cs[0])
              and is_run_commit(cs[0], wf, rid, att, a.job) and check_path(p) is None
              and after[p]["mode"] == "100644")
        if not ok:
            ignorados.append(p)
            continue
        if p in entries:
            raise Falha(f"duplicidade: {p}")
        entries[p] = {"path": p, "sha256": after[p]["sha256"], "sha256_criacao": sha256(blob_at(cs[0], p)),
                      "created_commit": cs[0], "workflow": wf, "run_id": rid, "run_attempt": att, "job": a.job}
    for p in ignorados:
        print(f"::warning::novo na janela mas NÃO registrado (proveniência/escopo): {p}", file=sys.stderr)
    obj = {"schema": SCHEMA, "workflow": wf, "run_id": rid, "run_attempt": att, "run_base": base,
           "entries": [entries[k] for k in sorted(entries)]}
    write_out(obj, a.out, a.github_output)
    return 0


def validate(a) -> tuple[dict, list[str]]:
    wf, rid, att = run_ids(a)
    m = load_manifest(a.manifest, a.manifest_sha256)
    errs = []
    if (m["workflow"], m["run_id"], m["run_attempt"]) != (wf, rid, att):
        errs.append(f"run/attempt divergente: manifesto {m['workflow']}/{m['run_id']}/{m['run_attempt']} "
                    f"!= {wf}/{rid}/{att}")
    base = m["run_base"]
    if not HEX40.match(str(base)) or base != a.run_base:
        errs.append(f"run_base divergente: manifesto {base!r} != autorizado {a.run_base!r}")
        return m, errs
    if not is_ancestor(base, a.ref):
        errs.append("run_base não é ancestral do ref")
    if not m["entries"]:
        errs.append("manifesto vazio")
    if git("diff", "--quiet", a.ref, "--", MEM, check=False).returncode != 0 or \
            git("status", "--porcelain", "-uall", "--", MEM).stdout.strip():
        errs.append("working tree de docs/memory difere do ref (sincronize antes)")
    seen, seen_cf = set(), set()
    root = pathlib.Path.cwd().resolve()
    for i, e in enumerate(m["entries"]):
        if not isinstance(e, dict) or set(e) != ENTRY_KEYS or not all(isinstance(v, str) for v in e.values()):
            errs.append(f"entrada {i}: esquema inválido"); continue
        p = e["path"]
        pe = check_path(p)
        if pe:
            errs.append(pe); continue
        if p in seen or p.casefold() in seen_cf:
            errs.append(f"duplicidade: {p}"); continue
        seen.add(p); seen_cf.add(p.casefold())
        if (e["workflow"], e["run_id"], e["run_attempt"]) != (wf, rid, att) or e["job"] not in JOBS:
            errs.append(f"run/attempt/job divergente na entrada: {p}"); continue
        if not (HEX64.match(e["sha256"]) and HEX64.match(e["sha256_criacao"]) and HEX40.match(e["created_commit"])):
            errs.append(f"hash/commit malformado: {p}"); continue
        ls = git("ls-tree", a.ref, "--", p).stdout.split()
        if not ls:
            errs.append(f"arquivo ausente no ref: {p}"); continue
        if ls[0] != "100644" or ls[1] != "blob":
            errs.append(f"não é arquivo regular (symlink/modo {ls[0]}): {p}"); continue
        lp = pathlib.Path(p)
        cur = pathlib.Path(".")
        sym = False
        for part in lp.parts:
            cur = cur / part
            if cur.is_symlink():
                sym = True
        if sym or (lp.exists() and lp.resolve() != root / p):
            errs.append(f"symlink no caminho: {p}"); continue
        if not lp.is_file():
            errs.append(f"arquivo ausente na working tree: {p}"); continue
        wt = sha256(lp.read_bytes())
        rb = sha256(blob_at(a.ref, p))
        if not (wt == rb == e["sha256"]):
            errs.append(f"hash divergente: {p} (wt={wt[:12]} ref={rb[:12]} manifesto={e['sha256'][:12]})"); continue
        cs = adds(a.ref, p)
        c = e["created_commit"]
        if cs != [c]:
            errs.append(f"commit de criação não confere: {p} (git={','.join(x[:12] for x in cs)} manifesto={c[:12]})"); continue
        if c == base or not is_ancestor(base, c) or not is_ancestor(c, a.ref):
            errs.append(f"commit de criação fora da janela do run: {p} ({c[:12]})"); continue
        if not is_run_commit(c, wf, rid, att, e["job"]):
            errs.append(f"commit de criação não pertence a este run/job: {p} ({c[:12]})"); continue
        if sha256(blob_at(c, p)) != e["sha256_criacao"]:
            errs.append(f"hash de criação divergente: {p}"); continue
        for t in git("log", "--format=%H", f"{base}..{a.ref}", "--", p).stdout.split():
            if not is_run_commit(t, wf, rid, att):
                errs.append(f"alterado por commit fora do run: {p} ({t[:12]})"); break
    return m, errs


def cmd_limpa(a):
    m, errs = validate(a)
    if errs:
        for x in errs:
            print(f"::error::limpeza abortada: {x}", file=sys.stderr)
        print(json.dumps({"abortado": True, "erros": errs, "removidos": []}, ensure_ascii=False))
        return 1
    paths = [e["path"] for e in m["entries"]]
    if not a.dry_run:
        for p in paths:
            pathlib.Path(p).unlink()
    print(json.dumps({"abortado": False, "dry_run": a.dry_run, "removidos": paths}, ensure_ascii=False))
    return 0


def cmd_verifica(a):
    m = load_manifest(a.manifest, a.manifest_sha256)
    antes = json.loads(pathlib.Path(a.antes).read_text())
    after = snapshot(a.ref)
    rm = {e["path"] for e in m["entries"]}
    esperado = {k: v for k, v in antes.items() if k not in rm}
    difs = []
    for k in sorted(set(esperado) | set(after)):
        if esperado.get(k) != after.get(k):
            difs.append(f"{k}: antes={esperado.get(k)} depois={after.get(k)}")
    for k in sorted(rm & set(after)):
        difs.append(f"item do manifesto ainda no remoto: {k}")
    if difs:
        for d in difs:
            print(f"::error::verificação remota: {d}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "preservados": len(esperado), "removidos": sorted(rm)}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("--ref", required=True); s.add_argument("--out", required=True)
    for name in ("registra", "limpa", "verifica"):
        s = sub.add_parser(name)
        s.add_argument("--ref", required=True)
        s.add_argument("--workflow"); s.add_argument("--run-id"); s.add_argument("--attempt")
        if name == "registra":
            s.add_argument("--job", required=True); s.add_argument("--run-base", required=True)
            s.add_argument("--antes", required=True); s.add_argument("--out", required=True)
            s.add_argument("--anterior"); s.add_argument("--anterior-sha256")
            s.add_argument("--github-output")
        else:
            s.add_argument("--manifest", required=True); s.add_argument("--manifest-sha256", required=True)
        if name == "limpa":
            s.add_argument("--run-base", required=True); s.add_argument("--dry-run", action="store_true")
        if name == "verifica":
            s.add_argument("--antes", required=True)
    a = ap.parse_args(argv)
    try:
        return {"snapshot": cmd_snapshot, "registra": cmd_registra,
                "limpa": cmd_limpa, "verifica": cmd_verifica}[a.cmd](a)
    except Falha as e:
        print(f"::error::{a.cmd}: {e}", file=sys.stderr)
        print(json.dumps({"abortado": True, "erros": [str(e)], "removidos": []}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
