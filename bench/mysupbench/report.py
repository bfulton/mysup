"""Tables from the rows under bench/runs/.

A cell is (condition, arm, workload, threads). Where more than one run
file holds a cell, the newest file wins whole: rows from different runs
are never pooled, because they were not taken under the same hour's host.

How a cell's samples become one number:

    throughput and CPU per query are the median over every second of every
    measured run in the cell, with the quartiles beside it. The host's
    speed moves from second to second, mostly downward from its best, and
    the median of two hundred seconds does not follow a bad ten.

    counts (disk reads, their duration, queries) are totals over the cell
    divided by its total queries: they are sums, and a sum has no outliers
    to resist.
"""

import collections
import glob
import json
import os
import statistics

from . import plan


def load(runs, conditions):
    docs = []
    for cond in conditions:
        for path in sorted(glob.glob(os.path.join(runs, cond, "*.json"))):
            with open(path) as f:
                doc = json.load(f)
            doc["_file"] = os.path.relpath(path, runs)
            docs.append(doc)
    docs.sort(key=lambda d: d["started"])
    return docs


def quartiles(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    return (xs[n // 4], statistics.median(xs), xs[(3 * n) // 4])


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
            xs = [x for r in rs if r.get("pass", 0) == p
                  for x in r["tps_by_second"]]
            self.by_pass[p] = statistics.median(xs)


def cells_of(docs):
    """{(condition, arm, workload, threads): Cell}, newest file per cell."""
    out = {}
    for doc in docs:
        groups = collections.defaultdict(list)
        for r in doc["rows"]:
            groups[(doc["condition"], r["arm"], r["workload"],
                    r["threads"])].append(r)
        for key, rows in groups.items():
            out[key] = Cell(doc, rows)
    return out


def profiles_of(docs):
    out = {}
    for doc in docs:
        for p in doc.get("profiles", []):
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
        row = [title] + [med_iqr(cs[a].cpu_us) for a in arms]
        if extra:
            b, i = cs["blackhole"].cpu_us[1], cs["innodb"].cpu_us[1]
            row.append(f"{(i - b) / i:.0%}")
            row.append(f"{cs['myrocks'].cpu_us[1] / i:.2f}×"
                       if "myrocks" in cs else "")
        rows.append(row)
    return table(head, rows)


def split_table(cells, cond):
    """Where a query's wall time goes at one client thread."""
    rows = []
    for w, title in MICRO:
        for a in ("blackhole", "innodb", "myrocks", "myrocks-default"):
            c = cells.get((cond, a, w, 1))
            if not c or not c.n:
                continue
            srv = c.cpu_us_total
            rows.append([
                title, plan.ARMS[a]["title"], us(c.wall_us),
                us(srv * (1 - c.sys_share)), us(srv * c.sys_share),
                us(c.client_us), us(c.read_wait_us),
                f"{c.reads:.2f}", f"{c.read_kb:.1f}",
                f"{c.peak / 2**20:.0f}"])
    return table(["Query", "Arm", "Wall", "Server user", "Server kernel",
                  "Client CPU", "Waiting on disk", "Disk reads",
                  "KiB read", "Peak MiB"], rows)


OWNERS = [("rocksdb_core", "RocksDB core"),
          ("rocksdb_txn", "RocksDB transaction utilities"),
          ("myrocks", "MyRocks")]


def profile_table(profiles, cond, arm):
    ws = [(w, t) for w, t in MICRO if (cond, arm, w) in profiles]
    if not ws:
        return None
    head = [""] + [t for _, t in ws]
    rows = []
    for key, title in OWNERS:
        rows.append([title] + [
            f"{profiles[(cond, arm, w)]['owners'].get(key, 0) / profiles[(cond, arm, w)]['samples']:.1%}"
            for w, _ in ws])
    rows.append(["All three"] + [
        f"{1 - profiles[(cond, arm, w)]['owners'].get('server', 0) / profiles[(cond, arm, w)]['samples']:.1%}"
        for w, _ in ws])
    rows.append(["Samples"] + [str(profiles[(cond, arm, w)]["samples"])
                               for w, _ in ws])
    return table(head, rows)


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
                row.append(med_iqr(c.tps, "{:.0f}"))
                best = max(best, c.tps[1])
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
            v = list(cell.by_pass.values())
            drift = f"{(max(v) - min(v)) / statistics.median(v):.1%}"
        rows.append([
            w, t, plan.ARMS[a]["title"],
            f"{cell.tps[1]:.0f}", f"{cell.q_per_tx:.0f}",
            us(cell.cpu_us[1] * cell.q_per_tx),
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
                     f"{load['settle_wall_s']:.0f}"])
    return table(["Arm", "Table files, MiB", "Bytes per row",
                  "Per byte stored", "SST compression",
                  "Insert, s", "Settle, s"], rows)


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


TITLES = {"mem": "In memory", "limit": "Under the memory limit"}


def main_report(args):
    conds = args.conditions.split(",")
    docs = load(args.runs, conds)
    cells = cells_of(docs)
    profiles = profiles_of(docs)
    arms = arms_of(docs)
    out = []
    for cond in conds:
        if not any(d["condition"] == cond for d in docs):
            continue
        cd = plan.CONDITIONS[cond]
        lim = f"{cd['limit'] / 2**30:.0f} GiB" if cd["limit"] else "none"
        out.append(f"## {TITLES.get(cond, cond)}\n")
        out.append(f"{cd['rows']:,} rows, engine cache "
                   f"{cd['cache'] / 2**20:.0f} MiB, memory limit {lim}.\n")
        out.append("### Server CPU per query, one client thread\n")
        out.append("Median over every measured second, quartiles in "
                   "brackets.\n")
        out.append(cpu_table(cells, cond) + "\n")
        out.append("### Where a query's time goes, one client thread\n")
        out.append(split_table(cells, cond) + "\n")
        for arm in ("myrocks", "myrocks-default"):
            t = profile_table(profiles, cond, arm)
            if t:
                out.append(f"### Share of server CPU by owner, "
                           f"{plan.ARMS[arm]['title']}\n")
                out.append(t + "\n")
        out.append("### sysbench throughput\n")
        out.append("Transactions per second: median over every measured "
                   "second, quartiles in brackets.\n")
        out.append(throughput_table(cells, cond) + "\n")
        out.append("### Every cell\n")
        out.append(detail_table(cells, cond) + "\n")
        out.append("### Bytes on disk after the load\n")
        out.append(size_table(arms, cond) + "\n")
        out.append("### The host while it ran\n")
        out.append(floors_table(docs, cond) + "\n")
    print("\n".join(out))
