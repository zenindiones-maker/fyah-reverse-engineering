"""Decodificação da assinatura CPUID da folha básica 1, registrador EAX."""

def decode_signature(signature):
    if isinstance(signature, bool) or not isinstance(signature, int):
        raise TypeError("signature deve ser um inteiro de 32 bits")
    if not 0 <= signature <= 0xFFFFFFFF:
        raise ValueError("signature fora do intervalo uint32")

    base_family = (signature >> 8) & 0xF
    base_model = (signature >> 4) & 0xF
    extended_family = (signature >> 20) & 0xFF
    extended_model = (signature >> 16) & 0xF
    stepping = signature & 0xF

    family = base_family
    if base_family == 0xF:
        family += extended_family

    model = base_model
    if base_family in (0x6, 0xF):
        model += extended_model << 4

    return {
        "signature": f"0x{signature:08X}",
        "base_family": base_family,
        "base_model": base_model,
        "extended_family": extended_family,
        "extended_model": extended_model,
        "family": family,
        "model": model,
        "stepping": stepping,
    }
