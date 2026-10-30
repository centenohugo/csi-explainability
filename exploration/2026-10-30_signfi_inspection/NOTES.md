# 2026-10-30 · SignFi data format

Goal: see what the SignFi arrays look like and how they are structured (downlink, which is what the
paper uses), without downloading the ~6 GB.

## Scripts

- `signfi_remote.py`: reads the `.mat` files directly from Box and keeps only the first 300 instances
  in `data/samples/`. Samples generated: `csid_lab` and `csid_home`.
- `inspect_format.py`: prints the structure of an array and plots the amplitude of one instance
  (`amplitude_one_instance.png`).

## Dataset files

| File | Variables | CSI shape | Instances |
|---|---|---|---|
| `dataset_lab_276_dl.mat` (1.44 GB) | `csid_lab`, `label_lab` | 200×30×3×5520 | 276 words × 20 repetitions, 1 user |
| `dataset_lab_276_ul.mat` (1.33 GB) | `csiu_lab`, `label_lab` | 200×30×3×5520 | same, uplink |
| `dataset_home_276.mat` (1.37 GB) | `csid_home`, `csiu_home`, `label_home` | 200×30×3×2760 | 276 × 10, 1 user |
| `dataset_lab_150.mat` (1.93 GB) | `label`, `csi1`…`csi5` | 200×30×3×1500 each | 150 words × 10 × 5 users |

`csid_*` = downlink, `csiu_*` = uplink.

## Array structure

```
csid_lab.shape = (200, 30, 3, 5520)
                  │    │   │   └─ instance (one recorded gesture)
                  │    │   └───── antenna (the AP's 3 antennas)
                  │    └───────── subcarrier (30, Intel 5300 grouping)
                  └────────────── time sample (WiFi packet)
```

- Each element is a **complex** number (`complex128`): `H = a + jb`.
  Amplitude `abs(H)`, phase `angle(H)`. Example: `H[0,0,0,0] = 55.61 + 9.02j` → |H| = 56.33, ∠H = 0.16 rad.
- **One instance** = `csid_lab[:, :, :, i]` = a 200 × 30 × 3 cube: how the channel changes over
  30 frequencies and 3 antennas while a gesture is performed.
- **One packet** = `csid_lab[t, :, :, i]` = a 30 × 3 matrix: a snapshot of the channel at one instant.
- **Labels** (`label_lab`): vector of 5520 integers from 1 to 276. Each word's name is on the
  matching line of `sign_labels.csv` (1 = FINISH, 2 = GO, …).
  They are interleaved (1, 2, …, 276, 1, 2, …), so repetition `r` of word `w` is at index
  `(r-1)*276 + (w-1)`.
- The example in the SignFi README feeds the CNN with `[abs(csi), angle(csi)]`.
