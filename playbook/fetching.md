# Playbook — fetching and environment

**Load this only when acquiring raw files or wrestling with local tooling.**
Sections keep their original `REPORT` numbers; `REPORT.md` is the index.

**§4, §7, §8 are solved.** **§11–§12 are marked IGNORE**: they cannot be resolved without a
human, so do not burn time re-attempting them — **§13 explains why §12 happens** and what to ask
the user for. **§19 is reference**: what the PMC APIs hand you, and what they do not.

---

## 4. Bulk data behind a Google Drive interstitial

Files over ~25 MB return an HTML virus-scan warning instead of bytes. Pass `confirm=t`:

```
curl -sSL -c ck.txt "https://drive.usercontent.google.com/download?id=<ID>&export=download" -o /dev/null
curl -sSL -b ck.txt "https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t" -o out.zip
```

Drive links are often referenced **only from a repository README**, never from the paper, and
can hold the ready-to-train dataset when the paper's own archive is gated. Check the README
before concluding data is unavailable.

Label rules are sometimes encoded in the **filenames** of such archives (e.g.
`<id>_neg=rnd234c0_pos=rnd4c5.csv` → positive at round-4 count ≥ 5, negative at count 0
across rounds 2–4), making thresholds recoverable without the paper.

## 7. Row limits

`.xlsx` caps at 1,048,576 rows. A screen's full labeled output — positives plus measured
negatives — routinely exceeds this. Keep the schema file to the positives and put the full
pool in CSV or Parquet.

## 8. Local tooling

- A stray script with a stdlib name (`inspect.py`, `csv.py`) in the working directory
  shadows the real module and breaks imports in confusing ways. Run from a different
  directory, and do not leave such scripts beside data.
- Where the system Python lacks `pandas`/`openpyxl`: `uv run --with openpyxl python` works
  without installing anything.
- Check for Excel lock files (`~$name.xlsx`) before overwriting an output — their presence
  means the file is open and the user will need to reopen it.

---

## 11. IGNORE — gated data repositories

Some archives cannot be scripted. Observed on Dryad, and the pattern generalizes:

- the public file-stream path returns an **Anubis proof-of-work JS challenge** (HTTP 200,
  `text/html`, "Validating…") instead of the file;
- the REST download endpoint returns **HTTP 401, "Unauthorized, must have current bearer
  token"**.

**The metadata API is usually open even when downloads are not**, which is enough to list
every filename, size and ID and decide whether the data is worth a human fetching:

```
https://datadryad.org/api/v2/datasets/doi%3A<url-encoded-doi>
https://datadryad.org/api/v2/versions/<version-id>/files
```

**Do not re-attempt the download.** Check first whether a mirror (§4) already covers the
need — it often does for processed data. What a mirror typically *lacks* is the raw
per-replicate or per-round counts, which means the paper's label threshold cannot be varied
or audited. Note that limitation and move on; a human can download it from the web page
normally.

## 12. IGNORE — supplementary documents from PMC

Supplementary `.docx`/`.pdf` files are frequently unreachable:

- `pmc.ncbi.nlm.nih.gov/articles/instance/<id>/bin/<file>` → HTTP 200 but returns the **HTML
  viewer shell**, not the document;
- `www.ncbi.nlm.nih.gov/pmc/articles/<PMCID>/bin/<file>` → **404**;
- the OA package service `pmc/utils/oa/oa.fcgi?id=<PMCID>` → **404**.

**Note the asymmetry: the same `/bin/` path serves figure images correctly** (figures §1). Always try
`/bin/` for images; do not bother for documents.

Before treating this as blocking, check whether the content is recoverable another way — a
supplementary table's substance is often also plotted in a main figure, which *is* reachable
(figures §1, §3). Only escalate to a human if it is not.

## 13. Why PMC supplementary documents fail — the proof-of-work gate

**§12 recorded the symptom; this is the cause, and it changes what you should do.**

A PMC supplementary *document* request returns a ~1,800-byte HTML shell rather than the file
because `pmc.ncbi.nlm.nih.gov` puts those paths behind a **JavaScript proof-of-work challenge**:
the page expects a browser to solve a hash puzzle and set a `cloudpmc-viewer-pow` cookie before
the bytes are released. The `www.ncbi.nlm.nih.gov/pmc/...` variant makes this explicit with a
"Preparing to download …" interstitial.

This is why **the same file opens fine for the user in a browser** and cannot be curled. It is a
bot check, not a permissions problem, and **it must not be worked around** — do not fetch or
execute the challenge script.

What to do instead, in order:

1. **Europe PMC's bulk endpoint** — *one* quick attempt, and do not wait on it:
   ```
   https://www.ebi.ac.uk/europepmc/webservices/rest/PMC<digits>/supplementaryFiles
   ```
   It returns a ZIP of every supplementary file and sidesteps the gate **when it works**, which
   is not often: it serves only the open-access subset, refuses every author-manuscript paper
   with a ~300-byte `"Article with id PMC… is not open access one"`, and **timed out on all six
   open-access papers tried here** (§19). So give it one short-timeout attempt and move to step 2
   — the refusal is a definitive no, and a timeout is not worth a retry. **Do not build any
   automated step on this endpoint.**
2. **The publisher CDN**, which is usually ungated, and for a Springer/Nature paper is the move
   to try *first* -- 8 of 8 Nature Communications supplementary files came back on 2026-10-06,
   three of them by script after a screen had already written them onto a human's shopping list.

   ```
   Springer   https://static-content.springer.com/esm/art%3A10.1038%2F<DOI-suffix>/MediaObjects/<filename>
   Elsevier   https://ars.els-cdn.com/content/image/1-s2.0-<PII>-mmcN.<ext>
   ```

   `<DOI-suffix>` is everything after `10.1038/`, e.g. `s41467-025-63288-3`. Take it from the
   cached XML, which the probe already wrote -- no lookup call:

   ```bash
   grep -o '<article-id pub-id-type="doi">[^<]*' journals/<J##>_*/xml/<PMID>.xml | head -1
   ```

   `<filename>` is the bare `xlink:href` from `<supplementary-material>`, which is what the
   card's "supplementary files" section already lists. Leave `%3A` and `%2F` encoded; a literal
   `:` or `/` there 404s. `media.springernature.com` is the same store under another name.
3. **Main-paper figure images**, which `/bin/` *does* serve without any challenge — the §1/§12
   asymmetry holds. Supplementary *figures* are usually bound into a supplementary PDF and are
   therefore gated, while main figures are not.
4. **Ask the user to download the one file**, naming it exactly. A single named file is a small
   ask; "the supplement is unreachable" is not. Record the filename in `source_notes` so the
   blocker is actionable rather than vague.

Observed on PMC10841602 (Dezfulian 2023), where `NIHMS1947859-supplement-6.pdf` — Figure S6, holding
two minimal-epitope panels — was the sole blocker for two otherwise complete rows.

**Check the bytes, never the status code.** The gate answers **HTTP 200** and hands back a
~1,800-byte HTML shell, so an exit code of 0 and a file on disk prove nothing. A fetch succeeded
only if the file is the type it claims to be:

```bash
curl -sS -L --max-time 120 -o "$out" "$url" && file -b --mime-type "$out"
```

`application/pdf` or `...spreadsheetml.sheet` is a success; `text/html` is the gate. A 2 KB
`.xlsx` is the gate too, not a small spreadsheet. Delete it rather than leaving it to be found
later and mistaken for data.

**One request at a time to a publisher host.** `probe.py`'s rate limit is NCBI's and does not
apply here, and no publisher CDN policy is recorded anywhere -- so stay conservative: serial
downloads, a short pause between them, never a fan-out of parallel agents against one host.
Whatever you do with the files *after* they land can be parallelised freely; the downloads
cannot.

## 19. Resolving a PMID, and what the PMC APIs actually hand you

**Use `idconv` for PMID → PMCID. Never `elink`.** A multi-id `elink` response does not reliably
pair each linkset back to the id you sent; it returned *one article's* PMCID for *another's* PMID
here, mapping two different articles to the same record. Nothing errors — the wrong article is simply
fetched and screened. It is authoritative and batched:

```bash
curl -sS "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/?ids=<PMID,PMID,...>&format=json"
```

**One `efetch db=pmc` is worth a dozen scraping attempts.** That single document carries the full
body, the **complete supplementary file inventory with filenames and extensions**, the
data-availability statement and every figure caption. It is how a screen names a gated file exactly
rather than reporting a vague blocker — the inventory for PMC10841602 names
`NIHMS1947859-supplement-6.pdf`, the file that later unblocked that extraction. Measured over 12 journals, **95%
of candidate papers are in PMC**, so this route covers nearly the whole corpus.

**But the inventory is not the bytes.** Two routes that look like they should work and do not:

- `https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/bin/<filename>` — 404s or returns an HTML shell.
  This is §13's proof-of-work gate, still live.
- Europe PMC `.../webservices/rest/<PMCID>/supplementaryFiles` — a whole-article ZIP, but **only
  for the open-access subset**. It refuses every author-manuscript paper (`"is not open access
  one"`), which is where NIH-funded Cell/Science/Nature papers live — and
  it timed out on all six OA papers tried. Do not build on it. §13 step 1 is the same endpoint,
  kept there as a single cheap attempt before the publisher CDN, for the same reason.

So: **the inventory is free and reliable; the bytes are not.** A screen should judge from the
inventory and defer downloading, and a gated file becomes a precise request to the user — name,
source URL, destination path, and what it unblocks.

## 24. IGNORE — GEO accession pages are behind a reCAPTCHA

`https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=<GSE>` does not serve the accession page to a
script. It answers **HTTP 200** with a Google reCAPTCHA challenge page -- `recaptcha-boq-challengepage`
in the body, no supplementary file list anywhere in it. Like the PMC proof-of-work gate (§13) this
is a bot check rather than a permissions problem, **it must not be worked around**, and the same
page opens normally in a browser.

This matters because a data-availability statement naming a GEO accession reads like a cheap
check and is not one. Treat a GEO accession as a human item from the start: name the accession
and what it would settle, and let someone open it.

Two things that do still work from a script, and are worth trying first:

- **Zenodo's REST API is open** and gives the file list without any challenge:
  ```
  https://zenodo.org/api/records/<id>
  ```
  A *concept* DOI redirects to the current record, so the `id` you get back may differ from the
  one the paper cites -- `14516943` answers as record `14551359`. The response carries each
  file's `key` and `size`, which is enough to decide whether a download is worth it before
  starting one. Sizes are often large: the record above holds a 5.8 GB, a 318 MB and a 165 MB
  archive, none of which a screen should pull on spec.
- **A GitHub-hosted deposit is fully open**, both the issue thread and the file:
  ```
  https://api.github.com/repos/<owner>/<repo>/issues/<n>
  https://raw.githubusercontent.com/<owner>/<repo>/master/<path>
  ```
  Observed on `antigenomics/vdjdb-db` issue 413, whose body named
  https://raw.githubusercontent.com/antigenomics/vdjdb-db/master/chunks/PMID_40640147.tsv --
  28 KB, 154 rows with paired CDR3/V/J, epitope and MHC, and it turned a PARK into a PASS for one
  GET (Sturmlechner 2025, PMID 40640147). When a paper
  says its sequences went to VDJdb, this is the route -- not the VDJdb web UI.

## 25. One deposit, several datasets -- answer the question you actually asked

A park or a blocker names a question ("does the deposit carry per-cell CDR3/V/J **with the
tetramer labels**?"). A deposit then hands back a dozen files. The failure mode is to open the
first file that looks like the answer, find it convincing, and never notice it belongs to a
different experiment.

Observed on Cardon 2025 (PMID 39880819), Zenodo record 14551359. `figure2_input_metadata.csv` has
paired CDR3/V/J for 2,768 cells and an `Ag_reactivity` column -- it looks exactly like the answer.
It is the **peptide-stimulation** experiment, and its labels are protein names, so the honest
conclusion from that file is "no usable antigen". The tetramer experiment was
`figure4_output_metadata.RData`, a different file for a different figure, holding 31 clonotypes
against one defined epitope. **The paper was failed on the strength of the wrong file and had to
be reinstated.**

What to do instead:

- **Name the figure, not just the file.** A deposit is usually organised by figure
  (`figure2_*`, `figure4_*`). Find which figure the question is about -- the Results paragraph
  that describes the experiment says so -- and read that figure's files first.
- **Enumerate the whole archive before concluding anything**, including files you do not plan to
  open. 14 names is cheap to scan; it is how you notice `figure4_` exists at all.
- **A negative answer is the one to double-check.** "This deposit has nothing usable" ends a
  paper, so it needs the same evidence a positive would. A positive gets checked by the audit
  later; a negative never gets checked again.
- Do not assume one format per deposit. The usable half here was `.RData`, readable with
  `pyreadr` and invisible to any CSV-oriented scan.
