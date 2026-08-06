def interleave(streams: list[bytes]) -> bytes:
    """Combine equal-length byte streams by interleaving one byte from
    each in turn. All streams must already be the same length — padding
    is the caller's responsibility."""
    n = len(streams)
    length = len(streams[0])
    out = bytearray(n * length)
    for j, s in enumerate(streams):
        out[j::n] = s
    return bytes(out)


def deinterleave(data: bytes, n: int) -> list[bytes]:
    """Split interleaved bytes into n equal-length streams. len(data)
    must already be a multiple of n — truncation is the caller's
    responsibility."""
    return [data[j::n] for j in range(n)]
