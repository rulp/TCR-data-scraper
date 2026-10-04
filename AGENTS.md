# data_finder — building TCR–pMHC training data from published papers

Extract TCR-binding datasets from published papers into one common format, for training a
TCR-specificity model.

**This file is the entry point for any AI agent working in this repo**, whichever one you are.
Everything it routes to is an ordinary markdown file at an ordinary path — nothing here depends on
a particular tool's skill, plugin or memory mechanism. `README.md` is the same pipeline explained
for people; `SETUP.md` is how to run it on a fresh machine.

## Routing — load only what the task needs

| You were given | Read | Which gives you |
|---|---|---|
| a PMID, PMCID, DOI, or a queued paper | `procedures/extract-paper.md` | the six-step extraction procedure |
| "find papers that…", a literature sweep, corpus building | `procedures/screen-corpus.md` | the funnel, gate rules and search terms |
| a `J##`, or "screen journal X" | `procedures/screen-journal.md` | the three gates, the pass rule, the locator template |
| verifying that recorded sources are real | `procedures/audit-provenance.md` | `audit.py`, the blind figure protocol, how to investigate |
| "which journal is next", a window question | `journals/journals.md` | the 40-journal master list, shared across machines, with its sweep state |
| **what the output must look like** | `docs/schema.md` | the ten columns, the conventions, the provenance vocabulary |
| a judgement call mid-extraction | `playbook/judgement.md` | mandatory for every extraction |
| validating output before writing it | `playbook/checks.md` | the checks, as paste-in assertions |
| sequences only visible in a figure | `playbook/figures.md` | |
| trouble acquiring files, or tooling trouble | `playbook/fetching.md` | |
| train/test splitting | `docs/evaluation.md` | |
| how the journal list was built, and why | `journals/method.md` | read-once provenance; not needed to sweep |

`REPORT.md` is the index mapping every `§N` citation to its playbook file. Section numbers are
permanent and never reused, so citations in build scripts and in shipped `source_notes` sheets
keep resolving. **`§N` always means a `REPORT.md` section** — `docs/` deliberately uses named
headings rather than numbers so it cannot collide with that namespace.

**A PMID means extract, never screen.** Do not run literature searches, chase companion papers,
or add rows to `paper_source.md` beyond the paper asked for. Following a citation *out of* the
paper in hand — to recover a TCR sequence it only names — is extraction work and is in scope.

## Layout

```
web_scraper/
├── AGENTS.md                this file — identity, indexing, routing. Start here.
├── README.md                the same pipeline for PEOPLE — keep it non-technical
├── SETUP.md                 running it on another machine
├── requirements.txt         pandas · openpyxl · pypdf, and nothing else
├── paper_source.md          the extraction queue — one row per paper, see below.
│                            PER-MACHINE and gitignored; seeded from docs/templates/
├── REPORT.md                index into playbook/
├── procedures/              the four procedures: extract-paper · screen-journal ·
│                            screen-corpus · audit-provenance
├── playbook/                judgement.md · checks.md · figures.md · fetching.md
├── docs/                    schema.md — the output contract · evaluation.md
├── journals/                journals.md — the harvest axis, plus one folder per swept journal
├── lib/provenance.py        the one provenance schema every build script emits
├── audit.py · AUDIT.md      the independent source audit and its report
├── tools/                   check_docs.py · init_workspace.py · export_index.py
├── .claude/skills/          four pointer stubs, for Claude Code only — delete it and
│                            nothing breaks; the procedures live in procedures/
└── <ID>_<FirstAuthor>/      one folder per paper — everything that paper produces
    ├── <ID>_<FirstAuthor>.py    its build script: raw/ → clean_<ID>
    ├── raw/                     the acquired inputs
    └── clean_<ID>.xlsx          plus its clean_<ID>_* companions
```

## Indexing: every artifact carries the paper's ID

**This index is per-machine.** Each computer runs its own copy of this repo with its own
`paper_source.md`, both starting at `001`, and neither is in git — so a local `ID` is meaningful
*here* and nowhere else. The key that crosses machines is the **PMID**: `lib/provenance.py`
requires `source_pmid` on every row for exactly this reason, and a shared tracking sheet keyed on
PMID is what stops two machines extracting the same paper. `SETUP.md` has the protocol.

`paper_source.md` is the index for this machine. Each paper gets a zero-padded three-digit **`ID`** when its row
is appended, and that ID names everything the paper produces:

```
paper_source.md row     | <ID> | <PMID> | <FirstAuthor> | …
folder                    <ID>_<FirstAuthor>/
  build script            <ID>_<FirstAuthor>/<ID>_<FirstAuthor>.py
  raw inputs              <ID>_<FirstAuthor>/raw/
  schema file             <ID>_<FirstAuthor>/clean_<ID>.xlsx    sheets: clean, provenance, source_notes
  provenance              <ID>_<FirstAuthor>/clean_<ID>_provenance.csv
  companion files         <ID>_<FirstAuthor>/clean_<ID>_<what>.csv
```

Rules, all of them about not breaking paths that already exist:

- **A paper's folder holds everything that paper produces, build script included.** Nothing
  belonging to one paper sits at the repo root. Write the script so its paths resolve relative
  to its own location, not to the working directory:

  ```python
  HERE = os.path.dirname(os.path.abspath(__file__))
  RAW  = os.path.join(HERE, "raw")
  OUT  = HERE
  ```

  so `python <ID>_<FirstAuthor>/<ID>_<FirstAuthor>.py` works from the repo root and from
  anywhere else.
- **IDs are assigned on append and are permanent.** Add new papers at the end of the table and
  take the next free number. Never renumber, never reorder, never reuse. A dropped paper keeps
  its row and its number with `Status = dropped`.
- **`<FirstAuthor>` is the FIRST author's surname**, never the last author's. It is a human
  label only; the ID is what makes the name unique, so two papers by the same first author need
  no suffix.
- **Three digits from the start** (`001`, not `1`) so the directory listing sorts in queue order
  past 100 papers.
- A paper's own files refer to it by ID, not by position: `clean_<ID>`, never `clean_<N-th>`.

`clean_<ID>` in any document means "the schema file for that paper" — on disk, `clean_007.xlsx`
for paper 007.

## Invariants

True in every mode, and costly to violate. `docs/schema.md` is the full contract; these five are
here because they must stay loaded whatever the task:

- **`Va`, `Ja` and `CDR3a` are mandatory.** An extraction that cannot supply the α chain is not
  worth producing. A paper that looks β-chain-only is a signal to dig harder, not to emit `NA`.
- **Dedupe on at least (`CDR3a`, `CDR3b`, `Antigen`).** Neither chain alone is a unique TCR key:
  engineered variants share an α while colliding in β, and public clonotypes share a β — or an
  α — across genuinely different receptors.
- **Never emit a non-amino-acid string in a sequence column.** Published positive sets contain
  control labels and masked placeholders; resolve them or drop them, never pass them through.
  The alphabet check alone is not enough — a CDR3 must also begin with the conserved cysteine.
- **`pMHC_species` records where the peptide actually comes from.** If it is not human, do not
  label it `Human`. Viral, bacterial and synthetic-library peptides each get their own value,
  decided once per peptide *source* and never per peptide — see `playbook/judgement.md` §10.
- **Anything read off a figure or a main-paper table is extrapolated** and must say so, citing
  its exact location. Every row records this per field in the workbook's `provenance` sheet —
  built by `lib/provenance.py`, checked by `playbook/checks.md` **C12**.

## Working in this repo

- **Run Python through `uv run --with pandas --with openpyxl --with pypdf python <script>`**, or
  activate a venv built from `requirements.txt`. `journals/probe.py` is standard-library only and
  runs under a bare `python3`. `SETUP.md` has both paths.
- **`journals/journals.md` is the one tracked file you edit.** It is the master journal list,
  identical on every machine, and it carries each journal's sweep `Status`, `Machine` and
  `Last swept`. Claim a journal by marking its row and pushing *before* sweeping. Edit only that
  row's cells and never re-align the table; its Rules section says why.
- **The workspace is not in git** — `paper_source.md`, the paper folders, the journal sweep
  folders and `AUDIT.md`. Git carries the toolkit only, so a pull never conflicts with work in
  progress, and it is also not a backup: that is the Drive mirror's job. Each build script's
  module docstring records the `curl` commands that rebuilt its inputs; files needing a human are
  listed in each journal's `NEEDS_HUMAN.md`.
- **Never edit a `clean_*.xlsx` by hand.** It is the output of a build script; change the script
  and re-run, so the change is reproducible and the assertions still fire.
- **After moving or renaming any doc, run `python3 tools/check_docs.py`.** It fails on a cited
  path that does not exist, which is how a routing table rots.

## After every batch, update `REPORT.md`

`REPORT.md` is the troubleshooting memory of this project, and it only works if it grows. When a
batch of papers is finished, add a section for **every problem that could not be solved within
the extraction** — a gated file, an unpublished mapping, a missing threshold, junk in a
published column — along with what was tried and what the next session should do instead.

Add a section when the answer to "would a future session waste time rediscovering this?" is yes.
Do not add one for problems the procedure already handles cleanly. Append the next free number,
add its row to the index table, and never renumber.
