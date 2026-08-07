from __future__ import annotations

import argparse
import sys
from pathlib import Path

from romtool import __version__, core


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
        if values is None:
            values = []
        if len(values) < self.min_length:
            label = option_string or self.dest
            parser.error(
                f"{label} requires at least {self.min_length} values, "
                f"got {len(values)}"
            )
        setattr(namespace, self.dest, values)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="romtool")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__} - " \
        "home: https://github.com/mj1911/romtool"
    )
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


def _collect_files(paths: list[Path], recursive: bool) -> list[Path]:
    """Expands paths (files and/or folders) into a flat list of regular
    files, in argument order then name-sorted within each folder.
    Symlinks and non-regular files (sockets, FIFOs, etc.) are always
    skipped, at any level. Files are de-duplicated by resolved path."""
    collected: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        resolved = p.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        collected.append(p)

    def walk_dir(dir_path: Path, recurse: bool) -> None:
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: p.name)
        except OSError as e:
            raise RomToolError(f"cannot read {dir_path}: {e.strerror}")
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if recurse:
                    walk_dir(entry, recurse)
            elif entry.is_file():
                add(entry)
            # else: socket/FIFO/device/etc. - silently skipped.

    for p in paths:
        if p.is_symlink():
            continue
        if not p.exists():
            raise RomToolError(f"{p}: no such file or directory")
        if p.is_file():
            add(p)
        elif p.is_dir():
            walk_dir(p, recursive)
        # else: socket/FIFO/device/etc. - silently skipped.

    return collected


def _print_checksum_line(path: Path, data: bytes) -> None:
    sum_hex, crc16_hex, crc32_hex, md5_hex = core.checksums(data)
    print(
        f"{path}: sum={sum_hex} crc16={crc16_hex} crc32={crc32_hex} "
        f"md5={md5_hex}"
    )


def cmd_combine(args: argparse.Namespace) -> int:
    datas = []
    for p in args.inputs:
        data = _read_file(p)
        _print_checksum_line(p, data)
        datas.append(data)
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
    # Printed before truncation: this checksum is of the full on-disk
    # file, not the truncated data used below.
    _print_checksum_line(args.input, data)
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "combine":
            return cmd_combine(args)
        else:
            return cmd_split(args)
    except RomToolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
