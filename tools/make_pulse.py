#!/usr/bin/env python3
"""How spec/pulses/e0.toml was made. Provenance, not a gate.

    python tools/make_pulse.py            prints the file's text
    python tools/make_pulse.py --write    writes spec/pulses/e0.toml

The pulse is 64 samples of a sine, 4 cycles long, under a Hann window, with a
peak near 1000, rounded half to even. The committed file is the fact. This
script uses floating point, whose last digit can differ between machines, so
no stage reruns it: a difference would say something about the machine, not
about the project.
"""
import math
import os
import sys

N, CYCLES, PEAK = 64, 4, 1000


def samples():
    out = []
    for i in range(N):
        window = 0.5 - 0.5 * math.cos(2 * math.pi * i / (N - 1))
        out.append(round(PEAK * window * math.sin(2 * math.pi * CYCLES * i / N)))
    return out


def text():
    s = samples()
    rows = [", ".join("%5d" % v for v in s[i:i + 8]) for i in range(0, N, 8)]
    return ("# The reference pulse of stage E0, as integers. Made by tools/make_pulse.py:\n"
            "# %d samples of a %d-cycle sine under a Hann window, peak near %d.\n"
            "# This file is the fact. Nothing regenerates it.\n"
            "name = \"e0\"\n"
            "samples = [\n    " + ",\n    ".join(rows) + ",\n]\n") % (N, CYCLES, PEAK)


if __name__ == "__main__":
    if "--write" in sys.argv:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "spec", "pulses", "e0.toml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text())
        print("wrote", path)
    else:
        sys.stdout.buffer.write(text().encode("utf-8"))  # bytes: no CR is added on Windows
