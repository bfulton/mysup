#!/usr/bin/env python3
"""How sysbench's rows compress, by coder and block size.

    python3 bench/tools/rowcompress.py

The rows are built the way sysbench's oltp_common.lua builds them: `c` is
ten groups of eleven random digits joined by dashes, `pad` five groups.
They are cut into blocks the size an engine compresses, and each block is
handed to the system's liblz4, libsnappy and libzstd, the libraries the
servers' RocksDB links. Prints compressed bytes over raw bytes.
"""
import ctypes
import random
import struct

ROWS = 40_000


def rows():
    rng = random.Random(1)

    def groups(n):
        return "-".join("".join(rng.choice("0123456789") for _ in range(11))
                        for _ in range(n))
    return b"".join(
        struct.pack(">ii", i, rng.randrange(1, 1_000_000))
        + groups(10).ljust(120).encode() + groups(5).ljust(60).encode()
        for i in range(1, ROWS + 1))


def coders():
    lz4 = ctypes.CDLL("liblz4.so.1")
    zstd = ctypes.CDLL("libzstd.so.1")
    snappy = ctypes.CDLL("libsnappy.so.1")
    zstd.ZSTD_compress.restype = ctypes.c_size_t

    def room(b):
        return ctypes.create_string_buffer(len(b) * 2 + 64)

    def c_lz4(b):
        out = room(b)
        return lz4.LZ4_compress_default(b, out, len(b), len(out))

    def c_snappy(b):
        out = room(b)
        n = ctypes.c_size_t(len(out))
        assert snappy.snappy_compress(b, ctypes.c_size_t(len(b)), out,
                                      ctypes.byref(n)) == 0
        return n.value

    def c_zstd(b):
        out = room(b)
        return zstd.ZSTD_compress(out, ctypes.c_size_t(len(out)), b,
                                  ctypes.c_size_t(len(b)), 6)

    return [("LZ4", c_lz4), ("Snappy", c_snappy), ("ZSTD level 6", c_zstd)]


def main():
    blob = rows()
    print(f"{ROWS} rows of {len(blob) // ROWS} bytes")
    for block in (4096, 16384, 65536):
        parts = [blob[i:i + block] for i in range(0, len(blob), block)]
        line = f"blocks of {block:5}:"
        for name, f in coders():
            # A block that does not shrink is stored as it is.
            size = sum(min(f(p), len(p)) for p in parts)
            line += f"  {name} {size / len(blob):.2f}"
        print(line)


if __name__ == "__main__":
    main()
