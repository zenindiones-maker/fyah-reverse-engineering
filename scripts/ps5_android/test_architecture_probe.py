import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from architecture_probe import classify_elf_header

SCRIPT = Path(__file__).with_name("architecture_probe.py")


def make_elf(machine, elf_class=2, endian=1, version=1, ehsize=64):
    order = "<" if endian == 1 else ">"
    ident = (
        b"\x7fELF"
        + bytes([elf_class, endian, version])
        + bytes(9)
    )
    # ELF64: e_type, e_machine, e_version, campos restantes
    header = struct.pack(
        order + "HHIQQQIHHHHHH",
        2, machine, 1,
        0, 0, 0, 0,
        ehsize, 56, 0, 64, 0, 0,
    )
    return ident + header


class ArchitectureProbeTests(unittest.TestCase):
    def test_x86_64_on_arm64_requires_translation(self):
        self.assertEqual(
            classify_elf_header(make_elf(62), "aarch64"),
            "translation_required",
        )

    def test_arm64_on_arm64_is_native(self):
        self.assertEqual(
            classify_elf_header(make_elf(183), "aarch64"),
            "native",
        )

    def test_arm64_elf_on_x86_64_host_is_not_native(self):
        self.assertEqual(
            classify_elf_header(make_elf(183), "x86_64"),
            "unsupported",
        )

    def test_invalid_magic_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_elf_header(b"NOT-ELF" + bytes(60), "aarch64")

    def test_truncated_header_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_elf_header(b"\x7fELF" + bytes(59), "aarch64")

    def test_elf32_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_elf_header(make_elf(62, elf_class=1), "aarch64")

    def test_invalid_endianness_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_elf_header(make_elf(62, endian=3), "aarch64")

    def test_invalid_ident_version_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_elf_header(make_elf(62, version=0), "aarch64")

    def test_invalid_header_size_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_elf_header(make_elf(62, ehsize=60), "aarch64")

    def test_x86_64_big_endian_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_elf_header(make_elf(62, endian=2), "aarch64")

    def test_cli_inspects_file_without_executing_it(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(make_elf(62))
            path = f.name
        try:
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT), path,
                    "--host", "aarch64",
                ],
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("translation_required", result.stdout)
            self.assertIn("x86_64", result.stdout)
        finally:
            os.unlink(path)

    def test_cli_rejects_invalid_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"not an ELF file")
            path = f.name
        try:
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT), path,
                    "--host", "aarch64",
                ],
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
        finally:
            os.unlink(path)


    def test_unknown_machine_is_unsupported(self):
        self.assertEqual(
            classify_elf_header(make_elf(0xFFFF), "aarch64"),
            "unsupported",
        )

    def test_unknown_host_is_rejected_for_unknown_machine(self):
        with self.assertRaises(ValueError):
            classify_elf_header(make_elf(0xFFFF), "mips")


if __name__ == "__main__":
    unittest.main(verbosity=2)
