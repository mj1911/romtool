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
