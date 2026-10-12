import json

import pytest

import fyah_re_cli


def test_cli_list_outputs_catalog_json(capsys):
    assert fyah_re_cli.main(["list"]) == 0
    output = capsys.readouterr().out
    catalog = json.loads(output)
    assert isinstance(catalog, list)
    assert "media-inspect" in {item["name"] for item in catalog}


def test_cli_without_command_fails_instead_of_claiming_success():
    with pytest.raises(SystemExit) as exc:
        fyah_re_cli.main([])
    assert exc.value.code == 2


def test_cli_unknown_tool_fails_with_actionable_error(capsys):
    with pytest.raises(SystemExit) as exc:
        fyah_re_cli.main([
            "run", "not-a-real-tool",
            "--input", "fixture.bin",
            "--out", "out.json",
        ])
    assert exc.value.code != 0
    assert "ferramenta desconhecida" in str(exc.value).lower()



def test_catalog_entries_have_registered_execution_routes():
    import importlib.util
    from tools.catalog import CATALOG

    assert len({item["name"] for item in CATALOG}) == len(CATALOG)
    supported_kinds = {"shell", "stems", "silero_vad", "supervision"}
    pipeline_names = {"audio-full", "video-full", "apk-full", "binary-inspect"}
    for item in CATALOG:
        assert item.get("name") and item.get("version") and item.get("desc")
        if item.get("module") == "pipelines":
            assert item["name"] in pipeline_names
            assert item["argv"] == [item["name"]]
            assert importlib.util.find_spec("pipelines") is not None
        elif item.get("module"):
            assert importlib.util.find_spec(item["module"]) is not None, item["name"]
        else:
            assert item.get("kind") in supported_kinds, item["name"]


def test_supervision_tool_never_reports_fabricated_detections(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    output = tmp_path / "detections.json"
    result = subprocess.run(
        [sys.executable, "-m", "tools", "run", "supervision-detect",
         "--input", str(tmp_path / "not-downloaded.mp4"), "--out", str(output)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert not output.exists()
    receipt = json.loads((tmp_path / "detections.json.receipt.json").read_text())
    assert receipt["status"] == "blocked"
    assert receipt["error_category"] == "input_or_policy_rejection"
    assert receipt["output_artifacts"] == []
    assert "modelo de inferência" in result.stderr
