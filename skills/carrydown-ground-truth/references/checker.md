# The checker

`scripts/check_specs.py` reads `plan.yaml` and the specification folder and reports faults. It never writes a file. Exit status is 0 when clean and 1 when there are findings.

```bash
python3 scripts/check_specs.py --root .            # everything
python3 scripts/check_specs.py --root . --item 3   # one item
python3 scripts/check_specs.py --root . --report   # schedule, load table, critical path
python3 scripts/check_specs.py --root . --json     # machine readable
```

## Plan checks

Required fields. Unique ids. Milestones numbered 1 to N in order, with ordered dates and a demonstration inside the work unit. Breaks that do not overlap a work unit. Each item has a known track, a known owner on the same track, a completion date inside its work unit on a weekday that is not a day off, a checkpoint that exists and is on or after the completion date. Dependencies refer to known items and finish no later than the item. No dependency cycle. If `unblocks` is written, it matches the inverse of `depends`.

## Item checks

- The file exists at `<spec_dir>/<milestone folder>/<id>-<slug>.md`.
- The title is `# <ID> <label>`.
- The header rows match the plan: Milestone, Track, Target, Checkpoint (right after Target), Demonstration, Size, Depends on (every id, plus a "program input" note exactly when the plan has one), Unblocks, Ground truth.
- The sections appear in the template order.
- Evidence of completion has a `Demo.` lead and at least four lines. Integration points has the three leads.
- Acceptance criteria has checkbox items.
- Decisions recorded says `None yet.` or has a dated entry.
- The file length is inside `limits.spec_lines`.
- No `TODO` markers remain.
- Banned vocabulary: dashes, names of people from the plan, AI vendor names, sprint words, "open questions", "non-goals".
- No reference to a program-owned id or to an id that does not exist.
- No broken relative link.
- If the ground truth headings are numbered, every section number in the Ground truth row exists.

## Milestone and folder checks

`milestone.md` has the title, the header rows, the five parts, at least three acceptance criteria, at least two outcomes and every item of the milestone. The README lists every item and has the comment templates. Files in a milestone folder that are not in the plan are reported as orphans.

## Configuring the vocabulary

In `plan.yaml`, under `banned`:

```yaml
banned:
  words: ["sprints?", "story points?", "velocity"]   # replaces the default word list
  phrases: ["open questions?", "non-goals?"]         # replaces the default phrase list
  vendors: ["acme assistant"]                        # extra names added to the built-in list
  names: ["Dr Smith"]                                # extra names. People in the plan are always banned.
  dashes: true                                       # reject em and en dashes
  skip_code_blocks: false                            # true to ignore fenced code
```

Entries are regular expressions matched whole-word and without regard to case.

## Continuous integration

`python3 scripts/scaffold_spec.py --root . --ci --apply` writes `.github/workflows/check-specs.yml` from `templates/check-specs-workflow.yml` and copies `check_specs.py` and `carrydown_lib.py` to `tools/carrydown/`. The workflow runs `python3 tools/carrydown/check_specs.py --root .` on every pull request and on pushes to the default branch. A finding exits with status 1, so the job fails and the pull request shows a red mark. Mark the job as required in branch protection to block merges. Copy the two scripts again when you update the kit.

## Reading the output

Each finding names the file and a line number when it can. Fix the source, not the checker. If a finding is wrong for your project, change the configuration in `plan.yaml` and say why in the commit message.
