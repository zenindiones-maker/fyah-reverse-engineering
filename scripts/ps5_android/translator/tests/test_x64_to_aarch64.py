import pytest

from x64_to_aarch64 import translate_block, UnsupportedInstruction


def test_translates_x64_nop_to_aarch64_nop():
    assert translate_block(bytes.fromhex("90")) == bytes.fromhex("1f2003d5")


def test_translates_x64_ret_to_aarch64_ret():
    assert translate_block(bytes.fromhex("c3")) == bytes.fromhex("c0035fd6")


def test_translates_multiple_supported_instructions():
    assert translate_block(bytes.fromhex("90c3")) == bytes.fromhex(
        "1f2003d5c0035fd6"
    )


def test_rejects_unsupported_opcode():
    with pytest.raises(UnsupportedInstruction):
        translate_block(bytes.fromhex("ff"))


def test_translates_mov_eax_ecx():
    # x86-64: mov eax, ecx
    # AArch64: mov w0, w1 (alias de ORR)
    assert translate_block(bytes.fromhex("89c8")) == bytes.fromhex(
        "e003012a"
    )


def test_translates_mov_ebx_eax():
    # x86-64: mov ebx, eax
    # AArch64: mov w3, w0
    assert translate_block(bytes.fromhex("89c3")) == bytes.fromhex(
        "e303002a"
    )


def test_rejects_truncated_mov():
    with pytest.raises(UnsupportedInstruction):
        translate_block(bytes.fromhex("89"))


def test_rejects_memory_form_of_mov():
    # 89 08 usa memória; ainda não suportamos essa forma.
    with pytest.raises(UnsupportedInstruction):
        translate_block(bytes.fromhex("8908"))
