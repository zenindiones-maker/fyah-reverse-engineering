import audio
import fyah_re_cli
import video


def test_packages_import():
    assert audio is not None and video is not None


def test_cli_placeholder_returns_zero():
    assert fyah_re_cli.main([]) == 0
