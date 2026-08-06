# Input File Checksum Display — Design

## Purpose

`romtool` currently prints CRC16/CRC32/SHA-256 for every file it *writes*
(`combine`'s output, each `split` output). It prints nothing for the
files it *reads*. Add a checksum line for every input file too, so users
can record/verify the identity of their source dumps as well as the
results — using CRC16, CRC32, and MD5 for inputs (deliberately a
different third hash than outputs' SHA-256, per user request — e.g. to
match MD5 values reported by other ROM-dump tooling/databases).

## Behavior

- **`combine`**: for each input file, print its checksum line
  immediately after that file is successfully read — before the
  size-mismatch/`--pad-byte` check runs. If reading a later input fails
  (`RomToolError`), the checksum lines for inputs already read still
  appear on stdout; the command then exits 1 as it does today.
- **`split`**: print the single input file's checksum line immediately
  after it's successfully read — before the divisibility/
  `--allow-truncate` check runs.
- Existing output-file checksum behavior (CRC16/CRC32/SHA-256, printed
  after each file is written) is unchanged.

## Format

Same shape as the existing output line, field names distinguish the
hash used:

```
<path>: crc16=<4 lowercase hex> crc32=<8 lowercase hex> md5=<32 lowercase hex>
```

Example, for `romtool combine LOW.bin HIGH.bin -o combined.bin`:

```
LOW.bin: crc16=1234 crc32=abcdef01 md5=25f9e794323b453885f5181f1b624d0b
HIGH.bin: crc16=5678 crc32=23456789 md5=d41d8cd98f00b204e9800998ecf8427e
combined.bin: crc16=29b1 crc32=1a2b3c4d sha256=9f86d0818...
```

## Implementation

`src/romtool/core.py`:

- Generalize `checksums()` to accept which algorithm computes the third
  field, rather than adding a second hardcoded function (avoids
  duplicating the CRC16/CRC32 computation that's identical either way):

  ```python
  def checksums(data: bytes, *, third: str = "sha256") -> tuple[str, str, str]:
      """Returns (crc16_hex, crc32_hex, third_hex) for the given bytes.
      third selects the third algorithm: "sha256" or "md5"."""
      crc16_hex = f"{crc16_ccitt_false(data):04x}"
      crc32_hex = f"{zlib.crc32(data):08x}"
      if third == "sha256":
          third_hex = hashlib.sha256(data).hexdigest()
      elif third == "md5":
          third_hex = hashlib.md5(data).hexdigest()
      else:
          raise ValueError(f"unsupported third algorithm: {third!r}")
      return crc16_hex, crc32_hex, third_hex
  ```

  All existing callers (`_print_checksum_line` for outputs) call
  `checksums(data)` unchanged — the default keeps today's behavior.
  `third` is keyword-only so call sites read clearly
  (`checksums(data, third="md5")`) and existing positional-style calls
  (there are none besides the single-arg form) can't silently break.

`src/romtool/cli.py`:

- Add `_print_input_checksum_line(path: Path, data: bytes) -> None`,
  parallel to the existing `_print_checksum_line`:

  ```python
  def _print_input_checksum_line(path: Path, data: bytes) -> None:
      crc16_hex, crc32_hex, md5_hex = core.checksums(data, third="md5")
      print(f"{path}: crc16={crc16_hex} crc32={crc32_hex} md5={md5_hex}")
  ```

- `cmd_combine`: change the input-reading loop so each file's data is
  checksum-printed right after it's read:

  ```python
  datas = []
  for p in args.inputs:
      data = _read_file(p)
      _print_input_checksum_line(p, data)
      datas.append(data)
  lengths = [len(d) for d in datas]
  ```

  (replaces the current `datas = [_read_file(p) for p in args.inputs]`
  one-liner; the mismatched-size check and everything after it is
  unchanged).

- `cmd_split`: print the input's checksum line right after `_read_file`:

  ```python
  data = _read_file(args.input)
  _print_input_checksum_line(args.input, data)
  remainder = len(data) % n
  ```

  (unchanged from there on).

## Testing

`tests/test_core.py`:

- `checksums(b"123456789", third="md5")` returns `("29b1", "cbf43926",
  "25f9e794323b453885f5181f1b624d0b")` — the MD5 catalogue check value
  for `"123456789"`, verified independently against `hashlib.md5`.
- `checksums(b"", third="md5")[2] == "d41d8cd98f00b204e9800998ecf8427e"`
  (empty-input MD5 check value).
- `checksums(data)` (no `third` argument) is unchanged from today —
  still defaults to SHA-256 (extend/reuse the existing default-behavior
  tests to also assert this didn't regress).
- `checksums(data, third="bogus")` raises `ValueError`.

`tests/test_cli.py`:

- `combine`: given two input files, asserts both inputs' `crc16=...
  crc32=... md5=...` lines appear in stdout, in input order, before the
  output's `crc16=... crc32=... sha256=...` line.
- `combine` size-mismatch case: asserts both (mismatched-size) inputs'
  checksum lines still appear in stdout even though the command then
  raises `RomToolError` and no output file is written.
- `split`: asserts the single input's `crc16=... crc32=... md5=...` line
  appears in stdout before the per-part output lines.
- `split` non-divisible-without-`--allow-truncate` case: asserts the
  input's checksum line still appears even though the command then
  raises `RomToolError`.

## Out of scope

- No CLI flag to opt in/out of input checksums — always printed,
  consistent with how output checksums are always printed.
- No change to output-file checksum behavior or format.
- No change to error handling/exit codes — checksum printing is purely
  additive around the existing read/validate/write flow.
