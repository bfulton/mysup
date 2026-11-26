"""Checks of the harness's own arithmetic. No server needed.

    cd bench && python3 -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mysupbench import plan, profile, report  # noqa: E402


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

    def test_baselines_are_arms(self):
        for arm in plan.BASELINE_ARMS:
            self.assertIn(arm, plan.ARMS)


class Quartiles(unittest.TestCase):
    def test_median_ignores_a_bad_stretch(self):
        calm = [100.0] * 90
        disturbed = [160.0] * 10
        lo, mid, hi = report.quartiles(calm + disturbed)
        self.assertEqual((lo, mid, hi), (100.0, 100.0, 100.0))


if __name__ == "__main__":
    unittest.main()
