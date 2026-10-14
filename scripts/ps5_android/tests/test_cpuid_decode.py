import pytest

from cpuid_decode import decode_signature


def test_decodes_profile_max_signature():
    result = decode_signature(0x00000663)
    assert result == {
        "signature": "0x00000663",
        "base_family": 6,
        "base_model": 6,
        "extended_family": 0,
        "extended_model": 0,
        "family": 6,
        "model": 6,
        "stepping": 3,
    }


def test_decodes_profile_epyc_rome_signature():
    result = decode_signature(0x00830F10)
    assert result == {
        "signature": "0x00830F10",
        "base_family": 15,
        "base_model": 1,
        "extended_family": 8,
        "extended_model": 3,
        "family": 23,
        "model": 49,
        "stepping": 0,
    }


@pytest.mark.parametrize("value", [-1, 0x1_0000_0000, True, "663", None])
def test_rejects_invalid_signature(value):
    with pytest.raises((TypeError, ValueError)):
        decode_signature(value)
