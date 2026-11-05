"""What a Widar3.0 CSI file looks like.

Reads the .dat files in data/samples/widar3/ (generated with widar_remote.py), decodes the label
from the file name and prints the structure of the CSI.

The .dat files are raw logs of the Intel 5300 CSI Tool. Python port of read_bf_file.m +
read_bfee.c from the official csi_tool_box (only the fields used here).
"""
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples" / "widar3"

# Gesture ids are per date folder (README table). These are for 20181128.
GESTURES_20181128 = {1: "Push&Pull", 2: "Sweep", 3: "Clap", 4: "Draw-O(H)", 5: "Draw-Zigzag(H)",
                     6: "Draw-N(H)"}

np.set_printoptions(precision=2, suppress=True, linewidth=120)


def parse_name(path):
    """user6-1-1-1-1-r1.dat -> dict with the label fields."""
    m = re.fullmatch(r"user(\d+)-(\d+)-(\d+)-(\d+)-(\d+)-r(\d)\.dat", path.name)
    keys = ("user", "gesture", "location", "orientation", "repetition", "receiver")
    return dict(zip(keys, map(int, m.groups())))


def read_dat(path):
    """Return (csi, timestamps_us, rssi): csi is complex (packets, 30 subcarriers, Nrx, Ntx)."""
    raw = Path(path).read_bytes()
    csi, ts, rssi = [], [], []
    p = 0
    while p + 3 <= len(raw):
        field_len = int.from_bytes(raw[p:p + 2], "big")
        code = raw[p + 2]
        b = raw[p + 3:p + 2 + field_len]
        p += 2 + field_len
        if code != 0xBB or len(b) < field_len - 1:  # 0xBB = beamforming (CSI) record
            continue
        nrx, ntx = b[8], b[9]
        payload = np.frombuffer(b[20:], dtype=np.uint8).astype(np.uint16)
        h = np.empty((30, nrx * ntx), dtype=complex)
        index = 0
        for i in range(30):
            index += 3
            for j in range(nrx * ntx):
                k, r = index // 8, index % 8
                re_ = np.int8(((payload[k] >> r) | (payload[k + 1] << (8 - r))) & 0xFF)
                im_ = np.int8(((payload[k + 1] >> r) | (payload[k + 2] << (8 - r))) & 0xFF)
                h[i, j] = complex(re_, im_)
                index += 16
        csi.append(h.reshape(30, nrx, ntx))  # MATLAB order is [Ntx, Nrx, 30], tx fastest
        ts.append(int.from_bytes(b[0:4], "little"))
        rssi.append((b[10], b[11], b[12]))
    return np.stack(csi), np.array(ts), np.array(rssi)


files = sorted(SAMPLES.glob("*.dat"))
print(f"{len(files)} files in {SAMPLES}\n")

# 1) the label lives in the file name
f = files[0]
lab = parse_name(f)
print(f"file name: {f.name}")
for k, v in lab.items():
    extra = f"  ({GESTURES_20181128[v]})" if k == "gesture" else ""
    print(f"   {k:<12} = {v}{extra}")

# 2) what is inside one file
csi, ts, rssi = read_dat(f)
print(f"\ncsi.shape = {csi.shape}  ->  (packet, subcarrier, rx antenna, tx antenna)   dtype: {csi.dtype}")
dur = (ts[-1] - ts[0]) / 1e6
print(f"packets: {len(ts)}, duration {dur:.2f} s, ~{len(ts) / dur:.0f} packets/s")
print(f"one value, H[t=0, sub=0, rx=0, tx=0] = {csi[0, 0, 0, 0]:.0f}"
      f"  ->  |H| = {abs(csi[0, 0, 0, 0]):.2f}, ∠H = {np.angle(csi[0, 0, 0, 0]):.2f} rad")
print("one packet (t=0), amplitude |H|, first 6 subcarriers × 3 rx antennas:")
print(np.abs(csi[0, :6, :, 0]))
print(f"RSSI of the 3 antennas, first packet: {rssi[0].tolist()}")

# 3) one gesture instance = 6 files (one per receiver), with different lengths
print("\none gesture instance (same name except -rN) across the 6 receivers:")
inst = sorted(SAMPLES.glob(f.name.rsplit("-r", 1)[0] + "-r*.dat"))
data = {}
for g in inst:
    c, t, _ = read_dat(g)
    data[parse_name(g)["receiver"]] = c
    print(f"   {g.name}: {c.shape[0]} packets, {(t[-1] - t[0]) / 1e6:.2f} s")

print("\nall files in the sample (packets per file):")
for g in files:
    lab = parse_name(g)
    print(f"   {g.name}  gesture={GESTURES_20181128[lab['gesture']]:<15} {read_dat(g)[0].shape[0]} packets")

fig, axs = plt.subplots(2, 3, figsize=(11, 5.5), sharey=True, layout="constrained")
vmax = np.percentile(np.abs(np.concatenate([c[..., 0, 0] for c in data.values()])), 99)
for ax, (rx, c) in zip(axs.flat, sorted(data.items())):
    im = ax.imshow(np.abs(c[:, :, 0, 0]).T, aspect="auto", origin="lower", cmap="Blues",
                   vmin=0, vmax=vmax, interpolation="nearest")
    ax.set_title(f"receiver r{rx}, antenna 1", fontsize=9, loc="left")
    ax.set_xlabel("packet (time)")
axs[0, 0].set_ylabel("subcarrier")
axs[1, 0].set_ylabel("subcarrier")
fig.colorbar(im, ax=axs, label="|H|")
lab = parse_name(f)
fig.suptitle(f"{f.name.rsplit('-r', 1)[0]} — gesture «{GESTURES_20181128[lab['gesture']]}», amplitude",
             x=0.01, ha="left", fontsize=10)
fig.savefig(Path(__file__).parent / "amplitude_one_instance.png", dpi=130)
