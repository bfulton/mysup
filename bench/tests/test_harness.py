"""Checks of the harness's own arithmetic. No server needed.

    cd bench && python3 -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mysupbench import plan, probes, profile, report, sysbench  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def stack(*frames):
    return "\n" + "".join(f"\t{i:x} {sym} ({dso})\n"
                          for i, (sym, dso) in enumerate(frames, 1))


SERVER = "/usr/sbin/mariadbd"
PLUGIN = "/usr/lib/mysql/plugin/ha_rocksdb.so"
LIBC = "/usr/lib/x86_64-linux-gnu/libc.so.6"
ROOT = ("start_thread", LIBC)


class Attribution(unittest.TestCase):
    def owners(self, *stacks):
        return profile.attribute("".join(stacks))["owners"]

    def test_innermost_engine_frame_owns_the_sample(self):
        # libc under RocksDB under the transaction wrapper under MyRocks:
        # the core owns it.
        got = self.owners(stack(
            ("__memcmp_evex_movbe", LIBC),
            ("rocksdb::DBIter::Seek(rocksdb::Slice const&)", PLUGIN),
            ("rocksdb::BaseDeltaIterator::Seek(rocksdb::Slice const&)", PLUGIN),
            ("myrocks::ha_rocksdb::index_read_map_impl(unsigned char*)",
             PLUGIN),
            ("handler::ha_index_read_map(unsigned char*)", SERVER), ROOT))
        self.assertEqual(got, {"rocksdb_core": 1})

    def test_transaction_utilities_are_apart_from_the_core(self):
        got = self.owners(
            stack(("rocksdb::WriteBatchWithIndex::Rep::ClearIndex()", PLUGIN),
                  ROOT),
            stack(("rocksdb::PessimisticTransaction::Clear()", PLUGIN), ROOT),
            stack(("rocksdb::TransactionBaseImpl::SetSavePoint()", PLUGIN),
                  ROOT),
            stack(("rocksdb::PointLockManager::UnLock("
                   "rocksdb::PessimisticTransaction*, "
                   "rocksdb::LockTracker const&, rocksdb::Env*)", PLUGIN),
                  ROOT))
        self.assertEqual(got, {"rocksdb_txn": 4})

    def test_a_core_function_taking_a_transaction_is_core(self):
        # The class name appears only among the arguments.
        got = self.owners(stack(
            ("rocksdb::DBImpl::GetImpl(rocksdb::ReadOptions const&, "
             "rocksdb::Slice const&, rocksdb::DBImpl::GetImplOptions&)",
             PLUGIN), ROOT))
        self.assertEqual(got, {"rocksdb_core": 1})

    def test_myrocks_method_with_rocksdb_arguments_is_myrocks(self):
        got = self.owners(stack(
            ("myrocks::Rdb_transaction_impl::get(rocksdb::ColumnFamilyHandle*,"
             " rocksdb::Slice const&, rocksdb::PinnableSlice*) const",
             PLUGIN), ROOT))
        self.assertEqual(got, {"myrocks": 1})

    def test_server_code_called_from_an_engine_is_the_engines(self):
        got = self.owners(stack(
            ("Field_long::unpack(unsigned char*)", SERVER),
            ("myrocks::Rdb_converter::decode(unsigned char*)", PLUGIN),
            ROOT))
        self.assertEqual(got, {"myrocks": 1})

    def test_unnamed_plugin_frames_fall_to_their_caller(self):
        got = self.owners(stack(
            ("[unknown]", PLUGIN),
            ("myrocks::ha_rocksdb::external_lock(THD*, int)", PLUGIN), ROOT))
        self.assertEqual(got, {"myrocks": 1})

    def test_innodb_is_known_by_its_entry_points(self):
        got = self.owners(
            stack(("btr_cur_t::search_leaf(dtuple_t const*)", SERVER),
                  ("row_search_mvcc(unsigned char*)", SERVER),
                  ("ha_innobase::index_read(unsigned char*)", SERVER),
                  ("handler::ha_index_read_map(unsigned char*)", SERVER),
                  ROOT),
            stack(("trx_commit_for_mysql(trx_t*)", SERVER),
                  ("innobase_commit(handlerton*, THD*, bool)", SERVER),
                  ("ha_commit_trans(THD*, bool)", SERVER), ROOT))
        self.assertEqual(got, {"innodb": 2})

    def test_no_engine_frame_is_the_server(self):
        text = stack(("entry_SYSCALL_64", "[kernel.kallsyms]"),
                     ("__send", LIBC),
                     ("Protocol::send_result_set_row(List<Item>*)", SERVER),
                     ROOT)
        got = profile.attribute(text)
        self.assertEqual(got["owners"], {"server": 1})
        self.assertEqual(got["kernel"], {"server": 1})
        self.assertEqual(got["rooted"], 1)

    def test_an_engines_own_thread_owns_what_no_frame_claims(self):
        # The page cleaner writes pages out through no handler call.
        flush = ("buf_flush_page_cleaner()", SERVER)
        text = ("page_cleaner \n\t1 pwrite64 (" + LIBC + ")\n\t2 "
                + flush[0] + " (" + SERVER + ")\n\n"
                "one_connection \n\t1 Protocol::net_store_data() ("
                + SERVER + ")\n\n"
                "ib_tpool_worker \n\t1 fil_aio_callback() (" + SERVER
                + ")\n\n"
                "rocksdb:low \n\t1 __memmove_avx512 (" + LIBC + ")\n")
        got = profile.attribute(text)
        self.assertEqual(got["owners"],
                         {"innodb": 2, "server": 1, "rocksdb_core": 1})
        self.assertEqual(got["own_threads"],
                         {"innodb": 2, "rocksdb_core": 1})
        self.assertEqual(got["threads"]["one_connection"], 1)

    def test_a_query_thread_decides_nothing(self):
        self.assertIsNone(profile.thread_owner("one_connection"))
        self.assertIsNone(profile.thread_owner("mariadbd"))
        self.assertIsNone(profile.thread_owner(None))
        self.assertEqual(profile.thread_owner("ib_pg_flush_co"), "innodb")
        self.assertEqual(profile.thread_owner("myrocks-bg"), "myrocks")

    def test_a_truncated_stack_is_counted_as_not_rooted(self):
        got = profile.attribute(stack(("[unknown]", "[unknown]")))
        self.assertEqual((got["samples"], got["rooted"]), (1, 0))


class Plan(unittest.TestCase):
    def test_suites_name_real_workloads(self):
        for cells in plan.SUITES.values():
            for workload, threads in cells:
                self.assertIn(workload, plan.WORKLOADS)
                self.assertGreater(threads, 0)

    def test_one_statement_workloads_isolate_one_range_type(self):
        for name, on in (("sum100", "sum_ranges"),
                         ("range100", "simple_ranges")):
            opts = plan.WORKLOADS[name]["opts"]
            self.assertIn(f"--{on}=1", opts)
            self.assertIn("--point_selects=0", opts)
            self.assertIn("--skip_trx=on", opts)
            ones = [o for o in opts if o.endswith("=1")]
            self.assertEqual(ones, [f"--{on}=1"])

    def test_cache_reaches_the_engine_that_uses_it(self):
        s = dict(plan.arm_settings("innodb", 123))
        self.assertEqual(s["innodb_buffer_pool_size"], 123)
        s = dict(plan.arm_settings("myrocks", 123))
        self.assertEqual(s["rocksdb_block_cache_size"], 123)
        self.assertEqual(s["innodb_buffer_pool_size"], 32 * plan.MIB)

    def test_an_allocator_is_named_only_for_an_arm(self):
        for cond in plan.CONDITIONS.values():
            for arm, lib in cond["malloc"].items():
                self.assertIn(arm, plan.ARMS)
                self.assertTrue(lib.startswith("lib"))

    def test_baselines_are_arms(self):
        for arm in plan.BASELINE_ARMS:
            self.assertIn(arm, plan.ARMS)


class Sysbench(unittest.TestCase):
    def test_reads_what_sysbench_printed(self):
        # The fixture is a real three-second oltp_read_only run, two
        # threads; the numbers below were read off it by eye.
        with open(os.path.join(HERE, "sysbench-1.0.20.out")) as f:
            got = sysbench.parse(f.read())
        want = {
            "reads": 59318, "writes": 0, "other": 8474, "queries": 67792,
            "transactions": 4237, "ignored_errors": 0, "reconnects": 0,
            "seconds": 3.0032, "lat_min_ms": 0.44, "lat_avg_ms": 1.41,
            "lat_max_ms": 6.41, "lat_p99_ms": 3.07,
            "tps_by_second": [1383.68, 1298.53, 1550.98],
            "qps_by_second": [22161.89, 20768.54, 24815.71],
        }
        self.assertEqual(got, want)

    def test_output_without_a_summary_is_an_error(self):
        with self.assertRaises(ValueError):
            sysbench.parse("FATAL: unable to connect to MySQL server\n")


class Threads(unittest.TestCase):
    def test_this_process_has_a_named_thread_with_cpu(self):
        got = probes.thread_cpu(os.getpid())
        name, cpu = got[os.getpid()]
        self.assertTrue(name)
        self.assertGreaterEqual(cpu, 0.0)

    def test_delta_keeps_only_threads_alive_at_both_ends(self):
        before = {1: ("page_cleaner", 1.0), 2: ("one_connection", 5.0)}
        after = {1: ("page_cleaner", 1.5), 3: ("one_connection", 9.0),
                 4: ("page_cleaner", 0.0)}
        self.assertEqual(probes.thread_cpu_delta(after, before),
                         {"page_cleaner": 0.5})


class Quartiles(unittest.TestCase):
    def test_median_ignores_a_bad_stretch(self):
        calm = [100.0] * 90
        disturbed = [160.0] * 10
        lo, mid, hi = report.quartiles(calm + disturbed)
        self.assertEqual((lo, mid, hi), (100.0, 100.0, 100.0))


    def test_nearest_rank_percentile(self):
        xs = list(range(1, 101))
        self.assertEqual(report.percentile(xs, 10), 10)
        self.assertEqual(report.percentile(xs, 90), 90)
        self.assertEqual(report.percentile([5.0], 10), 5.0)
        self.assertEqual(report.percentile([1, 2, 3], 90), 3)

    def test_best_tenth_ignores_a_slow_pass(self):
        quiet = [100.0 + i * 0.01 for i in range(120)]
        slow = [112.0 + i * 0.01 for i in range(60)]
        self.assertLess(report.percentile(quiet + slow, 10), 100.2)
        self.assertGreater(report.quartiles(quiet + slow)[1], 100.8)


if __name__ == "__main__":
    unittest.main()
