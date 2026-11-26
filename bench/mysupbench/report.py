"""Tables from the rows under bench/runs/.

A cell is (condition, arm, workload, threads). Where more than one run
file holds a cell, the newest file wins whole: rows from different runs
are never pooled, because they were not taken under the same hour's host.

How a cell's samples become one number:

    Reads. Throughput and CPU per query are taken over every measured
    second of the cell, all runs and passes together, and the number is
    the edge of the best tenth: the 90th percentile of throughput, the
    10th of CPU per query. The median stands beside it. A read-only
    workload on a warm cache does the same work every second, so what
    varies is the host, and the host only ever takes time away. Measured
    on the first rows: between passes ten minutes apart the median moved
    by up to 12% and the best tenth by half that or less.

    Writes. Throughput is the cell's transactions over its seconds, the
    plain mean. An engine that stalls to flush or compact has spent that
    time, and trimming its slow seconds would hide it.

    Counts (disk reads, their duration) are totals over the cell divided
    by its queries: they are sums, and a sum has no outliers to resist.
"""

import collections
import glob
import json
import os
import re
import statistics

from . import plan


def load(runs, conditions):
    docs = []
    for cond in conditions:
        for path in sorted(glob.glob(os.path.join(runs, cond, "*.json"))):
            with open(path) as f:
                doc = json.load(f)
            doc["_file"] = os.path.relpath(path, runs)
            doc["_tag"] = doc.get("server_tag") or _tag(doc["server"])
            docs.append(doc)
    docs.sort(key=lambda d: d["started"])
    return docs


def _tag(version_text):
    """The server tag of a row file written before rows carried one."""
    m = re.search(r"Ver (\d+\.\d+\.\d+)", version_text)
    family = ("percona" if "Percona" in version_text
              else "mariadb" if "MariaDB" in version_text else "mysql")
    return f"{family}-{m.group(1)}"


def quartiles(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    return (xs[n // 4], statistics.median(xs), xs[(3 * n) // 4])


def percentile(xs, p):
    """Nearest-rank percentile: the smallest value with at least p percent
    of the samples at or below it."""
    xs = sorted(xs)
    k = max(0, -(-len(xs) * p // 100) - 1)
    return xs[int(k)]


class Cell:
    def __init__(self, doc, rows):
        self.doc = doc
        self.failed = [r for r in rows if "failed" in r]
        self.rows = [r for r in rows if "failed" not in r]
        rs = self.rows
        self.n = len(rs)
        if not rs:
            return
        self.threads = rs[0]["threads"]
        q = sum(r["queries"] for r in rs)
        tx = sum(r["transactions"] for r in rs)
        secs = sum(r["seconds"] for r in rs)
        self.queries, self.transactions, self.seconds = q, tx, secs
        self.q_per_tx = q / tx
        tps, cpu = [], []
        for r in rs:
            tps += r["tps_by_second"]
            for c, qps, dt in zip(r.get("server_cpu_by_second", []),
                                  r["qps_by_second"], r.get("tick_s", [])):
                if qps > 0:
                    cpu.append(c / (qps * dt) * 1e6)
        self.tps = quartiles(tps)
        self.cpu_us = quartiles(cpu)
        self.tps_total = tx / secs
        self.cpu_us_total = sum(r["server"]["cpu_s"] for r in rs) / q * 1e6
        self.writes = plan.WORKLOADS[rs[0]["workload"]]["writes"]
        if self.writes or not cpu:
            self.rate, self.cpu = self.tps_total, self.cpu_us_total
        else:
            self.rate, self.cpu = percentile(tps, 90), percentile(cpu, 10)
        self.rate_by_pass = {}
        ut = sum(r["server"]["utime_s"] for r in rs)
        stt = sum(r["server"]["stime_s"] for r in rs)
        self.sys_share = stt / (ut + stt) if ut + stt else 0.0
        self.client_us = sum(r["client"]["utime_s"] + r["client"]["stime_s"]
                             for r in rs) / q * 1e6
        self.wall_us = secs * self.threads / q * 1e6
        self.reads = sum(r["block"]["read_ios"] for r in rs) / q
        self.read_kb = sum(r["block"]["read_sectors"] for r in rs) / q / 2
        self.read_wait_us = sum(r["block"]["read_ms"] for r in rs) / q * 1e3
        self.write_kb = sum(r["block"]["write_sectors"] for r in rs) / q / 2
        self.flushes = sum(r["block"]["flush_ios"] for r in rs) / tx
        self.peak = max(r["cgroup"]["peak"] for r in rs)
        self.p99_ms = statistics.median(r["lat_p99_ms"] for r in rs)
        self.errors = sum(r["ignored_errors"] for r in rs)
        self.passes = sorted({r.get("pass", 0) for r in rs})
        self.by_pass = {}
        for p in self.passes:
            mine = [r for r in rs if r.get("pass", 0) == p]
            xs = [x for r in mine for x in r["tps_by_second"]]
            self.by_pass[p] = statistics.median(xs)
            self.rate_by_pass[p] = (
                sum(r["transactions"] for r in mine)
                / sum(r["seconds"] for r in mine)
                if self.writes else percentile(xs, 90))


def cells_of(docs):
    """{(condition, arm, workload, threads): Cell}.

    Every arm of one (condition, workload, threads) is taken from one
    file, so that arms set side by side were measured in the same run:
    the file holding the most arms for it, and of those the newest.
    """
    per_doc = []
    for doc in docs:
        groups = collections.defaultdict(list)
        for r in doc["rows"]:
            groups[(doc["condition"], r["arm"], r["workload"],
                    r["threads"])].append(r)
        per_doc.append((doc, groups))
    best = {}
    for i, (doc, groups) in enumerate(per_doc):
        arms = collections.Counter((c, w, t) for (c, _a, w, t) in groups)
        for key, n in arms.items():
            if key not in best or (n, i) >= best[key][:2]:
                best[key] = (n, i)
    out = {}
    for i, (doc, groups) in enumerate(per_doc):
        for key, rows in groups.items():
            c, _a, w, t = key
            if best[(c, w, t)][1] == i:
                out[key] = Cell(doc, rows)
    return out


def profiles_of(docs, threads=1):
    out = {}
    for doc in docs:
        for p in doc.get("profiles", []):
            if p.get("threads", 1) == threads:
                out[(doc["condition"], p["arm"], p["workload"])] = p
    return out


def arms_of(docs):
    out = {}
    for doc in docs:
        for arm, info in doc["arms"].items():
            out[(doc["condition"], arm)] = info
    return out


# -- formatting ----------------------------------------------------------

def us(x):
    return f"{x:.1f} µs" if x < 1000 else f"{x / 1000:.2f} ms"


def med_iqr(q, fmt="{:.1f}"):
    lo, mid, hi = q
    return f"{fmt.format(mid)} ({fmt.format(lo)}–{fmt.format(hi)})"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


MICRO = [("oltp_point_select", "Point select by primary key"),
         ("sum100", "SUM over a 100-row range"),
         ("range100", "Return a 100-row range")]


def cpu_table(cells, cond):
    arms = [a for a in ("blackhole", "innodb", "myrocks", "myrocks-default")
            if (cond, a, "oltp_point_select", 1) in cells]
    head = ["Query"] + [plan.ARMS[a]["title"] for a in arms]
    extra = "blackhole" in arms and "innodb" in arms
    if extra:
        head += ["InnoDB over BLACKHOLE", "MyRocks ÷ InnoDB"]
    rows = []
    for w, title in MICRO:
        cs = {a: cells.get((cond, a, w, 1)) for a in arms}
        if not all(c and c.n for c in cs.values()):
            continue
        row = [title] + [f"{cs[a].cpu:.1f} ({cs[a].cpu_us[1]:.1f})"
                         for a in arms]
        if extra:
            b, i = cs["blackhole"].cpu, cs["innodb"].cpu
            row.append(f"{(i - b) / i:.0%}")
            row.append(f"{cs['myrocks'].cpu / i:.2f}×"
                       if "myrocks" in cs else "")
        rows.append(row)
    return table(head, rows)


def split_table(cells, cond, threads=1, workloads=None):
    """Where a query's time goes. The time is the client threads' seconds
    over the queries they finished: at one thread, the wall time from one
    query to the next."""
    workloads = workloads or MICRO
    rows = []
    for w, title in workloads:
        for a in ("blackhole", "innodb", "myrocks", "myrocks-default"):
            c = cells.get((cond, a, w, threads))
            if not c or not c.n:
                continue
            srv = c.cpu_us_total
            rows.append([
                title, plan.ARMS[a]["title"], us(c.wall_us),
                us(srv * (1 - c.sys_share)), us(srv * c.sys_share),
                us(c.client_us), us(c.read_wait_us),
                f"{c.reads:.2f}", f"{c.read_kb:.1f}",
                f"{c.peak / 2**20:.0f}"])
    if not rows:
        return None
    return table(["Query", "Arm", "Wall" if threads == 1 else "Thread time",
                  "Server user", "Server kernel",
                  "Client CPU", "Waiting on disk", "Disk reads",
                  "KiB read", "Peak MiB"], rows)


def write_table(cells, cond):
    """A write test's event: its time, the CPU in it, and the rest, which
    is the wait for the log to reach the device."""
    rows = []
    for (c, a, w, t), cell in sorted(
            cells.items(), key=lambda kv: (
                list(plan.WORKLOADS).index(kv[0][2]), kv[0][3],
                list(plan.ARMS).index(kv[0][1]))):
        if c != cond or not cell.n or not cell.writes:
            continue
        k = cell.q_per_tx
        cpu = (cell.cpu_us_total + cell.client_us) * k
        wall = cell.wall_us * k
        rows.append([
            w, t, plan.ARMS[a]["title"], f"{cell.tps_total:.0f}", us(wall),
            us(cell.cpu_us_total * k), us(cell.client_us * k),
            us(wall - cpu), f"{cell.flushes:.2f}",
            f"{cell.write_kb * k:.1f}", cell.errors])
    if not rows:
        return None
    return table(["Test", "Threads", "Arm", "tps", "Thread time per event",
                  "Server CPU", "Client CPU", "Neither (waiting)",
                  "Device flushes per event", "KiB written per event",
                  "Errors sysbench retried"], rows)


OWNERS = [("rocksdb_core", "RocksDB core"),
          ("rocksdb_txn", "RocksDB transaction utilities"),
          ("myrocks", "MyRocks"),
          ("innodb", "InnoDB")]


def profile_table(profiles, cond, arm):
    ws = [(w, t) for w, t in MICRO if (cond, arm, w) in profiles]
    if not ws:
        return None
    ps = [profiles[(cond, arm, w)] for w, _ in ws]
    head = [""] + [t for _, t in ws]
    rows = []
    shown = [(k, t) for k, t in OWNERS
             if any(p["owners"].get(k) for p in ps)]
    for key, title in shown:
        rows.append([title] + [
            f"{p['owners'].get(key, 0) / p['samples']:.1%}" for p in ps])
    if len(shown) > 1:
        rows.append(["Engine, all of it"] + [
            f"{1 - p['owners'].get('server', 0) / p['samples']:.1%}"
            for p in ps])
    rows.append(["Server outside the engine"] + [
        f"{p['owners'].get('server', 0) / p['samples']:.1%}" for p in ps])
    rows.append(["of which in the kernel"] + [
        f"{p['kernel'].get('server', 0) / p['samples']:.1%}" for p in ps])
    rows.append(["Samples"] + [str(p["samples"]) for p in ps])
    return table(head, rows)


def room_table(cells, profiles, cond, threads=1):
    """What is InnoDB's to lose: the part of an event's time that is
    InnoDB's CPU or its wait on the disk, and what throughput would gain
    if an engine did that part for nothing. A ceiling, not a forecast.

    An event's time is the client threads' seconds over the events they
    finished. At one thread that is the wall time between two events; at
    more it is the same quantity per thread, and on a host with no idle
    CPU it is the CPU and disk time an event costs, client included."""
    rows = []
    for w in plan.WORKLOADS:
        p = profiles.get((cond, "innodb", w))
        c = cells.get((cond, "innodb", w, threads))
        if not p or not c or not c.n or not p["owners"].get("innodb"):
            continue
        share = p["owners"]["innodb"] / p["samples"]
        engine = share * c.cpu_us_total
        wait = c.read_wait_us
        mine = engine + wait
        # A tenth more events in the same time is 1/11 less time each.
        need = (c.wall_us / 11) / mine
        rows.append([
            w, f"{share:.1%}", us(c.wall_us * c.q_per_tx),
            us(engine * c.q_per_tx), us(wait * c.q_per_tx),
            f"{mine / c.wall_us:.0%}",
            f"+{c.wall_us / (c.wall_us - mine) - 1:.0%}",
            f"+{c.wall_us / (c.wall_us - mine / 2) - 1:.0%}",
            f"{need:.0%} of it" if need < 1 else "more than all of it"])
    if not rows:
        return None
    return table(["Test", "InnoDB's share of server CPU", "Time per event",
                  "InnoDB CPU per event", "Waiting on disk per event",
                  "InnoDB's part of it", "Gain if that part were free",
                  "Gain if it were halved",
                  "What +10% takes away"], rows)


def profile_table_any(profiles, cond, arm):
    """profile_table over whichever workloads were profiled."""
    ws = [w for w in plan.WORKLOADS if (cond, arm, w) in profiles]
    if not ws:
        return None
    ps = [profiles[(cond, arm, w)] for w in ws]
    rows = []
    shown = [(k, t) for k, t in OWNERS
             if any(p["owners"].get(k) for p in ps)]
    for w, p in zip(ws, ps):
        n = p["samples"]
        rows.append([w] + [f"{p['owners'].get(k, 0) / n:.1%}"
                           for k, _ in shown]
                    + [f"{1 - p['owners'].get('server', 0) / n:.1%}",
                       f"{p['kernel'].get('server', 0) / n:.1%}", str(n)])
    return table(["Test"] + [t for _, t in shown]
                 + ["Engine, all of it", "Server's kernel time", "Samples"],
                 rows)


ENTRY = [("records_in_range", "Estimating rows for the optimizer"),
         ("index_read", "Finding the first row of a lookup or range"),
         ("general_fetch", "Stepping to the next row"),
         ("multi_range_read", "Ranges handed over as a batch"),
         ("build_template", "Preparing the row template")]


def entry_table(profiles, cond):
    """InnoDB's share of server CPU by the handler call it was reached
    through. InnoDB is known in a profile by its entry points, so the
    innermost one in a sample's stack is what the server had asked for."""
    rows = []
    for w in plan.WORKLOADS:
        p = profiles.get((cond, "innodb", w))
        if not p or not p["owners"].get("innodb"):
            continue
        n = p["samples"]
        frames = p["top_owner_frames"].get("innodb", [])
        row = [w, f"{p['owners']['innodb'] / n:.1%}"]
        seen = 0
        for key, _ in ENTRY:
            c = sum(k for name, k in frames if key in name.split("(")[0])
            seen += c
            row.append(f"{c / n:.1%}")
        row.append(f"{(p['owners']['innodb'] - seen) / n:.1%}")
        rows.append(row)
    if not rows:
        return None
    return table(["Test", "InnoDB, all"] + [t for _, t in ENTRY]
                 + ["Everything else"], rows)


def throughput_table(cells, cond):
    keys = sorted({(w, t) for (c, a, w, t) in cells if c == cond
                   and a in plan.BASELINE_ARMS},
                  key=lambda k: (list(plan.WORKLOADS).index(k[0]), k[1]))
    rows = []
    for w, t in keys:
        cs = {a: cells.get((cond, a, w, t)) for a in plan.BASELINE_ARMS}
        row = [w, t]
        best = 0.0
        for a in plan.BASELINE_ARMS:
            c = cs[a]
            if c and c.n:
                row.append(f"{c.rate:.0f} ({c.tps[1]:.0f})")
                best = max(best, c.rate)
            elif c and c.failed:
                row.append("server died")
            else:
                row.append("")
        row.append(f"{best * 1.10:.0f}" if best else "")
        rows.append(row)
    return table(["Test", "Threads"] +
                 [plan.ARMS[a]["title"] + " tps" for a in plan.BASELINE_ARMS]
                 + ["MySup's mark (1.10× the better)"], rows)


def detail_table(cells, cond):
    rows = []
    for (c, a, w, t), cell in sorted(
            cells.items(), key=lambda kv: (
                list(plan.WORKLOADS).index(kv[0][2]), kv[0][3],
                list(plan.ARMS).index(kv[0][1]))):
        if c != cond:
            continue
        if not cell.n:
            f = cell.failed[0]
            rows.append([w, t, plan.ARMS[a]["title"], "server died",
                         "", "", "", "", "", "",
                         f"{f['cgroup']['peak'] / 2**20:.0f}"])
            continue
        drift = ""
        if len(cell.by_pass) > 1:
            v = list(cell.rate_by_pass.values())
            drift = f"{(max(v) - min(v)) / statistics.median(v):.1%}"
        rows.append([
            w, t, plan.ARMS[a]["title"],
            f"{cell.rate:.0f}", f"{cell.q_per_tx:.0f}",
            us(cell.cpu * cell.q_per_tx),
            f"{cell.reads * cell.q_per_tx:.2f}",
            f"{cell.write_kb * cell.q_per_tx:.1f}",
            f"{cell.p99_ms:.2f}", drift, f"{cell.peak / 2**20:.0f}"])
    return table(["Test", "Threads", "Arm", "tps", "Queries per event",
                  "Server CPU per event", "Disk reads per event",
                  "KiB written per event", "p99 ms",
                  "Between passes", "Peak MiB"], rows)


def size_table(arms, cond):
    rows = []
    for a in plan.ARMS:
        info = arms.get((cond, a))
        if not info or a == "blackhole":
            continue
        load = info["load"]
        n = load["rows"]
        b = load["bytes"]["table"]
        algo = ""
        if "sst" in load:
            algo = ", ".join(f"{s['algo']} ×{s['files']}"
                             for s in load["sst"])
        rows.append([plan.ARMS[a]["title"], f"{b / 2**20:.0f}",
                     f"{b / n:.0f}", f"{b / n / plan.ROW_BYTES:.2f}",
                     algo, f"{load['insert_wall_s']:.0f}",
                     f"{load['settle_wall_s']:.0f}",
                     info.get("malloc", "the C library's")])
    return table(["Arm", "Table files, MiB", "Bytes per row",
                  "Per byte stored", "SST compression",
                  "Insert, s", "Settle, s", "Allocator"], rows)


def floors_table(docs, cond):
    rows = []
    for doc in docs:
        if doc["condition"] != cond:
            continue
        cpus = [f["cpu"]["iters_per_cpu_s"] / 1e6
                for f in doc["floors"].values()]
        reads = [f["disk_read_16k"]["mean_us"] for f in doc["floors"].values()]
        if cpus:
            rows.append([doc["_file"], doc["host"]["cpu_model"],
                         f"{min(cpus):.2f}–{max(cpus):.2f}",
                         f"{min(reads):.0f}–{max(reads):.0f}"])
    return table(["Run", "CPU", "CPU floor, M iterations/s",
                  "16 KiB direct read, µs"], rows)


def servers_table(docs, cond):
    """The one-statement workloads on every server measured, side by side.
    Each server's rows come from its own run, so two servers were not
    measured in the same hour; read differences of a few percent as
    nothing."""
    tags = []
    for d in docs:
        if d["condition"] == cond and d["_tag"] not in tags:
            tags.append(d["_tag"])
    if len(tags) < 2:
        return None
    rows = []
    for w, title in MICRO:
        for tag in tags:
            mine = [d for d in docs if d["_tag"] == tag]
            cells, profs = cells_of(mine), profiles_of(mine)
            cs = {a: cells.get((cond, a, w, 1))
                  for a in ("blackhole", "innodb", "myrocks")}
            if not all(c and c.n for c in cs.values()):
                continue

            def share(arm):
                p = profs.get((cond, arm, w))
                if not p or len(p["owners"]) < 2:
                    return ""
                return f"{1 - p['owners'].get('server', 0) / p['samples']:.1%}"
            rows.append([
                title, tag,
                f"{cs['blackhole'].cpu:.1f}", f"{cs['innodb'].cpu:.1f}",
                f"{cs['myrocks'].cpu:.1f}",
                f"{cs['myrocks'].cpu / cs['innodb'].cpu:.2f}×",
                f"{cs['innodb'].rate:.0f}", f"{cs['myrocks'].rate:.0f}",
                share("innodb"), share("myrocks")])
    return table(["Query", "Server", "BLACKHOLE µs", "InnoDB µs",
                  "MyRocks µs", "MyRocks ÷ InnoDB", "InnoDB qps",
                  "MyRocks qps", "InnoDB's share of its server's CPU",
                  "MyRocks' share"], rows)


TITLES = {"mem": "In memory", "limit": "Under the memory limit"}


def main_report(args):
    conds = args.conditions.split(",")
    every = load(args.runs, conds)
    docs = [d for d in every if d["_tag"] == args.server]
    cells = cells_of(docs)
    profiles = profiles_of(docs)
    arms = arms_of(docs)
    out = [f"Server: {args.server}.\n"]
    for cond in conds:
        t = servers_table(every, cond)
        if t:
            out.append(f"## {TITLES.get(cond, cond)}, every server "
                       "measured\n")
            out.append("Server CPU per query in microseconds and queries "
                       "per second at one client thread, the best tenth "
                       "of seconds. Each server's rows are from its own "
                       "run.\n")
            out.append(t + "\n")
    for cond in conds:
        if not any(d["condition"] == cond for d in docs):
            continue
        cd = plan.CONDITIONS[cond]
        lim = f"{cd['limit'] / 2**30:.0f} GiB" if cd["limit"] else "none"
        out.append(f"## {TITLES.get(cond, cond)}\n")
        out.append(f"{cd['rows']:,} rows, engine cache "
                   f"{cd['cache'] / 2**20:.0f} MiB, memory limit {lim}.\n")
        out.append("### Server CPU per query, one client thread\n")
        out.append("Microseconds: the best tenth of measured seconds, "
                   "with the median in brackets.\n")
        out.append(cpu_table(cells, cond) + "\n")
        t = split_table(cells, cond)
        if t:
            out.append("### Where a query's time goes, one client thread\n")
            out.append("Whole-run means, so the columns add up to the wall "
                       "time less what the client waited.\n")
            out.append(t + "\n")
        for arm in ("innodb", "myrocks", "myrocks-default"):
            t = profile_table(profiles, cond, arm)
            if t:
                out.append(f"### Share of server CPU by owner, "
                           f"{plan.ARMS[arm]['title']}\n")
                out.append(t + "\n")
        for arm in ("innodb", "myrocks"):
            extra = {k: v for k, v in profiles.items()
                     if k[2] not in dict(MICRO)}
            pt = profile_table_any(extra, cond, arm)
            if pt:
                out.append(f"### Share of server CPU by owner, "
                           f"{plan.ARMS[arm]['title']}, sysbench's tests\n")
                out.append(pt + "\n")
        t = entry_table(profiles, cond)
        if t:
            out.append("### What the server asked InnoDB for, one client "
                       "thread\n")
            out.append("Share of server CPU, by the handler call InnoDB "
                       "was entered through.\n")
            out.append(t + "\n")
        t = room_table(cells, profiles, cond)
        if t:
            out.append("### Room against InnoDB, one client thread\n")
            out.append("InnoDB's share is from the profile; the times are "
                       "whole-run means.\n")
            out.append(t + "\n")
        reads = [(w, w) for w, d in plan.WORKLOADS.items()
                 if not d["writes"]]
        for n in (4,):
            t = split_table(cells, cond, n, reads)
            if t:
                out.append(f"### Where a query's time goes, {n} client "
                           "threads\n")
                out.append("Per query, not per event. Thread time is the "
                           "client threads' seconds over the queries they "
                           "finished.\n")
                out.append(t + "\n")
            pn = profiles_of(docs, n)
            for arm in ("innodb", "myrocks"):
                pt = profile_table_any(pn, cond, arm)
                if pt:
                    out.append(f"### Share of server CPU by owner, "
                               f"{plan.ARMS[arm]['title']}, {n} client "
                               "threads\n")
                    out.append(pt + "\n")
            t = entry_table(pn, cond)
            if t:
                out.append(f"### What the server asked InnoDB for, {n} "
                           "client threads\n")
                out.append(t + "\n")
            t = room_table(cells, pn, cond, n)
            if t:
                out.append(f"### Room against InnoDB, {n} client threads\n")
                out.append(t + "\n")
        out.append("### sysbench throughput\n")
        out.append("Transactions per second. Reads: the best tenth of "
                   "measured seconds, median in brackets. Writes: the "
                   "whole run's mean, median second in brackets.\n")
        out.append(throughput_table(cells, cond) + "\n")
        t = write_table(cells, cond)
        if t:
            out.append("### Where a write's time goes\n")
            out.append("Whole-run means per event.\n")
            out.append(t + "\n")
        out.append("### Every cell\n")
        out.append(detail_table(cells, cond) + "\n")
        out.append("### Bytes on disk after the load\n")
        out.append(size_table(arms, cond) + "\n")
        out.append("### The host while it ran\n")
        out.append(floors_table(docs, cond) + "\n")
    print("\n".join(out))
