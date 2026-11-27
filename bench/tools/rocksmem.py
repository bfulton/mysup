#!/usr/bin/env python3
"""Where MyRocks' memory is, under the 1 GiB limit, as tests follow one
another on one server.

    python3 bench/tools/rocksmem.py SERVER CACHE_MIB ALLOCATOR STEP...

    SERVER     a directory holding a server's packages unpacked
    ALLOCATOR  glibc, one-arena (glibc with MALLOC_ARENA_MAX=1) or jemalloc
    STEP       workload:threads:seconds, run in the order given

For example, the kill the brief met and what removes it:

    rocksmem.py /opt/servers/mariadb-12.3.4 640 glibc \
        oltp_point_select:1:45 oltp_point_select:4:60
    rocksmem.py /opt/servers/mariadb-12.3.4 640 jemalloc \
        oltp_point_select:1:45 oltp_point_select:4:60

It starts from the harness's loaded table for the limit condition
(`mysupbench run --condition limit --arms myrocks`), and every five seconds
prints the cgroup's memory beside RocksDB's own count of its block cache and
memtables and the process's anonymous memory. A step ends with whether the
server survived it.
"""
import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))
from mysupbench import plan, run as harness  # noqa: E402
from mysupbench.server import Instance, ServerDied, drop_page_cache  # noqa: E402

MIB = plan.MIB


def anonymous(pid):
    """MiB of anonymous memory resident, and how many regions over 4 MiB."""
    total = regions = 0
    name = None
    with open(f"/proc/{pid}/smaps") as f:
        for line in f:
            if re.match(r"^[0-9a-f]+-[0-9a-f]+ ", line):
                fields = line.split()
                name = fields[5] if len(fields) > 5 else ""
            elif line.startswith("Rss:") and name in ("", "[heap]"):
                kb = int(line.split()[1])
                total += kb
                regions += kb > 4096
    return total / 1024, regions


def sample(inst, label):
    cg = inst.cgroup.read()
    status = inst.sql_text("SHOW ENGINE ROCKSDB STATUS")

    def stat(name):
        m = re.search(name + r": (\d+)", status)
        return int(m.group(1)) / MIB if m else float("nan")
    anon, regions = anonymous(inst.pid)
    print(f"{label:>6}  cgroup {cg['usage'] / MIB:5.0f} MiB "
          f"(anonymous {cg['rss'] / MIB:5.0f}, page cache "
          f"{cg['cache'] / MIB:4.0f})  block cache "
          f"{stat('Cache Total'):4.0f}  memtables "
          f"{stat('MemTable Total'):4.0f}  process anonymous {anon:5.0f} "
          f"in {regions} regions", flush=True)


def main():
    server, cache, allocator = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    steps = [(w, int(t), int(s))
             for w, t, s in (a.split(":") for a in sys.argv[4:])]
    with tempfile.TemporaryDirectory() as scratch:
        r = harness.Run("limit", "/var/tmp/mysup-bench", scratch, 1, 20,
                        None, server)
    directory = os.path.join(r.workdir, r.tag, "limit-myrocks")
    inst = Instance(r.flavor, directory, "limit-myrocks",
                    preload=plan.JEMALLOC if allocator == "jemalloc" else None)
    kept = inst.cnf_text()
    inst.write_cnf(plan.arm_settings("myrocks", cache * MIB, r.flavor.kind))
    inst.restore()
    drop_page_cache()
    if allocator == "one-arena":
        os.environ["MALLOC_ARENA_MAX"] = "1"
    try:
        inst.start(limit=plan.CONDITIONS["limit"]["limit"])
        os.environ.pop("MALLOC_ARENA_MAX", None)
        if not inst.preloaded():
            sys.exit(f"the server started without {inst.preload}")
        print(f"block cache {cache} MiB, {allocator}")
        sample(inst, "start")
        for workload, threads, seconds in steps:
            sb = subprocess.Popen(
                r._cmd(inst, "myrocks", workload, threads, seconds, 7),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            t0 = time.time()
            alive = True
            while sb.poll() is None and alive:
                time.sleep(5)
                try:
                    sample(inst, f"{time.time() - t0:.0f}s")
                except (ServerDied, RuntimeError):
                    alive = False
            out = sb.communicate()[0]
            alive = alive and inst.proc is not None \
                and inst.proc.poll() is None
            tps = re.search(r"transactions:\s+\d+\s+\(([\d.]+) per sec", out)
            cg = inst.cgroup.read()
            print(f"{workload} x{threads}: "
                  f"{'survived' if alive else 'KILLED'}, "
                  f"{tps.group(1) if tps else '?'} tps, cgroup peak "
                  f"{cg['peak'] / MIB:.0f} MiB, oom kills {cg['oom_kill']}",
                  flush=True)
            if not alive:
                break
    finally:
        if inst.proc is not None and inst.proc.poll() is None:
            inst.stop()
        else:
            inst.proc = None
        inst.cgroup.destroy()
        with open(inst.cnf, "w") as f:
            f.write(kept)


if __name__ == "__main__":
    main()
