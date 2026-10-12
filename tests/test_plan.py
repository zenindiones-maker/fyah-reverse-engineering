import json
import math
import wave
from pathlib import Path

import pytest

from tools.plan import PlanError, PlanFailed, execute_plan, validate_plan


def _plan(steps):
    return {"schema": "fyah-re/plan@1", "steps": steps}


def test_plan_rejects_unknown_tool_and_cycle_before_any_execution():
    calls = []

    def run_tool(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("não deveria executar")

    with pytest.raises(PlanError, match="não allowlisted"):
        validate_plan(_plan([{"id": "a", "tool": "not-real", "input": "x.wav"}]))
    with pytest.raises(PlanError, match="ciclo"):
        validate_plan(_plan([
            {"id": "a", "tool": "media-inspect", "input": "x.wav", "after": ["b"]},
            {"id": "b", "tool": "audio-profile", "input": {"step": "a", "artifact": "input"}, "after": ["a"]},
        ]))
    with pytest.raises(PlanError, match="arbitrária"):
        validate_plan(_plan([{"id": "a", "tool": "media-inspect", "input": "x.wav", "shell": "rm -rf /"}]))
    assert calls == []


def test_failed_required_step_blocks_dependent_tool(tmp_path):
    calls = []

    def run_tool(name, _inputs, _out):
        calls.append(name)
        raise SystemExit(1)

    with pytest.raises(PlanFailed) as exc:
        execute_plan(_plan([
            {"id": "inspect", "tool": "media-inspect", "input": "missing.wav"},
            {"id": "profile", "tool": "audio-profile", "input": {"step": "inspect", "artifact": "input"}, "after": ["inspect"]},
        ]), workspace=tmp_path, run_tool=run_tool)
    assert calls == ["media-inspect"]
    report = exc.value.result
    assert report["ok"] is False
    assert report["steps"][1]["status"] == "blocked"
    assert report["steps"][1]["blocked_by"] == ["inspect"]


def _tone(path: Path, seconds: float = 4.0, frequency: float = 440.0) -> None:
    sample_rate = 22050
    frames = bytearray()
    for i in range(int(sample_rate * seconds)):
        value = int(8000 * math.sin(2 * math.pi * frequency * i / sample_rate))
        frames.extend(value.to_bytes(2, "little", signed=True))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)


def _scene_video(path: Path) -> None:
    import numpy as np
    import cv2
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened()
    rng = np.random.default_rng(3)
    for _scene in range(3):
        frame = rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)
        for _ in range(15):
            writer.write(frame)
    writer.release()


def test_orchestration_e2e_runs_real_media_profile_compare_and_cuts(tmp_path):
    from tools.__main__ import run_tool

    tone_a = tmp_path / "tone-a.wav"
    tone_b = tmp_path / "tone-b.wav"
    video = tmp_path / "scenes.mp4"
    _tone(tone_a, frequency=440)
    _tone(tone_b, frequency=554)
    _scene_video(video)
    workspace = tmp_path / "run"
    result = execute_plan(_plan([
        {"id": "inspect", "tool": "media-inspect", "input": str(tone_a)},
        {"id": "profile", "tool": "audio-profile", "input": {"step": "inspect", "artifact": "input"}, "after": ["inspect"]},
        {"id": "compare", "tool": "compare", "input": str(tone_a), "input2": str(tone_b), "after": ["profile"]},
        {"id": "cuts", "tool": "cuts-pacing", "input": str(video)},
    ]), workspace=workspace, run_tool=run_tool)

    assert result["ok"] is True
    assert {step["status"] for step in result["steps"]} == {"success"}
    inspected = json.loads((workspace / "inspect.json").read_text())
    profile = json.loads((workspace / "profile.json").read_text())
    compared = json.loads((workspace / "compare.json").read_text())
    cuts = json.loads((workspace / "cuts.json").read_text())
    assert inspected["ffprobe"]["streams"][0]["codec_name"] == "pcm_s16le"
    assert profile["schema"] == "fyah-re/audio-profile@1"
    assert profile["duration_s"] == 4.0
    assert profile["spectrum"]["centroid_hz"] > 0
    assert compared["schema"] == "fyah-re/audio-compare@1"
    assert "Comparação de faixas" in (workspace / "compare.md").read_text()
    assert cuts["schema"] == "fyah-re/video-pacing@1"
    assert cuts["shots"] >= 2
    inspect_receipt = json.loads((workspace / "inspect.json.receipt.json").read_text())
    assert inspect_receipt["output_artifacts"][0]["sha256"]
    compare_receipt = json.loads((workspace / "compare.json.receipt.json").read_text())
    assert {item["path"] for item in compare_receipt["output_artifacts"]} == {"compare.json", "compare.md"}
