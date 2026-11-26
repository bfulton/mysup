# The baseline harness

Loads sysbench's table into each engine on one MariaDB server, measures the
engines under the same conditions, and writes one file of raw rows per run
under `runs/`. `python3 -m mysupbench report` draws every table in
[`docs/baselines.md`](../docs/baselines.md) from those files.

The definition of what is measured is [`mysupbench/plan.py`](mysupbench/plan.py):
the arms and every setting they change from the server's default, the two
conditions, the workloads. A change there is a change to the benchmark.

## Running it

```sh
sh bench/setup.sh                      # MariaDB, the MyRocks plugin, sysbench, perf
cd bench
python3 -m mysupbench run --condition mem   --arms blackhole,innodb,myrocks,myrocks-default \
        --suite micro --passes 3 --profile oltp_point_select,sum100
python3 -m mysupbench run --condition mem   --arms innodb,myrocks --suite read,write
python3 -m mysupbench run --condition limit --arms innodb,myrocks --suite micro,read
python3 -m mysupbench report
```

It needs root: it drops the page cache, makes a cgroup, and attaches perf
to the server. It needs the cgroup v1 memory controller, which is where the
limit is set and the peak is read; on a cgroup v2 host it stops and says so.
Nothing else may be running. `--condition smoke` runs the whole path on
50,000 rows in a minute and proves only that the harness works.

Data directories go under `--workdir` (default `/var/tmp/mysup-bench`), about
15 GB for both conditions. The block device under it is the one whose reads
are counted.

## What a run does

**Load, once per arm and condition.** A fresh data directory. sysbench's own
`prepare` with one thread and a fixed seed, so every arm holds the same rows.
Then the engine's deferred work is brought to rest: RocksDB's memtable is
flushed and the column family compacted into one level, InnoDB is shut down
with `innodb_fast_shutdown=0`. `ANALYZE TABLE`. The stopped data directory is
kept as the arm's snapshot.

One level is the best shape a RocksDB tree has for reads, and it puts every
row under the last level's compression. Both favour MyRocks; a baseline
should.

**Measure.** The snapshot is copied back, the page cache dropped, and the
server started inside a memory cgroup of its own, under the condition's
limit. Where the table fits in the cache it is read through once on each
index. Then, per workload: a warm-up run of the workload itself, and `--reps`
measured runs of `--time` seconds. A workload that writes starts from the
snapshot again, so each write test sees the table as loaded.

**Passes.** The arms are gone round `--passes` times, one server running at
a time. The host's speed drifts, and a pass apart is how the rows show it.

**Profile.** After the last pass, `perf record -e cpu-clock -g` on the server
for 20 seconds of the workload, and every sample given to one owner by the
rule at the top of [`mysupbench/profile.py`](mysupbench/profile.py).

## What a row holds

One row per measured run. sysbench's own figures (transactions, queries,
latency, its per-second throughput), and beside them, read as counters
before and after:

| | from |
|---|---|
| server CPU, exact | the process's CPU-time clock, `clock_gettime` |
| server CPU by second | the same clock, read as each of sysbench's one-second reports arrives |
| user and kernel split | `utime`, `stime` in `/proc/<pid>/stat` |
| client CPU | sysbench's own `rusage` |
| disk reads, sectors, time in reads | `/sys/block/<dev>/stat` |
| bytes the server read and wrote | `/proc/<pid>/io` |
| memory peak, OOM kills | the cgroup's `memory.max_usage_in_bytes`, `memory.oom_control` |
| engine counters | `SHOW GLOBAL STATUS`, the difference across the run |

The file also holds each arm's `my.cnf` as written, its InnoDB and RocksDB
variables as the server reports them, the plan `EXPLAIN` gives for each
query shape, what the load left on disk, and two floors taken before each
arm: a fixed single-thread loop timed, and 2,000 random 16 KiB direct reads
of a file on the same device.

A server that dies in a run, the cgroup's kill included, is a row saying so
with the cgroup's counters, and the run goes on from the snapshot.

## How samples become a number

The host is a virtual machine among others. A fixed loop on one idle vCPU ran
between 7.1 and 10.8 million iterations a second over 75 seconds, changing
from one second to the next, and it has no hardware counters to count
instructions instead. So:

- Throughput and CPU per query are the **median over every measured second**
  of a cell, all runs and passes together, with the quartiles beside it.
- Counts (disk reads, their duration) are totals over the cell divided by
  its queries.
- Rows from different run files are never pooled. Two engines are compared
  only within one file, which is one afternoon of one host.

That last rule is why the goal is a ratio taken in one run and not a number
to beat: see [`docs/baselines.md`](../docs/baselines.md).

## Not done

- Only MariaDB has been run, so only MariaDB is implemented. The seam for
  another server is `server.py`.
- cgroup v2.
- A client on another host. With the client on the server's host, a third of
  a point select's wall time is the client's own CPU.
