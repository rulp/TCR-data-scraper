#!/usr/bin/env python3
"""Take a screened paper into an extraction batch: assign its ID, index it, make its folder.

`journals/journals.md` states the rule -- "a paper gets its permanent ID, its
paper_source.md row and its root-level folder when it enters an extraction batch" -- but
nothing performed it, so the never-renumber/never-reuse invariant was maintained by hand.
This does it in one step, and moves across any files already fetched into the journal's
`incoming/<PMID>/` staging directory.

    python3 tools/new_paper.py --pmid 38684663 --from J01
    python3 tools/new_paper.py --pmid 41058174 --author Jones --year 2026 --journal "Mol Ther"
    python3 tools/new_paper.py --pmid 38684663 --from J01 --dry-run
    python3 tools/new_paper.py --help

With `--from J##` the author, year and title come from that sweep's `candidates.tsv` and the
journal name from `journals/journals.md`; the explicit flags override whatever is found and
are the whole input for a PMID handed over ad hoc. `--title` and `--source` are optional.

Standard library only. Safe to re-run: a PMID already in the index is refused, never
duplicated, because PMID is the key that makes a paper found twice -- once by a journal
sweep, once by a database citation -- dedupe to one row.
"""
import csv
import datetime
import importlib.util
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "paper_source.md")

sys.path.insert(0, HERE)
import export_index                                  # noqa: E402  -- its rows() parses the index

FLAGS = ("--pmid", "--from", "--author", "--year", "--journal", "--title", "--source",
         "--dry-run", "--help", "-h")
VALUED = ("--pmid", "--from", "--author", "--year", "--journal", "--title", "--source")


def arg(argv, flag, default=None):
    """Value of a --flag, or `default`. Exits with usage if the value is missing."""
    if flag not in argv:
        return default
    i = argv.index(flag) + 1
    if i >= len(argv) or argv[i].startswith("--"):
        sys.exit("new_paper.py: %s needs a value\n%s" % (flag, __doc__))
    return argv[i]


def journal_name(jid):
    """The journal's NLM [ta] abbreviation, via probe.py's own parser of journals.md.

    Imported rather than re-implemented: a second regex over the same table is a second
    thing to keep in step with the table's layout.
    """
    p = os.path.join(ROOT, "journals", "probe.py")
    spec = importlib.util.spec_from_file_location("_probe", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    name, ta, _win, _hdr = m.journal_row(jid)
    return ta, name


def sweep_dir(jid):
    """The journal's sweep folder, found by prefix so the abbreviation need not be rebuilt."""
    base = os.path.join(ROOT, "journals")
    hits = [d for d in sorted(os.listdir(base)) if d.startswith(jid + "_")
            and os.path.isdir(os.path.join(base, d))]
    return os.path.join(base, hits[0]) if hits else None


def from_candidates(jid, pmid):
    """(author, year, title) for a PMID out of that sweep's ledger, or blanks."""
    d = sweep_dir(jid)
    led = os.path.join(d, "candidates.tsv") if d else None
    if not led or not os.path.exists(led):
        return "", "", ""
    with open(led, encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            # probe.py COLS: pmid pmcid author year verdict ... title
            if row and row[0] == pmid:
                return (row[2] if len(row) > 2 else "",
                        row[3] if len(row) > 3 else "",
                        row[13] if len(row) > 13 else "")
    return "", "", ""


def label(author):
    """A folder-safe surname. Keeps hyphens (Marrer-Berger), drops everything else."""
    s = re.sub(r"[^A-Za-z-]", "", (author or "").strip().replace(" ", "-")).strip("-")
    return s or "Unknown"


def read_index():
    """(existing rows, insert position) -- the line AFTER the table's last row."""
    lines = open(INDEX, encoding="utf-8").read().split("\n")
    rows = list(export_index.rows("\n".join(lines)))
    sep = next((i for i, ln in enumerate(lines)
                if ln.startswith("|") and set(ln) <= set("|- ")), None)
    if sep is None:
        sys.exit("new_paper.py: no table found in paper_source.md -- is it the seeded template?")
    i = sep + 1
    while i < len(lines) and lines[i].startswith("|"):
        i += 1
    return lines, rows, i


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)          # an explicit help request is a success, not an error
        return 0
    values = {argv[i + 1] for i, a in enumerate(argv) if a in VALUED and i + 1 < len(argv)}
    for a in argv:
        if a.startswith("-") and a not in FLAGS and a not in values:
            sys.exit("new_paper.py: unknown option %s\n%s" % (a, __doc__))

    pmid = arg(argv, "--pmid")
    if not pmid or not pmid.isdigit():
        sys.exit("new_paper.py: --pmid is required and must be digits\n%s" % __doc__)
    if not os.path.exists(INDEX):
        sys.exit("no paper_source.md yet -- run: python3 tools/init_workspace.py")

    jid = arg(argv, "--from")
    if jid and not re.fullmatch(r"J\d\d", jid):
        sys.exit("new_paper.py: --from takes a journal id like J01")

    author = year = title = ""
    journal = ""
    if jid:
        author, year, title = from_candidates(jid, pmid)
        journal = journal_name(jid)[0]
    author = arg(argv, "--author", author)
    year = arg(argv, "--year", year)
    journal = arg(argv, "--journal", journal)
    title = arg(argv, "--title", title)
    source = arg(argv, "--source",
                 ("%s %s" % (jid, datetime.date.today().strftime("%Y-%m"))) if jid else "ad hoc")
    if not author:
        sys.exit("new_paper.py: no author found for PMID %s -- pass --author\n%s" % (pmid, __doc__))

    lines, rows, at = read_index()

    for r in rows:
        if r[1] == pmid:
            sys.exit("new_paper.py: PMID %s is already paper %s (%s). IDs are never reused; "
                     "if it was dropped, leave the row as it is." % (pmid, r[0], r[2]))

    # max + 1, NOT count + 1: a dropped paper keeps its row and its number.
    nid = "%03d" % (max((int(r[0]) for r in rows), default=0) + 1)
    name = label(author)
    folder = os.path.join(ROOT, "%s_%s" % (nid, name))
    raw = os.path.join(folder, "raw")

    staged = []
    if jid:
        d = sweep_dir(jid)
        inc = os.path.join(d, "incoming", pmid) if d else None
        if inc and os.path.isdir(inc):
            staged = sorted(f for f in os.listdir(inc) if not f.startswith("."))

    row = "| %s | %s | %s | %s | %s | %s | %s | queued |" % (
        nid, pmid, author, year or "?", journal or "?",
        (title or "")[:60].replace("|", "/"), source)

    print("paper   %s_%s" % (nid, name))
    print("row     %s" % row)
    print("folder  %s/" % os.path.relpath(raw, ROOT))
    if staged:
        print("staged  %d file(s) to move from %s"
              % (len(staged), os.path.relpath(inc, ROOT)))
        for f in staged:
            print("          %s" % f)

    if "--dry-run" in argv:
        print("\n--dry-run: nothing written.")
        return 0

    if os.path.exists(folder):
        sys.exit("new_paper.py: %s already exists -- refusing to merge into it" % folder)

    os.makedirs(raw)
    for f in staged:
        shutil.move(os.path.join(inc, f), os.path.join(raw, f))

    lines.insert(at, row)
    open(INDEX, "w", encoding="utf-8").write("\n".join(lines))

    print("\nwrote the row and created the folder.")
    if staged:
        print("moved %d staged file(s) into raw/." % len(staged))
    print("next: write %s/%s_%s.py" % (os.path.relpath(folder, ROOT), nid, name))
    if jid:
        d = sweep_dir(jid)
        note = os.path.join(d, "notes", pmid + ".md") if d else None
        if note and os.path.exists(note):
            print("      the locator at %s already says where every column lives"
                  % os.path.relpath(note, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
