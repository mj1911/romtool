import hashlib
import zlib
from pathlib import Path


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
    each in turn.  All streams must already be the same length — padding
    is the caller's responsibility."""
    n = len(streams)
    length = len(streams[0])
    out = bytearray(n * length)
    for j, s in enumerate(streams):
        out[j::n] = s
    return bytes(out)


def deinterleave(data: bytes, n: int) -> list[bytes]:
    """Split interleaved bytes into n equal-length streams.  len(data)
    must already be a multiple of n — truncation is the caller's
    responsibility."""
    return [data[j::n] for j in range(n)]


def checksums(data: bytes) -> tuple[str, str, str, str]:
    """Returns (sum_hex, crc16_hex, crc32_hex, md5_hex) for the given
    bytes, all upper-case.  sum_hex is the plain sum of byte
    values, zero-padded to at least 4 digits."""
    sum_hex = f"{sum(data):04X}"
    crc16_hex = f"{crc16_ccitt_false(data):04X}"
    crc32_hex = f"{zlib.crc32(data):08X}"
    md5_hex = hashlib.md5(data, usedforsecurity=False).hexdigest().upper()
    return sum_hex, crc16_hex, crc32_hex, md5_hex


def group_duplicates(
    hashes: dict[Path, str]
) -> tuple[dict[str, list[Path]], list[Path]]:
    """Groups paths by hash. hashes maps path -> hash string, in
    processing order (dict insertion order = first-processed file
    first). Returns (duplicate_groups, unique_paths):
      - duplicate_groups: {hash: [paths...]} for every hash shared by
        2+ paths, values in first-seen order, dict keys in
        first-seen-hash order.
      - unique_paths: paths whose hash occurs exactly once, in
        first-seen order.
    """
    by_hash: dict[str, list[Path]] = {}
    for path, digest in hashes.items():
        by_hash.setdefault(digest, []).append(path)

    duplicate_groups = {
        digest: paths for digest, paths in by_hash.items() if len(paths) > 1
    }
    unique_paths = [
        paths[0] for paths in by_hash.values() if len(paths) == 1
    ]
    return duplicate_groups, unique_paths
