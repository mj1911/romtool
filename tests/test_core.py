import random

import pytest

from romtool import core


def test_interleave_byte_order():
    low = b"\x01\x02\x03"
    high = b"\xAA\xBB\xCC"
    combined = core.interleave([low, high])
    assert combined == b"\x01\xAA\x02\xBB\x03\xCC"


def test_interleave_deinterleave_empty_streams():
    streams = [b"", b""]
    combined = core.interleave(streams)
    assert combined == b""
    assert core.deinterleave(combined, 2) == [b"", b""]


def test_interleave_deinterleave_single_byte_streams():
    streams = [b"\xAA", b"\x55"]
    combined = core.interleave(streams)
    assert combined == b"\xAA\x55"
    assert core.deinterleave(combined, 2) == streams


@pytest.mark.parametrize("n", [2, 3, 4])
def test_interleave_deinterleave_roundtrip(n):
    streams = [bytes([i]) * 4 for i in range(n)]
    combined = core.interleave(streams)
    result = core.deinterleave(combined, n)
    assert result == streams


@pytest.mark.parametrize(
    "n,seed",
    [
        (2, 1), (2, 2),
        (3, 1), (3, 2),
        (4, 1), (4, 2),
        (8, 1), (8, 2),
    ],
)
def test_randomized_roundtrip(n, seed):
    rng = random.Random(seed)
    length = rng.randint(1, 500)
    streams = [bytes(rng.randrange(256) for _ in range(length)) for _ in range(n)]
    combined = core.interleave(streams)
    result = core.deinterleave(combined, n)
    assert result == streams


def test_checksums_empty():
    crc16_hex, crc32_hex, sha256_hex = core.checksums(b"")
    assert crc16_hex == "ffff"
    assert crc32_hex == "00000000"
    assert sha256_hex == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_checksums_crc32_known_check_value():
    # "123456789" is the standard CRC-32/ISO-HDLC (zlib) check value input;
    # the expected CRC32 is the well-known catalogue check value 0xCBF43926.
    _, crc32_hex, _ = core.checksums(b"123456789")
    assert crc32_hex == "cbf43926"


def test_checksums_crc16_known_check_value():
    # Same "123456789" catalogue input; expected CRC-16/CCITT-FALSE is
    # the well-known check value 0x29B1.
    crc16_hex, _, _ = core.checksums(b"123456789")
    assert crc16_hex == "29b1"


def test_checksums_crc16_is_zero_padded():
    # crc16 of b"\x00\x00\x0c" is 0x0d10 — exercises the leading-zero pad.
    assert core.checksums(b"\x00\x00\x0c")[0] == "0d10"


def test_checksums_format_and_determinism():
    data = bytes(range(256))
    crc16_hex, crc32_hex, sha256_hex = core.checksums(data)
    assert len(crc16_hex) == 4
    assert len(crc32_hex) == 8
    assert len(sha256_hex) == 64
    assert crc16_hex == crc16_hex.lower()
    assert crc32_hex == crc32_hex.lower()
    assert sha256_hex == sha256_hex.lower()
    assert core.checksums(data) == (crc16_hex, crc32_hex, sha256_hex)


def test_checksums_md5_known_check_value():
    # "123456789" MD5 catalogue check value, independently verified
    # against hashlib.md5(b"123456789").hexdigest().
    crc16_hex, crc32_hex, md5_hex = core.checksums(
        b"123456789", third="md5"
    )
    assert crc16_hex == "29b1"
    assert crc32_hex == "cbf43926"
    assert md5_hex == "25f9e794323b453885f5181f1b624d0b"


def test_checksums_md5_empty():
    assert core.checksums(b"", third="md5")[2] == (
        "d41d8cd98f00b204e9800998ecf8427e"
    )


def test_checksums_default_third_is_sha256():
    # Omitting `third` still defaults to sha256 — unchanged from before
    # this function was generalized.
    assert core.checksums(b"123456789") == core.checksums(
        b"123456789", third="sha256"
    )


def test_checksums_unsupported_third_raises():
    with pytest.raises(ValueError):
        core.checksums(b"data", third="bogus")


def test_crc16_ccitt_false_empty():
    # CRC-16/CCITT-FALSE has init=0xFFFF, no input/output reflection, and
    # no final XOR, so an empty input leaves the CRC at its init value.
    assert core.crc16_ccitt_false(b"") == 0xFFFF


def test_crc16_ccitt_false_known_check_value():
    # "123456789" is the standard CRC catalogue check-value input; the
    # expected result is the well-known CRC-16/CCITT-FALSE check value
    # 0x29B1.
    assert core.crc16_ccitt_false(b"123456789") == 0x29B1
