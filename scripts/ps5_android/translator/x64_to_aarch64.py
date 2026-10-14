class UnsupportedInstruction(ValueError):
    pass


def translate_block(code: bytes) -> bytes:
    if not isinstance(code, bytes):
        raise TypeError("code must be bytes")

    output = bytearray()
    offset = 0

    while offset < len(code):
        opcode = code[offset]

        if opcode == 0x90:  # NOP
            output.extend(bytes.fromhex("1f2003d5"))
            offset += 1
            continue

        if opcode == 0xC3:  # RET
            output.extend(bytes.fromhex("c0035fd6"))
            offset += 1
            continue

        if opcode == 0x89:  # MOV r/m32, r32
            if offset + 1 >= len(code):
                raise UnsupportedInstruction(
                    f"Truncated MOV at offset {offset}"
                )

            modrm = code[offset + 1]
            mod = (modrm >> 6) & 0b11

            # Apenas modo registrador; memória ainda não é suportada.
            if mod != 0b11:
                raise UnsupportedInstruction(
                    f"MOV memory form unsupported at offset {offset}"
                )

            src = (modrm >> 3) & 0b111
            dst = modrm & 0b111

            # AArch64: ORR Wd, WZR, Wm (alias MOV Wd, Wm).
            # Mapeamento experimental: índices x86 0..7 -> W0..W7.
            instruction = 0x2A0003E0 | (src << 16) | dst
            output.extend(instruction.to_bytes(4, "little"))
            offset += 2
            continue

        raise UnsupportedInstruction(
            f"Unsupported x86-64 opcode 0x{opcode:02x} at offset {offset}"
        )

    return bytes(output)
