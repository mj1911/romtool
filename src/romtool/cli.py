import argparse
from pathlib import Path

from romtool import core


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
