#!/usr/bin/env python3
"""Gates A and B of the journal screen: harvest a journal, then probe it mechanically.

Zero model tokens. One PMC XML fetch per paper supplies everything: the full body, the
supplementary file inventory, the data-availability statement and the figure captions.

Standard library only -- no pandas, no venv needed.

    python3 journals/probe.py J12                        # one journal, from journals/journals.md
    python3 journals/probe.py --pmids 12345678,23456789  # control run on an explicit list
    python3 journals/probe.py --pmids ... --out DIR      # ... written somewhere else
    python3 journals/probe.py --help

Writes into journals/<J##>_<Abbrev>/:
    xml/<PMID>.xml     cached PMC XML (gitignored) -- delete to force a re-fetch
    cards/<PMID>.md    the mechanical card a screening agent reads
    candidates.tsv     append-only ledger, one row per PMID ever seen
    sweep.md           run log: query, window, counts at each gate

Resumable: a PMID already in candidates.tsv is skipped. Set NCBI_API_KEY to raise the
NCBI rate limit from 3/s to 10/s.

PMID -> PMCID goes through the idconv service, NEVER through elink: elink's multi-id
response does not reliably pair linksets back to the ids you sent, and silently returns
one article's PMCID for another's PMID. See playbook/fetching.md.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA   = {"User-Agent": "web_scraper-probe/1.0 (TCR-pMHC dataset curation)"}
KEY  = os.environ.get("NCBI_API_KEY", "")
GAP  = 0.11 if KEY else 0.36          # NCBI allows 10/s with a key, 3/s without
_last = [0.0]

# The harvest query. Kept identical to the one recorded in journals/journals.md --
# broad on purpose: the probe rejects, not the search.
CORE = ('("T cell receptor"[tiab] OR TCR[tiab]) AND '
        '(epitope[tiab] OR peptide[tiab] OR pMHC[tiab] OR HLA[tiab] OR antigen[tiab]) '
        'NOT review[pt]')

AA = "ACDEFGHIKLMNPQRSTVWY"

# All-caps English and biology words that are 8-11 letters over the amino-acid alphabet.
# Without this the peptide-token count drowns in false positives -- the failure mode
# screen-corpus explicitly warns about.
STOP = set("""ACTIVATED ACTIVATES ACTIVATE CANDIDATE CANDIDATES SIGNIFICANT SEQUENCING
SEQUENCES SEQUENCE SPECIFIC SPECIFICITY BINDING DETECTED BETWEEN BECAUSE BASELINE
MATERIALS MATERIAL METHODS ANALYSIS ANALYSES BIOLOGICAL CHEMICAL CLINICAL CONTAINS
CONTAINING BUFFERED FOLLOWING BLOCKING STAINING BLOCKED SELECTED SELECTION BLOTTING
CYTOMETRY PEPTIDE PEPTIDES PROTEIN PROTEINS ANTIGEN ANTIGENS EPITOPE EPITOPES
TRANSFECT ELEVATED ENRICHED ENRICHMENT INCLUDING INCUBATED INDICATED INHIBITED
GENERATED GENETIC IDENTICAL INTERNAL ISOLATED LABELLED LABELED MEASURED MEDIATED
NEGATIVE PRESENTED POSITIVE POTENTIAL PREDICTED PRESENCE PRIMARY REPORTED REPLICATE
REPLICATES RESPONSE RESPONSES SAMPLING SCANNING SCREENING SEPARATE SIMILAR SPLENIC
STATISTICAL STIMULATED SYNTHETIC THERAPEUTIC TREATMENT VALIDATED VARIANTS CONTROLS
COMPARISON CALCULATED COLLECTED COMPLETE CONFIRMED DEPLETION DIFFERENT DILUTION
DETECTION DECREASED INCREASED REGRESSION RESISTANT SENSITIVE SIGNALING SIGNALLING
SPECTRAL STANDARD STRATEGY STRUCTURE SUPPLEMENT TARGETING TECHNICAL THRESHOLD
AVAILABLE ADDITIONAL ASSESSMENT ASSOCIATED ALIGNMENT AMPLIFIED ANTIBODIES ANTIBODY
APPLIED APPROACH ARTIFICIAL ATTACHED AVERAGED CAPTURED CHARACTER CLASSIFIED CLEAVAGE
COLLAGEN CONSTANT CONSTRUCT CONVERTED CORRECTED CRITICAL CULTURED DEFICIENT DELIVERED
DEPENDENT DERIVED DESIGNED DIGESTED DISEASE DISTINCT DOMINANT EFFICIENT ELIMINATE
ENGINEER ESTIMATED EVALUATED EXPANDED EXPRESSED EXTRACTED FILTERED FRACTION FRAGMENT
FREQUENCY FUNCTIONAL HIGHLIGHT IDENTIFIED IMMEDIATE IMPAIRED IMPLIES INDICATES
INFECTED INHERENT INTEGRATED INTENSITY INTERFACE MAGNITUDE MAINTAIN MALIGNANT
MECHANISM MICROSCOPE MITIGATED MODIFIED MONITORED MUTATIONS NORMALISED NORMALIZED
OPTIMISED OPTIMIZED PARALLEL PARAMETER PATHOGENIC PERFORMED PERIPHERAL PHENOTYPE
PLATFORM POPULATION PRACTICAL PRECISION PREPARED PRESENTING PREVALENT PROCESSED
PROMINENT PROVIDED PURIFIED QUANTIFIED RECEPTOR RECEPTORS RECOGNISE RECOGNIZE
RECOMBINANT REFERENCE REGULATED RELEVANT REMAINING REPEATED REPRESENT RESIDUAL
RESOLVED RESTRICTED RETAINED SATELLITE SATURATED SCAFFOLD SECRETED SEGREGATE
SELECTIVE SEPARATED SIGNATURE SIMULATED SOLUTION SPLITTING STIMULATE SUCCESSFUL
SUFFICIENT SUPERNATANT SURFACE SURVIVAL SUSTAINED THERAPIES TRANSFER TRANSLATED
TRIPLICATE TRUNCATED VACCINATED VALIDATION VARIATION MATCHMAKERS MATCHMAKER
THERAPEUTICS DIAGNOSTIC CHARACTERS SCAFFOLDS SIMILARITY STRUCTURAL SPECIFICALLY
HIGHLIGHTS INTERFACES SELECTIVITY SENSITIVITY STATISTICS SUBSTRATE CYTOTOXIC
CRYSTALLINE DIFFRACTION INHIBITORS MITIGATION PRECURSORS REFINEMENT""".split())

CLONES = ["1G4", "DMF5", "JM22", "LC13", "A6 TCR", "MART-1", "NY-ESO", "MAGE-A3",
          "DMF4", "868 TCR", "ILA1", "TCR1G4", "3QEQ"]


# ---------------------------------------------------------------- http helpers
def _wait():
    d = GAP - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)
    _last[0] = time.time()


def fetch(url, tries=3, timeout=60):
    for a in range(tries):
        _wait()
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout
            ).read().decode("utf-8", "replace")
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(1.5 * (a + 1))


def eutils(tool, **kw):
    if KEY:
        kw["api_key"] = KEY
    return ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/%s.fcgi?" % tool
            + urllib.parse.urlencode(kw))


# ---------------------------------------------------------------- gate A
def harvest(ta, win):
    term = '"%s"[ta] AND %s AND %s[dp]' % (ta, CORE, win)
    d = json.loads(fetch(eutils("esearch", db="pubmed", retmode="json",
                                retmax=2000, term=term)))
    return term, d["esearchresult"]["idlist"]


def summaries(pmids):
    out = {}
    for i in range(0, len(pmids), 200):
        chunk = pmids[i:i + 200]
        d = json.loads(fetch(eutils("esummary", db="pubmed", retmode="json",
                                    id=",".join(chunk))))["result"]
        for p in chunk:
            r = d.get(p)
            if not r:
                continue
            au = r.get("sortfirstauthor") or ""
            if not au and r.get("authors"):
                au = r["authors"][0].get("name", "")
            out[p] = {"title": r.get("title", "").rstrip("."),
                      "author": au.split()[0] if au else "?",
                      "year": (r.get("pubdate") or "????")[:4],
                      "types": [t for t in r.get("pubtype", [])]}
    return out


def to_pmcid(pmids):
    """PMID -> PMCID via idconv. Never elink; see the module docstring."""
    out = {}
    for i in range(0, len(pmids), 200):
        chunk = pmids[i:i + 200]
        try:
            recs = json.loads(fetch(
                "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?ids=%s&format=json"
                % ",".join(chunk)))["records"]
        except Exception:
            recs = []
        for r in recs:
            if r.get("pmcid"):
                out[str(r.get("pmid"))] = r["pmcid"]
    return out


SKIP_TYPES = {"Review", "Editorial", "Comment", "Published Erratum", "Retraction of Publication",
              "Retracted Publication", "News", "Biography", "Historical Article",
              "Systematic Review", "Meta-Analysis", "Preprint"}


# ---------------------------------------------------------------- gate B
def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def parse_xml(x):
    f = {}
    blocks = re.findall(r"<supplementary-material.*?(?:</supplementary-material>|/>)", x, re.S)
    f["supp"] = sorted(set(re.findall(r'xlink:href="([^"]+)"', "".join(blocks))))
    f["supp_titles"] = [strip_tags(b)[:120] for b in blocks]

    ext = lambda names, es: [n for n in names if n.lower().rsplit(".", 1)[-1] in es]
    f["supp_machine"] = ext(f["supp"], {"xlsx", "xls", "csv", "tsv", "txt", "zip"})
    f["supp_doc"] = ext(f["supp"], {"pdf", "docx", "doc"})

    # Publishers put this in three different places. Missing any one of them makes the card
    # say "(no statement found)" on a paper that has one -- observed on 38744947 (Li).
    da = []
    for tag in ("sec", "notes"):
        da += re.findall(r"(?is)<%s[^>]*(?:-type=\"[^\"]*(?:data-availability|data-access)[^\"]*\""
                         r"|>\s*<title>[^<]*(?:data (?:and code )?availability|accession"
                         r"|availability of data)[^<]*</title>).*?</%s>" % (tag, tag), x)
    txt = " | ".join(strip_tags(d) for d in da)
    f["data_avail"] = (txt[:900] + ("..." if len(txt) > 900 else "")) if txt else ""

    caps = [strip_tags(c) for c in re.findall(r"<caption>.*?</caption>", x, re.S)]
    f["n_figs"] = len(re.findall(r"<fig\b", x))
    f["caps_seq"] = [c[:200] for c in caps if re.search(
        r"(?i)CDR3|clonotype|TCR sequence|TCRα|TCRβ|V\(D\)J|sequence alignment", c)][:6]
    f["caps_pep"] = [c[:200] for c in caps if re.search(
        r"(?i)peptide|epitope|library|screen|antigen|mimotope", c)][:6]

    body = strip_tags(re.sub(r"(?s)<ref-list.*?</ref-list>", " ", x))
    f["body_len"] = len(body)
    f["trav"] = len(re.findall(r"\bTR[AB][VJ]\d", body))
    f["cdr3_like"] = len(set(re.findall(r"\bC[%s]{6,20}[FW]\b" % AA, body)))
    f["hla"] = len(set(re.findall(r"\bHLA-[A-Z]{1,4}\d?\*\d\d:?\d*", body)))
    f["cdr3_word"] = len(re.findall(r"(?i)\bCDR3\b", body))
    f["clones"] = sorted({c for c in CLONES if c.lower() in body.lower()})

    toks = {t for t in re.findall(r"\b[%s]{8,11}\b" % AA, body)
            if t not in STOP and not t.isdigit()}
    f["pep_like"] = len(toks)
    f["pep_sample"] = sorted(toks)[:8]

    acc = {}
    for name, pat in [("GEO", r"\bGSE\d{4,7}\b"), ("SRA", r"\b[SE]RP\d{6,}\b"),
                      # a PDB id is 4 chars starting with a digit -- but so is a year, and "PDB ID:" prose
                      # sits near citation years. Require at least one letter; observed 2007/2024
                      # reported as structures on 39672953.
                      ("PDB", r"(?i)\b(?:PDB|RCSB)[^.]{0,30}?\b([0-9](?![0-9]{3}\b)[A-Za-z0-9]{3})\b"),
                      ("dbGaP", r"\bphs\d{6}\b"), ("Zenodo", r"(?i)zenodo\.\d{4,}|10\.5281/zenodo\.\d+"),
                      ("Dryad", r"(?i)10\.5061/dryad\.\w+"), ("GitHub", r"(?i)github\.com/[\w.-]+/[\w.-]+"),
                      ("Figshare", r"(?i)10\.6084/m9\.figshare\.\d+")]:
        m = sorted(set(re.findall(pat, x)))
        if m:
            # keep all of them -- a truncated list silently hides the one that matters
            acc[name] = m if len(m) <= 12 else m[:12] + ["(+%d more)" % (len(m) - 12)]
    f["accessions"] = acc
    return f


def score(f, has_pmc):
    """Encodes screen-corpus's asymmetric rule: peptides must come FROM the paper
    (hard), TCR identity only has to be RESOLVABLE (soft)."""
    p, t, why = 0, 0, []
    if not f:
        # no PMC body to read -- "no evidence" must never collapse into "no access"
        return 0, 0, "unclear", ["no PMC full text -- cannot see; never rejected on absence"]

    if f["supp_machine"]:
        p += 3; why.append("+3 machine-readable supplement(s): %d" % len(f["supp_machine"]))
        if len(f["supp_machine"]) >= 3:
            p += 2; why.append("+2 three or more of them")
    if f["caps_pep"]:
        p += 3; why.append("+3 caption promises peptide/epitope content")
    if f["pep_like"] >= 10:
        p += 2; why.append("+2 peptide-like tokens in body: %d" % f["pep_like"])
    elif f["pep_like"] >= 3:
        p += 1; why.append("+1 peptide-like tokens in body: %d" % f["pep_like"])
    if f["accessions"]:
        p += 2; why.append("+2 data availability names %s" % ", ".join(f["accessions"]))

    if f["trav"] >= 2:
        t += 3; why.append("+3 TRAV/TRBV tokens: %d" % f["trav"])
    if f["cdr3_like"] >= 2:
        t += 3; why.append("+3 CDR3-like strings: %d" % f["cdr3_like"])
    if f["clones"]:
        t += 2; why.append("+2 named clone(s): %s" % ", ".join(f["clones"]))
    if "PDB" in f["accessions"]:
        t += 2; why.append("+2 PDB accession -> paired chains resolvable")
    if f["caps_seq"]:
        t += 1; why.append("+1 caption promises sequences")
    if f["cdr3_word"]:
        t += 1; why.append('+1 the word "CDR3" appears')

    if f and not (f["trav"] or f["cdr3_like"] or f["cdr3_word"]):
        why.append("!! NO TCR SEQUENCE EVIDENCE: zero TRAV/TRBV, zero CDR3-like, zero \"CDR3\". "
                   "Any clone names above may be citations, not this paper's own receptors -- "
                   "confirm the paper identifies receptors of its own before passing it")

    if not has_pmc:
        return p, t, "unclear", why + ["no PMC full text -- cannot see; never rejected on absence"]
    if p >= 3 and t >= 2:
        v = "likely"
    elif p >= 3:
        v = "unclear"          # peptides are there; TCR may still be resolvable externally
    else:
        v = "unlikely"
    return p, t, v, why


CARD = """# {pmid} -- {author} {year}{pmcid_s}
{title}

**verdict: {verdict}**  (peptide {p}, tcr {t})   figs={n_figs}  body={body_len}B

## score
{why}

## supplementary files ({n_supp})
{supp}

## data availability
{da}

## accessions
{acc}

## captions promising sequences
{caps_seq}

## captions promising peptides/epitopes
{caps_pep}

## body signals
TRAV/TRBV={trav}  CDR3-like={cdr3_like}  "CDR3"x{cdr3_word}  HLA-alleles={hla}
peptide-like tokens={pep_like}  e.g. {pep_sample}
clones: {clones}
"""


def bullets(xs, empty="(none)"):
    return "\n".join("- " + str(x) for x in xs) if xs else empty


def write_card(d, pmid, meta, f, p, t, v, why):
    txt = CARD.format(
        pmid=pmid, author=meta.get("author", "?"), year=meta.get("year", "????"),
        pmcid_s=(" · " + meta["pmcid"]) if meta.get("pmcid") else " · no PMC",
        title=meta.get("title", ""), verdict=v.upper(), p=p, t=t,
        n_figs=f.get("n_figs", 0), body_len=f.get("body_len", 0),
        why=bullets(why), n_supp=len(f.get("supp", [])),
        supp=bullets(f.get("supp", [])), da=f.get("data_avail") or "(no statement found)",
        acc=bullets(["%s: %s" % (k, ", ".join(v2)) for k, v2 in f.get("accessions", {}).items()]),
        caps_seq=bullets(f.get("caps_seq", [])), caps_pep=bullets(f.get("caps_pep", [])),
        trav=f.get("trav", 0), cdr3_like=f.get("cdr3_like", 0), cdr3_word=f.get("cdr3_word", 0),
        hla=f.get("hla", 0), pep_like=f.get("pep_like", 0),
        pep_sample=", ".join(f.get("pep_sample", [])) or "-",
        clones=", ".join(f.get("clones", [])) or "-")
    open(os.path.join(d, "cards", pmid + ".md"), "w", encoding="utf-8").write(txt)


COLS = ["pmid", "pmcid", "author", "year", "verdict", "peptide", "tcr",
        "supp_machine", "supp_doc", "trav", "cdr3_like", "pep_like", "accessions", "title"]


def run(pmids, outdir, meta_by_pmid, label):
    for sub in ("xml", "cards"):
        os.makedirs(os.path.join(outdir, sub), exist_ok=True)
    led = os.path.join(outdir, "candidates.tsv")
    seen = set()
    if os.path.exists(led):
        for i, ln in enumerate(open(led, encoding="utf-8")):
            if i:
                seen.add(ln.split("\t")[0])
    else:
        open(led, "w", encoding="utf-8").write("\t".join(COLS) + "\n")

    todo = [p for p in pmids if p not in seen]
    print("  %s: %d PMIDs, %d already done, %d to probe" % (label, len(pmids), len(seen), len(todo)))
    pmc = to_pmcid(todo) if todo else {}
    tally = {}
    with open(led, "a", encoding="utf-8") as fh:
        for n, pmid in enumerate(todo, 1):
            meta = dict(meta_by_pmid.get(pmid, {}))
            meta["pmcid"] = pmc.get(pmid, "")
            f, has = {}, bool(meta["pmcid"])
            if has:
                cache = os.path.join(outdir, "xml", pmid + ".xml")
                if os.path.exists(cache):
                    x = open(cache, encoding="utf-8").read()
                else:
                    try:
                        x = fetch(eutils("efetch", db="pmc", retmode="xml", id=meta["pmcid"][3:]))
                        open(cache, "w", encoding="utf-8").write(x)
                    except Exception as e:
                        x, has = "", False
                if has and "<body" not in x:
                    has = False          # abstract-only PMC record
                if has:
                    f = parse_xml(x)
            p, t, v, why = score(f, has)
            tally[v] = tally.get(v, 0) + 1
            write_card(outdir, pmid, meta, f, p, t, v, why)
            fh.write("\t".join(str(c) for c in [
                pmid, meta["pmcid"], meta.get("author", "?"), meta.get("year", "?"), v, p, t,
                len(f.get("supp_machine", [])), len(f.get("supp_doc", [])), f.get("trav", 0),
                f.get("cdr3_like", 0), f.get("pep_like", 0),
                ";".join(f.get("accessions", {})), meta.get("title", "").replace("\t", " ")[:150],
            ]) + "\n")
            fh.flush()
            print("    [%3d/%3d] %s %-10s %-9s p=%-2d t=%-2d %s" % (
                n, len(todo), pmid, meta.get("author", "?")[:10], v, p, t,
                meta.get("pmcid", "") or "no-pmc"))
    return tally


def journal_row(jid):
    md = open(os.path.join(HERE, "journals.md"), encoding="utf-8").read()
    m = re.search(r"^\|\s*%s\s*\|([^|]*)\|([^|]*)\|([^|]*)\|" % jid, md, re.M)
    if not m:
        sys.exit("no row for %s in journals/journals.md" % jid)
    name, ta, win = (g.strip().strip("`") for g in m.groups())
    yrs = re.findall(r"\d{4}", win)
    return name, ta, "%s/01/01:%s/12/31" % (yrs[0], yrs[-1]), win


def arg(argv, flag, default=None):
    """Value of a --flag, or `default`. Exits with usage if the value is missing."""
    if flag not in argv:
        return default
    i = argv.index(flag) + 1
    if i >= len(argv) or argv[i].startswith("--"):
        sys.exit("probe.py: %s needs a value\n%s" % (flag, __doc__))
    return argv[i]


def main(argv):
    if "--help" in argv or "-h" in argv:
        sys.exit(__doc__)
    for a in argv:
        if a.startswith("--") and a not in ("--pmids", "--out", "--help"):
            sys.exit("probe.py: unknown option %s\n%s" % (a, __doc__))
    if "--out" in argv and "--pmids" not in argv:
        sys.exit("probe.py: --out only applies to a --pmids control run; in J## mode the\n"
                 "output directory is derived from the journal abbreviation.\n%s" % __doc__)

    if "--pmids" in argv:
        pmids = arg(argv, "--pmids").split(",")
        out = arg(argv, "--out", os.path.join(HERE, "_control"))
        os.makedirs(out, exist_ok=True)
        print("control run -> %s" % out)
        tally = run(pmids, out, summaries(pmids), "control")
        print("\n  " + "  ".join("%s=%d" % kv for kv in sorted(tally.items())))
        return

    if not argv or not re.fullmatch(r"J\d\d", argv[0]):
        sys.exit(__doc__)
    jid = argv[0]
    name, ta, win, win_h = journal_row(jid)
    outdir = os.path.join(HERE, "%s_%s" % (jid, re.sub(r"\s+", "_", ta.replace(".", ""))))
    print("%s  %s  [ta]=%s  window=%s" % (jid, name, ta, win_h))

    term, pmids = harvest(ta, win)
    meta = summaries(pmids)
    kept, dropped = [], []
    for p in pmids:
        if set(meta.get(p, {}).get("types", [])) & SKIP_TYPES:
            dropped.append(p)
        else:
            kept.append(p)
    print("  gate A: %d hits, %d dropped by type, %d kept" % (len(pmids), len(dropped), len(kept)))

    tally = run(kept, outdir, meta, jid)

    tsv = os.path.join(outdir, "candidates.tsv")
    allv = {}
    for i, ln in enumerate(open(tsv, encoding="utf-8")):
        if i:
            allv[ln.split("\t")[4]] = allv.get(ln.split("\t")[4], 0) + 1
    # APPEND, never overwrite: screen-journal has agents append their wave logs to this
    # same file, and a re-probe used to wipe them.
    sweep = os.path.join(outdir, "sweep.md")
    if not os.path.exists(sweep):
        open(sweep, "w", encoding="utf-8").write(
            "# %s %s -- sweep log\n\n- window: %s\n- `[ta]`: `%s`\n\n## query\n\n```\n%s\n```\n"
            % (jid, name, win_h, ta, term))
    open(sweep, "a", encoding="utf-8").write(
        "\n## probe run -- %s\n\n| gate | n |\n|---|---|\n"
        "| A harvest | %d |\n| A dropped by publication type | %d |\n| B probed | %d |\n%s\n"
        "Next: run `procedures/screen-journal.md` on the top unscreened `likely`/`unclear` rows of "
        "`candidates.tsv` (wave of ~20).\n"
        % (time.strftime("%Y-%m-%d"), len(pmids), len(dropped), sum(allv.values()),
           "".join("| B %s | %d |\n" % (k, v) for k, v in sorted(allv.items()))))
    print("\n  totals: " + "  ".join("%s=%d" % kv for kv in sorted(allv.items())))
    print("  -> %s" % outdir)


if __name__ == "__main__":
    main(sys.argv[1:])
