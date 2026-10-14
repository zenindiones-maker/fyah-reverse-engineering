#!/usr/bin/env python3
"""Inspeção estática de dependências ELF64; nunca executa o binário."""

import argparse
import json
import struct
import sys
from pathlib import Path

ELF_HEADER_SIZE = 64
PHDR_SIZE = 56
DYNAMIC_SIZE = 16

ELFCLASS64 = 2
ELFDATA2LSB = 1
ELFDATA2MSB = 2

PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3

DT_NULL = 0
DT_NEEDED = 1
DT_STRTAB = 5
DT_STRSZ = 10

MACHINE_NAMES = {62: "x86_64", 183: "aarch64"}
HOST_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def _range(data, offset, size, label):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise ValueError(f"{label}: range outside file")
    return data[offset:offset + size]


def _cstring(data, offset, limit, label):
    if offset < 0 or offset >= limit or limit > len(data):
        raise ValueError(f"{label}: invalid string offset")
    end = data.find(b"\0", offset, limit)
    if end < 0:
        raise ValueError(f"{label}: unterminated string")
    try:
        return data[offset:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: invalid UTF-8") from exc


def inspect_elf(data: bytes, host: str, library_dirs=None):
    if not isinstance(data, bytes):
        raise TypeError("ELF data must be bytes")

    if len(data) < ELF_HEADER_SIZE:
        raise ValueError("Truncated ELF header")
    if data[:4] != b"\x7fELF":
        raise ValueError("Invalid ELF magic")
    if data[4] != ELFCLASS64:
        raise ValueError("Only ELF64 is supported")
    if data[5] not in (ELFDATA2LSB, ELFDATA2MSB):
        raise ValueError("Invalid ELF endianness")
    if data[6] != 1:
        raise ValueError("Invalid ELF identification version")

    order = "<" if data[5] == ELFDATA2LSB else ">"
    (
        e_type, machine, version, _entry, phoff, _shoff, _flags,
        ehsize, phentsize, phnum, _shentsize, _shnum, _shstrndx,
    ) = struct.unpack_from(order + "HHIQQQIHHHHHH", data, 16)

    if version != 1 or ehsize != ELF_HEADER_SIZE:
        raise ValueError("Invalid ELF64 header version or size")
    if e_type not in (2, 3):
        raise ValueError(f"Unsupported ELF file type: {e_type}")
    if phnum and phentsize < PHDR_SIZE:
        raise ValueError("Program header entry is too small")
    if phnum > 65535:
        raise ValueError("Excessive program header count")

    host_name = HOST_ALIASES.get(host.lower())
    if host_name is None:
        raise ValueError(f"Unsupported host architecture: {host}")

    phdr_bytes = phnum * phentsize
    _range(data, phoff, phdr_bytes, "Program header table")

    segments = []
    for index in range(phnum):
        off = phoff + index * phentsize
        values = struct.unpack_from(order + "IIQQQQQQ", data, off)
        kind, flags, fileoff, vaddr, _paddr, filesz, memsz, align = values
        if filesz > memsz and kind == PT_LOAD:
            raise ValueError(f"PT_LOAD[{index}]: filesz exceeds memsz")
        _range(data, fileoff, filesz, f"Program segment {index}")
        segments.append({
            "type": kind,
            "flags": flags,
            "offset": fileoff,
            "vaddr": vaddr,
            "filesz": filesz,
            "memsz": memsz,
            "align": align,
        })

    def vaddr_to_offset(address, size, label):
        for seg in segments:
            if seg["type"] != PT_LOAD:
                continue
            start = seg["vaddr"]
            delta = address - start
            if delta >= 0 and delta <= seg["filesz"] and size <= seg["filesz"] - delta:
                return seg["offset"] + delta
        raise ValueError(f"{label}: virtual address is not backed by PT_LOAD")

    interp = None
    for seg in segments:
        if seg["type"] == PT_INTERP:
            if interp is not None:
                raise ValueError("Multiple PT_INTERP segments")
            raw = _range(data, seg["offset"], seg["filesz"], "PT_INTERP")
            if not raw or raw[-1] != 0 or b"\0" in raw[:-1]:
                raise ValueError("Malformed PT_INTERP string")
            try:
                interp = {"path": raw[:-1].decode("utf-8")}
            except UnicodeDecodeError as exc:
                raise ValueError("PT_INTERP is not valid UTF-8") from exc

    dynamic_segments = [s for s in segments if s["type"] == PT_DYNAMIC]
    if len(dynamic_segments) > 1:
        raise ValueError("Multiple PT_DYNAMIC segments")

    needed_offsets = []
    strtab_address = None
    strsz = None

    if dynamic_segments:
        dynamic = dynamic_segments[0]
        if dynamic["filesz"] % DYNAMIC_SIZE:
            raise ValueError("PT_DYNAMIC size is not entry-aligned")

        found_null = False
        for pos in range(dynamic["offset"],
                         dynamic["offset"] + dynamic["filesz"],
                         DYNAMIC_SIZE):
            tag, value = struct.unpack_from(order + "qQ", data, pos)
            if tag == DT_NULL:
                found_null = True
                break
            if tag == DT_NEEDED:
                needed_offsets.append(value)
            elif tag == DT_STRTAB:
                strtab_address = value
            elif tag == DT_STRSZ:
                strsz = value

        if not found_null:
            raise ValueError("PT_DYNAMIC has no DT_NULL terminator")

    needed = []
    if needed_offsets:
        if strtab_address is None or strsz is None:
            raise ValueError("DT_NEEDED requires DT_STRTAB and DT_STRSZ")
        if strsz == 0:
            raise ValueError("DT_STRSZ must be nonzero")
        strtab_offset = vaddr_to_offset(
            strtab_address, strsz, "DT_STRTAB"
        )
        _range(data, strtab_offset, strsz, "Dynamic string table")
        for string_offset in needed_offsets:
            if string_offset >= strsz:
                raise ValueError("DT_NEEDED offset exceeds DT_STRSZ")
            name = _cstring(
                data, strtab_offset + string_offset,
                strtab_offset + strsz, "DT_NEEDED",
            )
            if not name:
                raise ValueError("Empty DT_NEEDED entry")
            needed.append(name)

    architecture = MACHINE_NAMES.get(machine, "unknown")
    if architecture == "unknown":
        classification = "unsupported"
    elif architecture == host_name:
        classification = "native"
    elif architecture == "x86_64" and host_name == "aarch64":
        classification = "translation_required"
    else:
        classification = "unsupported"

    dirs = [Path(p) for p in (library_dirs or [])]
    dependencies = []
    for name in needed:
        # DT_NEEDED normalmente é um nome, mas caminhos absolutos ou com
        # separadores também podem aparecer em binários malformados/atípicos.
        candidate_name = Path(name)
        if candidate_name.is_absolute() or len(candidate_name.parts) > 1:
            candidates = [candidate_name]
        else:
            candidates = [directory / name for directory in dirs]

        resolved = None
        for candidate in candidates:
            try:
                if candidate.is_file():
                    resolved = candidate
                    break
            except OSError:
                continue

        item = {"name": name, "path": str(resolved) if resolved else None}
        if resolved is None:
            item["status"] = "missing" if dirs else "unverified"
        else:
            try:
                library_data = resolved.read_bytes()
                library_info = inspect_elf(
                    library_data, host=host, library_dirs=[]
                )
                if library_info["architecture"] != architecture:
                    item["status"] = "incompatible"
                    item["reason"] = (
                        "library architecture differs from the inspected ELF"
                    )
                else:
                    item["status"] = "found"
            except (OSError, ValueError, TypeError, RecursionError):
                item["status"] = "incompatible"
                item["reason"] = "file is not a valid supported ELF64 library"
        dependencies.append(item)

    return {
        "format": "ELF64",
        "architecture": architecture,
        "machine": machine,
        "host": host_name,
        "classification": classification,
        "interpreter": interp,
        "needed": needed,
        "dependencies": dependencies,
        "execution_performed": False,
        "limitations": [
            "Does not load or execute the binary",
            "Found libraries are checked for ELF architecture, not ABI compatibility",
            "Library search only covers explicitly supplied directories",
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Inspect ELF64 dependencies without executing the binary."
    )
    parser.add_argument("file")
    parser.add_argument("--host", required=True, choices=sorted(HOST_ALIASES))
    parser.add_argument(
        "--lib-dir", action="append", default=[],
        help="Directory to search for DT_NEEDED libraries; repeatable",
    )
    args = parser.parse_args()

    try:
        data = Path(args.file).read_bytes()
        report = inspect_elf(data, args.host, args.library_dirs if False else args.lib_dir)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, struct.error) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
