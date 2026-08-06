# CRC16 Checksum Display — Design

## Purpose

`romtool` currently prints CRC32 and SHA-256 for every file it writes
(`combine` output, each `split` output). Add a CRC16 checksum to that
same line, since CRC16 is a common integrity check in ROM/EPROM tooling
and some downstream tools/programmers expect it.

## Variant

**CRC-16/CCITT-FALSE**: polynomial `0x1021`, initial value `0xFFFF`, no
input reflection, no output reflection, no final XOR. This is the
variant most commonly produced by firmware and EPROM-programmer
checksum utilities. Standard catalogue check value: CRC16 of ASCII
`"123456789"` is `0x29B1`.

Not available in Python's standard library (`zlib` only provides
CRC32), so it must be implemented directly. No third-party runtime
dependency is added, consistent with the existing "no third-party
runtime dependencies" requirement in the README.

## Implementation

`src/romtool/core.py`:

- Add a module-level 256-entry lookup table, built once at import time
  from the CRC-16/CCITT-FALSE polynomial (`0x1021`).
- Add `crc16_ccitt_false(data: bytes) -> int`, a table-driven CRC16
  implementation: initialize the running CRC to `0xFFFF`, then for each
  byte, XOR it into the high byte of the CRC, look up the table entry,
  and shift/XOR per the standard table-driven CRC algorithm. Returns
  the final 16-bit integer.
- Change `checksums(data: bytes) -> tuple[str, str, str]` to return
  `(crc16_hex, crc32_hex, sha256_hex)` — three lowercase hex strings,
  ordered from shortest/weakest check to strongest, matching the
  existing crc32-before-sha256 ordering. `crc16_hex` is always 4 lowercase
  hex digits (e.g. `f"{crc16_ccitt_false(data):04x}"`).

`src/romtool/cli.py`:

- `_print_checksum_line` unpacks the new 3-tuple and prints:
  `f"{path}: crc16={crc16_hex} crc32={crc32_hex} sha256={sha256_hex}"`
- No other call site changes; `cmd_combine` and `cmd_split` already
  just call `_print_checksum_line`.

## Output format

```
combined.bin: crc16=29b1 crc32=cbf43926 sha256=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

## Testing

`tests/test_core.py`:

- `crc16_ccitt_false(b"") == 0xFFFF` (init value carries through
  unchanged on empty input, since there's no input/output reflection
  or final XOR).
- `crc16_ccitt_false(b"123456789") == 0x29B1` (standard CRC catalogue
  check value for CRC-16/CCITT-FALSE).
- `checksums(data)` returns a 3-tuple; `crc16_hex` is 4 lowercase hex
  chars; `checksums` is deterministic (same input -> same output),
  extending the existing crc32/sha256 assertions to also cover crc16.

`tests/test_cli.py`:

- All existing assertions of the form
  `crc32_hex, sha256_hex = core.checksums(...)` change to
  `crc16_hex, crc32_hex, sha256_hex = core.checksums(...)`, and the
  corresponding `assert f"...crc32=... sha256=..." in captured.out`
  lines change to include `crc16=...` in the expected string, for the
  `combine` output and both `split` output test cases.

## Out of scope

- No new CLI flag to opt in/out of CRC16 — it's always printed,
  consistent with how CRC32 and SHA-256 are always printed today.
- No change to file-writing behavior, error handling, or any other
  existing command semantics.
