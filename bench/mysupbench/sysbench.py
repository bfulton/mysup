"""Running sysbench and reading what it printed."""

import re
import resource
import subprocess
import time

from . import probes


def command(inst, test, engine, rows, extra):
    return ["sysbench", test, "--db-driver=mysql",
            "--mysql-socket=" + inst.sock, "--mysql-user=root",
            "--mysql-db=sbtest", "--tables=1", f"--table_size={rows}",
            "--rand-type=uniform", "--mysql_storage_engine=" + engine,
            ] + list(extra)


def version():
    return subprocess.run(["sysbench", "--version"], capture_output=True,
                          text=True, check=True).stdout.strip()


_NUM = r"([0-9.]+)"
_PATTERNS = {
    "reads": rf"read:\s+{_NUM}",
    "writes": rf"write:\s+{_NUM}",
    "other": rf"other:\s+{_NUM}",
    "queries": rf"total:\s+{_NUM}",
    "transactions": rf"transactions:\s+{_NUM}",
    "ignored_errors": rf"ignored errors:\s+{_NUM}",
    "reconnects": rf"reconnects:\s+{_NUM}",
    "seconds": rf"total time:\s+{_NUM}s",
    "lat_min_ms": rf"min:\s+{_NUM}",
    "lat_avg_ms": rf"avg:\s+{_NUM}",
    "lat_max_ms": rf"max:\s+{_NUM}",
    "lat_p99_ms": rf"99th percentile:\s+{_NUM}",
}
_INTERVAL = re.compile(
    r"^\[ *\d+s \] thds: \d+ tps: ([0-9.]+) qps: ([0-9.]+)", re.M)


def parse(text):
    out = {}
    for key, pat in _PATTERNS.items():
        m = re.search(pat, text)
        if not m:
            raise ValueError(f"sysbench output has no {key!r}:\n{text}")
        v = float(m.group(1))
        out[key] = int(v) if v == int(v) and "lat" not in key \
            and key != "seconds" else v
    series = _INTERVAL.findall(text)
    out["tps_by_second"] = [float(t) for t, _ in series]
    out["qps_by_second"] = [float(q) for _, q in series]
    return out


class SysbenchFailed(RuntimeError):
    pass


def run(cmd, tick=None):
    """Run one sysbench command; return (its output, client CPU, wall).

    `tick` is called as sysbench starts its clock and again as each of its
    one-second reports arrives, so a caller can read a counter at the
    boundaries of the seconds sysbench itself reports. stdbuf makes those
    lines arrive when they are printed and not when a pipe buffer fills.
    """
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    w0 = time.monotonic()
    p = subprocess.Popen(["stdbuf", "-oL"] + cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines = []
    for line in p.stdout:
        lines.append(line)
        if tick and line.startswith(("Threads started!", "[ ")):
            tick()
    p.wait()
    wall = time.monotonic() - w0
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    text = "".join(lines)
    if p.returncode != 0 or "FATAL" in text:
        raise SysbenchFailed(" ".join(cmd) + "\n" + text)
    client = {"utime_s": ru1.ru_utime - ru0.ru_utime,
              "stime_s": ru1.ru_stime - ru0.ru_stime}
    return text, client, wall


_STATUS_PREFIXES = ("Innodb_", "Rocksdb_", "Handler_", "Com_", "Select_",
                    "Sort_", "Created_tmp", "Questions", "Queries",
                    "Bytes_", "Table_locks", "Opened_")


def status(inst):
    out = {}
    for row in inst.sql("SHOW GLOBAL STATUS"):
        if len(row) == 2 and row[0].startswith(_STATUS_PREFIXES):
            try:
                out[row[0]] = int(row[1])
            except ValueError:
                pass
    return out


def measured(inst, dev, cmd):
    """One measured run: sysbench's own figures, and beside them what the
    server process, its cgroup and the block device did meanwhile.

    The status snapshots sit outside the counters' window, so their own
    cost is not charged to the workload.
    """
    st0 = status(inst)
    pid = inst.pid
    inst.cgroup.reset_peak()
    b0 = probes.block_stat(dev)
    io0 = probes.proc_io(pid)
    t0 = probes.proc_ticks(pid)
    ticks = []
    c0 = probes.proc_cpu_ns(pid)
    try:
        text, client, wall = run(
            cmd, lambda: ticks.append((time.monotonic(),
                                       probes.proc_cpu_ns(pid))))
    except SysbenchFailed:
        inst.check()
        raise
    c1 = probes.proc_cpu_ns(pid)
    t1 = probes.proc_ticks(pid)
    io1 = probes.proc_io(pid)
    b1 = probes.block_stat(dev)
    cg = inst.cgroup.read()
    mem = probes.proc_mem(pid)
    st1 = status(inst)
    row = parse(text)
    row["wall_s"] = wall
    # Server CPU in each of sysbench's reported seconds. The host's speed
    # changes from one second to the next, and a run's total hides that.
    if len(ticks) == len(row["qps_by_second"]) + 1:
        row["server_cpu_by_second"] = [
            (ticks[i + 1][1] - ticks[i][1]) / 1e9
            for i in range(len(ticks) - 1)]
        row["tick_s"] = [ticks[i + 1][0] - ticks[i][0]
                         for i in range(len(ticks) - 1)]
    row["server"] = {
        "cpu_s": (c1 - c0) / 1e9,
        "utime_s": t1[0] - t0[0],
        "stime_s": t1[1] - t0[1],
        "io": probes.delta(io1, io0),
        "rss": mem.get("VmRSS"),
    }
    row["client"] = client
    row["block"] = probes.delta(b1, b0)
    row["cgroup"] = cg
    row["status"] = {k: st1[k] - st0[k] for k in st1
                     if k in st0 and st1[k] != st0[k]}
    return row
