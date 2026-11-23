#!/usr/bin/env python3
"""The figures of study D1b, drawn from the fetched records.

    <venv>/python docs/studies/d1/figs.py DATA_DIR OUT_DIR

It needs numpy and matplotlib, which live in the virtual environment under
the parcel's scratch folder. It makes no request. It reads the *.mseed files
of DATA_DIR through firstlook.py and mseed.py beside it, and writes two PNG
files into OUT_DIR:

  d1b-ladder.png        for each station of the ladder, the ratio of band
                        power to noise in the 2 to 8 Hz band of the vertical
                        channel against seconds after T0, on the launch day
                        and on both control days, with the two predicted
                        windows shaded. The numbers are firstlook.py's.
  d1b-spectrograms.png  for CI.LOC and CI.MPP, power by frequency and time
                        on the launch day and on the day before, each
                        frequency divided by its own median over the ten
                        minutes that end one minute before T0.

A figure is something to look at. It is not a measurement: every claim of
the study rests on a number that firstlook.py prints.
"""
import math
import os
import sys
from datetime import timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import firstlook as fl  # noqa: E402
import mseed  # noqa: E402

COLOURS = {"2021-09-13": "#4477aa", "2021-09-14": "#000000", "2021-09-15": "#cc6633"}


def ladder(data_dir, out):
    data = fl.load(data_dir)
    stations = [s for s in fl.STATIONS if (s[0], "HHZ", "2021-09-14") in data]
    fig, axes = plt.subplots(len(stations), 1, figsize=(8, 1.45 * len(stations) + 0.8),
                             sharex=True)
    for ax, (sta, d) in zip(axes, stations):
        w = fl.windows(d)
        ax.axvspan(w["ground"][0], w["ground"][1], color="#bbbbbb", alpha=0.35, lw=0)
        ax.axvspan(w["sound"][0], w["sound"][1], color="#88cc88", alpha=0.35, lw=0)
        for day, label, _shift in (fl.DAYS[0], fl.DAYS[2], fl.DAYS[1]):
            got = data.get((sta, "HHZ", day))
            if not got:
                continue
            r = got[0][fl.COUNTING_BAND]
            ks = sorted(r)
            ax.plot(ks, [r[k] for k in ks], color=COLOURS[day], lw=0.7 if day != "2021-09-14" else 0.9,
                    label=label)
        ax.axhline(fl.UP_ABOVE, color="#aa0000", lw=0.5, ls="--")
        ax.set_yscale("log")
        ax.set_ylim(0.1, 20000)
        ax.set_xlim(-700, 1500)
        ax.set_ylabel("CI.%s\n%.1f km" % (sta, d), fontsize=8)
        ax.tick_params(labelsize=7)
    axes[0].legend(fontsize=7, ncol=3, loc="upper right")
    axes[0].set_title("Band power over noise, 2 to 8 Hz, vertical channel. Grey: ground window. "
                      "Green: sound window. Dashed: ratio 3.", fontsize=8)
    axes[-1].set_xlabel("seconds after T0 (2021-09-14 03:55:50 UTC, or the same clock time "
                        "on a control day)", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=80)
    plt.close(fig)


def spectrum_by_time(path, t0):
    first, x = fl.grid(mseed.read(path))
    offset = (t0 - first).total_seconds()
    hann = np.hanning(fl.FRAME)
    ks, rows = [], []
    for k in range(-660, 901):
        centre = int(round((offset + k) * fl.RATE))
        frame = x[centre - fl.FRAME // 2:centre + fl.FRAME // 2]
        if centre - fl.FRAME // 2 < 0 or len(frame) != fl.FRAME or np.isnan(frame).any():
            continue
        spec = np.abs(np.fft.rfft((frame - frame.mean()) * hann)) ** 2
        ks.append(k)
        rows.append(spec[:200].reshape(50, 4).mean(axis=1))    # 1 Hz wide, 0 to 50 Hz
    ks, rows = np.array(ks), np.array(rows)
    quiet = rows[(ks >= fl.NOISE_FROM) & (ks <= fl.NOISE_TO)]
    return ks, 10 * np.log10(rows / np.median(quiet, axis=0))


def spectrograms(data_dir, out):
    fig, axes = plt.subplots(2, 2, figsize=(8, 5), sharex=True, sharey=True)
    for row, sta in enumerate(("LOC", "MPP")):
        d = dict(fl.STATIONS)[sta]
        for col, (day, label, shift) in enumerate((fl.DAYS[1], fl.DAYS[0])):
            path = os.path.join(data_dir, "CI.%s.HHZ.%s.mseed" % (sta, day))
            ks, db = spectrum_by_time(path, fl.T0 + timedelta(days=shift))
            ax = axes[row][col]
            im = ax.pcolormesh(ks, np.arange(0, 50) + 0.5, db.T, vmin=-5, vmax=35,
                               cmap="viridis", shading="nearest", rasterized=True)
            for edge in fl.windows(d)["sound"]:
                ax.axvline(edge, color="white", lw=0.6, ls="--")
            ax.set_title("CI.%s, %.1f km, %s" % (sta, d, label), fontsize=8)
            ax.tick_params(labelsize=7)
            if col == 0:
                ax.set_ylabel("Hz", fontsize=8)
            if row == 1:
                ax.set_xlabel("seconds after T0", fontsize=8)
    bar = fig.colorbar(im, ax=axes, shrink=0.8)
    bar.set_label("power over the pre-launch median, dB", fontsize=8)
    bar.ax.tick_params(labelsize=7)
    fig.suptitle("Vertical channel. Dashed: the sound window's edges.", fontsize=8)
    fig.savefig(out, dpi=80)
    plt.close(fig)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    ladder(data_dir, os.path.join(out_dir, "d1b-ladder.png"))
    spectrograms(data_dir, os.path.join(out_dir, "d1b-spectrograms.png"))
    for name in ("d1b-ladder.png", "d1b-spectrograms.png"):
        print("%s: %d bytes" % (name, os.path.getsize(os.path.join(out_dir, name))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
