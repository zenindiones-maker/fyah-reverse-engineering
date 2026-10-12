import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "harness" / "run_dsh.py"
SPEC = importlib.util.spec_from_file_location("run_dsh", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_rea_decision_mode_uses_dedicated_prompt_without_media_tool_catalog():
    system, task = MODULE.build_dsh_prompts(
        task="Inspect the authorized fixture with REA MCP.",
        file_url="https://example.invalid/audio.ogg",
        decision_mode=True,
        base_system="BASE MEDIA SYSTEM",
        tools_prompt="MEDIA TOOL CATALOG",
    )
    assert "MEDIA TOOL CATALOG" not in system
    assert "BASE MEDIA SYSTEM" not in system
    assert "authorized fixture" in system.lower()
    assert "REA_MCP_REQUEST=inspect_artifact" in task
    assert "REA_MCP_REQUEST=deny" in task
    assert "https://example.invalid/audio.ogg" not in task


def test_normal_mode_keeps_existing_media_prompt_and_url():
    system, task = MODULE.build_dsh_prompts(
        task="Analyze the audio.",
        file_url="https://example.invalid/audio.ogg",
        decision_mode=False,
        base_system="BASE MEDIA SYSTEM",
        tools_prompt="MEDIA TOOL CATALOG",
    )
    assert "BASE MEDIA SYSTEM" in system
    assert "MEDIA TOOL CATALOG" in system
    assert "https://example.invalid/audio.ogg" in task
    assert "REA_MCP_REQUEST=inspect_artifact" not in task
