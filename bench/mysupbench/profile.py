"""Where the server's CPU goes, by who owns the code.

`perf record -e cpu-clock -g` on the server while one client thread runs a
workload, then each sample is given to exactly one owner:

    the innermost frame of its call stack that belongs to an engine names
    the owner; a sample with no engine frame belongs to the engine whose
    own thread it was taken in, and otherwise to the server.

So time in libc or the kernel is charged to whichever engine code called
it, and an engine's callbacks into the server (field packing, say) are
charged to the engine frame they return to. An engine's own threads, the
ones that flush and purge behind the queries, are known by the names the
server gives them. The owners:

    rocksdb_core  RocksDB proper: what a RocksDB-compatible layer replaces
    rocksdb_txn   RocksDB's transaction and write-batch-with-index
                  utilities: a layer keeps these
    myrocks       the storage engine written against RocksDB
    innodb        InnoDB, where the server's debug symbols are installed
    server        everything else: parser, optimizer, protocol, executor

Frames are recognised by C++ namespace in the plugin, which exports its
symbols. The transaction utilities share the rocksdb:: namespace with the
core, so they are picked out by class name, listed in TXN_CLASSES.

The three RocksDB owners together and `innodb` are the same quantity for
the two engines: samples taken under the engine's entry points.
"""

import collections
import glob
import os
import re
import subprocess

# Classes under utilities/transactions and
# utilities/write_batch_with_index in RocksDB 6.29.
TXN_CLASSES = (
    "TransactionBaseImpl", "PessimisticTransaction", "WriteCommittedTxn",
    "WritePreparedTxn", "WriteUnpreparedTxn", "OptimisticTransaction",
    "PessimisticTransactionDB", "WriteCommittedTxnDB", "WritePreparedTxnDB",
    "TransactionDB", "TransactionDBImpl", "TransactionUtil",
    "TransactionLogIteratorImpl", "Transaction",
    "WriteBatchWithIndex", "WriteBatchWithIndexInternal", "BaseDeltaIterator",
    "WBWIIteratorImpl", "WBWIIterator", "ReadableWriteBatch",
    "WriteBatchEntryComparator", "WriteBatchIndexEntry",
    "PointLockManager", "PointLockTracker", "LockTracker", "LockManager",
    "RangeTreeLockManager", "LockMap", "LockMapStripe", "DeadlockInfoBuffer",
    "SnapshotChecker", "WritePreparedSnapshotChecker",
)
_TXN = re.compile(r"\brocksdb::(?:%s)\b(?:::|<)" % "|".join(TXN_CLASSES))
_NS = re.compile(r"\b(myrocks|rocksdb)::")

# InnoDB is linked into the server and shares no namespace, so it is known
# by its doors: the handler class and the handlerton functions, every one
# of which is named ha_innobase:: or innobase_ or innodb_. A sample with
# one of these in its stack was taken inside InnoDB or in something InnoDB
# called. The server binary hides these names; they resolve only with its
# debug symbols installed (bench/README.md), and without them InnoDB's
# share reads as zero and its samples sit under `server`.
_INNODB_ENTRY = re.compile(r"(?:ha_innobase::|ha_innopart::|innobase_|innodb_)")

_FRAME = re.compile(r"^\s*([0-9a-f]+) (.*) \(([^()]*)\)$")

# Threads an engine starts for itself, by the name the kernel shows for
# them. InnoDB's work in these enters through none of its handler calls,
# so the thread is the only thing that says whose it is. The names are
# MariaDB's (its thread pool's workers serve InnoDB alone) and MySQL's,
# which begin ib_.
_OWN_THREADS = (
    (re.compile(r"^(?:ib_|page_cleaner$|io_uring_wait$)"), "innodb"),
    (re.compile(r"^rocksdb:"), "rocksdb_core"),
    (re.compile(r"^myrocks-"), "myrocks"),
)


def perf_binary():
    """The newest perf under /usr/lib/linux-tools. Ubuntu's /usr/bin/perf
    is a wrapper that refuses to run when the package does not match the
    running kernel; the binary itself works across kernel versions."""
    found = sorted(glob.glob("/usr/lib/linux-tools/*/perf"))
    if found:
        return found[-1]
    return "perf"


def record(pid, seconds, path, hz=1999):
    subprocess.run(
        [perf_binary(), "record", "-F", str(hz), "-e", "cpu-clock", "-g",
         "-p", str(pid), "-o", path, "--", "sleep", str(seconds)],
        check=True, capture_output=True)


def script(path):
    # `-F dso,sym` alone prints blank lines; ip must be among the fields.
    return subprocess.run(
        [perf_binary(), "script", "-i", path, "-F", "comm,ip,sym,dso"],
        check=True, capture_output=True, text=True, errors="replace").stdout


def samples(text):
    """Yield each sample as (thread name, frames), the frames innermost
    first as (symbol, dso). A sample is a line naming its thread, then
    its frames; the name is None where the text has none."""
    thread, frames = None, []
    for line in text.splitlines():
        m = _FRAME.match(line)
        if m:
            frames.append((m.group(2), m.group(3)))
            continue
        if frames:
            yield thread, frames
            thread, frames = None, []
        if line.strip():
            thread = line.strip()
    if frames:
        yield thread, frames


def thread_owner(name):
    """The engine a thread belongs to by its name, or None."""
    for pattern, owner in _OWN_THREADS:
        if name and pattern.match(name):
            return owner
    return None


def owner_of(symbol, dso):
    """The engine a frame belongs to, or None."""
    if dso.endswith("ha_rocksdb.so"):
        m = _NS.search(symbol)
        if not m:
            return None
        if m.group(1) == "myrocks":
            return "myrocks"
        return "rocksdb_txn" if _TXN.search(symbol) else "rocksdb_core"
    if _INNODB_ENTRY.match(symbol) and dso.endswith(("mariadbd", "mysqld")):
        return "innodb"
    return None


def is_kernel(dso):
    return dso.startswith("[kernel")


def attribute(text, top=25):
    counts = collections.Counter()
    kernel = collections.Counter()
    self_syms = collections.defaultdict(collections.Counter)
    owner_frames = collections.defaultdict(collections.Counter)
    threads = collections.Counter()
    own = collections.Counter()
    rooted = 0
    total = 0
    for thread, frames in samples(text):
        total += 1
        who = "server"
        via = None
        for sym, dso in frames:
            o = owner_of(sym, dso)
            if o:
                who, via = o, sym
                break
        if thread:
            threads[thread] += 1
        mine = thread_owner(thread)
        if mine:
            # Whatever the frames said, this was the engine's own thread;
            # where they said nothing, the thread decides.
            own[mine] += 1
            if who == "server":
                who = mine
        counts[who] += 1
        leaf_sym, leaf_dso = frames[0]
        if is_kernel(leaf_dso):
            kernel[who] += 1
        self_syms[who][leaf_sym] += 1
        if via:
            owner_frames[who][via] += 1
        # A stack that reaches the thread's entry was unwound whole.
        if any(s in ("start_thread", "__clone3", "clone3", "__clone",
                     "handle_one_connection", "_start")
               for s, _ in frames[-4:]):
            rooted += 1
    return {
        "samples": total,
        "rooted": rooted,
        "owners": dict(counts),
        "kernel": dict(kernel),
        # Samples by thread name, and those taken in an engine's own
        # threads by engine.
        "threads": dict(threads.most_common(top)),
        "own_threads": dict(own),
        "top_self": {o: c.most_common(top) for o, c in self_syms.items()},
        "top_owner_frames": {o: c.most_common(top)
                             for o, c in owner_frames.items()},
    }
