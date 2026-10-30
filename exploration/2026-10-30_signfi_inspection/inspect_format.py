"""What a SignFi array looks like (downlink, lab and home).

Reads the samples in data/samples/ (generated with signfi_remote.py) and prints their structure.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
NAMES = open(SAMPLES / "sign_labels.csv", encoding="utf-8-sig").read().splitlines()

np.set_printoptions(precision=2, suppress=True, linewidth=120)

for fname, var in [("dataset_lab_276_dl__csid_lab__300.npz", "csid_lab"),
                   ("dataset_home_276__csid_home__300.npz", "csid_home")]:
    d = np.load(SAMPLES / fname)
    csi, labels = d["csi"], d["labels_all"]
    print(f"\n=== {var} (sample of the first {csi.shape[-1]} instances)")
    print(f"shape: {csi.shape}  ->  (time, subcarrier, antenna, instance)   dtype: {csi.dtype}")

    x = csi[..., 0]  # one instance = one gesture
    print(f"\none instance: {x.shape} = 200 packets × 30 subcarriers × 3 antennas")
    print(f"one value, H[t=0, sub=0, ant=0] = {x[0, 0, 0]:.2f}")
    print(f"   amplitude |H| = {abs(x[0, 0, 0]):.2f}   phase ∠H = {np.angle(x[0, 0, 0]):.2f} rad")

    print("\none packet (t=0), amplitude |H|, first 6 subcarriers × 3 antennas:")
    print(np.abs(x[0, :6, :]))

    print(f"\nlabels: {labels.shape}, values 1..{labels.max()}, first 5: {labels[:5].tolist()}")
    print("   ", [NAMES[i - 1] for i in labels[:5]])
    print(f"   interleaved: index 276 is word {labels[276]} again")

    if var == "csid_lab":
        a = np.abs(x)
        fig, axs = plt.subplots(1, 3, figsize=(11, 3.2), sharey=True, layout="constrained")
        for k in range(3):
            im = axs[k].imshow(a[:, :, k].T, aspect="auto", origin="lower", cmap="Blues",
                               vmin=0, vmax=np.percentile(a, 99), interpolation="nearest")
            axs[k].set_title(f"antenna {k + 1}", fontsize=9, loc="left")
            axs[k].set_xlabel("packet (time)")
        axs[0].set_ylabel("subcarrier")
        fig.colorbar(im, ax=axs, label="|H|")
        fig.suptitle(f"csid_lab[:, :, :, 0] — word «{NAMES[labels[0] - 1]}», amplitude",
                     x=0.01, ha="left", fontsize=10)
        fig.savefig(Path(__file__).parent / "amplitude_one_instance.png", dpi=130)
