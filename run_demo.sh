#!/usr/bin/env bash
# Start the dashboard with live simulation. Needs only python3 (no compiler, no build).
#   bash run_demo.sh            unpack the bundled simulator (first time only) and open the dashboard
#   bash run_demo.sh --check    run one tiny simulation and exit (use this before the demo)
#   PORT=9000 bash run_demo.sh  use another port
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"
DEST="${NSS_HOME:-$HOME/.nss-wifi6}"
BUNDLE="$HERE/prebuilt/ns3-prebuilt-linux-x86_64.tar.xz"
SUMS="$HERE/prebuilt/ns3-prebuilt-linux-x86_64.tar.xz.sha256"

command -v python3 >/dev/null 2>&1 || { echo "python3 not found. In Ubuntu: sudo apt update && sudo apt install -y python3"; exit 1; }

find_bin() { ls "$1"/build/scratch/ns3.*-nss-wifi6* 2>/dev/null | head -1 || true; }

# 1. a simulator built from source (setup_ns3.sh) wins, otherwise use the bundled one
NS3=""
for d in "${NS3_DIR:-}" "$HOME/ns-3.49" "$DEST/ns3-prebuilt"; do
  [ -n "$d" ] && [ -n "$(find_bin "$d")" ] && { NS3="$d"; break; }
done

# 2. unpack the bundled simulator into the Linux home (not the Windows disk)
if [ -z "$NS3" ]; then
  [ "$(uname -m)" = "x86_64" ] || { echo "The bundled simulator is for x86_64 only. Build it instead:  bash setup_ns3.sh"; exit 1; }
  [ -f "$BUNDLE" ] || { echo "missing $BUNDLE. Build the simulator instead:  bash setup_ns3.sh"; exit 1; }
  if [ -f "$SUMS" ]; then
    want="$(awk '{print $1}' "$SUMS")"
    got="$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$BUNDLE")"
    [ "$want" = "$got" ] || { echo "checksum mismatch on the bundled simulator, re-download the repo"; exit 1; }
  fi
  echo "unpacking the simulator into $DEST (first run only) ..."
  mkdir -p "$DEST"
  python3 - "$BUNDLE" "$DEST" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1], "r:xz") as t:
    t.extractall(sys.argv[2])
PY
  NS3="$DEST/ns3-prebuilt"
fi

BIN="$(find_bin "$NS3")"
export LD_LIBRARY_PATH="$NS3/build/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# 3. prove it runs on this machine
if ! out="$("$BIN" --nStations=5 --simTime=1 2>&1)" || ! printf '%s' "$out" | grep -q goodput; then
  echo "The bundled simulator did not start on this system:"
  printf '%s\n' "$out" | head -5
  echo "It needs Ubuntu 24.04 or newer (WSL: wsl --install -d Ubuntu-24.04). Or build from source:  bash setup_ns3.sh"
  exit 1
fi
echo "simulator OK: $(printf '%s' "$out" | grep -m1 goodput | sed 's/^ *//')"

[ "${1:-}" = "--check" ] && { echo "check passed"; exit 0; }

# 4. open the browser a moment after the server is up (WSL -> Windows browser, Linux desktop -> xdg-open)
URL="http://localhost:$PORT"
( sleep 2
  if grep -qi microsoft /proc/version 2>/dev/null && command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then xdg-open "$URL" >/dev/null 2>&1 || true
  fi ) &

exec python3 "$HERE/app.py" --ns3 "$NS3" --port "$PORT"
