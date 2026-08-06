import pytest

from romtool import core
from romtool.cli import build_parser, RomToolError, cmd_combine


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
