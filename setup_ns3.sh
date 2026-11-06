#!/usr/bin/env bash
# Download ns-3.49, build only the modules the scenario needs, build nss-wifi6.
#   ./setup_ns3.sh                     installs into ~/ns-3.49
#   NS3_DIR=/path JOBS=3 ./setup_ns3.sh
set -euo pipefail

VER=3.49
URL="https://www.nsnam.org/releases/ns-${VER}.tar.bz2"
SHA256=81c9eb0839d2b527e9cc01db7eb0a521d8fc6a520ebb23d17f3a5c96e47b4d68
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/ns-$VER}"

case "$HERE$NS3_DIR" in
  /mnt/*|*/mnt/c/*) echo "warning: /mnt/... is the Windows disk and builds there are very slow." \
                         "Keep this folder and NS3_DIR inside the Linux home (~)." ;;
esac

missing=""
for t in g++ cmake ninja python3 curl tar bzip2 sha256sum; do
  command -v "$t" >/dev/null 2>&1 || missing="$missing $t"
done
if [ -n "$missing" ]; then
  echo "missing tools:$missing"
  echo "install with:  sudo apt update && sudo apt install -y git g++ cmake ninja-build python3 curl ca-certificates bzip2 python3-pandas python3-matplotlib"
  exit 1
fi

cmv="$(cmake --version | head -1 | awk '{print $3}')"
if [ "$(printf '%s\n3.25\n' "$cmv" | sort -V | head -1)" != "3.25" ]; then
  echo "cmake $cmv is too old, ns-$VER needs 3.25 or newer"; exit 1
fi

# parallel jobs: one per core, but at most one per 1 GB of free RAM (wifi files are heavy)
if [ -z "${JOBS:-}" ]; then
  cores="$(nproc)"
  mem_kb="$(awk '/MemAvailable/ {print $2}' /proc/meminfo)"
  by_mem=$(( mem_kb / 1000000 ))
  [ "$by_mem" -lt 1 ] && by_mem=1
  JOBS=$(( cores < by_mem ? cores : by_mem ))
fi
echo "ns-3 dir: $NS3_DIR | cmake $cmv | jobs: $JOBS"

if [ ! -f "$NS3_DIR/ns3" ]; then
  tmp="$(mktemp -d)"
  echo "downloading $URL"
  curl -fL --retry 3 -o "$tmp/ns3.tar.bz2" "$URL"
  echo "$SHA256  $tmp/ns3.tar.bz2" | sha256sum -c -
  mkdir -p "$NS3_DIR"
  tar -xjf "$tmp/ns3.tar.bz2" -C "$NS3_DIR" --strip-components=1
  rm -rf "$tmp"
fi

cp "$HERE/nss-wifi6.cc" "$NS3_DIR/scratch/nss-wifi6.cc"
cd "$NS3_DIR"
# NS3_NATIVE_OPTIMIZATIONS=OFF: no -march=native, so the build does not depend on this CPU
./ns3 configure -G Ninja --build-profile=optimized --disable-examples --disable-tests --disable-python \
    --enable-modules="wifi;flow-monitor;applications;mobility;internet;network;core;spectrum;propagation;stats" \
    -- -DNS3_NATIVE_OPTIMIZATIONS=OFF
./ns3 build nss-wifi6 -j "$JOBS"

bin="$(ls "$NS3_DIR"/build/scratch/ns3.*-nss-wifi6* | head -1)"
echo "built: $bin"
echo "smoke test:"
out="$("$bin" --nStations=5 --simTime=1)"
echo "$out"
case "$out" in
  *goodput*) echo "OK - now run:  python3 demo.py --ns3 $NS3_DIR" ;;
  *) echo "smoke test FAILED"; exit 1 ;;
esac
