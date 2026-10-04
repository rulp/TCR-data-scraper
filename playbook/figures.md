# Playbook — figures

**Load this only when sequences or labels have to come out of a figure image.**
Sections keep their original `REPORT` numbers; `REPORT.md` is the index.

---

## 1. The TCR sequences exist only inside a figure image

**The single most important failure mode.** A paper can be written as if β-chain-only — no
CDR3α in the full text, none in the authors' own data files, none in the repository — while
publishing every CDR3α, with V and J genes, as a **sequence-alignment panel in a main
figure**. A first pass that reads only text and attached files will wrongly conclude that
half the schema is unobtainable and emit `NA`.

**Method, in order of efficiency:**

1. **Read the figure captions first.** Pull the PMC full-text XML and list `<fig>` blocks
   with their `xlink:href` graphic filenames and captions. A caption saying "CDR3α and CDR3β
   sequence alignments" is the whole answer, and costs one request to find.
2. **Download the figure.** This path serves 300 DPI originals (~2000×2100 px), not
   thumbnails:
   ```
   https://pmc.ncbi.nlm.nih.gov/articles/instance/<PMCID-digits>/bin/<graphic>.jpg
   ```
3. **Crop the panel and upscale ~3–4× with Lanczos before reading it.** A full-page view
   loses single-residue detail; a cropped, upscaled panel makes every letter unambiguous.
4. **Cross-validate the transcription** — see §2.

**Also read the paragraph describing the figure, and the Methods**, not just the caption.
V-gene families are frequently named in the Results prose when no per-TCR table exists, and
Methods is often the only place stating things like which chain an engineered variant
retained from its parent.

**Caveat to record:** alignment figures usually give gene-level names (`AV21`, `AJ57`) with
no allele. Write them gene-level and note it; do not append `*01`.

## 2. Validating a figure transcription

Never trust a transcription you cannot check.

**Find a machine-readable file that duplicates *part* of the same figure** — a repository
CSV listing one of the two chains, a table repeating a subset. If the overlapping part
matches character-for-character, the rest of the panel is validated too, since it was read
from the same image at the same resolution.

If nothing overlaps, transcribe twice from independent crops before accepting the values.

## 3. Labels are in a figure, values are in a file

A heatmap labels its rows by gene or sample name; a repository CSV holds the sequences and
values but no labels. Neither alone is usable.

**Match them on a shared pattern rather than trusting row order.** Transcribe the figure's
grid as a binary matrix, then compare against the data file over the shared columns. An
exact match across all rows both confirms the correspondence and assigns every label — and
it is self-verifying in a way that assuming row order never is.


---

## Who reads the figure

A transcription error in an alignment panel is a single wrong residue in a training row. It
never announces itself. So the rule is about **what can check the transcription**, not about
which model is cheaper:

| Situation | Who transcribes | Safety net |
|---|---|---|
| A machine-readable file contains the same strings | cheaper model (subagent) | the build script asserts transcription == file, so an error is a crash |
| A file covers only *part* of the panel (§2) | cheaper model (subagent) | assert on the overlap; the match validates the rest |
| Nothing anywhere can check it | **the strongest model you have**, two independent crops | diff the two transcriptions before accepting |

Transcribe inside a **subagent** whenever your tool has them; if it does not, do the
transcription in a separate pass and keep only the strings. The crop-and-upscale loop costs 30–40k
tokens of images for one panel; delegating keeps all of that out of the orchestrator, which
receives only the strings, a per-string confidence, the crop box used, and the diff result.

Never use the cheapest model tier here. Single-character discrimination inside a dense panel is
exactly the failure that survives into the dataset unnoticed.
