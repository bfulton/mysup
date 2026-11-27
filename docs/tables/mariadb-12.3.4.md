# Tables: mariadb-12.3.4

Drawn from the rows under `bench/runs/` by `python3 -m mysupbench report --server mariadb-12.3.4`. Not edited by hand. [`bench/README.md`](../../bench/README.md) says how a cell's samples become its number.

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
| Point select by primary key | 35.0 (37.2) | 42.0 (44.6) | 50.3 (54.0) | 17% | 1.20× |
| SUM over a 100-row range | 41.9 (44.6) | 73.1 (77.9) | 99.6 (110.9) | 43% | 1.36× |
| Return a 100-row range | 39.8 (42.2) | 79.2 (87.0) | 106.5 (117.4) | 50% | 1.34× |

### Where a query's time goes, one client thread

Whole-run means, so the columns add up to the wall time less what the client waited.

| Query | Arm | Wall | Server user | Server kernel | Client CPU | Waiting on disk | Disk reads | KiB read | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|
| Point select by primary key | BLACKHOLE | 54.9 µs | 16.6 µs | 20.9 µs | 18.1 µs | 0.0 µs | 0.00 | 0.0 | 133 |
| Point select by primary key | InnoDB | 62.7 µs | 23.6 µs | 21.4 µs | 18.6 µs | 0.0 µs | 0.00 | 0.0 | 399 |
| Point select by primary key | MyRocks | 70.8 µs | 32.5 µs | 22.5 µs | 18.5 µs | 0.0 µs | 0.00 | 0.0 | 350 |
| SUM over a 100-row range | BLACKHOLE | 63.5 µs | 23.8 µs | 21.6 µs | 18.7 µs | 0.0 µs | 0.00 | 0.0 | 133 |
| SUM over a 100-row range | InnoDB | 98.5 µs | 58.2 µs | 21.5 µs | 19.4 µs | 0.0 µs | 0.00 | 0.0 | 398 |
| SUM over a 100-row range | MyRocks | 128.7 µs | 88.5 µs | 22.9 µs | 19.5 µs | 0.0 µs | 0.00 | 0.0 | 350 |
| Return a 100-row range | BLACKHOLE | 60.5 µs | 21.5 µs | 21.4 µs | 18.4 µs | 0.0 µs | 0.00 | 0.0 | 133 |
| Return a 100-row range | InnoDB | 113.9 µs | 62.2 µs | 26.2 µs | 25.8 µs | 0.0 µs | 0.00 | 0.0 | 399 |
| Return a 100-row range | MyRocks | 143.5 µs | 93.4 µs | 25.5 µs | 26.3 µs | 0.0 µs | 0.00 | 0.0 | 351 |

### Share of server CPU by owner, InnoDB

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| InnoDB | 9.9% | 23.2% | 23.3% |
| Server outside the engine | 90.1% | 76.8% | 76.7% |
| of which in the kernel | 54.1% | 33.9% | 35.4% |
| Samples | 28609 | 32166 | 31578 |

### Share of server CPU by owner, MyRocks

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| RocksDB core | 13.7% | 25.7% | 23.9% |
| RocksDB transaction utilities | 2.2% | 3.7% | 3.8% |
| MyRocks | 4.6% | 11.2% | 12.0% |
| Engine, all of it | 20.5% | 40.5% | 39.8% |
| Server outside the engine | 79.5% | 59.5% | 60.2% |
| of which in the kernel | 46.9% | 25.8% | 26.3% |
| Samples | 29848 | 33708 | 33521 |

### Share of server CPU by owner, InnoDB, sysbench's tests

| Test | InnoDB | Engine, all of it | Server's kernel time | Samples |
|---|---|---|---|---|
| oltp_read_only | 13.3% | 13.3% | 43.5% | 30178 |
| select_random_points | 54.4% | 54.4% | 20.5% | 34566 |
| select_random_ranges | 39.3% | 39.3% | 21.7% | 34459 |

### Share of server CPU by owner, MyRocks, sysbench's tests

| Test | RocksDB core | RocksDB transaction utilities | MyRocks | Engine, all of it | Server's kernel time | Samples |
|---|---|---|---|---|---|---|
| oltp_read_only | 16.1% | 1.6% | 7.3% | 25.0% | 35.9% | 31458 |
| select_random_points | 52.3% | 1.8% | 6.8% | 60.9% | 16.8% | 35244 |
| select_random_ranges | 37.9% | 2.2% | 9.2% | 49.3% | 17.9% | 34961 |

### What the server asked InnoDB for, one client thread

Share of server CPU, by the handler call InnoDB was entered through.

| Test | InnoDB, all | Estimating rows for the optimizer | Finding the first row of a lookup or range | Stepping to the next row | Ranges handed over as a batch | Preparing the row template | Everything else |
|---|---|---|---|---|---|---|---|
| oltp_point_select | 9.9% | 0.0% | 7.1% | 0.0% | 0.0% | 0.8% | 2.0% |
| sum100 | 23.2% | 6.7% | 1.7% | 12.0% | 1.0% | 0.3% | 1.5% |
| range100 | 23.3% | 6.5% | 1.6% | 12.7% | 0.8% | 0.4% | 1.3% |
| oltp_read_only | 13.3% | 2.5% | 4.2% | 4.3% | 0.3% | 0.6% | 1.4% |
| select_random_points | 54.4% | 26.2% | 24.2% | 0.8% | 1.5% | 0.5% | 1.1% |
| select_random_ranges | 39.3% | 23.8% | 6.0% | 6.8% | 1.3% | 0.3% | 1.1% |

### Room against InnoDB, one client thread

InnoDB's share is from the profile; the times are whole-run means.

| Test | InnoDB's share of server CPU | Time per event | InnoDB CPU per event | Waiting on disk per event | InnoDB's part of it | Gain if that part were free | Gain if it were halved | What +10% takes away |
|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 9.9% | 62.7 µs | 4.5 µs | 0.0 µs | 7% | +8% | +4% | more than all of it |
| sum100 | 23.2% | 98.5 µs | 18.5 µs | 0.0 µs | 19% | +23% | +10% | 49% of it |
| range100 | 23.3% | 113.9 µs | 20.6 µs | 0.0 µs | 18% | +22% | +10% | 50% of it |
| oltp_read_only | 13.3% | 1.21 ms | 120.1 µs | 0.8 µs | 10% | +11% | +5% | 91% of it |
| select_random_points | 54.4% | 156.3 µs | 72.7 µs | 0.0 µs | 47% | +87% | +30% | 20% of it |
| select_random_ranges | 39.3% | 146.4 µs | 49.7 µs | 0.0 µs | 34% | +51% | +20% | 27% of it |

### Where a query's time goes, 4 client threads

Per query, not per event. Thread time is the client threads' seconds over the queries they finished.

| Query | Arm | Thread time | Server user | Server kernel | Client CPU | Waiting on disk | Disk reads | KiB read | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|
| oltp_point_select | InnoDB | 22.6 µs | 12.2 µs | 4.2 µs | 5.1 µs | 0.0 µs | 0.00 | 0.0 | 414 |
| oltp_point_select | MyRocks | 27.9 µs | 17.5 µs | 4.3 µs | 5.1 µs | 0.0 µs | 0.00 | 0.0 | 376 |
| sum100 | InnoDB | 46.4 µs | 35.4 µs | 4.4 µs | 5.6 µs | 0.0 µs | 0.00 | 0.0 | 421 |
| sum100 | MyRocks | 68.6 µs | 57.0 µs | 4.6 µs | 5.7 µs | 0.0 µs | 0.00 | 0.0 | 368 |
| range100 | InnoDB | 54.1 µs | 39.4 µs | 4.8 µs | 8.8 µs | 0.0 µs | 0.00 | 0.0 | 421 |
| range100 | MyRocks | 76.6 µs | 60.8 µs | 5.4 µs | 9.0 µs | 0.0 µs | 0.00 | 0.0 | 376 |
| oltp_read_only | InnoDB | 33.6 µs | 24.0 µs | 3.7 µs | 5.4 µs | 0.0 µs | 0.00 | 0.0 | 421 |
| oltp_read_only | MyRocks | 43.6 µs | 33.1 µs | 4.1 µs | 5.8 µs | 0.0 µs | 0.00 | 0.0 | 376 |
| select_random_points | InnoDB | 119.6 µs | 105.4 µs | 4.4 µs | 8.4 µs | 0.0 µs | 0.00 | 0.0 | 421 |
| select_random_points | MyRocks | 169.6 µs | 141.5 µs | 11.1 µs | 10.4 µs | 0.0 µs | 0.00 | 0.0 | 376 |
| select_random_ranges | InnoDB | 114.7 µs | 102.3 µs | 4.2 µs | 6.9 µs | 0.0 µs | 0.00 | 0.0 | 421 |
| select_random_ranges | MyRocks | 129.8 µs | 110.8 µs | 7.2 µs | 8.2 µs | 0.0 µs | 0.00 | 0.0 | 376 |

### Share of server CPU by owner, InnoDB, 4 client threads

| Test | InnoDB | Engine, all of it | Server's kernel time | Samples |
|---|---|---|---|---|
| oltp_point_select | 13.6% | 13.6% | 41.2% | 104718 |
| sum100 | 27.7% | 27.7% | 22.9% | 122430 |
| range100 | 28.6% | 28.6% | 23.1% | 118601 |
| oltp_read_only | 16.9% | 16.9% | 30.7% | 115212 |
| select_random_points | 61.8% | 61.8% | 12.0% | 135788 |
| select_random_ranges | 48.5% | 48.5% | 12.1% | 135935 |

### Share of server CPU by owner, MyRocks, 4 client threads

| Test | RocksDB core | RocksDB transaction utilities | MyRocks | Engine, all of it | Server's kernel time | Samples |
|---|---|---|---|---|---|---|
| oltp_point_select | 18.5% | 3.1% | 6.1% | 27.8% | 32.8% | 111258 |
| sum100 | 30.2% | 4.6% | 12.7% | 47.6% | 15.6% | 131197 |
| range100 | 28.4% | 4.0% | 15.0% | 47.5% | 15.5% | 128961 |
| oltp_read_only | 18.5% | 1.7% | 8.8% | 29.0% | 24.6% | 120410 |
| select_random_points | 58.9% | 1.8% | 7.3% | 68.0% | 9.6% | 136693 |
| select_random_ranges | 40.7% | 2.3% | 10.1% | 53.1% | 11.4% | 136569 |

### What the server asked InnoDB for, 4 client threads

| Test | InnoDB, all | Estimating rows for the optimizer | Finding the first row of a lookup or range | Stepping to the next row | Ranges handed over as a batch | Preparing the row template | Everything else |
|---|---|---|---|---|---|---|---|
| oltp_point_select | 13.6% | 0.0% | 9.3% | 0.0% | 0.0% | 1.0% | 3.3% |
| sum100 | 27.7% | 8.0% | 2.2% | 13.8% | 1.0% | 0.4% | 2.2% |
| range100 | 28.6% | 8.2% | 2.1% | 14.8% | 1.0% | 0.5% | 2.0% |
| oltp_read_only | 16.9% | 2.9% | 5.5% | 5.3% | 0.5% | 0.7% | 2.0% |
| select_random_points | 61.8% | 26.1% | 31.3% | 1.1% | 1.2% | 0.5% | 1.6% |
| select_random_ranges | 48.5% | 25.7% | 11.0% | 8.6% | 1.2% | 0.2% | 1.8% |

### Room against InnoDB, 4 client threads

| Test | InnoDB's share of server CPU | Time per event | InnoDB CPU per event | Waiting on disk per event | InnoDB's part of it | Gain if that part were free | Gain if it were halved | What +10% takes away |
|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 13.6% | 22.6 µs | 2.2 µs | 0.0 µs | 10% | +11% | +5% | 92% of it |
| sum100 | 27.7% | 46.4 µs | 11.0 µs | 0.0 µs | 24% | +31% | +13% | 38% of it |
| range100 | 28.6% | 54.1 µs | 12.7 µs | 0.0 µs | 23% | +31% | +13% | 39% of it |
| oltp_read_only | 16.9% | 537.2 µs | 75.0 µs | 0.0 µs | 14% | +16% | +8% | 65% of it |
| select_random_points | 61.8% | 119.6 µs | 67.8 µs | 0.0 µs | 57% | +131% | +40% | 16% of it |
| select_random_ranges | 48.5% | 114.7 µs | 51.6 µs | 0.0 µs | 45% | +82% | +29% | 20% of it |

### sysbench throughput

Transactions per second. Reads: the best tenth of measured seconds, median in brackets. Writes: the whole run's mean, median second in brackets.

| Test | Threads | InnoDB tps | MyRocks tps | MySup's mark (1.10× the better) |
|---|---|---|---|---|
| oltp_point_select | 1 | 16948 (16056) | 15316 (14252) | 18643 |
| oltp_point_select | 4 | 196022 (187708) | 153056 (146847) | 215624 |
| sum100 | 1 | 11018 (10338) | 8590 (7813) | 12120 |
| sum100 | 4 | 92033 (89029) | 62035 (60478) | 101236 |
| range100 | 1 | 9713 (8835) | 7722 (7101) | 10684 |
| range100 | 4 | 77355 (75179) | 54597 (52757) | 85090 |
| oltp_read_only | 1 | 877 (832) | 759 (716) | 965 |
| oltp_read_only | 4 | 7848 (7585) | 6078 (5829) | 8632 |
| select_random_points | 1 | 6785 (6443) | 5459 (5211) | 7463 |
| select_random_points | 4 | 35484 (33868) | 24913 (23890) | 39033 |
| select_random_ranges | 1 | 7206 (6902) | 6290 (5908) | 7927 |
| select_random_ranges | 4 | 36917 (35346) | 33559 (31292) | 40609 |
| oltp_write_only | 1 | 1537 (1518) | 1265 (1270) | 1690 |
| oltp_write_only | 4 | 4874 (4906) | 3551 (3570) | 5362 |
| oltp_read_write | 1 | 513 (515) | 425 (429) | 565 |
| oltp_read_write | 4 | 1650 (1615) | 1304 (1286) | 1815 |
| oltp_update_index | 1 | 4336 (4352) | 2951 (2911) | 4770 |
| oltp_update_index | 4 | 11258 (11308) | 7084 (7132) | 12384 |
| oltp_update_non_index | 1 | 5158 (5156) | 2920 (2934) | 5674 |
| oltp_update_non_index | 4 | 12720 (12741) | 7117 (7122) | 13992 |
| oltp_insert | 1 | 4956 (4947) | 3089 (3083) | 5451 |
| oltp_insert | 4 | 12513 (12503) | 7367 (7402) | 13764 |

### Where a write's time goes

Whole-run means per event.

| Test | Threads | Arm | tps | Thread time per event | Server CPU | Client CPU | Neither (waiting) | Device flushes per event | KiB written per event | Errors sysbench retried |
|---|---|---|---|---|---|---|---|---|---|---|
| oltp_write_only | 1 | InnoDB | 1537 | 650.7 µs | 329.5 µs | 105.6 µs | 215.6 µs | 1.00 | 7.7 | 0 |
| oltp_write_only | 1 | MyRocks | 1265 | 790.4 µs | 394.1 µs | 110.3 µs | 286.1 µs | 1.00 | 8.7 | 0 |
| oltp_write_only | 4 | InnoDB | 4874 | 820.6 µs | 336.4 µs | 128.2 µs | 356.1 µs | 0.78 | 5.6 | 0 |
| oltp_write_only | 4 | MyRocks | 3551 | 1.13 ms | 448.7 µs | 137.7 µs | 539.9 µs | 0.72 | 7.1 | 6 |
| oltp_read_write | 1 | InnoDB | 513 | 1.95 ms | 1.27 ms | 364.8 µs | 308.9 µs | 1.00 | 10.7 | 0 |
| oltp_read_write | 1 | MyRocks | 425 | 2.35 ms | 1.61 ms | 368.9 µs | 369.9 µs | 1.00 | 8.7 | 0 |
| oltp_read_write | 4 | InnoDB | 1650 | 2.42 ms | 1.18 ms | 454.3 µs | 785.1 µs | 0.92 | 7.2 | 4 |
| oltp_read_write | 4 | MyRocks | 1304 | 3.07 ms | 1.60 ms | 501.0 µs | 965.2 µs | 0.92 | 8.0 | 3 |
| oltp_update_index | 1 | InnoDB | 4336 | 230.6 µs | 115.0 µs | 19.0 µs | 96.6 µs | 1.00 | 7.1 | 0 |
| oltp_update_index | 1 | MyRocks | 2951 | 338.9 µs | 137.3 µs | 24.0 µs | 177.6 µs | 1.00 | 8.3 | 0 |
| oltp_update_index | 4 | InnoDB | 11258 | 355.3 µs | 127.8 µs | 24.0 µs | 203.5 µs | 0.55 | 5.0 | 0 |
| oltp_update_index | 4 | MyRocks | 7084 | 564.6 µs | 168.3 µs | 26.6 µs | 369.8 µs | 0.51 | 4.5 | 0 |
| oltp_update_non_index | 1 | InnoDB | 5158 | 193.9 µs | 80.1 µs | 17.8 µs | 95.9 µs | 1.00 | 4.6 | 0 |
| oltp_update_non_index | 1 | MyRocks | 2920 | 342.5 µs | 136.2 µs | 25.0 µs | 181.2 µs | 1.00 | 8.2 | 0 |
| oltp_update_non_index | 4 | InnoDB | 12720 | 314.5 µs | 92.8 µs | 24.2 µs | 197.4 µs | 0.53 | 2.6 | 0 |
| oltp_update_non_index | 4 | MyRocks | 7117 | 562.1 µs | 168.1 µs | 28.5 µs | 365.4 µs | 0.52 | 4.5 | 0 |
| oltp_insert | 1 | InnoDB | 4956 | 201.8 µs | 81.2 µs | 19.7 µs | 100.9 µs | 1.00 | 4.6 | 0 |
| oltp_insert | 1 | MyRocks | 3089 | 323.8 µs | 124.4 µs | 25.7 µs | 173.7 µs | 1.00 | 8.3 | 0 |
| oltp_insert | 4 | InnoDB | 12513 | 319.7 µs | 93.9 µs | 26.5 µs | 199.3 µs | 0.53 | 2.6 | 0 |
| oltp_insert | 4 | MyRocks | 7367 | 543.0 µs | 148.8 µs | 29.6 µs | 364.6 µs | 0.51 | 4.5 | 0 |

### Every cell

| Test | Threads | Arm | tps | Queries per event | Server CPU per event | Disk reads per event | KiB written per event | p99 ms | Between passes | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 1 | InnoDB | 16948 | 1 | 42.0 µs | 0.00 | 0.0 | 0.11 | 2.2% | 399 |
| oltp_point_select | 1 | MyRocks | 15316 | 1 | 50.3 µs | 0.00 | 0.0 | 0.14 | 4.9% | 350 |
| oltp_point_select | 1 | BLACKHOLE | 19358 | 1 | 35.0 µs | 0.00 | 0.0 | 0.10 | 3.9% | 133 |
| oltp_point_select | 4 | InnoDB | 196022 | 1 | 15.2 µs | 0.00 | 0.0 | 0.08 | 6.8% | 414 |
| oltp_point_select | 4 | MyRocks | 153056 | 1 | 20.6 µs | 0.00 | 0.0 | 0.08 | 3.1% | 376 |
| sum100 | 1 | InnoDB | 11018 | 1 | 73.1 µs | 0.00 | 0.0 | 0.21 | 8.6% | 398 |
| sum100 | 1 | MyRocks | 8590 | 1 | 99.6 µs | 0.00 | 0.0 | 0.28 | 0.5% | 350 |
| sum100 | 1 | BLACKHOLE | 16883 | 1 | 41.9 µs | 0.00 | 0.0 | 0.12 | 3.3% | 133 |
| sum100 | 4 | InnoDB | 92033 | 1 | 38.0 µs | 0.00 | 0.0 | 0.11 | 0.8% | 421 |
| sum100 | 4 | MyRocks | 62035 | 1 | 58.8 µs | 0.00 | 0.0 | 0.16 | 0.8% | 368 |
| range100 | 1 | InnoDB | 9713 | 1 | 79.2 µs | 0.00 | 0.0 | 0.25 | 7.3% | 399 |
| range100 | 1 | MyRocks | 7722 | 1 | 106.5 µs | 0.00 | 0.0 | 0.30 | 4.6% | 351 |
| range100 | 1 | BLACKHOLE | 17700 | 1 | 39.8 µs | 0.00 | 0.0 | 0.11 | 5.1% | 133 |
| range100 | 4 | InnoDB | 77355 | 1 | 42.8 µs | 0.00 | 0.0 | 0.13 | 1.8% | 421 |
| range100 | 4 | MyRocks | 54597 | 1 | 64.1 µs | 0.00 | 0.0 | 0.17 | 1.2% | 376 |
| oltp_read_only | 1 | InnoDB | 877 | 16 | 855.4 µs | 0.01 | 0.0 | 2.07 | 1.8% | 421 |
| oltp_read_only | 1 | MyRocks | 759 | 16 | 1.04 ms | 0.00 | 0.0 | 2.39 | 2.9% | 376 |
| oltp_read_only | 4 | InnoDB | 7848 | 16 | 423.9 µs | 0.00 | 0.0 | 1.04 | 2.9% | 421 |
| oltp_read_only | 4 | MyRocks | 6078 | 16 | 563.8 µs | 0.00 | 0.0 | 1.54 | 4.1% | 376 |
| select_random_points | 1 | InnoDB | 6785 | 1 | 126.7 µs | 0.00 | 0.0 | 0.29 | 5.1% | 421 |
| select_random_points | 1 | MyRocks | 5459 | 1 | 162.6 µs | 0.00 | 0.0 | 0.42 | 3.5% | 376 |
| select_random_points | 4 | InnoDB | 35484 | 1 | 103.7 µs | 0.00 | 0.0 | 0.22 | 5.8% | 421 |
| select_random_points | 4 | MyRocks | 24913 | 1 | 146.0 µs | 0.00 | 0.0 | 0.38 | 0.2% | 376 |
| select_random_ranges | 1 | InnoDB | 7206 | 1 | 119.5 µs | 0.00 | 0.0 | 0.27 | 3.7% | 421 |
| select_random_ranges | 1 | MyRocks | 6290 | 1 | 141.2 µs | 0.00 | 0.0 | 0.38 | 4.5% | 376 |
| select_random_ranges | 4 | InnoDB | 36917 | 1 | 101.2 µs | 0.00 | 0.0 | 0.21 | 7.5% | 421 |
| select_random_ranges | 4 | MyRocks | 33559 | 1 | 109.5 µs | 0.00 | 0.0 | 0.30 | 3.5% | 376 |
| oltp_write_only | 1 | InnoDB | 1537 | 6 | 329.5 µs | 0.00 | 7.7 | 1.31 | 1.3% | 421 |
| oltp_write_only | 1 | MyRocks | 1265 | 6 | 394.1 µs | 0.00 | 8.7 | 1.48 | 3.4% | 440 |
| oltp_write_only | 4 | InnoDB | 4874 | 6 | 336.4 µs | 0.00 | 5.6 | 1.61 | 0.9% | 439 |
| oltp_write_only | 4 | MyRocks | 3551 | 6 | 448.7 µs | 0.04 | 7.1 | 2.24 | 2.5% | 707 |
| oltp_read_write | 1 | InnoDB | 513 | 20 | 1.27 ms | 0.00 | 10.7 | 2.92 | 3.7% | 417 |
| oltp_read_write | 1 | MyRocks | 425 | 20 | 1.61 ms | 0.00 | 8.7 | 3.65 | 2.2% | 375 |
| oltp_read_write | 4 | InnoDB | 1650 | 20 | 1.18 ms | 0.00 | 7.2 | 4.29 | 6.2% | 438 |
| oltp_read_write | 4 | MyRocks | 1304 | 20 | 1.60 ms | 0.00 | 8.0 | 5.28 | 5.2% | 455 |
| oltp_update_index | 1 | InnoDB | 4336 | 1 | 115.0 µs | 0.00 | 7.1 | 0.61 | 8.5% | 427 |
| oltp_update_index | 1 | MyRocks | 2951 | 1 | 137.3 µs | 0.00 | 8.3 | 0.79 | 11.4% | 433 |
| oltp_update_index | 4 | InnoDB | 11258 | 1 | 127.8 µs | 0.00 | 5.0 | 0.93 | 4.9% | 447 |
| oltp_update_index | 4 | MyRocks | 7084 | 1 | 168.3 µs | 0.01 | 4.5 | 1.19 | 9.5% | 606 |
| oltp_update_non_index | 1 | InnoDB | 5158 | 1 | 80.1 µs | 0.00 | 4.6 | 0.49 | 11.1% | 411 |
| oltp_update_non_index | 1 | MyRocks | 2920 | 1 | 136.2 µs | 0.00 | 8.2 | 0.80 | 11.2% | 417 |
| oltp_update_non_index | 4 | InnoDB | 12720 | 1 | 92.8 µs | 0.00 | 2.6 | 0.70 | 3.4% | 419 |
| oltp_update_non_index | 4 | MyRocks | 7117 | 1 | 168.1 µs | 0.01 | 4.5 | 1.21 | 23.1% | 590 |
| oltp_insert | 1 | InnoDB | 4956 | 1 | 81.2 µs | 0.00 | 4.6 | 0.51 | 2.4% | 470 |
| oltp_insert | 1 | MyRocks | 3089 | 1 | 124.4 µs | 0.00 | 8.3 | 0.75 | 19.0% | 433 |
| oltp_insert | 4 | InnoDB | 12513 | 1 | 93.9 µs | 0.00 | 2.6 | 0.70 | 6.0% | 576 |
| oltp_insert | 4 | MyRocks | 7367 | 1 | 148.8 µs | 0.00 | 4.5 | 1.20 | 12.9% | 559 |

### Bytes on disk after the load

| Arm | Table files, MiB | Bytes per row | Per byte stored | SST compression | Insert, s | Settle, s | Allocator |
|---|---|---|---|---|---|---|---|
| InnoDB | 232 | 243 | 1.29 |  | 9 | 0 | the C library's |
| MyRocks | 101 | 106 | 0.57 | ZSTD ×2 | 18 | 14 | the C library's |

### The host while it ran

| Run | CPU | CPU floor, M iterations/s | 16 KiB direct read, µs |
|---|---|---|---|
| mem/20261126T184713Z-b9550f0.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 8.25–10.62 | 45–72 |
| mem/20261126T202334Z-994876f.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 7.66–10.58 | 44–57 |
| mem/20261126T210954Z-607d300.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 8.99–10.41 | 36–48 |
| mem/20261126T214215Z-607d300.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 10.13–10.79 | 45–49 |
| mem/20261126T214901Z-607d300-dirty.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 10.41–10.91 | 34–50 |
| mem/20261127T000109Z-73e0384.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 10.33–11.14 | 32–48 |

## Under the memory limit

16,000,000 rows, engine cache 640 MiB, memory limit 1 GiB.

### Server CPU per query, one client thread

Microseconds: the best tenth of measured seconds, with the median in brackets.

| Query | InnoDB | MyRocks |
|---|---|---|
| Point select by primary key | 58.0 (59.6) | 95.0 (98.7) |
| SUM over a 100-row range | 114.4 (118.7) | 213.1 (227.1) |
| Return a 100-row range | 119.2 (123.9) | 217.2 (230.4) |

### Where a query's time goes, one client thread

Whole-run means, so the columns add up to the wall time less what the client waited.

| Query | Arm | Wall | Server user | Server kernel | Client CPU | Waiting on disk | Disk reads | KiB read | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|
| Point select by primary key | InnoDB | 99.8 µs | 26.1 µs | 33.9 µs | 17.4 µs | 32.8 µs | 0.84 | 13.5 | 763 |
| Point select by primary key | MyRocks | 141.1 µs | 65.2 µs | 34.0 µs | 17.1 µs | 36.3 µs | 0.80 | 6.8 | 935 |
| SUM over a 100-row range | InnoDB | 190.2 µs | 65.7 µs | 53.7 µs | 18.4 µs | 74.4 µs | 1.98 | 31.7 | 763 |
| SUM over a 100-row range | MyRocks | 337.9 µs | 172.3 µs | 55.8 µs | 25.8 µs | 92.3 µs | 1.76 | 16.6 | 935 |
| Return a 100-row range | InnoDB | 206.5 µs | 69.4 µs | 55.3 µs | 24.4 µs | 77.7 µs | 1.97 | 31.6 | 763 |
| Return a 100-row range | MyRocks | 361.8 µs | 174.2 µs | 57.9 µs | 33.2 µs | 103.3 µs | 1.76 | 16.6 | 935 |

### Share of server CPU by owner, InnoDB

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| InnoDB | 36.4% | 48.7% | 48.4% |
| Server outside the engine | 63.6% | 51.3% | 51.6% |
| of which in the kernel | 36.6% | 19.4% | 20.7% |
| Samples | 24388 | 25157 | 25006 |

### Share of server CPU by owner, MyRocks

|  | Point select by primary key | SUM over a 100-row range | Return a 100-row range |
|---|---|---|---|
| RocksDB core | 50.9% | 56.1% | 54.9% |
| RocksDB transaction utilities | 1.1% | 2.0% | 1.8% |
| MyRocks | 2.9% | 5.7% | 6.5% |
| Engine, all of it | 54.9% | 63.9% | 63.2% |
| Server outside the engine | 45.1% | 36.1% | 36.8% |
| of which in the kernel | 23.2% | 12.2% | 13.1% |
| Samples | 26834 | 26402 | 26082 |

### What the server asked InnoDB for, one client thread

Share of server CPU, by the handler call InnoDB was entered through.

| Test | InnoDB, all | Estimating rows for the optimizer | Finding the first row of a lookup or range | Stepping to the next row | Ranges handed over as a batch | Preparing the row template | Everything else |
|---|---|---|---|---|---|---|---|
| oltp_point_select | 36.4% | 0.0% | 34.5% | 0.0% | 0.0% | 0.5% | 1.5% |
| sum100 | 48.7% | 38.3% | 1.6% | 6.7% | 0.8% | 0.3% | 1.0% |
| range100 | 48.4% | 38.1% | 1.4% | 7.0% | 0.7% | 0.3% | 0.9% |

### Room against InnoDB, one client thread

InnoDB's share is from the profile; the times are whole-run means.

| Test | InnoDB's share of server CPU | Time per event | InnoDB CPU per event | Waiting on disk per event | InnoDB's part of it | Gain if that part were free | Gain if it were halved | What +10% takes away |
|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 36.4% | 99.8 µs | 21.9 µs | 32.8 µs | 55% | +121% | +38% | 17% of it |
| sum100 | 48.7% | 190.2 µs | 58.1 µs | 74.4 µs | 70% | +229% | +53% | 13% of it |
| range100 | 48.4% | 206.5 µs | 60.4 µs | 77.7 µs | 67% | +202% | +50% | 14% of it |

### Where a query's time goes, 4 client threads

Per query, not per event. Thread time is the client threads' seconds over the queries they finished.

| Query | Arm | Thread time | Server user | Server kernel | Client CPU | Waiting on disk | Disk reads | KiB read | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|
| oltp_point_select | InnoDB | 135.2 µs | 27.9 µs | 32.2 µs | 19.4 µs | 44.8 µs | 0.84 | 13.5 | 780 |
| oltp_point_select | MyRocks | 195.4 µs | 64.7 µs | 40.9 µs | 25.6 µs | 40.5 µs | 0.79 | 6.8 | 953 |
| oltp_read_only | InnoDB | 189.9 µs | 46.1 µs | 44.1 µs | 25.4 µs | 52.2 µs | 1.02 | 16.2 | 787 |
| oltp_read_only | MyRocks | 249.3 µs | 95.8 µs | 47.2 µs | 27.9 µs | 48.1 µs | 0.94 | 8.4 | 955 |
| select_random_points | InnoDB | 1.31 ms | 270.7 µs | 247.2 µs | 41.6 µs | 769.0 µs | 14.07 | 225.2 | 787 |
| select_random_points | MyRocks | 1.46 ms | 682.5 µs | 237.7 µs | 50.1 µs | 497.1 µs | 10.20 | 83.4 | 958 |
| select_random_ranges | InnoDB | 134.6 µs | 123.8 µs | 2.6 µs | 6.8 µs | 0.0 µs | 0.00 | 0.0 | 787 |
| select_random_ranges | MyRocks | 128.8 µs | 113.2 µs | 5.7 µs | 7.5 µs | 0.0 µs | 0.00 | 0.0 | 974 |

### sysbench throughput

Transactions per second. Reads: the best tenth of measured seconds, median in brackets. Writes: the whole run's mean, median second in brackets.

| Test | Threads | InnoDB tps | MyRocks tps | MySup's mark (1.10× the better) |
|---|---|---|---|---|
| oltp_point_select | 1 | 10579 (10070) | 7608 (7087) | 11637 |
| oltp_point_select | 4 | 32323 (30187) | 21390 (20481) | 35555 |
| sum100 | 1 | 5641 (5264) | 3282 (2941) | 6206 |
| range100 | 1 | 5295 (4849) | 3091 (2777) | 5824 |
| oltp_read_only | 1 | 503 (474) | 340 (317) | 553 |
| oltp_read_only | 4 | 1378 (1313) | 1071 (1003) | 1516 |
| select_random_points | 1 | 1174 (1075) | 895 (803) | 1292 |
| select_random_points | 4 | 3197 (3074) | 2842 (2741) | 3516 |
| select_random_ranges | 1 | 6358 (6186) | 5989 (5773) | 6994 |
| select_random_ranges | 4 | 30929 (29926) | 32348 (31440) | 35583 |
| oltp_write_only | 1 | 1020 (1020) |  | 1122 |
| oltp_write_only | 4 | 2266 (2290) |  | 2493 |
| oltp_read_write | 1 | 279 (280) |  | 307 |
| oltp_read_write | 4 | 754 (753) |  | 829 |
| oltp_update_index | 1 | 2118 (2134) |  | 2330 |
| oltp_update_index | 4 | 4642 (4678) |  | 5106 |
| oltp_update_non_index | 1 | 3088 (3077) |  | 3397 |
| oltp_update_non_index | 4 | 6992 (7002) |  | 7691 |
| oltp_insert | 1 | 5290 (5269) |  | 5819 |
| oltp_insert | 4 | 12677 (12691) |  | 13944 |

### Where a write's time goes

Whole-run means per event.

| Test | Threads | Arm | tps | Thread time per event | Server CPU | Client CPU | Neither (waiting) | Device flushes per event | KiB written per event | Errors sysbench retried |
|---|---|---|---|---|---|---|---|---|---|---|
| oltp_write_only | 1 | InnoDB | 1020 | 980.3 µs | 534.9 µs | 110.3 µs | 335.2 µs | 1.06 | 115.1 | 0 |
| oltp_write_only | 4 | InnoDB | 2266 | 1.76 ms | 596.8 µs | 146.2 µs | 1.02 ms | 0.92 | 114.7 | 0 |
| oltp_read_write | 1 | InnoDB | 279 | 3.58 ms | 2.17 ms | 390.3 µs | 1.02 ms | 1.18 | 197.3 | 0 |
| oltp_read_write | 4 | InnoDB | 754 | 5.31 ms | 2.23 ms | 467.4 µs | 2.61 ms | 1.10 | 174.0 | 0 |
| oltp_update_index | 1 | InnoDB | 2118 | 472.1 µs | 270.8 µs | 27.7 µs | 173.6 µs | 1.03 | 72.6 | 0 |
| oltp_update_index | 4 | InnoDB | 4642 | 861.7 µs | 307.8 µs | 27.4 µs | 526.5 µs | 0.74 | 63.1 | 0 |
| oltp_update_non_index | 1 | InnoDB | 3088 | 323.8 µs | 127.5 µs | 21.3 µs | 175.0 µs | 1.02 | 33.9 | 0 |
| oltp_update_non_index | 4 | InnoDB | 6992 | 572.1 µs | 145.0 µs | 26.1 µs | 401.0 µs | 0.64 | 32.4 | 0 |
| oltp_insert | 1 | InnoDB | 5290 | 189.0 µs | 78.8 µs | 18.7 µs | 91.5 µs | 1.00 | 4.6 | 0 |
| oltp_insert | 4 | InnoDB | 12677 | 315.5 µs | 94.0 µs | 26.3 µs | 195.2 µs | 0.54 | 3.4 | 0 |

### Every cell

| Test | Threads | Arm | tps | Queries per event | Server CPU per event | Disk reads per event | KiB written per event | p99 ms | Between passes | Peak MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| oltp_point_select | 1 | InnoDB | 10579 | 1 | 58.0 µs | 0.84 | 0.0 | 0.20 | 3.3% | 763 |
| oltp_point_select | 1 | MyRocks | 7608 | 1 | 95.0 µs | 0.80 | 0.0 | 0.33 | 0.0% | 935 |
| oltp_point_select | 4 | InnoDB | 32323 | 1 | 56.4 µs | 0.84 | 0.0 | 0.34 | 1.8% | 780 |
| oltp_point_select | 4 | MyRocks | 21390 | 1 | 102.0 µs | 0.79 | 0.0 | 0.47 | 1.3% | 953 |
| sum100 | 1 | InnoDB | 5641 | 1 | 114.4 µs | 1.98 | 0.0 | 0.42 | 0.1% | 763 |
| sum100 | 1 | MyRocks | 3282 | 1 | 213.1 µs | 1.76 | 0.0 | 0.72 | 4.3% | 935 |
| range100 | 1 | InnoDB | 5295 | 1 | 119.2 µs | 1.97 | 0.0 | 0.47 | 2.2% | 763 |
| range100 | 1 | MyRocks | 3091 | 1 | 217.2 µs | 1.76 | 0.0 | 0.76 | 4.8% | 935 |
| oltp_read_only | 1 | InnoDB | 503 | 16 | 1.25 ms | 16.29 | 0.0 | 3.42 | 0.2% | 785 |
| oltp_read_only | 1 | MyRocks | 340 | 16 | 2.04 ms | 14.99 | 0.0 | 5.82 | 0.6% | 954 |
| oltp_read_only | 4 | InnoDB | 1378 | 16 | 1.39 ms | 16.24 | 0.0 | 4.78 | 4.0% | 787 |
| oltp_read_only | 4 | MyRocks | 1071 | 16 | 2.18 ms | 15.01 | 0.0 | 6.73 | 7.9% | 955 |
| select_random_points | 1 | InnoDB | 1174 | 1 | 457.5 µs | 14.08 | 0.0 | 1.67 | 0.6% | 787 |
| select_random_points | 1 | MyRocks | 895 | 1 | 810.3 µs | 10.18 | 0.0 | 2.27 | 5.2% | 968 |
| select_random_points | 4 | InnoDB | 3197 | 1 | 494.4 µs | 14.07 | 0.0 | 2.46 | 1.3% | 787 |
| select_random_points | 4 | MyRocks | 2842 | 1 | 891.2 µs | 10.20 | 0.0 | 3.04 | 0.4% | 958 |
| select_random_ranges | 1 | InnoDB | 6358 | 1 | 138.9 µs | 0.00 | 0.0 | 0.28 | 1.2% | 787 |
| select_random_ranges | 1 | MyRocks | 5989 | 1 | 150.5 µs | 0.00 | 0.0 | 0.33 | 0.1% | 967 |
| select_random_ranges | 4 | InnoDB | 30929 | 1 | 122.5 µs | 0.00 | 0.0 | 0.23 | 2.0% | 787 |
| select_random_ranges | 4 | MyRocks | 32348 | 1 | 115.7 µs | 0.00 | 0.0 | 0.27 | 2.7% | 974 |
| oltp_write_only | 1 | InnoDB | 1020 | 6 | 534.9 µs | 2.78 | 115.1 | 6.79 |  | 769 |
| oltp_write_only | 4 | InnoDB | 2266 | 6 | 596.8 µs | 2.80 | 114.7 | 9.73 |  | 792 |
| oltp_read_write | 1 | InnoDB | 279 | 20 | 2.17 ms | 21.84 | 197.3 | 11.45 |  | 769 |
| oltp_read_write | 4 | InnoDB | 754 | 20 | 2.23 ms | 21.69 | 174.0 | 15.55 |  | 782 |
| oltp_update_index | 1 | InnoDB | 2118 | 1 | 270.8 µs | 0.91 | 72.6 | 3.62 |  | 775 |
| oltp_update_index | 4 | InnoDB | 4642 | 1 | 307.8 µs | 0.92 | 63.1 | 7.04 |  | 788 |
| oltp_update_non_index | 1 | InnoDB | 3088 | 1 | 127.5 µs | 0.84 | 33.9 | 2.57 |  | 765 |
| oltp_update_non_index | 4 | InnoDB | 6992 | 1 | 145.0 µs | 0.84 | 32.4 | 4.65 |  | 781 |
| oltp_insert | 1 | InnoDB | 5290 | 1 | 78.8 µs | 0.00 | 4.6 | 0.42 |  | 697 |
| oltp_insert | 4 | InnoDB | 12677 | 1 | 94.0 µs | 0.00 | 3.4 | 0.67 |  | 771 |

### Bytes on disk after the load

| Arm | Table files, MiB | Bytes per row | Per byte stored | SST compression | Insert, s | Settle, s | Allocator |
|---|---|---|---|---|---|---|---|
| InnoDB | 3653 | 239 | 1.27 |  | 185 | 0 | the C library's |
| MyRocks | 1628 | 107 | 0.57 | ZSTD ×26 | 252 | 130 | libjemalloc.so.2 |

### The host while it ran

| Run | CPU | CPU floor, M iterations/s | 16 KiB direct read, µs |
|---|---|---|---|
| limit/20261126T192759Z-8886b7c.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 9.46–10.52 | 48–59 |
| limit/20261126T224815Z-7982e90.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 9.86–10.69 | 37–46 |
| limit/20261126T233841Z-73e0384.json | Intel(R) Xeon(R) Processor @ 2.10GHz | 10.71–10.96 | 34–36 |

