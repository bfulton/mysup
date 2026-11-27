# M0: the baselines

2026-11-26, amended 2026-11-27. This is milestone M0 of the
[brief](brief.md): the rival measured by a harness that is kept, the brief's
tables taken again, and the goal fixed before any engine code exists. No
engine work was done.

**Amended 2026-11-27: the goal is against InnoDB alone, and it is
double-digit gains where an engine can make them, not a threshold on every
test.** MyRocks was a second rival when these measurements were taken. Its
rows stay, as a reference, and what they showed is at the end.

Every number here was measured on one host in one nine-hour session. The
rows are under [`bench/runs/`](../bench/runs/), every table drawn from them
under [`tables/`](tables/), and what a row means in
[`bench/README.md`](../bench/README.md) and
[`bench/mysupbench/plan.py`](../bench/mysupbench/plan.py).

## In short

1. **The brief's numbers hold.** Its three tables reproduce to within the
   host's noise, on its server and on two others.
2. **In memory, a double-digit gain over InnoDB is within an engine's reach
   on two of the four read tests.** In `select_random_points` and
   `select_random_ranges` a third to a half of what a query costs is
   InnoDB's own code. In `oltp_point_select` and `oltp_read_only` it is a
   tenth, and an engine that cost nothing would gain 8% to 16%.
3. **Half of InnoDB's cost in those two tests is the optimizer's row
   estimate**, a quarter of all server CPU. The brief's design already has
   an answer to it. So does InnoDB: with the estimate switched off by one
   server variable it ran `select_random_points` 24% faster at one thread
   and 47% faster at four.
4. **Under the memory limit more of a query is the engine's**, 44% of a
   point select, but half of that is the wait for the disk, and sysbench's
   rows do not shrink without entropy coding. supdb's compact form has
   none.
5. **A durable write at one client thread is mostly the device.** Of an
   InnoDB insert's 202 µs, 101 µs is the wait for the log to reach the
   device, which is what one write and one flush cost here by themselves,
   and 11 µs is InnoDB's own code.
6. **The server is an open choice again.** My case for MariaDB rested first
   on Oracle's MySQL shipping no MyRocks. What is left is that MariaDB is
   the easier one to build an engine for.

## The goal, as registered

> Double-digit throughput gains over InnoDB on sysbench, where an engine
> can make them, on the same server and host.

- **Every test is reported**, as MySup's throughput over InnoDB's in one
  run of this harness, gains and losses alike. No test has a threshold of
  its own: a gain may be more or less than 10% on any one of them.
- **The claim is the tests with a double-digit gain.** Where a cheaper
  engine cannot make one, the result is reported as it comes. The next
  section says which tests those are likely to be.

What is fixed, so that the ratios mean the same thing at M1 as at M5:

- **Tests:** `oltp_point_select`, `oltp_read_only`, `select_random_points`,
  `select_random_ranges`, and the write tests `oltp_write_only`,
  `oltp_read_write`, `oltp_update_index`, `oltp_update_non_index`,
  `oltp_insert`. sysbench 1.0.20, uniform keys, one table.
- **Threads:** 1 and 4. The host has 4 vCPUs and the client runs on it.
- **Conditions:** in memory (1M rows, 2 GiB cache, no limit) and under a
  memory limit (16M rows, 640 MiB cache, the server's cgroup held to 1 GiB).
- **The rival:** InnoDB, flushing its log to the device at every commit, on
  direct I/O, otherwise at the server's defaults. Every setting is in
  `plan.py`. MySup runs on the same terms: the same cache size, the same
  limit, its log on the device at every commit.
- **The number:** for a read test, the edge of the best tenth of measured
  seconds; for a write test, the whole run's mean. `bench/README.md` says
  why.
- **One run:** the host's speed drifts, by 13% to 22% between two runs of
  the same queries three hours apart. A ratio counts only between arms
  that took turns in one run. InnoDB's numbers below are today's, for
  orientation. What counts is the ratio.
- **Beside throughput**, from the same rows: bytes on disk, disk reads per
  query, and the write tests.

What I fixed that the brief left open, for you to confirm or change:

- 1 and 4 threads, one table, the two table sizes.
- InnoDB at the server's defaults but for its cache, its log size, direct
  I/O and no reload of its buffer pool at start. It is not compressed. The
  brief's "compare compressed against compressed" was about MyRocks.

### Where a double-digit gain looks possible

From "Where the room is" and "Writes" below: how much of an event is
InnoDB's, and how much of that a 10% gain would have to remove. A ceiling
on what replacing InnoDB like for like can do, not a forecast.

| | Tests | Threads | InnoDB's part of an event | A 10% gain removes |
|---|---|---|---|---|
| Within reach, in memory | `select_random_points`, `select_random_ranges` | 1, 4 | 34% to 57% | 16% to 27% of it |
| Hard, in memory | `oltp_read_only` | 1, 4 | 10% to 14% | 65% to 91% |
| | `oltp_update_index` | 1, 4 | 12% to 19% | 49% to 77% |
| | `oltp_write_only`, `oltp_read_write` | 1 | 12% | 74% to 77% |
| Out of reach for a cheaper engine alone, or nearly, in memory | `oltp_point_select` | 1, 4 | 7% to 10% | 91% to more than all of it |
| | `oltp_write_only`, `oltp_read_write` | 4 | 8% to 9% | more than all of it |
| | `oltp_insert`, `oltp_update_non_index` | 1, 4 | 5% to 7% | more than all of it |
| Under the limit, reads | all four | 1, 4 | 43% to 88% | 10% to 21% |
| Under the limit, writes | all five | | not profiled | |

For the reads InnoDB's part is its CPU and its wait on disk reads. For the
writes it is its own code alone: the kernel's share, carrying the log to
the device, is a cost any durable engine pays in some form.

Under the limit about half of InnoDB's part is the wait for the disk, which
only reading less often removes, and sysbench's rows do not compress under
LZ4. The writes in memory are mostly the device: the log write and its
flush.

### InnoDB today

MariaDB 12.3.4, transactions per second.

| Test | Threads | In memory | Under the limit |
|---|---|---|---|
| `oltp_point_select` | 1 | 16,948 | 10,579 |
| | 4 | 202,553 | 32,323 |
| `oltp_read_only` | 1 | 877 | 503 |
| | 4 | 7,848 | 1,378 |
| `select_random_points` | 1 | 6,785 | 1,174 |
| | 4 | 35,484 | 3,197 |
| `select_random_ranges` | 1 | 7,206 | 6,358 |
| | 4 | 36,917 | 30,929 |
| `oltp_write_only` | 1 | 1,537 | 1,020 |
| | 4 | 4,874 | 2,266 |
| `oltp_read_write` | 1 | 513 | 279 |
| | 4 | 1,650 | 754 |
| `oltp_update_index` | 1 | 4,336 | 2,118 |
| | 4 | 11,258 | 4,642 |
| `oltp_update_non_index` | 1 | 5,158 | 3,088 |
| | 4 | 12,720 | 6,992 |
| `oltp_insert` | 1 | 4,956 | 5,290 |
| | 4 | 12,513 | 12,677 |

- The two conditions were measured hours apart, so a number in one column
  is not to be set against the other. An insert was faster under the limit
  only because the device was faster that hour.
- Between the passes of one run the read tests moved by up to 9% and the
  write tests by up to 23%. The device's flush time drifts more than the
  CPU does.
- The write tests under the limit are one pass of three runs. Everything
  else is two or three passes.
- `select_random_ranges` reads only the `k` index, which fits in the cache,
  so it does no disk reads under the limit either.

### Bytes on disk

InnoDB stores sysbench's table at 1.27 to 1.29 bytes on disk per byte
stored: 232 MiB for 1M rows, 3,653 MiB for 16M. A row is 188 bytes as the
table declares it.

## The brief's tables, taken again

### Server CPU per query, in memory

MariaDB 10.11.14, the brief's server, one client thread, microseconds. The
brief took the mean of two runs. Beside it is this harness's median second
and, in brackets, its best tenth. MyRocks here is the server's defaults, as
in the brief.

| Query | BLACKHOLE | InnoDB | MyRocks |
|---|---|---|---|
| Point select, brief | 36.5 | 43.2 | 50.1 |
| Point select, here | 38.0 (35.7) | 45.5 (42.2) | 54.3 (50.0) |
| SUM over 100 rows, brief | 41.7 | 84.3 | 121.7 |
| SUM over 100 rows, here | 44.6 (41.3) | 81.8 (75.8) | 119.8 (108.7) |
| Return 100 rows, brief | 38.8 | 87.9 | 129.8 |
| Return 100 rows, here | 42.1 (39.7) | 89.1 (80.9) | 126.6 (113.2) |

InnoDB's distance above BLACKHOLE: 16%, 51%, 56% in the brief; 15%, 45%, 51%
here.

The same on three servers, best tenth, with MyRocks compressed:

| Query | Server | BLACKHOLE | InnoDB | MyRocks | MyRocks ÷ InnoDB |
|---|---|---|---|---|---|
| Point select | MariaDB 10.11.14 | 35.7 | 42.2 | 49.3 | 1.17× |
| | MariaDB 12.3.4 | 35.0 | 42.0 | 50.3 | 1.20× |
| | Percona Server 8.4.11 | 33.4 | 40.9 | 48.9 | 1.20× |
| SUM over 100 rows | MariaDB 10.11.14 | 41.3 | 75.8 | 100.1 | 1.32× |
| | MariaDB 12.3.4 | 41.9 | 73.1 | 99.6 | 1.36× |
| | Percona Server 8.4.11 | 39.7 | 70.6 | 106.2 | 1.51× |
| Return 100 rows | MariaDB 10.11.14 | 39.7 | 80.9 | 103.4 | 1.28× |
| | MariaDB 12.3.4 | 39.8 | 79.2 | 106.5 | 1.34× |
| | Percona Server 8.4.11 | 38.3 | 79.1 | 116.2 | 1.47× |

Each server was measured in its own run, so differences of a few percent
between servers mean nothing. The three agree. Percona's MyRocks is built on
RocksDB 9.3.1 and MariaDB's on 6.29.5, and the newer one is not the faster.

### Share of server CPU, MyRocks in memory

MariaDB 10.11.14: the server's defaults as in the brief, then compressed.

| | Point select, brief | here, defaults | here, compressed | SUM over 100 rows, brief | here, defaults | here, compressed |
|---|---|---|---|---|---|---|
| RocksDB core | 15% | 13.5% | 13.3% | 30% | 27.8% | 24.3% |
| RocksDB transaction wrapper | 3% | 2.4% | 2.2% | 4% | 3.8% | 3.9% |
| MyRocks glue | 6% | 5.1% | 5.2% | 12% | 11.4% | 11.6% |
| All of it | 24% | 21.0% | 20.7% | 46% | 43.1% | 39.8% |

### Three times memory

16M rows, the server held to 1 GiB, 640 MiB cache, one client thread.
MariaDB 12.3.4, one table where the brief had four.

| | Wall per query | Disk reads per query | Device time in reads |
|---|---|---|---|
| InnoDB point select, brief | 114 µs | 0.84 | 40 µs |
| here, the 19:27 run | 115.1 µs | 0.84 | 40.7 µs |
| here, the 22:48 run | 99.8 µs | 0.84 | 32.8 µs |
| InnoDB SUM over 100 rows, brief | 255 µs | 2.0 | 103 µs |
| here, the 19:27 run | 242.5 µs | 1.97 | 94.9 µs |
| here, the 22:48 run | 190.2 µs | 1.98 | 74.4 µs |
| MyRocks point select, brief (Snappy) | 119 µs | 0.80 | 35 µs |
| here, ZSTD, the 22:48 run | 141.1 µs | 0.80 | 36.3 µs |
| MyRocks SUM over 100 rows, brief (Snappy) | 416 µs | 3.2 | 164 µs |
| here, ZSTD, the 22:48 run | 337.9 µs | 1.76 | 92.3 µs |

- InnoDB reproduces in the first run. Three hours later the same queries
  ran 13% and 22% faster, because the device did: a 16 KiB direct read took
  48 to 59 µs during the first run and 37 to 46 µs during the second. The
  reads per query did not move.
- Compressed, MyRocks is well behind InnoDB here and not level with it: 41%
  more time for a point select, 78% more for a SUM. The difference is CPU.
- With 16 KiB blocks MyRocks reads 1.76 times per SUM where the brief's
  defaults read 3.2.
- The last column is what the brief called waiting on disk: the time the
  device's requests were open. The wait is shorter, because a request is
  open while its thread is still on the CPU sending it, and again
  collecting it. In the 22:48 run an InnoDB point select spent 22.4 µs with
  neither server nor client on a CPU, against 32.8 µs of device time.

## What the measurements change in the brief

**"MyRocks ran uncompressed (MariaDB's default)."** MariaDB's default is
Snappy. On this data it comes to nearly the same thing: sysbench's `c` and
`pad` columns are random decimal digits, and a coder without an entropy
stage finds little in them.

| Coder, on sysbench's rows | 4 KiB blocks | 16 KiB | 64 KiB |
|---|---|---|---|
| LZ4 | 0.94 | 0.87 | 0.82 |
| Snappy | 0.99 | 0.94 | 0.88 |
| ZSTD, level 6 | 0.52 | 0.52 | 0.52 |

Compressed size over raw size, from `bench/tools/rowcompress.py`.

**"InnoDB's engine-and-row share: 16%, 51%, 56%."** That is the distance to
BLACKHOLE, and the brief says it is a ceiling. With InnoDB's symbols loaded
the profile gives InnoDB's own code:

| MariaDB 12.3.4, share of server CPU | Point select | SUM over 100 rows | Return 100 rows |
|---|---|---|---|
| InnoDB's distance to BLACKHOLE, one thread | 17% | 43% | 50% |
| InnoDB's own code, one thread | 9.9% | 23.2% | 23.3% |
| InnoDB's own code, four threads | 13.6% | 27.7% | 28.6% |
| InnoDB's own code, under the limit, one thread | 36.4% | 48.7% | 48.4% |

MariaDB 10.11.14 gave 12.6%, 24.0%, 25.9% at one thread in memory, and
Percona Server 11.5%, 27.7%, 28.6%. About half of the distance to BLACKHOLE
on the range queries is the server's own work per row, which stays whatever
the engine.

**"About 37 µs of every query is outside any engine."** At one client
thread. With four, and every vCPU busy, an InnoDB point select costs 15.3 µs
of server CPU and not 45.0: 11.3 µs in user code and 4.0 µs in the kernel,
where one thread had 23.6 µs and 21.4 µs. The client's own CPU falls the
same way, from 18.6 µs to 4.7 µs. Most of the floor is the cost of going to
sleep and waking for each query on an otherwise idle virtual machine.

| Server CPU per query, best tenth | BLACKHOLE | InnoDB | MyRocks | InnoDB over BLACKHOLE |
|---|---|---|---|---|
| Point select, one thread | 35.0 µs | 42.0 µs | 50.3 µs | 17% |
| Point select, four threads | 11.0 µs | 14.8 µs | 19.6 µs | 26% |
| SUM over 100 rows, one thread | 41.9 µs | 73.1 µs | 99.6 µs | 43% |
| SUM over 100 rows, four threads | 13.4 µs | 37.0 µs | 57.0 µs | 64% |
| Return 100 rows, one thread | 39.8 µs | 79.2 µs | 106.5 µs | 50% |
| Return 100 rows, four threads | 13.1 µs | 41.6 µs | 62.2 µs | 69% |

InnoDB's own code gets cheaper with everything else, from 4.5 µs a point
select to 2.1 µs, so its share moves less than the floor does: 9.9% at one
thread, 13.6% at four. I do not know which mechanism makes warm code twice
as fast here. The host has no counters that would tell cache misses from
anything else.

**"sysbench's read-only test … roughly a quarter to a third of it is the
engine's … a 10% win means doing that part about 1.5 times cheaper."**
Measured, InnoDB is 13.3% of the server's CPU in `oltp_read_only` at one
thread and 16.9% at four. Of the time an event takes, client included, that
is 10% and 14%. A tenth more throughput takes 91% of InnoDB's part away at
one thread and 65% at four: 11 times cheaper than InnoDB, or 2.9 times.

**"In memory, point selects leave little room: about 16%."** Less. InnoDB is
7% of a point select's time at one thread and 10% at four. An engine that
cost nothing would gain 8% and 11%.

**"The headline will come from range scans, secondary-index lookups and data
larger than memory."** From the secondary index, yes. The next section has
the rest.

**"MyRocks with four client threads passed the 1 GiB limit and was killed.
Size its cache with headroom."** The cache is not what grows. See "MyRocks,
for reference".

**"Writes are unmeasured."** They now are for InnoDB, in memory and under
the limit. See "Writes".

## Where the room is

For each test, InnoDB's part of an event: the server CPU spent in InnoDB's
own code, from the profile, plus the time off the CPU waiting on its disk
reads, over the time the event takes with the client's CPU in it. The last
column is how much of that part has to go for a 10% gain, the smallest
double-digit one, all else equal. These are ceilings on what replacing InnoDB like for like can
do, not forecasts.

| Test | Condition | Threads | InnoDB's part of an event | Gain if that part cost nothing | What +10% takes away |
|---|---|---|---|---|---|
| `oltp_point_select` | in memory | 1 | 7% | +8% | more than all of it |
| | | 4 | 10% | +11% | 91% of it |
| `oltp_read_only` | in memory | 1 | 10% | +11% | 91% of it |
| | | 4 | 14% | +16% | 65% of it |
| `select_random_points` | in memory | 1 | 47% | +87% | 20% of it |
| | | 4 | 57% | +131% | 16% of it |
| `select_random_ranges` | in memory | 1 | 34% | +51% | 27% of it |
| | | 4 | 45% | +82% | 20% of it |
| SUM over 100 rows | in memory | 1 | 19% | +23% | 49% of it |
| | | 4 | 24% | +32% | 38% of it |
| Return 100 rows | in memory | 1 | 18% | +22% | 50% of it |
| | | 4 | 24% | +31% | 39% of it |
| `oltp_point_select` | under the limit | 1 | 44% | +80% | 20% of it |
| | | 4 | 50% | +98% | 18% of it |
| `oltp_read_only` | under the limit | 1 | 47% | +88% | 19% of it |
| | | 4 | 45% | +81% | 20% of it |
| `select_random_points` | under the limit | 1 | 84% | | 11% of it |
| | | 4 | 88% | | 10% of it |
| `select_random_ranges` | under the limit | 1 | 43% | +77% | 21% of it |
| | | 4 | 53% | +113% | 17% of it |
| SUM over 100 rows | under the limit | 1 | 58% | +139% | 16% of it |
| Return 100 rows | under the limit | 1 | 57% | +133% | 16% of it |

A second bound, from throughput and not from the profile: BLACKHOLE, which
finds no row and sends none, ran 14% more point selects a second than InnoDB
at one thread and 25% more at four.

What the server asked InnoDB for, as shares of all server CPU at one thread
in memory:

| Test | InnoDB, all | Estimating rows | Finding the first row | Stepping to the next row | The rest |
|---|---|---|---|---|---|
| `oltp_point_select` | 9.9% | 0.0% | 7.1% | 0.0% | 2.8% |
| `oltp_read_only` | 13.3% | 2.5% | 4.2% | 4.4% | 2.2% |
| `select_random_points` | 54.4% | 26.2% | 24.2% | 0.9% | 3.1% |
| `select_random_ranges` | 39.3% | 23.8% | 6.0% | 6.9% | 2.6% |
| SUM over 100 rows | 23.2% | 6.7% | 1.7% | 12.2% | 2.6% |
| Return 100 rows | 23.3% | 6.5% | 1.6% | 12.8% | 2.4% |

- **`select_random_points` and `select_random_ranges`** send ten values or
  ten ranges on the `k` index. For each one the optimizer asks the engine
  how many rows it holds (`records_in_range`), and InnoDB answers by
  descending the index to both ends. That estimate is 26% and 24% of the
  server's CPU. A tenth more throughput is about 40% of the estimate's
  cost. The brief's design lists estimates from the ordered index's ranks.
- **InnoDB can drop the estimate too.** `eq_range_index_dive_limit` at or
  below the number of values makes the optimizer use stored statistics for
  an `IN` list. With it at 5 and the same plan, InnoDB ran
  `select_random_points` at 8,250 queries a second against 6,650 at one
  thread, and 50,400 against 34,400 at four (`bench/tools/divelimit.py`,
  the two settings in turns, three times). Its server CPU per query fell by
  30 µs at one thread, where the profile had put the estimate at 35 µs. So
  the profile holds, and a win on this test that comes from the estimate
  alone is one InnoDB's user can take with a setting. There is no such
  setting for the ranges of `select_random_ranges`.
- **`oltp_point_select` and `oltp_read_only`** are where the server itself
  is most of the work: parsing, planning, the socket. What the brief's
  design proposes all sits inside the engine's tenth.
- **The two range statements** sit between: a fifth to a quarter is
  InnoDB's, and a tenth takes 38% to 50% of it. More than a quarter of
  InnoDB's part is again the estimate.
- **Under the limit**, InnoDB's part is 44% of a point select and 84% of a
  `select_random_points`, and about half of it is the wait for the device:
  22 µs of a point select, for 0.84 reads. A rival gains there only by
  reading less often, and with rows that do not compress, a cache holds
  about the same fraction of them whoever owns it. What is left is InnoDB's
  CPU: 22 µs of a 100 µs point select, of which 7 µs is the call that hands
  the read to the hypervisor.
- **The disk reads of a range query happen inside the estimate.** Under the
  limit `records_in_range` is 38% of the server's CPU in the SUM query. The
  estimate descends to both ends of the range, and on a cold page that
  descent is the read the query needed anyway.

## Writes

In memory, MariaDB 12.3.4, InnoDB flushing at every commit, one client
thread. Time per transaction, where it went, and how much of it is InnoDB's
own code by the profile.

| Test | Time | Server CPU | Client CPU | Neither | InnoDB's own code | What +10% takes away |
|---|---|---|---|---|---|---|
| `oltp_insert` | 202 µs | 81 µs | 20 µs | 101 µs | 11 µs | more than all of it |
| `oltp_update_non_index` | 194 µs | 80 µs | 18 µs | 96 µs | 13 µs | more than all of it |
| `oltp_update_index` | 231 µs | 115 µs | 19 µs | 97 µs | 43 µs | 49% of it |
| `oltp_write_only` | 651 µs | 330 µs | 106 µs | 216 µs | 80 µs | 74% of it |
| `oltp_read_write` | 1.95 ms | 1.27 ms | 365 µs | 309 µs | 231 µs | 77% of it |

- "Neither" is the wait for the log to reach the device, plus the idle
  moments between client and server. InnoDB makes exactly one write call
  and one device flush per transaction at one thread.
- InnoDB's wait is already at the device's floor: 101 µs an insert, where
  one direct 4 KiB write and one flush took 100 µs by themselves
  (`bench/tools/logsync.py`).
- Most of InnoDB's CPU in a simple write is the kernel carrying the log to
  the device, which a durable engine pays in some form. InnoDB is 46.7% of
  the server's CPU in an insert, and 33.3% of the server's CPU is InnoDB in
  the kernel. The commit, which is the log write and its sync, is 35.0%,
  and writing the row 9.0%.
- At four threads the wait is the larger part still: 199 µs of a 320 µs
  insert, with InnoDB flushing 0.53 times per transaction. Its own code is
  15 µs of that insert.
- A log that grows costs more than one that is overwritten. The same test
  took 155 µs a commit appending to a file and 100 to 130 µs overwriting
  one, with one more device write each time: an `fdatasync` after an append
  also writes the file's new length. InnoDB overwrites a log of fixed size.
  supdb already overwrites a recycled, pre-written one (`recycle_wal` in
  its `Options`).

Under the limit InnoDB runs every write test and stays under 800 MiB. An
update there writes 34 to 73 KiB to the device where an insert writes 4.6.
34 KiB is what a 16 KiB page written twice comes to, once through the
doublewrite buffer, with the log. I did not trace those writes. An engine
that only appends does not pay that.

## Open decisions, with what M0 adds

**Server.** Open again. I recommended MariaDB first because Oracle's MySQL
ships no MyRocks, and that reason went with MyRocks.

- For MariaDB 12.3, from 12.3.4: a storage engine builds against the
  installed development package, with no server source tree, and the
  release is supported to June 2029. Both were read from the vendor's pages
  and not checked a second time ([`servers.md`](servers.md)). Every number
  above was taken on it.
- For MySQL: the name, and its InnoDB is the one most readers will take
  "InnoDB" to mean. No supported way to build an engine outside its source
  tree was found.
- Measured: on the three one-statement queries in memory InnoDB costs the
  same on MariaDB 10.11.14, MariaDB 12.3.4 and Percona Server 8.4.11, which
  is MySQL 8.4's code, to within a few percent. Nothing else was measured
  on a MySQL-family server, and Oracle's own build was not measured at all.
  On MySQL the baselines would have to be taken again.
- I would still build on MariaDB 12.3.4 first, for the build route alone.
  It is a weaker case than it was.
- In both families an engine is tied to one exact server version.

**Whether supdb grows a mode that stores only its compact form.** If bytes
on disk are reported beside throughput, as the plan says, it needs one.

- InnoDB stores sysbench's table at 1.27 to 1.34 bytes per byte across the
  three servers.
- supdb keeps both forms today, 1.94 on its own suite by the brief. Its
  compact form is LZ4, which leaves these rows at 0.82 to 0.94 of their
  size. Derived, not measured: with both forms supdb would be larger than
  InnoDB on this table, and with the compact form alone smaller.
- The same arithmetic touches the brief's strongest number. "It reads 74
  bytes from disk per point read … because its compact form fits in memory"
  was on data that compresses. Sixteen million of these rows are 3 GB, and
  at 0.82 they do not fit in 1 GiB.

**One store or one per table.** M0 adds nothing. Every test here uses one
table.

**New, raised by M0:**

- **Whether InnoDB runs at the server's defaults.** One variable is worth
  24% to 47% to it on `select_random_points`.
- **InnoDB's buffer pool under the limit.** At the brief's 640 MiB the
  server peaks at 787 MiB of its 1,024 in the read tests. A larger pool
  would make InnoDB a stronger rival there.
- **Where the client runs.** On this host at four threads it takes 23% of
  the CPU a point select costs.

## Not done, not verified

- **supdb on sysbench's rows**, alone: its bytes on disk, and its disk reads
  per query at three times memory. This is the measurement the project most
  needs next, and it needs no MySQL.
- Profiles of the write tests under the limit.
- Percona Server and MariaDB 10.11.14 were measured on the three
  one-statement queries in memory only.
- A client on another host, bare metal, cgroup v2.
- The facts in [`servers.md`](servers.md) beyond what is marked as checked
  here.
- Everything was measured once, on one day, on one virtual machine.

## MyRocks, for reference

MyRocks was the second rival until 2026-11-27. What its rows showed, with
LZ4 above its last level and ZSTD in it:

- **It trailed InnoDB almost everywhere.** In memory by 10% to 79% in every
  test at both thread counts. Under the limit in all but
  `select_random_ranges` at four threads, where it led by 5%. No write test
  under the limit was measured for it.
- **It is much smaller on disk:** 0.57 bytes per byte stored against
  InnoDB's 1.27 to 1.29, and 1.11 with the server's default, Snappy.
- **Under the limit it reads as often as InnoDB and then decompresses.**
  `libzstd` is 24% of the server's CPU in its point select.
- **Its log grows.** A MyRocks insert waits 73 µs longer than an InnoDB one,
  and 40 to 60 µs of that is the extra device write described under
  "Writes". Traced with `strace`, in turns, twice, InnoDB's write and sync
  calls took 282 µs a commit and MyRocks' 332 and 356 µs
  (`bench/tools/tracesync.py`).
- **The brief's kill under the limit is glibc's allocator, not the cache
  size.** With a 640 MiB block cache MyRocks is killed at 1 GiB when four
  client threads follow one. By RocksDB's own count the cache holds 639 MiB
  throughout. The process holds 728 MiB after one thread has filled it and
  1,017 MiB five seconds after four threads start, in glibc's per-thread
  arenas. Held to one arena it stays under 830 MiB, and under jemalloc at
  890 MiB at any thread count. A smaller cache does not help under glibc.
  `bench/tools/rocksmem.py` repeats this. The same allocator sits under any
  engine loaded into the server, MySup included.
- Under jemalloc it survived every read test under the limit, and no write
  test at any cache size tried from 640 down to 384 MiB. That question
  closed with the decision.

## The host

A virtual machine with 4 vCPUs (Intel Xeon, 2.1 GHz) and 15 GB, Linux 6.18,
Ubuntu 24.04. One virtual disk, ext4 without a journal. The client is
sysbench 1.0.20 on the same machine, over a Unix socket. Servers: MariaDB
10.11.14 from Ubuntu, MariaDB 12.3.4 and Percona Server 8.4.11-12 from
their own Ubuntu packages. A fixed loop on one idle vCPU ran between 7.1 and
10.8 million iterations a second from one second to the next.
