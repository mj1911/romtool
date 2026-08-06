# romtool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `romtool`, a cross-platform Python CLI that interleaves (combines) N byte-aligned binary files into one, and de-interleaves (splits) one file into N, with CRC32+SHA-256 checksums printed for every output file.

**Architecture:** A `core.py` module holds pure, I/O-free functions (`interleave`, `deinterleave`, `checksums`) implemented via bytes slice assignment. A `cli.py` module holds argparse wiring, file I/O, padding/truncation pre-processing, and error handling, calling into `core.py` for the actual byte manipulation. `__main__.py` is a thin entry point. This mirrors the spec at `docs/superpowers/specs/2026-08-05-romtool-design.md`.

**Tech Stack:** Python >=3.9, standard library only at runtime (`argparse`, `pathlib`, `sys`, `zlib`, `hashlib`), `pytest` as a test-only dependency, `setuptools` packaging via `pyproject.toml`.

## Global Constraints

- CLI with arguments only — no interactive menu, no confirmation prompts. (spec: Interface)
- Byte-wise interleaving only. (spec: Purpose, Out of scope)
- Runtime code uses only the Python standard library; no third-party runtime dependencies. (spec: Packaging)
- Python `>=3.9`. (spec: Packaging)
- Exit code 0 = success; exit code 1 = user/runtime error (missing file, size mismatch without override flag); exit code 2 = argparse-level validation error (bad `--pad-byte` value, N < 2). (spec: Error handling)
- After successfully writing each output file, print one line to stdout: `<filename>: crc32=<8 lowercase hex digits> sha256=<64 lowercase hex digits>`. (spec: Interface, Core logic)
- Size-mismatch overrides are CLI flags only (`--pad-byte`, `--allow-truncate`) — never interactive prompts. (spec: Overrides are flags only)
- `combine` byte order follows command-line input order (first file = byte 0 of each group). (spec: `combine`)

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/romtool/__init__.py`
- Create: `README.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: an installable, importable `romtool` package (`src/romtool/__init__.py` defines `__version__ = "0.1.0"`) that later tasks add modules to.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "romtool"
version = "0.1.0"
description = "Interleave and de-interleave binary ROM/EEPROM images"
readme = "README.md"
requires-python = ">=3.9"

[project.scripts]
romtool = "romtool.cli:main"

[project.optional-dependencies]
test = ["pytest>=7.0"]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create `src/romtool/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `README.md`**

```markdown
# romtool

Interleave (combine) and de-interleave (split) binary ROM/EEPROM images,
byte-wise, across any number of files. Commonly used for merging/splitting
separate High/Low byte ROM dumps.

## Install

    pip install -e ".[test]"

## Usage

    romtool combine LOW.bin HIGH.bin -o combined.bin
    romtool combine LOW.bin HIGH.bin -o combined.bin --pad-byte 0xFF

    romtool split combined.bin -n 2
    romtool split combined.bin -o low.bin high.bin
    romtool split combined.bin -n 2 --allow-truncate

Each successfully written output file gets a line printed with its CRC32
and SHA-256 checksums.

## Test

    pytest
```

- [ ] **Step 4: Verify the package installs and imports**

Run: `cd /media/sda1/git/rom && pip install -e ".[test]"`
Expected: install succeeds with no errors.

Run: `python -c "import romtool; print(romtool.__version__)"`
Expected: prints `0.1.0`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/romtool/__init__.py README.md
git commit -m "Scaffold romtool package"
```

---

## Task 2: Core — interleave/deinterleave

**Files:**
- Create: `src/romtool/core.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: nothing beyond the standard library.
- Produces: `core.interleave(streams: list[bytes]) -> bytes` and
  `core.deinterleave(data: bytes, n: int) -> list[bytes]`, used by Task 5
  (`cmd_combine`) and Task 6 (`cmd_split`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_core.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core.py -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError` — `core.py` doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `src/romtool/core.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add src/romtool/core.py tests/test_core.py
git commit -m "Add interleave/deinterleave core functions"
```

---

## Task 3: Core — checksums

**Files:**
- Modify: `src/romtool/core.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `core.checksums(data: bytes) -> tuple[str, str]` returning
  `(crc32_hex, sha256_hex)`, used by Task 5 and Task 6 to print checksum
  lines after writing each output file.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_core.py`:

```python
def test_checksums_empty():
    crc32_hex, sha256_hex = core.checksums(b"")
    assert crc32_hex == "00000000"
    assert sha256_hex == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_checksums_crc32_known_check_value():
    # "123456789" is the standard CRC-32/ISO-HDLC (zlib) check value input;
    # the expected CRC32 is the well-known catalogue check value 0xCBF43926.
    crc32_hex, _ = core.checksums(b"123456789")
    assert crc32_hex == "cbf43926"


def test_checksums_format_and_determinism():
    data = bytes(range(256))
    crc32_hex, sha256_hex = core.checksums(data)
    assert len(crc32_hex) == 8
    assert len(sha256_hex) == 64
    assert crc32_hex == crc32_hex.lower()
    assert sha256_hex == sha256_hex.lower()
    assert core.checksums(data) == (crc32_hex, sha256_hex)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core.py -v`
Expected: FAIL with `AttributeError: module 'romtool.core' has no attribute 'checksums'`

- [ ] **Step 3: Write minimal implementation**

Add to the top of `src/romtool/core.py`:

```python
import hashlib
import zlib
```

Append to `src/romtool/core.py`:

```python
def checksums(data: bytes) -> tuple[str, str]:
    """Returns (crc32_hex, sha256_hex) for the given bytes."""
    crc32_hex = f"{zlib.crc32(data):08x}"
    sha256_hex = hashlib.sha256(data).hexdigest()
    return crc32_hex, sha256_hex
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add src/romtool/core.py tests/test_core.py
git commit -m "Add checksums function to core"
```

---

## Task 4: CLI — argument parser

**Files:**
- Create: `src/romtool/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: nothing from `core.py` yet.
- Produces: `cli.parse_pad_byte(value: str) -> int` and
  `cli.build_parser() -> argparse.ArgumentParser`, whose parsed
  `argparse.Namespace` objects are consumed by Task 5's `cmd_combine` and
  Task 6's `cmd_split`. Parsed namespace attributes:
  - `combine`: `args.inputs: list[Path]`, `args.output: Path`,
    `args.pad_byte: int | None`
  - `split`: `args.input: Path`, `args.n: int | None`,
    `args.outputs: list[Path] | None`, `args.allow_truncate: bool`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
import pytest

from romtool.cli import build_parser


def test_parser_combine_basic():
    parser = build_parser()
    args = parser.parse_args(["combine", "a.bin", "b.bin", "-o", "out.bin"])
    assert args.command == "combine"
    assert [str(p) for p in args.inputs] == ["a.bin", "b.bin"]
    assert str(args.output) == "out.bin"
    assert args.pad_byte is None


def test_parser_combine_pad_byte_hex():
    parser = build_parser()
    args = parser.parse_args(
        ["combine", "a.bin", "b.bin", "-o", "out.bin", "--pad-byte", "0xFF"]
    )
    assert args.pad_byte == 255


def test_parser_combine_pad_byte_decimal():
    parser = build_parser()
    args = parser.parse_args(
        ["combine", "a.bin", "b.bin", "-o", "out.bin", "--pad-byte", "255"]
    )
    assert args.pad_byte == 255


def test_parser_combine_pad_byte_out_of_range_rejected(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(
            ["combine", "a.bin", "b.bin", "-o", "out.bin", "--pad-byte", "256"]
        )
    assert exc_info.value.code == 2


def test_parser_combine_single_input_rejected(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["combine", "a.bin", "-o", "out.bin"])
    assert exc_info.value.code == 2


def test_parser_split_with_n():
    parser = build_parser()
    args = parser.parse_args(["split", "combined.bin", "-n", "2"])
    assert args.command == "split"
    assert str(args.input) == "combined.bin"
    assert args.n == 2
    assert args.outputs is None
    assert args.allow_truncate is False


def test_parser_split_with_outputs():
    parser = build_parser()
    args = parser.parse_args(
        ["split", "combined.bin", "-o", "low.bin", "high.bin"]
    )
    assert args.n is None
    assert [str(p) for p in args.outputs] == ["low.bin", "high.bin"]


def test_parser_split_n_and_outputs_mutually_exclusive(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(
            ["split", "combined.bin", "-n", "2", "-o", "low.bin", "high.bin"]
        )
    assert exc_info.value.code == 2


def test_parser_split_requires_n_or_outputs(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["split", "combined.bin"])
    assert exc_info.value.code == 2


def test_parser_split_n_below_minimum_rejected(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["split", "combined.bin", "-n", "1"])
    assert exc_info.value.code == 2


def test_parser_split_outputs_below_minimum_rejected(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["split", "combined.bin", "-o", "only_one.bin"])
    assert exc_info.value.code == 2


def test_parser_missing_subcommand(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'romtool.cli'`

- [ ] **Step 3: Write minimal implementation**

Create `src/romtool/cli.py`:

```python
import argparse
from pathlib import Path


def parse_pad_byte(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid --pad-byte value: {value!r} (expected e.g. 0xFF or 255)"
        )
    if not 0 <= parsed <= 255:
        raise argparse.ArgumentTypeError(
            f"--pad-byte must be between 0 and 255, got {parsed}"
        )
    return parsed


def parse_split_n(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"-n must be an integer, got {value!r}"
        )
    if parsed < 2:
        raise argparse.ArgumentTypeError(
            f"-n must be at least 2, got {parsed}"
        )
    return parsed


class _MinLengthAction(argparse.Action):
    """argparse Action enforcing a minimum number of values for an
    nargs='+' argument (positional or optional), so violations exit with
    argparse's own status code 2 instead of a runtime error."""

    def __init__(self, *args, min_length: int = 2, **kwargs):
        self.min_length = min_length
        super().__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) < self.min_length:
            label = option_string or self.dest
            parser.error(
                f"{label} requires at least {self.min_length} values, "
                f"got {len(values)}"
            )
        setattr(namespace, self.dest, values)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="romtool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    combine_parser = subparsers.add_parser(
        "combine", help="Interleave N input files into one output file"
    )
    combine_parser.add_argument(
        "inputs", nargs="+", type=Path, action=_MinLengthAction
    )
    combine_parser.add_argument("-o", "--output", required=True, type=Path)
    combine_parser.add_argument(
        "--pad-byte", type=parse_pad_byte, default=None
    )

    split_parser = subparsers.add_parser(
        "split", help="De-interleave one input file into N output files"
    )
    split_parser.add_argument("input", type=Path)
    split_group = split_parser.add_mutually_exclusive_group(required=True)
    split_group.add_argument("-n", type=parse_split_n, default=None)
    split_group.add_argument(
        "-o",
        "--outputs",
        nargs="+",
        type=Path,
        default=None,
        dest="outputs",
        action=_MinLengthAction,
    )
    split_parser.add_argument(
        "--allow-truncate", action="store_true", default=False
    )

    return parser
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add src/romtool/cli.py tests/test_cli.py
git commit -m "Add romtool CLI argument parser"
```

---

## Task 5: CLI — combine command

**Files:**
- Modify: `src/romtool/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `core.interleave(streams: list[bytes]) -> bytes`,
  `core.checksums(data: bytes) -> tuple[str, str]` (Task 2, 3);
  `build_parser()` (Task 4).
- Produces: `cli.RomToolError` (exception, message via `str(e)`),
  `cli.cmd_combine(args: argparse.Namespace) -> int`, used by Task 7's
  `main()`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
from romtool import core
from romtool.cli import RomToolError, cmd_combine


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
    crc32_hex, sha256_hex = core.checksums(out.read_bytes())
    assert f"{out}: crc32={crc32_hex} sha256={sha256_hex}" in captured.out


def test_cmd_combine_size_mismatch_without_pad_byte_raises(tmp_path):
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


def test_cmd_combine_pads_shorter_inputs(tmp_path):
    low = tmp_path / "low.bin"
    high = tmp_path / "high.bin"
    out = tmp_path / "out.bin"
    low.write_bytes(b"\x01\x02\x03")
    high.write_bytes(b"\xAA\xBB")

    parser = build_parser()
    args = parser.parse_args(
        [
            "combine", str(low), str(high), "-o", str(out),
            "--pad-byte", "0xFF",
        ]
    )
    exit_code = cmd_combine(args)

    assert exit_code == 0
    assert out.read_bytes() == b"\x01\xAA\x02\xBB\x03\xFF"


def test_cmd_combine_missing_input_file_raises(tmp_path):
    missing = tmp_path / "missing.bin"
    high = tmp_path / "high.bin"
    high.write_bytes(b"\xAA")
    out = tmp_path / "out.bin"

    parser = build_parser()
    args = parser.parse_args(
        ["combine", str(missing), str(high), "-o", str(out)]
    )

    with pytest.raises(RomToolError):
        cmd_combine(args)
```

Add the missing import at the top of `tests/test_cli.py`:

```python
from romtool.cli import build_parser
```

(This import already exists from Task 4 — just confirm it's present; don't duplicate it.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'RomToolError'` (or `'cmd_combine'`)

- [ ] **Step 3: Write minimal implementation**

Add to the top of `src/romtool/cli.py`:

```python
from romtool import core
```

Append to `src/romtool/cli.py`:

```python
class RomToolError(Exception):
    """Raised for user-facing errors (bad input, size mismatches)."""


def _read_file(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as e:
        raise RomToolError(f"cannot read {path}: {e.strerror}")


def _write_output(path: Path, data: bytes) -> None:
    try:
        path.write_bytes(data)
    except OSError as e:
        raise RomToolError(f"cannot write {path}: {e.strerror}")


def _print_checksum_line(path: Path, data: bytes) -> None:
    crc32_hex, sha256_hex = core.checksums(data)
    print(f"{path}: crc32={crc32_hex} sha256={sha256_hex}")


def cmd_combine(args: argparse.Namespace) -> int:
    datas = [_read_file(p) for p in args.inputs]
    lengths = [len(d) for d in datas]

    if args.pad_byte is None:
        if len(set(lengths)) > 1:
            sizes = ", ".join(
                f"{p}={n}" for p, n in zip(args.inputs, lengths)
            )
            raise RomToolError(
                f"input files have mismatched sizes ({sizes}); "
                "use --pad-byte to pad shorter files, or fix the inputs"
            )
    else:
        max_len = max(lengths)
        datas = [
            d + bytes([args.pad_byte]) * (max_len - len(d)) for d in datas
        ]

    combined = core.interleave(datas)
    _write_output(args.output, combined)
    _print_checksum_line(args.output, combined)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add src/romtool/cli.py tests/test_cli.py
git commit -m "Add romtool combine command"
```

---

## Task 6: CLI — split command

**Files:**
- Modify: `src/romtool/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `core.deinterleave(data: bytes, n: int) -> list[bytes]`,
  `core.checksums` (Task 2, 3); `build_parser()` (Task 4);
  `RomToolError`, `_read_file`, `_write_output`, `_print_checksum_line`
  (Task 5).
- Produces: `cli.cmd_split(args: argparse.Namespace) -> int`, used by
  Task 7's `main()`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
from romtool.cli import cmd_split


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
    assert str(low_out) in captured.out
    assert str(high_out) in captured.out


def test_cmd_split_with_n_auto_names_outputs(tmp_path):
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


def test_cmd_split_with_n_auto_names_always_use_bin_suffix(tmp_path):
    # Spec: auto-generated names are always "<stem>.partN.bin", regardless
    # of the input file's own extension.
    combined = tmp_path / "combined.eeprom"
    combined.write_bytes(b"\x01\xAA\x02\xBB")

    parser = build_parser()
    args = parser.parse_args(["split", str(combined), "-n", "2"])
    exit_code = cmd_split(args)

    assert exit_code == 0
    assert (tmp_path / "combined.part0.bin").read_bytes() == b"\x01\x02"
    assert (tmp_path / "combined.part1.bin").read_bytes() == b"\xAA\xBB"


def test_cmd_split_non_divisible_without_allow_truncate_raises(tmp_path):
    combined = tmp_path / "combined.bin"
    combined.write_bytes(b"\x01\xAA\x02")  # length 3, not divisible by 2

    parser = build_parser()
    args = parser.parse_args(["split", str(combined), "-n", "2"])

    with pytest.raises(RomToolError):
        cmd_split(args)


def test_cmd_split_allow_truncate_drops_remainder_and_warns(
    tmp_path, capsys
):
    combined = tmp_path / "combined.bin"
    combined.write_bytes(b"\x01\xAA\x02")  # length 3, not divisible by 2

    parser = build_parser()
    args = parser.parse_args(
        ["split", str(combined), "-n", "2", "--allow-truncate"]
    )
    exit_code = cmd_split(args)

    assert exit_code == 0
    part0 = tmp_path / "combined.part0.bin"
    part1 = tmp_path / "combined.part1.bin"
    assert part0.read_bytes() == b"\x01"
    assert part1.read_bytes() == b"\xAA"

    captured = capsys.readouterr()
    assert "truncat" in captured.err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_split'`

- [ ] **Step 3: Write minimal implementation**

Add to the top of `src/romtool/cli.py`:

```python
import sys
```

Append to `src/romtool/cli.py`:

```python
def _split_output_paths(args: argparse.Namespace, n: int) -> list[Path]:
    if args.outputs is not None:
        return list(args.outputs)
    # Spec: auto-generated names are always "<stem>.partN.bin", regardless
    # of the input file's own extension.
    stem = args.input.stem
    parent = args.input.parent
    return [parent / f"{stem}.part{i}.bin" for i in range(n)]


def cmd_split(args: argparse.Namespace) -> int:
    # n is guaranteed >= 2 here: build_parser() validates -n via
    # parse_split_n and -o via _MinLengthAction, both at parse time.
    n = args.n if args.n is not None else len(args.outputs)

    data = _read_file(args.input)
    remainder = len(data) % n
    if remainder != 0:
        if not args.allow_truncate:
            raise RomToolError(
                f"{args.input} has size {len(data)}, not divisible by "
                f"{n} ({remainder} trailing bytes); use --allow-truncate "
                "to drop them, or fix N/the input"
            )
        print(
            f"warning: truncating {remainder} trailing byte(s) from "
            f"{args.input} to make its size divisible by {n}",
            file=sys.stderr,
        )
        data = data[: len(data) - remainder]

    outputs = _split_output_paths(args, n)
    parts = core.deinterleave(data, n)
    for path, part in zip(outputs, parts):
        _write_output(path, part)
        _print_checksum_line(path, part)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit**

```bash
git add src/romtool/cli.py tests/test_cli.py
git commit -m "Add romtool split command"
```

---

## Task 7: CLI — main() entry point, packaging, end-to-end smoke test

**Files:**
- Modify: `src/romtool/cli.py`
- Create: `src/romtool/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `build_parser()`, `cmd_combine()`, `cmd_split()`,
  `RomToolError` (Task 4, 5, 6).
- Produces: `cli.main(argv: list[str] | None = None) -> int`, referenced
  by the `pyproject.toml` `romtool` console-script entry point (Task 1)
  and by `src/romtool/__main__.py`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
from romtool.cli import main


def test_main_combine_end_to_end(tmp_path, capsys):
    low = tmp_path / "low.bin"
    high = tmp_path / "high.bin"
    out = tmp_path / "out.bin"
    low.write_bytes(b"\x01\x02")
    high.write_bytes(b"\xAA\xBB")

    exit_code = main(
        ["combine", str(low), str(high), "-o", str(out)]
    )

    assert exit_code == 0
    assert out.read_bytes() == b"\x01\xAA\x02\xBB"


def test_main_split_end_to_end(tmp_path):
    combined = tmp_path / "combined.bin"
    combined.write_bytes(b"\x01\xAA\x02\xBB")

    exit_code = main(["split", str(combined), "-n", "2"])

    assert exit_code == 0
    assert (tmp_path / "combined.part0.bin").read_bytes() == b"\x01\x02"
    assert (tmp_path / "combined.part1.bin").read_bytes() == b"\xAA\xBB"


def test_main_reports_romtool_error_on_stderr_with_exit_1(tmp_path, capsys):
    missing = tmp_path / "missing.bin"
    high = tmp_path / "high.bin"
    high.write_bytes(b"\xAA")
    out = tmp_path / "out.bin"

    exit_code = main(
        ["combine", str(missing), str(high), "-o", str(out)]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "cannot read" in captured.err


def test_main_combine_roundtrips_with_split(tmp_path):
    low = tmp_path / "low.bin"
    high = tmp_path / "high.bin"
    combined = tmp_path / "combined.bin"
    low.write_bytes(bytes(range(0, 50)))
    high.write_bytes(bytes(range(50, 100)))

    assert main(["combine", str(low), str(high), "-o", str(combined)]) == 0
    assert main(["split", str(combined), "-n", "2"]) == 0

    assert (tmp_path / "combined.part0.bin").read_bytes() == low.read_bytes()
    assert (tmp_path / "combined.part1.bin").read_bytes() == high.read_bytes()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'main'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/romtool/cli.py`:

```python
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "combine":
            return cmd_combine(args)
        elif args.command == "split":
            return cmd_split(args)
    except RomToolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
```

Create `src/romtool/__main__.py`:

```python
import sys

from romtool.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (all tests green)

Run the full suite: `pytest -v`
Expected: all tests across `test_core.py` and `test_cli.py` PASS

- [ ] **Step 5: Manual smoke test**

Run:

```bash
cd /media/sda1/git/rom
pip install -e ".[test]"
printf '\x01\x02\x03' > /tmp/low.bin
printf '\xAA\xBB\xCC' > /tmp/high.bin
romtool combine /tmp/low.bin /tmp/high.bin -o /tmp/combined.bin
python -m romtool split /tmp/combined.bin -n 2
xxd /tmp/combined.bin
```

Expected: `romtool combine` prints a `crc32=... sha256=...` line for
`/tmp/combined.bin`; `python -m romtool split` prints two checksum lines
for `/tmp/combined.part0.bin` and `/tmp/combined.part1.bin`; `xxd` shows
`01 aa 02 bb 03 cc`.

- [ ] **Step 6: Commit**

```bash
git add src/romtool/cli.py src/romtool/__main__.py tests/test_cli.py
git commit -m "Add romtool main() entry point and __main__"
```

---
