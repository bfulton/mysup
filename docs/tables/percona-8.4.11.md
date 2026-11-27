# Tables: percona-8.4.11

Drawn from the rows under `bench/runs/` by `python3 -m mysupbench report --server percona-8.4.11`. Not edited by hand. [`bench/README.md`](../../bench/README.md) says how a cell's samples become its number.

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

| Query | BLACKHOLE | InnoDB | MyRocks | InnoDB over BLACKHOLE | MyRocks ÷ InnoDB |
|---|---|---|---|---|---|
| Point select by primary key | 33.4 (35.6) | 40.9 (43.6) | 48.9 (52.4) | 18% | 1.20× |
| SUM over a 100-row range | 39.7 (41.7) | 70.6 (77.7) | 106.2 (118.0) | 44% | 1.51× |
| Return a 100-row range | 38.3 (40.6) | 79.1 (86.6) | 116.2 (131.5) | 52% | 1.47× |

### Where a query's time goes, one client thread

Whole-run means, so the columns add up to the wall time less what the client waited.

| Query | Arm | Wall | Server user | Server kernel | Client CPU | Waiting on disk | Disk reads | KiB read | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|
| Point select by primary key | BLACKHOLE | 56.0 µs | 13.8 µs | 22.0 µs | 18.3 µs | 0.0 µs | 0.00 | 0.0 | 486 |
| Point select by primary key | InnoDB | 65.5 µs | 21.6 µs | 22.9 µs | 19.4 µs | 0.0 µs | 0.00 | 0.0 | 2669 |
| Point select by primary key | MyRocks | 74.6 µs | 31.1 µs | 22.6 µs | 19.0 µs | 0.0 µs | 0.00 | 0.0 | 710 |
| SUM over a 100-row range | BLACKHOLE | 62.8 µs | 20.3 µs | 21.9 µs | 18.7 µs | 0.0 µs | 0.00 | 0.0 | 487 |
| SUM over a 100-row range | InnoDB | 100.0 µs | 55.3 µs | 22.9 µs | 19.9 µs | 0.0 µs | 0.00 | 0.0 | 2669 |
| SUM over a 100-row range | MyRocks | 143.4 µs | 97.5 µs | 22.7 µs | 20.4 µs | 0.0 µs | 0.00 | 0.0 | 710 |
| Return a 100-row range | BLACKHOLE | 62.7 µs | 19.1 µs | 22.3 µs | 19.4 µs | 0.0 µs | 0.00 | 0.0 | 487 |
| Return a 100-row range | InnoDB | 116.6 µs | 62.3 µs | 25.7 µs | 26.1 µs | 0.0 µs | 0.00 | 0.0 | 2669 |
| Return a 100-row range | MyRocks | 164.6 µs | 106.0 µs | 27.4 µs | 27.6 µs | 0.0 µs | 0.00 | 0.0 | 710 |

### Share of server CPU by owner, InnoDB

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| InnoDB | 11.5% | 27.7% | 28.6% |
| Server outside the engine | 88.5% | 72.3% | 71.4% |
| of which in the kernel | 57.6% | 35.3% | 35.1% |
| Samples | 28021 | 30923 | 30646 |

### Share of server CPU by owner, MyRocks

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| RocksDB core | 13.1% | 25.7% | 23.2% |
| RocksDB transaction utilities | 3.2% | 5.4% | 5.0% |
| MyRocks | 6.2% | 14.8% | 16.0% |
| Engine, all of it | 22.4% | 45.9% | 44.2% |
| Server outside the engine | 77.6% | 54.1% | 55.8% |
| of which in the kernel | 46.4% | 24.8% | 25.0% |
| Samples | 29784 | 33677 | 32862 |

### What the server asked InnoDB for, one client thread

Share of server CPU, by the handler call InnoDB was entered through.

| Test | InnoDB, all | Estimating rows for the optimizer | Finding the first row of a lookup or range | Stepping to the next row | Ranges handed over as a batch | Preparing the row template | Everything else |
|---|---|---|---|---|---|---|---|
| oltp_point_select | 11.5% | 0.0% | 8.1% | 0.0% | 0.0% | 0.4% | 3.0% |
| sum100 | 27.7% | 9.0% | 14.3% | 2.1% | 0.0% | 0.3% | 2.0% |
| range100 | 28.6% | 8.2% | 6.2% | 12.0% | 0.0% | 0.3% | 1.9% |

### Room against InnoDB, one client thread

InnoDB's share is from the profile; the times are whole-run means.

| Test | InnoDB's share of server CPU | Time per event | InnoDB CPU per event | Waiting on disk per event | InnoDB's part of it | Gain if that part were free | Gain if it were halved | What +10% takes away |
|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 11.5% | 65.5 µs | 5.1 µs | 0.0 µs | 8% | +8% | +4% | more than all of it |
| sum100 | 27.7% | 100.0 µs | 21.6 µs | 0.0 µs | 22% | +28% | +12% | 42% of it |
| range100 | 28.6% | 116.6 µs | 25.2 µs | 0.0 µs | 22% | +28% | +12% | 42% of it |

### sysbench throughput

Transactions per second. Reads: the best tenth of measured seconds, median in brackets. Writes: the whole run's mean, median second in brackets.

| Test | Threads | InnoDB tps | MyRocks tps | MySup's mark (1.10× the better) |
|---|---|---|---|---|
| oltp_point_select | 1 | 16323 (15456) | 14484 (13642) | 17955 |
| sum100 | 1 | 10938 (10043) | 7895 (7149) | 12032 |
| range100 | 1 | 9424 (8656) | 6868 (6135) | 10367 |

### Every cell

| Test | Threads | Arm | tps | Queries per event | Server CPU per event | Disk reads per event | KiB written per event | p99 ms | Between passes | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 1 | InnoDB | 16323 | 1 | 40.9 µs | 0.00 | 0.0 | 0.12 | 0.1% | 2669 |
| oltp_point_select | 1 | MyRocks | 14484 | 1 | 48.9 µs | 0.00 | 0.0 | 0.17 | 3.8% | 710 |
| oltp_point_select | 1 | BLACKHOLE | 18953 | 1 | 33.4 µs | 0.00 | 0.0 | 0.11 | 3.1% | 486 |
| sum100 | 1 | InnoDB | 10938 | 1 | 70.6 µs | 0.00 | 0.0 | 0.21 | 6.0% | 2669 |
| sum100 | 1 | MyRocks | 7895 | 1 | 106.2 µs | 0.00 | 0.0 | 0.38 | 2.1% | 710 |
| sum100 | 1 | BLACKHOLE | 16860 | 1 | 39.7 µs | 0.00 | 0.0 | 0.12 | 2.7% | 487 |
| range100 | 1 | InnoDB | 9424 | 1 | 79.1 µs | 0.00 | 0.0 | 0.26 | 2.7% | 2669 |
| range100 | 1 | MyRocks | 6868 | 1 | 116.2 µs | 0.00 | 0.0 | 0.41 | 1.5% | 710 |
| range100 | 1 | BLACKHOLE | 17114 | 1 | 38.3 µs | 0.00 | 0.0 | 0.13 | 4.7% | 487 |

### Bytes on disk after the load

| Arm | Table files, MiB | Bytes per row | Per byte stored | SST compression | Insert, s | Settle, s | Allocator |
|---|---|---|---|---|---|---|---|
| InnoDB | 240 | 252 | 1.34 |  | 9 | 0 | the C library's |
| MyRocks | 101 | 106 | 0.57 | ZSTD ×4 | 15 | 9 | the C library's |

### The host while it ran

| Run | CPU | CPU floor, M iterations/s | 16 KiB direct read, µs |
|---|---|---|---|
| mem/20261126T181831Z-5486e47.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 8.51–10.81 | 38–64 |

