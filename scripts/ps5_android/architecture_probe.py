#!/usr/bin/env python3

import argparse
import struct
import sys
from pathlib import Path

ELF_HEADER_SIZE = 64
ELFCLASS64 = 2
ELFDATA2LSB = 1
ELFDATA2MSB = 2
EV_CURRENT = 1
EM_X86_64 = 62
EM_AARCH64 = 183

MACHINE_NAMES = {
    EM_X86_64: "x86_64",
    EM_AARCH64: "aarch64",
}

HOST_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def classify_elf_header(data: bytes, host: str) -> str:
    """Classifica um cabeçalho ELF64; não executa o arquivo."""

    if not isinstance(data, bytes):
        raise TypeError("ELF data must be bytes")

    if len(data) < ELF_HEADER_SIZE:
        raise ValueError("Truncated ELF64 header: expected 64 bytes")

    if data[:4] != b"\x7fELF":
        raise ValueError("Invalid ELF magic")

    elf_class, elf_data, ident_version = data[4], data[5], data[6]

    if elf_class != ELFCLASS64:
        raise ValueError(f"Unsupported ELF class: {elf_class}")

    if elf_data not in (ELFDATA2LSB, ELFDATA2MSB):
        raise ValueError(f"Invalid ELF endianness value: {elf_data}")

    if ident_version != EV_CURRENT:
        raise ValueError(f"Invalid ELF identification version: {ident_version}")

    order = "<" if elf_data == ELFDATA2LSB else ">"

    e_type, e_machine = struct.unpack_from(order + "HH", data, 16)
    e_version = struct.unpack_from(order + "I", data, 20)[0]
    e_ehsize = struct.unpack_from(order + "H", data, 52)[0]

    if e_version != EV_CURRENT:
        raise ValueError(f"Invalid ELF header version: {e_version}")

    if e_ehsize != ELF_HEADER_SIZE:
        raise ValueError(
            f"Invalid ELF64 header size: {e_ehsize}; expected 64"
        )

    if e_type not in (2, 3):
        raise ValueError(f"Unsupported ELF file type: {e_type}")

    normalized_host = HOST_ALIASES.get(host.lower())
    if normalized_host is None:
        raise ValueError(f"Unsupported host architecture: {host}")

    machine_name = MACHINE_NAMES.get(e_machine)
    if machine_name is None:
        return "unsupported"

    if machine_name == "x86_64" and elf_data != ELFDATA2LSB:
        raise ValueError("x86_64 ELF must use little-endian encoding")

    if machine_name == normalized_host:
        return "native"

    if machine_name == "x86_64" and normalized_host == "aarch64":
        return "translation_required"

    return "unsupported"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect an ELF64 header without executing it."
    )
    parser.add_argument("file", help="Path to the ELF file")
    parser.add_argument(
        "--host",
        required=True,
        choices=sorted(HOST_ALIASES),
        help="Host architecture",
    )
    args = parser.parse_args()

    try:
        data = Path(args.file).read_bytes()
        classification = classify_elf_header(data, args.host)
        order = "<" if data[5] == ELFDATA2LSB else ">"
        machine = struct.unpack_from(order + "H", data, 18)[0]
        architecture = MACHINE_NAMES.get(machine, "unknown")

        print(f"architecture={architecture}")
        print(f"host={HOST_ALIASES[args.host]}")
        print(f"classification={classification}")
        return 0

    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
