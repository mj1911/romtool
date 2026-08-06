# romtool — ROM Interleave/De-interleave CLI

**Date:** 2026-08-05
**Status:** Approved

## Purpose

A cross-platform (Linux/Windows/Mac) command-line tool to combine (interleave)
N byte-aligned binary ROM/EEPROM images into a single file, and to split
(de-interleave) a single file back into N byte-aligned images. Covers the
common case of separate High/Low byte ROM images that need to be merged for
programming or analysis, and generalizes to N-way interleaving (e.g. 4 ROMs
on a 32-bit bus) - something perhaps rare but invaluable.

## Interface

One-shot CLI with arguments — no interactive menu. Fully scriptable, standard
process exit codes.

```bash
romtool combine IN0 IN1 [IN2 ...] -o OUTPUT [--pad-byte BYTE]
romtool split INPUT.FILE (-n N | -o OUT0 OUT1 [OUT2 ...]) [--allow-truncate]
```

After successfully writing output file(s), the tool prints one line per
output file to stdout with both a CRC32 and a SHA-256 checksum, e.g.:

```
combined.bin: crc32=3a2f9c11 sha256=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

CRC32 matches the convention used by classic EPROM programmer tools and
no-intro/redump-style ROM checksums; SHA-256 gives a collision-resistant
integrity check. Both come from the standard library (`zlib.crc32`,
`hashlib.sha256`) — no extra dependencies.

### `combine`

- Takes 2 or more input files.
- Byte order follows the command-line argument order: the first input file
  supplies byte 0 of each interleaved group (conventionally "Low"), the
  second supplies byte 1, and so on.
- All input files must be the same length, **unless** `--pad-byte` is given.
  `--pad-byte` accepts a value in hex (`0xFF`) or decimal (`255`); shorter
  files are padded with this byte value up to the length of the longest
  input before interleaving.
- Without `--pad-byte`, a length mismatch is a hard error (exit 1) naming the
  mismatched files and their sizes.

### `split`

- Takes exactly one input file.
- Output count/names determined by either:
  - `-n N`: auto-generates output filenames `<input_stem>.part0.bin` …
    `<input_stem>.part{N-1}.bin` next to the input file.
  - or `-o OUT0 OUT1 ...`: explicit output filenames; N is inferred from the
    count of names given.
- Input file length must be evenly divisible by N, **unless**
  `--allow-truncate` is given, in which case the trailing partial group of
  bytes is dropped. In that case, a warning is printed to stderr, and the 
  operation proceeds with the truncated length.
- Without `--allow-truncate`, a non-divisible length is a hard error (exit 1)
  naming the file size and N.

### Overrides are flags only

No interactive confirmation prompts. All size-mismatch handling is opt-in via
explicit CLI flags (`--pad-byte`, `--allow-truncate`), keeping the tool
predictable and scriptable in pipelines/CI.

## Core logic

Pure functions with no I/O, implemented via slice assignment for clarity and
speed (no manual per-byte loops):

```python
def interleave(streams: list[bytes]) -> bytes:
    """All streams must already be equal length (padding handled by caller)."""
    n = len(streams)
    length = len(streams[0])
    out = bytearray(n * length)
    for j, s in enumerate(streams):
        out[j::n] = s
    return bytes(out)

def deinterleave(data: bytes, n: int) -> list[bytes]:
    """len(data) must already be a multiple of n (truncation handled by caller)."""
    return [data[j::n] for j in range(n)]

def checksums(data: bytes) -> tuple[str, str]:
    """Returns (crc32_hex, sha256_hex) for the given bytes."""
    crc32_hex = f"{zlib.crc32(data):08x}"
    sha256_hex = hashlib.sha256(data).hexdigest()
    return crc32_hex, sha256_hex
```

Padding (for `combine`) and truncation (for `split`) are pre-processing steps
performed by the CLI layer before calling these functions, keeping the core
functions simple, deterministic, and independently testable. `checksums` is
called by the CLI layer once per output file, after it has been written.

## Error handling

- Missing/unreadable input file → clear message naming the file and the
  underlying OS error, exit 1.
- Size mismatch on `combine` without `--pad-byte` → message states each
  input's size and which files disagree, exit 1.
- Non-divisible size on `split` without `--allow-truncate` → message states
  the file size and N, and how many trailing bytes would be dropped, exit 1.
- Invalid `--pad-byte` value, or N < 2 → argparse-level validation error,
  exit 2.

## Testing (pytest)

`tests/test_core.py`:

- Round-trip tests (`interleave` then `deinterleave` recovers the originals)
  for N = 2, 3, 4.
- Edge cases: empty (0-byte) streams, 1-byte streams.
- **Randomized round-trip tests:** using Python's `random` module with fixed
  seeds for reproducibility, generate N files of random (but equal, within a
  test case) length filled with random byte content, run
  `interleave` → `deinterleave`, and assert the result exactly matches the
  original inputs. Parametrized across multiple N values (2, 3, 4, 8) and
  multiple seeds, to catch ordering/off-by-one logic errors that hand-picked
  fixtures might miss.
- `checksums()` correctness against known CRC32/SHA-256 values for small
  fixed inputs (including the empty-bytes case).

`tests/test_cli.py`:

- Invokes `cli.main(argv)` directly (no subprocess) for speed.
- Covers: `combine` happy path, `split` happy path, size-mismatch error
  without override, `--pad-byte` success path, non-divisible split error
  without override, `--allow-truncate` success path with warning printed,
  auto-generated split output filenames, explicit `-o` output filenames,
  checksum lines printed for each output file on success.

## Packaging

```
romtool/
  pyproject.toml
  src/romtool/
    __init__.py
    __main__.py    # enables `python -m romtool`
    cli.py         # argparse setup + subcommand dispatch
    core.py        # interleave/deinterleave/checksums, pure functions
  tests/
    test_core.py
    test_cli.py
  README.md
```

- Installable via `pip install .` or `pipx install .`, providing a `romtool`
  command on Linux, Windows, and Mac.
- Zero-install usage also works: `python -m romtool ...` from the `src`
  directory, since the implementation only uses the Python standard library
  (`argparse`, `pathlib`, `sys`, `zlib`, `hashlib`, `random` in tests).

## Out of scope (YAGNI)

- Interactive/menu-driven mode.
- Word-wise (>1 byte) interleaving granularity — byte-wise only, matching
  the stated EEPROM High/Low use case.
