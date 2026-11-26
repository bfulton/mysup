# MySup: project brief

Date: 2026-11-26. Status: proposal, nothing built.

## What it is

MySup is a MySQL storage engine built on supdb, in the way MyRocks is built
on RocksDB. It is a separate project from supdb, with its own post.

**Goal:** a double-digit throughput improvement on an existing benchmark
(sysbench), against both InnoDB and MyRocks, on the same server and host.

## Decided (Bright, 2026-11-26)

- A new project and a new post, not part of supdb.
- A native engine written for supdb. Not a RocksDB-compatible layer under
  MyRocks.
- Ideas from RocksDB and MyRocks are fine. No copied implementation.
- Benchmark against both MyRocks and InnoDB.
- Compare compressed against compressed.

## Open decisions

- Name: MySup or Mysup. (Recommended: MySup, after MyISAM and MyRocks.)
- Server: MySQL (bigger name) or MariaDB (friendlier to third-party engines,
  ships MyRocks as a loadable plugin).
- Whether supdb grows a mode that stores only its compact form.
- One supdb store for all tables, or one per table.

## Why a native engine and not a compatibility layer

Measured on MyRocks in memory, share of server CPU:

| | Point select | SUM over 100 rows |
|---|---|---|
| RocksDB core (all a layer could replace) | 15% | 30% |
| RocksDB transaction wrapper (a layer keeps it) | 3% | 4% |
| MyRocks glue (a layer keeps it) | 6% | 12% |
| Everything a native engine can redesign | 24% | 46% |

- MyRocks already trails InnoDB (1.16x its CPU on point selects, 1.44x on
  ranges), so a layer's ceiling is parity with InnoDB.
- A C++ RocksDB emulation has no second customer. TiKV and FoundationDB each
  have their own seam.
- A layer cannot use anything supdb does differently.

## What the engine competes over

Server CPU per query, one client thread, table in memory. BLACKHOLE is the
engine that does no lookup and returns no row, so the gap to it is a ceiling.

| Query | BLACKHOLE | InnoDB | MyRocks | InnoDB's engine-and-row share |
|---|---|---|---|---|
| Point select by primary key | 36.5 µs | 43.2 µs | 50.1 µs | 16% |
| SUM over a 100-row range | 41.7 µs | 84.3 µs | 121.7 µs | 51% |
| Return a 100-row range | 38.8 µs | 87.9 µs | 129.8 µs | 56% |

(MariaDB 10.11.14. MySQL 8.0.46 gave 18% and 48% for InnoDB on the first two.)

With data three times memory (16M rows, server held to 1 GiB, 640 MB cache,
direct I/O, one thread, uniform keys):

| | Wall per query | Disk reads per query | Waiting on disk |
|---|---|---|---|
| InnoDB point select | 114 µs | 0.84 | 40 µs |
| MyRocks point select | 119 µs | 0.80 | 35 µs |
| InnoDB SUM over 100 rows | 255 µs | 2.0 | 103 µs |
| MyRocks SUM over 100 rows | 416 µs | 3.2 | 164 µs |

- RocksDB's core is 53% of a MyRocks point select's time there and 69% of a
  range's. About four fifths of that is the disk read itself.
- MyRocks with four client threads passed the 1 GiB limit and was killed.
- MyRocks ran uncompressed (MariaDB's default). That is not how its users
  run it.

What this means for the goal:

- In memory, point selects leave little room: about 16% against InnoDB.
- The headline will come from range scans, secondary-index lookups and data
  larger than memory.
- sysbench's read-only test is 10 point selects and 4 range queries per
  transaction. Roughly a quarter to a third of it is the engine's (estimate:
  two of the four range types were measured). A 10% win against InnoDB there
  means doing that part about 1.5 times cheaper than InnoDB.

## What supdb brings

- Against tuned RocksDB on its own suite: 3.8x in memory, 7x to 8x under a
  memory limit, reads 14x to 15x under the limit.
- At 10M keys under 1 GiB it reads 74 bytes from disk per point read against
  RocksDB's 2,517, because its compact form fits in memory.
- Bytes on disk per byte stored at 10M keys: supdb raw 1.30, compact form
  about 0.64, both together 1.94. RocksDB 1.00, with LZ4 0.83. supdb keeps
  both forms today.
- A C boundary that lends values costs a point read nothing measurable.
  Copying a 100-byte value adds about a third.
- MIT licensed, so it can link into a GPL engine.

## Design

**Language split**

- C++ for everything that touches MySQL's objects: the handler subclass,
  registration, row and key encoding, DDL hooks, system variables, optimizer
  statistics.
- Rust for everything else: supdb, the transaction layer (row locks, write
  buffer, savepoints, prepared state), cursors.
- A C ABI between them that passes only bytes. Lend, do not copy. One call
  per operation. Scans return batches. No Rust panic crosses the boundary.

**What to exploit**

- Secondary indexes as multivalues: key is the indexed columns, values are
  the run of primary keys. An equality lookup becomes one hash read.
- Child rows under a composite primary key as a run under the parent key.
- No write-buffer merge on statements that have written nothing.
- Row-count estimates from the ordered index's ranks.
- Decode fields straight from the mapped record.
- The stride form for auto-increment keys, if it accepts the key encoding
  (unknown).

## What supdb must grow first

1. A cursor that moves both ways, with bounds.
2. Range delete.
3. A check for "was this key written since my snapshot".
4. Prepared state (durable, hidden, decided later by id).
5. A stable C ABI.
6. Removing one value from a run. Today `put` replaces the run and `delete`
   drops the key.
7. Options for living inside a server process: an explicit memory budget, no
   process-wide allocator trim, control of background threads.

Items 1 and 2 are already open on supdb's roadmap. MySup follows supdb's tag.

## Benchmark plan

Fix the baselines, tests and conditions before building.

- **Engines:** MySup, InnoDB, MyRocks with compression on.
- **Tests (sysbench):** `oltp_point_select`, `oltp_read_only`,
  `select_random_points` and `select_random_ranges` (these two query the
  non-unique `k` index), and the write tests.
- **Conditions:** in memory, and under a memory limit with data several
  times larger.
- **Report beside throughput:** bytes on disk, write throughput, disk reads
  per query.

## Milestones

- **M0. Baselines.** Reproduce the tables above on the chosen server with
  MyRocks compressed. Register the goal. Needs no engine work.
- **M1. Read-only engine.** Handler read path, row codec, C ABI. Run the
  read tests against both rivals. Gate: is double-digit against InnoDB in
  reach?
- **M2. supdb features** from the list above.
- **M3. Transactions.** Locks, write buffer, savepoints, conflict check,
  crash recovery.
- **M4. Prepared state, binary log, DDL, statistics.**
- **M5. Full benchmark and the post.**

## Risks

- **The SQL layer is a fixed floor.** About 37 µs of every query is outside
  any engine.
- **Correctness inside MySQL is the long tail.** MyRocks is 55K lines of
  glue; the handler class has 169 virtual methods and the engine-wide
  struct 93 hooks.
- **MyRocks wins on what it is chosen for.** Space and write efficiency are
  supdb's weaker or unmeasured axes.
- **Writes are unmeasured.** No write test has been run through MySQL.
- **The engine is tied to one exact server version.**

## How the numbers were taken

- Host: a 4-vCPU virtual machine, 15 GB. sysbench 1.0.20, one client thread
  over a Unix socket, uniform keys, latin1 tables.
- In memory: 1M rows; server CPU per query from the server's `utime+stime`
  in `/proc`, mean of two runs.
- Profiles: `perf record -e cpu-clock -g` on the server, samples attributed
  by the `rocksdb::` and `myrocks::` namespaces in the call stack.
- Under the limit: 4 tables of 4M rows, a cgroup v1 memory limit of 1 GiB,
  caches dropped before start, disk reads from `/sys/block/vda/stat`.

The scripts were throwaway and are not kept. Build the M0 harness fresh.

## Pitfalls met while taking the numbers

- MySQL and MariaDB packages conflict. Removing MySQL also removed sysbench.
- `perf script -F dso,sym` printed empty lines. `-F ip,sym,dso` works.
- MariaDB's InnoDB does not export its internal symbols, so its profile
  cannot be split by symbol. MyRocks' plugin exports both `rocksdb::` and
  `myrocks::`, so it can.
- The BLACKHOLE gap is a ceiling: it includes building and sending the row.
- MyRocks with a 640 MB block cache and direct reads passed a 1 GiB limit
  with four client threads and was killed. Size its cache with headroom.
- InnoDB reloads part of its buffer pool at startup, so a "cold" start is
  not fully cold. Warm up before measuring either way.
- Drop the page cache before starting the server inside the memory limit.
- About 20 µs of every query here is kernel time on the socket. This is a
  virtual machine; on bare metal the engine's share will be larger.

## Not verified

- Why people run MyRocks, and Meta's space figures, are from memory.
- MariaDB's MyRocks is an older port than Meta's. Source sizes are from
  Meta's tree, measurements from MariaDB's.
- The in-memory wall-time shares mix two table sizes and are approximate.
- supdb's disk reads per query at three times memory are unmeasured.
- Every gain quoted for MySup is a ceiling or an estimate, not a result.
