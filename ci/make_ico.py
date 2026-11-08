#!/usr/bin/env python3
"""Make a Windows .ico from one square PNG, with no image library.

    python3 ci/make_ico.py master.png out.ico

Resizes with macOS `sips` to 16/24/32/48/64/128/256 and stores each size as
PNG inside the .ico (Windows Vista and later read PNG entries). Run on a Mac
once per logo change; the .ico is committed to the tool's repo so Windows
never has to draw anything.
"""
import os
import struct
import subprocess
import sys
import tempfile

SIZES = (16, 24, 32, 48, 64, 128, 256)


def ico_from_pngs(pngs: list) -> bytes:
    """pngs: [(size, png bytes)]. Returns the .ico file's bytes."""
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, data in pngs:
        dim = 0 if size >= 256 else size          # 0 means 256 in an ICONDIRENTRY
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    return header + entries + blobs


def main(master: str, out: str) -> None:
    pngs = []
    with tempfile.TemporaryDirectory() as work:
        for size in SIZES:
            p = os.path.join(work, "%d.png" % size)
            subprocess.run(["sips", "-z", str(size), str(size), master, "--out", p],
                           check=True, capture_output=True)
            with open(p, "rb") as f:
                pngs.append((size, f.read()))
    with open(out, "wb") as f:
        f.write(ico_from_pngs(pngs))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
