#!/usr/bin/env python3
"""Audit every clean row against the source it claims to come from.

`checks.md` C12 asserts that an attribution is PRESENT. This asserts it is TRUE. The two
are different jobs: C12 runs inside the build, this runs against the shipped workbook and
imports nothing from any build script -- it re-reads raw/, re-fetches external records and
re-transcribes figures.

Needs pandas, openpyxl and pypdf (see requirements.txt); a bare `python3 audit.py` only
works inside a venv that has them. Otherwise:

    uv run --with pandas --with openpyxl --with pypdf python audit.py

    audit.py                   # every paper in the tree, writes AUDIT.md
    audit.py --papers <ID>,... # only these paper IDs; writes AUDIT_partial.md instead
    audit.py --figures         # also (re)emit blind transcription task cards
    audit.py --no-network      # skip external re-fetching; PDB checks -> unverifiable
    audit.py --root DIR        # audit a different tree and write ITS AUDIT.md
    audit.py --help

Verdicts, one per distinct (field, value, source):

    verified      found at the place the source names
    mislocated    present in the paper's raw/, but NOT in the file the source names
    judgement     an annotation decision, not a quotable string (the two species columns)
    unverifiable  no machine route; the reason is recorded, never silently passed
    contradicted  claimed to be in the paper's materials and is nowhere in them

Exits non-zero if anything is contradicted. It never writes to clean_*.xlsx or
clean_*_provenance.csv -- resolving a mismatch is a judgement call, not an edit.

Figure-sourced values are verified in two phases so that blindness is structural:
`--figures` writes a task card naming only the image and what to transcribe, an agent
writes its reading to audit/reads/<id>.json, and every subsequent run diffs the two.
The card never contains the recorded value; an agent shown the answer would simply
confirm it. `procedures/audit-provenance.md` is the procedure around this script.
"""
import glob
import json
import logging
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))


def arg(flag, default=None):
    """Value of a --flag, or `default`. Exits with usage if the value is missing."""
    if flag not in sys.argv:
        return default
    i = sys.argv.index(flag) + 1
    if i >= len(sys.argv) or sys.argv[i].startswith("--"):
        sys.exit("audit.py: %s needs a value\n%s" % (flag, __doc__))
    return sys.argv[i]


if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)          # an explicit help request is a success, not an error
    sys.exit(0)
_FLAGS = ("--papers", "--figures", "--no-network", "--root", "--help", "-h")
_values = {sys.argv[i + 1] for i, a in enumerate(sys.argv[1:], 1)
           if a in ("--papers", "--root") and i + 1 < len(sys.argv)}
for _a in sys.argv[1:]:
    # Single-dash too: `audit.py -x` used to be ignored and proceed to a full run that
    # overwrites AUDIT.md. SETUP.md promises an unknown flag is refused, not ignored.
    if _a.startswith("-") and _a not in _FLAGS and _a not in _values:
        sys.exit("audit.py: unknown option %s\n%s" % (_a, __doc__))

# Fail loudly on a missing dependency. A missing pypdf used to be swallowed, which turned
# every PDF-sourced value into `contradicted` -- a wrong answer delivered quietly.
_missing = []
for _m in ("pandas", "openpyxl", "pypdf"):
    try:
        __import__(_m)
    except ImportError:
        _missing.append(_m)
if _missing:
    sys.exit("audit.py needs: %s\n  pip install -r requirements.txt\n"
             "  or: uv run %s python audit.py"
             % (", ".join(_missing),
                " ".join("--with " + m for m in ("pandas", "openpyxl", "pypdf"))))

# --root audits a different tree (used for the negative control, which corrupts a scratch
# copy on purpose). EVERYTHING the audit writes follows the root -- the report and the
# audit/ state directory alike. Pinning audit/ to HERE meant a `--root <scratch> --figures`
# run overwrote the real tree's task cards and reused its blind reads, and audit/reads/
# is the one thing SETUP.md says cannot be regenerated honestly.
ROOT = arg("--root", HERE)
AUDIT = os.path.join(ROOT, "audit")
SCHEMA = ["Va", "Ja", "CDR3a", "Vb", "Jb", "CDR3b",
          "Antigen", "MHC", "pMHC_species", "TCR_species"]
# These two record a decision about provenance, not a string lifted from the paper.
# Nothing to match them against, so they are never reported as `verified`.
JUDGEMENT_COLS = {"pMHC_species", "TCR_species"}
# What KIND of thing each column holds decides what can verify it. A CDR3 is a
# substring of a protein sequence; a V gene is an ASSIGNMENT someone made about that
# sequence. A PDB entry can confirm the first and says nothing about the second.
AA_COLS = {"CDR3a", "CDR3b", "Antigen"}
GENE_COLS = {"Va", "Ja", "Vb", "Jb"}
ALLELE_COLS = {"MHC"}
# Sources that name a gene call rather than a raw sequence.
GENE_SOURCES = re.compile(r"(?i)\b(VDJdb|IMGT|IEDB|Table|GenBank)\b")

TOKEN = re.compile(r"[A-Za-z0-9*:_.\-]+")
NET = "--no-network" not in sys.argv
logging.getLogger("pypdf").setLevel(logging.ERROR)   # font/xref noise, not our problem


# ------------------------------------------------------------------ raw/ indexing
def read_any(path):
    """Best-effort text of one raw file. Returns '' for things we cannot read."""
    ext = path.lower().rsplit(".", 1)[-1]
    try:
        if ext in ("xml", "csv", "tsv", "txt", "json", "md", "fasta", "fa"):
            return open(path, encoding="utf-8", errors="replace").read()
        if ext in ("xlsx", "xlsm"):
            import openpyxl
            out = []
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            for ws in wb.worksheets:
                out.append(ws.title)
                for row in ws.iter_rows(values_only=True):
                    out.extend(str(c) for c in row if c is not None)
            wb.close()
            return "\n".join(out)
        if ext == "zip":
            out = []
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    out.append(n)
                    if n.lower().rsplit(".", 1)[-1] in ("csv", "tsv", "txt", "json", "xml"):
                        with z.open(n) as fh:
                            out.append(fh.read().decode("utf-8", "replace"))
            return "\n".join(out)
        if ext == "pdf":
            from pypdf import PdfReader   # guaranteed present; checked at startup
            return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    except Exception as e:
        return "\n<<unreadable: %s>>" % e
    return ""


_raw_cache = {}


def raw_index_cached(paper_dir):
    if paper_dir not in _raw_cache:
        _raw_cache[paper_dir] = index_raw(paper_dir)
    return _raw_cache[paper_dir]


def index_raw(paper_dir):
    """{relative path -> (text, token set)} for every readable file under raw/."""
    idx = {}
    for p in sorted(glob.glob(os.path.join(paper_dir, "raw", "**", "*"), recursive=True)):
        if os.path.isdir(p):
            continue
        txt = read_any(p)
        if txt:
            idx[os.path.relpath(p, paper_dir)] = (txt, set(TOKEN.findall(txt)))
    return idx


def variants(field, value):
    """Spellings of the same fact to accept.

    MHC alleles are written several ways across sources: `DRB1*11:01` (IMGT colon form,
    what this schema uses), `DRB1*1101` (4-digit, common in older papers) and with or
    without the `HLA-` prefix. They denote the same allele, so a literal string match
    produces false `contradicted` verdicts. Class II heterodimers (`DQA1*05/DQB1*02`)
    are split and every chain must be found.
    """
    v = str(value).strip()
    if field in GENE_COLS:
        # Supplementary tables routinely abbreviate: a TRAJ column holding "J43" with a
        # neighbouring TRAV column means TRAJ43. Accept the abbreviations the full name
        # implies, so a legitimate normalisation is not reported as a fabrication.
        #
        # IMGT dual TRA/TRD genes carry a slash -- TRAV14/DV4*03, TRAV38-2/DV8*01 -- and the
        # tokenizer does not treat "/" as a word character, so the file holds TRAV14 and
        # DV4*03 as two separate tokens and the full name is never one. Split on the slash
        # and require BOTH halves, exactly as a class II heterodimer below is split and every
        # chain must be found. Without this, every paper using a dual gene reported its Va as
        # unverifiable even when the name was printed verbatim in raw/.
        def _forms(part):
            f = {part}
            if part.startswith("TR") and len(part) > 3:
                f |= {part[2:], part[3:]}
            return sorted(f)

        if "/" in v:
            return [_forms(part.strip()) for part in v.split("/") if part.strip()]
        return [_forms(v)]
    if field not in ALLELE_COLS:
        return [[v]]
    groups = []
    for part in v.split("/"):
        part = part.strip()
        forms = {part, part.replace(":", ""), "HLA-" + part, "HLA-" + part.replace(":", "")}
        if part.startswith("H2-"):          # mouse: H2-IAb, also written H2-IA(b), I-Ab
            stem = part[3:]
            forms |= {part.replace("H2-", "H-2"), "I-" + stem,
                      "H2-%s(%s)" % (stem[:-1], stem[-1]) if len(stem) > 1 else part}
        groups.append(sorted(forms))
    return groups


def found_in(idx, value, field=None):
    """Which raw files contain this value. Every component group must be satisfied.

    Gene names match whole tokens only: `TRAJ5` must not be satisfied by `TRAJ53`.
    Sequences may match as substrings, because a peptide is often quoted inside a longer
    tile and a CDR3 inside a full-length chain.
    """
    groups = variants(field, value)
    exact_only = field in GENE_COLS

    # Pass 1: token lookups only. These are O(1) set hits and settle almost everything.
    hits = [rel for rel, (txt, toks) in idx.items()
            if all(any(f in toks for f in g) for g in groups)]
    if hits or exact_only:
        return hits

    # Pass 2: substring, only when nothing matched as a token anywhere. A peptide is often
    # quoted inside a longer tile and a CDR3 inside a full-length chain, so this is needed --
    # but it scans whole files, so it must never run in the common case. Doing it per file
    # in pass 1 made a 28k-row paper effectively unauditable.
    return [rel for rel, (txt, toks) in idx.items()
            if all(any(f in txt for f in g) for g in groups)]


# ------------------------------------------------------- what does a source point at?
FIG = re.compile(r"(?i)\b(?:fig\.?|figure|extended data fig\.?)\s*(s?\d+[a-z]?)")
EXT = re.compile(r"(?i)\b(PDB|RCSB|VDJdb|GenBank|IEDB|IMGT|UniProt|PMID|doi)\b")
# "reused from paper <ID>" -- a legitimate cross-paper citation; audit it against THAT
# paper's raw/. The number is whatever local ID that paper carries in this workspace.
# paper's raw/, because that is where the evidence actually lives.
REUSE = re.compile(r"(?i)\b(?:reused from |see )?paper\s*(\d{3})\b")
PDBID = re.compile(r"\b([0-9][A-Za-z0-9]{3})\b")
FILEISH = re.compile(r"(?i)(raw/[\w./-]+|mmc\d+\.\w+|[\w.-]+\.(?:csv|tsv|xlsx|xls|zip|json|xml|pdf))")
TABLE = re.compile(r"(?i)\btable\s*(s?\d+[a-z]?)")


def locator(source, idx):
    """Resolve the files a source string points at. Returns a sorted list of paths."""
    paths = []
    for m in FILEISH.findall(source):
        name = m[0] if isinstance(m, tuple) else m
        base = os.path.basename(name)
        for rel in idx:
            if os.path.basename(rel).lower() == base.lower() or rel.lower().endswith(base.lower()):
                paths.append(rel)
    if not paths:
        for t in TABLE.findall(source):
            tag = ("TableS" + t.lstrip("Ss")).lower()
            for rel in idx:
                if tag in os.path.basename(rel).replace("_", "").lower():
                    paths.append(rel)
    return sorted(set(paths))


NO_RAW = ("%s/raw/ is not present, so nothing local can be checked -- this is the normal "
          "state of a fresh clone. Rebuild it from the curl commands in the build script's "
          "docstring (see SETUP.md), then re-run.")


def classify(field, value, source, idx, figure_reads, paper):
    """-> (verdict, evidence)"""
    if field in JUDGEMENT_COLS:
        return "judgement", "annotation decision; no quotable string to match"

    value = str(value).strip()
    if not value:
        return "contradicted", "empty value"

    hinted = locator(source, idx)
    anywhere = found_in(idx, value, field)

    # 1. cited a specific file we can open
    if hinted:
        inside = [h for h in hinted if h in anywhere]
        if inside:
            return "verified", "found in " + ", ".join(inside[:3])
        if anywhere:
            return "mislocated", ("source names %s but the value is in %s"
                                  % (", ".join(hinted[:2]), ", ".join(anywhere[:3])))

    # 1b. present verbatim in the paper's own materials. This outranks any figure
    # mention in the source string: a source often cites a figure for the PAIRING while
    # the value itself is printed in Methods, and the text is the stronger evidence.
    if anywhere:
        return "verified", "found verbatim in " + ", ".join(anywhere[:3])

    # 2. cited a figure -> only the blind re-read can settle it
    figs = FIG.findall(source)
    if figs:
        key = "%s_fig%s" % (paper, figs[0].lower())
        read = figure_reads.get(key)
        if read is None:
            return "unverifiable", ("figure %s: no blind transcription yet -- run "
                                    "`audit.py --figures`, then follow "
                                    "procedures/audit-provenance.md" % figs[0])
        if value in read["tokens"]:
            return "verified", "matches blind re-read of %s (%s)" % (figs[0], read["by"])
        if value in read.get("unreadable", []):
            return "unverifiable", "figure %s: transcriber marked it unreadable" % figs[0]
        return "contradicted", ("blind re-read of figure %s does not contain %r; it read: %s"
                                % (figs[0], value, ", ".join(sorted(read["tokens"])[:6])))

    # 2b. cited another paper of ours -- look where that paper keeps its evidence
    for other in REUSE.findall(source):
        odir = next((d for d in glob.glob(os.path.join(ROOT, other + "_*"))
                     if os.path.isdir(d)), None)
        if odir:
            oidx = raw_index_cached(odir)
            hits = found_in(oidx, value, field)
            if hits:
                return "verified", "found in paper %s raw/: %s" % (other, hits[0])

    # 3. cited an external record
    if EXT.search(source):
        if field in GENE_COLS and not GENE_SOURCES.search(source):
            return "unverifiable", (
                "a V/J call cannot be checked against a sequence record -- %s gives residues, "
                "not a gene assignment. Needs a VDJdb/IMGT/table record that states the gene."
                % (EXT.search(source).group(1)))
        ok, why = check_external(source, value, idx, field)
        if ok is True:
            return "verified", why
        if ok is False:
            return "contradicted", why
        if anywhere:
            return "verified", "external citation; also present locally in " + anywhere[0]
        return "unverifiable", why

    # 4. no locator at all, and not present anywhere
    if field in GENE_COLS:
        return "unverifiable", (
            "gene call with no machine-readable source naming it; not present in %s/raw/" % paper)
    if not idx:
        return "unverifiable", NO_RAW % paper
    return "contradicted", "not present in any file under %s/raw/" % paper


# ------------------------------------------------------------------ external records
_pdb_cache = {}


def pdb_sequences(pdb_id):
    if pdb_id in _pdb_cache:
        return _pdb_cache[pdb_id]
    if not NET:
        return None
    import urllib.request
    seqs = []
    try:
        url = "https://data.rcsb.org/rest/v1/core/entry/%s" % pdb_id
        e = json.load(urllib.request.urlopen(url, timeout=30))
        for i in e["rcsb_entry_container_identifiers"]["polymer_entity_ids"]:
            pe = json.load(urllib.request.urlopen(
                "https://data.rcsb.org/rest/v1/core/polymer_entity/%s/%s" % (pdb_id, i),
                timeout=30))
            seqs.append(pe["entity_poly"]["pdbx_seq_one_letter_code_can"].replace("\n", ""))
    except Exception:
        seqs = None
    _pdb_cache[pdb_id] = seqs
    return seqs


def check_external(source, value, idx, field=None):
    """(True|False|None, why). None = no machine route."""
    s = source
    # A gene call is never confirmable from a structure: skip the PDB route entirely
    # rather than reporting "not in the sequence", which would be true but meaningless.
    if field in GENE_COLS:
        # Only consult a local database copy that the SOURCE actually cites. A clone
        # resolved from IEDB is not falsified by its absence from VDJdb -- they are
        # different databases, and conflating them manufactures contradictions.
        for rel, (txt, toks) in idx.items():
            base = rel.lower()
            cited = ((("vdjdb" in base) and re.search(r"(?i)vdjdb", s))
                     or (("imgt" in base) and re.search(r"(?i)imgt", s)))
            if cited:
                return (value in toks or value in txt), "checked against local %s" % rel
        return None, ("gene call; cited source names no machine-readable gene assignment "
                      "stored in raw/ (a PDB entry gives residues, not a V/J call)")

    if re.search(r"(?i)\b(PDB|RCSB)\b", s):
        ids = [i.upper() for i in PDBID.findall(s)
               if not re.fullmatch(r"\d{4}", i) and i.upper() not in ("CDR3",)]
        tried = []
        for pid in ids[:6]:
            seqs = pdb_sequences(pid)
            if seqs is None:
                continue
            tried.append(pid)
            if any(value in sq for sq in seqs):
                return True, "found in PDB %s polymer entity sequence" % pid
        if tried:
            return False, "not in any polymer entity of PDB %s" % ", ".join(tried)
        return None, "PDB id(s) %s could not be fetched" % (", ".join(ids[:4]) or "none parsed")

    if re.search(r"(?i)VDJdb", s):
        for rel, (txt, toks) in idx.items():
            if "vdjdb" in rel.lower():
                return (value in toks or value in txt,
                        "checked against local %s" % rel)
        return None, "VDJdb cited but no local VDJdb file in raw/"

    return None, "external source with no machine route (%s)" % s[:60]


# ------------------------------------------------------------------ figure task cards
WHAT = {
    "CDR3a": "the CDR3-alpha amino-acid sequence of every labelled TCR",
    "CDR3b": "the CDR3-beta amino-acid sequence of every labelled TCR",
    "Va": "the TRAV gene of every labelled TCR", "Ja": "the TRAJ gene of every labelled TCR",
    "Vb": "the TRBV gene of every labelled TCR", "Jb": "the TRBJ gene of every labelled TCR",
    "Antigen": "every peptide amino-acid sequence shown",
    "MHC": "every HLA or H2 allele shown",
}


def images_for(paper_dir, fig):
    """Images in raw/ plausibly showing this figure: prefer a filename carrying its number."""
    allimg = sorted(glob.glob(os.path.join(paper_dir, "raw", "**", "*.jpg"), recursive=True)
                    + glob.glob(os.path.join(paper_dir, "raw", "**", "*.png"), recursive=True))
    num = re.sub(r"[^0-9]", "", fig)
    supp = fig.lower().startswith("s")
    named = [i for i in allimg
             if re.search(r"(?i)(?:^|[^0-9])%s%s(?:[^0-9]|$)" % ("s" if supp else "", num),
                          os.path.basename(i))]
    return [os.path.relpath(i, ROOT) for i in (named or allimg)]


def emit_cards(jobs):
    os.makedirs(os.path.join(AUDIT, "tasks"), exist_ok=True)
    os.makedirs(os.path.join(AUDIT, "reads"), exist_ok=True)
    for key, (paper, fig, fields, images) in sorted(jobs.items()):
        want = sorted({WHAT.get(f, f) for f in fields})
        path = os.path.join(AUDIT, "tasks", key + ".md")
        open(path, "w", encoding="utf-8").write(
            "# Blind transcription task: %s, figure %s\n\n"
            "Transcribe from the image(s) below. **You are deliberately not being told what "
            "is expected** -- this reading is compared against a recorded value afterwards, and "
            "that comparison is only worth anything if you have not seen it. Do not look for the "
            "answer anywhere else: do not read the paper text, the build script, the workbook or "
            "any CSV in the paper's folder. Report only what the image shows.\n\n"
            "## Images\n%s\n\n## Transcribe\n%s\n\n"
            "## Write your reading to\n`audit/reads/%s.json`\n\n"
            "```json\n{\n  \"by\": \"<model or agent name>\",\n"
            "  \"figure\": \"%s\",\n"
            "  \"tokens\": [\"every string you read, one per entry\"],\n"
            "  \"unreadable\": [\"any label you can see but cannot read confidently\"],\n"
            "  \"notes\": \"anything ambiguous\"\n}\n```\n\n"
            "`tokens` is a flat list -- sequences, gene names, alleles, labels. Put anything you "
            "cannot read confidently in `unreadable` rather than guessing: a guess that happens "
            "to match would silently certify an error.\n"
            % (paper, fig, "\n".join("- `%s`" % i for i in images),
               "\n".join("- " + w for w in want), key, fig))
    return len(jobs)


# ------------------------------------------------------------------------- main
def load_reads():
    out = {}
    for p in glob.glob(os.path.join(AUDIT, "reads", "*.json")):
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        d["tokens"] = set(d.get("tokens", []))
        d.setdefault("by", "unknown")
        out[os.path.basename(p)[:-5]] = d
    return out


def main():
    import pandas as pd

    papers = arg("--papers")
    only = set(papers.split(",")) if papers else None

    # Both halves must accept any three digits. Anchored on a literal `0`, this used to
    # find only 000_*-099_*, so a corpus past 100 papers audited 99 of them and still
    # printed `0 contradicted` and exited 0 -- the loudest possible all-clear from a
    # check that had stopped looking. Matches .gitignore's `[0-9][0-9][0-9]_*`.
    books = sorted(glob.glob(os.path.join(ROOT, "[0-9][0-9][0-9]_*",
                                          "clean_[0-9][0-9][0-9].xlsx")))
    have = {re.search(r"clean_(\d+)\.xlsx", b).group(1) for b in books}
    if only:
        gone = sorted(only - have)
        if gone:
            sys.exit("audit.py: no workbook for paper ID(s): %s\n  found: %s"
                     % (", ".join(gone), ", ".join(sorted(have)) or "none"))
    reads = load_reads()
    results, jobs = [], {}

    for book in books:
        pdir = os.path.dirname(book)
        pid = re.search(r"clean_(\d+)\.xlsx", book).group(1)
        if only and pid not in only:
            continue
        clean = pd.read_excel(book, sheet_name="clean")
        try:
            prov = pd.read_excel(book, sheet_name="provenance")
        except Exception:
            results.append(dict(paper=pid, field="-", value="-", source="-",
                                verdict="contradicted", evidence="no provenance sheet"))
            continue
        print("auditing %s (%d rows) ..." % (os.path.basename(book), len(clean)), flush=True)
        idx = raw_index_cached(pdir)
        if idx:
            print("   raw/: %d readable files" % len(idx), flush=True)
        else:
            print("   raw/: EMPTY OR ABSENT -- local checks downgraded to `unverifiable`, "
                  "not `contradicted`. See SETUP.md.", flush=True)

        seen = set()
        # The two sheets are joined on positional index below. A provenance sheet of a
        # different length yields NaN keys, and groupby drops those by default -- rows
        # would vanish from the audit instead of failing it. lib/provenance.py makes the
        # same check at build time (C12); the independent check cannot afford to skip it.
        if len(prov) != len(clean):
            results.append(dict(paper=pid, field="-", value="-", source="-",
                                verdict="contradicted",
                                evidence="provenance has %d rows, clean has %d; they are "
                                         "aligned positionally and must match 1:1"
                                         % (len(prov), len(clean))))
            continue
        for col in SCHEMA:
            scol = col + "_source"
            if col not in clean.columns:
                # A column missing from `clean` is a finding about this paper, not a
                # reason to abort the whole corpus run with a KeyError.
                results.append(dict(paper=pid, field=col, value="-", source="-",
                                    verdict="contradicted",
                                    evidence="clean sheet has no %s column" % col))
                continue
            if scol not in prov.columns:
                results.append(dict(paper=pid, field=col, value="-", source="-",
                                    verdict="contradicted", evidence="missing " + scol))
                continue
            pairs = pd.DataFrame({"v": clean[col].astype(str), "s": prov[scol].astype(str)})
            for (val, src), grp in pairs.groupby(["v", "s"], sort=False):
                if (col, val, src) in seen:
                    continue
                seen.add((col, val, src))
                v, why = classify(col, val, src, idx, reads, pid)
                # Queue a blind transcription only when the verdict actually hangs on the
                # figure. A source that merely cites a figure for the PAIRING, while the
                # value itself is printed in Methods, needs no vision read.
                if v == "unverifiable" and "no blind transcription yet" in why:
                    fig = FIG.findall(src)[0]
                    key = "%s_fig%s" % (pid, fig.lower())
                    imgs = images_for(pdir, fig)
                    if imgs:
                        want = jobs.setdefault(key, (pid, fig, set(), imgs))
                        want[2].add(col)
                    else:
                        v, why = "unverifiable", (
                            "figure %s is cited but no image of it is stored in %s/raw/ -- "
                            "re-acquire the figure to make this verifiable" % (fig, pid))
                results.append(dict(paper=pid, field=col, value=val, source=src,
                                    verdict=v, evidence=why, rows=int(len(grp))))

    if "--figures" in sys.argv:
        n = emit_cards(jobs)
        print("\nwrote %d blind task card(s) to audit/tasks/" % n)

    report = write_report(results, jobs, only)
    bad = [r for r in results if r["verdict"] == "contradicted"]
    tally = {}
    for r in results:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("\n" + "  ".join("%s=%d" % kv for kv in sorted(tally.items())))
    print("-> %s" % report)
    if bad:
        print("\nCONTRADICTED (%d):" % len(bad))
        for r in bad[:20]:
            print("  %s %s=%r  %s" % (r["paper"], r["field"], r["value"], r["evidence"][:90]))
        return 1
    return 0


def write_report(results, jobs, only=None):
    import time
    from collections import Counter
    by_paper = {}
    for r in results:
        by_paper.setdefault(r["paper"], []).append(r)

    L = ["# AUDIT — are the recorded sources real?",
         "",
         ("**PARTIAL RUN — only paper(s) %s. This is not a corpus report; re-run "
          "`audit.py` with no `--papers` to write the full AUDIT.md.**\n"
          % ", ".join(sorted(only))) if only else "",
         "Generated by `audit.py` on %s. One verdict per distinct "
         "`(field, value, source)`; rows sharing a source are audited once and the `rows` "
         "column says how many they cover." % time.strftime("%Y-%m-%d"),
         "",
         "`verified` found where the source says · `mislocated` real but mis-cited · "
         "`judgement` an annotation decision, not a quotable string · `unverifiable` no machine "
         "route · **`contradicted`** not where it is claimed to be.",
         ""]
    tot = Counter(r["verdict"] for r in results)
    L += ["## Corpus", "", "| verdict | checks |", "|---|---|"]
    L += ["| `%s` | %d |" % (k, v) for k, v in sorted(tot.items())]
    L += ["", "**%d contradicted.**" % tot.get("contradicted", 0), ""]

    for pid in sorted(by_paper):
        rs = by_paper[pid]
        c = Counter(r["verdict"] for r in rs)
        L += ["## Paper %s" % pid, "",
              "%d checks covering %d rows — %s" % (
                  len(rs), sum(r.get("rows", 0) for r in rs),
                  ", ".join("%s %d" % kv for kv in sorted(c.items()))), ""]
        odd = [r for r in rs if r["verdict"] not in ("verified", "judgement")]
        if odd:
            L += ["| field | value | verdict | evidence |", "|---|---|---|---|"]
            for r in odd:
                L.append("| `%s` | `%s` | **%s** | %s |" % (
                    r["field"], str(r["value"])[:40], r["verdict"],
                    r["evidence"].replace("|", "\\|")[:150]))
            L.append("")
    if jobs:
        L += ["## Figure transcription tasks", "",
              "Blind re-reads required; the task cards never contain the recorded value.", ""]
        L += ["- `audit/tasks/%s.md` — paper %s, figure %s, for %s" %
              (k, v[0], v[1], ", ".join(sorted(v[2]))) for k, v in sorted(jobs.items())]
        L.append("")
    # A --papers run covers only those papers, so it goes to its own file. Writing it to
    # AUDIT.md would silently delete every other paper's section from the full report.
    name = "AUDIT_partial.md" if only else "AUDIT.md"
    open(os.path.join(ROOT, name), "w", encoding="utf-8").write("\n".join(L))
    return name


if __name__ == "__main__":
    sys.exit(main())
