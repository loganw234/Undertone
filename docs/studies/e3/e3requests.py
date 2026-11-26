#!/usr/bin/env python3
"""The requests of stage E3, made from the frozen rule, vectors/e3s/rule.json.

    python docs/studies/e3/e3requests.py            write docs/studies/e3/requests.tsv
    python docs/studies/e3/e3requests.py --check    exit 1 if the file would differ

It makes no request. The list is fetched by study D2's fetch.py, unchanged, one
request after another (the design, section 12):

    python docs/studies/d2/fetch.py docs/studies/e3/requests.tsv <data> docs/studies/e3/manifest.tsv <log> 1440

THE REQUESTS, in this order:
  for each day of the rule, in order, and each station of the rule, in order:
    one dataselect request for the day's HHZ, 00:00:00 to 24:00:00 UTC
    (a day at 100 samples a second is inside the service's largest window,
    which its page gives as (window * rate + 100) <= 400 * 1024 * 1024 / 4);
  then, for each day, one event-service request: SCEDC's catalogue, every
  event type and geographic type, from the rule's before_day_s before the
  day's start to its end, as text.
  The station metadata is NOT asked: study D3's answer is reused, held to its
  SHA-256 (rule.json, stations_file_sha256).

WHAT IT CANNOT SEE
  - Whether the service holds a record for any request.
  - Whether the service's answer for a day changes between two fetches.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RULE = os.path.join(ROOT, "vectors", "e3s", "rule.json")
DATASELECT = "https://service.scedc.caltech.edu/fdsnws/dataselect/1/query"
ISO = "%Y-%m-%dT%H:%M:%S"


def load_rule(path=RULE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def day_start(day):
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def waveform_name(rule, sta, day):
    return "%s.%s.%s.%s.mseed" % (rule["network"], sta, rule["channel"], day)


def events_name(day):
    return "scedc-events-%s.txt" % day


def requests(rule):
    """[(file name, address), ...] in the order they are made."""
    out = []
    for day in rule["days"]:
        t = day_start(day)
        for sta in rule["stations"]:
            out.append((waveform_name(rule, sta, day),
                        "%s?net=%s&sta=%s&loc=%s&cha=%s&start=%s&end=%s&nodata=404"
                        % (DATASELECT, rule["network"], sta, rule["location"], rule["channel"],
                           t.strftime(ISO), (t + timedelta(days=1)).strftime(ISO))))
    ev = rule["events"]
    for day in rule["days"]:
        t = day_start(day)
        out.append((events_name(day),
                    "%s?starttime=%s&endtime=%s&catalog=SCEDC&etype=any&gtype=any&magtype=all"
                    "&format=text&orderby=time&nodata=404"
                    % (ev["service"], (t - timedelta(seconds=ev["before_day_s"])).strftime(ISO),
                       (t + timedelta(days=1)).strftime(ISO))))
    return out


def text(rule):
    lines = ["# The requests of stage E3, in the order they are made, written by e3requests.py",
             "# from vectors/e3s/rule.json. Tab-separated: the file a response is saved under; the address."]
    lines += ["%s\t%s" % row for row in requests(rule)]
    return "\n".join(lines) + "\n"


def main():
    args = sys.argv[1:]
    want = text(load_rule())
    path = os.path.join(HERE, "requests.tsv")
    if args == ["--check"]:
        have = open(path, encoding="utf-8", newline="").read() if os.path.exists(path) else None
        print("%s requests.tsv: %d requests" % ("OK check:" if have == want else "DIFFERS:",
                                                 len(want.strip().split("\n")) - 2))
        return 0 if have == want else 1
    if args:
        raise SystemExit(__doc__)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(want)
    print("wrote requests.tsv: %d requests" % (len(want.strip().split("\n")) - 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
