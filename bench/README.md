# The baseline harness

Loads sysbench's table into each engine on one server, measures the engines
under the same conditions, and writes one file of raw rows per run under
`runs/`. `python3 -m mysupbench report` draws the tables under
[`docs/tables/`](../docs/tables/) from those files, and
[`docs/baselines.md`](../docs/baselines.md) says what they show.

The definition of what is measured is [`mysupbench/plan.py`](mysupbench/plan.py):
the arms and every setting they change from the server's default, the two
conditions, the workloads. A change there is a change to the benchmark.

## Running it

```sh
sh bench/setup.sh                      # MariaDB, the MyRocks plugin, jemalloc, sysbench, perf
cd bench
python3 -m unittest discover tests     # the harness's own arithmetic, no server
python3 -m mysupbench run --condition mem   --arms blackhole,innodb \
        --suite micro --passes 3 --profile oltp_point_select,sum100,range100
python3 -m mysupbench run --condition mem   --arms innodb --suite read --passes 3 --reps 2
python3 -m mysupbench run --condition mem   --arms innodb --suite micro4 --reps 2
python3 -m mysupbench run --condition mem   --arms innodb --suite write --reps 2
python3 -m mysupbench run --condition limit --arms innodb --suite micro,read --reps 2 --warmup 30
python3 -m mysupbench run --condition limit --arms innodb --suite write --passes 1 --reps 3
python3 -m mysupbench report --server mariadb-10.11.14 > ../docs/tables/mariadb-10.11.14.md
```

The goal is against InnoDB, and `BASELINE_ARMS` in `plan.py` says so. The
arms `myrocks` and `myrocks-default` remain from when MyRocks was a second
rival, and the rows under `runs/` were taken with them beside InnoDB. Add
them to `--arms` to measure them again.

`--suite none --profile <workloads> --profile-threads 4` profiles without
measuring, at a thread count of its own.

It needs root: it drops the page cache, makes a cgroup, and attaches perf
to the server. It needs the cgroup v1 memory controller, which is where the
limit is set and the peak is read; on a cgroup v2 host it stops and says so.
Nothing else may be running. `--condition smoke` runs the whole path on
50,000 rows in a minute and proves only that the harness works.

Data directories go under `--workdir` (default `/var/tmp/mysup-bench`), about
15 GB for both conditions of one server. The block device under it is the
one whose reads are counted.

### Another server

MariaDB's and MySQL's server packages cannot both be installed. A second
server is its packages unpacked into a directory, and `--server` names it:

```sh
mkdir -p /opt/servers/percona-8.4.11
for deb in percona-server-server percona-server-rocksdb percona-server-common percona-server-client; do
    dpkg-deb -x ${deb}_8.4.11-12-1.noble_amd64.deb /opt/servers/percona-8.4.11
done
python3 -m mysupbench run --server /opt/servers/percona-8.4.11 --condition mem --arms blackhole,innodb,myrocks
python3 -m mysupbench report --server percona-8.4.11
```

Run this way so far: Percona Server 8.4.11-12 from `repo.percona.com/ps-84-lts`
and MariaDB 12.3.4 from `archive.mariadb.org/mariadb-12.3.4/repo/ubuntu`
(`mariadb-server`, `mariadb-server-core`, `mariadb-client`,
`mariadb-client-core`, `mariadb-plugin-rocksdb`). `plan.py` holds the few
settings the MySQL family names or ships differently.

### Debug symbols, for InnoDB's share

A profile knows MyRocks by the namespaces its plugin exports. InnoDB is
linked into the server, and MariaDB's server binary hides its names, so
InnoDB's share reads as zero until the debug file for that exact build is
where perf looks, `/usr/lib/debug/.build-id/`:

- Ubuntu's MariaDB: `mariadb-server-core-dbgsym`. The `ddebs.ubuntu.com`
  archive did not carry the 10.11.14 security build; its Launchpad build
  page did, as a `.ddeb` to install with `dpkg -i`.
- MariaDB's own packages: the `.ddeb` under `pool/main/debug/` of the same
  repository, unpacked and linked by build id.
- Percona's `mysqld` exports the names; nothing to install.

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
rule at the top of [`mysupbench/profile.py`](mysupbench/profile.py). The
rule finds an engine by the calls that enter it from a query's thread, and
by the names of the threads it runs for itself. A server that has not yet
run the workload runs it for the condition's warm-up first.

**Allocator.** An arm runs under the C library's allocator unless the
condition names another for it in `plan.py`. Under the memory limit MyRocks
runs with jemalloc; `docs/baselines.md` has why. The run checks the library
is mapped in the server it started and records it with the arm.

## What a row holds

One row per measured run. sysbench's own figures (transactions, queries,
latency, its per-second throughput), and beside them, read as counters
before and after:

| | from |
|---|---|
| server CPU, exact | the process's CPU-time clock, `clock_gettime` |
| server CPU by second | the same clock, read as each of sysbench's one-second reports arrives |
| user and kernel split | `utime`, `stime` in `/proc/<pid>/stat` |
| server CPU by thread name | `/proc/<pid>/task/*/stat`, over the threads that lived through the run |
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
from one second to the next; over an afternoon it also slowed for minutes at
a time. It has no hardware counters to count instructions instead. So:

- **Reads:** throughput and CPU per query are taken over every measured
  second of a cell, all runs and passes together, and the number is the edge
  of the best tenth, with the median beside it. A read-only workload on a
  warm cache does the same work every second, so what varies is the host,
  and the host only takes time away. Between passes ten minutes apart the
  median moved by up to 12% and the best tenth by half that or less.
- **Writes:** the cell's transactions over its seconds. An engine that
  stalls to flush or compact has spent that time.
- **Counts** (disk reads, their duration) are totals over the cell divided
  by its queries.
- Arms set side by side come from one run file. Rows from different files
  are never pooled, and two servers, each measured in its own run, are
  compared only to within a few percent.

That is why the goal is a ratio taken in one run and not a number to beat:
see [`docs/baselines.md`](../docs/baselines.md).

## Pitfalls

Beyond those in the brief:

- sysbench's `select_random_points` and `select_random_ranges` refuse more
  than one table, so every test here runs on one table, 16M rows under the
  limit where the brief had four of 4M.
- `/usr/bin/perf` on Ubuntu is a wrapper that refuses a kernel its package
  does not match. The binary under `/usr/lib/linux-tools/` runs anyway.
- In this VM `cpu-clock` samples taken with interrupts off land where they
  come back on: `_raw_spin_unlock_irqrestore` and `finish_task_switch` hold
  40% of a point select's samples. They are the socket and the scheduler.
- Percona Server will not start without a `secure-file-priv` directory; its
  default is one only its package creates.
- MyRocks under glibc's allocator is killed at the 1 GiB limit when four
  client threads follow one, whatever its cache size down to 448 MiB. The
  memory is in glibc's per-thread arenas, not in RocksDB's cache.
  `tools/rocksmem.py` shows it.
- A cgroup's peak includes page cache, so a peak at the limit is not a
  server in trouble. A kill is, and so is throughput falling to tens of
  transactions a second.
- The filesystem here is ext4 without a journal. An `fdatasync` after an
  append that grew the file still costs one more device write than one
  after an overwrite. `tools/logsync.py` measures it.
- `strace -p` stops the server at every system call, traced or not. Times
  it reports are longer than the same calls untraced.
- A prepared statement is optimized again at each execution, so the
  optimizer's calls into the engine (`records_in_range`) are part of every
  range query, not a one-time cost.

## Tools

Small programs behind single claims in `docs/baselines.md`, kept so the
claims can be checked:

| | |
|---|---|
| `tools/rowcompress.py` | how sysbench's rows compress under LZ4, Snappy and ZSTD |
| `tools/logsync.py` | what a durable log write costs by how the log file is laid out |
| `tools/tracesync.py` | each engine's write and sync calls per commit, under `strace` |
| `tools/rocksmem.py` | MyRocks' memory under the limit, by allocator and cache size |
| `tools/divelimit.py` | what InnoDB's row estimates cost it in `select_random_points`, by switching them off |

## Not done

- cgroup v2.
- A client on another host. With the client on the server's host, a quarter
  of a point select's wall time is the client's own CPU.
