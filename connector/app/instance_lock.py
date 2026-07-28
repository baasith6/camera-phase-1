"""Cross-platform single-instance lock for one connector state directory."""
from __future__ import annotations

import atexit
import os
from pathlib import Path
from typing import BinaryIO


class InstanceLock:
    def __init__(self, state_dir: str, filename: str = "connector.lock"):
        self.path = Path(state_dir) / filename
        self._file: BinaryIO | None = None

    def acquire(self) -> bool:
        handle: BinaryIO | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+b")
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            if handle is not None:
                handle.close()
            return False

        self._file = handle
        atexit.register(self.release)
        return True

    def release(self) -> None:
        if self._file is None:
            return
        try:
            self._file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None
