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
