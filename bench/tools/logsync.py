#!/usr/bin/env python3
"""What one small durable log write costs on this filesystem, by how the
log file is laid out.

    python3 bench/tools/logsync.py [directory]

Each layout does 3,000 commits of one write and one fdatasync, six times,
and reports per commit: the time, and the writes, sectors and flushes the
block device under the directory saw. Nothing else may be writing to the
device. The directory defaults to the harness's work directory.
"""
import ctypes
import mmap
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))
from mysupbench import probes  # noqa: E402

COMMITS = 3000
ROUNDS = 6
RECORD = b"x" * 300
SIZE = 80 << 20
FALLOC_FL_KEEP_SIZE = 1


def prewritten(fd):
    os.pwrite(fd, b"\0" * SIZE, 0)


def empty(fd):
    pass


def reserved(fd):
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    libc.fallocate.argtypes = [ctypes.c_int, ctypes.c_int,
                               ctypes.c_longlong, ctypes.c_longlong]
    if libc.fallocate(fd, FALLOC_FL_KEEP_SIZE, 0, SIZE) != 0:
        raise OSError(ctypes.get_errno(), "fallocate")


def allocated(fd):
    os.posix_fallocate(fd, 0, SIZE)


LAYOUTS = [
    ("overwrite a file already written", prewritten, False),
    ("the same, 4 KiB direct writes", prewritten, True),
    ("write into space allocated to its full length", allocated, False),
    ("append, the file grows", empty, False),
    ("append into space reserved with fallocate", reserved, False),
]


def one(directory, dev, prepare, direct):
    path = os.path.join(directory, "logsync.tmp")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        prepare(fd)
        os.fsync(fd)
        dfd = os.open(directory, os.O_RDONLY)
        os.fsync(dfd)
        os.close(dfd)
        record, step = RECORD, len(RECORD)
        if direct:
            os.close(fd)
            fd = os.open(path, os.O_RDWR | os.O_DIRECT)
            record = mmap.mmap(-1, 4096)
            record.write(b"y" * 4096)
            step = 4096
        time.sleep(0.3)
        before = probes.block_stat(dev)
        t0 = time.perf_counter()
        for i in range(COMMITS):
            if direct:
                os.pwritev(fd, [record], i * step)
            else:
                os.pwrite(fd, record, i * step)
            os.fdatasync(fd)
        seconds = time.perf_counter() - t0
        d = probes.delta(probes.block_stat(dev), before)
    finally:
        os.close(fd)
        os.unlink(path)
    return (seconds / COMMITS * 1e6, d["write_ios"] / COMMITS,
            d["write_sectors"] / COMMITS, d["flush_ios"] / COMMITS)


def main():
    directory = sys.argv[1] if len(sys.argv) > 1 else "/var/tmp/mysup-bench"
    dev = probes.block_device_of(directory)
    got = {name: [] for name, _, _ in LAYOUTS}
    for _ in range(ROUNDS):
        for name, prepare, direct in LAYOUTS:
            got[name].append(one(directory, dev, prepare, direct))
    print(f"{'layout':46} us/commit, median (range)   device writes  "
          "sectors  flushes")
    for name, runs in got.items():
        us = sorted(r[0] for r in runs)
        print(f"{name:46} {statistics.median(us):6.0f} "
              f"({us[0]:.0f}-{us[-1]:.0f})".ljust(72)
              + f"{statistics.median(r[1] for r in runs):9.2f}"
              + f"{statistics.median(r[2] for r in runs):9.1f}"
              + f"{statistics.median(r[3] for r in runs):9.2f}")


if __name__ == "__main__":
    main()
