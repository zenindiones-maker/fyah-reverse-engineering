import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TRANSLATOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRANSLATOR_DIR))

from x64_to_aarch64 import translate_block


def test_all_64_register_mov_encodings_match_llvm_mc():
    llvm_mc = shutil.which("llvm-mc")
    if llvm_mc is None:
        pytest.skip("llvm-mc não está instalado")

    cases = [
        (src, dst)
        for src in range(8)
        for dst in range(8)
    ]
    assembly = "\n".join(
        f"mov w{dst}, w{src}"
        for src, dst in cases
    )

    result = subprocess.run(
        [
            llvm_mc,
            "--triple=aarch64-linux-android",
            "-show-encoding",
        ],
        input=assembly,
        text=True,
        capture_output=True,
        check=True,
    )

    encodings = re.findall(
        r"encoding: \[([^\]]+)\]",
        result.stdout,
    )
    assert len(encodings) == 64

    for (src, dst), encoded in zip(cases, encodings):
        expected = bytes(
            int(byte.strip(), 16)
            for byte in encoded.split(",")
        )

        modrm = 0xC0 | (src << 3) | dst
        x86_instruction = bytes([0x89, modrm])
        actual = translate_block(x86_instruction)

        assert actual == expected, (
            f"src={src}, dst={dst}: "
            f"tradutor={actual.hex()}, "
            f"llvm-mc={expected.hex()}"
        )
