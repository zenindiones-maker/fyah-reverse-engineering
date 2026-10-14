import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from elf_dependencies import inspect_elf


def make_elf(
    machine=62,
    needed=("libc.so.6", "libm.so.6"),
    interp="/lib64/ld-linux-x86-64.so.2",
):
    """Constrói um ELF64 little-endian sintético, sem código executável."""
    base = 0x400000
    phoff = 64
    phentsize = 56
    phnum = 3
    interp_off = 0x200
    dynamic_off = 0x240
    strings_off = 0x300

    strings = bytearray(b"\0")
    needed_offsets = []
    for name in needed:
        needed_offsets.append(len(strings))
        strings.extend(name.encode("ascii") + b"\0")

    interp_bytes = interp.encode("ascii") + b"\0" if interp else b""

    dynamic_entries = [
        (1, offset) for offset in needed_offsets
    ]
    dynamic_entries.extend([
        (5, base + strings_off),  # DT_STRTAB
        (10, len(strings)),       # DT_STRSZ
        (0, 0),                   # DT_NULL
    ])
    dynamic_bytes = b"".join(
        struct.pack("<qQ", tag, value)
        for tag, value in dynamic_entries
    )

    total = max(
        strings_off + len(strings),
        dynamic_off + len(dynamic_bytes),
        interp_off + len(interp_bytes),
    )
    data = bytearray(total)

    ident = b"\x7fELF" + bytes([2, 1, 1]) + bytes(9)
    header = struct.pack(
        "<HHIQQQIHHHHHH",
        3, machine, 1, 0, phoff, 0, 0,
        64, phentsize, phnum, 0, 0, 0,
    )
    data[:16] = ident
    data[16:64] = header

    def phdr(kind, offset, vaddr, filesz, memsz, flags=4, align=1):
        return struct.pack(
            "<IIQQQQQQ",
            kind, flags, offset, vaddr, 0,
            filesz, memsz, align,
        )

    load = phdr(1, 0, base, total, total, flags=4, align=0x1000)
    interp_ph = phdr(
        3, interp_off, base + interp_off,
        len(interp_bytes), len(interp_bytes),
    ) if interp_bytes else phdr(0, 0, 0, 0, 0)
    dynamic_ph = phdr(
        2, dynamic_off, base + dynamic_off,
        len(dynamic_bytes), len(dynamic_bytes),
    )

    data[phoff:phoff + 56] = load
    data[phoff + 56:phoff + 112] = interp_ph
    data[phoff + 112:phoff + 168] = dynamic_ph
    data[interp_off:interp_off + len(interp_bytes)] = interp_bytes
    data[dynamic_off:dynamic_off + len(dynamic_bytes)] = dynamic_bytes
    data[strings_off:strings_off + len(strings)] = strings
    return bytes(data)


class ElfDependencyTests(unittest.TestCase):
    def test_reads_interpreter_and_needed_libraries(self):
        result = inspect_elf(make_elf(), host="aarch64")
        self.assertEqual(result["architecture"], "x86_64")
        self.assertEqual(result["interpreter"]["path"],
                         "/lib64/ld-linux-x86-64.so.2")
        self.assertEqual(
            result["needed"],
            ["libc.so.6", "libm.so.6"],
        )
        self.assertEqual(result["classification"], "translation_required")

    def test_no_interpreter_is_reported_as_none(self):
        result = inspect_elf(make_elf(interp=""), host="x86_64")
        self.assertIsNone(result["interpreter"])

    def test_truncated_elf_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect_elf(b"\x7fELF" + bytes(20), host="aarch64")

    def test_invalid_program_header_offset_is_rejected(self):
        data = bytearray(make_elf())
        struct.pack_into("<Q", data, 32, len(data) + 100)
        with self.assertRaises(ValueError):
            inspect_elf(bytes(data), host="aarch64")

    def test_unmapped_string_table_is_rejected(self):
        data = bytearray(make_elf())
        # DT_STRTAB: substituir o endereço virtual por um endereço sem PT_LOAD.
        dynamic_off = 0x240
        needed_count = len(("libc.so.6", "libm.so.6"))
        strtab_value_offset = dynamic_off + needed_count * 16 + 8
        struct.pack_into("<Q", data, strtab_value_offset, 0x7FFFFFFFFFFF)
        with self.assertRaises(ValueError):
            inspect_elf(bytes(data), host="aarch64")

    def test_library_resolution_statuses(self):
        result = inspect_elf(
            make_elf(needed=("libc.so.6", "libmissing.so")),
            host="x86_64",
            library_dirs=[],
        )
        statuses = {item["name"]: item["status"]
                    for item in result["dependencies"]}
        self.assertEqual(statuses["libc.so.6"], "unverified")
        self.assertEqual(statuses["libmissing.so"], "unverified")

    def test_library_is_found_in_explicit_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            library = Path(temp) / "libdemo.so"
            library.write_bytes(make_elf(machine=62, needed=(), interp=""))
            result = inspect_elf(
                make_elf(needed=("libdemo.so",), interp=""),
                host="x86_64",
                library_dirs=[temp],
            )
        self.assertEqual(result["dependencies"][0]["status"], "found")

    def test_wrong_architecture_library_is_incompatible(self):
        with tempfile.TemporaryDirectory() as temp:
            library = Path(temp) / "libdemo.so"
            library.write_bytes(
                make_elf(machine=183, needed=(), interp="")
            )
            result = inspect_elf(
                make_elf(needed=("libdemo.so",), interp=""),
                host="x86_64",
                library_dirs=[temp],
            )
        self.assertEqual(
            result["dependencies"][0]["status"], "incompatible"
        )

    def test_cli_emits_json_without_executing_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "sample.elf"
            binary.write_bytes(make_elf())
            process = subprocess.run(
                [
                    sys.executable,
                    str(BASE / "elf_dependencies.py"),
                    str(binary),
                    "--host", "aarch64",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["architecture"], "x86_64")
        self.assertEqual(report["needed"], ["libc.so.6", "libm.so.6"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
