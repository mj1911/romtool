# CRC16 Checksum Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Print a CRC-16/CCITT-FALSE checksum alongside the existing CRC32 and SHA-256 on every file `romtool` writes.

**Architecture:** `core.py` gains a table-driven `crc16_ccitt_false(data: bytes) -> int` function and `checksums()` grows from a 2-tuple to a 3-tuple `(crc16_hex, crc32_hex, sha256_hex)`. `cli.py`'s single print call site (`_print_checksum_line`) is updated to unpack and print the new field. No other behavior changes.

**Tech Stack:** Python 3.9+, stdlib only (`zlib`, `hashlib`) — CRC16 is hand-implemented since it's not in `zlib`.

## Global Constraints

- CRC16 variant: CRC-16/CCITT-FALSE — polynomial `0x1021`, initial value `0xFFFF`, no input reflection, no output reflection, no final XOR.
- No third-party runtime dependencies (per README).
- Output format: 4 lowercase hex digits for CRC16, printed as `crc16=<4 lowercase hex digits>`, ordered before `crc32=` and `sha256=` on the same line.
- Python 3.9+ compatible syntax throughout (matches existing codebase).

---

### Task 1: Add `crc16_ccitt_false` to `core.py`

**Files:**
- Modify: `src/romtool/core.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `crc16_ccitt_false(data: bytes) -> int`, used by Task 2's `checksums()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
def test_crc16_ccitt_false_empty():
    # CRC-16/CCITT-FALSE has init=0xFFFF, no input/output reflection, and
    # no final XOR, so an empty input leaves the CRC at its init value.
    assert core.crc16_ccitt_false(b"") == 0xFFFF


def test_crc16_ccitt_false_known_check_value():
    # "123456789" is the standard CRC catalogue check-value input; the
    # expected result is the well-known CRC-16/CCITT-FALSE check value
    # 0x29B1.
    assert core.crc16_ccitt_false(b"123456789") == 0x29B1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py -k crc16_ccitt_false -v`
Expected: FAIL with `AttributeError: module 'romtool.core' has no attribute 'crc16_ccitt_false'`

- [ ] **Step 3: Implement `crc16_ccitt_false`**

Add to `src/romtool/core.py` (near the top, after the imports):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py -k crc16_ccitt_false -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/romtool/core.py tests/test_core.py
git commit -m "Add CRC-16/CCITT-FALSE checksum function to core"
```

---

### Task 2: Extend `checksums()` to a 3-tuple including CRC16

**Files:**
- Modify: `src/romtool/core.py:24-28` (the existing `checksums` function)
- Test: `tests/test_core.py:55-77` (existing checksum tests)

**Interfaces:**
- Consumes: `crc16_ccitt_false(data: bytes) -> int` from Task 1.
- Produces: `checksums(data: bytes) -> tuple[str, str, str]` returning `(crc16_hex, crc32_hex, sha256_hex)`, used by Task 3's `_print_checksum_line`.

- [ ] **Step 1: Update the failing tests**

In `tests/test_core.py`, replace the three existing `checksums`-related tests with:

```python
def test_checksums_empty():
    crc16_hex, crc32_hex, sha256_hex = core.checksums(b"")
    assert crc16_hex == "ffff"
    assert crc32_hex == "00000000"
    assert sha256_hex == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_checksums_crc32_known_check_value():
    # "123456789" is the standard CRC-32/ISO-HDLC (zlib) check value input;
    # the expected CRC32 is the well-known catalogue check value 0xCBF43926.
    _, crc32_hex, _ = core.checksums(b"123456789")
    assert crc32_hex == "cbf43926"


def test_checksums_crc16_known_check_value():
    # Same "123456789" catalogue input; expected CRC-16/CCITT-FALSE is
    # the well-known check value 0x29B1.
    crc16_hex, _, _ = core.checksums(b"123456789")
    assert crc16_hex == "29b1"


def test_checksums_format_and_determinism():
    data = bytes(range(256))
    crc16_hex, crc32_hex, sha256_hex = core.checksums(data)
    assert len(crc16_hex) == 4
    assert len(crc32_hex) == 8
    assert len(sha256_hex) == 64
    assert crc16_hex == crc16_hex.lower()
    assert crc32_hex == crc32_hex.lower()
    assert sha256_hex == sha256_hex.lower()
    assert core.checksums(data) == (crc16_hex, crc32_hex, sha256_hex)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py -k checksums -v`
Expected: FAIL — `checksums` still returns a 2-tuple, so the 3-way unpacking raises `ValueError: not enough values to unpack`.

- [ ] **Step 3: Update `checksums()`**

Replace the existing `checksums` function in `src/romtool/core.py`:

```python
def checksums(data: bytes) -> tuple[str, str, str]:
    """Returns (crc16_hex, crc32_hex, sha256_hex) for the given bytes."""
    crc16_hex = f"{crc16_ccitt_false(data):04x}"
    crc32_hex = f"{zlib.crc32(data):08x}"
    sha256_hex = hashlib.sha256(data).hexdigest()
    return crc16_hex, crc32_hex, sha256_hex
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py -v`
Expected: PASS (all tests in the file, including Task 1's and the updated checksum tests)

- [ ] **Step 5: Commit**

```bash
git add src/romtool/core.py tests/test_core.py
git commit -m "Extend checksums() to include CRC16"
```

---

### Task 3: Print CRC16 in the CLI output and update CLI tests

**Files:**
- Modify: `src/romtool/cli.py:115-117` (`_print_checksum_line`)
- Test: `tests/test_cli.py:104-125,179-222` (three tests that call `core.checksums` and assert on printed output)

**Interfaces:**
- Consumes: `checksums(data: bytes) -> tuple[str, str, str]` from Task 2 (returns `(crc16_hex, crc32_hex, sha256_hex)`).

- [ ] **Step 1: Update the failing tests**

In `tests/test_cli.py`, update `test_cmd_combine_writes_interleaved_output_and_prints_checksums` (currently lines 104-124):

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
    crc16_hex, crc32_hex, sha256_hex = core.checksums(out.read_bytes())
    assert (
        f"{out}: crc16={crc16_hex} crc32={crc32_hex} sha256={sha256_hex}"
        in captured.out
    )
```

Update `test_cmd_split_with_outputs_writes_deinterleaved_files_and_checksums` (currently lines 179-201):

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
    low_crc16, low_crc32, low_sha256 = core.checksums(low_out.read_bytes())
    high_crc16, high_crc32, high_sha256 = core.checksums(
        high_out.read_bytes()
    )
    assert (
        f"{low_out}: crc16={low_crc16} crc32={low_crc32} sha256={low_sha256}"
        in captured.out
    )
    assert (
        f"{high_out}: crc16={high_crc16} crc32={high_crc32} "
        f"sha256={high_sha256}" in captured.out
    )
```

Update `test_cmd_split_with_n_auto_names_outputs` (currently lines 204-222):

```python
def test_cmd_split_with_n_auto_names_outputs(tmp_path, capsys):
    combined = tmp_path / "combined.bin"
    combined.write_bytes(b"\x01\xAA\x02\xBB\x03\xCC")

    parser = build_parser()
    args = parser.parse_args(["split", str(combined), "-n", "2"])
    exit_code = cmd_split(args)

    assert exit_code == 0
    part0 = tmp_path / "combined.part0.bin"
    part1 = tmp_path / "combined.part1.bin"
    assert part0.read_bytes() == b"\x01\x02\x03"
    assert part1.read_bytes() == b"\xAA\xBB\xCC"

    captured = capsys.readouterr()
    part0_crc16, part0_crc32, part0_sha256 = core.checksums(
        part0.read_bytes()
    )
    part1_crc16, part1_crc32, part1_sha256 = core.checksums(
        part1.read_bytes()
    )
    assert (
        f"{part0}: crc16={part0_crc16} crc32={part0_crc32} "
        f"sha256={part0_sha256}" in captured.out
    )
    assert (
        f"{part1}: crc16={part1_crc16} crc32={part1_crc32} "
        f"sha256={part1_sha256}" in captured.out
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL on the three updated tests — `_print_checksum_line` still prints only `crc32=...sha256=...`, and/or the 3-way unpack of `core.checksums(...)` now works (Task 2 already updated it) but the printed line doesn't yet contain `crc16=`.

- [ ] **Step 3: Update `_print_checksum_line`**

Replace in `src/romtool/cli.py`:

```python
def _print_checksum_line(path: Path, data: bytes) -> None:
    crc16_hex, crc32_hex, sha256_hex = core.checksums(data)
    print(f"{path}: crc16={crc16_hex} crc32={crc32_hex} sha256={sha256_hex}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS (all tests in `tests/test_core.py` and `tests/test_cli.py`)

- [ ] **Step 6: Commit**

```bash
git add src/romtool/cli.py tests/test_cli.py
git commit -m "Print CRC16 alongside CRC32/SHA-256 in CLI output"
```

---

### Task 4: Update README documentation

**Files:**
- Modify: `README.md:31,99,102`

**Interfaces:** None (documentation only).

- [ ] **Step 1: Update the checksum bullet point**

In `README.md`, find the line (around line 31):

```
- Every output file gets its CRC32 and SHA-256 checksum printed after
```

Replace with:

```
- Every output file gets its CRC16, CRC32, and SHA-256 checksums printed
```

(keep the following line of that bullet — "it's written, so you can verify results..." — unchanged, just re-flow the wrapping if needed so the bullet still reads naturally as one point).

- [ ] **Step 2: Update the "Command Options" section checksum line and example**

Find (around line 99-102):

```
Each successfully written output file has its CRC32 and SHA-256 checksum
reported, e.g.:

    combined.bin: crc32=1a2b3c4d sha256=9f86d0818...
```

Replace with:

```
Each successfully written output file has its CRC16, CRC32, and SHA-256
checksums reported, e.g.:

    combined.bin: crc16=29b1 crc32=1a2b3c4d sha256=9f86d0818...
```

- [ ] **Step 3: Verify no other stale references remain**

Run: `grep -n "crc32\|checksum" README.md`
Expected: Every checksum-related line mentions CRC16 alongside CRC32/SHA-256; no line shows the old two-field-only format.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Document CRC16 in checksum output"
```

---

## Final Verification

- [ ] Run `python -m pytest -v` from the repo root — all tests pass.
- [ ] Run `PYTHONPATH=src python3 -m romtool combine <any two equal-length files> -o /tmp/out.bin` and confirm the printed line has the form `crc16=<4 hex> crc32=<8 hex> sha256=<64 hex>`.
