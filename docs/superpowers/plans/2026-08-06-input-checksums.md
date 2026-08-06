# Input File Checksum Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Print a CRC16/CRC32/MD5 checksum line for every input file `romtool` reads (in `combine` and `split`), in addition to the existing CRC16/CRC32/SHA-256 lines already printed for output files.

**Architecture:** `core.checksums()` gains a keyword-only `third` parameter (`"sha256"` default, or `"md5"`) so the same CRC16/CRC32 computation is reused for both input and output checksum lines. `cli.py` gets a new `_print_input_checksum_line` (parallel to the existing `_print_checksum_line`), called from `cmd_combine` and `cmd_split` right after each input file is read, before any validation runs.

**Tech Stack:** Python 3.9+, stdlib only (`hashlib.md5`, already used for `hashlib.sha256`).

## Global Constraints

- Input checksum line format: `<path>: crc16=<4 lowercase hex> crc32=<8 lowercase hex> md5=<32 lowercase hex>`.
- Output checksum line format and content is unchanged: `<path>: crc16=<4 lowercase hex> crc32=<8 lowercase hex> sha256=<64 lowercase hex>`.
- Input checksum lines print immediately after that file is successfully read, before any size/divisibility validation — so they still appear even if the command later raises `RomToolError`.
- No third-party runtime dependencies (stdlib only).
- Python 3.9+ compatible syntax throughout (matches existing codebase).

---

### Task 1: Generalize `core.checksums()` with a selectable third hash

**Files:**
- Modify: `src/romtool/core.py:52-57` (the existing `checksums` function)
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `checksums(data: bytes, *, third: str = "sha256") -> tuple[str, str, str]`, returning `(crc16_hex, crc32_hex, third_hex)`. `third="sha256"` (the default, unchanged behavior) or `third="md5"`; any other value raises `ValueError`. Used by Task 2's `_print_input_checksum_line`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`, right after `test_checksums_format_and_determinism` (currently ending at line 92) and before `test_crc16_ccitt_false_empty`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py -k "md5 or unsupported_third" -v`
Expected: FAIL — `test_checksums_md5_known_check_value`, `test_checksums_md5_empty`, and `test_checksums_unsupported_third_raises` fail with `TypeError: checksums() got an unexpected keyword argument 'third'`. `test_checksums_default_third_is_sha256` also fails the same way.

- [ ] **Step 3: Update `checksums()`**

Replace the existing `checksums` function in `src/romtool/core.py`:

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py -v`
Expected: PASS (all tests in the file, including the pre-existing checksum/CRC16 tests — the default-argument behavior is unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/romtool/core.py tests/test_core.py
git commit -m "Generalize checksums() with a selectable third hash (sha256/md5)"
```

---

### Task 2: Print input file checksums in `combine` and `split`

**Files:**
- Modify: `src/romtool/cli.py:112-114` (add `_print_input_checksum_line` after the existing `_print_checksum_line`)
- Modify: `src/romtool/cli.py:117-119` (`cmd_combine`'s input-reading loop)
- Modify: `src/romtool/cli.py:157` (`cmd_split`'s input read)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `core.checksums(data: bytes, *, third: str = "sha256") -> tuple[str, str, str]` from Task 1.
- Produces: `_print_input_checksum_line(path: Path, data: bytes) -> None`, printing `<path>: crc16=... crc32=... md5=...`. Not consumed elsewhere — this task is the last one in the plan.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli.py`, replace `test_cmd_combine_writes_interleaved_output_and_prints_checksums` (currently lines 104-127) with:

```python
def test_cmd_combine_writes_interleaved_output_and_prints_checksums(
    tmp_path, capsys
):
    low = tmp_path / "low.bin"
    high = tmp_path / "high.bin"
    out = tmp_path / "out.bin"
    low.write_bytes(b"\x01\x02\x03")
    high.write_bytes(b"\xAA\xBB\xCC")

    parser = build_parser()
    args = parser.parse_args(
        ["combine", str(low), str(high), "-o", str(out)]
    )
    exit_code = cmd_combine(args)

    assert exit_code == 0
    assert out.read_bytes() == b"\x01\xAA\x02\xBB\x03\xCC"

    captured = capsys.readouterr()
    low_crc16, low_crc32, low_md5 = core.checksums(
        low.read_bytes(), third="md5"
    )
    high_crc16, high_crc32, high_md5 = core.checksums(
        high.read_bytes(), third="md5"
    )
    crc16_hex, crc32_hex, sha256_hex = core.checksums(out.read_bytes())

    low_line = f"{low}: crc16={low_crc16} crc32={low_crc32} md5={low_md5}"
    high_line = (
        f"{high}: crc16={high_crc16} crc32={high_crc32} md5={high_md5}"
    )
    out_line = (
        f"{out}: crc16={crc16_hex} crc32={crc32_hex} sha256={sha256_hex}"
    )

    assert low_line in captured.out
    assert high_line in captured.out
    assert out_line in captured.out
    # Inputs are checksummed before the output is written.
    assert captured.out.index(low_line) < captured.out.index(out_line)
    assert captured.out.index(high_line) < captured.out.index(out_line)
```

Add a new test right after `test_cmd_combine_size_mismatch_without_pad_byte_raises` (currently ending at line 144):

```python
def test_cmd_combine_size_mismatch_still_prints_input_checksums(
    tmp_path, capsys
):
    low = tmp_path / "low.bin"
    high = tmp_path / "high.bin"
    out = tmp_path / "out.bin"
    low.write_bytes(b"\x01\x02\x03")
    high.write_bytes(b"\xAA\xBB")

    parser = build_parser()
    args = parser.parse_args(
        ["combine", str(low), str(high), "-o", str(out)]
    )

    with pytest.raises(RomToolError):
        cmd_combine(args)
    assert not out.exists()

    captured = capsys.readouterr()
    low_crc16, low_crc32, low_md5 = core.checksums(
        low.read_bytes(), third="md5"
    )
    high_crc16, high_crc32, high_md5 = core.checksums(
        high.read_bytes(), third="md5"
    )
    assert (
        f"{low}: crc16={low_crc16} crc32={low_crc32} md5={low_md5}"
        in captured.out
    )
    assert (
        f"{high}: crc16={high_crc16} crc32={high_crc32} md5={high_md5}"
        in captured.out
    )
```

Replace `test_cmd_split_with_outputs_writes_deinterleaved_files_and_checksums` (currently lines 182-212) with:

```python
def test_cmd_split_with_outputs_writes_deinterleaved_files_and_checksums(
    tmp_path, capsys
):
    combined = tmp_path / "combined.bin"
    combined.write_bytes(b"\x01\xAA\x02\xBB\x03\xCC")
    low_out = tmp_path / "low.bin"
    high_out = tmp_path / "high.bin"

    parser = build_parser()
    args = parser.parse_args(
        ["split", str(combined), "-o", str(low_out), str(high_out)]
    )
    exit_code = cmd_split(args)

    assert exit_code == 0
    assert low_out.read_bytes() == b"\x01\x02\x03"
    assert high_out.read_bytes() == b"\xAA\xBB\xCC"

    captured = capsys.readouterr()
    in_crc16, in_crc32, in_md5 = core.checksums(
        combined.read_bytes(), third="md5"
    )
    low_crc16, low_crc32, low_sha256 = core.checksums(low_out.read_bytes())
    high_crc16, high_crc32, high_sha256 = core.checksums(
        high_out.read_bytes()
    )
    input_line = (
        f"{combined}: crc16={in_crc16} crc32={in_crc32} md5={in_md5}"
    )
    low_line = (
        f"{low_out}: crc16={low_crc16} crc32={low_crc32} "
        f"sha256={low_sha256}"
    )
    high_line = (
        f"{high_out}: crc16={high_crc16} crc32={high_crc32} "
        f"sha256={high_sha256}"
    )
    assert input_line in captured.out
    assert low_line in captured.out
    assert high_line in captured.out
    # The input is checksummed before either output.
    assert captured.out.index(input_line) < captured.out.index(low_line)
    assert captured.out.index(input_line) < captured.out.index(high_line)
```

Add a new test right after `test_cmd_split_non_divisible_without_allow_truncate_raises` (currently ending at line 269):

```python
def test_cmd_split_non_divisible_still_prints_input_checksum(
    tmp_path, capsys
):
    combined = tmp_path / "combined.bin"
    combined.write_bytes(b"\x01\xAA\x02")  # length 3, not divisible by 2

    parser = build_parser()
    args = parser.parse_args(["split", str(combined), "-n", "2"])

    with pytest.raises(RomToolError):
        cmd_split(args)

    captured = capsys.readouterr()
    crc16_hex, crc32_hex, md5_hex = core.checksums(
        combined.read_bytes(), third="md5"
    )
    assert (
        f"{combined}: crc16={crc16_hex} crc32={crc32_hex} md5={md5_hex}"
        in captured.out
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — the two replaced tests fail because no input checksum lines are printed yet (assertions on `low_line`/`high_line`/`input_line` fail); the two new tests fail the same way (`capsys` output doesn't contain the expected input checksum line, since nothing is printed before the `RomToolError` is raised).

- [ ] **Step 3: Add `_print_input_checksum_line` and wire it in**

In `src/romtool/cli.py`, add this function right after the existing `_print_checksum_line` (currently lines 112-114):

```python
def _print_input_checksum_line(path: Path, data: bytes) -> None:
    crc16_hex, crc32_hex, md5_hex = core.checksums(data, third="md5")
    print(f"{path}: crc16={crc16_hex} crc32={crc32_hex} md5={md5_hex}")
```

In `cmd_combine`, replace the current input-reading line:

```python
    datas = [_read_file(p) for p in args.inputs]
    lengths = [len(d) for d in datas]
```

with:

```python
    datas = []
    for p in args.inputs:
        data = _read_file(p)
        _print_input_checksum_line(p, data)
        datas.append(data)
    lengths = [len(d) for d in datas]
```

In `cmd_split`, replace the current input-reading line:

```python
    data = _read_file(args.input)
    remainder = len(data) % n
```

with:

```python
    data = _read_file(args.input)
    _print_input_checksum_line(args.input, data)
    remainder = len(data) % n
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS (all tests in `tests/test_core.py` and `tests/test_cli.py`)

- [ ] **Step 6: Commit**

```bash
git add src/romtool/cli.py tests/test_cli.py
git commit -m "Print CRC16/CRC32/MD5 checksums for input files"
```

---

## Final Verification

- [ ] Run `python -m pytest -v` from the repo root — all tests pass.
- [ ] Run `PYTHONPATH=src python3 -m romtool combine <two equal-length files> -o /tmp/out.bin` and confirm two `crc16=... crc32=... md5=...` input lines print before the `crc16=... crc32=... sha256=...` output line.
- [ ] Run `PYTHONPATH=src python3 -m romtool split /tmp/out.bin -n 2` and confirm one `crc16=... crc32=... md5=...` input line prints before the two `crc16=... crc32=... sha256=...` output lines.
