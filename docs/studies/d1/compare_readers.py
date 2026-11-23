#!/usr/bin/env python3
"""Holds this study's own miniSEED reader against a second, foreign one.

    <venv>/python docs/studies/d1/compare_readers.py DATA_DIR

It needs the package obspy, which lives in the virtual environment under the
parcel's scratch folder and nowhere else. For every *.mseed file of DATA_DIR
it reads the samples twice, with mseed.py beside this file and with obspy,
and compares: the number of samples, every sample, the first sample's time,
and the sample rate. It prints one line a file and one OK line, or a
FINDING line for each difference and exits 1.

It also runs a control: it changes one sample of mseed.py's reading in
memory and checks that the comparison then reports a difference.

WHAT IT CANNOT SEE
  An error both readers share. They were written by different people from
  the same format description, so a misreading of the format that both make
  would pass here.
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mseed  # noqa: E402


def differences(mine, theirs):
    """A list of strings, empty when the two readings agree."""
    out = []
    mine_x = [x for r in mine for x in r["samples"]]
    if len(theirs) != 1:
        out.append("obspy sees %d traces, not one unbroken trace" % len(theirs))
        return out
    tr = theirs[0]
    their_x = tr.data.tolist()
    if len(mine_x) != len(their_x):
        out.append("sample counts differ: %d against %d" % (len(mine_x), len(their_x)))
        return out
    bad = [i for i, (a, b) in enumerate(zip(mine_x, their_x)) if a != b]
    if bad:
        out.append("%d samples differ, the first at index %d" % (len(bad), bad[0]))
    if abs(mine[0]["start"].timestamp() - tr.stats.starttime.timestamp) > 1e-6:
        out.append("first sample times differ: %s against %s"
                   % (mine[0]["start"].isoformat(), tr.stats.starttime))
    if mine[0]["rate"] != tr.stats.sampling_rate:
        out.append("sample rates differ")
    return out


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    import obspy
    files = sorted(glob.glob(os.path.join(sys.argv[1], "*.mseed")))
    if not files:
        print("REFUSED compare: NOTHING-SELECTED")
        return 2
    findings = total = 0
    for i, path in enumerate(files):
        mine = mseed.read(path)
        theirs = obspy.read(path)
        diffs = differences(mine, theirs)
        n = sum(r["nsamp"] for r in mine)
        total += n
        name = os.path.basename(path)
        for d in diffs:
            findings += 1
            print("FINDING compare %s: %s" % (name, d))
        if not diffs:
            print("same  %-34s %d samples" % (name, n))
        if i == 0:
            mine[0]["samples"][len(mine[0]["samples"]) // 2] += 1
            if not differences(mine, theirs):
                print("FINDING compare: the control did not fail: a changed sample was not seen")
                findings += 1
            else:
                print("control: one changed sample in %s was reported, as it must be" % name)
    if findings:
        print("FAIL compare: %d finding(s)" % findings)
        return 1
    print("OK compare: %d files, %d samples, the two readers agree on every one (obspy %s)"
          % (len(files), total, obspy.__version__))
    return 0


if __name__ == "__main__":
    sys.exit(main())
