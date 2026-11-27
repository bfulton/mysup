"""Counters read from the kernel, each as a snapshot to subtract.

Nothing here samples: every quantity is a cumulative counter the kernel
keeps, read before and after a run.
"""

import mmap
import os
import random
import time

CLK_TCK = os.sysconf("SC_CLK_TCK")


def proc_cpu_ns(pid):
    """On-CPU time of every thread the process has had, in nanoseconds.

    This is the process's CPU-time clock (what clock_getcpuclockid(3)
    names), which the scheduler keeps exactly. utime and stime in
    /proc/<pid>/stat are charged a whole tick at a time, so they are kept
    beside this only for the user/system split.
    """
    return time.clock_gettime_ns(((~pid) << 3) | 2)


def proc_ticks(pid):
    """(utime, stime) of the process in seconds, tick-sampled."""
    with open(f"/proc/{pid}/stat") as f:
        s = f.read()
    rest = s[s.rindex(")") + 2:].split()
    return int(rest[11]) / CLK_TCK, int(rest[12]) / CLK_TCK


def thread_cpu(pid):
    """{tid: (name, CPU seconds)} for the process's threads, tick-sampled.
    A thread that exits between two calls is in the first only."""
    out = {}
    base = f"/proc/{pid}/task"
    for tid in os.listdir(base):
        try:
            with open(f"{base}/{tid}/stat") as f:
                s = f.read()
        except OSError:
            continue
        name = s[s.index("(") + 1:s.rindex(")")]
        rest = s[s.rindex(")") + 2:].split()
        out[int(tid)] = (name, (int(rest[11]) + int(rest[12])) / CLK_TCK)
    return out


def thread_cpu_delta(after, before):
    """CPU seconds by thread name, over the threads alive at both ends.
    Query threads come and go with their connections, so what this is
    for is the threads that stay: the engine's own."""
    out = {}
    for tid, (name, cpu) in after.items():
        if tid in before and before[tid][0] == name:
            d = cpu - before[tid][1]
            if d > 0:
                out[name] = round(out.get(name, 0.0) + d, 2)
    return out


def proc_io(pid):
    """/proc/<pid>/io: read_bytes and write_bytes are bytes that reached
    the block layer on the process's behalf."""
    out = {}
    with open(f"/proc/{pid}/io") as f:
        for line in f:
            k, v = line.split(":")
            out[k.strip()] = int(v)
    return out


def proc_mem(pid):
    out = {}
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith(("VmRSS:", "VmHWM:")):
                k, v = line.split(":")
                out[k] = int(v.split()[0]) * 1024
    return out


_BLOCK_FIELDS = (
    "read_ios", "read_merges", "read_sectors", "read_ms",
    "write_ios", "write_merges", "write_sectors", "write_ms",
    "in_flight", "io_ms", "queue_ms",
    "discard_ios", "discard_merges", "discard_sectors", "discard_ms",
    "flush_ios", "flush_ms",
)


def block_device_of(path):
    """The sysfs directory of the block device a path lives on."""
    st = os.stat(path)
    return os.path.realpath(
        f"/sys/dev/block/{os.major(st.st_dev)}:{os.minor(st.st_dev)}")


def block_stat(sysdir):
    """The device's request counters. read_ms is the summed duration of
    completed reads, so at queue depth one it is the time spent waiting on
    them."""
    with open(os.path.join(sysdir, "stat")) as f:
        vals = [int(x) for x in f.read().split()]
    return dict(zip(_BLOCK_FIELDS, vals))


def delta(after, before):
    return {k: after[k] - before[k] for k in after if k in before}


def disk_read_floor(directory, block=16384, count=2000, size=1 << 30):
    """What one uncached read of `block` bytes costs on this device.

    Random O_DIRECT reads of a file written for the purpose, one at a
    time. Every engine's wait on the disk is some number of these.
    """
    path = os.path.join(directory, "readfloor.dat")
    if not os.path.exists(path) or os.path.getsize(path) != size:
        chunk = os.urandom(1 << 20)
        with open(path, "wb") as f:
            for _ in range(size >> 20):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
    fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
    buf = mmap.mmap(-1, block)
    rng = random.Random(1)
    samples = []
    try:
        for _ in range(count):
            off = rng.randrange(size // block) * block
            t = time.perf_counter_ns()
            os.preadv(fd, [buf], off)
            samples.append(time.perf_counter_ns() - t)
    finally:
        os.close(fd)
        buf.close()
    samples.sort()
    return {
        "block_bytes": block,
        "reads": count,
        "mean_us": sum(samples) / count / 1e3,
        "p50_us": samples[count // 2] / 1e3,
        "p99_us": samples[count * 99 // 100] / 1e3,
    }


def cpu_floor(seconds=3.0):
    """A fixed single-thread loop, timed: how fast this vCPU is right now.

    Rows taken hours apart on a shared host are only comparable if this
    did not move between them.
    """
    n = 0
    x = 0
    t0 = time.perf_counter()
    c0 = time.process_time()
    while time.perf_counter() - t0 < seconds:
        for i in range(100000):
            x = (x * 1103515245 + 12345 + i) & 0x7FFFFFFF
        n += 100000
    cpu = time.process_time() - c0
    wall = time.perf_counter() - t0
    return {"iters_per_cpu_s": n / cpu, "cpu_over_wall": cpu / wall}
