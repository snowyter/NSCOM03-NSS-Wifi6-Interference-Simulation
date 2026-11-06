#!/usr/bin/env python3
"""Live demo: run the four configurations at one station count, side by side.

Usage:  python3 demo.py [--ns3 ~/ns-3.49] [--n 30] [--sim 4] [--topology single|hidden]
Takes about 30-60 s for N=30 (the four runs go in parallel).
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

CONFIGS = [
    ("CSMA/CA only", ["--rts=0", "--ofdma=0"]),
    ("RTS/CTS", ["--rts=1", "--ofdma=0"]),
    ("OFDMA", ["--rts=0", "--ofdma=1", "--accessReqMs=2"]),
    ("RTS/CTS + OFDMA", ["--rts=1", "--ofdma=1", "--accessReqMs=2"]),
]

ap = argparse.ArgumentParser()
ap.add_argument("--ns3", default=os.path.expanduser("~/ns-3.49"))
ap.add_argument("--n", type=int, default=30)
ap.add_argument("--sim", type=float, default=4)
ap.add_argument("--topology", default="single", choices=["single", "hidden"])
a = ap.parse_args()

bins = [b for b in glob.glob(os.path.join(a.ns3, "build", "scratch", "ns3.*-nss-wifi6*"))
        if os.path.isfile(b) and os.access(b, os.X_OK)]
if not bins:
    sys.exit("not built: run './ns3 build nss-wifi6' in " + a.ns3)

if a.topology == "single":
    scen = ["--topology=single", "--direction=both", "--payload=200", "--perStaMbps=0.8", "--mcs=5"]
else:
    scen = ["--topology=hidden", "--hiddenOffset=38", "--direction=ul", "--payload=512", "--perStaMbps=2", "--mcs=2"]


def run(item):
    name, args = item
    out = subprocess.run([bins[0], f"--nStations={a.n}", f"--simTime={a.sim}"] + scen + args,
                         capture_output=True, text=True, timeout=600).stdout
    g = lambda pat: float(re.search(pat, out).group(1))
    return (name, g(r"goodput ([\d.]+) Mbps"), g(r"mean delay ([\d.]+) ms"), g(r"loss ([\d.]+) %"),
            g(r"Jain ([\d.]+)"), g(r"([\d.]+) % multi-user"))


print(f"{a.topology} cell, N={a.n}, {a.sim:g} s of traffic, 4 configs in parallel ...", flush=True)
t0 = time.time()
with ThreadPoolExecutor(4) as pool:
    rows = list(pool.map(run, CONFIGS))
print(f"\n{'config':<18}{'goodput Mb/s':>13}{'delay ms':>10}{'loss %':>8}{'Jain':>7}{'MU PPDU %':>11}")
for r in rows:
    print(f"{r[0]:<18}{r[1]:>13.2f}{r[2]:>10.1f}{r[3]:>8.1f}{r[4]:>7.2f}{r[5]:>11.1f}")
print(f"\n({time.time() - t0:.0f} s)")
