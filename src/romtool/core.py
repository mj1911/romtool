import hashlib
import zlib


_CRC16_CCITT_FALSE_POLY = 0x1021


def _build_crc16_table(poly: int) -> list[int]:
    table = []
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
        table.append(crc)
    return table


_CRC16_TABLE = _build_crc16_table(_CRC16_CCITT_FALSE_POLY)


def crc16_ccitt_false(data: bytes) -> int:
    """Returns the CRC-16/CCITT-FALSE checksum of data as an int
    (poly=0x1021, init=0xFFFF, no reflection, no final XOR)."""
    crc = 0xFFFF
    for byte in data:
        crc = ((crc << 8) & 0xFFFF) ^ _CRC16_TABLE[((crc >> 8) ^ byte) & 0xFF]
    return crc


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


def checksums(data: bytes, *, third: str = "sha256") -> tuple[str, str, str]:
    """Returns (crc16_hex, crc32_hex, third_hex) for the given bytes.
    third selects the third algorithm: "sha256" or "md5"."""
    crc16_hex = f"{crc16_ccitt_false(data):04x}"
    crc32_hex = f"{zlib.crc32(data):08x}"
    if third == "sha256":
        third_hex = hashlib.sha256(data).hexdigest()
    elif third == "md5":
        third_hex = hashlib.md5(data, usedforsecurity=False).hexdigest()
    else:
        raise ValueError(
            f"unsupported third algorithm: {third!r} "
            "(expected 'sha256' or 'md5')"
        )
    return crc16_hex, crc32_hex, third_hex
