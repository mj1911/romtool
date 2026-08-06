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

Each successfully written output file gets a line printed with its CRC16,
CRC32, and SHA-256 checksums.

## Test

    pytest
