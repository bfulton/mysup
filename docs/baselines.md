# M0: the baselines

2026-11-26. This is milestone M0 of the [brief](brief.md): the rivals
measured by a harness that is kept, the brief's tables taken again, and the
goal fixed before any engine code exists. No engine work was done.

Every number here was measured on one host in one nine-hour session. The rows are under
[`bench/runs/`](../bench/runs/), every table drawn from them under
[`tables/`](tables/), and what a row means in
[`bench/README.md`](../bench/README.md) and
[`bench/mysupbench/plan.py`](../bench/mysupbench/plan.py).

## In short

1. **The brief's numbers hold.** Its three tables reproduce to within the
   host's noise, on its server and on two others.
2. **InnoDB sets the mark almost everywhere.** MyRocks, compressed, is
   behind InnoDB in every test at every thread count in memory, by 10% to
   79%, and under the memory limit in all but one. It wins on bytes on disk,
   0.57 per byte stored against InnoDB's 1.3.
3. **In memory, a tenth more than InnoDB is within an engine's reach on two
   of the four read tests.** In `select_random_points` and
   `select_random_ranges` a third to a half of what a query costs is
   InnoDB's own code. In `oltp_point_select` and `oltp_read_only` it is a
   tenth, and a tenth is what the goal asks for.
4. **Half of InnoDB's cost in those two tests is the optimizer's row
   estimate**, a quarter of all server CPU. The brief's design already has
   an answer to it. So does InnoDB: with the estimate switched off by one
   server variable it ran `select_random_points` 24% faster at one thread
   and 47% faster at four.
5. **Under the memory limit more of a query is the engine's**, 44% of a
   point select, but half of that is the wait for the disk, and sysbench's
   rows do not shrink without entropy coding. supdb's compact form has
   none.
6. **A durable write at one client thread is mostly the device.** Of an
   InnoDB insert's 202 µs, 101 µs is the wait for the log to reach the
   device, which is what one write and one flush cost here by themselves,
   and 11 µs is InnoDB's own code.
7. **MyRocks is killed under the limit by glibc's allocator, not by its
   cache size.** With jemalloc it survives every read test. It does not yet
   survive the write tests at any cache size tried.
8. **Server: MariaDB 12.3, from 12.3.4.** Oracle's MySQL ships no MyRocks, so
   the goal as worded cannot be tested on it.

## The goal, as registered

> For a sysbench test at a client thread count under a condition, MySup
> meets the goal when its throughput is at least 1.10 times the better of
> InnoDB's and MyRocks', all three measured in one run of this harness.

What that fixes:

- **Tests:** `oltp_point_select`, `oltp_read_only`, `select_random_points`,
  `select_random_ranges`, and the write tests `oltp_write_only`,
  `oltp_read_write`, `oltp_update_index`, `oltp_update_non_index`,
  `oltp_insert`. sysbench 1.0.20, uniform keys, one table.
- **Threads:** 1 and 4. The host has 4 vCPUs and the client runs on it.
- **Conditions:** in memory (1M rows, 2 GiB cache, no limit) and under a
  memory limit (16M rows, 640 MiB cache, the server's cgroup held to 1 GiB).
- **Rivals:** InnoDB, and MyRocks with LZ4 above its last level and ZSTD in
  it. Both flush their log to the device at every commit and use direct
  I/O. Every setting is in `plan.py`.
- **The number:** for a read test, the edge of the best tenth of measured
  seconds; for a write test, the whole run's mean. `bench/README.md` says
  why.
- **One run:** the host's speed drifts, by 13% to 22% between two runs of
  the same queries three hours apart. A ratio counts only between arms
  that took turns in one run. The marks below are today's, for
  orientation. The test is the ratio.
- **Beside throughput**, from the same rows: bytes on disk, disk reads per
  query, and the write tests.

What I fixed that the brief left open, for you to confirm or change:

- The threshold is per test. The brief says "on sysbench" and not on which
  tests. The grid is reported whole, wins and losses.
- 1 and 4 threads, one table, the two table sizes.
- MyRocks' options: its own tuning page's example, without the lines that
  size it for a large machine.
- MyRocks runs under jemalloc where there is a memory limit.
- InnoDB at the server's defaults but for its cache, its log size, direct
  I/O and no reload of its buffer pool at start.

### Today's marks, in memory

MariaDB 12.3.4, transactions per second. The mark is 1.10 times the better
rival.

| Test | Threads | InnoDB | MyRocks | Mark |
|---|---|---|---|---|
| `oltp_point_select` | 1 | 16,948 | 15,316 | 18,643 |
| | 4 | 202,553 | 161,273 | 222,808 |
| `oltp_read_only` | 1 | 877 | 759 | 965 |
| | 4 | 7,848 | 6,078 | 8,632 |
| `select_random_points` | 1 | 6,785 | 5,459 | 7,463 |
| | 4 | 35,484 | 24,913 | 39,033 |
| `select_random_ranges` | 1 | 7,206 | 6,290 | 7,927 |
| | 4 | 36,917 | 33,559 | 40,609 |
| `oltp_write_only` | 1 | 1,537 | 1,265 | 1,690 |
| | 4 | 4,874 | 3,551 | 5,362 |
| `oltp_read_write` | 1 | 513 | 425 | 565 |
| | 4 | 1,650 | 1,304 | 1,815 |
| `oltp_update_index` | 1 | 4,336 | 2,951 | 4,770 |
| | 4 | 11,258 | 7,084 | 12,384 |
| `oltp_update_non_index` | 1 | 5,158 | 2,920 | 5,674 |
| | 4 | 12,720 | 7,117 | 13,992 |
| `oltp_insert` | 1 | 4,956 | 3,089 | 5,451 |
| | 4 | 12,513 | 7,367 | 13,764 |

Between the passes of one run the read tests moved by up to 9% and the
write tests by up to 23%. The device's flush time drifts more than the CPU
does.

### Today's marks, under the memory limit

| Test | Threads | InnoDB | MyRocks | Mark |
|---|---|---|---|---|
| `oltp_point_select` | 1 | 10,579 | 7,608 | 11,637 |
| | 4 | 32,323 | 21,390 | 35,555 |
| `oltp_read_only` | 1 | 503 | 340 | 553 |
| | 4 | 1,378 | 1,071 | 1,516 |
| `select_random_points` | 1 | 1,174 | 895 | 1,292 |
| | 4 | 3,197 | 2,842 | 3,516 |
| `select_random_ranges` | 1 | 6,358 | 5,989 | 6,994 |
| | 4 | 30,929 | 32,348 | 35,583 |
| `oltp_write_only` | 1 | 1,020 | none yet | |
| | 4 | 2,266 | none yet | |
| `oltp_read_write` | 1 | 279 | none yet | |
| | 4 | 754 | none yet | |
| `oltp_update_index` | 1 | 2,118 | none yet | |
| | 4 | 4,642 | none yet | |
| `oltp_update_non_index` | 1 | 3,088 | none yet | |
| | 4 | 6,992 | none yet | |
| `oltp_insert` | 1 | 5,290 | none yet | |
| | 4 | 12,677 | none yet | |

`select_random_ranges` reads only the `k` index, which fits in the cache, so
it does no disk reads under the limit either. InnoDB's write rows are from a
run of their own, an hour after the reads.

### Bytes on disk

| | 1M rows | 16M rows | Bytes on disk per byte stored |
|---|---|---|---|
| InnoDB | 232 MiB | 3,653 MiB | 1.27 to 1.29 |
| MyRocks, ZSTD in the last level | 101 MiB | 1,628 MiB | 0.57 |
| MyRocks, the server's defaults (Snappy) | 198 MiB | | 1.11 |

A row is 188 bytes as the table declares it. MyRocks was compacted into one
level before measuring, the best case for its size and its reads.

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
  It reads as often as InnoDB and then decompresses the block: `libzstd` is
  24% of the server's CPU in its point select.
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
Size its cache with headroom."** The cache is not what grows. See "MyRocks
under the limit".

**"Writes are unmeasured."** In memory they now are, and InnoDB's under the
limit. See "Writes".

## Where the room is

For each test, InnoDB's part of an event: the server CPU spent in InnoDB's
own code, from the profile, plus the time off the CPU waiting on its disk
reads, over the time the event takes with the client's CPU in it. The last
column is how much of that part a tenth more throughput takes away, all
else equal. These are ceilings on what replacing InnoDB like for like can
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

In memory, MariaDB 12.3.4, both engines flushing at every commit, one
client thread. Time per transaction, and where it went.

| Test | Engine | Transactions per second | Time | Server CPU | Client CPU | Neither | KiB written |
|---|---|---|---|---|---|---|---|
| `oltp_insert` | InnoDB | 4,956 | 202 µs | 81 µs | 20 µs | 101 µs | 4.6 |
| | MyRocks | 3,089 | 324 µs | 124 µs | 26 µs | 174 µs | 8.3 |
| `oltp_update_non_index` | InnoDB | 5,158 | 194 µs | 80 µs | 18 µs | 96 µs | 4.6 |
| | MyRocks | 2,920 | 343 µs | 136 µs | 25 µs | 181 µs | 8.2 |
| `oltp_update_index` | InnoDB | 4,336 | 231 µs | 115 µs | 19 µs | 97 µs | 7.1 |
| | MyRocks | 2,951 | 339 µs | 137 µs | 24 µs | 178 µs | 8.3 |
| `oltp_write_only` | InnoDB | 1,537 | 651 µs | 330 µs | 106 µs | 216 µs | 7.7 |
| | MyRocks | 1,265 | 790 µs | 394 µs | 110 µs | 286 µs | 8.7 |

- "Neither" is the wait for the log to reach the device, plus the idle
  moments between client and server. At one thread both engines make
  exactly one write call and one device flush per transaction.
- What differs is what reaches the device: InnoDB 2.05 writes per insert,
  MyRocks 3.00. The third write is what growing a file costs on this
  filesystem. InnoDB overwrites a log of fixed size. RocksDB appends to one
  that grows, and each `fdatasync` then also writes the file's new length.
  That alone, in `bench/tools/logsync.py`, six runs of 3,000 commits each:

  | Log layout | Device writes per commit | Time per commit, median |
  |---|---|---|
  | Overwrite a file already written, 4 KiB direct writes | 2.03 | 100 µs |
  | Overwrite a file already written | 2.03 | 130 µs |
  | Append, the file grows | 3.00 | 155 µs |
  | Append into space reserved with `fallocate` | 3.00 | 161 µs |

- That accounts for 40 to 60 µs of the 73 µs by which a MyRocks insert
  waits longer than an InnoDB one. Traced with `strace`, in turns, twice,
  InnoDB's write and sync calls took 282 µs a commit and MyRocks' 332 and
  356 µs (`bench/tools/tracesync.py`).
- supdb already overwrites a recycled, pre-written log for this reason
  (`recycle_wal` in its `Options`).
- InnoDB's wait is already at the device's floor: 101 µs an insert, where
  one direct 4 KiB write and one flush took 100 µs by themselves.
- Most of InnoDB's CPU in a simple write is the kernel carrying the log to
  the device, which a durable engine pays in some form. Its own code is
  small. At one thread, from the profile:

  | Test | InnoDB's share of server CPU | of which in the kernel | InnoDB's own code | as part of the transaction | What +10% takes away |
  |---|---|---|---|---|---|
  | `oltp_insert` | 46.7% | 33.3% | 11 µs | 5% | more than all of it |
  | `oltp_update_non_index` | 49.5% | 33.5% | 13 µs | 7% | more than all of it |
  | `oltp_update_index` | 62.0% | 24.5% | 43 µs | 19% | 49% of it |
  | `oltp_write_only` | 35.9% | 11.7% | 80 µs | 12% | 74% of it |
  | `oltp_read_write` | 23.2% | 5.0% | 231 µs | 12% | 77% of it |

  In an insert the commit, which is the log write and its sync, is 35.0% of
  the server's CPU and writing the row 9.0%.
- At four threads the wait is the larger part still: 199 µs of a 320 µs
  insert, with InnoDB flushing 0.53 times per transaction. Its own code is
  15 µs of that insert.

Under the limit InnoDB runs every write test and stays under 800 MiB. An
update there writes 34 to 73 KiB to the device where an insert writes 4.6.
34 KiB is what a 16 KiB page written twice comes to, once through the
doublewrite buffer, with the log. I did not trace those writes. An engine
that only appends does not pay that, and there is no rival number for it
yet.

## MyRocks under the limit

The brief's kill reproduces. With a 640 MiB block cache and glibc's
allocator MyRocks is killed at 1 GiB when four client threads follow one, in
every test that reads from disk.

- The block cache is not what grows. By RocksDB's own count it holds 639 MiB
  throughout. The process holds 728 MiB after one thread has filled the
  cache, and 1,017 MiB five seconds after four threads start.
- It is glibc's per-thread arenas. Held to one arena (`MALLOC_ARENA_MAX=1`)
  the process stays under 830 MiB at four threads. Under jemalloc it sits
  at 890 MiB whatever the thread count.
- A smaller cache does not help under glibc. At 448 MiB the process still
  reaches the limit and is killed in `select_random_points`.
- So under the limit the MyRocks arm runs with jemalloc, and the harness
  records it. Throughput at one thread was the same either way.
  `bench/tools/rocksmem.py` repeats all three.

Not settled: the write tests. Writing adds memtables, 160 to 250 MiB of
them, to the cache and the allocator's overhead. Under jemalloc, in a row of
4-thread write tests a minute each:

| Block cache | What happened |
|---|---|
| 640 MiB | at the limit in the first test, 60 transactions a second in the second, killed in the third |
| 512 MiB | at the limit, 60 transactions a second in the fifth |
| 448 MiB | killed in the fifth |
| 384 MiB | killed in the sixth |

MyRocks needs a configuration for writes under 1 GiB that bounds its
memtables as well as its cache. That is a choice about the rival, and it is
yours. Until it is made there is no MyRocks number for the write tests
under the limit, the condition where MyRocks is most likely to lead.

## Open decisions, with what M0 adds

**Server.** Recommended: MariaDB 12.3, from 12.3.4.

- The goal is "against both InnoDB and MyRocks, on the same server". Oracle's
  MySQL ships no MyRocks. In the MySQL family only Percona Server does.
- Measured here: the three servers cost the same per query to within a few
  percent, and Percona's newer MyRocks is not a stronger rival on reads.
- Read today from the vendors' pages by a research pass, listed with
  sources in [`servers.md`](servers.md), and not checked a second time:
  MariaDB 12.3 is a long-term release supported to June 2029. From 12.3.4 a
  storage engine builds against the installed development package, with no
  server source tree. MySQL has no such route. Meta's MyRocks tree was
  archived in March 2026. In both families an engine is tied to one exact
  server version.

**Whether supdb grows a mode that stores only its compact form.** If bytes
on disk are reported beside throughput, as the plan says, it needs one.

- InnoDB stores sysbench's table at 1.27 to 1.34 bytes per byte, MyRocks
  with ZSTD at 0.57.
- supdb keeps both forms today, 1.94 on its own suite by the brief. Its
  compact form is LZ4, which leaves these rows at 0.82 to 0.94 of their
  size. Derived, not measured: with both forms supdb would be the largest of
  the three on this table, and with the compact form alone still about
  half again as large as MyRocks.
- The same arithmetic touches the brief's strongest number. "It reads 74
  bytes from disk per point read … because its compact form fits in memory"
  was on data that compresses. Sixteen million of these rows are 3 GB, and
  at 0.82 they do not fit in 1 GiB.

**One store or one per table.** M0 adds nothing. Every test here uses one
table.

**New, raised by M0:**

- **Which tests carry the claim.** By the measurements, in memory the goal
  is beyond a cheaper engine against InnoDB on `oltp_point_select`, on
  inserts and on updates that touch no index, and close to beyond it on
  `oltp_read_only`.
- **Whether InnoDB runs at the server's defaults.** One variable is worth
  24% to 47% to it on `select_random_points`.
- **MyRocks' configuration for writes under the limit.**
- **InnoDB's buffer pool under the limit.** At the brief's 640 MiB the
  server peaks at 787 MiB of its 1,024. A larger pool would make InnoDB a
  stronger rival there, and InnoDB sets the marks.
- **Where the client runs.** On this host at four threads it takes 23% of
  the CPU a point select costs.

## Not done, not verified

- **supdb on sysbench's rows**, alone: its bytes on disk, and its disk reads
  per query at three times memory. This is the measurement the project most
  needs next, and it needs no MySQL.
- Write tests under the limit for MyRocks, and profiles of them for
  either engine.
- Percona Server and MariaDB 10.11.14 were measured on the three
  one-statement queries in memory only.
- A client on another host, bare metal, cgroup v2.
- The facts in [`servers.md`](servers.md) beyond what is marked as checked
  here.
- Everything was measured once, on one day, on one virtual machine.

## The host

A virtual machine with 4 vCPUs (Intel Xeon, 2.1 GHz) and 15 GB, Linux 6.18,
Ubuntu 24.04. One virtual disk, ext4 without a journal. The client is
sysbench 1.0.20 on the same machine, over a Unix socket. Servers: MariaDB
10.11.14 from Ubuntu, MariaDB 12.3.4 and Percona Server 8.4.11-12 from
their own Ubuntu packages. A fixed loop on one idle vCPU ran between 7.1 and
10.8 million iterations a second from one second to the next.
