# tooling/src/otsafety_tooling/atomic.py
"""A record is replaced atomically, or the original survives untouched.

Path.write_text OPENS FOR WRITING AND TRUNCATES before a byte is written, so an
interruption leaves the file as neither its old content nor its new one.
Twenty-five call sites wrote that way -- the plan, the ledger, the trace, the
matrix, the README, every contract export and every run record -- and all of
them run unattended, where nobody is watching to notice a half-written record.

THE SEQUENCE, AND WHY EACH STEP IS THERE:

  stage in the TARGET'S OWN DIRECTORY, because os.replace is atomic only within
    one filesystem and fails with EXDEV across devices -- a staged file in /tmp
    is the bug that forces a non-atomic copy instead;
  flush, which reaches the operating system's cache and no further;
  fsync, which waits for the bytes to reach the disk;
  replace, atomic on POSIX and on Windows alike;
  fsync the PARENT DIRECTORY, so the new entry itself survives power loss --
    without it the rename is atomic to another process and still not durable;
  carry the mode across, because mkstemp creates at 0600 and a replaced file
    would silently lose its permissions.

A FAILURE BEFORE THE REPLACE TOUCHES NOTHING. The staged file is removed and the
original stands, which is the whole guarantee: a reader sees the complete old
record or the complete new one, never a fragment of either.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Replace `path` with `text`, atomically, or leave it as it was."""
    write_bytes(path, text.encode(encoding))


def write_bytes(path: Path, data: bytes) -> None:
    """Replace `path` with `data`, atomically, or leave it as it was."""
    folder = path.parent
    folder.mkdir(parents=True, exist_ok=True)
    # THE MODE TO RESTORE, read before anything is staged: mkstemp creates at
    # 0600 and a replace would carry that onto a file that was executable.
    mode = path.stat().st_mode & 0o777 if path.exists() else None

    handle, staged = tempfile.mkstemp(dir=folder, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as writing:
            writing.write(data)
            writing.flush()
            os.fsync(writing.fileno())
        if mode is not None:
            os.chmod(staged, mode)
        os.replace(staged, path)
    except BaseException:
        # NOTHING PARTIAL IS PUBLISHED. The staged file goes and the original
        # stands exactly as it was.
        Path(staged).unlink(missing_ok=True)
        raise

    # THE RENAME IS ATOMIC TO ANOTHER PROCESS AND NOT YET DURABLE. Syncing the
    # directory is what makes the new entry survive losing power here.
    opened = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(opened)
    finally:
        os.close(opened)
