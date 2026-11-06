# Dense Wi-Fi 6: CSMA/CA vs RTS/CTS vs OFDMA (ns-3 simulation)

NSCOM03 S40C, Network Simulation Study, Milestone 2 (code and demo). Group 3: Kryster Knowell Limpin, Justin Doctora, Alessandro Gabriel Rey Encarnacion XIV, De La Salle University.

## What this is

Crowded Wi-Fi gets slow because many stations fight for one channel. Wi-Fi 6 (802.11ax) has two answers:

- **RTS/CTS**: a station sends a short "request to send" and waits for the AP's "clear to send" before the long data frame. If two stations collide, only the short RTS is lost instead of a whole data frame.
- **OFDMA**: the AP splits the 20 MHz channel into small resource units and serves several stations in the same transmission instead of one at a time.

Our question: **which of the two reduces the losses in a dense cell, and when?** We simulate it in ns-3.49, the standard open-source network simulator, with one access point and N stations, and compare four setups on identical traffic:

| Setup | RTS/CTS | OFDMA |
|---|---|---|
| CSMA/CA only (baseline) | off | off |
| RTS/CTS | on | off |
| OFDMA | off | on |
| RTS/CTS + OFDMA | on | on |

For each run the simulator reports goodput (useful Mbit/s delivered), delay, packet loss and fairness. It can also dump every frame sent on the air, which is what the dashboard replays.

## What it does: the dashboard

`dashboard.html` is the prototype. It shows the four setups side by side for one station count:

- Per setup: goodput, delay, loss, fairness and the share of OFDMA transmissions.
- A **frame timeline** per setup: what the AP and the stations actually transmit, millisecond by millisecond (data, RTS, CTS, acks, OFDMA triggers), with collisions in red. Press Replay to scroll through a 20 ms capture, hover a frame for its details.
- An **airtime bar** per setup: how much of the channel went to data, control frames, collisions and idle time.
- Two scenarios: **Single cell** (everyone hears everyone) and **Hidden nodes** (two groups on opposite sides of the AP that cannot hear each other).
- Station counts from 5 to 40 (single cell) or 4 to 16 (hidden nodes), plus charts of the full sweeps (up to 60 stations).
- **Run it live**: type a station count, press *Run all four*, and ns-3 simulates it on your machine in a few seconds. This needs the one-time setup below.

Everything on the page is ns-3 output. Nothing is mocked up. The recorded timelines come from real runs saved in `results/samples/`.

## Quick start on Windows

### 1. Recorded results (no install, works right away)

Clone the repo or download it as a ZIP (Code > Download ZIP), unzip, and **double-click `dashboard.html`**. It opens in your browser and everything works except the *Run it live* box.

### 2. Live simulation (one-time setup, about 10 minutes)

ns-3 does not run on plain Windows, so it runs inside WSL2 (a real Ubuntu inside Windows). The repo ships a ready-made simulator, so there is **no compiling**.

1. Open PowerShell **as Administrator** and run `wsl --install -d Ubuntu-24.04`. Reboot if asked, then open "Ubuntu 24.04" from the Start menu once and create a username and password. (Needs Windows 10 2004+ or Windows 11, with virtualization on in the BIOS.)
2. Back in Windows, open the repo folder and **double-click `demo.bat`**. A window starts the simulator and the browser opens the dashboard at `http://localhost:8000`.

The first run unpacks the simulator (6 MB) into the Ubuntu home folder. After that it starts in a couple of seconds. Keep the `demo.bat` window open while you use the page.

From a terminal instead: `wsl bash run_demo.sh` from the repo folder. To test the setup without opening a browser: `wsl bash run_demo.sh --check`, which should end with `check passed`.

Do this setup once ahead of time, not when you need it.

### Troubleshooting

| Problem | Fix |
|---|---|
| `demo.bat` says WSL is not installed | Do step 2.1 above. |
| `python3 not found` | In Ubuntu: `sudo apt update && sudo apt install -y python3` |
| `--check` fails with a library or GLIBC error | The bundled simulator needs Ubuntu 24.04 or newer. Check with `wsl lsb_release -a`, or build from source with `bash setup_ns3.sh` (see the end of this file). |
| Browser cannot connect to `localhost:8000` | Keep the `demo.bat` window open and try `http://127.0.0.1:8000`. If the port is taken: `wsl env PORT=9000 bash run_demo.sh` and open port 9000. |
| Live run is slow | Four simulations run in parallel. 10 to 30 stations takes seconds on a desktop-class CPU, 60 stations can take minutes. Use 2 s of traffic. We have not timed it on a laptop. |
| Page stuck on "Running..." | Reload the page and run again. |

## What we found

Mean of 3 seeds. Single cell, DL + UL traffic, 200 B packets, 20 MHz. Cells show goodput (Mbit/s) / delay (ms) / loss (%).

| N | offered | CSMA/CA only | RTS/CTS | OFDMA | RTS/CTS + OFDMA |
|---|---|---|---|---|---|
| 5 | 8 | 8.00 / 1.7 / 0 | 8.00 / 2.5 / 0 | 8.00 / 2.5 / 0 | 8.00 / 2.6 / 0 |
| 10 | 16 | 15.99 / 17.8 / 0 | 15.99 / 16.9 / 0 | 15.99 / 27.7 / 0.02 | 15.99 / 7.1 / 0 |
| 20 | 32 | 22.73 / 381 / 28.9 | 26.21 / 353 / 18.0 | 20.22 / 314 / 36.7 | **29.67 / 85 / 7.2** |
| 30 | 48 | 20.17 / 241 / 57.9 | 27.59 / 182 / 42.4 | 19.38 / 210 / 59.5 | **34.04** / 314 / 28.9 |
| 40 | 64 | 19.36 / 232 / 69.7 | 31.49 / 149 / 50.6 | 18.32 / 202 / 71.3 | **34.99** / 280 / 45.2 |
| 60 | 96 | 16.23 / 232 / 83.0 | 36.03 / 162 / 62.3 | 17.03 / 228 / 82.2 | **36.19** / 246 / 62.1 |

Hidden nodes versus the same stations on one side, uplink goodput (Mbit/s):

| N | CSMA/CA hidden | CSMA/CA same side | RTS/CTS hidden | RTS/CTS same side |
|---|---|---|---|---|
| 4 | 8.00 | 8.00 | 8.00 | 8.00 |
| 8 | 8.95 | 13.55 | 15.85 | 15.81 |
| 12 | 6.49 | 12.88 | 17.44 | 18.82 |
| 16 | 4.75 | 12.39 | 17.46 | 19.28 |

Packet size, N = 30, goodput (Mbit/s), CSMA/CA vs OFDMA: 100 B 15.62 vs 16.67, 200 B 20.17 vs 19.38, 500 B 23.68 vs 22.34, 1000 B 26.18 vs 24.35.

- **RTS/CTS matters most once the cell is crowded.** At 60 stations it more than doubles goodput over plain CSMA/CA (36.0 vs 16.2) and cuts loss from 83% to 62%.
- **Hidden nodes break plain CSMA/CA.** At 16 stations it falls to 4.75 Mbit/s against 12.39 for the same stations on one side. RTS/CTS brings the hidden case back to 17.46.
- **OFDMA alone did not raise goodput here.** It is 0.8 to 2.5 Mbit/s below CSMA/CA at 20 to 40 stations (the 30-station gap is inside the seed spread) and level at 60.
- **RTS/CTS + OFDMA was best at 20 to 40 stations** (+13%, +23%, +11% over RTS/CTS alone) and tied at 60, where the channel is saturated anyway.
- **Packet size:** OFDMA only came out ahead at the smallest payload (100 B, about 2 sd, 3 seeds).
- Our paper expected OFDMA to increase throughput and reduce delay as stations grow. That is **only partly supported**: it holds for OFDMA combined with RTS/CTS and under load, not for OFDMA by itself.

## Limits

- Why OFDMA alone underperforms is a hypothesis, not tested: it still wins the channel by contention, and trigger-based uplink adds overhead (buffer status, trigger, multi-station block ack) that costs time for small frames. We did not isolate it.
- The cell is overloaded from 20 stations up (offered 32 to 96 Mbit/s against about 36 Mbit/s of capacity), so loss and delay describe a saturated cell. Delay is averaged over delivered packets only, so read it together with loss.
- "Hidden" is shown by the control comparison (same stations on one side). We did not log carrier-sense range directly.
- One AP, UDP only, fixed rate (no rate adaptation), 20 MHz, static stations, association set up directly, no neighbouring networks, no TCP.
- OFDMA setting `accessReqMs=2`: without it the AP never starts uplink OFDMA when downlink is idle (an uplink-only run showed 0% multi-user frames). Other values were not swept.
- The frame timelines show a 20 ms slice (seed 1, starting 2 s into the run). They illustrate behaviour, the numbers come from the whole runs.
- Tested on an Ubuntu server and in a clean Ubuntu 24.04 container (bundled simulator, python3 only), and the dashboard in Chromium on Linux. **Not yet run on a real Windows laptop, and `demo.bat` itself is untested.** Not run on the phone either.

## Notes for the demo

- Open the dashboard on Single cell, 30 stations. The cards already hold the comparison. Point at the timelines (a collided RTS is short, a collided data frame is long), then flip to Hidden nodes at 16 stations.
- If asked about the live box, run 10 or 20 stations with 2 s of traffic.
- If the live setup misbehaves, `dashboard.html` on its own still shows everything recorded, and `results/` has the figures and CSVs.
- When asked about OFDMA, say plainly that alone it did not beat CSMA/CA here and helped only with RTS/CTS, then point to Limits.

## How it is built

| File | What it does |
|---|---|
| `dashboard.html` | The prototype. Self-contained, opens from the file system. |
| `demo.bat`, `run_demo.sh` | Start the live dashboard on Windows (through WSL) or Linux. |
| `app.py` | Small local web server (standard library only) that runs the simulator when the page asks. Listens on 127.0.0.1 only. |
| `simlib.py` | Finds the simulator, runs one configuration, parses its output. |
| `nss-wifi6.cc` | The ns-3 scenario: topology, traffic, the four configurations, FlowMonitor metrics, optional frame trace. |
| `prebuilt/` | The compiled simulator for Linux x86_64 (6 MB, built from `nss-wifi6.cc` on ns-3.49 without CPU-specific flags, SHA-256 included). |
| `setup_ns3.sh` | Alternative: download and build ns-3.49 from source (checksum verified), about 12 min on 8 cores. |
| `demo.py` | Text-mode demo: the four setups in a table. `python3 demo.py --n 30` |
| `run_sweep.py`, `make_plots.py` | Re-run all 156 experiments (about 19 min on 8 cores) and rebuild `results/figures`. |
| `make_dashboard.py`, `dashboard.template.html` | Rebuild `dashboard.html` from the saved runs. Not needed to give the demo. |
| `results/` | Sweep CSVs (`raw/` is one file per run), 10 figures, `summary.txt`, saved demo output, `samples/` (the recorded runs behind the dashboard). |

Experiments: **scaling** (N = 5 to 60, four setups, 72 runs), **hidden** (two groups out of mutual range, 30 runs), **control** (the same stations on one side, 30 runs), **payload** (N = 30, 100 to 1000 B, 24 runs). Three seeds per point, 6 s of traffic each. Runs are deterministic: the same options and seed give the same numbers.

Setup used: 5 GHz, 20 MHz, HE MCS 5 (scaling, payload) or MCS 2 (hidden-node runs), guard interval 1600 ns, fixed rate, stations on a 5 m ring around the AP (single cell) or 38 m either side of it (hidden), UDP at 0.8 Mbit/s per station per direction with 200 B packets (single cell) or 2 Mbit/s uplink with 512 B packets (hidden).

One run by hand, from a built ns-3 folder:

    ./ns3 run "nss-wifi6 --nStations=30 --rts=1 --ofdma=1 --accessReqMs=2 --payload=200 --perStaMbps=0.8 --mcs=5 --direction=both"

Every option: `./ns3 run "nss-wifi6 --PrintHelp"`.

### Building from source instead of using the bundled simulator

On Linux or WSL (Ubuntu 24.04). `setup_ns3.sh` builds into `~/ns-3.49`, and the dashboard and demo scripts prefer that build when it exists.

    sudo apt update
    sudo apt install -y git g++ cmake ninja-build python3 curl ca-certificates bzip2 python3-pandas python3-matplotlib
    git clone https://github.com/snowyter/NSCOM03-NSS-Wifi6-Interference-Simulation.git
    cd NSCOM03-NSS-Wifi6-Interference-Simulation
    bash setup_ns3.sh
    python3 demo.py --n 30            # table in the terminal
    python3 app.py                    # dashboard at http://localhost:8000

Keep the repo and the build inside the Linux home (`~`), not under `/mnt/c/...`, where builds are very slow.
