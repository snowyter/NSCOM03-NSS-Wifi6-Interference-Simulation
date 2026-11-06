# NSS Milestone 2 - Dense Wi-Fi 6: CSMA/CA vs RTS/CTS vs OFDMA (ns-3.49)

Group 3, NSCOM03 S40C: Kryster Knowell Limpin, Justin Doctora, Alessandro Gabriel Rey Encarnacion XIV (De La Salle University). Topic: reducing interference/contention in dense Wi-Fi 6 networks.
Simulator: ns-3.49 (released Oct 7 2026), 802.11ax, SpectrumWifiPhy, one AP, N stations.

## What is in this folder

| File | What it does |
|---|---|
| `setup_ns3.sh` | One command: downloads ns-3.49 (checksum verified), builds only the modules we need, builds the scenario, runs a smoke test. |
| `nss-wifi6.cc` | The ns-3 scenario. One run = one configuration, one N, one seed. Appends a CSV row. |
| `run_sweep.py` | Runs every experiment (4 configs x N x 3 seeds), in parallel, resumable. |
| `make_plots.py` | Turns `results/*.csv` into 10 figures and `results/summary.txt`. |
| `demo.py` | Live demo: the four configurations side by side at one N (30-40 s). |
| `results/` | The data and figures from our run (`raw/` = one CSV per run), plus saved demo output. Viewable on any OS, no build needed. |

## The four configurations

| Name | RTS/CTS | OFDMA |
|---|---|---|
| CSMA/CA only (baseline) | off | off |
| RTS/CTS | on, every frame (`RtsCtsThreshold=0`) | off |
| OFDMA | off | DL + UL, round-robin scheduler, up to 9 stations per transmission, BSRP, AP requests channel access every 2 ms |
| RTS/CTS + OFDMA | on | on |

Same PHY (SpectrumWifiPhy), same fixed rate, same traffic in all four, so only the MAC differs.

## Setup (what was actually run)

- 5 GHz, 20 MHz, HE MCS 5 (scaling, payload) or MCS 2 (hidden-node runs), guard interval 1600 ns, fixed rate (no rate adaptation).
- Stations static, on a ring of radius 5 m around the AP (all in range of each other), static association and block-ack.
- UDP, constant rate, 0.8 Mbit/s per station per direction, 200 B payload, DL and UL together. 6 s of traffic, 3 seeds (`RngRun` 1-3), mean +/- sd.
- Metrics from FlowMonitor: aggregate goodput, mean one-way delay (delivered packets only), loss, Jain fairness. Also the share of PPDUs sent as multi-user (a check that OFDMA is really used).

## Experiments

1. **scaling** - N = 5, 10, 20, 30, 40, 60, single cell, all four configs. (72 runs)
2. **hidden** - two groups of stations on opposite sides of the AP, 38 m each (out of range of each other, both reach the AP), uplink only, baseline vs RTS/CTS. N = 2-16. (30 runs)
3. **control** - the same stations stacked on ONE side (they hear each other). Compare with 2 to separate the hidden-node effect from plain crowding. (30 runs)
4. **payload** - N = 30, same offered load, payload 100/200/500/1000 B, baseline vs OFDMA. (24 runs)

Full sweep: 156 runs, about 19 minutes on 6 parallel jobs (8-core server).

## Results (mean of 3 seeds)

Scaling, single cell, DL+UL, 200 B. Cell shows goodput (Mbit/s) / delay (ms) / loss (%).

| N | offered | CSMA/CA only | RTS/CTS | OFDMA | RTS/CTS + OFDMA |
|---|---|---|---|---|---|
| 5 | 8 | 8.00 / 1.7 / 0 | 8.00 / 2.5 / 0 | 8.00 / 2.5 / 0 | 8.00 / 2.6 / 0 |
| 10 | 16 | 15.99 / 17.8 / 0 | 15.99 / 16.9 / 0 | 15.99 / 27.7 / 0.02 | 15.99 / 7.1 / 0 |
| 20 | 32 | 22.73 / 381 / 28.9 | 26.21 / 353 / 18.0 | 20.22 / 314 / 36.7 | **29.67 / 85 / 7.2** |
| 30 | 48 | 20.17 / 241 / 57.9 | 27.59 / 182 / 42.4 | 19.38 / 210 / 59.5 | **34.04** / 314 / 28.9 |
| 40 | 64 | 19.36 / 232 / 69.7 | 31.49 / 149 / 50.6 | 18.32 / 202 / 71.3 | **34.99** / 280 / 45.2 |
| 60 | 96 | 16.23 / 232 / 83.0 | 36.03 / 162 / 62.3 | 17.03 / 228 / 82.2 | **36.19** / 246 / 62.1 |

Hidden nodes vs same-side control, uplink goodput (Mbit/s):

| N | baseline hidden | baseline same side | RTS/CTS hidden | RTS/CTS same side |
|---|---|---|---|---|
| 4 | 8.00 | 8.00 | 8.00 | 8.00 |
| 8 | 8.95 | 13.55 | 15.85 | 15.81 |
| 12 | 6.49 | 12.88 | 17.44 | 18.82 |
| 16 | 4.75 | 12.39 | 17.46 | 19.28 |

Payload size, N = 30, goodput (Mbit/s): 100 B 15.62 vs 16.67 (CSMA/CA vs OFDMA); 200 B 20.17 vs 19.38; 500 B 23.68 vs 22.34; 1000 B 26.18 vs 24.35.

## What the data says

- **RTS/CTS is the big lever once the cell is crowded.** At N=60 it more than doubles goodput over CSMA/CA only (36.0 vs 16.2 Mbit/s) and cuts loss from 83 % to 62 %. This holds even when every station hears every other, because a collided RTS wastes far less airtime than a collided data frame.
- **Hidden nodes make plain CSMA/CA collapse.** At N=16 the baseline falls to 4.75 Mbit/s versus 12.39 for the same stations on one side. RTS/CTS brings the hidden case back to 17.46 (about 91 % of the same-side RTS figure).
- **OFDMA alone did not raise goodput in our setup.** It is 0.8-2.5 Mbit/s below CSMA/CA at N = 20-40 and level at N = 60. The gap is clear at N = 20 and 40 but inside the seed spread at N = 30. It does cut delay a little at N >= 20 (for example 210 vs 241 ms at N=30) but raises it at small N.
- **OFDMA plus RTS/CTS gave the best goodput at N = 20-40**, +13 %, +23 %, +11 % over RTS/CTS alone, and tied at N = 60 where the channel is saturated either way. Its delay is better at N=20 (85 vs 353 ms) and worse at N = 30-40.
- **Packet size:** OFDMA only came out ahead at the smallest payload (100 B, +1.05 Mbit/s, roughly 2 sd, only 3 seeds) and fell behind as packets grew.
- The paper's expected outcome ("OFDMA increases throughput and reduces delay as the number of stations increases") is **only partly supported**: OFDMA helps when combined with RTS/CTS and under load, not on its own. The paper should say so.

## Limits and things not verified

- Why OFDMA alone underperforms is a hypothesis, not tested: TXOP acquisition still goes through contention and collides, and trigger-based UL adds overhead (BSRP, trigger, multi-STA block ack) for small frames. We did not isolate it.
- The cell is overloaded for N >= 20 (offered 32-96 Mbit/s against about 36 Mbit/s of capacity), so loss and delay describe a saturated cell. Delay is averaged over delivered packets only, so read it together with loss.
- "Hidden" is shown by the control comparison. Carrier-sense range was not logged directly.
- One AP, UDP only, fixed MCS, 20 MHz, static stations, no mobility, no rate adaptation, no TCP, no interference from neighbouring BSSs. Association is static (set up directly), so association storms are not modelled.
- The OFDMA setting `accessReqMs=2` was chosen because without it the AP never starts UL OFDMA when downlink is idle (an uplink-only run showed 0 % multi-user PPDUs). Other values were not swept.
- Built and run on an Ubuntu server. `setup_ns3.sh` was also run end to end in a clean Ubuntu 24.04 container (apt packages only, 4 jobs): download, checksum, build, smoke test, then `demo.py --n 30` gave the same numbers as the server build. It has not been run on real Windows/WSL2 or on the phone.

## Reproduce

ns-3 builds on Linux and macOS. On Windows it runs inside WSL2 (Ubuntu), see the next section.
You need g++, cmake >= 3.25, ninja and python3. On Ubuntu 24.04 everything comes from apt:

    sudo apt update
    sudo apt install -y git g++ cmake ninja-build python3 curl ca-certificates bzip2 python3-pandas python3-matplotlib

    git clone <this repo> nss-wifi6 && cd nss-wifi6
    ./setup_ns3.sh                       # downloads + builds ns-3.49 into ~/ns-3.49, then a smoke test

    python3 demo.py --ns3 ~/ns-3.49 --n 30         # live demo, about 40 s
    python3 demo.py --ns3 ~/ns-3.49 --n 12 --topology hidden
    python3 run_sweep.py --ns3 ~/ns-3.49           # full sweep, about 19 min on 8 cores
    python3 make_plots.py                          # rebuilds results/figures

One run by hand (from the ns-3 folder):

    ./ns3 run "nss-wifi6 --nStations=30 --rts=1 --ofdma=1 --accessReqMs=2 --payload=200 --perStaMbps=0.8 --mcs=5 --direction=both"

Every option: `./ns3 run "nss-wifi6 --PrintHelp"`. Runs are deterministic: the same options and seed give the same numbers.

## Running it from a Windows laptop

Two separate things, and only the second needs setup:

1. **Showing the results needs nothing but Windows.** Download the repo as a ZIP (Code > Download ZIP) or clone it. Open
   `results/figures/*.png`, `results/summary.txt`, `results/*.csv` and this README directly. `results/demo_N30_single.txt` and
   `results/demo_N12_hidden.txt` are saved outputs of `demo.py`.
2. **Running the simulation live needs Linux.** ns-3 does not build on plain Windows, so use WSL2 (a real Ubuntu inside Windows, from Microsoft).

One-time WSL2 setup (Windows 10 2004+ or Windows 11, virtualization enabled in BIOS):

    # PowerShell as Administrator
    wsl --install -d Ubuntu-24.04
    # reboot when asked, then open "Ubuntu 24.04" from the Start menu and create a username + password

Then inside the Ubuntu window:

    sudo apt update
    sudo apt install -y git g++ cmake ninja-build python3 curl ca-certificates bzip2 python3-pandas python3-matplotlib
    cd ~                                   # stay in the Linux home, NOT /mnt/c/... (the Windows disk is very slow for builds)
    git clone <this repo> nss-wifi6 && cd nss-wifi6
    ./setup_ns3.sh                         # the long step: build it BEFORE the demo day
    python3 demo.py --ns3 ~/ns-3.49 --n 30

Tips:
- To open the figures in Windows from Ubuntu: `explorer.exe results/figures` (or browse to `\\wsl$\Ubuntu-24.04\home\<you>\nss-wifi6`).
- WSL2 gets half of the laptop's RAM by default. 8 GB of RAM is enough because `setup_ns3.sh` picks the number of parallel jobs from free memory. If the build is killed, run `JOBS=2 ./setup_ns3.sh`.
- Build time depends on the laptop's core count. It took about 12 minutes on an 8-thread server. Expect longer on a laptop; we have not measured it.
- Do the build once, ahead of time, and leave it. In front of the professor you only run `demo.py`, which takes under a minute.
- If the laptop is not usable, `demo.py` can be run on the group server from any laptop over SSH, or shown from the saved output and figures above.
