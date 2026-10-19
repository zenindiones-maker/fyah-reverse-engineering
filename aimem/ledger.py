"""Fila durável de handoffs no git (fyah-handoff@1).

Um arquivo por item em docs/memory/handoffs/fila/<id>.json. Estados:
pending → claimed → consumed | pending (falha, com tentativas) | failed (esgotou).
claimed → claimed só por lease expirado ou re-run do mesmo run (registrado).
Nada é apagado; toda transição entra em `history`.
"""
from __future__ import annotations

import datetime as dt, hashlib, json, os, pathlib, re, subprocess, uuid

SCHEMA = "fyah-handoff@1"
REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "zenindiones-maker/fyah-reverse-engineering")
TRANS = {"pending": {"claimed"}, "claimed": {"claimed", "consumed", "pending", "failed"},
         "consumed": set(), "failed": set()}
DEFAULT_LEASE = 6 * 3600 + 1800   # job máx. 6 h no runner padrão + margem


class LedgerError(RuntimeError):
    pass


class LostClaim(LedgerError):
    """O item não está mais claimed com o nosso claim_token."""


class UnsafeMerge(LedgerError):
    """Merge semântico impossível sem descartar ou inventar transição."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def fila_dir(mem: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(mem) / "handoffs" / "fila"


def me() -> dict:
    wf = os.environ.get("GITHUB_WORKFLOW") or "local"
    run = os.environ.get("GITHUB_RUN_ID") or "local"
    att = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    return {"consumer_id": f"{wf}:{run}", "attempt_id": f"{run}.{att}",
            "workflow": wf, "run_id": run, "run_attempt": att}


def _head_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def origin_from_env(session: str, agent: str) -> dict:
    m = me()
    return {"workflow": m["workflow"], "run_id": m["run_id"], "run_attempt": m["run_attempt"],
            "sha": os.environ.get("GITHUB_SHA") or _head_sha(), "session": session, "agent": agent,
            "created_utc": now()}


def new_item(summary, next_steps, open_questions, files, origin: dict) -> dict:
    stamp = _ts(origin["created_utc"]).strftime("%Y%m%dT%H%M%SZ")
    iid = f"{stamp}-{origin['run_id']}-{origin['run_attempt']}-{uuid.uuid4().hex[:6]}"
    return {"schema": SCHEMA, "id": iid, "state": "pending", "summary": summary,
            "next_steps": list(next_steps or []), "open_questions": list(open_questions or []),
            "files_touched": list(files or []), "origin": origin, "consumer": None, "consumed": None,
            "attempts": 0, "max_attempts": int(os.environ.get("AIMEM_MAX_ATTEMPTS", "3")),
            "history": [{"at": origin["created_utc"], "from": None, "to": "pending",
                         "by": f"{origin['workflow']}:{origin['run_id']}", "reason": "criado"}]}


def dumps(item: dict) -> str:
    return json.dumps(item, indent=2, ensure_ascii=False) + "\n"


def save(mem, item: dict) -> pathlib.Path:
    d = fila_dir(mem); d.mkdir(parents=True, exist_ok=True)
    p = d / f"{item['id']}.json"; p.write_text(dumps(item)); return p


def load(mem, iid: str) -> dict:
    return json.loads((fila_dir(mem) / f"{iid}.json").read_text())


def load_all(mem) -> list[dict]:
    d = fila_dir(mem)
    items = [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.is_dir() else []
    return sorted(items, key=lambda i: ((i.get("origin") or {}).get("created_utc") or "", i["id"]))


def transition(item: dict, to: str, by: str, reason: str) -> None:
    fr = item["state"]
    if to not in TRANS[fr]:
        raise LedgerError(f"transição inválida {fr}→{to} em {item['id']}")
    item["history"].append({"at": now(), "from": fr, "to": to, "by": by, "reason": reason,
                            "claim_token": (item.get("consumer") or {}).get("claim_token")})
    item["state"] = to


def lease_seconds() -> int:
    return int(os.environ.get("AIMEM_LEASE_SECONDS", str(DEFAULT_LEASE)))


def _expired(item: dict) -> bool:
    c = item.get("consumer") or {}
    exp = c.get("lease_expires_at")
    return bool(exp) and _ts(exp) <= dt.datetime.now(dt.timezone.utc)


def _claimable(item: dict, m: dict) -> tuple[bool, str]:
    if item["state"] == "pending":
        return True, "claim"
    if item["state"] != "claimed":
        return False, ""
    c = item.get("consumer") or {}
    if c.get("consumer_id") == m["consumer_id"]:
        return True, "retry (mesmo run)"
    if _expired(item):
        return True, "lease expirado"
    return False, ""


def claimable(mem) -> list[tuple[dict, str]]:
    m = me(); out = []
    for i in load_all(mem):
        ok, why = _claimable(i, m)
        if ok:
            out.append((i, why))
    return out


def apply_claim(item: dict, reason: str) -> dict:
    m = me()
    prev = item.get("consumer") or {}
    # retry do mesmo consumer: preserva claim_token (chave do efeito); senão gera novo
    if item["state"] == "claimed" and prev.get("consumer_id") == m["consumer_id"] and prev.get("claim_token"):
        token = prev["claim_token"]
    else:
        token = uuid.uuid4().hex
    t = now(); exp = (_ts(t) + dt.timedelta(seconds=lease_seconds())).strftime("%Y-%m-%dT%H:%M:%SZ")
    item["consumer"] = {"consumer_id": m["consumer_id"], "claim_token": token, "attempt_id": m["attempt_id"],
                        "claimed_at": prev.get("claimed_at") or t, "lease_expires_at": exp,
                        "reclaimed_at": t if prev.get("claim_token") == token and item["state"] == "claimed" else None}
    if item["state"] == "pending":
        item["attempts"] = item.get("attempts", 0) + 1
    transition(item, "claimed", m["consumer_id"], reason)
    return item


def apply_consume(item: dict, result_status: str) -> dict:
    m = me(); token = (item.get("consumer") or {}).get("claim_token")
    if item["state"] != "claimed" or (item.get("consumer") or {}).get("consumer_id") != m["consumer_id"]:
        raise LostClaim(f"não sou o dono do claim de {item['id']}")
    item["consumed"] = {"consumer_id": m["consumer_id"], "claim_token": token, "attempt_id": m["attempt_id"],
                        "at": now(), "result_status": result_status}
    transition(item, "consumed", m["consumer_id"], f"efeito confirmado ({result_status})")
    return item


def apply_release(item: dict, reason: str) -> dict:
    m = me()
    if item["state"] != "claimed" or (item.get("consumer") or {}).get("consumer_id") != m["consumer_id"]:
        raise LostClaim(f"não sou o dono do claim de {item['id']}")
    nxt = "failed" if item.get("attempts", 0) >= item.get("max_attempts", 3) else "pending"
    transition(item, nxt, m["consumer_id"], reason)
    if nxt == "pending":
        item["consumer"] = None
    return item


def verify_mine(item: dict, token: str) -> None:
    c = item.get("consumer") or {}
    if item["state"] != "claimed" or c.get("consumer_id") != me()["consumer_id"] or c.get("claim_token") != token:
        raise LostClaim(f"claim remoto de {item['id']} não é o meu")


def _hist_keys(item: dict) -> set:
    return {(h.get("at"), h.get("from"), h.get("to"), h.get("by"), h.get("claim_token"))
            for h in (item.get("history") or [])}


def _is_prefix_hist(a: dict, b: dict) -> bool:
    """True se o history de a (ordenado) é prefixo do de b."""
    ha = sorted(a.get("history") or [], key=lambda h: (h.get("at") or "", h.get("to") or ""))
    hb = sorted(b.get("history") or [], key=lambda h: (h.get("at") or "", h.get("to") or ""))
    if len(ha) > len(hb):
        return False
    return all(ha[i] == hb[i] for i in range(len(ha)))


def validate_item(item: dict) -> list[str]:
    """Verificador da máquina de estados. Retorna lista de erros (vazia = ok)."""
    errs = []
    if item.get("schema") != SCHEMA:
        errs.append("schema inválido")
    st = item.get("state")
    if st not in TRANS:
        errs.append(f"estado desconhecido {st!r}"); return errs
    hist = item.get("history") or []
    if not hist:
        errs.append("history vazio"); return errs
    cur = None
    for h in hist:
        to = h.get("to"); fr = h.get("from")
        if cur is None:
            if to != "pending" or fr is not None:
                errs.append(f"primeira transição inválida {fr!r}→{to!r}")
        else:
            if fr != cur:
                errs.append(f"from {fr!r} ≠ estado corrente {cur!r}")
            if to not in TRANS.get(cur, set()):
                errs.append(f"transição ilegal {cur!r}→{to!r}")
        cur = to
    if cur != st:
        errs.append(f"estado final {st!r} ≠ última transição {cur!r}")
    cons = [h for h in hist if h.get("to") == "consumed"]
    if len(cons) > 1:
        tokens = {h.get("claim_token") for h in cons}
        if len(tokens) > 1:
            errs.append("dois consumed com claim_tokens diferentes")
        else:
            errs.append("consumed duplicado")
    if st == "consumed":
        c = item.get("consumed") or {}
        if not c.get("claim_token"):
            errs.append("consumed sem claim_token")
    if st == "claimed":
        c = item.get("consumer") or {}
        if not c.get("claim_token") or not c.get("consumer_id"):
            errs.append("claimed sem consumer completo")
    return errs


def merge_items(ours: dict, theirs: dict) -> dict:
    """Merge semântico seguro. Levanta UnsafeMerge se precisaria descartar ou inventar transição.

    Política (mesmo ID):
    - conteúdos idênticos → qualquer;
    - history de um é prefixo do outro → fica o mais avançado (se validate ok);
    - dois claimed com consumers/tokens diferentes (ambos válidos) → UnsafeMerge;
    - dois consumed com tokens diferentes → UnsafeMerge;
    - históricos divergentes / transição inválida no resultado → UnsafeMerge.
    IDs distintos não passam por aqui (arquivos diferentes, sem conflito de path).
    """
    if ours.get("id") != theirs.get("id"):
        raise UnsafeMerge(f"merge_items exigiu mesmo id: {ours.get('id')} vs {theirs.get('id')}")
    if dumps(ours) == dumps(theirs):
        return json.loads(json.dumps(ours))

    # payload essencial diverge → nunca descartar silenciosamente (mesmo que history coincida)
    core = lambda it: (it.get("summary"), tuple(it.get("next_steps") or []),
                       tuple(it.get("open_questions") or []),
                       (it.get("recovery") or {}).get("original_sha256"),
                       (it.get("migration") or {}).get("original_sha256"))
    if core(ours) != core(theirs):
        raise UnsafeMerge(f"{ours['id']}: mesmo ID com conteúdo essencial diferente (não descartar)")

    co, ct = ours.get("consumer") or {}, theirs.get("consumer") or {}
    if (ours.get("state") == "claimed" and theirs.get("state") == "claimed"
            and co.get("claim_token") and ct.get("claim_token")
            and co.get("claim_token") != ct.get("claim_token")
            and not _expired(ours) and not _expired(theirs)):
        raise UnsafeMerge(f"{ours['id']}: dois claimed vivos com tokens diferentes")

    cons_o = [h for h in (ours.get("history") or []) if h.get("to") == "consumed"]
    cons_t = [h for h in (theirs.get("history") or []) if h.get("to") == "consumed"]
    toks = {h.get("claim_token") for h in cons_o + cons_t if h.get("claim_token")}
    if len(toks) > 1:
        raise UnsafeMerge(f"{ours['id']}: históricos com consumed de tokens diferentes")

    # evolução linear: prefixo
    if _is_prefix_hist(ours, theirs):
        cand = json.loads(json.dumps(theirs))
    elif _is_prefix_hist(theirs, ours):
        cand = json.loads(json.dumps(ours))
    else:
        # tentar união só se um estado domina e tokens não conflitam
        rank = {"consumed": 3, "failed": 2, "claimed": 1, "pending": 0}
        def score(it):
            r = rank.get(it["state"], -1)
            if it["state"] == "claimed" and _expired(it):
                r = 0
            return r
        if score(ours) == score(theirs) and ours["state"] in ("pending", "failed"):
            # pending/failed equivalentes: unir history e validar
            cand = json.loads(json.dumps(ours if len(ours.get("history") or []) >= len(theirs.get("history") or []) else theirs))
        elif score(ours) > score(theirs):
            cand = json.loads(json.dumps(ours))
        elif score(theirs) > score(ours):
            cand = json.loads(json.dumps(theirs))
        else:
            raise UnsafeMerge(f"{ours['id']}: históricos divergentes sem evolução linear")
        seen, hist = set(), []
        for h in (ours.get("history") or []) + (theirs.get("history") or []):
            k = (h.get("at"), h.get("from"), h.get("to"), h.get("by"), h.get("claim_token"))
            if k not in seen:
                seen.add(k); hist.append(h)
        hist.sort(key=lambda h: (h.get("at") or "", h.get("to") or ""))
        cand["history"] = hist
        # reconstruir estado pela última transição
        if hist:
            cand["state"] = hist[-1]["to"]

    errs = validate_item(cand)
    if errs:
        raise UnsafeMerge(f"{ours['id']}: merge produziria item inválido: {errs}")
    return cand


# ---------- migração / recuperação (aberto.json legado) ----------

def _item_from_aberto(body: bytes, *, reason: str, by: str, recovery: dict | None = None, migration: dict | None = None) -> dict:
    d = json.loads(body)
    created = d.get("created_utc") or now()
    session = d.get("from_session") or "legado"
    m = re.search(r"-(\d{5,})-", session)
    run_id = m.group(1) if m else "legado"
    origin = {"workflow": d.get("from_agent") or "legado", "run_id": run_id, "run_attempt": "1",
              "sha": None, "session": session, "agent": d.get("from_agent"), "created_utc": created}
    stamp = _ts(created).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(body).hexdigest()[:12]
    iid = f"{stamp}-{run_id}-1-{digest}"
    item = {"schema": SCHEMA, "id": iid, "state": "pending",
            "summary": d.get("summary"), "next_steps": list(d.get("next_steps") or []),
            "open_questions": list(d.get("open_questions") or []),
            "files_touched": list(d.get("files_touched") or []),
            "origin": origin, "consumer": None, "consumed": None,
            "attempts": 0, "max_attempts": 3,
            "history": [{"at": now(), "from": None, "to": "pending", "by": by, "reason": reason}]}
    if recovery:
        item["recovery"] = recovery
    if migration:
        item["migration"] = migration
    return item


def migrate_aberto(mem: pathlib.Path, by: str = "aimem migrate") -> dict | None:
    ab = pathlib.Path(mem) / "handoffs" / "aberto.json"
    if not ab.is_file():
        return None
    body = ab.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    for it in load_all(mem):
        if (it.get("migration") or {}).get("original_sha256") == digest:
            return None
        if (it.get("recovery") or {}).get("original_sha256") == digest:
            return None
    raw_dir = pathlib.Path(mem) / "handoffs" / "raw"; raw_dir.mkdir(parents=True, exist_ok=True)
    raw_name = f"aberto-{digest[:12]}.json"
    (raw_dir / raw_name).write_bytes(body)
    raw_path = f"docs/memory/handoffs/raw/{raw_name}"
    item = _item_from_aberto(body, reason="migrado de aberto.json", by=by,
                             migration={"original_sha256": digest, "raw_path": raw_path, "migrated_utc": now(), "by": by})
    save(mem, item)
    return item


def recover_lost(mem: pathlib.Path, commit: str, overwritten_by: str, path: str, by: str,
                 repo: pathlib.Path | None = None) -> dict:
    cwd = str(repo or pathlib.Path.cwd())
    shown = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=cwd, capture_output=True)
    if shown.returncode != 0:
        err = (shown.stderr or shown.stdout or b"").decode("utf-8", errors="replace")[-400:]
        raise LedgerError(
            f"objeto git ausente: {commit}:{path} (cwd={cwd}). "
            f"Faça fetch completo do histórico (actions/checkout fetch-depth: 0). Detalhe: {err.strip()}"
        )
    body = shown.stdout
    digest = hashlib.sha256(body).hexdigest()
    for it in load_all(mem):
        if (it.get("recovery") or {}).get("original_sha256") == digest:
            return it
    raw_dir = pathlib.Path(mem) / "handoffs" / "raw"; raw_dir.mkdir(parents=True, exist_ok=True)
    raw_name = f"recuperado-{digest[:12]}.json"
    (raw_dir / raw_name).write_bytes(body)
    raw_path = f"docs/memory/handoffs/raw/{raw_name}"
    run_url = f"https://github.com/{REPO_SLUG}/actions/runs/39177110784"
    recovery = {"from_commit": commit, "overwritten_by_commit": overwritten_by, "source_path": path,
                "original_sha256": digest, "raw_path": raw_path, "source_run": run_url,
                "recovered_by": by, "recovered_utc": now()}
    item = _item_from_aberto(body, reason="recuperado (perdido por -X theirs)", by=by, recovery=recovery)
    save(mem, item)
    return item
