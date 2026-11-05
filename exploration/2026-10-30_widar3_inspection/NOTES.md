# 2026-10-30 · Widar3.0 data format

Goal: see what the Widar3.0 CSI files look like and how the labels are stored, without downloading
the full dataset (~60 GB of CSI zips).

## Where the data is

IEEE DataPort needs an account, but the Widar3.0 homepage also links a public Tsinghua Cloud
share (no login) with the same files: `CSI/*.zip` (one per collection date, 1–9 GB each), `BVP/BVP.zip`
(0.4 GB), the extraction code and `csi_tool_box.zip` (the Intel 5300 CSI Tool parser).

## Scripts

- `widar_remote.py`: lists the share and extracts single `.dat` files from a remote zip using HTTP
  Range requests (reading the zip index costs ~0.5 MB). Sample generated: `/CSI/20181128.zip`
  (room 2, user 6), the 6 gestures at location 1, orientation 1, repetition 1, all 6 receivers →
  36 files, 13 MB, in `data/samples/widar3/`.
- `inspect_format.py`: parses the `.dat` files (Python port of `read_bfee.c`), decodes the label from
  the file name and plots the amplitude of one instance on the 6 receivers (`amplitude_one_instance.png`).

## Labels: in the file name

```
user6-1-1-1-1-r1.dat
    │ │ │ │ │  └─ receiver (1..6, six WiFi receivers around the user)
    │ │ │ │ └──── repetition
    │ │ │ └────── face orientation (1..5, -90° to +90°)
    │ │ └──────── torso location (1..8, coordinates in the README)
    │ └────────── gesture id
    └──────────── user id
```

- The **gesture id depends on the date folder**: in `20181128` 1 = Push&Pull, 2 = Sweep, 3 = Clap,
  4 = Draw-O(H), 5 = Draw-Zigzag(H), 6 = Draw-N(H), but in `20181130` 4 = Slide. The mapping is the
  table in the README (`README_IEEE_DataPort.pdf`).
- `20181128.zip` = 4500 files = 6 gestures × 5 locations × 5 orientations × 5 repetitions × 6 receivers,
  all from user 6.
- The README lists 7 empty `.dat` files to skip.

## What is inside one `.dat`

Raw log of the Intel 5300 CSI Tool: a sequence of records, one per received packet.

```
csi.shape = (1452, 30, 3, 1)
              │    │   │  └─ tx antenna (1 in this sample)
              │    │   └──── rx antenna (3 per receiver)
              │    └──────── subcarrier (30, Intel 5300 grouping, same as SignFi)
              └───────────── packet (time), ~1000 packets/s
```

- Each value is complex, `H = a + jb` with integer `a, b` (raw, unscaled; `get_scaled_csi.m` in the
  toolbox converts to absolute units). Example: `H[0,0,0,0] = -10-22j` → |H| = 24.17, ∠H = -2.00 rad.
- Each record also has a timestamp (µs), the RSSI of the 3 antennas, noise, AGC, etc.
- **Length is not fixed**: 1188–1721 packets per file in the sample (~1.2–1.7 s), and the 6 receivers
  of the same instance do not have exactly the same number of packets (1439–1455 for Push&Pull).
- **One gesture instance = 6 files** (same name except `-rN`), i.e. 6 × 3 = 18 antenna streams.

## Comparison with SignFi (format only)

| | SignFi | Widar3.0 |
|---|---|---|
| Labels | `label_*` vector inside the `.mat` | file name (user, gesture, location, orientation, repetition, receiver) |
| Storage | one big `.mat` array, all instances | one `.dat` per instance and receiver |
| One instance | 200 × 30 × 3, fixed | ~1200–1700 × 30 × 3 per receiver, variable, × 6 receivers |
| Values | complex, already parsed | complex, raw Intel 5300 log to parse |
| Extra | — | precomputed BVP (`.mat`, 20 × 20 × T) with the same naming |
