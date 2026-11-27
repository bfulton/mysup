#!/usr/bin/env python3
"""The write and sync calls each engine makes per commit, and how long
they take, traced with strace while sysbench inserts at one client thread.

    python3 bench/tools/tracesync.py /path/to/unpacked/server [workload]

The arms take turns, twice. Each needs its in-memory load from the harness
(`mysupbench run --condition mem`). strace slows every call it reports, so
read the two engines against each other and not against the rows.
"""
import collections
import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))
from mysupbench import run as harness  # noqa: E402

CALLS = ("fdatasync,fsync,sync_file_range,pwrite64,write,pwritev,"
         "fallocate,io_submit")


def trace(r, arm, workload, scratch):
    inst, _ = r.prepare(arm)
    r._start(inst, arm, restore=True)
    try:
        sb = subprocess.Popen(r._cmd(inst, arm, workload, 1, 22, 7),
                              stdout=subprocess.PIPE, text=True)
        time.sleep(8)
        fds = {}
        for fd in os.listdir(f"/proc/{inst.pid}/fd"):
            try:
                fds[fd] = os.readlink(f"/proc/{inst.pid}/fd/{fd}")
            except OSError:
                pass
        out = os.path.join(scratch, f"strace-{arm}.txt")
        st = subprocess.Popen(
            ["strace", "-f", "-T", "-e", "trace=" + CALLS,
             "-p", str(inst.pid), "-o", out],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(8)
        st.send_signal(2)
        st.wait()
        text = sb.communicate()[0]
    finally:
        inst.stop()
        inst.cgroup.destroy()
    tps = re.search(r"transactions:\s+\d+\s+\(([\d.]+) per sec", text)
    calls = collections.defaultdict(list)
    with open(out) as f:
        for line in f:
            m = re.match(r"\d+\s+(\w+)\((\d+)?.*<([\d.]+)>$", line.strip())
            if m:
                name = os.path.basename(fds.get(m.group(2), "?"))
                calls[(m.group(1), re.sub(r"\d{6,}", "N", name))].append(
                    float(m.group(3)) * 1e6)
    print(f"{arm}: {tps.group(1) if tps else '?'} tps over the run, "
          "traced for 8 of its 22 seconds")
    for (call, name), us in sorted(calls.items(), key=lambda kv: -sum(kv[1])):
        us.sort()
        print(f"   {call:16} {name:24} {len(us):6} calls  "
              f"mean {sum(us) / len(us):6.0f} us  "
              f"median {us[len(us) // 2]:6.0f} us")


def main():
    server = sys.argv[1]
    workload = sys.argv[2] if len(sys.argv) > 2 else "oltp_insert"
    with tempfile.TemporaryDirectory() as scratch:
        r = harness.Run("mem", "/var/tmp/mysup-bench", scratch, 1, 20, None,
                        server)
        for arm in ("innodb", "myrocks", "innodb", "myrocks"):
            trace(r, arm, workload, scratch)


if __name__ == "__main__":
    main()
