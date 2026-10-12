import pytest

import audio
import fyah_re_cli
import video


def test_packages_import():
    assert audio is not None and video is not None


def test_cli_without_command_does_not_claim_success():
    with pytest.raises(SystemExit) as exc:
        fyah_re_cli.main([])
    assert exc.value.code == 2
