"""Registro de efeitos idempotentes (chave = handoff_id + claim_token + attempt_id).

O efeito é gravado em docs/memory/handoffs/efeitos/<key>.json ANTES do confirm.
Na retomada, se a chave já existe, o efeito não é reaplicado — só se confirma o consumo.
"""
from __future__ import annotations

import json, pathlib, re

from aimem import ledger
from aimem.nomes import valida_nome


class EffectError(RuntimeError):
    pass


def effect_key(handoff_id: str, claim_token: str, attempt_id: str | None = None) -> str:
    """Chave estável do efeito: handoff_id + claim_token (attempt_id é auditoria, não parte da chave)."""
    raw = f"{handoff_id}:{claim_token}"
    safe = re.sub(r"[^a-zA-Z0-9._:-]+", "_", raw)
    return safe


def effects_dir(mem: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(mem) / "handoffs" / "efeitos"


def path_for(mem: pathlib.Path, key: str) -> pathlib.Path:
    return effects_dir(mem) / valida_nome(f"{key}.json")


def find(mem: pathlib.Path, handoff_id: str, claim_token: str, attempt_id: str) -> dict | None:
    p = path_for(mem, effect_key(handoff_id, claim_token, attempt_id))
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def apply(mem: pathlib.Path, handoff: dict, payload: dict) -> tuple[dict, bool]:
    """Aplica o efeito uma vez. Retorna (registro, created). created=False se já existia (dedup)."""
    c = handoff.get("consumer") or {}
    token, attempt = c.get("claim_token"), c.get("attempt_id")
    if not token or not attempt:
        raise EffectError("handoff sem claim_token/attempt_id")
    key = effect_key(handoff["id"], token, attempt)
    p = path_for(mem, key)          # valida o nome ANTES de criar diretório/arquivo
    effects_dir(mem).mkdir(parents=True, exist_ok=True)
    if p.is_file():
        return json.loads(p.read_text()), False
    rec = {"key": key, "handoff_id": handoff["id"], "claim_token": token, "attempt_id": attempt,
           "consumer_id": c.get("consumer_id"), "applied_utc": ledger.now(), "payload": payload,
           "status": "applied"}
    p.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    return rec, True


def count_for_handoff(mem: pathlib.Path, handoff_id: str) -> int:
    d = effects_dir(mem)
    if not d.is_dir():
        return 0
    n = 0
    for p in d.glob("*.json"):
        try:
            if json.loads(p.read_text()).get("handoff_id") == handoff_id:
                n += 1
        except Exception:  # noqa: BLE001
            pass
    return n
