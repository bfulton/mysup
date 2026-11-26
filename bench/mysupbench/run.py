"""Load an arm, then measure it: the order of operations.

Load (`prepare`):
    a fresh data directory; sysbench's own prepare, one thread, fixed
    seed, so every arm holds the same rows; the engine's deferred work
    brought to rest (RocksDB flushed and compacted to one level, InnoDB
    shut down slowly); statistics analysed; the stopped data directory
    kept as the arm's snapshot.

Measure (`measure`):
    the snapshot copied back; the page cache dropped; the server started
    inside its cgroup, under the condition's limit; then per workload a
    warm-up run and `reps` measured runs. A workload that writes starts
    from the snapshot again, so each write test sees the loaded table and
    not what the test before it left.
"""

import datetime
import json
import os
import platform
import subprocess
import sys
import time

from . import plan, probes, profile, sysbench
from .server import (Instance, MariaDB, ServerDied, drop_page_cache,
                     tree_bytes)

LOAD_SEED = 20261126


def log(msg):
    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def git_sha():
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run(["git", "-C", here, "rev-parse", "--short", "HEAD"],
                       capture_output=True, text=True)
    sha = r.stdout.strip() if r.returncode == 0 else "uncommitted"
    d = subprocess.run(["git", "-C", here, "status", "--porcelain", "--",
                        here], capture_output=True, text=True)
    return sha + ("-dirty" if d.stdout.strip() else "")


def host_meta(workdir):
    cpu = "unknown"
    with open("/proc/cpuinfo") as f:
        for line in f:
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    with open("/proc/meminfo") as f:
        mem_kb = int(f.readline().split()[1])
    osname = ""
    with open("/etc/os-release") as f:
        for line in f:
            if line.startswith("PRETTY_NAME="):
                osname = line.split("=", 1)[1].strip().strip('"')
    dev = probes.block_device_of(workdir)
    return {
        "cpu_model": cpu,
        "vcpus": os.cpu_count(),
        "mem_bytes": mem_kb * 1024,
        "kernel": platform.release(),
        "os": osname,
        "block_device": dev,
    }


class Run:
    """One invocation: one condition, some arms, one file of rows."""

    def __init__(self, condition, workdir, outdir, reps, seconds,
                 warmup=None):
        self.condition = condition
        self.cond = dict(plan.CONDITIONS[condition])
        if warmup is not None:
            self.cond["warmup"] = warmup
        self.workdir = workdir
        os.makedirs(workdir, exist_ok=True)
        self.reps = reps
        self.seconds = seconds
        self.flavor = MariaDB()
        self.dev = probes.block_device_of(workdir)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ")
        sha = git_sha()
        os.makedirs(os.path.join(outdir, condition), exist_ok=True)
        self.path = os.path.join(outdir, condition, f"{stamp}-{sha}.json")
        self.doc = {
            "condition": condition,
            "condition_def": self.cond,
            "started": stamp,
            "sha": sha,
            "reps": reps,
            "seconds": seconds,
            "host": host_meta(workdir),
            "server": self.flavor.version(),
            "sysbench": sysbench.version(),
            "floors": {},
            "arms": {},
            "rows": [],
            "profiles": [],
        }

    def save(self, done=False):
        """Write the rows so far. Until the run is done they live beside
        their final name as `.partial`, which nothing reads and git
        ignores: a file under runs/ is a run that finished."""
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.doc, f, indent=1, sort_keys=True)
            f.write("\n")
        os.replace(tmp, self.path if done else self.path + ".partial")
        if done and os.path.exists(self.path + ".partial"):
            os.unlink(self.path + ".partial")

    def floors(self, label):
        """How fast the host's CPU and disk are at this moment."""
        drop_page_cache()
        self.doc["floors"][label] = {
            "cpu": probes.cpu_floor(),
            "disk_read_16k": probes.disk_read_floor(self.workdir),
        }
        self.save()

    def instance(self, arm):
        d = os.path.join(self.workdir, f"{self.condition}-{arm}")
        os.makedirs(d, exist_ok=True)
        inst = Instance(self.flavor, d, f"{self.condition}-{arm}")
        inst.write_cnf(plan.arm_settings(arm, self.cond["cache"]))
        return inst

    # -- load -----------------------------------------------------------

    def prepare(self, arm, force=False):
        inst = self.instance(arm)
        marker = os.path.join(inst.dir, "load.json")
        if inst.has_snapshot() and os.path.exists(marker) and not force:
            with open(marker) as f:
                load = json.load(f)
            if load.get("cnf") == inst.cnf_text() and \
                    load.get("rows") == self.cond["rows"]:
                log(f"{arm}: loaded already")
                return inst, load
        engine = plan.ARMS[arm]["engine"]
        rows = self.cond["rows"]
        log(f"{arm}: loading {rows} rows")
        inst.init()
        inst.start()
        try:
            inst.sql("CREATE DATABASE sbtest")
            pid = inst.pid
            c0 = probes.proc_cpu_ns(pid)
            cmd = sysbench.command(
                inst, "oltp_read_write", engine, rows,
                ["--threads=1", f"--rand-seed={LOAD_SEED}", "prepare"])
            _out, _client, wall = sysbench.run(cmd)
            t0 = time.monotonic()
            if engine == "rocksdb":
                inst.sql("SET GLOBAL rocksdb_force_flush_memtable_now=1")
                inst.sql("SET GLOBAL rocksdb_compact_cf='default'")
            inst.sql("ANALYZE TABLE sbtest1", db="sbtest")
            settle = time.monotonic() - t0
            load = {
                "rows": rows,
                "insert_wall_s": wall,
                "settle_wall_s": settle,
                "server_cpu_s": (probes.proc_cpu_ns(pid) - c0) / 1e9,
                "count": int(inst.sql("SELECT COUNT(*) FROM sbtest1",
                                      db="sbtest")[0][0])
                if engine != "blackhole" else 0,
            }
            if engine == "rocksdb":
                load["sst"] = [
                    dict(zip(("files", "algo", "entries", "raw_key",
                              "raw_value", "data_block", "index_block",
                              "filter_block"), r))
                    for r in inst.sql(
                        "SELECT COUNT(*), COMPRESSION_ALGO, SUM(ENTRIES), "
                        "SUM(RAW_KEY_SIZE), SUM(RAW_VALUE_SIZE), "
                        "SUM(DATA_BLOCK_SIZE), SUM(INDEX_BLOCK_SIZE), "
                        "SUM(FILTER_BLOCK_SIZE) FROM "
                        "information_schema.ROCKSDB_SST_PROPS "
                        "WHERE COLUMN_FAMILY=0 GROUP BY COMPRESSION_ALGO")]
                load["levels"] = _rocksdb_levels(inst)
        finally:
            inst.stop(slow=True)
        load["bytes"] = _sizes(inst.datadir, engine)
        load["cnf"] = inst.cnf_text()
        inst.snapshot()
        with open(marker, "w") as f:
            json.dump(load, f, indent=1)
        log(f"{arm}: loaded in {load['insert_wall_s']:.0f} s, "
            f"settled in {load['settle_wall_s']:.0f} s, "
            f"{load['bytes']['table'] / 1e6:.0f} MB of table files")
        return inst, load

    # -- measure --------------------------------------------------------

    def _start(self, inst, arm, restore):
        if restore and plan.ARMS[arm]["engine"] != "blackhole":
            inst.restore()
        drop_page_cache()
        inst.start(limit=self.cond["limit"])
        if self.cond["preload"] and plan.ARMS[arm]["engine"] != "blackhole":
            inst.sql("SELECT SUM(LENGTH(c)) FROM sbtest1 "
                     "FORCE INDEX (PRIMARY)", db="sbtest")
            inst.sql("SELECT COUNT(k) FROM sbtest1 FORCE INDEX (k_1)",
                     db="sbtest")

    def _cmd(self, inst, arm, workload, threads, seconds, seed):
        w = plan.WORKLOADS[workload]
        return sysbench.command(
            inst, w["test"], plan.ARMS[arm]["engine"], self.cond["rows"],
            w["opts"] + [f"--threads={threads}", f"--time={seconds}",
                         "--events=0", "--report-interval=1",
                         "--percentile=99", f"--rand-seed={seed}", "run"])

    def measure(self, arm, cells, profile_cells=(), pass_no=0):
        self.pass_no = pass_no
        inst, load = self.prepare(arm)
        engine = plan.ARMS[arm]["engine"]
        if engine == "blackhole":
            cells = [c for c in cells if c[0] in plan.BLACKHOLE_WORKLOADS]
            profile_cells = [c for c in profile_cells
                             if c in plan.BLACKHOLE_WORKLOADS]
        info = {"load": load, "cnf": inst.cnf_text()}
        self.doc["arms"][arm] = info
        self.floors(f"pass {pass_no} before {arm}")
        self._start(inst, arm, restore=True)
        try:
            info["variables"] = _variables(inst)
            info["explain"] = {
                k: inst.sql_text("EXPLAIN " + q, db="sbtest")
                for k, q in plan.EXPLAINS.items()}
            self.save()
            fresh = True
            for workload, threads in cells:
                writes = plan.WORKLOADS[workload]["writes"]
                if writes and not fresh:
                    inst.stop()
                    self._start(inst, arm, restore=True)
                fresh = not writes
                if not self._cell(inst, arm, workload, threads):
                    # The server is gone. Say so in the rows and go on
                    # with the next cell from the snapshot.
                    inst.kill()
                    self._start(inst, arm, restore=True)
                    fresh = True
            for workload in profile_cells:
                if plan.WORKLOADS[workload]["writes"] and not fresh:
                    inst.stop()
                    self._start(inst, arm, restore=True)
                fresh = not plan.WORKLOADS[workload]["writes"]
                self._profile(inst, arm, workload)
        except BaseException:
            inst.kill()
            raise
        inst.stop()
        inst.cgroup.destroy()

    def _cell(self, inst, arm, workload, threads):
        tag = f"{self.condition} {arm} {workload} x{threads}"
        ident = dict(arm=arm, workload=workload, threads=threads)
        ident["pass"] = self.pass_no
        warm = self.cond["warmup"]
        for rep in range(-1 if warm else 0, self.reps):
            # rep -1 is the warm-up: the same command, not kept.
            secs = warm if rep < 0 else self.seconds
            seed = 100 * (self.pass_no + 1) + rep
            cmd = self._cmd(inst, arm, workload, threads, secs, seed)
            try:
                if rep < 0:
                    sysbench.run(cmd)
                    inst.check()
                    continue
                row = sysbench.measured(inst, self.dev, cmd)
            except (ServerDied, sysbench.SysbenchFailed) as e:
                died = inst.proc is None or inst.proc.poll() is not None
                if not died:
                    raise
                cg = inst.cgroup.read()
                self.doc["rows"].append(dict(
                    ident, rep=rep, failed="server died",
                    cgroup=cg, detail=str(e)[-600:]))
                self.save()
                log(f"{tag} rep {rep}: SERVER DIED, cgroup oom_kill="
                    f"{cg['oom_kill']} failcnt={cg['failcnt']} "
                    f"peak {cg['peak'] / 2**20:.0f} MiB")
                return False
            row.update(ident, rep=rep)
            self.doc["rows"].append(row)
            self.save()
            q = row["queries"]
            log(f"{tag} rep {rep}: {row['transactions'] / row['seconds']:.0f}"
                f" tps, {row['server']['cpu_s'] / q * 1e6:.1f} us cpu/query,"
                f" {row['block']['read_ios'] / q:.2f} reads/query,"
                f" peak {row['cgroup']['peak'] / 2**20:.0f} MiB")
        return True

    def _profile(self, inst, arm, workload, seconds=20):
        tag = f"{self.condition} {arm} {workload}"
        data = os.path.join(inst.dir, f"perf-{workload}.data")
        cmd = self._cmd(inst, arm, workload, 1, seconds + 4, 7)
        sb = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        try:
            time.sleep(2)
            pid = inst.pid
            c0 = probes.proc_cpu_ns(pid)
            b0 = probes.block_stat(self.dev)
            w0 = time.monotonic()
            profile.record(pid, seconds, data)
            wall = time.monotonic() - w0
            cpu = (probes.proc_cpu_ns(pid) - c0) / 1e9
            blk = probes.delta(probes.block_stat(self.dev), b0)
        finally:
            out = sb.communicate()[0]
        res = profile.attribute(profile.script(data))
        res.update(arm=arm, workload=workload, threads=1,
                   **{"pass": self.pass_no},
                   window_wall_s=wall, window_server_cpu_s=cpu,
                   window_read_ms=blk["read_ms"],
                   window_read_ios=blk["read_ios"],
                   sysbench=sysbench.parse(out))
        self.doc["profiles"].append(res)
        self.save()
        os.unlink(data)
        n = res["samples"] or 1
        shares = ", ".join(f"{k} {v / n:.1%}"
                           for k, v in sorted(res["owners"].items()))
        log(f"{tag} profile: {res['samples']} samples "
            f"({res['rooted'] / n:.0%} unwound to the root): {shares}")


def _variables(inst):
    keep = ("innodb_", "rocksdb_")
    names = {"version", "version_comment", "character_set_server",
             "collation_server", "query_cache_type", "query_cache_size",
             "performance_schema", "thread_handling", "log_bin",
             "sync_binlog", "tx_isolation", "max_connections",
             "table_open_cache", "optimizer_switch", "join_cache_level"}
    return {r[0]: (r[1] if len(r) > 1 else "")
            for r in inst.sql("SHOW GLOBAL VARIABLES")
            if r and (r[0].startswith(keep) or r[0] in names)}


def _rocksdb_levels(inst):
    """The default column family's level table from the engine's status:
    how many files and bytes sit at each level after the load settled."""
    text = inst.sql_text("SHOW ENGINE ROCKSDB STATUS")
    text = text.replace("\\n", "\n")
    out = []
    grab = False
    for line in text.splitlines():
        if line.startswith("** Compaction Stats [default] **"):
            grab = True
            continue
        if grab:
            parts = line.split()
            if len(parts) > 3 and "/" in parts[1] and \
                    (parts[0] == "Sum" or parts[0][1:].isdigit()):
                out.append({"level": parts[0],
                            "files": int(parts[1].split("/")[0]),
                            "size": " ".join(parts[2:4])})
            elif parts and parts[0] in ("Int", "**"):
                break
    return out


def _sizes(datadir, engine):
    if engine == "rocksdb":
        table = tree_bytes(datadir, lambda p: p.startswith("#rocksdb")
                           and p.endswith(".sst"))
    elif engine == "innodb":
        table = tree_bytes(datadir, lambda p: p.startswith("sbtest")
                           and p.endswith(".ibd"))
    else:
        table = 0
    return {"table": table, "datadir": tree_bytes(datadir)}


def main_run(args):
    cells = []
    for suite in args.suite.split(","):
        for cell in plan.SUITES[suite]:
            if cell not in cells:
                cells.append(cell)
    if args.threads:
        want = {int(t) for t in args.threads.split(",")}
        cells = [c for c in cells if c[1] in want]
    if args.workloads:
        want = set(args.workloads.split(","))
        cells = [c for c in cells if c[0] in want]
    prof = [w for w in (args.profile.split(",") if args.profile else [])]
    for w in prof:
        if w not in plan.WORKLOADS:
            sys.exit(f"unknown workload {w}")
    run = Run(args.condition, args.workdir, args.out, args.reps, args.time,
              args.warmup)
    log(f"writing {run.path}")
    for arm in args.arms.split(","):
        if arm not in plan.ARMS:
            sys.exit(f"unknown arm {arm}")
    run.doc["passes"] = args.passes
    for pass_no in range(args.passes):
        last = pass_no == args.passes - 1
        for arm in args.arms.split(","):
            run.measure(arm, cells, prof if last else (), pass_no)
    run.floors("end")
    run.save(done=True)
    log(f"done: {run.path}")
