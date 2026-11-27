#!/usr/bin/env python3
"""What the optimizer's row estimates cost InnoDB in select_random_points,
measured by switching them off.

    python3 bench/tools/divelimit.py /path/to/unpacked/server

The test sends `k IN (ten values)`. For each value the optimizer asks the
engine how many rows match, and InnoDB descends the index to answer.
`eq_range_index_dive_limit` at or below the number of values makes the
optimizer use the index's stored statistics instead. The two settings take
turns on one server, in memory, at one and at four client threads.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))
from mysupbench import run as harness, sysbench  # noqa: E402

QUERY = ("SELECT id, k, c, pad FROM sbtest1 WHERE k IN "
         "(101,1202,2303,3404,4505,5606,6707,7808,8909,9910)")


def main():
    with tempfile.TemporaryDirectory() as scratch:
        r = harness.Run("mem", "/var/tmp/mysup-bench", scratch, 1, 20, None,
                        sys.argv[1])
        inst, _ = r.prepare("innodb")
        r._start(inst, "innodb", restore=True)
        try:
            default = inst.sql("SELECT @@global.eq_range_index_dive_limit")
            print("server default:", default[0][0])
            for limit in (200, 5):
                inst.sql(f"SET GLOBAL eq_range_index_dive_limit={limit}")
                print(f"limit {limit}:")
                print(inst.sql_text("EXPLAIN " + QUERY, db="sbtest"))
            for threads in (1, 4):
                for turn in range(3):
                    for limit in (200, 5):
                        inst.sql("SET GLOBAL "
                                 f"eq_range_index_dive_limit={limit}")
                        row = sysbench.measured(inst, r.dev, r._cmd(
                            inst, "innodb", "select_random_points", threads,
                            15, 100 + turn))
                        qps = sorted(row["qps_by_second"])
                        print(f"x{threads} limit {limit:3}: "
                              f"{qps[len(qps) // 2]:8.0f} qps median second, "
                              f"{row['server']['cpu_s'] / row['queries'] * 1e6:6.1f}"
                              " us server CPU per query", flush=True)
        finally:
            inst.stop()
            inst.cgroup.destroy()


if __name__ == "__main__":
    main()
