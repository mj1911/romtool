import argparse
import os

import pytest

from romtool import core
from romtool.cli import (
    _collect_files,
    _MinLengthAction,
    build_parser,
    RomToolError,
    cmd_combine,
    cmd_split,
)


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


def test_parser_compare_basic():
    parser = build_parser()
    args = parser.parse_args(["compare", "a.bin", "b.bin"])
    assert args.command == "compare"
    assert [str(p) for p in args.paths] == ["a.bin", "b.bin"]
    assert args.recursive is False


def test_parser_compare_recursive_flag():
    parser = build_parser()
    args = parser.parse_args(["compare", "dir", "--recursive"])
    assert args.recursive is True


def test_parser_compare_single_path_is_valid():
    parser = build_parser()
    args = parser.parse_args(["compare", "onlyone.bin"])
    assert [str(p) for p in args.paths] == ["onlyone.bin"]


def test_parser_compare_requires_at_least_one_path(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["compare"])
    assert exc_info.value.code == 2


def test_min_length_action_treats_none_values_as_too_few(capsys):
    # argparse passes values=None for nargs values that don't collect a
    # sequence; _MinLengthAction should still report "too few" via
    # parser.error() rather than crashing on len(None).
    parser = argparse.ArgumentParser()
    action = _MinLengthAction(
        option_strings=["--foo"], dest="foo", min_length=2
    )
    namespace = argparse.Namespace()
    with pytest.raises(SystemExit) as exc_info:
        action(parser, namespace, None, "--foo")
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
    low_sum, low_crc16, low_crc32, low_md5 = core.checksums(
        low.read_bytes()
    )
    high_sum, high_crc16, high_crc32, high_md5 = core.checksums(
        high.read_bytes()
    )
    sum_hex, crc16_hex, crc32_hex, out_md5_hex = core.checksums(
        out.read_bytes()
    )

    low_line = (
        f"{low}: sum={low_sum} crc16={low_crc16} crc32={low_crc32} "
        f"md5={low_md5}"
    )
    high_line = (
        f"{high}: sum={high_sum} crc16={high_crc16} crc32={high_crc32} "
        f"md5={high_md5}"
    )
    out_line = (
        f"{out}: sum={sum_hex} crc16={crc16_hex} crc32={crc32_hex} "
        f"md5={out_md5_hex}"
    )

    assert low_line in captured.out
    assert high_line in captured.out
    assert out_line in captured.out
    # Inputs are checksummed before the output is written.
    assert captured.out.index(low_line) < captured.out.index(out_line)
    assert captured.out.index(high_line) < captured.out.index(out_line)
    # Inputs are checksummed in the order given on the command line.
    assert captured.out.index(low_line) < captured.out.index(high_line)


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
    low_sum, low_crc16, low_crc32, low_md5 = core.checksums(
        low.read_bytes()
    )
    high_sum, high_crc16, high_crc32, high_md5 = core.checksums(
        high.read_bytes()
    )
    assert (
        f"{low}: sum={low_sum} crc16={low_crc16} crc32={low_crc32} "
        f"md5={low_md5}" in captured.out
    )
    assert (
        f"{high}: sum={high_sum} crc16={high_crc16} crc32={high_crc32} "
        f"md5={high_md5}" in captured.out
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


def test_cmd_combine_prints_earlier_input_checksums_before_later_read_failure(
    tmp_path, capsys
):
    low = tmp_path / "low.bin"
    missing = tmp_path / "missing.bin"
    out = tmp_path / "out.bin"
    low.write_bytes(b"\x01\x02\x03")

    parser = build_parser()
    args = parser.parse_args(
        ["combine", str(low), str(missing), "-o", str(out)]
    )

    with pytest.raises(RomToolError):
        cmd_combine(args)

    captured = capsys.readouterr()
    low_sum, low_crc16, low_crc32, low_md5 = core.checksums(
        low.read_bytes()
    )
    assert (
        f"{low}: sum={low_sum} crc16={low_crc16} crc32={low_crc32} "
        f"md5={low_md5}" in captured.out
    )


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
    in_sum, in_crc16, in_crc32, in_md5 = core.checksums(
        combined.read_bytes()
    )
    low_sum, low_crc16, low_crc32, low_md5 = core.checksums(
        low_out.read_bytes()
    )
    high_sum, high_crc16, high_crc32, high_md5 = core.checksums(
        high_out.read_bytes()
    )
    input_line = (
        f"{combined}: sum={in_sum} crc16={in_crc16} crc32={in_crc32} "
        f"md5={in_md5}"
    )
    low_line = (
        f"{low_out}: sum={low_sum} crc16={low_crc16} crc32={low_crc32} "
        f"md5={low_md5}"
    )
    high_line = (
        f"{high_out}: sum={high_sum} crc16={high_crc16} crc32={high_crc32} "
        f"md5={high_md5}"
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
    part0_sum, part0_crc16, part0_crc32, part0_md5 = core.checksums(
        part0.read_bytes()
    )
    part1_sum, part1_crc16, part1_crc32, part1_md5 = core.checksums(
        part1.read_bytes()
    )
    assert (
        f"{part0}: sum={part0_sum} crc16={part0_crc16} crc32={part0_crc32} "
        f"md5={part0_md5}" in captured.out
    )
    assert (
        f"{part1}: sum={part1_sum} crc16={part1_crc16} crc32={part1_crc32} "
        f"md5={part1_md5}" in captured.out
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
    sum_hex, crc16_hex, crc32_hex, md5_hex = core.checksums(
        combined.read_bytes()
    )
    assert (
        f"{combined}: sum={sum_hex} crc16={crc16_hex} crc32={crc32_hex} "
        f"md5={md5_hex}" in captured.out
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


def test_collect_files_non_recursive_direct_children_only(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"a")
    (tmp_path / "b.bin").write_bytes(b"b")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.bin").write_bytes(b"c")

    result = _collect_files([tmp_path], recursive=False)

    assert result == [tmp_path / "a.bin", tmp_path / "b.bin"]


def test_collect_files_recursive_includes_nested_sorted(tmp_path):
    (tmp_path / "b.bin").write_bytes(b"b")
    (tmp_path / "a.bin").write_bytes(b"a")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.bin").write_bytes(b"d")
    (sub / "c.bin").write_bytes(b"c")

    result = _collect_files([tmp_path], recursive=True)

    assert result == [
        tmp_path / "a.bin",
        tmp_path / "b.bin",
        sub / "c.bin",
        sub / "d.bin",
    ]


def test_collect_files_file_argument_included_directly(tmp_path):
    f = tmp_path / "solo.bin"
    f.write_bytes(b"solo")

    result = _collect_files([f], recursive=False)

    assert result == [f]


def test_collect_files_deduplicates_overlapping_paths(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    f = sub / "x.bin"
    f.write_bytes(b"x")

    # tmp_path (walked recursively) and f (the same file, given directly)
    # both resolve to the same on-disk file.
    result = _collect_files([tmp_path, f], recursive=True)

    assert result == [f]


def test_collect_files_nonexistent_path_raises(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(RomToolError):
        _collect_files([missing], recursive=False)


@pytest.mark.skipif(
    not hasattr(os, "symlink"), reason="platform has no symlink support"
)
def test_collect_files_skips_symlinked_file(tmp_path):
    real = tmp_path / "real.bin"
    real.write_bytes(b"data")
    link = tmp_path / "link.bin"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("creating symlinks not permitted on this platform")

    result = _collect_files([tmp_path], recursive=False)

    assert result == [real]


@pytest.mark.skipif(
    not hasattr(os, "symlink"), reason="platform has no symlink support"
)
def test_collect_files_skips_symlinked_directory(tmp_path):
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    (real_dir / "inside.bin").write_bytes(b"data")
    link_dir = tmp_path / "link_dir"
    try:
        os.symlink(real_dir, link_dir, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks not permitted on this platform")

    result = _collect_files([tmp_path], recursive=True)

    assert result == [real_dir / "inside.bin"]


@pytest.mark.skipif(
    not hasattr(os, "symlink"), reason="platform has no symlink support"
)
def test_collect_files_skips_top_level_symlink_argument(tmp_path):
    real = tmp_path / "real.bin"
    real.write_bytes(b"data")
    link = tmp_path / "link.bin"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("creating symlinks not permitted on this platform")

    result = _collect_files([link], recursive=False)

    assert result == []


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
