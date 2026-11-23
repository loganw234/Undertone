#!/usr/bin/env python3
"""What a station service says, at response level, about each channel's digitiser.

    python docs/studies/d1/digitisers.py RESPONSE.xml

It makes no request. It reads one saved answer of an FDSN station service
at level=response (FDSN StationXML) and prints a markdown table, one row a
channel: the sensor's description, the data logger's description if the
answer has one, the gain of the stage that turns volts into counts, and the
overall sensitivity.

It also prints, for that volts-to-counts gain g, the number g * 40 / 2**24.
A 24-bit converter spanning 40 volts gives 2**24 / 40 = 419430.4 counts a
volt, so a value near 1 is what such a converter would show.

WHAT IT CANNOT SEE
  - The converter's width. A gain in counts per volt is not a width: the
    answer does not state the converter's full-scale voltage, so the width
    stays an inference until a record's own sample values are read.
  - Whether the description matches the instrument in the vault.
"""
import sys
import xml.etree.ElementTree as ET

NS = {"s": "http://www.fdsn.org/xml/station/1"}


def text(node, path):
    found = node.find(path, NS)
    return found.text.strip() if found is not None and found.text else ""


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    root = ET.parse(sys.argv[1]).getroot()
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print("| channel | epoch | sensor, as described | data logger, as described | "
          "samples/s | volts-to-counts gain | gain x 40 / 2^24 | counts per input unit |")
    print("|---|---|---|---|---|---|---|---|")
    rows = 0
    for net in root.findall("s:Network", NS):
        for sta in net.findall("s:Station", NS):
            for cha in sta.findall("s:Channel", NS):
                adc = []
                for stage in cha.findall("s:Response/s:Stage", NS):
                    unit_in = unit_out = ""
                    for kind in ("PolesZeros", "Coefficients", "FIR", "Polynomial",
                                 "ResponseList"):
                        k = stage.find("s:" + kind, NS)
                        if k is not None:
                            unit_in = text(k, "s:InputUnits/s:Name")
                            unit_out = text(k, "s:OutputUnits/s:Name")
                            break
                    if unit_in.upper() in ("V", "VOLTS") and unit_out.upper() in ("COUNTS",
                                                                                 "COUNT"):
                        adc.append(float(text(stage, "s:StageGain/s:Value")))
                if len(adc) != 1:
                    raise SystemExit("REFUSED NOT-ONE-CONVERTER-STAGE: %s.%s %s has %d"
                                     % (net.get("code"), sta.get("code"), cha.get("code"),
                                        len(adc)))
                g = adc[0]
                print("| %s.%s.%s.%s | %s to %s | %s | %s | %s | %g | %.4f | %s %s per %s |" % (
                    net.get("code"), sta.get("code"), cha.get("locationCode") or "--",
                    cha.get("code"), cha.get("startDate", "")[:10], cha.get("endDate", "")[:10],
                    text(cha, "s:Sensor/s:Description") or "none given",
                    text(cha, "s:DataLogger/s:Description") or "none given",
                    text(cha, "s:SampleRate"), g, g * 40 / 2 ** 24,
                    "%.6g" % float(text(cha, "s:Response/s:InstrumentSensitivity/s:Value")),
                    text(cha, "s:Response/s:InstrumentSensitivity/s:OutputUnits/s:Name").lower(),
                    text(cha, "s:Response/s:InstrumentSensitivity/s:InputUnits/s:Name")))
                rows += 1
    print()
    print("%d channels. A data logger is described for %s of them."
          % (rows, "none" if "DataLogger" not in open(sys.argv[1], encoding="latin-1").read()
             else "some"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
