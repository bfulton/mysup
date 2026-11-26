"""One server instance: its directory, its config, its cgroup, its lifetime.

The harness never touches a system service. Each arm gets a directory of
its own with a data directory, a config file naming every setting that is
not the server's default, and a socket.

Only MariaDB is implemented, because only MariaDB has been run. The seam
for a second server is the four executables named in `MariaDB` and the
`[mariadbd]` group in `Instance.write_cnf`.
"""

import os
import shutil
import subprocess
import time

CG_ROOT = "/sys/fs/cgroup/memory"


class MemCgroup:
    """A cgroup v1 memory group holding the server and nothing else.

    Every run uses one, limited or not, because its peak is how the
    server's memory is recorded.
    """

    def __init__(self, name):
        if not os.path.exists(os.path.join(CG_ROOT, "memory.limit_in_bytes")):
            raise RuntimeError(
                f"no cgroup v1 memory controller at {CG_ROOT}; the memory "
                "limit and the peak are taken from it")
        self.path = os.path.join(CG_ROOT, "mysup-bench-" + name)

    def _write(self, name, value):
        with open(os.path.join(self.path, name), "w") as f:
            f.write(str(value))

    def _read(self, name):
        with open(os.path.join(self.path, name)) as f:
            return f.read()

    def create(self, limit=None):
        self.destroy()
        os.makedirs(self.path)
        if limit:
            self._write("memory.limit_in_bytes", limit)
            if os.path.exists(
                    os.path.join(self.path, "memory.memsw.limit_in_bytes")):
                self._write("memory.memsw.limit_in_bytes", limit)

    def destroy(self):
        if not os.path.isdir(self.path):
            return
        err = None
        for _ in range(100):
            try:
                os.rmdir(self.path)
                return
            except OSError as e:
                err = e
                time.sleep(0.1)
        raise err

    def enter(self):
        self._write("cgroup.procs", os.getpid())

    def reset_peak(self):
        self._write("memory.max_usage_in_bytes", 0)

    def read(self):
        stat = dict(l.split() for l in self._read("memory.stat").splitlines())
        oom = dict(
            l.split() for l in self._read("memory.oom_control").splitlines())
        limit = int(self._read("memory.limit_in_bytes"))
        return {
            "limit": limit if limit < (1 << 60) else None,
            "usage": int(self._read("memory.usage_in_bytes")),
            "peak": int(self._read("memory.max_usage_in_bytes")),
            "failcnt": int(self._read("memory.failcnt")),
            "rss": int(stat["rss"]),
            "cache": int(stat["cache"]),
            "oom_kill": int(oom.get("oom_kill", 0)),
        }


class MariaDB:
    name = "mariadb"

    def __init__(self):
        self.mysqld = self._need("mariadbd")
        self.install_db = self._need("mariadb-install-db")
        self.client = self._need("mariadb")
        self.admin = self._need("mariadb-admin")

    @staticmethod
    def _need(exe):
        path = shutil.which(exe)
        if not path:
            raise RuntimeError(f"{exe} is not installed; see bench/README.md")
        return path

    def version(self):
        out = subprocess.run([self.mysqld, "--version"], capture_output=True,
                             text=True, check=True).stdout
        return out.strip()


class ServerDied(RuntimeError):
    pass


class Instance:
    def __init__(self, flavor, directory, name):
        self.flavor = flavor
        self.name = name
        self.dir = directory
        self.datadir = os.path.join(directory, "data")
        self.snapdir = os.path.join(directory, "snapshot")
        self.tmpdir = os.path.join(directory, "tmp")
        self.sock = os.path.join(directory, "mysqld.sock")
        self.cnf = os.path.join(directory, "my.cnf")
        self.errlog = os.path.join(directory, "error.log")
        self.proc = None
        self.cgroup = MemCgroup(name)

    # -- config ---------------------------------------------------------

    def write_cnf(self, settings):
        """`settings` is a list of (name, value); value None is a flag."""
        fixed = [
            ("datadir", self.datadir),
            ("socket", self.sock),
            ("pid-file", os.path.join(self.dir, "mysqld.pid")),
            ("log-error", self.errlog),
            ("tmpdir", self.tmpdir),
        ]
        if os.geteuid() == 0:
            fixed.append(("user", "root"))
        os.makedirs(self.tmpdir, exist_ok=True)
        with open(self.cnf, "w") as f:
            f.write("[mariadbd]\n")
            for k, v in fixed + list(settings):
                f.write(k + "\n" if v is None else f"{k}={v}\n")

    def cnf_text(self):
        with open(self.cnf) as f:
            return f.read()

    # -- lifetime -------------------------------------------------------

    def init(self):
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)
        cmd = [self.flavor.install_db, "--no-defaults",
               "--datadir=" + self.datadir,
               "--auth-root-authentication-method=normal"]
        if os.geteuid() == 0:
            cmd.append("--user=root")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("install-db failed:\n" + r.stdout + r.stderr)

    def start(self, limit=None):
        assert self.proc is None
        self.cgroup.create(limit)
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        log = open(os.path.join(self.dir, "stdout.log"), "ab")
        self.proc = subprocess.Popen(
            [self.flavor.mysqld, "--defaults-file=" + self.cnf],
            stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            preexec_fn=self.cgroup.enter)
        log.close()
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                self._died("exited during startup")
            if os.path.exists(self.sock):
                r = subprocess.run(self._client() + ["-e", "select 1"],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    return
            time.sleep(0.2)
        self._died("did not accept connections within 600 s")

    def _died(self, what):
        tail = ""
        if os.path.exists(self.errlog):
            with open(self.errlog, errors="replace") as f:
                tail = "".join(f.readlines()[-25:])
        code = self.proc.poll() if self.proc else None
        self.proc = None
        raise ServerDied(f"{self.name}: server {what} (exit {code})\n{tail}")

    def check(self):
        """Raise if the server is gone, saying whether the cgroup killed it."""
        if self.proc is not None and self.proc.poll() is not None:
            cg = self.cgroup.read()
            self._died(f"died; cgroup oom_kill={cg['oom_kill']} "
                       f"failcnt={cg['failcnt']}")

    @property
    def pid(self):
        return self.proc.pid

    def stop(self, slow=False):
        """Shut down. `slow` asks InnoDB for a full purge and merge first,
        so the files left behind hold no deferred work."""
        if self.proc is None:
            return
        if self.proc.poll() is None:
            if slow:
                self.sql("SET GLOBAL innodb_fast_shutdown=0")
            subprocess.run(
                [self.flavor.admin, "--no-defaults", "-S", self.sock,
                 "-uroot", "shutdown"], capture_output=True, text=True)
            self.proc.wait(timeout=1800)
        self.proc = None

    def kill(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        self.proc = None

    # -- SQL ------------------------------------------------------------

    def _client(self, db=None):
        cmd = [self.flavor.client, "--no-defaults", "-S", self.sock,
               "-uroot", "-B", "-N", "--raw"]
        if db:
            cmd.append(db)
        return cmd

    def sql(self, query, db=None):
        r = subprocess.run(self._client(db) + ["-e", query],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.check()
            raise RuntimeError(f"{self.name}: {query!r} failed: {r.stderr}")
        return [line.split("\t") for line in r.stdout.splitlines()]

    def sql_text(self, query, db=None):
        cmd = self._client(db)
        cmd.remove("-N")
        r = subprocess.run(cmd + ["-e", query], capture_output=True, text=True)
        if r.returncode != 0:
            self.check()
            raise RuntimeError(f"{self.name}: {query!r} failed: {r.stderr}")
        return r.stdout

    # -- files ----------------------------------------------------------

    def snapshot(self):
        """Keep the stopped server's data directory as loaded."""
        assert self.proc is None
        if os.path.exists(self.snapdir):
            shutil.rmtree(self.snapdir)
        subprocess.run(["cp", "-a", self.datadir, self.snapdir], check=True)

    def restore(self):
        assert self.proc is None
        if os.path.exists(self.datadir):
            shutil.rmtree(self.datadir)
        subprocess.run(["cp", "-a", self.snapdir, self.datadir], check=True)

    def has_snapshot(self):
        return os.path.isdir(self.snapdir)


def tree_bytes(root, keep=lambda rel: True):
    """Bytes allocated to the files under `root` that `keep` accepts."""
    total = 0
    for base, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            if keep(os.path.relpath(path, root)):
                total += os.lstat(path).st_blocks * 512
    return total


def drop_page_cache():
    subprocess.run(["sync"], check=True)
    with open("/proc/sys/vm/drop_caches", "w") as f:
        f.write("3\n")
