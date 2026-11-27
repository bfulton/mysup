# Which server: what was read, and where

For the open decision in the [brief](brief.md), MySQL or MariaDB. The
measurements on three servers are in [`baselines.md`](baselines.md). This
page holds the facts that were read and not measured.

MyRocks stopped being a rival on 2026-11-27, so who ships it no longer
bears on the choice. That table stays for the record. What still bears on
it is the second half: how an engine is built for each server.

Everything below was read from the pages listed on 2026-11-26 by a research
pass. Lines marked **checked here** were also seen on this host. The rest was
not checked a second time.

## Who ships MyRocks

| Server | MyRocks | RocksDB under it |
|---|---|---|
| Oracle MySQL 8.4, 9.7 | no | |
| Percona Server 8.4, 9.7 | yes | 9.3.1 |
| MariaDB 10.11, 11.4, 11.8, 12.3, 13.1 | yes, as a plugin package | 6.29.5 |
| Meta's `facebook/mysql-5.6` | archived, read-only since 1 March 2026 | 9.7.1 on its last branch |

- Oracle's manuals for 8.4 and 9.7 list no RocksDB engine and say third-party
  engines are not supported. The 8.0 manual was not read.
- Percona Server 8.4.11-12, released 2026-11-12, is the newest 8.4. Percona
  Server 8.0 reached end of life on 1 April 2026. No deprecation of MyRocks
  was found in its documentation or release notes.
- Meta's last branch is `fb-mysql-8.0.32`, last commit January 2025. Where
  its development continues was not found.
- MariaDB pins the same RocksDB commit in 10.11, 12.3, 13.1 and main. No
  deprecation of MyRocks was found.
- **Checked here:** Percona Server 8.4.11-12 and MariaDB 12.3.4 were
  installed from their Ubuntu 24.04 packages and ran MyRocks. Percona's
  reports RocksDB 9.3.1, MariaDB's 6.29.5.

## MariaDB's long-term releases

| Series | Community support ends |
|---|---|
| 10.11 | 16 February 2028 |
| 11.4 | 29 May 2029 |
| 11.8 | 4 June 2028 |
| 12.3, generally available 28 May 2026 | 12 June 2029 |

The newest stable release is the rolling 13.1.

## Building an engine outside the server's source tree

**MariaDB:** documented and supported, from this autumn's releases.

- "Building a plugin with only the MariaDB development package, without the
  server source tree, requires MariaDB 11.4.14, 11.8.10, 12.3.4, 13.1.2,
  13.2.1, or later" (MDEV-40608, resolved 2026-09-25). The package provides
  `find_package(mariadb-plugin)` and `MARIADB_ADD_PLUGIN(... STORAGE_ENGINE
  ...)`.
- In MariaDB's own Ubuntu 24.04 packages, by their contents index:

  | Releases | `server/private/handler.h` | CMake package |
  |---|---|---|
  | 10.11.19, 10.11.20 | absent | absent |
  | 11.4.13, 11.8.9, 12.3.3 | in `libmariadbd-dev` | absent |
  | 11.4.14, 11.8.10, 12.3.4, 13.1.2 | in `libmariadb-dev` | in `libmariadb-dev` |

- MariaDB Foundry packages engines built this way. Two are in the 12.3.4
  repository.
- **Checked here:** Ubuntu's `libmariadbd-dev` 10.11.14 has no
  `server/private/handler.h`.

**MySQL 8.0, 8.4:** no supported route was found. The documentation
describes only a plugin directory inside the source tree. The installed
headers are the client's, with no `plugin.h` or `handler.h`.

**Both:** an engine is tied to one exact server version. Both compute the
engine interface version from the server's version number, and the loader
refuses a mismatch.

## Sources

Oracle MySQL
- https://dev.mysql.com/doc/refman/8.4/en/storage-engines.html
- https://dev.mysql.com/doc/refman/9.7/en/storage-engines.html
- https://dev.mysql.com/doc/refman/8.4/en/storage-engines-other.html
- https://dev.mysql.com/doc/extending-mysql/8.4/en/compiling-plugin-libraries.html
- https://dev.mysql.com/doc/extending-mysql/8.4/en/plugin-api-characteristics.html
- https://raw.githubusercontent.com/mysql/mysql-server/8.4/include/CMakeLists.txt
- https://raw.githubusercontent.com/mysql/mysql-server/8.4/include/mysql/plugin.h
- https://raw.githubusercontent.com/mysql/mysql-server/8.4/sql/sql_plugin.cc

Percona Server
- https://www.percona.com/release-lifecycle-of-percona-software-for-mysql/
- https://docs.percona.com/percona-server/8.4/release-notes/release-notes-index.html
- https://docs.percona.com/percona-server/8.4/release-notes/8.4.5-5.html
- https://repo.percona.com/ps-84-lts/apt/pool/main/p/percona-server/
- https://github.com/percona/percona-server/tree/Percona-Server-8.4.11-12/storage/rocksdb

Meta
- https://github.com/facebook/mysql-5.6
- https://github.com/facebook/mysql-5.6/branches/all

MariaDB
- https://mariadb.org/about/
- https://downloads.mariadb.org/rest-api/mariadb/
- https://archive.mariadb.org/mariadb-12.3.4/repo/ubuntu/pool/main/m/mariadb/
- https://github.com/MariaDB/server/tree/12.3/storage/rocksdb
- https://mariadb.com/docs/server/reference/product-development/plugin-development/development-writing-plugins-for-mariadb
- https://jira.mariadb.org/browse/MDEV-40608
- https://archive.mariadb.org/mariadb-12.3.4/repo/ubuntu/dists/noble/main/Contents-amd64.gz
- https://github.com/MariaDB/foundry
- https://mariadb.org/mariadb-foundation-newsletter-october-2026/
- https://mariadb.com/docs/server/server-usage/storage-engines/duckdb-storage-engine
