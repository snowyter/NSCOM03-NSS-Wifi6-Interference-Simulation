"""Shared helpers: find the compiled scenario, run one configuration, parse the result.

Used by app.py (live dashboard) and make_dashboard.py (saved sample runs).
Standard library only.
"""
import csv
import glob
import os
import subprocess
import tempfile

CONFIGS = {
    "baseline": ("CSMA/CA only", ["--rts=0", "--ofdma=0"]),
    "rts": ("RTS/CTS", ["--rts=1", "--ofdma=0"]),
    "ofdma": ("OFDMA", ["--rts=0", "--ofdma=1", "--accessReqMs=2"]),
    "rts+ofdma": ("RTS/CTS + OFDMA", ["--rts=1", "--ofdma=1", "--accessReqMs=2"]),
}

# the two scenarios shown in the demo (same settings as the sweeps and demo.py)
SCENARIOS = {
    "single": ["--topology=single", "--direction=both", "--payload=200", "--perStaMbps=0.8", "--mcs=5"],
    "hidden": ["--topology=hidden", "--hiddenOffset=38", "--direction=ul", "--payload=512",
               "--perStaMbps=2", "--mcs=2"],
}

TYPE_NAMES = ["Data", "RTS", "CTS", "Ack", "BlockAck", "BlockAckReq", "Trigger", "Null", "Other"]
_TYPE_INDEX = {
    "QOSDATA": 0, "DATA": 0,
    "CTL_RTS": 1, "CTL_CTS": 2, "CTL_ACK": 3, "CTL_BACKRESP": 4, "CTL_BACKREQ": 5,
    "CTL_TRIGGER": 6, "QOSDATA_NULL": 7, "DATA_NULL": 7,
}

WINDOW_START = 2.0   # seconds of simulated time, traffic runs from 1 s
WINDOW_LEN = 0.02    # 20 ms of frames
PRE = 0.006          # longest PPDU is 5.5 ms: capture earlier so frames already on air at the start are kept


def default_ns3():
    """Where to look for the compiled scenario when --ns3 is not given."""
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.environ.get("NS3_DIR"), os.path.join(here, "ns3-prebuilt"), os.path.expanduser("~/ns-3.49"),
              os.path.join(os.environ.get("NSS_HOME", os.path.expanduser("~/.nss-wifi6")), "ns3-prebuilt")):
        if d and glob.glob(os.path.join(d, "build", "scratch", "ns3.*-nss-wifi6*")):
            return d
    return os.path.expanduser("~/ns-3.49")


def find_binary(ns3_dir):
    hits = glob.glob(os.path.join(ns3_dir, "build", "scratch", "ns3.*-nss-wifi6*"))
    hits = [h for h in hits if os.path.isfile(h) and os.access(h, os.X_OK)]
    if not hits:
        raise FileNotFoundError("scenario not built in %s (run ./setup_ns3.sh)" % ns3_dir)
    return hits[0]


def child_env(ns3_dir):
    """Environment for the binary: find the ns-3 libraries next to it, wherever the tree was unpacked."""
    env = dict(os.environ)
    lib = os.path.join(ns3_dir, "build", "lib")
    env["LD_LIBRARY_PATH"] = lib + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    return env


def run_one(ns3_dir, config, n, topology, sim=3.0, seed=1, with_trace=True):
    """Run one configuration. Returns a dict of metrics plus a compact frame trace."""
    if config not in CONFIGS:
        raise ValueError("unknown config " + config)
    if topology not in SCENARIOS:
        raise ValueError("unknown topology " + topology)
    binary = find_binary(ns3_dir)
    name, cfg_args = CONFIGS[config]
    with tempfile.TemporaryDirectory() as tmp:
        res = os.path.join(tmp, "r.csv")
        trc = os.path.join(tmp, "t.csv")
        cmd = [binary, "--nStations=%d" % n, "--simTime=%g" % sim, "--seed=%d" % seed,
               "--csv=" + res] + SCENARIOS[topology] + cfg_args
        if with_trace:
            cmd += ["--trace=" + trc, "--traceFrom=%g" % (WINDOW_START - PRE),
                    "--traceTo=%g" % (WINDOW_START + WINDOW_LEN)]
        subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=True, env=child_env(ns3_dir))
        row = next(csv.DictReader(open(res)))
        trace = []
        if with_trace and os.path.exists(trc):
            t0 = int(WINDOW_START * 1e6)
            for r in csv.DictReader(open(trc)):
                start, dur = int(r["startUs"]) - t0, int(r["durUs"])
                if start + dur <= 0:          # ended before the window
                    continue
                trace.append([start, int(r["node"]), _TYPE_INDEX.get(r["type"], 8),
                              dur, int(r["bytes"]), int(r["mpdus"]), int(r["receivers"]),
                              int(r["mu"]), int(r["retry"])])
    return {
        "config": config, "name": name, "n": n, "topology": topology, "sim": sim, "seed": seed,
        "goodputMbps": round(float(row["goodputMbps"]), 2),
        "offeredMbps": round(float(row["offeredMbps"]), 2),
        "meanDelayMs": round(float(row["meanDelayMs"]), 1),
        "lossPct": round(float(row["lossPct"]), 1),
        "jain": round(float(row["jain"]), 2),
        "muPct": round(float(row["muPct"]), 1),
        "wallSec": round(float(row["wallSec"]), 1),
        "trace": trace,
        "window": [0, int(WINDOW_LEN * 1e6)],
    }
