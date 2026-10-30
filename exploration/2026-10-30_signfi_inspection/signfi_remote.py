"""Partial access to the SignFi .mat files hosted on Box, without downloading them in full.

The .mat files are MATLAB v5 (not HDF5): each variable is an independent miCOMPRESSED (zlib)
element. Box supports HTTP Range requests, so:
  - headers and labels are read with a few KB;
  - CSI is decompressed on the fly and only the first K instances are kept.

Note: CSI is complex and MATLAB stores ALL the real part first and then ALL the imaginary part
(column-major, instance on the last axis). Rebuilding the first K complex instances requires
streaming through ~50 % of the variable.

Usage:
  python signfi_remote.py map                       # print the variables in each file
  python signfi_remote.py sample <file> <var> <K>   # save data/samples/<file>__<var>__K.npz
"""
import re
import struct
import sys
import time
import urllib.request
import zlib
from pathlib import Path

import numpy as np

SHARES = {
    "dataset_lab_276_dl.mat": "z9vsrn3998n4xyzkpqtj89yclk28eatp",
    "dataset_lab_276_ul.mat": "5hr4u7lsj10c329oibp8fjv95i524tnl",
    "dataset_home_276.mat": "mmikgi9ubkg7vnwaztplnxudh8sgj1np",
    "dataset_lab_150.mat": "kidoq54rv93ysojgzv7xjqixyzwir7lq",
}
MI_TYPES = {1: np.int8, 2: np.uint8, 3: np.int16, 4: np.uint16, 5: np.int32, 6: np.uint32,
            7: np.float32, 9: np.float64, 12: np.int64, 13: np.uint64}
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"


def file_url(fname):
    share = SHARES[fname]
    html = urllib.request.urlopen(f"https://wm1693.box.com/s/{share}").read().decode()
    fid = re.search(r'"typedID":"(f_\d+)"', html).group(1)
    return (f"https://wm1693.app.box.com/index.php?rm=box_download_shared_file"
            f"&shared_name={share}&file_id={fid}")


def open_range(url, start, end=""):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    return urllib.request.urlopen(req)


def get_range(url, start, end):
    with open_range(url, start, end) as r:
        return r.read(), int(r.headers["Content-Range"].split("/")[1])


def parse_matrix_header(buf):
    """Header of a decompressed miMATRIX -> name, dims, complex flag and data offset."""
    t, _ = struct.unpack("<II", buf[:8])
    assert t == 14, f"expected miMATRIX, got type {t}"
    flags, = struct.unpack("<I", buf[16:20])
    p = 24
    _, dn = struct.unpack("<II", buf[p:p + 8])
    dims = struct.unpack(f"<{dn // 4}i", buf[p + 8:p + 8 + dn])
    p += 8 + ((dn + 7) // 8) * 8
    t0, = struct.unpack("<I", buf[p:p + 4])
    if t0 >> 16:  # small data element format (name <= 4 bytes)
        name = buf[p + 4:p + 4 + (t0 >> 16)].decode()
        p += 8
    else:
        ln, = struct.unpack("<I", buf[p + 4:p + 8])
        name = buf[p + 8:p + 8 + ln].decode()
        p += 8 + ((ln + 7) // 8) * 8
    return dict(name=name, dims=dims, complex=bool(flags & 0x800), data_offset=p)


def list_vars(url):
    """Walk the top-level elements jumping from header to header."""
    _, total = get_range(url, 0, 127)
    off, out = 128, []
    while off < total:
        tag, _ = get_range(url, off, off + 8 + 4095)
        t, n = struct.unpack("<II", tag[:8])
        assert t == 15, "only compressed variables are supported"
        head = zlib.decompressobj().decompress(tag[8:], 1024)
        out.append(dict(parse_matrix_header(head), file_offset=off, compressed_bytes=n))
        off += 8 + n
    return out, total


class _Stream:
    """Iterator over the decompressed bytes of a variable, reading from the network in chunks."""

    def __init__(self, url, var, chunk=1 << 20):
        self.resp = open_range(url, var["file_offset"] + 8, var["file_offset"] + 7 + var["compressed_bytes"])
        self.z = zlib.decompressobj()
        self.buf = bytearray()
        self.chunk = chunk
        self.net_bytes = 0

    def read(self, n):
        while len(self.buf) < n:
            c = self.resp.read(self.chunk)
            if not c:
                raise EOFError
            self.net_bytes += len(c)
            self.buf += self.z.decompress(c)
        out, self.buf = bytes(self.buf[:n]), self.buf[n:]
        return out

    def skip(self, n):
        while n > 0:
            k = min(n, 1 << 24)
            self.read(k)
            n -= k


def _read_tag(s):
    t, n = struct.unpack("<II", s.read(8))
    if t >> 16:  # small data element format
        return t & 0xFFFF, t >> 16, True
    return t, n, False


def read_array(url, var, k=None, verbose=True):
    """Return the variable as an ndarray (MATLAB order). With k, only the first k instances
    along the last axis."""
    s = _Stream(url, var)
    s.read(var["data_offset"])
    dims = var["dims"]
    per_inst = int(np.prod(dims[:-1]))
    n_inst = dims[-1] if k is None else min(k, dims[-1])
    t0 = time.time()

    def part():
        t, nbytes, small = _read_tag(s)
        dt = np.dtype(MI_TYPES[t])
        want = per_inst * n_inst * dt.itemsize
        arr = np.frombuffer(s.read(want), dtype=dt).astype(np.float64)
        rest = nbytes - want
        pad = (-nbytes) % 8 if not small else 4 - nbytes
        if pad < 0:
            pad = 0
        return arr, rest + pad

    re_, rest = part()
    if var["complex"]:
        if verbose:
            print(f"  real part read; skipping {rest / 1e6:.0f} MB (decompressed) to the imaginary part...")
        s.skip(rest)
        im, _ = part()
        data = re_ + 1j * im
    else:
        data = re_
    s.resp.close()
    if verbose:
        print(f"  {s.net_bytes / 1e6:.1f} MB downloaded in {time.time() - t0:.0f} s")
    shape = tuple(dims[:-1]) + (n_inst,)
    return data.reshape(shape, order="F")


def main():
    cmd = sys.argv[1]
    if cmd == "map":
        for fname in SHARES:
            vars_, total = list_vars(file_url(fname))
            print(f"{fname}  ({total / 1e9:.2f} GB)")
            for v in vars_:
                print(f"   {v['name']:<10} dims={v['dims']} complex={v['complex']} "
                      f"compressed={v['compressed_bytes'] / 1e6:.0f} MB")
    elif cmd == "sample":
        fname, vname, k = sys.argv[2], sys.argv[3], int(sys.argv[4])
        url = file_url(fname)
        vars_, _ = list_vars(url)
        byname = {v["name"]: v for v in vars_}
        label_var = next(v for v in vars_ if v["name"].startswith("label"))
        labels = read_array(url, label_var, verbose=False).ravel().astype(int)
        csi = read_array(url, byname[vname], k)
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        out = SAMPLES_DIR / f"{fname[:-4]}__{vname}__{k}.npz"
        np.savez_compressed(out, csi=csi, labels_all=labels, labels=labels[:csi.shape[-1]])
        print(f"  saved {out} csi{csi.shape}")


if __name__ == "__main__":
    main()
