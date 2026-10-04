# Setup — running this on another machine

Nothing here is specific to macOS, to Claude, or to any one AI tool. You need Python and an
internet connection.

## 1. Python

Python **3.9 or newer**. Three third-party packages, and that is the whole list:

| package | used by |
|---|---|
| `pandas` | every build script, `audit.py`, `lib/provenance.py` |
| `openpyxl` | the `.xlsx` engine behind every read and write |
| `pypdf` | `audit.py`, to read the text layer of supplementary PDFs |

Pick either route.

**A virtual environment** — ordinary, works anywhere:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python audit.py --help
```

**Or [uv](https://docs.astral.sh/uv/)** — no venv to manage, which is how it is run here:

```bash
uv run --with pandas --with openpyxl --with pypdf python audit.py
```

`journals/probe.py` imports nothing outside the standard library, so it runs under a bare
`python3` either way.

Every script resolves its paths from its own location, so it does not matter which directory you
run it from. `audit.py` and `journals/probe.py` both take `--help`, and both refuse an unknown
flag rather than ignoring it.

## 2. Set up this machine's workspace

```bash
python3 tools/init_workspace.py
```

**The repo is a toolkit, not a corpus.** It ships the procedures, the playbook, the scripts and
the journal list — and nothing else. There are no papers in it. Your index starts empty, at
`001`, and everything you produce stays on this machine.

| in git — shared, identical everywhere | not in git — yours alone |
|---|---|
| `AGENTS.md` `README.md` `SETUP.md` | `paper_source.md`, your index |
| `procedures/` `playbook/` `docs/` `REPORT.md` | `<ID>_<Author>/` — every paper, `raw/` and output |
| `audit.py` `lib/` `tools/` `journals/probe.py` | `journals/J##_*/` — every sweep |
| `journals/journals.md` `journals/method.md` | `AUDIT.md` · `audit/` |

That split is deliberate: because no mutable file is shared, pulling a corrected procedure can
never conflict with work in progress.

**It also means git is not a backup of your data.** Papers, `raw/`, `AUDIT.md` and
`audit/reads/` live only on this disk. Mirror the whole folder to Drive or equivalent — and
especially `audit/reads/*.json`, the blind figure transcriptions, which cannot be regenerated
honestly once an agent has seen the workbook.

Some supplementary files cannot be fetched by a script at all: publishers put them behind a
proof-of-work gate (`REPORT.md` §13). The screen lists those per journal in
`journals/<J##>_*/NEEDS_HUMAN.md` with the URL, the destination path, and what each one
unblocks, so you can fetch them in a browser in one sitting.

## 3. Optional: an NCBI API key

`journals/probe.py` queries PubMed and PMC. Without a key NCBI allows 3 requests/second; with one,
10/second. The script reads it from the environment and works fine without:

```bash
export NCBI_API_KEY=...     # https://account.ncbi.nlm.nih.gov/settings/
```

## 4. Check it works

```bash
python3 tools/check_docs.py                    # no dangling path in any document
python3 journals/probe.py --help               # standard library only
python audit.py --help                         # dependencies and flags
```

A fresh clone has no papers yet, so there is nothing for the audit to check until you extract
one. When you do, a missing `raw/` is reported as `unverifiable` per file, never as an error.

## 5. Working on more than one computer

Each machine runs its own copy with its own index. **Local IDs are local** — `007` on the laptop
and `007` on the desktop are different papers, and that is fine, because nothing keys on them
across machines. **PMID is the shared key**: it is in `paper_source.md`, it is required on every
provenance row by `lib/provenance.py`, and it is what lets two machines' outputs merge later.

Two things coordinate the machines, and they split cleanly:

**Journals — in git.** `journals/journals.md` is the master list, identical everywhere, and it
carries `Status`, `Machine` and `Last swept`. Pull, mark the row for the journal you are taking,
push that change *before* you sweep. The other machine then sees the claim. It is the only
tracked file you edit, and its own Rules section has the three rules that keep it mergeable.

**Papers — in a shared sheet.** `docs/templates/tracking_sheet.csv` is one tab keyed on PMID.
Your paper index is private to this machine, so this is the only way to know a paper is already
taken. Check it before extracting.

```bash
python3 tools/export_index.py          # this machine's papers as CSV, ready to paste
```

Day to day: `git pull` whenever you want the other machine's toolkit fixes — procedures,
playbook, scripts, and the journal list. It cannot touch your papers or your index. Push toolkit
and journal-status changes the same way. Your data travels by Drive, not by git.

## 6. Pointing an AI agent at it

Start it on **`AGENTS.md`**. That file routes every task to an ordinary markdown file at an
ordinary path — the four procedures are in `procedures/`, the reference material in `playbook/`
and `docs/`. No skill system, plugin or memory feature is required.

`.claude/skills/` holds four four-line stubs so that Claude Code can auto-invoke the procedures by
name. They contain no content of their own. Delete the whole `.claude/` directory if you use a
different tool and nothing breaks.
