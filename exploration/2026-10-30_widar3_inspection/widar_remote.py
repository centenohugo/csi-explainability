"""Partial access to the Widar3.0 zips hosted on the Tsinghua cloud, without downloading them in full.

The public share (linked from the Widar3.0 homepage) needs no login, and its file server supports
HTTP Range requests. A zip keeps its index (central directory) at the end, so `zipfile` can list
the entries and extract single .dat files reading only those bytes.

Usage:
  python widar_remote.py ls                          # folders and zips in the share
  python widar_remote.py list <zip path>             # entries of one zip, e.g. /CSI/20181128.zip
  python widar_remote.py get <zip path> <pattern>    # extract entries containing <pattern>
                                                     # into data/samples/widar3/
"""
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import quote

SHARE = "2760bb9557ca4d09a74d"
BASE = "https://cloud.tsinghua.edu.cn"
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples" / "widar3"


def list_dir(path):
    url = f"{BASE}/api/v2.1/share-links/{SHARE}/dirents/?path={path}"
    return json.load(urllib.request.urlopen(url))["dirent_list"]


def file_url(path):
    """The share link redirects to a temporary direct URL on the file server."""
    req = urllib.request.Request(f"{BASE}/d/{SHARE}/files/?p={quote(path)}&dl=1", method="HEAD")
    return urllib.request.urlopen(req).url


class HttpFile(io.RawIOBase):
    """Read-only, seekable file over HTTP Range requests (enough for zipfile)."""

    def __init__(self, url):
        self.url, self.pos, self.net_bytes = url, 0, 0
        req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req) as r:
            self.size = int(r.headers["Content-Range"].split("/")[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        end = min(self.pos + len(b), self.size)
        if end <= self.pos:
            return 0
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end - 1}"})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        b[:len(data)] = data
        self.pos += len(data)
        self.net_bytes += len(data)
        return len(data)


def open_zip(path):
    f = HttpFile(file_url(path))
    # buffered reads so zipfile does not issue one request per tiny read
    return zipfile.ZipFile(io.BufferedReader(f, buffer_size=1 << 20)), f


def main():
    cmd = sys.argv[1]
    if cmd == "ls":
        for top in ("/", "/CSI/", "/BVP/"):
            for d in list_dir(top):
                p = d.get("file_path") or d.get("folder_path")
                print(f"{p:<45} {d['size'] / 1e9:6.2f} GB")
    elif cmd == "list":
        z, f = open_zip(sys.argv[2])
        infos = [i for i in z.infolist() if not i.is_dir()]
        for i in infos:
            print(f"{i.filename:<50} {i.file_size / 1e6:7.2f} MB")
        print(f"{len(infos)} files, {sum(i.file_size for i in infos) / 1e9:.2f} GB uncompressed "
              f"({f.net_bytes / 1e6:.1f} MB downloaded to read the index)")
    elif cmd == "get":
        z, f = open_zip(sys.argv[2])
        pattern = sys.argv[3]
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        for i in z.infolist():
            if pattern in i.filename and not i.is_dir():
                out = SAMPLES_DIR / Path(i.filename).name
                out.write_bytes(z.read(i))
                print(f"  {out.name} ({i.file_size / 1e6:.2f} MB)")
        print(f"  {f.net_bytes / 1e6:.1f} MB downloaded")


if __name__ == "__main__":
    main()
