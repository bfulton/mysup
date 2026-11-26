import argparse
import os

from . import plan


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser(
        prog="mysupbench",
        description="MySup's baseline harness. See bench/README.md.")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="load the arms if needed, then measure")
    r.add_argument("--condition", required=True, choices=plan.CONDITIONS)
    r.add_argument("--arms", required=True,
                   help="comma-separated: " + ", ".join(plan.ARMS))
    r.add_argument("--suite", default="micro",
                   help="comma-separated: " + ", ".join(plan.SUITES))
    r.add_argument("--workloads", help="keep only these workloads")
    r.add_argument("--threads", help="keep only these thread counts")
    r.add_argument("--profile",
                   help="workloads to profile with perf after measuring")
    r.add_argument("--passes", type=int, default=2,
                   help="times to go round the arms; the host's speed "
                        "drifts, and a pass apart shows it")
    r.add_argument("--reps", type=int, default=3,
                   help="measured runs per workload in each pass")
    r.add_argument("--time", type=int, default=20,
                   help="seconds per measured run")
    r.add_argument("--warmup", type=int,
                   help="seconds of warm-up per workload "
                        "(default: the condition's)")
    r.add_argument("--server",
                   help="a directory holding another server's packages "
                        "unpacked; default is the MariaDB on PATH")
    r.add_argument("--workdir", default="/var/tmp/mysup-bench",
                   help="where data directories live; its block device is "
                        "the one whose reads are counted")
    r.add_argument("--out", default=os.path.join(here, "runs"))

    t = sub.add_parser("report", help="tables from the committed rows")
    t.add_argument("--runs", default=os.path.join(here, "runs"))
    t.add_argument("--conditions", default="mem,limit")
    t.add_argument("--server", default="mariadb-10.11.14",
                   help="the server whose tables to draw, as rows name it")

    args = p.parse_args()
    if args.cmd == "run":
        from .run import main_run
        main_run(args)
    else:
        from .report import main_report
        main_report(args)


if __name__ == "__main__":
    main()
