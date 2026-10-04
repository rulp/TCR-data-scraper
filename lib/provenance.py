"""One provenance schema for every paper.

Each build script is bespoke -- no two groups format their tables alike -- but the
*attribution* must not be. Before this module existed, four papers produced four different
vocabularies (`Va_source` vs `tcr_sequence_source` vs `peptide_source`), so a merged table
could not be filtered by where a row came from. This module fixes the schema; the paper
script still decides what the values are.

Usage, once per emitted row:

    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lib.provenance import Prov, check_provenance

    p = Prov()
    p.set("Va", "Ja", "CDR3a", "Vb", "Jb", "CDR3b", origin="external",
          source="VDJdb 2026-10-03 (PMID 19864595); not stated in PMID <this paper>")
    p.set("Antigen", origin="text", source="Methods, 'Peptide pulsing ...', verbatim")
    p.set("MHC", origin="text", source="Methods, 'Generation of target cells'")
    p.set("pMHC_species", origin="text", source="Methods, library design")
    p.set("TCR_species", origin="text", source="Results, clone roster")
    prov.append(p.row(tcr_id="NLV3", source_pmid="38956325", assay="CD69 upregulation"))

`row()` raises if any of the ten schema fields was never attributed, so a missing source is a
build failure rather than a silent blank.
"""

SCHEMA = ["Va", "Ja", "CDR3a", "Vb", "Jb", "CDR3b",
          "Antigen", "MHC", "pMHC_species", "TCR_species"]

#: The paper's PMID, required on every row. Paper IDs are assigned per machine and
#: start at 001 on each, so `007` means different papers in different workspaces --
#: the PMID is the only key that means the same thing everywhere, and it is what two
#: machines' outputs merge on. Required by contract, not by convention.
KEYS = ["tcr_id", "source_pmid"]

#: Where a value physically came from.
#:   file     - a machine-readable supplement of THIS paper (.xlsx/.csv/.tsv)
#:   figure   - read off a figure image or panel
#:   text     - this paper's prose: Methods, Results, a main-paper table, a figure legend
#:   external - another paper, VDJdb, PDB, IMGT, or a data repository
ORIGINS = {"file", "figure", "text", "external"}

#: Only a machine-readable file of the paper itself is non-extrapolated. AGENTS.md:
#: "anything read off a figure or a main-paper table -- rather than taken from a
#: machine-readable file -- must say so."
NOT_EXTRAPOLATED = {"file"}


class Prov:
    """Collects a per-field attribution for one output row."""

    def __init__(self):
        self._origin = {}
        self._source = {}

    def set(self, *columns, **kw):
        """Attribute one or more schema columns to the same origin and source string."""
        origin, source = kw.pop("origin"), kw.pop("source")
        if kw:
            raise TypeError("unexpected keyword(s): %s" % ", ".join(kw))
        if origin not in ORIGINS:
            raise ValueError("origin %r not in %s" % (origin, sorted(ORIGINS)))
        if not str(source).strip():
            raise ValueError("empty source for %s" % ", ".join(columns))
        for c in columns:
            if c not in SCHEMA:
                raise ValueError("%r is not a schema column; expected one of %s" % (c, SCHEMA))
            self._origin[c] = origin
            self._source[c] = str(source).strip()
        return self

    def row(self, tcr_id, source_pmid=None, **extra):
        """Emit the provenance row. Raises if any schema column is unattributed."""
        missing = [c for c in SCHEMA if c not in self._source]
        if missing:
            raise ValueError("row %r has no attribution for: %s" % (tcr_id, ", ".join(missing)))
        if not str(source_pmid or "").strip():
            raise ValueError(
                "row %r has no source_pmid. Local paper IDs differ between machines; the PMID "
                "is the only key two workspaces can merge on, so it is required." % (tcr_id,))
        origins = sorted(set(self._origin.values()))
        r = {"tcr_id": tcr_id,
             "source_pmid": str(source_pmid).strip(),
             "origin": "+".join(origins),
             "extrapolated": "no" if set(origins) <= NOT_EXTRAPOLATED else "yes"}
        for c in SCHEMA:
            r[c + "_source"] = self._source[c]
        r.update(extra)
        return r


def columns(extra=()):
    """Canonical column order: keys first, then the ten sources, then paper-specific extras."""
    fixed = KEYS + ["origin", "extrapolated"]
    return (fixed
            + [c + "_source" for c in SCHEMA]
            + [c for c in extra if c not in
               set(fixed) | {c2 + "_source" for c2 in SCHEMA}])


def check_provenance(clean, prov, label=""):
    """C12. Assert the provenance frame really attributes every clean row."""
    tag = (label + ": ") if label else ""
    assert len(clean) == len(prov), (
        "%sprovenance has %d rows but clean has %d -- they must align 1:1"
        % (tag, len(prov), len(clean)))

    for c in KEYS + ["origin", "extrapolated"] + [s + "_source" for s in SCHEMA]:
        assert c in prov.columns, "%smissing provenance column %r" % (tag, c)

    blank_pmid = (prov["source_pmid"].isna()
                  | (prov["source_pmid"].astype(str).str.strip() == ""))
    assert not blank_pmid.any(), (
        "%s%d row(s) have no source_pmid -- it is the only key that survives across machines"
        % (tag, int(blank_pmid.sum())))

    for col in [s + "_source" for s in SCHEMA]:
        blank = prov[col].isna() | (prov[col].astype(str).str.strip() == "")
        assert not blank.any(), (
            "%s%d row(s) have an empty %s -- every field must say where it came from; "
            "first at position %d" % (tag, int(blank.sum()), col, int(blank.values.argmax())))

    for i, o in enumerate(prov["origin"].astype(str)):
        bad = set(o.split("+")) - ORIGINS
        assert not bad, "%srow %d has unknown origin(s) %s; allowed: %s" % (
            tag, i, sorted(bad), sorted(ORIGINS))

    for i, (o, e) in enumerate(zip(prov["origin"].astype(str), prov["extrapolated"].astype(str))):
        want = "no" if set(o.split("+")) <= NOT_EXTRAPOLATED else "yes"
        assert e == want, (
            "%srow %d: origin=%r implies extrapolated=%r but the row says %r"
            % (tag, i, o, want, e))
    return True


def finalize(prov, origins):
    """Vectorized counterpart to ``Prov.row()``.

    For scripts that build the provenance frame column-wise rather than row by row.
    ``prov`` must already carry a ``<column>_source`` column for all ten schema fields;
    ``origins`` maps each schema column to its origin -- a string, or a per-row Series when
    one column's origin varies between rows.

        prov = finalize(prov, {**{c: "external" for c in SCHEMA[:6]},
                               "Antigen": "file", "MHC": "text",
                               "pMHC_species": "text", "TCR_species": "text"})
    """
    import pandas as pd

    missing = [c for c in SCHEMA if c + "_source" not in prov.columns]
    if missing:
        raise ValueError("no <col>_source for: %s" % ", ".join(missing))
    if "source_pmid" not in prov.columns:
        raise ValueError("no source_pmid column -- set prov['source_pmid'] = PMID before "
                         "finalize(); it is the only key that survives across machines")
    missing = [c for c in SCHEMA if c not in origins]
    if missing:
        raise ValueError("no origin given for: %s" % ", ".join(missing))

    cols = {}
    for c in SCHEMA:
        o = origins[c]
        s = o if isinstance(o, pd.Series) else pd.Series([o] * len(prov), index=prov.index)
        bad = set(s.unique()) - ORIGINS
        if bad:
            raise ValueError("origin(s) %s for %s not in %s" % (sorted(bad), c, sorted(ORIGINS)))
        cols[c] = s

    combo = pd.DataFrame(cols).apply(lambda r: "+".join(sorted(set(r))), axis=1)
    prov = prov.copy()
    prov["origin"] = combo
    prov["extrapolated"] = combo.map(
        lambda o: "no" if set(o.split("+")) <= NOT_EXTRAPOLATED else "yes")
    return prov[columns(prov.columns)]
