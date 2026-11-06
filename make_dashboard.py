#!/usr/bin/env python3
"""Rebuild dashboard.html: saved sample runs (with frame traces) + sweep averages.

Only needed if you change the scenario or the saved runs. The finished dashboard.html is
already in the repo, so you do NOT need to run this to give the demo.

    python3 make_dashboard.py [--ns3 ~/ns-3.49] [--jobs 6] [--sim 6]

Resumable: a saved run in results/samples/ is reused. Standard library only.
"""
import argparse
import csv
import json
import os
import sys
import statistics
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simlib

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED_N = {"single": [5, 10, 20, 30, 40], "hidden": [4, 8, 12, 16]}
SEED = 1


def sample(ns3, topo, n, cfg, sim):
    path = os.path.join(HERE, "results", "samples", "%s_%d_%s.json" % (topo, n, cfg.replace("+", "_")))
    if os.path.exists(path):
        return json.load(open(path))
    run = simlib.run_one(ns3, cfg, n, topo, sim=sim, seed=SEED)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".part", "w") as fh:
        json.dump(run, fh, separators=(",", ":"))
    os.rename(path + ".part", path)
    return run


def aggregate(fname, xcol):
    path = os.path.join(HERE, "results", fname)
    if not os.path.exists(path):
        return []
    groups = {}
    for r in csv.DictReader(open(path)):
        groups.setdefault((r["label"], int(r[xcol])), []).append(r)
    out = []
    for (label, x), rows in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        rec = {"config": label, "x": x, "seeds": len(rows)}
        for key, col in (("goodput", "goodputMbps"), ("delay", "meanDelayMs"), ("loss", "lossPct"),
                         ("jain", "jain"), ("mu", "muPct")):
            vals = [float(r[col]) for r in rows]
            rec[key] = round(statistics.mean(vals), 3)
            rec[key + "Sd"] = round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns3", default=simlib.default_ns3())
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--sim", type=float, default=6)
    a = ap.parse_args()

    jobs = [(t, n, c) for t, ns in SAVED_N.items() for n in ns for c in simlib.CONFIGS]
    print("%d sample runs (%g s each, seed %d), %d parallel" % (len(jobs), a.sim, SEED, a.jobs), flush=True)
    with ThreadPoolExecutor(a.jobs) as pool:
        runs = list(pool.map(lambda j: sample(a.ns3, j[0], j[1], j[2], a.sim), jobs))

    samples = {}
    for (t, n, c), run in zip(jobs, runs):
        samples.setdefault(t, {}).setdefault(str(n), {})[c] = run

    data = {
        "configs": {k: v[0] for k, v in simlib.CONFIGS.items()},
        "typeNames": simlib.TYPE_NAMES,
        "savedN": SAVED_N,
        "samples": samples,
        "sweeps": {
            "scaling": aggregate("scaling.csv", "nStations"),
            "hidden": aggregate("hidden.csv", "nStations"),
            "control": aggregate("control.csv", "nStations"),
            "payload": aggregate("payload.csv", "payload"),
        },
    }
    tpl = open(os.path.join(HERE, "dashboard.template.html"), encoding="utf-8").read()
    marker = "/*__DATA__*/null"
    if marker not in tpl:
        raise SystemExit("marker missing in dashboard.template.html")
    html = tpl.replace(marker, json.dumps(data, separators=(",", ":")))
    out = os.path.join(HERE, "dashboard.html")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("wrote dashboard.html (%d KB)" % (len(html) // 1024))


if __name__ == "__main__":
    main()
