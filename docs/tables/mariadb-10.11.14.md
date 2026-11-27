# Tables: mariadb-10.11.14

Drawn from the rows under `bench/runs/` by `python3 -m mysupbench report --server mariadb-10.11.14`. Not edited by hand. [`bench/README.md`](../../bench/README.md) says how a cell's samples become its number.

## In memory, every server measured

Server CPU per query in microseconds and queries per second at one client thread, the best tenth of seconds. Each server's rows are from its own run.

| Query | Server | BLACKHOLE µs | InnoDB µs | MyRocks µs | MyRocks ÷ InnoDB | InnoDB qps | MyRocks qps | InnoDB's share of its server's CPU | MyRocks' share |
|---|---|---|---|---|---|---|---|---|---|
| Point select by primary key | mariadb-10.11.14 | 35.7 | 42.2 | 49.3 | 1.17× | 16159 | 14506 | 12.6% | 20.7% |
| Point select by primary key | percona-8.4.11 | 33.4 | 40.9 | 48.9 | 1.20× | 16323 | 14484 | 11.5% | 22.4% |
| Point select by primary key | mariadb-12.3.4 | 35.0 | 42.0 | 50.3 | 1.20× | 16948 | 15316 | 9.9% | 20.5% |
| SUM over a 100-row range | mariadb-10.11.14 | 41.3 | 75.8 | 100.1 | 1.32× | 10293 | 8203 | 24.0% | 39.8% |
| SUM over a 100-row range | percona-8.4.11 | 39.7 | 70.6 | 106.2 | 1.51× | 10938 | 7895 | 27.7% | 45.9% |
| SUM over a 100-row range | mariadb-12.3.4 | 41.9 | 73.1 | 99.6 | 1.36× | 11018 | 8590 | 23.2% | 40.5% |
| Return a 100-row range | mariadb-10.11.14 | 39.7 | 80.9 | 103.4 | 1.28× | 9245 | 7584 | 25.9% | 39.3% |
| Return a 100-row range | percona-8.4.11 | 38.3 | 79.1 | 116.2 | 1.47× | 9424 | 6868 | 28.6% | 44.2% |
| Return a 100-row range | mariadb-12.3.4 | 39.8 | 79.2 | 106.5 | 1.34× | 9713 | 7722 | 23.3% | 39.8% |

## In memory

1,000,000 rows, engine cache 2048 MiB, memory limit none.

### Server CPU per query, one client thread

Microseconds: the best tenth of measured seconds, with the median in brackets.

| Query | BLACKHOLE | InnoDB | MyRocks | MyRocks, server defaults | InnoDB over BLACKHOLE | MyRocks ÷ InnoDB |
|---|---|---|---|---|---|---|
| Point select by primary key | 35.7 (38.0) | 42.2 (45.5) | 49.3 (52.7) | 50.0 (54.3) | 15% | 1.17× |
| SUM over a 100-row range | 41.3 (44.6) | 75.8 (81.8) | 100.1 (108.5) | 108.7 (119.8) | 45% | 1.32× |
| Return a 100-row range | 39.7 (42.1) | 80.9 (89.1) | 103.4 (115.0) | 113.2 (126.6) | 51% | 1.28× |

### Where a query's time goes, one client thread

Whole-run means, so the columns add up to the wall time less what the client waited.

| Query | Arm | Wall | Server user | Server kernel | Client CPU | Waiting on disk | Disk reads | KiB read | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|
| Point select by primary key | BLACKHOLE | 58.9 µs | 16.8 µs | 21.5 µs | 18.7 µs | 0.0 µs | 0.00 | 0.0 | 114 |
| Point select by primary key | InnoDB | 66.6 µs | 24.4 µs | 21.4 µs | 18.6 µs | 0.0 µs | 0.00 | 0.0 | 381 |
| Point select by primary key | MyRocks | 74.5 µs | 32.0 µs | 21.6 µs | 18.7 µs | 0.1 µs | 0.00 | 0.0 | 333 |
| Point select by primary key | MyRocks, server defaults | 78.4 µs | 34.6 µs | 22.1 µs | 19.2 µs | 0.0 µs | 0.00 | 0.0 | 343 |
| SUM over a 100-row range | BLACKHOLE | 65.6 µs | 22.2 µs | 22.6 µs | 18.9 µs | 0.0 µs | 0.00 | 0.0 | 114 |
| SUM over a 100-row range | InnoDB | 105.9 µs | 61.4 µs | 22.0 µs | 19.7 µs | 0.0 µs | 0.00 | 0.0 | 381 |
| SUM over a 100-row range | MyRocks | 132.7 µs | 87.7 µs | 21.8 µs | 19.8 µs | 0.0 µs | 0.00 | 0.0 | 334 |
| SUM over a 100-row range | MyRocks, server defaults | 147.8 µs | 100.1 µs | 23.1 µs | 20.8 µs | 0.0 µs | 0.00 | 0.0 | 342 |
| Return a 100-row range | BLACKHOLE | 63.1 µs | 20.9 µs | 21.6 µs | 18.5 µs | 0.0 µs | 0.00 | 0.0 | 114 |
| Return a 100-row range | InnoDB | 119.0 µs | 63.7 µs | 26.2 µs | 25.9 µs | 0.0 µs | 0.00 | 0.0 | 382 |
| Return a 100-row range | MyRocks | 145.9 µs | 90.2 µs | 25.8 µs | 26.4 µs | 0.0 µs | 0.00 | 0.0 | 334 |
| Return a 100-row range | MyRocks, server defaults | 160.0 µs | 101.5 µs | 26.8 µs | 27.3 µs | 0.0 µs | 0.00 | 0.0 | 343 |

### Share of server CPU by owner, InnoDB

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| InnoDB | 12.6% | 24.0% | 25.9% |
| Server outside the engine | 87.4% | 76.0% | 74.1% |
| of which in the kernel | 52.6% | 31.9% | 31.5% |
| Samples | 28265 | 31948 | 30919 |

### Share of server CPU by owner, MyRocks

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| RocksDB core | 13.3% | 24.3% | 22.5% |
| RocksDB transaction utilities | 2.2% | 3.9% | 3.9% |
| MyRocks | 5.2% | 11.6% | 12.9% |
| Engine, all of it | 20.7% | 39.8% | 39.3% |
| Server outside the engine | 79.3% | 60.2% | 60.7% |
| of which in the kernel | 46.9% | 24.9% | 26.5% |
| Samples | 29425 | 33184 | 32539 |

### Share of server CPU by owner, MyRocks, server defaults

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| RocksDB core | 13.5% | 27.8% | 26.8% |
| RocksDB transaction utilities | 2.4% | 3.8% | 4.3% |
| MyRocks | 5.1% | 11.4% | 13.1% |
| Engine, all of it | 21.0% | 43.1% | 44.2% |
| Server outside the engine | 79.0% | 56.9% | 55.8% |
| of which in the kernel | 47.0% | 23.9% | 21.6% |
| Samples | 29409 | 33637 | 32584 |

### What the server asked InnoDB for, one client thread

Share of server CPU, by the handler call InnoDB was entered through.

| Test | InnoDB, all | Estimating rows for the optimizer | Finding the first row of a lookup or range | Stepping to the next row | Ranges handed over as a batch | Preparing the row template | Everything else |
|---|---|---|---|---|---|---|---|
| oltp_point_select | 12.6% | 0.0% | 10.3% | 0.0% | 0.0% | 0.7% | 1.6% |
| sum100 | 24.0% | 8.2% | 1.8% | 0.0% | 0.2% | 0.3% | 13.4% |
| range100 | 25.9% | 8.2% | 1.9% | 0.0% | 0.2% | 0.4% | 15.2% |

### Room against InnoDB, one client thread

InnoDB's share is from the profile; the times are whole-run means.

| Test | InnoDB's share of server CPU | Time per event | InnoDB CPU per event | Waiting on disk per event | InnoDB's part of it | Gain if that part were free | Gain if it were halved | What +10% takes away |
|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 12.6% | 66.6 µs | 5.8 µs | 0.0 µs | 9% | +10% | +5% | more than all of it |
| sum100 | 24.0% | 105.9 µs | 20.0 µs | 0.0 µs | 19% | +23% | +10% | 48% of it |
| range100 | 25.9% | 119.0 µs | 23.3 µs | 0.0 µs | 20% | +24% | +11% | 46% of it |

### sysbench throughput

Transactions per second. Reads: the best tenth of measured seconds, median in brackets. Writes: the whole run's mean, median second in brackets.

| Test | Threads | InnoDB tps | MyRocks tps | MySup's mark (1.10× the better) |
|---|---|---|---|---|
| oltp_point_select | 1 | 16159 (15094) | 14506 (13648) | 17775 |
| sum100 | 1 | 10293 (9558) | 8203 (7629) | 11323 |
| range100 | 1 | 9245 (8434) | 7584 (6918) | 10170 |

### Every cell

| Test | Threads | Arm | tps | Queries per event | Server CPU per event | Disk reads per event | KiB written per event | p99 ms | Between passes | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 1 | InnoDB | 16159 | 1 | 42.2 µs | 0.00 | 0.0 | 0.13 | 5.2% | 381 |
| oltp_point_select | 1 | MyRocks | 14506 | 1 | 49.3 µs | 0.00 | 0.0 | 0.15 | 2.5% | 333 |
| oltp_point_select | 1 | MyRocks, server defaults | 14320 | 1 | 50.0 µs | 0.00 | 0.0 | 0.16 | 12.8% | 343 |
| oltp_point_select | 1 | BLACKHOLE | 18109 | 1 | 35.7 µs | 0.00 | 0.0 | 0.11 | 3.2% | 114 |
| sum100 | 1 | InnoDB | 10293 | 1 | 75.8 µs | 0.00 | 0.0 | 0.21 | 5.9% | 381 |
| sum100 | 1 | MyRocks | 8203 | 1 | 100.1 µs | 0.00 | 0.0 | 0.30 | 2.7% | 334 |
| sum100 | 1 | MyRocks, server defaults | 7606 | 1 | 108.7 µs | 0.00 | 0.0 | 0.35 | 2.7% | 342 |
| sum100 | 1 | BLACKHOLE | 16282 | 1 | 41.3 µs | 0.00 | 0.0 | 0.12 | 2.1% | 114 |
| range100 | 1 | InnoDB | 9245 | 1 | 80.9 µs | 0.00 | 0.0 | 0.26 | 3.5% | 382 |
| range100 | 1 | MyRocks | 7584 | 1 | 103.4 µs | 0.00 | 0.0 | 0.32 | 0.8% | 334 |
| range100 | 1 | MyRocks, server defaults | 6990 | 1 | 113.2 µs | 0.00 | 0.0 | 0.41 | 1.1% | 343 |
| range100 | 1 | BLACKHOLE | 16848 | 1 | 39.7 µs | 0.00 | 0.0 | 0.12 | 1.9% | 114 |

### Bytes on disk after the load

| Arm | Table files, MiB | Bytes per row | Per byte stored | SST compression | Insert, s | Settle, s | Allocator |
|---|---|---|---|---|---|---|---|
| InnoDB | 236 | 248 | 1.32 |  | 7 | 0 | the C library's |
| MyRocks | 101 | 106 | 0.57 | ZSTD ×2 | 13 | 13 | the C library's |
| MyRocks, server defaults | 198 | 208 | 1.11 | Snappy ×4 | 14 | 14 | the C library's |

### The host while it ran

| Run | CPU | CPU floor, M iterations/s | 16 KiB direct read, µs |
|---|---|---|---|
| mem/20261126T171423Z-7268ba5.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 7.69–10.49 | 35–59 |
| mem/20261126T180507Z-46566ba.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 8.63–10.22 | 37–61 |

