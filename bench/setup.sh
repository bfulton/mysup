#!/bin/sh
# What the harness needs, on Ubuntu 24.04, installed where missing.
#
# The server is the distribution's MariaDB with its MyRocks plugin, and
# jemalloc for the arms that run under it. The server's service is never
# started: the harness runs its own instances. MySQL's server packages
# conflict with these, so this does not install them.
set -eu

need=""
for pkg in mariadb-server mariadb-plugin-rocksdb libjemalloc2 sysbench linux-tools-generic coreutils; do
    dpkg -s "$pkg" >/dev/null 2>&1 || need="$need $pkg"
done
if [ -n "$need" ]; then
    # Keep the package from starting a system server while it installs,
    # and leave the host's policy as it was found.
    made=""
    if [ ! -e /usr/sbin/policy-rc.d ]; then
        printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
        chmod +x /usr/sbin/policy-rc.d
        made=1
    fi
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $need
    [ -z "$made" ] || rm -f /usr/sbin/policy-rc.d
fi

mariadbd --version
sysbench --version
ls /usr/lib/linux-tools/*/perf | tail -1
