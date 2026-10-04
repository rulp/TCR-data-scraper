#!/usr/bin/env python3
"""Turn this machine's paper_source.md into rows for the shared tracking sheet.

Indexes are per-machine, so the local ID means nothing elsewhere; PMID is the key
both machines agree on. This prints the Papers tab as CSV, ready to paste.

    python3 tools/export_index.py                 # this machine's name from hostname
    python3 tools/export_index.py --machine mac   # or name it yourself

Standard library only.
"""
import csv
import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "paper_source.md")


def rows(text):
    """Every data row of the one markdown table whose first cell is a 3-digit ID."""
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 8 and cells[0].isdigit() and len(cells[0]) == 3:
            yield cells


def main(argv):
    if "--help" in argv or "-h" in argv:
        sys.exit(__doc__)
    machine = argv[argv.index("--machine") + 1] if "--machine" in argv else socket.gethostname()

    if not os.path.exists(INDEX):
        sys.exit("no paper_source.md yet -- run: python3 tools/init_workspace.py")

    out = csv.writer(sys.stdout)
    out.writerow(["PMID", "Author", "Year", "Journal", "Machine", "Local ID", "Rows", "Status"])
    n = 0
    for c in rows(open(INDEX, encoding="utf-8").read()):
        pid, pmid, author, year, journal = c[0], c[1], c[2], c[3], c[4]
        out.writerow([pmid, author, year, journal, machine, pid, "", c[7]])
        n += 1
    print("# %d paper(s) from %s" % (n, machine), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
