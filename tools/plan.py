"""Allowlisted execution plans. No shell, no arbitrary Python, no hidden success."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from tools.catalog import by_name

PLAN_SCHEMA = "fyah-re/plan@1"


class PlanError(ValueError):
    """The plan is invalid and must not execute any tool."""


class PlanFailed(RuntimeError):
    """A required step failed or was blocked. `result` is the aggregate report."""

    def __init__(self, result: dict):
        super().__init__("plano exigido não concluiu com sucesso")
        self.result = result


def _reject_arbitrary(step: dict) -> None:
    forbidden = set(step) & {"shell", "command", "python", "code", "script", "argv"}
    if forbidden:
        raise PlanError("plano não pode conter execução arbitrária: " + ", ".join(sorted(forbidden)))


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise PlanError("schema do plano deve ser fyah-re/plan@1")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PlanError("plano sem passos")
    seen: set[str] = set()
    graph: dict[str, list[str]] = {}
    for step in steps:
        if not isinstance(step, dict):
            raise PlanError("passo inválido")
        _reject_arbitrary(step)
        sid = step.get("id")
        tool = step.get("tool")
        if not isinstance(sid, str) or not sid or sid in seen:
            raise PlanError("id de passo ausente ou duplicado")
        if tool not in by_name:
            raise PlanError(f"ferramenta não allowlisted: {tool}")
        if tool == "supervision-detect":
            raise PlanError("supervision-detect bloqueado até existir detector e pesos reais")
        after = step.get("after") or []
        if not isinstance(after, list) or any(not isinstance(item, str) for item in after):
            raise PlanError(f"after inválido em {sid}")
        if "input" not in step:
            raise PlanError(f"passo {sid} sem entrada")
        graph[sid] = after
        seen.add(sid)
    for step in steps:
        for dep in step.get("after") or []:
            if dep not in seen:
                raise PlanError(f"dependência desconhecida: {dep}")
        _validate_input(step.get("input"), seen, step["id"])
        if "input2" in step:
            _validate_input(step.get("input2"), seen, step["id"])
        expected = by_name[step["tool"]].get("inputs", 1)
        provided = 1 + (1 if step.get("input2") else 0)
        if provided != expected:
            raise PlanError(f"{step['tool']} exige {expected} entrada(s)")
    _assert_acyclic(graph)
    return plan


def _validate_input(value, known: set[str], sid: str) -> None:
    if isinstance(value, str) and value:
        return
    if isinstance(value, dict) and isinstance(value.get("step"), str) and value.get("artifact") == "input":
        if value["step"] not in known or value["step"] == sid:
            raise PlanError(f"referência de artefato inválida em {sid}")
        return
    raise PlanError(f"entrada inválida em {sid}")


def _assert_acyclic(graph: dict[str, list[str]]) -> None:
    color: dict[str, int] = {}

    def visit(node: str) -> None:
        color[node] = 1
        for dep in graph.get(node, []):
            state = color.get(dep, 0)
            if state == 1:
                raise PlanError("ciclo no plano")
            if state == 0:
                visit(dep)
        color[node] = 2

    for node in graph:
        if color.get(node, 0) == 0:
            visit(node)


def ordered_steps(plan: dict) -> list[dict]:
    pending = {step["id"]: step for step in plan["steps"]}
    done: set[str] = set()
    order: list[dict] = []
    while pending:
        ready = [step for step in pending.values() if set(step.get("after") or []).issubset(done)]
        if not ready:
            raise PlanError("ciclo no plano")
        ready.sort(key=lambda step: step["id"])
        for step in ready:
            order.append(step)
            done.add(step["id"])
            del pending[step["id"]]
    return order


def _resolve(value, produced: dict[str, dict]) -> str:
    if isinstance(value, str):
        return value
    previous = produced[value["step"]]
    inputs = previous.get("inputs") or []
    if previous.get("status") != "success" or not inputs:
        raise PlanError("referência aponta para passo sem entrada utilizável")
    return inputs[0]


def execute_plan(plan: dict, *, workspace: Path, run_tool: Callable) -> dict:
    """Validate the whole plan before the first tool runs, then execute in order."""
    plan = validate_plan(plan)
    workspace.mkdir(parents=True, exist_ok=True)
    produced: dict[str, dict] = {}
    steps_out: list[dict] = []
    required_failed = False
    for step in ordered_steps(plan):
        sid = step["id"]
        deps = step.get("after") or []
        blocked = [dep for dep in deps if produced[dep]["status"] != "success"]
        record = {
            "id": sid,
            "tool": step["tool"],
            "required": bool(step.get("required", True)),
            "status": "blocked" if blocked else "failed",
            "inputs": [],
            "output": None,
        }
        if blocked:
            record["blocked_by"] = blocked
            if record["required"]:
                required_failed = True
            produced[sid] = record
            steps_out.append(record)
            continue
        try:
            inputs = [_resolve(step["input"], produced)]
            if step.get("input2") is not None:
                inputs.append(_resolve(step["input2"], produced))
        except PlanError as exc:
            record["error"] = str(exc)
            if record["required"]:
                required_failed = True
            produced[sid] = record
            steps_out.append(record)
            continue
        record["inputs"] = inputs
        output = workspace / f"{sid}.json"
        try:
            data = run_tool(step["tool"], inputs, output)
        except (SystemExit, Exception) as exc:
            record["status"] = "failed"
            record["error"] = type(exc).__name__
            if record["required"]:
                required_failed = True
            produced[sid] = record
            steps_out.append(record)
            continue
        record["status"] = "success"
        record["schema"] = data.get("schema")
        record["output"] = output.name
        produced[sid] = record
        steps_out.append(record)
    result = {
        "schema": "fyah-re/orchestration@1",
        "ok": not required_failed,
        "steps": steps_out,
    }
    (workspace / "orchestration.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    if required_failed:
        raise PlanFailed(result)
    return result


def load_plan_file(path: str | Path) -> dict:
    return validate_plan(json.loads(Path(path).read_text()))
