#!/usr/bin/env python3
"""Run the NSS experiments against the compiled ns-3 scenario.

Usage:  python3 run_sweep.py [--ns3 ~/ns-3.49] [--jobs 5] [--seeds 3] [--sim 6] [exp ...]
Experiments: scaling, hidden, control, payload   (default: all)
Resumable: a run whose raw CSV already exists is skipped.
"""
import argparse
import csv
import glob
import hashlib
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ)

# four configurations of the study
CONFIGS = {
    "baseline": ["--rts=0", "--ofdma=0"],
    "rts": ["--rts=1", "--ofdma=0"],
    "ofdma": ["--rts=0", "--ofdma=1", "--accessReqMs=2"],
    "rts+ofdma": ["--rts=1", "--ofdma=1", "--accessReqMs=2"],
}


def experiments(seeds):
    S = range(1, seeds + 1)
    exps = {}
    # A: contention-only vs RTS vs OFDMA as stations grow (single cell, small packets, DL+UL)
    exps["scaling"] = [
        (cfg, [f"--nStations={n}", "--topology=single", "--direction=both",
               "--payload=200", "--perStaMbps=0.8", "--mcs=5", f"--seed={s}"] + CONFIGS[cfg])
        for cfg in CONFIGS for n in (5, 10, 20, 30, 40, 60) for s in S
    ]
    # B: hidden nodes (two groups ~66 m apart, both reach the AP), uplink only
    exps["hidden"] = [
        (cfg, [f"--nStations={n}", "--topology=hidden", "--hiddenOffset=38", "--direction=ul",
               "--payload=512", "--perStaMbps=2", "--mcs=2", f"--seed={s}"] + CONFIGS[cfg])
        for cfg in ("baseline", "rts") for n in (2, 4, 8, 12, 16) for s in S
    ]
    # B2: control for B - same distance from the AP but all stations on one side, so they hear each other
    exps["control"] = [
        (cfg, [f"--nStations={n}", "--topology=cluster", "--hiddenOffset=38", "--direction=ul",
               "--payload=512", "--perStaMbps=2", "--mcs=2", f"--seed={s}"] + CONFIGS[cfg])
        for cfg in ("baseline", "rts") for n in (2, 4, 8, 12, 16) for s in S
    ]
    # C: when does OFDMA pay off? vary payload at fixed N=30 (offered load held at 24 Mbit/s per direction)
    exps["payload"] = [
        (cfg, [f"--nStations=30", "--topology=single", "--direction=both",
               f"--payload={p}", f"--perStaMbps=0.8", "--mcs=5", f"--seed={s}"] + CONFIGS[cfg])
        for cfg in ("baseline", "ofdma") for p in (100, 200, 500, 1000) for s in S
    ]
    return exps


def run_one(binary, outdir, sim, exp, cfg, args):
    key = hashlib.md5((exp + cfg + " ".join(args) + str(sim)).encode()).hexdigest()[:10]
    raw = os.path.join(outdir, "raw", f"{exp}_{key}.csv")
    if os.path.exists(raw):
        return "skip"
    cmd = [binary, f"--simTime={sim}", f"--label={cfg}", f"--csv={raw}.part"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=ENV)
    if r.returncode != 0 or not os.path.exists(raw + ".part"):
        sys.stderr.write(f"FAILED: {' '.join(cmd)}\n{r.stderr[-400:]}\n")
        return "fail"
    os.rename(raw + ".part", raw)
    return "ok"


def merge(outdir, exp):
    rows, header = [], None
    for f in sorted(glob.glob(os.path.join(outdir, "raw", f"{exp}_*.csv"))):
        with open(f) as fh:
            rd = csv.reader(fh)
            h = next(rd)
            header = header or h
            rows += [r for r in rd]
    if not rows:
        return 0
    with open(os.path.join(outdir, f"{exp}.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns3", default=os.path.expanduser("~/ns-3.49"))
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--sim", type=float, default=6)
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("exp", nargs="*")
    a = ap.parse_args()

    binary = glob.glob(os.path.join(a.ns3, "build", "scratch", "ns3.*-nss-wifi6*"))
    binary = [b for b in binary if os.path.isfile(b) and os.access(b, os.X_OK)]
    if not binary:
        sys.exit("scenario not built: run './ns3 build nss-wifi6' in " + a.ns3)
    binary = binary[0]
    lib = os.path.join(a.ns3, "build", "lib")
    ENV["LD_LIBRARY_PATH"] = lib + (":" + ENV["LD_LIBRARY_PATH"] if ENV.get("LD_LIBRARY_PATH") else "")
    os.makedirs(os.path.join(a.out, "raw"), exist_ok=True)

    exps = experiments(a.seeds)
    todo = a.exp or list(exps)
    for exp in todo:
        jobs = exps[exp]
        t0 = time.time()
        done = 0
        print(f"[{exp}] {len(jobs)} runs, {a.jobs} parallel", flush=True)
        with ThreadPoolExecutor(a.jobs) as pool:
            futs = [pool.submit(run_one, binary, a.out, a.sim, exp, c, args) for c, args in jobs]
            for f in futs:
                f.result()
                done += 1
                if done % 10 == 0:
                    print(f"  {done}/{len(jobs)}  {time.time() - t0:.0f}s", flush=True)
        n = merge(a.out, exp)
        print(f"[{exp}] merged {n} rows -> results/{exp}.csv  ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
