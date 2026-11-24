#!/usr/bin/env python3
"""Score study D3's scored launches, once, by the frozen rule.

    python docs/studies/d3/d3score.py --freeze-hash
        print each frozen file's SHA-256 and the freeze hash. Opens no record.
    python docs/studies/d3/d3score.py DATA_DIR --freeze HEX
        THE scoring run. Writes scored-output.txt beside this file and prints it.
    python docs/studies/d3/d3score.py DATA_DIR --freeze HEX --rehearse
        the same code on the constant-setting launches, to see that every line
        runs. It is not a result: those launches set the constant they are
        then scored by. It writes nothing.

It makes no request. It is study D2's score.py with this study's files, names
and stations.

THE THREE WALLS IT HOLDS
  frozen    it refuses, NOT-FROZEN, unless HEX is the freeze hash of the files
            in FROZEN as they are on disk now: the rule, this script, the
            constants, the launches and their split, the fetch's manifest and
            the two files of D1 the measure is made of. The ledger carries HEX.
  the split it scores the launches launches.tsv puts on the scored side. A
            launch of the constant-setting side is refused by name,
            SCORED-A-CONSTANT-SETTING-LAUNCH, before any record is opened.
  once      it refuses, ALREADY-SCORED, when scored-output.txt exists. And it
            refuses, FETCH-NOT-COMPLETE, unless the manifest settles every
            record of every scored launch: it does not score part of the set.

THE TEST (the design of 2026-11-24, approved at 09:29)
  At each station on its own: a hits among n_L usable scored launch windows
  against b hits among n_C usable scored control windows; Fisher's exact test,
  one-sided; rejected at 0.0025, which is 0.01 shared over four stations.
  The two controls on the same records, each against the same control windows
  at 0.01 undivided: the wrong window, and the catalogue an hour early.

WHAT IT CANNOT SEE
  - What made a hit. A hit is seconds of power in a band.
  - A firing the catalogue does not list, or an earthquake, in any window.
  - Whether the catalogue's times are right.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import d3rule as rule  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FROZEN = ["docs/studies/d3/d3rule.py", "docs/studies/d3/d3score.py", "docs/studies/d3/constants.json",
          "docs/studies/d3/launches.tsv", "docs/studies/d3/manifest.tsv",
          "docs/studies/d1/firstlook.py", "docs/studies/d1/mseed.py"]
FAMILY_LEVEL = 0.01
LEVEL = FAMILY_LEVEL / len(rule.STATIONS)
CONTROL_LEVEL = 0.01
ENOUGH = 15
OUTPUT_NAME = "scored-output.txt"
OUTPUT = os.path.join(HERE, OUTPUT_NAME)


def freeze_lines(root=ROOT, files=FROZEN):
    """(the lines "sha256  path", the freeze hash: the SHA-256 of those lines)."""
    lines = []
    for rel in files:
        with open(os.path.join(root, rel), "rb") as f:
            lines.append("%s  %s" % (hashlib.sha256(f.read()).hexdigest(), rel))
    return lines, hashlib.sha256(("\n".join(lines) + "\n").encode("ascii")).hexdigest()


def summarise(rows, constants, side_label):
    """The lines of the output, from collect()'s rows and the constants."""
    m_of = constants["M"]
    out = []
    lines, verdicts, enough = [], {}, {}
    table = []
    for station, km in rule.STATIONS:
        m = m_of[station]

        def count(kind):
            s = [r[4] for r in rows if r[1] == station and r[2] == kind and r[4] is not None]
            gone = sum(1 for r in rows if r[1] == station and r[2] == kind and r[4] is None)
            return len(s), sum(1 for v in s if v >= m), gone

        n_l, a, gone_l = count("launch")
        n_c, b, gone_c = count("control")
        enough[station] = n_l if n_c else 0
        n_w, a_w, _g = count("wrong")
        n_h, a_h, _g = count("shifted")
        if n_l == 0 or n_c == 0:
            verdicts[station] = "NOT RUN: NO RECORD"
            table.append("| CI.%s | %.1f | %d | %d of %d | %d of %d | - | - | %d, %d | NOT RUN: "
                         "NO RECORD |" % (station, km, m, a, n_l, b, n_c, gone_l, gone_c))
            lines.append("| CI.%s | - | - | - | - | not run |" % station)
            continue
        p = rule.p_fisher(a, b, n_l, n_c)
        need = rule.needed(b, n_l, n_c, LEVEL)
        p_w = rule.p_fisher(a_w, b, n_w, n_c) if n_w else None
        p_h = rule.p_fisher(a_h, b, n_h, n_c) if n_h else None
        reject = p <= LEVEL
        w_rej = p_w is not None and p_w <= CONTROL_LEVEL
        h_rej = p_h is not None and p_h <= CONTROL_LEVEL
        if reject and (w_rej or h_rej):
            v = "VOID: THE RULE SEES SOMETHING THAT IS NOT THE LAUNCH"
        elif reject:
            v = "SEEN MORE OFTEN THAN A CONTROL WINDOW"
        elif n_l >= ENOUGH:
            v = "NOT SHOWN"
        else:
            v = "CANNOT TELL: TOO FEW RECORDS"
        verdicts[station] = v
        table.append("| CI.%s | %.1f | %d | %d of %d | %d of %d | %.3g | %s | %d, %d | %s |" % (
            station, km, m, a, n_l, b, n_c, p, "none can" if need is None else str(need),
            gone_l, gone_c, v))
        lines.append("| CI.%s | %d of %d | %s | %d of %d | %s | %s |" % (
            station, a_w, n_w, "-" if p_w is None else "%.3g" % p_w,
            a_h, n_h, "-" if p_h is None else "%.3g" % p_h,
            "; ".join(x for x in ("the wrong window REJECTS" if w_rej else "",
                                  "the shifted catalogue REJECTS" if h_rej else "") if x)
            or "neither rejects"))
    out.append("**The test, %s.** Fisher's exact test, one-sided, at %.4f a station (%.2f over "
               "%d stations)." % (side_label, LEVEL, FAMILY_LEVEL, len(rule.STATIONS)))
    out.append("")
    out.append("| station | km | M | launch windows that hit | control windows that hit | p "
               "| launch hits needed to reject | no record: launch, control | reading |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    out += table
    out.append("")
    out.append("**The two controls on the same records.** Each against the same control "
               "windows, at %.2f undivided. Neither may reject." % CONTROL_LEVEL)
    out.append("")
    out.append("| station | wrong windows that hit | p | windows an hour early that hit | p "
               "| reading |")
    out.append("|---|---|---|---|---|---|")
    out += lines
    out.append("")
    seen = [s for s, _k in rule.STATIONS if verdicts[s].startswith("SEEN")]
    void = [s for s, _k in rule.STATIONS if verdicts[s].startswith("VOID")]
    if seen:
        head = "YES: seen more often than a control window at %s" % ", ".join(
            "CI." + s for s in seen)
    elif any(n >= ENOUGH for n in enough.values()):
        head = "NO: NOT SHOWN at any station"
    else:
        head = "CANNOT TELL: too few records at every station"
    if void:
        head += "; VOID at %s" % ", ".join("CI." + s for s in void)
    out.append("**HEADLINE, %s: %s.**" % (side_label, head))
    return out


def window_lines(rows, constants):
    out = ["| launch | station | window | days from T0 | S | M | hit | no record because |",
           "|---|---|---|---|---|---|---|---|"]
    for tag, station, kind, days, s, why in rows:
        m = constants["M"][station]
        out.append("| %s | CI.%s | %s | %s | %s | %d | %s | %s |" % (
            tag, station, kind, "%+d" % days if kind == "control" else "0",
            "-" if s is None else s, m, "-" if s is None else ("yes" if s >= m else "no"),
            why or ""))
    return out


def main():
    args = sys.argv[1:]
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    lines, freeze = freeze_lines()
    if args == ["--freeze-hash"]:
        print("\n".join(lines))
        print("freeze hash: %s" % freeze)
        return 0
    rehearse = "--rehearse" in args
    args = [a for a in args if a != "--rehearse"]
    if len(args) != 3 or args[1] != "--freeze":
        raise SystemExit(__doc__)
    data_dir, given = args[0], args[2]
    if given != freeze:
        raise SystemExit("REFUSED NOT-FROZEN: the files hash to %s, not to %s" % (freeze, given))
    if not rehearse and os.path.exists(OUTPUT):
        raise SystemExit("REFUSED ALREADY-SCORED: %s exists" % OUTPUT)
    launches = rule.read_launches(os.path.join(HERE, "launches.tsv"))
    manifest = rule.read_manifest(os.path.join(HERE, "manifest.tsv"))
    with open(os.path.join(HERE, "constants.json"), encoding="utf-8") as f:
        constants = json.load(f)
    side = rule.SETS if rehearse else rule.SCORED
    tags = [row["tag"] for row in launches if row["side"] == side]
    missing = rule.not_fetched(launches, tags, manifest, data_dir)
    if missing:
        raise SystemExit("REFUSED FETCH-NOT-COMPLETE: %d records are not settled by the "
                         "manifest, the first %s" % (len(missing), missing[0]))
    try:
        rows = rule.collect(launches, tags, side, rule.make_loader(data_dir, manifest))
    except rule.Refusal as e:
        raise SystemExit("REFUSED %s" % e)
    label = ("REHEARSAL on the constant-setting launches, NOT A RESULT" if rehearse
             else "the scored launches")
    out = ["Study D3, %s." % ("a rehearsal" if rehearse else "the scoring run"),
           "Freeze hash %s." % freeze,
           "%d launches: %s." % (len(tags), ", ".join(tags)),
           "The constants M were set from: %s." % ", ".join(constants["launches"]), ""]
    out += summarise(rows, constants, label)
    out += ["", "**Every window.**", ""]
    out += window_lines(rows, constants)
    text = "\n".join(out) + "\n"
    if not rehearse:
        with open(OUTPUT, "x", encoding="utf-8", newline="\n") as f:
            f.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
