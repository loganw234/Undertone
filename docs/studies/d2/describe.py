#!/usr/bin/env python3
"""The figures study D2's document states, from the committed files alone.

    python docs/studies/d2/describe.py

It makes no request and opens no record. It reads, beside itself:
manifest.tsv (the fetch), constants.json, launches.tsv, and scored-output.txt
(the one scoring run's output, as printed). Every line it prints is labelled
D1, D2, ... so the document's register can point at it.

Lines marked AFTER LOOKING describe the scored output. They were not fixed
before the scoring run, they are not tests, and they change no headline.

WHAT IT CANNOT SEE
  - Whether the output is what the records hold. It reads the output.
  - Anything the scoring run did not print.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rule  # noqa: E402
import score  # noqa: E402

STATIONS = [s for s, _km in rule.STATIONS]


def manifest_rows():
    out = []
    for line in open(os.path.join(HERE, "manifest.tsv"), encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        out.append(line.rstrip("\n").split("\t"))
    return out


def window_rows():
    out = []
    for line in open(os.path.join(HERE, "scored-output.txt"), encoding="utf-8"):
        f = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(f) == 8 and f[0][:2] == "20" and f[1].startswith("CI."):
            out.append({"tag": f[0], "station": f[1][3:], "kind": f[2], "days": f[3],
                        "s": None if f[4] == "-" else int(f[4]), "m": int(f[5]),
                        "hit": f[6], "why": f[7]})
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    man = manifest_rows()
    wave = [r for r in man if r[0].endswith(".mseed")]
    print("D1  the fetch: %d requests, from %s to %s; %d answered 200, %d answered 404, %d other"
          % (len(man), man[0][2], man[-1][2], sum(1 for r in man if r[3] == "200"),
             sum(1 for r in man if r[3] == "404"),
             sum(1 for r in man if r[3] not in ("200", "404"))))
    print("D2  waveform requests: %d; files that came: %d, %d bytes; launch records %d, %d bytes; "
          "control records %d, %d bytes"
          % (len(wave), sum(1 for r in wave if r[3] == "200"), sum(int(r[4]) for r in wave),
             sum(1 for r in wave if r[3] == "200" and ".launch." in r[0]),
             sum(int(r[4]) for r in wave if ".launch." in r[0]),
             sum(1 for r in wave if r[3] == "200" and ".launch." not in r[0]),
             sum(int(r[4]) for r in wave if ".launch." not in r[0])))
    for sta in STATIONS:
        mine = [r for r in wave if r[0].startswith("CI.%s." % sta)]
        ok = [r for r in mine if r[3] == "200"]
        print("D3  CI.%s: %d requests, %d answered 200, %d answered 404" % (
            sta, len(mine), len(ok), sum(1 for r in mine if r[3] == "404")))
    gatr = [r for r in wave if r[0].startswith("CI.GATR.")]

    def start(r):
        return r[1].split("start=")[1].split("&")[0]
    print("D4  CI.GATR: the latest window answered 404 starts %s; the earliest answered 200 "
          "starts %s" % (max(start(r) for r in gatr if r[3] == "404"),
                         min(start(r) for r in gatr if r[3] == "200")))
    print("D5  CI.GATR launch records that came: %s" % ", ".join(
        r[0].split(".")[3] for r in gatr if r[3] == "200" and ".launch." in r[0]))

    with open(os.path.join(HERE, "constants.json"), encoding="utf-8") as f:
        con = json.load(f)
    for sta in STATIONS:
        a, b = con["S_launch"][sta], con["S_control"][sta]
        print("D7  constants, CI.%s: M = %d, set from records: %s; %d launch windows, S %s; "
              "%d control windows, largest S %s"
              % (sta, con["M"][sta], "yes" if con["set_from_records"][sta] else "no", len(a),
                 "%d to %d" % (min(a), max(a)) if a else "none", len(b), max(b) if b else "none"))
    print("D8  constants set from %d launches: %s" % (len(con["launches"]),
                                                     ", ".join(con["launches"])))

    rows = window_rows()
    print("D9  the scoring run's table of every window: %d rows" % len(rows))
    total_other = hits_other = 0
    for sta in STATIONS:
        m = con["M"][sta]

        def vals(kind):
            return [r["s"] for r in rows if r["station"] == sta and r["kind"] == kind
                    and r["s"] is not None]

        def gone(kind):
            return [r for r in rows if r["station"] == sta and r["kind"] == kind
                    and r["s"] is None]
        la, co, wr, sh = vals("launch"), vals("control"), vals("wrong"), vals("shifted")
        a, b = sum(1 for v in la if v >= m), sum(1 for v in co if v >= m)
        print("D10 CI.%s: %d of %d launch windows hit, %d of %d control windows hit; no record: "
              "%d launch, %d control; p = %.3g; needed to reject at %.4f: %s"
              % (sta, a, len(la), b, len(co), len(gone("launch")), len(gone("control")),
                 rule.p_fisher(a, b, len(la), len(co)), score.LEVEL,
                 rule.needed(b, len(la), len(co), score.LEVEL)))
        aw, ah = sum(1 for v in wr if v >= m), sum(1 for v in sh if v >= m)
        print("D11 CI.%s: %d of %d wrong windows hit, p = %.3g; %d of %d windows an hour early "
              "hit, p = %.3g" % (sta, aw, len(wr), rule.p_fisher(aw, b, len(wr), len(co)),
                                 ah, len(sh), rule.p_fisher(ah, b, len(sh), len(co))))
        total_other += len(wr) + len(sh)
        hits_other += aw + ah
        why = sorted(set(r["why"] for kind in ("launch", "control", "wrong", "shifted")
                         for r in gone(kind)))
        print("D12 CI.%s: every window with no record is so because: %s" % (
            sta, "; ".join(why) or "(none has no record)"))
        print("D13 AFTER LOOKING, CI.%s: launch windows' S %d to %d of %d seconds; the largest S "
              "of a control window %d, of a wrong window %d, of a window an hour early %d"
              % (sta, min(la), max(la), rule.window(sta)[1] - rule.window(sta)[0], max(co),
                 max(wr), max(sh)))
        miss = [(r["tag"], r["s"]) for r in rows if r["station"] == sta and r["kind"] == "launch"
                and r["hit"] == "no"]
        print("D14 AFTER LOOKING, CI.%s: launch windows that did not hit: %s" % (
            sta, ", ".join("%s (S = %d)" % t for t in miss) or "none"))
        if miss:
            did = [v for v in la if v >= m]
            print("D14 AFTER LOOKING, CI.%s: its %d launch windows that hit have S %d to %d"
                  % (sta, len(did), min(did), max(did)))
            for tag, _s in miss:
                print("D14 AFTER LOOKING, launch %s at the other stations: %s" % (
                    tag, "; ".join("CI.%s S = %s, hit: %s" % (
                        r["station"], "-" if r["s"] is None else r["s"], r["hit"])
                        for r in rows if r["tag"] == tag and r["kind"] == "launch"
                        and r["station"] != sta)))
        lo_m, hi_m = max(co + wr + sh) + 1, min(la)
        every = max(co + wr + sh) < min(la)
        print("D15 AFTER LOOKING, CI.%s: %s" % (
            sta, "any M from %d to %d would part every launch window from every other window"
            % (lo_m, hi_m) if every else
            "no M parts every launch window from every other window: the smallest launch S is "
            "%d and the largest other S is %d" % (min(la), max(co + wr + sh))))
    odd = [r for r in rows if r["kind"] != "launch" and r["hit"] == "yes"]
    print("D16 windows that are not launch windows and hit: %d of %d control, wrong and "
          "hour-early windows with a record: %s"
          % (len(odd), sum(1 for r in rows if r["kind"] != "launch" and r["s"] is not None),
             "; ".join("%s CI.%s %s, S = %d" % (r["tag"], r["station"], r["kind"], r["s"])
                       for r in odd) or "none"))
    print("D17 wrong and hour-early windows with a record: %d, of which %d hit"
          % (total_other, hits_other))
    for b in range(0, 4):
        print("D18 CI.GATR's test, 7 launch and 21 control windows, %d control hit(s): launch "
              "hits needed at %.4f: %s; at 0.01 / 3: %s"
              % (b, score.LEVEL, rule.needed(b, 7, 21, score.LEVEL),
                 rule.needed(b, 7, 21, 0.01 / 3)))
    for b in range(0, 4):
        print("D19 a station with 23 launch and 68 control windows, %d control hit(s): launch "
              "hits needed at %.4f: %s; at 0.01 / 3: %s"
              % (b, score.LEVEL, rule.needed(b, 23, 68, score.LEVEL),
                 rule.needed(b, 23, 68, 0.01 / 3)))
    launches = rule.read_launches(os.path.join(HERE, "launches.tsv"))
    print("D20 launches.tsv: %d on the constant-setting side (one of them, 2021-082, with no "
          "record), %d scored; control times: %d and %d"
          % (sum(1 for r in launches if r["side"] == rule.SETS),
             sum(1 for r in launches if r["side"] == rule.SCORED),
             sum(len(r["controls"]) for r in launches if r["side"] == rule.SETS),
             sum(len(r["controls"]) for r in launches if r["side"] == rule.SCORED)))
    # What the experiment could show, as the design computed it before any
    # record of 2024 was fetched: the chance one station's test rejects.
    def binom(n, p):
        return [math.comb(n, x) * p ** x * (1 - p) ** (n - x) for x in range(n + 1)]

    for n_l, n_c in ((23, 69), (15, 45), (10, 30)):
        rej = [[rule.p_fisher(a, b, n_l, n_c) <= score.LEVEL for b in range(n_c + 1)]
               for a in range(n_l + 1)]
        for p_l in (0.95, 0.8, 0.5, 0.3, 0.2):
            cells = []
            for p_c in (0.0, 0.05, 0.125, 0.25):
                pa, pb = binom(n_l, p_l), binom(n_c, p_c)
                cells.append("%.3f" % sum(pa[a] * pb[b] for a in range(n_l + 1)
                                          for b in range(n_c + 1) if rej[a][b]))
            print("D22 power, %d launch and %d control windows, a launch window hits with "
                  "chance %.2f; a control window with 0, 0.05, 0.125, 0.25: %s"
                  % (n_l, n_c, p_l, ", ".join(cells)))
        sizes = []
        for p in (0.05, 0.125, 0.25, 0.5):
            pa, pb = binom(n_l, p), binom(n_c, p)
            sizes.append("%.5f" % sum(pa[a] * pb[b] for a in range(n_l + 1)
                                      for b in range(n_c + 1) if rej[a][b]))
        print("D23 no effect, %d and %d windows, both chances 0.05, 0.125, 0.25, 0.5: a "
              "station's test rejects with chance %s" % (n_l, n_c, ", ".join(sizes)))
    print("D24 the smallest launch-hit count that rejects at %.4f with 23 and 69 windows, for "
          "0 to 10 control hits: %s" % (score.LEVEL, ", ".join(
              str(rule.needed(b, 23, 69, score.LEVEL)) for b in range(11))))
    _lines, freeze = score.freeze_lines()
    first = open(os.path.join(HERE, "scored-output.txt"), encoding="utf-8").read().split("\n")[1]
    print("D21 the freeze hash of the files as they are now: %s; the scoring run's own line: %s"
          % (freeze, first))
    return 0


if __name__ == "__main__":
    sys.exit(main())
