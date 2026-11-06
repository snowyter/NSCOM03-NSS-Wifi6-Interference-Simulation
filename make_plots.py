#!/usr/bin/env python3
"""Turn results/*.csv into figures + a summary table.

Usage: python3 make_plots.py [results_dir]
Needs pandas and matplotlib.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

res = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
figs = os.path.join(res, "figures")
os.makedirs(figs, exist_ok=True)

STYLE = {
    "baseline": dict(color="#555555", marker="o", label="CSMA/CA only"),
    "rts": dict(color="#d95f02", marker="s", label="RTS/CTS"),
    "ofdma": dict(color="#1b9e77", marker="^", label="OFDMA"),
    "rts+ofdma": dict(color="#7570b3", marker="D", label="RTS/CTS + OFDMA"),
}


def agg(df, x, y):
    g = df.groupby(["label", x])[y].agg(["mean", "std", "count"]).reset_index()
    g["std"] = g["std"].fillna(0)
    return g


def line_plot(df, x, y, ylabel, title, fname, xlabel, logx=False):
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    g = agg(df, x, y)
    for cfg, st in STYLE.items():
        d = g[g.label == cfg].sort_values(x)
        if d.empty:
            continue
        ax.errorbar(d[x], d["mean"], yerr=d["std"], capsize=3, lw=1.6, ms=6, **st)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    if logx:
        ax.set_xscale("log")
    fig.tight_layout()
    fig.savefig(os.path.join(figs, fname), dpi=160)
    plt.close(fig)


summary = []

# A: scaling
p = os.path.join(res, "scaling.csv")
if os.path.exists(p):
    d = pd.read_csv(p)
    line_plot(d, "nStations", "goodputMbps", "Aggregate goodput (Mbit/s)",
              "Single cell, DL+UL, 200 B packets: goodput vs stations", "scaling_goodput.png", "Stations (N)")
    line_plot(d, "nStations", "meanDelayMs", "Mean one-way delay (ms)",
              "Single cell: delay vs stations", "scaling_delay.png", "Stations (N)")
    line_plot(d, "nStations", "lossPct", "Packet loss (%)",
              "Single cell: loss vs stations", "scaling_loss.png", "Stations (N)")
    line_plot(d, "nStations", "jain", "Jain fairness index",
              "Single cell: fairness vs stations", "scaling_fairness.png", "Stations (N)")
    t = d.groupby(["nStations", "label"])[["goodputMbps", "meanDelayMs", "lossPct", "jain", "muPct"]].mean().round(2)
    summary.append(("scaling (single cell, DL+UL, 200 B)", t))

# B: hidden node
p = os.path.join(res, "hidden.csv")
if os.path.exists(p):
    d = pd.read_csv(p)
    line_plot(d, "nStations", "goodputMbps", "Uplink goodput (Mbit/s)",
              "Hidden nodes, uplink: goodput vs stations", "hidden_goodput.png", "Stations (N)")
    line_plot(d, "nStations", "lossPct", "Packet loss (%)",
              "Hidden nodes, uplink: loss vs stations", "hidden_loss.png", "Stations (N)")
    line_plot(d, "nStations", "meanDelayMs", "Mean one-way delay (ms)",
              "Hidden nodes, uplink: delay vs stations", "hidden_delay.png", "Stations (N)")
    t = d.groupby(["nStations", "label"])[["goodputMbps", "meanDelayMs", "lossPct", "jain"]].mean().round(2)
    summary.append(("hidden nodes (two groups out of mutual range, UL)", t))

# B2: hidden vs same-side control, baseline and RTS side by side
ph, pc = os.path.join(res, "hidden.csv"), os.path.join(res, "control.csv")
if os.path.exists(ph) and os.path.exists(pc):
    h, c = pd.read_csv(ph), pd.read_csv(pc)
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    for df, tag, ls in ((h, "hidden", "-"), (c, "same side", "--")):
        g = agg(df, "nStations", "goodputMbps")
        for cfg in ("baseline", "rts"):
            d = g[g.label == cfg].sort_values("nStations")
            st = STYLE[cfg]
            ax.errorbar(d["nStations"], d["mean"], yerr=d["std"], capsize=3, lw=1.6, ms=6, ls=ls,
                        color=st["color"], marker=st["marker"], label=f"{st['label']} - {tag}")
    ax.set_xlabel("Stations (N)")
    ax.set_ylabel("Uplink goodput (Mbit/s)")
    ax.set_title("Hidden-node effect: same stations, hidden vs same side", fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(figs, "hidden_vs_control.png"), dpi=160)
    plt.close(fig)
    t = pd.concat([h.assign(topo="hidden"), c.assign(topo="same side")]).groupby(
        ["nStations", "topo", "label"])[["goodputMbps", "meanDelayMs", "lossPct"]].mean().round(2)
    summary.append(("hidden-node control (hidden vs same-side, UL)", t))

# C: payload size
p = os.path.join(res, "payload.csv")
if os.path.exists(p):
    d = pd.read_csv(p)
    line_plot(d, "payload", "goodputMbps", "Aggregate goodput (Mbit/s)",
              "N=30, same offered load: goodput vs packet size", "payload_goodput.png", "UDP payload (bytes)")
    line_plot(d, "payload", "meanDelayMs", "Mean one-way delay (ms)",
              "N=30, same offered load: delay vs packet size", "payload_delay.png", "UDP payload (bytes)")
    t = d.groupby(["payload", "label"])[["goodputMbps", "meanDelayMs", "lossPct", "jain", "muPct"]].mean().round(2)
    summary.append(("payload size (N=30)", t))

with open(os.path.join(res, "summary.txt"), "w") as fh:
    for name, t in summary:
        fh.write(f"=== {name} ===\n{t.to_string()}\n\n")
print(open(os.path.join(res, "summary.txt")).read() if summary else "no results found")
print("figures:", sorted(os.listdir(figs)))
