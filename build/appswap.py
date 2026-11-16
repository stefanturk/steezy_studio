#!/usr/bin/env python3
"""Put a freshly built app where the old one was without ever leaving a gap.

    python3 appswap.py <staged.app> <final.app>

A Dock pin or an open window that looks for the app while it is half-built, or between "deleted"
and "rebuilt", shows a question mark. So the new app is built beside the old one and swapped in
with one atomic rename (macOS renamex_np with RENAME_SWAP); where that isn't possible it falls
back to two quick renames. The old copy is deleted last.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import sys

RENAME_SWAP = 2


def _swap_atomically(a: str, b: str) -> bool:
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        fn = libc.renamex_np
        fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        return fn(os.fsencode(a), os.fsencode(b), RENAME_SWAP) == 0
    except Exception:
        return False


def swap(staged: str, final: str) -> None:
    if not os.path.isdir(staged):
        raise SystemExit("Nothing built at %s" % staged)
    if not os.path.exists(final):
        os.rename(staged, final)
        return
    if _swap_atomically(staged, final):
        shutil.rmtree(staged, ignore_errors=True)       # `staged` now holds the old app
        return
    old = final + ".old"
    shutil.rmtree(old, ignore_errors=True)
    os.rename(final, old)
    os.rename(staged, final)
    shutil.rmtree(old, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    swap(sys.argv[1], sys.argv[2])
