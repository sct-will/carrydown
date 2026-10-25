# The project board

`github_project.py` creates or configures one GitHub Project (v2) for the plan. The project belongs to the GitHub account or organization you name with `--owner` (default: the repository owner) and is linked to the repository.

## Fields

| Field | Type | Values |
| --- | --- | --- |
| Work unit | Iteration | One iteration per milestone, titled `Work unit N, <name>`, with the start date and length from `plan.yaml`. |
| Track | Single select | One option per track, with the color from `plan.yaml`. |
| Complete by | Date | The completion date of the item. For a sub-epic, the milestone end. |
| Checkpoint | Date | The date of the item's checkpoint. For a sub-epic, the demonstration date. |

GitHub also provides Title, Assignees, Status, Labels, Parent issue and Sub-issues progress. Status keeps its default options.

## Work units of custom length

Each iteration has its own start date and duration in days, taken from the milestone dates. Days that fall between two iterations are a break. GitHub shows them as breaks in the Roadmap and on the iteration settings. The script lets each work unit run on to the day before the next one starts, so ordinary weekends are not breaks. A break from your `breaks` list is left as a real gap, from the break start to the day before the next work unit.

If the iterations on an existing project differ from the plan, the script says so and changes nothing. Pass `--reconfigure-iterations` to replace them. Replacing iterations can detach items from their old iteration, so rerun the script afterward to fill the field again.

## Views

The script ensures three views named Table, Board and Roadmap. A new project has one default table view called View 1. The script renames it Table. It sets the visible fields on all of them: Title, Assignees, Status, Work unit, Track, Complete by, Checkpoint and Parent issue.

## Items

Every sub-epic, work item issue and the Epic (if there is one) is added to the project. For each sub-epic and work item the script sets Work unit, Track (work items), Complete by and Checkpoint. A rerun skips values that are already right.

## What the script does not set yet

The script creates the fields and the views and sets each view's name, layout and visible fields. GitHub's endpoint for creating a view now also accepts group by, sort and the board column field, but the script does not set them yet. Give the user this list to click once:

1. Table view: group by Work unit (View menu, Group by). Sort by Complete by (View menu, Sort).
2. Board view: set the Column field to Status, or to Work unit for a board by work unit.
3. Roadmap view: choose the date fields (Complete by, and Checkpoint if you want markers), set the zoom level, show markers for iterations.
4. Optional: slice by Track and turn on field sums.
5. Project settings, Workflows: turn on Auto-add to project for the repository, and set Item closed to Status Done.
6. Optional: write a short project description and README in Settings.

The script prints this list at the end of every run.

## Rerunning

The script is safe to rerun. It finds the project by title (or by `--project-number`), keeps fields and views that exist, adds missing items and fills missing values.

## Verify

```bash
python3 <skill>/scripts/github_project.py --root . --repo owner/name --verify
```

It prints the count of plan issues on the board, the number of items with each field filled, the views and their layouts, and the project URL.
