"""A separate lock inode survives atomic state-file replacement."""
import os
import time
from contextlib import contextmanager
from pathlib import Path

from src.domain.feature_licenses import LicenseError


@contextmanager
def file_lock(path: Path, *, timeout: float = 5):
    handle = None
    locked = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LicenseError("license_storage_unavailable") from None
                time.sleep(0.02)
        yield
    except OSError:
        raise LicenseError("license_storage_unavailable") from None
    finally:
        if handle is not None:
            try:
                if locked:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
