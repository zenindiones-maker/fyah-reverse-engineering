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
