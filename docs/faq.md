# Frequently asked questions

## npx: command not found

`npx` comes with Node.js, which is not installed on this computer or is not on your path. Go to https://nodejs.org, download the version marked LTS, run its installer, then close and reopen your terminal and your agent, and try again. You can also ask your agent: "Node.js seems to be missing. Tell me how to install it for this computer." If you cannot install Node.js, there is a path without it: copy the three folders in `skills/` of the repository into your agent's skills folder. The README's Install options section lists the folders.

## How do I start each skill?

Say one sentence per skill. "Set up a project plan from this document." "Create the GitHub issues and the board." "Generate the developer skill." If your agent does not pick the skill up, put "Use the carrydown-ground-truth skill." (or `carrydown-plan-to-github`, or `carrydown-dev-skill`) in front.

## Do I need a terminal?

Only for one command, the install line in the README's [Getting started](../README.md#getting-started). After that you talk to your agent. If you create a GitHub token, you can save it in a plain text file and give the agent the path, and the agent runs `github_token.py --from-file` for you, so there is no terminal prompt.

## Which agents work?

Any agent that reads Agent Skills. The installer supports more than seventy. The README lists them. The scripts also run by hand with Python.

## What do I need installed?

Node.js 22.20 or later, for the install command. Python 3.9 or later, for the scripts. Nothing else, not even for Word files. Your agent can check these and tell you.

## Does it write the code?

No. It carries the plan down to the point where an engineer and their agent can start work. The developer skill then makes each work item start from its specification.

## Does it write my architecture document?

No. The document must exist and be worth trusting. The carrydown skills render it, helps you review it with prompts, and cites it everywhere.

## My document is a Word file with no section numbers.

The agent will render it anyway. Specifications work best when sections have numbers, because every item cites the sections it comes from. Ask the agent to propose numbering for the source document. Change the source, not the rendering, and render again.

## What if my ground truth changes?

Edit the source, render again, and run the checker. It reports cited sections that no longer exist. Update `plan.yaml` if dates or dependencies change, then run `scaffold_spec.py --refresh-headers --apply` so every header follows the plan. Rewrite the issue bodies with `github_sync.py --update-bodies` only if you want GitHub to match the files.

## Can I change the plan after the issues exist?

Yes. Change `plan.yaml` and the specifications. New items are added on the next `--apply`. Existing issues are left alone unless you pass `--update-bodies`. Do not rename an item's title after creation, because issues are matched by exact title. To rename, change the title in GitHub first and then in the plan.

## Why work units and not sprints?

Time boxes of equal length force the work to fit the box. Work units take the length the work needs. They have exit gates. The carrydown skills avoid sprint, story point and velocity vocabulary, and the checker rejects it unless you configure otherwise.

## Why are people's names not allowed in specifications?

People change. Names go in `plan.yaml`, and the checker keeps them out of the specification files so the files stay true when someone swaps in. Owners live in the GitHub issues.

## What is a program input?

Something the program provides outside the plan, such as a pilot team, an approval or a review. Items that wait for one say "program input". The program's own items are not issues in the plan. They leave a gap in the numbering.

## What does the board script leave for me to click?

The script creates the fields and the views and sets each view's name, layout and visible fields. It does not yet set group by, sort order or the board's column field, although GitHub's endpoint for creating a view now accepts them. It also does not set the roadmap's date fields and zoom, slice by, field sums or the project workflows. You click those once. The list is printed at the end of `github_project.py` and written in the plan-to-github skill.

## Why do the work units show as breaks in the roadmap?

Between two iterations with a gap in the dates, GitHub shows a break. The scripts leave the gaps from your `breaks` list.

## Can I use Jira or another tracker?

The GitHub scripts are for GitHub only. The specification folder and `plan.yaml` are plain files, so another tool can read them. Contributions are welcome.

## Why not PyYAML?

So the scripts run on a stock Python with no installation. `plan.yaml` uses a small subset of YAML, described at the top of `scripts/carrydown_lib.py`.

## How do I remove it?

`npx skills remove`, or delete the skill folders. The files under `docs/` in your project are yours.

## Where do I report a bug?

On the repository, without any secret in the report.
