# Playbook — the checks, as runnable tests

**Load this at Step 4, before writing any output file.** It is the operational half of
`playbook/judgement.md`: that file explains *why* each rule exists and what to do when one
fires; this file is just the tests, in the order you need them.

Every check below is written to be **pasted into the build script as an `assert`**, not run once
in a shell and forgotten. A check that lives only in a transcript stops protecting the data the
moment someone edits the script.

| # | Check | Fires when | Why — read before deciding |
|---|---|---|---|
| C1 | Amino-acid alphabet | a sequence column holds non-residues | `judgement.md` §5 |
| C2 | CDR3 shape | a CDR3 lacks the conserved `C`, or is absurdly short | `judgement.md` §16 |
| C3 | Peptide length window | a peptide is outside the class-I or class-II range | `judgement.md` §18 |
| C4 | Masked placeholders | an ML training file leaks `XXXXXXXXX`-style rows | `judgement.md` §5 |
| C5 | Dedup key uniqueness | two receptors collapse into one row | `judgement.md` §6 |
| C6 | Does the supplement even have sequences | a screen table is keyed by an opaque ID | `judgement.md` §14 |
| C7 | Is there a stated threshold | the paper never defines a hit | `judgement.md` §15 |
| C8 | `pMHC_species` agrees per source | one peptide disagrees with its siblings | `judgement.md` §10, §17 |
| C9 | Combined file double-count | a pooled file re-lists individual TCRs | `judgement.md`, recurring decision 4 |
| C10 | Figure transcription cross-check | a figure read disagrees with a file | `figures.md` §2 |
| C11 | Emit-time sanity | `NA`s, open workbooks, row limits | `fetching.md` §7, §8 |
| C12 | Per-row attribution | a row does not say where its values came from | `AGENTS.md`, the extrapolation invariant |

---

## C1–C3 — the sequence validators

One helper covers all three. Paste it; do not reimplement it per paper.

```python
AA = set("ACDEFGHIKLMNPQRSTVWY")

def valid_cdr3(s):
    """Amino acids only, the conserved leading cysteine, and a sane length."""
    return bool(s) and set(s) <= AA and s.startswith("C") and 8 <= len(s) <= 22

def valid_peptide(s, mhc_class="I"):
    lo, hi = (8, 11) if mhc_class == "I" else (9, 25)
    return bool(s) and set(s) <= AA and lo <= len(s) <= hi
```

```python
for col in ("CDR3a", "CDR3b"):
    bad = [s for s in clean[col] if not valid_cdr3(s)]
    assert not bad, f"{col} failed validation: {bad}"
for pep in clean["Antigen"]:
    assert valid_peptide(pep, MHC_CLASS), f"bad peptide: {pep!r} ({len(pep)})"
```

**The leading `C` is not optional.** `HPEGKLIF` and `CAVFF` are both pure amino-acid letters and
neither is a CDR3; an alphabet-only check passes both. See `judgement.md` §16.

## C4 — masked placeholders

Published ML training files leak masked rows, usually labelled positive. Do not let them crash
the build and do not drop them silently — route them to a companion and assert the count, so a
changed mirror announces itself.

```python
if not set(pep) <= AA:
    masked.append(dict(tcr_id=t, Epitope=pep, Score=score, reason="masked placeholder"))
    continue
...
assert len(masked) == 21, f"expected 21 masked rows, got {len(masked)}"
assert {m["tcr_id"] for m in masked} == {"9.1"}, "masked rows are no longer confined to 9.1"
```

## C5 — dedup key uniqueness

Neither chain alone is a key. Prove the collisions exist, then prove the composite key survives
them.

```python
betas = [v.CDR3b for v in panel]
assert len(set(betas)) < len(betas), "expected CDR3b collisions in this panel"
pairs = [(v.CDR3a, v.CDR3b) for v in panel]
assert len(set(pairs)) == len(pairs), "(CDR3a, CDR3b) is not unique across the panel"
assert not clean.duplicated(["CDR3a", "CDR3b", "Antigen"]).any()
```

## C6 — does the supplement contain sequences at all

Run this **before planning the extraction**. Zero hits across every table means the screen
cannot populate `Antigen`, however good its counts are.

```bash
tr ',\r' '\n\n' < table.csv | grep -cE '^[ACDEFGHIKLMNPQRSTVWY]{8,}$'
```

Then check the *unit*: a 56-, 90- or 15–18-aa library fragment is not a presented epitope, even
when its sequence is published. See `judgement.md` §14.

## C7 — is there a stated threshold

```bash
grep -oiE '.{80}(threshold|cutoff|FDR|z-score|fold.enrich).{80}' fulltext.xml | head -20
```

If `threshold` never appears and the only quantitative sentences are definitional or visual, the
hit calls were made by eye. Do not invent or borrow one — `judgement.md` §15.

## C8 — `pMHC_species` agrees within each source

The error this catches is one peptide carrying a different origin from its siblings because
someone judged it by eye.

```python
print(df.groupby(["peptide_source", "pMHC_species"]).size())
```

Expect exactly one value per source. More than one means either a genuine mixed panel — a
proteome set plus a microbial control, which is fine and must follow the *stated* provenance —
or an inferred value, which is the bug. `judgement.md` §10 and §17.

## C9 — combined-file double-count

A pooled file that re-lists individual receptors inflates them. Prove it is redundant before
excluding it, rather than assuming:

```python
assert (combined_rows, combined_pos) == (sum_of_parts_rows, sum_of_parts_pos), \
    "the combined file is not the union of its parts; re-check before excluding it"
```

## C10 — figure transcription cross-check

Never ship a figure read on its own authority. Find something machine-readable that overlaps it
and assert the overlap.

```python
assert PANEL[t].CDR3b == published_b[t], f"{t}: figure read disagrees with the published file"
```

If a figure has two panels that constrain each other — a sequence in one, a measurement in the
other — assert the implied ordering too. `figures.md` §2.

## C11 — emit-time sanity

```python
assert not clean.isin(["NA", "", None]).any().any(), "no column may be NA"
assert not os.path.exists(os.path.join(OUT, f"~$clean_{ID}.xlsx")), "workbook is open in Excel"
```

`.xlsx` caps at 1,048,576 rows; a full labelled screen exceeds it routinely. Positives go in the
workbook, the pool goes to CSV/Parquet — `fetching.md` §7.

## C12 — every row says where it came from

The `clean` sheet has no room for attribution, so it lives in the `provenance` sheet, aligned 1:1.
`lib/provenance.py` builds it and checks it; the build script never hand-rolls these columns.

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.provenance import Prov, check_provenance, columns

p = Prov()
p.set("Va", "Ja", "CDR3a", "Vb", "Jb", "CDR3b", origin="external",
      source="VDJdb 2026-10-03 (PMID 19864595); not stated in this paper")
p.set("Antigen", origin="file",   source="Table S3, column D")
p.set("MHC",     origin="figure", source="Fig. S6B legend")
p.set("pMHC_species", origin="text", source="Methods, library design")
p.set("TCR_species",  origin="text", source="Results, donor description")
prov.append(p.row(tcr_id=t, assay="CD69 upregulation"))   # extras are free-form

prov = pd.DataFrame(prov)[columns(pd.DataFrame(prov).columns)]
check_provenance(clean, prov, "<ID>")     # raises unless every row, every field, is attributed
```

`origin` is one of `file` · `figure` · `text` · `external`, joined with `+` when a row draws on
more than one — that combination is the point. `extrapolated` is derived: `no` only when every
field came from a machine-readable file of *this* paper.

**C12 checks that an attribution is PRESENT. It cannot check that it is TRUE** — that is
`audit.py` and `procedures/audit-provenance.md`, which run against the shipped workbook, re-read
`raw/`, re-fetch external records and re-transcribe figures blind. Run the audit after a batch;
C12 runs inside every build.

**A paper whose every row reads `origin = text` has not been attributed, it has been rubber-stamped.**
Real rows mix: the peptide from a table, the α chain from a database, the allele from a legend.
