#!/usr/bin/env python3
"""Station tables for study D1. Standard library only. It makes no request.

    python docs/studies/d1/stations.py --self-test
    python docs/studies/d1/stations.py --responses DIR
    python docs/studies/d1/stations.py --responses DIR --unhold es
    python docs/studies/d1/stations.py --responses DIR --as-of 2021-09-14

WHAT IT READS
  sites.tsv, beside this file: the launch sites and their coordinates.
  queries.tsv, beside this file: one line per station-service request that
      was made: the file its response was saved under, the site, the date
      the request asked about, whether the response is "used" or "held",
      and the URL. Only requests about the --as-of date are read (default
      2026-11-23, the day of the study). A held response is
      never opened, unless --unhold names its file-name prefix. Since the
      owner allowed EarthScope on 2026-11-23 its responses are marked "used"
      and --unhold has nothing left to unhold: the only held responses are
      Raspberry Shake's, whose prefix it refuses, and whose network, AM,
      stays out by name either way.
  DIR: the folder holding the saved responses. They are the "text" format
      of an FDSN station service at level=channel, one channel epoch per
      line, fields separated by "|":
          Network|Station|Location|Channel|Latitude|Longitude|Elevation|
          Depth|Azimuth|Dip|SensorDescription|Scale|ScaleFreq|ScaleUnits|
          SampleRate|StartTime|EndTime
      The responses are not committed (the round's rule). Re-making the
      "used" requests in queries.tsv reproduces them, as far as the services
      still answer the same.

WHAT IT WRITES
  Markdown on standard output, per site: the stations nearer than --near-km
  (and never fewer than --at-least of the nearest), a count by distance band, the stations with a pressure channel, a ladder
  of stations of one network at growing distances, and the predicted arrival
  windows for that ladder. Every number is computed here from the inputs
  above and the parameters below.

WHAT IT CANNOT SEE
  - Whether a waveform exists for any channel at any time. A channel epoch
    in station metadata says the channel is described, not that the data
    centre holds its data.
  - Whether a coordinate is exact. It uses what the service returned.
  - A station that no "used" response lists.
  - What a channel measures, beyond its three-letter code.

DISTANCE
  The geodesic on the WGS-84 ellipsoid by Vincenty's inverse formula. The
  self-test checks it against two cases that can be worked by hand (a
  quarter of the equator, and one degree of longitude on the equator),
  checks that it is symmetric and agrees with the spherical haversine
  distance within 0.6 percent (the two differ by the Earth's flattening),
  and checks that a call with latitude and longitude swapped is caught.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# WGS-84
A_M = 6378137.0
F = 1 / 298.257223563
B_M = A_M * (1 - F)

# Window parameters. Each is a stated assumption of the study (its section
# 5), not a measurement. Speeds in km/s, times in seconds.
C_AIR_FAST = 0.345      # fastest sound path considered
C_AIR_SLOW = 0.240      # slowest: below the slowest phase in the study's row A5
V_GROUND_FAST = 6.5     # fastest path through the ground considered
V_GROUND_SLOW = 1.5     # slowest surface wave considered
SOURCE_SECONDS = 180.0  # how long the source is assumed to radiate
TIME_MARGIN = 5.0       # catalogue time against first motion, either side

# Networks left out by code, with the reason.
EXCLUDED = {
    "SY": "synthetic seismograms, not instruments",
    "AM": "held: its service says use accepts a licence, which is the owner's to accept",
}

# file-name prefix -> the service that answered
CENTRES = {"es": "EarthScope", "scedc": "SCEDC", "ncedc": "NCEDC"}

AS_OF = "2026-11-23"    # default: a channel epoch must be open on this date

BANDS = [(0, 10), (10, 25), (25, 50), (50, 100), (100, 200), (200, 350)]

# The ladder: stations of this network with these three channels. The first
# rung is the station nearest the site; each next rung is the nearest
# station at least LADDER_FACTOR times farther than the rung before it.
LADDER_NET = "CI"
LADDER_CHANNELS = ("HHE", "HHN", "HHZ")
LADDER_FACTOR = 1.5
LADDER_MAX_KM = 350


def vincenty_km(lat1, lon1, lat2, lon2):
    """Geodesic distance in km on WGS-84. Refuses a pair that does not converge."""
    if lat1 == lat2 and lon1 == lon2:
        return 0.0
    u1 = math.atan((1 - F) * math.tan(math.radians(lat1)))
    u2 = math.atan((1 - F) * math.tan(math.radians(lat2)))
    big_l = math.radians(lon2 - lon1)
    su1, cu1, su2, cu2 = math.sin(u1), math.cos(u1), math.sin(u2), math.cos(u2)
    lam = big_l
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(cu2 * sl, cu1 * su2 - su1 * cu2 * cl)
        if ss == 0:
            return 0.0
        cs = su1 * su2 + cu1 * cu2 * cl
        sigma = math.atan2(ss, cs)
        sa = cu1 * cu2 * sl / ss
        c2a = 1 - sa * sa
        c2sm = cs - 2 * su1 * su2 / c2a if c2a else 0.0
        c = F / 16 * c2a * (4 + F * (4 - 3 * c2a))
        new = big_l + (1 - c) * F * sa * (
            sigma + c * ss * (c2sm + c * cs * (-1 + 2 * c2sm * c2sm)))
        if abs(new - lam) < 1e-12:
            lam = new
            break
        lam = new
    else:
        raise SystemExit("REFUSED NO-CONVERGENCE: %r %r %r %r" % (lat1, lon1, lat2, lon2))
    usq = c2a * (A_M * A_M - B_M * B_M) / (B_M * B_M)
    ka = 1 + usq / 16384 * (4096 + usq * (-768 + usq * (320 - 175 * usq)))
    kb = usq / 1024 * (256 + usq * (-128 + usq * (74 - 47 * usq)))
    ds = kb * ss * (c2sm + kb / 4 * (
        cs * (-1 + 2 * c2sm * c2sm)
        - kb / 6 * c2sm * (-3 + 4 * ss * ss) * (-3 + 4 * c2sm * c2sm)))
    return B_M * ka * (sigma - ds) / 1000.0


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from point 1 to point 2 on a sphere, degrees east of north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def self_test():
    """Raises unless every case holds. Prints one OK line."""
    cases = 0
    # A quarter of the equator is a * pi / 2.
    want = A_M * math.pi / 2 / 1000
    got = vincenty_km(0, 0, 0, 90)
    assert abs(got - want) < 1e-6, (got, want)
    cases += 1
    # One degree of longitude on the equator is a * pi / 180.
    want = A_M * math.pi / 180 / 1000
    got = vincenty_km(0, 10, 0, 11)
    assert abs(got - want) < 1e-9, (got, want)
    cases += 1
    # Symmetry, and agreement with the sphere to the flattening.
    pairs = [(34.633, -120.613, 34.0, -118.5), (28.5619, -80.5772, 28.0, -81.5),
             (25.997, -97.157, 27.5, -98.0), (34.633, -120.613, 37.6, -120.6)]
    for la1, lo1, la2, lo2 in pairs:
        d1, d2 = vincenty_km(la1, lo1, la2, lo2), vincenty_km(la2, lo2, la1, lo1)
        assert abs(d1 - d2) < 1e-6, (d1, d2)
        h = haversine_km(la1, lo1, la2, lo2)
        assert abs(d1 - h) / h < 0.006, (d1, h)
        cases += 1
    # The control: a call with latitude and longitude swapped must be caught by
    # the same comparison. (30, 60) to (31, 62), swapped, is (60, 30) to (62, 31).
    bad = vincenty_km(60, 30, 62, 31)
    h = haversine_km(30, 60, 31, 62)
    assert abs(bad - h) / h > 0.006, "the swapped-argument control was not caught"
    cases += 1
    # A bearing due north and one due east.
    assert abs(bearing_deg(10, 20, 11, 20)) < 1e-9
    assert abs(bearing_deg(0, 20, 0, 21) - 90) < 1e-9
    cases += 2
    print("OK self-test: %d cases" % cases)


def read_sites():
    sites = []
    with open(os.path.join(HERE, "sites.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            sid, lat, lon, name = line.rstrip("\n").split("\t")
            sites.append((sid, float(lat), float(lon), name))
    return sites


def read_queries():
    rows = []
    with open(os.path.join(HERE, "queries.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            name, site, day, use, url = line.rstrip("\n").split("\t")
            if use not in ("used", "held"):
                raise SystemExit("REFUSED BAD-USE in queries.tsv: %r" % use)
            rows.append((name, site, day, use, url))
    return rows


def open_on(start, end, day):
    """True when the epoch [start, end) holds the day. An empty end is open."""
    if start[:10] > day:
        return False
    return (not end.strip()) or end[:10] > day


def read_response(path, centre, stations, day):
    """Adds channel epochs open on the day to stations[(net, sta)]. Returns the count."""
    n = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = [x.strip() for x in line.rstrip("\n").split("|")]
            if len(p) != 17:
                raise SystemExit("REFUSED BAD-LINE in %s: %d fields" % (path, len(p)))
            net, sta, loc, cha = p[0], p[1], p[2], p[3]
            if net in EXCLUDED or not open_on(p[15], p[16], day):
                continue
            s = stations.setdefault((net, sta), {
                "lat": float(p[4]), "lon": float(p[5]), "centres": set(), "chan": {}})
            s["centres"].add(centre)
            s["chan"][(loc, cha)] = float(p[14])
            n += 1
    return n


def channel_summary(chan, want):
    """Groups channels by their first two letters and rate: 'HH[ENZ]@100'."""
    groups = {}
    for (_loc, cha), sr in chan.items():
        if not want(cha):
            continue
        groups.setdefault((cha[:2], "%g" % sr), set()).add(cha[2])
    return ", ".join("%s[%s]@%s" % (two, "".join(sorted(third)), sr)
                     for (two, sr), third in sorted(groups.items()))


def is_infrasound(cha):
    # source code D is pressure and subsource F is infrasound (the study's row K2)
    return len(cha) == 3 and cha[1:] == "DF" and cha[0] not in "AQ"


def is_barometer(cha):
    # pressure, outside, inside or down a hole. Band codes A and Q are left
    # out: with source D they name state-of-health values in these responses
    # (a data gap count, a latency), not a pressure.
    return len(cha) == 3 and cha[1] == "D" and cha[2] in "OID" and cha[0] not in "AQ"


def is_seismic(cha):
    # source codes H, L, N, P: seismometers, accelerometers, geophones. Band
    # codes sampled faster than 10 per second (the study's row K1).
    return len(cha) == 3 and cha[1] in "HLNP" and cha[0] in "BCDEFGHS"


def window(d_km):
    """(sound first, sound last, ground first, ground last), seconds after T0."""
    return (d_km / C_AIR_FAST - TIME_MARGIN,
            d_km / C_AIR_SLOW + SOURCE_SECONDS + TIME_MARGIN,
            d_km / V_GROUND_FAST - TIME_MARGIN,
            d_km / V_GROUND_SLOW + SOURCE_SECONDS + TIME_MARGIN)


def ladder(rows):
    """The nearest LADDER_NET station with LADDER_CHANNELS, then at each step
    the nearest one at least LADDER_FACTOR times farther. rows is sorted."""
    have = [r for r in rows if r[1] == LADDER_NET and r[0] <= LADDER_MAX_KM and all(
        any(cha == want for (_loc, cha) in r[3]["chan"]) for want in LADDER_CHANNELS)]
    picked = have[:1]
    for r in have[1:]:
        if r[0] >= LADDER_FACTOR * picked[-1][0]:
            picked.append(r)
    return picked


def station_rows(stations, slat, slon):
    rows = []
    for (net, sta), s in stations.items():
        seis = channel_summary(s["chan"], is_seismic)
        infra = channel_summary(s["chan"], is_infrasound)
        baro = channel_summary(s["chan"], is_barometer)
        pres = "; ".join(x for x in (infra and "infrasound " + infra,
                                     baro and "barometer " + baro) if x)
        if not seis and not pres:
            continue
        d = vincenty_km(slat, slon, s["lat"], s["lon"])
        rows.append((d, net, sta, s, seis, pres))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--responses", help="folder of saved station-service responses")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--unhold", action="append", default=[], choices=sorted(CENTRES),
                    help="read held responses whose file name starts with this prefix")
    ap.add_argument("--as-of", default=AS_OF,
                    help="read the requests made about this date (default %s)" % AS_OF)
    ap.add_argument("--near-km", type=float, default=60.0,
                    help="list every station nearer than this (default 60)")
    ap.add_argument("--at-least", type=int, default=6,
                    help="and never fewer than this many of the nearest (default 6)")
    ap.add_argument("--site", help="print this site only (an id from sites.tsv)")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        if not a.responses:
            return 0
    if not a.responses:
        ap.error("--responses DIR is needed")
    out = sys.stdout
    out.reconfigure(encoding="utf-8", newline="\n")
    queries = read_queries()
    sites = read_sites()
    if a.site and a.site not in [s[0] for s in sites]:
        raise SystemExit("REFUSED NO-SUCH-SITE: %s" % a.site)
    for sid, slat, slon, sname in sites:
        if a.site and sid != a.site:
            continue
        stations, used, held = {}, [], []
        for name, qsite, day, use, _url in queries:
            # KSC and CCSFS are a few km apart and share one set of responses.
            if qsite != sid and not (sid == "KSC" and qsite == "CCSFS"):
                continue
            if day != a.as_of:
                continue
            if use == "held" and name.split("-")[0] not in a.unhold:
                held.append(name)
                continue
            path = os.path.join(a.responses, name)
            if not os.path.isfile(path):
                raise SystemExit("REFUSED MISSING-RESPONSE: %s" % name)
            used.append((name, read_response(path, CENTRES[name.split("-")[0]],
                                             stations, a.as_of)))
        print("### %s: %s" % (sid, sname))
        print()
        print("Site at %.5f, %.5f. Responses used: %s. Responses held and not opened: %s."
              % (slat, slon,
                 "; ".join("`%s` (%d channel epochs open on %s)" % (u[0], u[1], a.as_of)
                           for u in used) or "none",
                 ", ".join("`%s`" % h for h in held) or "none"))
        print()
        if not used:
            print("No table: no response is in use for this site.")
            print()
            continue
        rows = station_rows(stations, slat, slon)
        print("Stations with a seismic or pressure channel open on %s: %d."
              % (a.as_of, len(rows)))
        print()
        print("| station | lat | lon | km | bearing from site | seismic channels @ samples/s "
              "| pressure channels @ samples/s | metadata served by |")
        print("|---|---|---|---|---|---|---|---|")
        listed = [r for r in rows if r[0] <= a.near_km]
        if len(listed) < a.at_least:
            listed = rows[:a.at_least]
        for d, net, sta, s, seis, pres in listed:
            print("| %s.%s | %.4f | %.4f | %.1f | %03.0f | %s | %s | %s |" % (
                net, sta, s["lat"], s["lon"], d,
                bearing_deg(slat, slon, s["lat"], s["lon"]), seis or "none",
                pres or "none", ", ".join(sorted(s["centres"]))))
        print()
        print("| distance band, km | stations | of them with a pressure channel | networks |")
        print("|---|---|---|---|")
        for lo, hi in BANDS:
            inband = [r for r in rows if lo <= r[0] < hi]
            nets = {}
            for r in inband:
                nets[r[1]] = nets.get(r[1], 0) + 1
            print("| %d to %d | %d | %d | %s |" % (
                lo, hi, len(inband), sum(1 for r in inband if r[5]),
                ", ".join("%s %d" % kv for kv in sorted(nets.items())) or "none"))
        print()
        pres_rows = [r for r in rows if r[5] and r[0] < BANDS[-1][1]]
        print("Stations within %d km with a pressure channel: %d."
              % (BANDS[-1][1], len(pres_rows)))
        print()
        if pres_rows:
            print("| station | km | pressure channels @ samples/s | seismic channels @ samples/s "
                  "| metadata served by |")
            print("|---|---|---|---|---|")
            for d, net, sta, s, seis, pres in pres_rows:
                print("| %s.%s | %.1f | %s | %s | %s |" % (
                    net, sta, d, pres, seis or "none", ", ".join(sorted(s["centres"]))))
            print()
        lad = ladder(rows)
        if not lad:
            print("No ladder: no %s station with %s is listed within %d km of this site."
                  % (LADDER_NET, ", ".join(LADDER_CHANNELS), LADDER_MAX_KM))
            print()
            continue
        print("The ladder: %s stations with %s out to %d km. The first rung is the nearest; "
              "each next rung is the nearest station at least %.1f times farther than the "
              "rung before. Windows are seconds after the catalogue's launch time."
              % (LADDER_NET, ", ".join(LADDER_CHANNELS), LADDER_MAX_KM, LADDER_FACTOR))
        print()
        print("| station | lat | lon | km | bearing from site | sound, earliest | sound, latest "
              "| ground, earliest | ground, latest |")
        print("|---|---|---|---|---|---|---|---|---|")
        for d, net, sta, s, seis, pres in lad:
            print("| %s.%s | %.4f | %.4f | %.1f | %03.0f | %.0f | %.0f | %.0f | %.0f |" % (
                (net, sta, s["lat"], s["lon"], d,
                 bearing_deg(slat, slon, s["lat"], s["lon"])) + window(d)))
        print()
    print("Window parameters: sound %.3f to %.3f km/s; ground %.1f to %.1f km/s; "
          "a source lasting %.0f s; %.0f s either side for the catalogue's time."
          % (C_AIR_SLOW, C_AIR_FAST, V_GROUND_SLOW, V_GROUND_FAST,
             SOURCE_SECONDS, TIME_MARGIN))
    print("Networks left out: %s." % "; ".join("%s (%s)" % kv for kv in EXCLUDED.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
