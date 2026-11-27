# MySup

A MySQL storage engine built on [supdb](https://github.com/bfulton/supdb), in
the way MyRocks is built on RocksDB.

**Goal:** a double-digit throughput improvement on sysbench against both
InnoDB and MyRocks, on the same server and host.

## Status

No engine yet. M0, the baselines, is done but for two open points: InnoDB and
MyRocks are measured by a harness that is kept, the brief's tables are taken
again, and the goal is fixed as a rule the harness can test. Open: MyRocks
has no configuration yet that survives the write tests under the memory
limit, and supdb itself has not been measured on sysbench's rows.

| where | what |
|---|---|
| [`docs/brief.md`](docs/brief.md) | the project brief: what is decided, what is open, the design, the milestones |
| [`docs/baselines.md`](docs/baselines.md) | M0: the goal as registered, what the rivals measure, what that changes in the brief |
| [`docs/tables/`](docs/tables/) | every table, drawn from the rows, one file per server |
| [`docs/servers.md`](docs/servers.md) | MySQL or MariaDB: what was read, with sources |
| [`bench/`](bench/) | the harness, its rows under `bench/runs/`, and how a row becomes a number |

## Reproducing the baselines

On Ubuntu 24.04, as root, on a host doing nothing else:

```sh
sh bench/setup.sh
cd bench && python3 -m mysupbench run --condition smoke --arms innodb,myrocks
```

[`bench/README.md`](bench/README.md) has the full runs and what each
measures.
