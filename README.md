# TCR-data-scraper: extracting TCR training data from papers

## What this is for

T cells recognise disease using a **T-cell receptor (TCR)**. Each receptor binds a short
**peptide** held up by an **MHC** molecule. Which receptor binds which peptide is the thing we
want to predict — and to train a model to predict it, you need a lot of examples of receptors
paired with the peptides they actually bind.

Those examples exist, but they are scattered across hundreds of papers, in different formats:
some in spreadsheets, some only inside a figure image, some only in a sentence in the Methods.

**This pipeline collects them into one clean table.** Every row is one receptor paired with one
peptide it recognises, always in the same ten columns, no matter which paper it came from.

The hard part is not collecting — it is *not being wrong*. A fabricated row is worse than a
missing one, because a model trained on it learns something false and nobody can tell. So most
of the machinery here exists to make mistakes visible: every value records where it came from,
and a final audit goes back and checks that it really is there.

## What comes out

One spreadsheet per paper, `clean_<ID>.xlsx`, with three tabs:

| tab | what's in it |
|---|---|
| `clean` | the data — exactly ten columns, one row per (receptor, peptide) pair |
| `provenance` | for every row, where each value came from |
| `source_notes` | the judgement calls made while extracting, in plain English |

The ten columns are `Va, Ja, CDR3a, Vb, Jb, CDR3b, Antigen, MHC, pMHC_species, TCR_species` —
the alpha chain, the beta chain, the peptide, the MHC allele, and what species the peptide and
the receptor come from.

A fresh copy starts empty. One paper typically yields anywhere from a handful of rows to
tens of thousands, depending on whether it published a screen or just a validated panel.

---

## The whole pipeline, at a glance

```bash
python3 tools/init_workspace.py                   # once per computer

python3 journals/probe.py J01                     # find and score candidates (free)
#   ... then ask your agent to SCREEN the journal
#   ... then fetch any blocked files into journals/J01_*/incoming/<PMID>/

python3 tools/new_paper.py --pmid <PMID> --from J01   # give it an ID and a folder
#   ... then ask your agent to EXTRACT it

uv run --with pandas --with openpyxl --with pypdf python audit.py    # check the result
```

Three of those are things **you** run; two are things you ask **your AI agent** to do. The agent
reads `AGENTS.md`, which routes it to the right procedure. You never have to name a file for it.

---

## Before you start

Once per computer:

```bash
python3 tools/init_workspace.py
```

This creates your own paper index (`paper_source.md`), the empty `journals/` and `audit/`
folders, and the skill adapters that let your AI tool invoke a procedure by name. `SETUP.md`
covers Python and the three packages you need, and how to work across two machines.

**The repo is a toolkit, not a corpus.** It ships the procedures, the playbook, the scripts and
the journal list — no papers. Everything you produce stays on your machine and is not in git, so
**git is not a backup**. Mirror the folder to Drive.

---

## The four steps

Each step is separate on purpose, so you can check the work before moving on.

### 1. Pick a journal, and claim it

`journals/journals.md` lists 40 credible journals, ranked `P1` (do these first) to `P3`.
Each has a date window, usually the last 2 years, and a rough count of how many candidate
papers it holds. Open the file and pick the next one that says `not started`.

Then **mark it `in progress` with your computer's name and today's date, and push that change
before you start.** This is the one file in git that you edit, and that one line is what stops a
second computer screening the same journal. Change only that journal's row, and never re-align
the table.

### 2. Screen that journal for useful papers

```bash
python3 journals/probe.py J01
```

This does the free part: it finds every candidate paper in that journal and downloads one
summary document each, then scores them. It costs nothing but time, and you can stop and
re-run it — it picks up where it left off.

Then ask your AI agent to **screen the journal**. It reads the scored summaries — about 20
papers at a time, not the whole journal — and decides which ones can actually yield data,
writing the result into that journal's folder:

- `screened.md` — three lists: the papers worth extracting, the ones **parked** (one cheap check
  away from an answer), and the ones that **failed**, so a later round never re-reads them
- `notes/<PMID>.md` — for each paper worth extracting, *where in the paper* each piece of data
  lives, down to the sheet, column or figure panel
- `NEEDS_HUMAN.md` — files it could not download, with exact names and what each one unblocks

**You will sometimes need to help here.** Some supplementary files sit behind a bot check that a
script cannot pass, though you can open them in a browser in seconds. `NEEDS_HUMAN.md` lists
them with the exact filename and what each one is worth, so you can judge whether it is worth
the trip.

Save what you fetch into that journal's `incoming/<PMID>/` folder. **You can do this at any
time** — you do not have to wait for extraction to start, and the files will be picked up
automatically when it does. (They go there rather than into a paper's own folder because a paper
has no number yet; it gets one only when extraction begins.)

Expect most papers to fail this screen, and expect that to be the point — screening is cheap,
extraction is not. Two real journals: of 7 candidates in Nature Biotechnology, 1 was usable; of
the first 20 screened in Nature Communications, 7 passed, 3 were parked and 10 failed.

### 3. Extract the papers that passed

Work in batches of **1 to 5**. Small batches are deliberate: you get to look at each batch
before the next one starts.

For each paper, give it its permanent number and its folder:

```bash
python3 tools/new_paper.py --pmid 38684663 --from J01
```

That picks the next free ID, adds a row to your index, creates the paper's folder, and **moves
anything you already fetched into it**. Add `--dry-run` first if you want to see what it will do.

Then ask your agent to **extract** the paper. It writes a small script inside that folder which
turns the raw files into the spreadsheet, so nothing is done by hand — if a rule changes later,
you re-run the script instead of redoing the paper:

```bash
uv run --with pandas --with openpyxl python papers/007_Smith/007_Smith.py
```

### 4. Audit — check the data is really where it says it is

```bash
uv run --with pandas --with openpyxl --with pypdf python audit.py
```

This is the safety net. For every value, it goes back to the source that value claims to come
from and looks for it. It writes `AUDIT.md` and **fails loudly** if anything is missing.

Values that exist only inside a figure get checked by having someone re-read the figure
**without being told the expected answer** — otherwise they would just agree with it.

Results are one of:

- **verified** — found where it says it is
- **mislocated** — the value is real but points at the wrong file (fix the note, not the data)
- **judgement** — a decision, not a quote (the two species columns; these can't be string-matched)
- **unverifiable** — no way to check automatically, and it says why
- **contradicted** — *not where it claims to be.* **Stop and investigate.**

A run that ends in **0 contradicted** is the result you want. Anything else is a finding, not
a failure of the audit.

**Never edit the data to make the audit pass.** A contradiction can mean the note is wrong, the
value is wrong, or the source changed — and those have different fixes.

---

## Where things live

```
journals/            the journal list, and one folder per journal you've screened
  J01_Nat_Commun/      its scored candidates, the screen's notes, and incoming/ for
                       files you fetched by hand
papers/              the corpus — one folder per paper, raw files in and spreadsheet out
  007_Author/          …each named by its permanent ID
paper_source.md      this computer's list of papers, with their permanent IDs
AUDIT.md             the latest audit result
tools/               the small helper scripts you run by hand
playbook/            hard-won lessons: what goes wrong and what to do about it
REPORT.md            index to the playbook — every numbered section lives here
procedures/          the four step-by-step procedures the agent follows
docs/schema.md       what the output must look like — the ten columns
lib/provenance.py    shared code so every paper records sources the same way
AGENTS.md            instructions for the AI agent (not meant for people)
SETUP.md             installing and running it on another computer
```

## Four rules that will bite you

1. **IDs are permanent.** Once a paper is `007`, it is `007` forever — the number is in file
   names and in provenance records. Add new papers at the end; never renumber or reuse, even
   for a paper that got dropped. `tools/new_paper.py` is what keeps this honest.
2. **Every paper lives in `papers/`**, one folder each, holding everything that paper
   produces — build script included. Never inside a journal folder, and never loose at the top
   level: that is what keeps the repo's own files findable once you have a few dozen papers.
3. **IDs are local to this computer.** If you run this on a second machine, its `001` is a
   different paper. The PMID is what the two have in common — which is why the shared tracking
   sheet is keyed on it, and why you should check that sheet before extracting. See `SETUP.md`.
   `tools/export_index.py` prints your papers as rows to paste into it.
4. **Don't delete anything from `raw/`.** The build scripts read from it, and the audit checks
   against it. If a file is gone, the paper can no longer be verified. Nothing under a paper
   folder is in git, so back it up yourself.

## When something goes wrong

`REPORT.md` is the index to everything that has already gone wrong and been solved — gated
downloads, sequences hidden in figures, junk in published tables, papers that never state their
own threshold, and papers that look extractable but cannot be.

If you hit something new that a future session would waste time rediscovering, add a section.
That is what keeps the pipeline from relearning the same lesson.
