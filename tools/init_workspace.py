#!/usr/bin/env python3
"""Set up this machine's workspace on a fresh clone.

The repo ships the toolkit only -- procedures, playbook, scripts, the journal list.
Two things are per-machine and gitignored, so a clone has to create them:

  * paper_source.md, this machine's index, seeded from docs/templates/
  * the skill adapters, which let your agent auto-invoke a procedure by name

    python3 tools/init_workspace.py                   # both adapter folders
    python3 tools/init_workspace.py --tools claude    # just one
    python3 tools/init_workspace.py --list            # show what would be written

SKILL.md is the Agent Skills open standard, so the file is the same everywhere --
only the folder each tool looks in differs, and no tool lets you redirect it. The
adapters are therefore generated, never committed: procedures/ is the one source
of truth. Re-run this after `git pull` if a procedure's description changed.

Safe to re-run. It never overwrites paper_source.md; it always refreshes the
adapters, because a stale description is how a skill stops matching.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCEDURES = os.path.join(ROOT, "procedures")
SEEDS = [("docs/templates/paper_source.md", "paper_source.md")]

#: Project skills directories, per each vendor's own documentation. If one of these
#: is ever wrong or a new tool appears, this table is the only thing to change.
SKILL_DIRS = {
    "agents": ".agents/skills",   # Codex CLI, Cursor, and the wider Agent Skills ecosystem
    "claude": ".claude/skills",   # Claude Code, which reads nothing else
}

STUB = """---
name: %(name)s
description: %(description)s
---

**Read `procedures/%(name)s.md` now and follow it.**

That file is the procedure. This is a generated pointer, not a copy -- it names the
procedure rather than duplicating it, so it cannot fall out of date. Regenerate with
`python3 tools/init_workspace.py`. Deleting this folder breaks nothing: every
procedure is reachable by path from AGENTS.md.
"""

FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def procedures():
    """(name, description) for every procedure, from its own frontmatter."""
    out = []
    for f in sorted(os.listdir(PROCEDURES)):
        if not f.endswith(".md"):
            continue
        name = f[:-3]
        m = FM.match(open(os.path.join(PROCEDURES, f), encoding="utf-8").read())
        if not m:
            sys.exit("procedures/%s has no YAML frontmatter; it needs `name` and "
                     "`description` so an adapter can be generated from it." % f)
        fields = dict(re.findall(r"^(\w[\w-]*):\s*(.*)$", m.group(1), re.M))
        # Cursor requires a skill's name to match its parent folder; keying off the
        # filename guarantees that, so a mismatch is a bug in the procedure file.
        if fields.get("name") != name:
            sys.exit("procedures/%s declares name %r but must declare %r -- the name has "
                     "to match the filename, or the skill will not load." %
                     (f, fields.get("name"), name))
        if not fields.get("description"):
            sys.exit("procedures/%s has no description; that is what an agent matches on." % f)
        out.append((name, fields["description"]))
    return out


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    want = SKILL_DIRS
    if "--tools" in argv:
        i = argv.index("--tools") + 1
        if i >= len(argv) or argv[i].startswith("--"):
            sys.exit("--tools needs a value, e.g. --tools claude\n" + __doc__)
        keys = [k.strip() for k in argv[i].split(",") if k.strip()]
        bad = [k for k in keys if k not in SKILL_DIRS]
        if bad:
            sys.exit("unknown tool(s) %s; known: %s" % (", ".join(bad), ", ".join(SKILL_DIRS)))
        want = {k: SKILL_DIRS[k] for k in keys}

    procs = procedures()

    if "--list" in argv:
        for key, d in sorted(want.items()):
            for name, _ in procs:
                print(os.path.join(d, name, "SKILL.md"))
        return 0

    made, kept = [], []
    for src, dst in SEEDS:
        d = os.path.join(ROOT, dst)
        if os.path.exists(d):
            kept.append(dst)
            continue
        shutil.copyfile(os.path.join(ROOT, src), d)
        made.append(dst)

    for d in ("journals", "audit"):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)

    written = 0
    for key, rel in sorted(want.items()):
        for name, description in procs:
            d = os.path.join(ROOT, rel, name)
            os.makedirs(d, exist_ok=True)
            # Always rewritten: these are derived files, and a stale description is
            # how a skill quietly stops being matched.
            with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as fh:
                fh.write(STUB % {"name": name, "description": description})
            written += 1

    for f in made:
        print("created  %s" % f)
    for f in kept:
        print("kept     %s (already present -- not overwritten)" % f)
    print("skills   %d adapter(s) in %s" % (written, ", ".join(sorted(want.values()))))

    print("""
Workspace ready. This machine's index starts at 001 and is not shared.

Next:
  1. Pick a journal in journals/journals.md, mark its Status/Machine row, and push
     that change -- before sweeping, so the other machine sees the claim.
  2. python3 journals/probe.py J01        # harvest + probe, zero model tokens
  3. Point your agent at AGENTS.md.

Mirror this folder to Drive. Git does not carry your papers, raw/ or audit reads.""")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
