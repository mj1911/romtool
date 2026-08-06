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
