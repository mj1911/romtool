<img width="1456" height="720" alt="romtool" src="https://github.com/user-attachments/assets/bfd640e4-0c94-42c8-b4e5-97937fb4322a" />

# romtool

`romtool` interleaves (combines) and de-interleaves (splits) binary
ROM/EPROM images, byte-wise, across any number of files.

This is a classic problem when working with retro hardware that spreads a
single logical ROM across multiple physical chips — for example a 16-bit
system that stores even bytes in one EPROM and odd bytes in another
("Low"/"High" halves), or some obscure board that splits a program across
4 or even 8 chips. `romtool` reassembles those dumps into a single linear
image for analysis, or can split a linear image back into chip-sized pieces
for burning to physical hardware.

It works on any binary file, not just ROM dumps — anything that needs
byte-wise interleaving/de-interleaving across N files will work. `romtool`
should run on Windows, Linux, and Mac.

## What it does

- **`combine`** — reads N input files and interleaves them one byte at a
  time (byte 0 of file 1, byte 0 of file 2, ..., byte 1 of file 1, byte 1
  of file 2, ...) into a single output file.
- **`split`** — reads one input file and de-interleaves it into N equal
  output files, reversing what `combine` does.
- Input files for `combine` are normally required to be the same length;
  `--pad-byte` relaxes that by padding shorter files up to the longest
  one.  Missing bytes are filled in with the specified pad byte value.
- Input size for `split` is normally required to be evenly divisible by
  N; `--allow-truncate` relaxes that by dropping trailing bytes that
  don't fill a complete row.  Use with caution.
- Every input and output file gets a plain byte-sum, CRC16, CRC32, and
  md5 checksum printed, so you can verify results or compare against
  known-good dumps.
- `combine` and `split` are exact inverses of each other (given
  same-sized inputs and no truncation), so round-tripping a set of files
  through both reproduces the originals byte-for-byte.

## Install

    pip install -e ".[test]"

## Dev or Arch Linux Install

    python -m venv .venv    (once, then)
    . .venv/bin/activate && pip install -e ".[test]"
    romtool -h

## Usage

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

## Command Options

    --pad-byte 0xnn   (combine) fills any missing bytes in shorter inputs
                      with hex (0x00-0xFF) or decimal value (0-255) so they
                      match the length of the longest input.
    --allow-truncate  (split) allows the input file's size to not be evenly
                      divisible by N, dropping the trailing bytes that don't
                      fill a complete row.

Each read input file has its sum, CRC16, CRC32, and MD5 checksums
reported before `romtool` does anything else with it, e.g.:

    LOW.bin: sum=1F4A crc16=9A12 crc32=02BC051A md5=25F9E79432...

Each successfully written output file also has its sum, CRC16, CRC32,
and MD5 checksums reported, e.g.:

    combined.bin: sum=3165 crc16=29B1 crc32=1A2B3C4D md5=9F86D0818...

## Requirements

Python 3.9+. No third-party runtime dependencies.

## End-to-End Test

    pytest

## Helpful Tidbits

**When naming EPROM files**, I find it very helpful to include the unit, model,
location, type of chip, as well as the sum in the filename.  Most programmers 
at least display the sum, so one can be sure it was read/written successfully.  
Ex:

    K-Tron_K-Commander_PCMCIA_RomLow_ST27C2001_0x15B25BC.bin

**Chip labels (U1, U2, "Low"/"High", etc.) don't reliably tell you the real 
byte order** — `romtool` has no way to know how a board's designer wired things
up, and it's not uncommon for a chip labeled U1 to actually hold the
high/odd bytes while U2 holds the low/even ones, or for the order to be
non-obvious in a 4+ chip interleave. `combine` uses exactly the order you
give it, nothing more. If the result looks like gibberish, try other input
orderings and check for readable text, e.g.:

    romtool combine U2.bin U1.bin -o test.bin && strings test.bin | less

Another cause of garbled-looking combines is readable text that's merely
interleaved with an unrelated data plane (attribute bytes, a lookup table,
etc.) Stripping these non-ASCII bytes from a suspect region before giving up on
an ordering can reveal text that `strings` misses.  

## Why?

Because I wanted a tool to combine low and high files to view the full data.

Looking on the web, such tools are a dime a dozen, but are all sketchy.  Found
such a tool in a rather obscure forum which seemed safe.  Downloaded it, but
wasn't going to run it without examining it first.  Discovered the file was
packed with UPX, which was a little suspicious but not unheard-of.  Tried to
decompress it, but the UPX header was scrubbed - even more suspicious.  Should
have left it at that and walked away... but decided to have Claude try to make
a static-analysis tool to patch such executables (reconstruct the scrubbed
headers) so they could be decompressed by UPX natively.  I explicitly told it
that this must be static-analysis only, and to never "dynamically get an
import table." Furthermore, I told it nothing of this particular file - just
of scrubbed UPX executables in general (and it even created its own example
files.)  And it totally worked!  Patched the example file and UPX decompressed
it successfully.  However, Claude or one of its sub-agents somehow found the
questionable file and thought it was a perfect test candidate, so *ran it*
(I'm guessing to verify the dynamic imports), which then infected a whole
workplace with some kind of nasty worm!

Ironically, in the next day's Claude release notes, saw lots of fixes for
similar rogue behavior.  Let this be a warning whenever using AI agents: a
bulletproof sandbox is not just a good idea; *it will totally save your bacon.*
