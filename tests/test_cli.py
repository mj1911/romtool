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
