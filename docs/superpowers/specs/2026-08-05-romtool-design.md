# romtool — ROM Interleave/De-interleave CLI

**Date:** 2026-08-05
**Status:** Approved

## Purpose

A cross-platform (Linux/Windows/Mac) command-line tool to combine (interleave)
N byte-aligned binary ROM/EEPROM images into a single file, and to split
(de-interleave) a single file back into N byte-aligned images. Covers the
common case of separate High/Low byte ROM images that need to be merged for
programming or analysis, and generalizes to N-way interleaving (e.g. 4 ROMs
on a 32-bit bus).

## Interface

One-shot CLI with arguments — no interactive menu. Fully scriptable, standard
process exit codes.

```
romtool combine IN0 IN1 [IN2 ...] -o OUTPUT [--pad-byte BYTE]
romtool split INPUT (-n N | -o OUT0 OUT1 [OUT2 ...]) [--allow-truncate]
```

### `combine`

- Takes 2 or more input files.
- Byte order follows command-line argument order: the first input file
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
  - `-o OUT0 OUT1 ...`: explicit output filenames; N is inferred from the
    count of names given.
- Input file length must be evenly divisible by N, **unless**
  `--allow-truncate` is given, in which case the trailing partial group of
  bytes is dropped, a warning is printed to stderr, and the operation
  proceeds with the truncated length.
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
```

Padding (for `combine`) and truncation (for `split`) are pre-processing steps
performed by the CLI layer before calling these functions, keeping the core
functions simple, deterministic, and independently testable.

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

`tests/test_cli.py`:

- Invokes `cli.main(argv)` directly (no subprocess) for speed.
- Covers: `combine` happy path, `split` happy path, size-mismatch error
  without override, `--pad-byte` success path, non-divisible split error
  without override, `--allow-truncate` success path with warning printed,
  auto-generated split output filenames, explicit `-o` output filenames.

## Packaging

```
romtool/
  pyproject.toml
  src/romtool/
    __init__.py
    __main__.py    # enables `python -m romtool`
    cli.py         # argparse setup + subcommand dispatch
    core.py        # interleave/deinterleave, pure functions
  tests/
    test_core.py
    test_cli.py
  README.md
```

- Installable via `pip install .` or `pipx install .`, providing a `romtool`
  command on Linux, Windows, and Mac.
- Zero-install usage also works: `python -m romtool ...` from the `src`
  directory, since the implementation only uses the Python standard library
  (`argparse`, `pathlib`, `sys`, `random` in tests).

## Out of scope (YAGNI)

- Interactive/menu-driven mode.
- Word-wise (>1 byte) interleaving granularity — byte-wise only, matching
  the stated EEPROM High/Low use case.
- Built-in checksum/verify command — round-trip correctness is covered by
  the test suite; users can diff/checksum files themselves if desired.
