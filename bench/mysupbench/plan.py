"""What is measured: the arms, the conditions, the workloads.

This file is the registered definition of the baseline. A number in
`bench/runs/` means what these tables say and nothing else, so a change
here is a change to the benchmark and belongs in the same commit as the
rows it produces.
"""

MIB = 1 << 20
GIB = 1 << 30

# -- conditions ----------------------------------------------------------
#
# rows:   rows in the one table. sysbench's select_random_points and
#         select_random_ranges refuse more than one table, so every test
#         runs against one table and the two conditions differ in its size.
# cache:  the engine's own cache (InnoDB buffer pool, RocksDB block cache).
# limit:  the cgroup memory limit on the server process, or None.
# warmup: seconds of the workload itself before the first measured run.

CONDITIONS = {
    "mem": {"rows": 1_000_000, "cache": 2 * GIB, "limit": None,
            "warmup": 10, "preload": True},
    "limit": {"rows": 16_000_000, "cache": 640 * MIB, "limit": 1 * GIB,
              "warmup": 60, "preload": False},
    # The harness's own check: seconds to run, proves nothing about engines.
    "smoke": {"rows": 50_000, "cache": 256 * MIB, "limit": 1 * GIB,
              "warmup": 2, "preload": True},
}

# A sysbench row as the table declares it: id INT, k INT, c CHAR(120),
# pad CHAR(60), in latin1. Bytes on disk are reported against this.
ROW_BYTES = 4 + 4 + 120 + 60

# -- arms ----------------------------------------------------------------
#
# Every setting an arm changes from the server's default is listed here
# and written to the arm's my.cnf. {cache} is the condition's cache size.

COMMON = [
    ("skip-networking", None),
    ("character-set-server", "latin1"),
    ("collation-server", "latin1_swedish_ci"),
    ("max_connections", 256),
    # A buffer pool reloaded at startup makes a cold start partly warm.
    ("innodb_buffer_pool_load_at_startup", "OFF"),
    ("innodb_buffer_pool_dump_at_shutdown", "OFF"),
]

# The column-family options MyRocks' own tuning page gives in its example
# (facebook/mysql-5.6 wiki, "my.cnf tuning"), without the lines that size
# it for a 32 GB cache: LZ4 above the last level, ZSTD in it, a bloom
# filter, and index and filter blocks charged to the block cache so the
# cache size bounds them.
MYROCKS_CF = (
    "compression_per_level=kLZ4Compression;"
    "bottommost_compression=kZSTD;"
    "compression_opts=-14:6:0;"
    "block_based_table_factory={cache_index_and_filter_blocks=1;"
    "filter_policy=bloomfilter:10:false;whole_key_filtering=1};"
    "level_compaction_dynamic_level_bytes=true;"
    "optimize_filters_for_hits=true;"
    "compaction_pri=kMinOverlappingRatio"
)

# InnoDB is compiled in and holds system tables, so the other arms keep it
# but give it no memory to speak of.
INNODB_IDLE = [("innodb_buffer_pool_size", 32 * MIB)]

ARMS = {
    "innodb": {
        "engine": "innodb",
        "title": "InnoDB",
        "settings": [
            ("innodb_buffer_pool_size", "{cache}"),
            ("innodb_flush_method", "O_DIRECT"),
            ("innodb_log_file_size", 1 * GIB),
            ("innodb_flush_log_at_trx_commit", 1),
        ],
    },
    "myrocks": {
        "engine": "rocksdb",
        "title": "MyRocks",
        "settings": INNODB_IDLE + [
            ("plugin-load-add", "ha_rocksdb.so"),
            ("rocksdb_block_cache_size", "{cache}"),
            ("rocksdb_block_size", 16384),
            ("rocksdb_use_direct_reads", "ON"),
            ("rocksdb_use_direct_io_for_flush_and_compaction", "ON"),
            ("rocksdb_flush_log_at_trx_commit", 1),
            ("rocksdb_default_cf_options", MYROCKS_CF),
        ],
    },
    # MyRocks as the server ships it: the arm the brief measured. Kept to
    # tie this harness to those numbers and to show what the tuned arm
    # changes. Not a baseline for the goal.
    "myrocks-default": {
        "engine": "rocksdb",
        "title": "MyRocks, server defaults",
        "settings": INNODB_IDLE + [
            ("plugin-load-add", "ha_rocksdb.so"),
            ("rocksdb_block_cache_size", "{cache}"),
            ("rocksdb_use_direct_reads", "ON"),
            ("rocksdb_use_direct_io_for_flush_and_compaction", "ON"),
            ("rocksdb_flush_log_at_trx_commit", 1),
        ],
    },
    # No lookup, no row: what a query costs before any engine.
    "blackhole": {
        "engine": "blackhole",
        "title": "BLACKHOLE",
        "settings": INNODB_IDLE + [("plugin-load-add", "ha_blackhole.so")],
    },
}

BASELINE_ARMS = ("innodb", "myrocks")


def arm_settings(arm, cache):
    out = list(COMMON)
    for k, v in ARMS[arm]["settings"]:
        out.append((k, cache if v == "{cache}" else v))
    return out


# -- workloads -----------------------------------------------------------
#
# Each is one sysbench 1.0 test with the options given. `per_event` is the
# number of statements one event sends, for the reader; the rows record
# what sysbench counted.

_ONLY = ["--skip_trx=on", "--point_selects=0", "--simple_ranges=0",
         "--sum_ranges=0", "--order_ranges=0", "--distinct_ranges=0",
         "--range_size=100"]


def _only(which):
    return [o if not o.startswith(f"--{which}=") else f"--{which}=1"
            for o in _ONLY]


WORKLOADS = {
    # One statement per event, so CPU per query is CPU per event.
    "oltp_point_select": {
        "test": "oltp_point_select", "opts": [], "writes": False,
        "what": "SELECT c FROM sbtest1 WHERE id=?"},
    "sum100": {
        "test": "oltp_read_only", "opts": _only("sum_ranges"),
        "writes": False,
        "what": "SELECT SUM(k) FROM sbtest1 WHERE id BETWEEN ? AND ?+99"},
    "range100": {
        "test": "oltp_read_only", "opts": _only("simple_ranges"),
        "writes": False,
        "what": "SELECT c FROM sbtest1 WHERE id BETWEEN ? AND ?+99"},
    # sysbench's tests as shipped.
    "oltp_read_only": {
        "test": "oltp_read_only", "opts": [], "writes": False,
        "what": "BEGIN; 10 point selects; 4 range queries of 100 rows "
                "(plain, SUM, ORDER BY, DISTINCT); COMMIT"},
    "select_random_points": {
        "test": "select_random_points", "opts": [], "writes": False,
        "what": "SELECT id,k,c,pad FROM sbtest1 WHERE k IN (10 values)"},
    "select_random_ranges": {
        "test": "select_random_ranges", "opts": [], "writes": False,
        "what": "SELECT count(k) FROM sbtest1 WHERE k BETWEEN ? AND ?+5 "
                "OR ... (10 ranges)"},
    "oltp_write_only": {
        "test": "oltp_write_only", "opts": [], "writes": True,
        "what": "BEGIN; UPDATE k; UPDATE c; DELETE; INSERT; COMMIT"},
    "oltp_read_write": {
        "test": "oltp_read_write", "opts": [], "writes": True,
        "what": "oltp_read_only's reads and oltp_write_only's writes in "
                "one transaction"},
    "oltp_update_index": {
        "test": "oltp_update_index", "opts": [], "writes": True,
        "what": "UPDATE sbtest1 SET k=k+1 WHERE id=?"},
    "oltp_update_non_index": {
        "test": "oltp_update_non_index", "opts": [], "writes": True,
        "what": "UPDATE sbtest1 SET c=? WHERE id=?"},
    "oltp_insert": {
        "test": "oltp_insert", "opts": [], "writes": True,
        "what": "INSERT INTO sbtest1 (id,k,c,pad) VALUES (0,?,?,?)"},
}

SUITES = {
    # The brief's per-query tables: one statement, one client thread.
    "micro": [("oltp_point_select", 1), ("sum100", 1), ("range100", 1)],
    "read": [(w, t) for w in ("oltp_point_select", "oltp_read_only",
                              "select_random_points", "select_random_ranges")
             for t in (1, 4)],
    "write": [(w, t) for w in ("oltp_write_only", "oltp_read_write",
                               "oltp_update_index", "oltp_update_non_index",
                               "oltp_insert")
              for t in (1, 4)],
}

# BLACKHOLE answers nothing, so only the one-statement workloads mean
# anything on it.
BLACKHOLE_WORKLOADS = {"oltp_point_select", "sum100", "range100"}

# The plans the optimizer chose, recorded per arm so that a difference in
# plan is seen and not mistaken for a difference in engine.
EXPLAINS = {
    "oltp_point_select": "SELECT c FROM sbtest1 WHERE id=500",
    "sum100": "SELECT SUM(k) FROM sbtest1 WHERE id BETWEEN 500 AND 599",
    "range100": "SELECT c FROM sbtest1 WHERE id BETWEEN 500 AND 599",
    "order100": "SELECT c FROM sbtest1 WHERE id BETWEEN 500 AND 599 "
                "ORDER BY c",
    "distinct100": "SELECT DISTINCT c FROM sbtest1 WHERE id BETWEEN 500 "
                   "AND 599 ORDER BY c",
    "select_random_points":
        "SELECT id, k, c, pad FROM sbtest1 WHERE k IN "
        "(101,1202,2303,3404,4505,5606,6707,7808,8909,9910)",
    "select_random_ranges":
        "SELECT count(k) FROM sbtest1 WHERE " + " OR ".join(
            f"k BETWEEN {a} AND {a + 5}" for a in range(1000, 11000, 1000)),
}
