# Recover a plan or publication

Recovery starts with a concrete preview. Local repairs write only with `--apply`. GitHub repairs also require separate approval for each run. They never delete or close duplicate issues. Owners, dates, scope and order stay with the plan owner.

## Repair local identities and source references

Run these commands from the project root. Replace `<skill>` with either installed carrydown skill folder.

```bash
python3 <skill>/scripts/plan_repair.py --root .
python3 <skill>/scripts/plan_repair.py --root . --apply
```

The preview lists changed records, affected references and a plan diff. Exactly identical people, tracks, external items and checkpoints collapse. Duplicate display labels include their existing track IDs. External item IDs become distinct without changing work-item IDs. Different people get IDs from their names. Different tracks get IDs from their labels. Ownership changes only when one candidate matches the item's track. Ambiguous track references remain decisions.

Different checkpoints on one date require confirmation of a combined checkpoint. Its proposed name and joint check retain both records. Its date stays the same. No source is selected just because it is first in a list.

When choices remain, the command returns 1 without writing. It prints JSON records with `path`, `question` and `options`, then asks for one combined decision. Save a JSON mapping from each path to the selected concrete option:

```json
{
  "items.1.owner": "alex-quill",
  "items.2.track": "frontend"
}
```

```bash
python3 <skill>/scripts/plan_repair.py --root . --decisions docs/repair-decisions.json
python3 <skill>/scripts/plan_repair.py --root . --decisions docs/repair-decisions.json --apply
```

Use exactly the value printed in an option, including the entire object for a combined checkpoint. The plan owner can instead edit the canonical plan to supply explicit source sections. The next preview checks that plan again.

Every item needs provenance in the plan. A specification row alone does not satisfy this requirement. A legacy `ground_truth` citation converts when it names one reviewed source or uses the explicitly configured legacy primary source. It must contain explicit section syntax, such as `Sections 3.1, 3.2`, and every section must be a heading in that readable source. A version number, item ID or number in prose is not a section citation.

A specification can provide recovery evidence only when it names one reviewed source and explicit sections. Without provable sections, the preview proposes `whole document` coverage for the plan owner to confirm. Unknown sources, unreadable sources and empty references need a decision. Repeated source references merge without losing distinct sections. Unreadable sources are never adopted automatically.

Apply writes the canonical plan first. It validates the plan, refreshes specification headers and generated planning text, refreshes existing engineers' skill references and runs the full checker. Remaining problems return nonzero. Formatting and comments are replaced by a normalized representation in the supported YAML subset, so review the diff before applying. Repeated repair makes no further canonical changes.

Both skills carry `plan_repair.py`, `scaffold_spec.py` and `generate_dev_skill.py` because recovery refreshes existing local generated material. The first skill still never publishes. The publishing skill carries the scaffold templates needed for recovery. The sample's checker library receives the same validation changes through asset synchronization.

## Resolve GitHub issue identity

The scripts save verified repository, issue number and issue ID mappings in `docs/spec/github-issues.json` only during apply. Keep this file with the plan. A mapping is verified on every run. Otherwise the scripts compare all matching markers and legacy titles. A duplicate is adopted only when exactly one candidate has canonical managed content and metadata. Issue number ordering never decides identity.

A tie prints a table with marker, title, state, labels and assignees. Choose one issue with `--select-issue WI-01=123`, preview it, then ask for approval before adding `--apply`. The preview identifies every duplicate marker that would be replaced by a nonmatching duplicate note. Comments, human text, labels and issue state remain. The metadata repair command accepts the same selection flag.

## Reconcile published issues and the board

```bash
python3 <skill>/scripts/github_sync.py --root . --reconcile
python3 <skill>/scripts/github_sync.py --root . --reconcile --apply
python3 <skill>/scripts/github_sync.py --root . --verify
python3 <skill>/scripts/github_project.py --root .
python3 <skill>/scripts/github_project.py --root . --apply
python3 <skill>/scripts/github_project.py --root . --verify
```

Each apply needs its own preview and approval. Public repositories also need `--allow-public`. Issue verification compares each issue's title, managed body and links, marker, required labels, planned assignee, parent and relevant state. Reports include work-item ID, issue number, expected value and actual value. Open and closed are valid unless an item explicitly declares `state`. Unrelated labels and assignees remain.

New issue bodies have managed start and end comments. Reconciliation changes that region and keeps text outside it. Legacy bodies have no reliable ownership boundary. If their content differs, reconciliation retains the entire previous body under `Preserved existing issue text` while installing the authoritative managed region. Human comments are never rewritten.

Board apply restores missing membership and managed fields. It adds missing Track options while retaining unrelated identifiers, names, colors and descriptions. Existing option identifiers are included in the update as required by the [GitHub input reference](https://docs.github.com/en/graphql/reference/projects#projectv2singleselectfieldoptioninput), so existing item values remain attached. Option names match without case sensitivity. Options differing only by case need an explicit rename before retrying. The field is re-read after mutation to verify new and existing option identifiers. Work unit iteration changes still need `--reconfigure-iterations`.

Project, field, view, item, item-value and nested view-field connections follow continuation tokens to the last page. A later-page failure names its connection and continuation token. Transient reads and idempotent field assignments retry a bounded number of times. Permanent errors identify the issue, field and intended value. Successful partial updates remain. Reruns repair only remaining drift.

Both apply paths verify after writing and return nonzero for required drift. Run both verification commands: each covers its own publication surface. View grouping, sorting and workflows still need the manual clicks printed by the board command.

## Keep token sources safe

`github_token.py --from-file PATH --delete-after --repo owner/name` deletes only the explicitly named regular file after authentication, repository access and permission checks pass. It rejects symlinks and directories and checks the file identity again before deletion. An environment variable is never a deletion target. Failures retain the source and report that it was retained.

Fine-grained write permissions cannot all be proven through the read-only API. In that case automatic deletion is refused. Confirm permissions with the plan owner and delete the source manually after successful publication. The default remains to keep it.

## Run offline tests

```bash
python3 scripts/selftest.py
python3 scripts/lint_prose.py
python3 scripts/check_specs.py --root sample/expense-approvals --report
python3 -m unittest discover -s tests -v
python3 scripts/sync_skill_assets.py --check
```

The suite uses separate temporary projects and mocked REST and GraphQL responses. Continuous integration runs Python 3.9 and the current stable Python on Ubuntu, macOS and Windows. Tests cover path separators, Unicode, newlines, temporary files, pagination, identity decisions, reconciliation, permission failures, retries and token retention.

Live GitHub mutation tests remain optional. A plan owner may approve them in a disposable private repository after reviewing the exact dry run. Keep the token outside the project. The default suite never runs them.

Default prose lint includes tracked candidates and untracked nonignored candidates. Ignored scratch cannot fail it. Explicit filenames still work for ignored files. `--all` includes ignored candidates but excludes build, dependency and virtual environment folders. Outside Git, paths are sorted with the same folder exclusions. Every finding includes its file and line.
