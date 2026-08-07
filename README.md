<img width="1456" height="720" alt="romtool" src="https://github.com/user-attachments/assets/bfd640e4-0c94-42c8-b4e5-97937fb4322a" />

# romtool

`romtool` interleaves (combines) and de-interleaves (splits) binary
ROM/EPROM images, byte-wise, across any number of files.  It can also show
duplicate/unique files.

This is a classic problem when working with retro hardware that spreads a
single logical ROM across multiple physical chips — for example a 16-bit
system that stores even bytes in one EPROM and odd bytes in another
("Low"/"High" halves), or some obscure board that splits a program across
4 or even 8 chips. `romtool` reassembles those dumps into a single linear
stream for analysis, or can split a stream back into chip-sized blocks
for burning to physical hardware.

It works on any binary file, not just ROM dumps — anything that can benefit
from byte-wise interleaving/de-interleaving. `romtool` should run on Windows,
Linux, and Mac.

## What it does (commands)

- **`combine`** — reads N input files and interleaves them one byte at a
  time (byte 0 of file 1, byte 0 of file 2, ..., byte 1 of file 1, byte 1
  of file 2, ...) into a single output file.
- Input files for `combine` are normally required to be the same length;
  `--pad-byte` relaxes that by padding shorter files up to the longest
  one.  Missing bytes are filled in with the specified pad byte value.
- **`split`** — reads one input file and de-interleaves it into N equal
  output files, reversing what `combine` does.
- Input size for `split` is normally required to be evenly divisible by
  N; `--allow-truncate` relaxes that by dropping trailing bytes that
  don't fill a complete row.  Use with caution.
- **`compare`** — reads a set of files/folders, MD5-hashes every file
  found, and reports which files are byte-identical duplicates, and which are 
  unique. `--recursive` makes folder arguments descend into subdirectories 
  (off by default).
- Every input and output file gets a bytewise-sum, CRC16, CRC32, and MD5
  checksum printed so you can verify results or compare against
  known-good dumps.
- `combine` and `split` are exact inverses of each other (given
  same-sized inputs and no truncation), so round-tripping a set of files
  through both reproduces the original file byte-for-byte.

## Install and run

    pip install -e ".[test]"
    romtool -h

## Dev or Arch Linux Install

    python -m venv .venv    (once, then)
    . .venv/bin/activate && pip install -e ".[test]"
    romtool -h

## Usage

Each input file and output file has its sum, CRC16, CRC32, and MD5 checksums
reported, e.g.:

    LOW.bin: sum=1F4A crc16=9A12 crc32=02BC051A md5=25F9E79432...

### Combine (interleave)

    romtool combine file1 file2 filen -o outputfile [--pad-byte 0xnn]

Takes 2 or more input files and interleaves them byte-by-byte into
`outputfile`. All inputs must be the same size unless `--pad-byte` is
given.  Example:

    romtool combine 01.bin 02.bin 03.bin 04.bin -o big.bin
    romtool combine LOW.bin HIGH.bin -o Combined.bin --pad-byte 0xFF

If input sizes differ and `--pad-byte` is not given, `romtool` refuses to
guess and reports the mismatched sizes:

    error: input files have mismatched sizes (low.bin=1024, high.bin=1000); use
    --pad-byte to pad shorter files, or fix the inputs

`--pad-byte 0xnn` fills any missing bytes in shorter inputs with hex
(0x00-0xFF) or decimal (0-255) so they match the length of the longest input.

### Split (de-interleave)

    romtool split inputfile [-n number]|[-o out1 out2 outn] [--allow-truncate]

Takes one input file and de-interleaves it into N output files, where N
is either given directly with `-n`, or inferred from the number of
filenames passed to `-o`. Exactly one of `-n` or `-o` must be given.

    romtool split Combined.bin -o LOW.bin HIGH.bin
    romtool split Combined.bin -n 4 --allow-truncate

If `-n` is used instead of `-o`, output files are auto-named
`<input-stem>.part0.bin`, `<input-stem>.part1.bin`, etc., regardless of
the input file's own extension:

    romtool split Combined.bin -n 2
    # writes Combined.part0.bin, Combined.part1.bin

If the input's size isn't evenly divisible by N, `romtool` refuses to
omit bytes unless `--allow-truncate` is given (in which case the
remainder is dropped with a warning on stderr):

    error: combined.bin has size 3, not divisible by 2 (1 trailing bytes); use
    --allow-truncate to fix N/the input

`--allow-truncate` allows the input file's size to not be evenly divisible by
N, dropping the trailing bytes that don't fill a complete row.  Use with
discretion.

### Compare (find duplicates)

    romtool compare path [path ...] [--recursive]

Takes one or more files and/or folders, MD5-hashes every file found, and
reports which are exact duplicates of each other and which are unique.
Folder arguments only look at their direct children unless `--recursive`
is given; file arguments are always included. Symlinks and non-regular
files (sockets, devices, etc.) are always skipped. Example:

    romtool compare dumps/ --recursive

    duplicates:
      dumps/copy_of_low.bin: duplicate of dumps/low.bin (md5=25F9E79432...)

    unique:
      dumps/high.bin (md5=9F86D081884C7D659A2FEAA0C55AD015)

    scanned 3 file(s): 1 duplicate group(s), 1 unique

Exit code is always 0 for a completed scan, whether or not duplicates
were found — `compare` is a report, intended for user info, not a pass/fail
check.

`--recursive` makes folder arguments descend into subdirectories; without it,
only a folder's direct children are considered. File arguments are always
included regardless of this flag.

## Requirements

Python 3.9+. No third-party runtime dependencies.

## End-to-End Test of all features

    pytest

## Helpful Tidbits

**When naming EPROM files**, it is very helpful to include the make, model,
location, type of chip, as well as the sum in the filename, while avoiding
spaces.  Many programmers display the sum, so one can verify it was read /
written successfully. Ex:

    KTron_K-Commander_PCMCIA_RomLow_ST27C2001_0x15B25BC.bin

**Chip labels (U1, U2, "Low"/"High", etc.)** don't reliably indicate the real
byte order — `romtool` has no way of knowing how a board's designer wired
things, and it is not uncommon for a chip labeled U1 to actually hold the
high/odd bytes while U2 holds the low/even ones, or for the order to be
non-obvious in a 4+ chip interleave. `combine` uses exactly the order you
specify, nothing more. If the result looks out-of-order, try other input
orderings and check for readable text, e.g.:

    romtool combine U2.bin U1.bin -o test.bin && strings test.bin | less

Another cause of a garbled-looking combine is readable text that's simply
interleaved with an unrelated data plane (attribute bytes, a lookup table,
etc.) Stripping these non-ASCII bytes from a suspect region can reveal text
which `strings` misses. Again, dependent on architecture and design.

## Versions

    0.1.1 - Added compare command, showing which files are duplicates/unique.
    0.1.0 - Initial release; split and combine commands.

## Why?

Because I wanted a tool to combine low and high files to view the full data.
And being able to identify duplicates is very handy.

Looking on the web, such a "binary merge" tool is common, but are all sketchy.
Found such a tool in an obscure forum which seemed safe.  Downloaded it, but
not going to blindly run it without examining it first.  Discovered it was
packed with UPX, which was a little suspicious but not unheard-of.  Tried to
decompress it, but the UPX header was scrubbed - even more suspicious.  Should
have left it at that and walked away... but decided to have Claude try to make
a static-analysis tool to patch such an executable (reconstruct the scrubbed
headers) so they could be decompressed by UPX natively.  I explicitly told it
that this must be *static-analysis only*, and to never *dynamically get an
import table.* Furthermore, I told it nothing of this suspect file - just of
how to scrub UPX executables in general (and it even created its own example
files.)  And it totally worked!  Patched the example file and UPX decompressed
it successfully.  However, one of the sub-agents somehow found the questionable
file and thought it was the perfect test candidate, so *ran it* (I'm guessing
to verify the dynamic imports), which then infected a whole workplace with
some kind of nasty worm!

Ironically, in the next day's Claude release notes, saw lots of patches for
similar rogue behavior.  Let this be a warning whenever using AI agents: a
bulletproof sandbox is not just a good idea; *it will totally save your bacon.*
