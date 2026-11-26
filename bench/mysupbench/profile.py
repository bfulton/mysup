"""Where the server's CPU goes, by who owns the code.

`perf record -e cpu-clock -g` on the server while one client thread runs a
workload, then each sample is given to exactly one owner:

    the innermost frame of its call stack that belongs to an engine names
    the owner; a sample with no engine frame belongs to the server.

So time in libc or the kernel is charged to whichever engine code called
it, and an engine's callbacks into the server (field packing, say) are
charged to the engine frame they return to. The owners:

    rocksdb_core  RocksDB proper: what a RocksDB-compatible layer replaces
    rocksdb_txn   RocksDB's transaction and write-batch-with-index
                  utilities: a layer keeps these
    myrocks       the storage engine written against RocksDB
    innodb        InnoDB, only where its symbols resolve (see innodb_owner)
    server        everything else: parser, optimizer, protocol, executor

Frames are recognised by C++ namespace in the plugin, which exports its
symbols. The transaction utilities share the rocksdb:: namespace with the
core, so they are picked out by class name, listed in TXN_CLASSES.
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

_FRAME = re.compile(r"^\s*([0-9a-f]+) (.*) \(([^()]*)\)$")


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
        [perf_binary(), "script", "-i", path, "-F", "ip,sym,dso"],
        check=True, capture_output=True, text=True, errors="replace").stdout


def samples(text):
    """Yield each sample's frames, innermost first, as (symbol, dso)."""
    frames = []
    for line in text.splitlines():
        m = _FRAME.match(line)
        if m:
            frames.append((m.group(2), m.group(3)))
        elif frames:
            yield frames
            frames = []
    if frames:
        yield frames


def owner_of(symbol, dso, innodb_owner=None):
    """The engine a frame belongs to, or None."""
    if dso.endswith("ha_rocksdb.so"):
        m = _NS.search(symbol)
        if not m:
            return None
        if m.group(1) == "myrocks":
            return "myrocks"
        return "rocksdb_txn" if _TXN.search(symbol) else "rocksdb_core"
    if innodb_owner is not None:
        return innodb_owner(symbol, dso)
    return None


def is_kernel(dso):
    return dso.startswith("[kernel")


def attribute(text, innodb_owner=None, top=25):
    counts = collections.Counter()
    kernel = collections.Counter()
    self_syms = collections.defaultdict(collections.Counter)
    owner_frames = collections.defaultdict(collections.Counter)
    rooted = 0
    total = 0
    for frames in samples(text):
        total += 1
        who = "server"
        via = None
        for sym, dso in frames:
            o = owner_of(sym, dso, innodb_owner)
            if o:
                who, via = o, sym
                break
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
        "top_self": {o: c.most_common(top) for o, c in self_syms.items()},
        "top_owner_frames": {o: c.most_common(top)
                             for o, c in owner_frames.items()},
    }


def innodb_owner_from(symfile):
    """An owner function for the server binary from a file of
    `address size name source-file` lines (see `debug_symbols`), or None
    when the file is absent. With it, a frame in the server binary whose
    function was compiled from storage/innobase/ belongs to InnoDB."""
    if not symfile or not os.path.exists(symfile):
        return None
    names = set()
    with open(symfile) as f:
        for line in f:
            names.add(line.rstrip("\n"))

    def owner(symbol, dso):
        if dso.endswith(("mariadbd", "mysqld")) and symbol in names:
            return "innodb"
        return None
    return owner
