import shutil

from pipelines import probe_disassembler


def test_probe_disassembler_reports_rizin_unavailable(monkeypatch, tmp_path):
    sample = tmp_path / "authorized.bin"
    sample.write_bytes(b"fyah-owned-test-bytes")
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    report = probe_disassembler(str(sample))
    assert report["available"] is False
    assert "ausentes" in report["error"]
