<img width="1456" height="720" alt="romtool" src="https://github.com/user-attachments/assets/bfd640e4-0c94-42c8-b4e5-97937fb4322a" />

# romtool

`romtool` interleaves (combines) and de-interleaves (splits) binary
ROM/EPROM images, byte-wise, across any number of files.  It also can show
duplicate/unique files.

These are some classic problems when working with retro hardware which spreads a
single logical ROM across multiple physical chips — for example a 16-bit
system that stores even bytes in one EPROM and odd bytes in another
("Low"/"High" halves), or some obscure board that uses 4 or even 8 chips.
`romtool` reassembles those dumps into a single linear
stream for analysis, or can split a stream back into chip-sized blocks
for burning to physical hardware.

It works on any binary file, not just ROM dumps — anything that can benefit
from byte-wise interleaving/de-interleaving. `romtool` should run on Windows,
Linux, and Mac.

## What it does (commands) and usage

- **`combine`** — reads N input files and interleaves them one byte at a
  time (byte 0 of file 1, byte 0 of file 2, ..., byte 1 of file 1, byte 1
  of file 2, ...) into a single output file.
  
Input files for `combine` are normally required to be the same length;
`--pad-byte` relaxes that by padding shorter files up to the longest
one.  Missing bytes are filled in with the specified pad byte value.

    romtool combine file1 file2 filen -o outputfile [--pad-byte 0xnn]
    romtool combine 01.bin 02.bin 03.bin 04.bin -o big.bin
    romtool combine LOW.bin HIGH.bin -o Combined.bin --pad-byte 0xFF

- **`split`** — reads one input file and de-interleaves it into N equal
  output files, reversing what `combine` does.

Input size for `split` is normally required to be evenly divisible by
N; `--allow-truncate` relaxes that by dropping trailing bytes that
don't fill a complete row; use with caution.

    romtool split inputfile [-n number]|[-o out1 out2 outn] [--allow-truncate]
    romtool split Combined.bin -o LOW.bin HIGH.bin
    romtool split Big.bin -n 4 --allow-truncate
    # writes Big.part0.bin, Big.part1.bin, Big.part2.bin, Big.part3.bin
  
- `combine` and `split` are exact inverses of each other (given
  same-sized inputs and no truncation), so round-tripping a set of files
  through both reproduces the original file byte-for-byte.

- **`compare`** — reads a set of files/folders, MD5-hashes every file
  found, and reports which files are byte-identical duplicates, and which are 
  unique.  Handy for de-duping a growing EPROM collection.  
  `--recursive` makes folder arguments descend into sub-directories 
  (off by default.)

    romtool compare path [path ...] [--recursive]
    romtool compare D:\dumps --recursive
    
    comparing 3 file(s) under dumps/
    
    duplicates (1 groups):
      Group 1 (2 files, md5=25F9E79432...):
        copy_of_low.bin
        low.bin
    
    unique (1 files):
      high.bin (md5=9F86D081884C7D659A2FEAA0C55AD015)

Every input and output file gets a byte-wise-sum, CRC16, CRC32, and MD5
checksum printed so you can verify results or compare against
known-good data:

    LOW.bin: sum=1F4A crc16=9A12 crc32=02BC051A md5=25F9E79432...
    
## Install and run (app only, no test framework)

    git clone https://github.com/mj1911/romtool
    cd romtool
    pip install -e .
    romtool -h

## Dev or Arch Linux Install (".[test]" includes test framework)

    git clone https://github.com/mj1911/romtool
    cd romtool
    python -m venv .venv
    . .venv/bin/activate
    pip install -e ".[test]"
    romtool -h

Changes made to the files when installed this way are instantly reflected
in the app - this folder *is* the location of the app; simply delete it to
uninstall.

## Requirements

Python 3.9+. No third-party runtime dependencies.

## End-to-End Test of all features

    pytest

## Helpful Tidbits

**When naming EPROM files**, it is very helpful to include the make, model,
location, type of chip, as well as the sum in the filename while avoiding
spaces.  Many programmers display the sum, so one can verify it was read /
written successfully. Ex:

    KTron_K-Commander_PCMCIA_RomLow_ST27C2001_0x15B25BC.bin

**Chip labels (U1, U2, "Low"/"High", etc.)** don't reliably indicate the real
byte order — `romtool` has no way of knowing how a board's designer wired
things, and it is not uncommon for a chip labeled U1 to actually hold the
high/odd bytes while U2 holds the low/even ones, or for the order to be
non-obvious in a 4+ chip set. `combine` uses exactly the order you
specify, nothing more. If the result looks out-of-order, try other input
orderings and check for readable text, e.g.:

    romtool combine U2.bin U1.bin -o test.bin && strings test.bin | less

Another cause of a garbled-looking combine is readable text that's simply
interleaved with an unrelated data plane, such as attribute bytes, lookup
tables, etc. 

## Versions

    0.1.2 - Reworked compare output to be more readable.
    0.1.1 - Added compare command, showing which files are duplicates/unique.
    0.1.0 - Initial release; split and combine commands.

## Why?

Because I wanted a tool to combine low and high files to view the full data,
and being able to identify duplicate ROMs is very handy.

Looking on the web, such "binary merge" tools are common, but *all are
sketchy* and some are even malware.  `romtool` is simple and open-source -
you know exactly what you're getting; no unwelcome suprises here.
