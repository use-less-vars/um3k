#!/usr/bin/env python3
"""Aggregate per-file JUnit XMLs into exact suite counts.

Counts come from <testcase> children only -- never from pytest progress
characters, which undercount on a killed run and cannot see errors/xfails.

  aggregate.py --mark <testfile> <rc> <wall_s>   write .scratch/test_state/<base>.done
  aggregate.py --summary                         exact totals + slowest files
"""
import os
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
STATE = os.path.join(ROOT, ".scratch", "test_state")
JUNIT = os.path.join(ROOT, ".scratch", "junit")


def counts(path):
    """Exact counts for one JUnit XML, from <testcase> elements."""
    t = f = e = s = x = 0
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return dict(tests=0, failed=0, errored=0, skipped=0, xfailed=0, time=0.0)
    suite_time = 0.0
    for ts in root.iter("testsuite"):
        try:
            suite_time += float(ts.get("time") or 0.0)
        except ValueError:
            pass
    for tc in root.iter("testcase"):
        t += 1
        kinds = {c.tag for c in tc}
        if "failure" in kinds:
            f += 1
        elif "error" in kinds:
            e += 1
        elif "skipped" in kinds:
            typ = ""
            for c in tc:
                if c.tag == "skipped":
                    typ = c.get("type") or ""
            if typ == "pytest.xfail":
                x += 1
            else:
                s += 1
    return dict(tests=t, failed=f, errored=e, skipped=s, xfailed=x, time=suite_time)


def mark(testfile, rc, wall):
    base = os.path.basename(testfile)[:-3] if testfile.endswith(".py") else testfile
    c = counts(os.path.join(JUNIT, base + ".xml"))
    os.makedirs(STATE, exist_ok=True)
    rc = int(rc)  # argv gives a string; "--mark" must not turn rc=0 into FAIL
    verdict = "PASS" if (rc == 0 and c["failed"] == 0 and c["errored"] == 0) else "FAIL"
    line = ("%s rc=%s wall=%ss tests=%d passed=%d failed=%d errored=%d "
            "skipped=%d xfailed=%d\n" % (
                verdict, rc, wall, c["tests"],
                c["tests"] - c["failed"] - c["errored"] - c["skipped"] - c["xfailed"],
                c["failed"], c["errored"], c["skipped"], c["xfailed"]))
    with open(os.path.join(STATE, base + ".done"), "w") as fh:
        fh.write(line)
    sys.stdout.write("MARK %-34s %s" % (base, line))


def summary():
    tests = dict(root=os.path.join(ROOT, "tests"))
    files = sorted(fn for fn in os.listdir(tests["root"])
                   if fn.startswith("test_") and fn.endswith(".py"))
    tot = dict(tests=0, passed=0, failed=0, errored=0, skipped=0, xfailed=0)
    per_file, missing = [], []
    for fn in files:
        base = fn[:-3]
        p = os.path.join(JUNIT, base + ".xml")
        if not os.path.exists(p):
            m = os.path.join(STATE, base + ".done")
            state = "marked" if os.path.exists(m) else "PENDING"
            missing.append((fn, state))
            continue
        c = counts(p)
        passed = c["tests"] - c["failed"] - c["errored"] - c["skipped"] - c["xfailed"]
        tot["tests"] += c["tests"]; tot["passed"] += passed
        tot["failed"] += c["failed"]; tot["errored"] += c["errored"]
        tot["skipped"] += c["skipped"]; tot["xfailed"] += c["xfailed"]
        per_file.append((c["time"], fn, c))

    for c_time, fn, c in per_file:
        passed = c["tests"] - c["failed"] - c["errored"] - c["skipped"] - c["xfailed"]
        print("%-38s tests=%-4d pass=%-4d fail=%-3d err=%-3d skip=%-3d xfail=%-3d %6.1fs"
              % (fn, c["tests"], passed, c["failed"], c["errored"], c["skipped"],
                 c["xfailed"], c_time))
    slow = sorted(per_file, reverse=True)[:8]
    print("\nslowest files:")
    for c_time, fn, _c in slow:
        print("  %6.1fs  %s" % (c_time, fn))
    if missing:
        print("\nfiles without results: %d" % len(missing))
        for fn, state in missing:
            print("  %-38s %s" % (fn, state))
    print("\nTOTAL: %d tests, %d passed, %d failed, %d skipped, %d xfailed (plus %d errored)"
          % (tot["tests"], tot["passed"], tot["failed"], tot["skipped"],
             tot["xfailed"], tot["errored"]))
    return 0 if not missing else 3


def main(argv):
    if len(argv) >= 4 and argv[1] == "--mark":
        mark(argv[2], argv[3], argv[4])
        return 0
    return summary()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
