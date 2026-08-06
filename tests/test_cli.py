import pytest

from romtool import core
from romtool.cli import build_parser, RomToolError, cmd_combine, cmd_split


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
    low_crc32, low_sha256 = core.checksums(low_out.read_bytes())
    high_crc32, high_sha256 = core.checksums(high_out.read_bytes())
    assert f"{low_out}: crc32={low_crc32} sha256={low_sha256}" in captured.out
    assert f"{high_out}: crc32={high_crc32} sha256={high_sha256}" in captured.out


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
    part0_crc32, part0_sha256 = core.checksums(part0.read_bytes())
    part1_crc32, part1_sha256 = core.checksums(part1.read_bytes())
    assert f"{part0}: crc32={part0_crc32} sha256={part0_sha256}" in captured.out
    assert f"{part1}: crc32={part1_crc32} sha256={part1_sha256}" in captured.out


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
