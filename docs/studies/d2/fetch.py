#!/usr/bin/env python3
"""Fetch the requests of study D2, ONE AFTER ANOTHER, never two at once.

    python docs/studies/d2/fetch.py LIST DATA_DIR MANIFEST LOG [MAX_SECONDS]

  LIST      "name TAB address" a line (requests.tsv, written by launches.py)
  DATA_DIR  where the files go; outside the repository; none is committed
  MANIFEST  tab-separated, appended to, one line a request: name, address,
            time fetched (UTC), HTTP status, bytes, SHA-256
  LOG       the parcel's request log, appended to, one line a request

It can resume. A name is not asked again when its last manifest line is 404,
or is 200 and the file in DATA_DIR has that line's SHA-256. Any other name is
asked. It stops by itself when two requests in a row are answered with
anything but 200 or 404, and at MAX_SECONDS if that is given.

It sends no personal detail: curl's default headers and nothing else. It uses
the Windows curl, because Git Bash's fails on some hosts of this desktop
(CLAUDE.md, trap 8). It waits 0.3 s between requests.

IT DECODES NOTHING. A file is bytes, a length and a hash. Whether a record
has a gap, or holds what was asked for, is not known until a reader opens it.

WHAT IT CANNOT SEE
  - Whether a file holds what was asked for.
  - A file changed after it was fetched, until a later run finds its hash wrong.
"""
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

CURL = r"C:\Windows\System32\curl.exe"
PAUSE = 0.3
HEAD = "# file\trequest\tfetched (UTC)\tHTTP status\tbytes\tSHA-256\n"


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def read_manifest(path):
    """{name: (status, bytes, sha256)}, the last line of each name."""
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        out[f[0]] = (f[3], int(f[4]), f[5])
    return out


def read_list(path):
    out = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        name, url = line.rstrip("\n").split("\t")[:2]
        out.append((name, url))
    return out


def have(name, row, data_dir):
    """True when this name need not be asked again."""
    if row is None:
        return False
    if row[0] == "404":
        return True
    path = os.path.join(data_dir, name)
    return row[0] == "200" and os.path.isfile(path) and sha256(path) == row[2]


def main():
    if len(sys.argv) not in (5, 6):
        raise SystemExit(__doc__)
    list_path, data_dir, manifest, log = sys.argv[1:5]
    limit = float(sys.argv[5]) if len(sys.argv) == 6 else None
    os.makedirs(data_dir, exist_ok=True)
    if not os.path.exists(manifest) or os.path.getsize(manifest) == 0:
        with open(manifest, "w", encoding="utf-8", newline="\n") as f:
            f.write(HEAD)
    done = read_manifest(manifest)
    todo = [(n, u) for n, u in read_list(list_path) if not have(n, done.get(n), data_dir)]
    print("%d requests in the list, %d to make" % (len(read_list(list_path)), len(todo)), flush=True)
    began, bad, made = time.time(), 0, 0
    for name, url in todo:
        if limit is not None and time.time() - began > limit:
            print("STOPPED at the time limit: %d made, %d left" % (made, len(todo) - made),
                  flush=True)
            return 3
        out = os.path.join(data_dir, name)
        part = out + ".part"
        when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        got = subprocess.run([CURL, "-sS", "-L", "--compressed", "--max-time", "120", "-o", part,
                              "-w", "%{http_code}", url], capture_output=True, text=True)
        status = got.stdout.strip() or "000"
        if status == "200" and os.path.isfile(part) and os.path.getsize(part) > 0:
            os.replace(part, out)
            size, digest = os.path.getsize(out), sha256(out)
        else:
            if os.path.exists(part):
                os.remove(part)
            size, digest = 0, "-"
        with open(manifest, "a", encoding="utf-8", newline="\n") as f:
            f.write("%s\t%s\t%s\t%s\t%d\t%s\n" % (name, url, when, status, size, digest))
        with open(log, "a", encoding="utf-8", newline="\n") as f:
            f.write("%s\t%s\t%s\t%d\t%s\tfetch.py\n" % (when, url, status, size, digest))
        made += 1
        if made % 25 == 0:
            print("%d made, the last: %s HTTP %s %d bytes" % (made, name, status, size), flush=True)
        bad = 0 if status in ("200", "404") else bad + 1
        if bad >= 2:
            print("STOPPED: two requests in a row were answered with neither 200 nor 404, the "
                  "last HTTP %s (%s)" % (status, got.stderr.strip()[:200]), flush=True)
            return 4
        time.sleep(PAUSE)
    print("DONE: %d made, none left" % made, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
