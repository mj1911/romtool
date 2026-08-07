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


def test_checksums_sum_known_value():
    # Plain 16-bit sum of byte values, wrapped mod 0x10000: sum("123456789"
    # ascii codes) = 477 = 0x01DD.
    sum_hex, _, _, _ = core.checksums(b"123456789")
    assert sum_hex == "01DD"


def test_checksums_empty():
    sum_hex, crc16_hex, crc32_hex, md5_hex = core.checksums(b"")
    assert sum_hex == "0000"
    assert crc16_hex == "FFFF"
    assert crc32_hex == "00000000"
    assert md5_hex == "D41D8CD98F00B204E9800998ECF8427E"


def test_checksums_crc32_known_check_value():
    # "123456789" is the standard CRC-32/ISO-HDLC (zlib) check value input;
    # the expected CRC32 is the well-known catalogue check value 0xCBF43926.
    _, _, crc32_hex, _ = core.checksums(b"123456789")
    assert crc32_hex == "CBF43926"


def test_checksums_crc16_known_check_value():
    # Same "123456789" catalogue input; expected CRC-16/CCITT-FALSE is
    # the well-known check value 0x29B1.
    _, crc16_hex, _, _ = core.checksums(b"123456789")
    assert crc16_hex == "29B1"


def test_checksums_crc16_is_zero_padded():
    # crc16 of b"\x00\x00\x0c" is 0x0d10 — exercises the leading-zero pad.
    assert core.checksums(b"\x00\x00\x0c")[1] == "0D10"


def test_checksums_sum_is_zero_padded_and_wraps():
    # sum of b"\xFF\xFF\xFF" is 0x2FD, wrapped mod 0x10000 and zero-padded.
    assert core.checksums(b"\xff\xff\xff")[0] == "02FD"


def test_checksums_format_and_determinism():
    data = bytes(range(256))
    sum_hex, crc16_hex, crc32_hex, md5_hex = core.checksums(data)
    assert len(sum_hex) == 4
    assert len(crc16_hex) == 4
    assert len(crc32_hex) == 8
    assert len(md5_hex) == 32
    assert sum_hex == sum_hex.upper()
    assert crc16_hex == crc16_hex.upper()
    assert crc32_hex == crc32_hex.upper()
    assert md5_hex == md5_hex.upper()
    assert core.checksums(data) == (sum_hex, crc16_hex, crc32_hex, md5_hex)


def test_checksums_md5_known_check_value():
    # "123456789" MD5 catalogue check value, independently verified
    # against hashlib.md5(b"123456789").hexdigest().
    _, crc16_hex, crc32_hex, md5_hex = core.checksums(b"123456789")
    assert crc16_hex == "29B1"
    assert crc32_hex == "CBF43926"
    assert md5_hex == "25F9E794323B453885F5181F1B624D0B"


def test_checksums_md5_empty():
    assert core.checksums(b"")[3] == "D41D8CD98F00B204E9800998ECF8427E"


def test_crc16_ccitt_false_empty():
    # CRC-16/CCITT-FALSE has init=0xFFFF, no input/output reflection, and
    # no final XOR, so an empty input leaves the CRC at its init value.
    assert core.crc16_ccitt_false(b"") == 0xFFFF


def test_crc16_ccitt_false_known_check_value():
    # "123456789" is the standard CRC catalogue check-value input; the
    # expected result is the well-known CRC-16/CCITT-FALSE check value
    # 0x29B1.
    assert core.crc16_ccitt_false(b"123456789") == 0x29B1
