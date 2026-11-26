# MySup

A MySQL storage engine built on [supdb](https://github.com/bfulton/supdb), in
the way MyRocks is built on RocksDB.

**Goal:** a double-digit throughput improvement on sysbench against both
InnoDB and MyRocks, on the same server and host.

## Status

No engine yet. M0, the baselines, is in progress: the harness exists and
its first rows are being taken.

| where | what |
|---|---|
| [`docs/brief.md`](docs/brief.md) | the project brief: what is decided, what is open, the design, the milestones |
| [`bench/`](bench/) | the harness that measures InnoDB and MyRocks, and its rows under `bench/runs/` |

## Reproducing the baselines

On Ubuntu 24.04, as root, on a host doing nothing else:

```sh
sh bench/setup.sh
cd bench && python3 -m mysupbench run --condition smoke --arms innodb,myrocks
```

[`bench/README.md`](bench/README.md) has the full runs and what each
measures.
