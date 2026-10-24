# Frequently asked questions

## npx: command not found

`npx` comes with Node.js, which is not installed on this computer or is not on your path. Go to [the Node.js website](https://nodejs.org), download the version marked LTS (long-term support), run its installer, then close and reopen your terminal and your agent, and try again. You can also ask your agent: "Node.js seems to be missing. Tell me how to install it for this computer." If you cannot install Node.js, there is a path without it: copy the two folders in `skills/` of the repository into your agent's skills folder. The README's Install options section lists the folders.

## How do I start each skill?

Two skills you install, one skill is generated for your engineers. Say one sentence per skill: "Set up a project plan from this document." and then "Put the plan on GitHub." The last step of the second skill generates the engineers' skill. To run that step on its own, say "Generate the engineers' skill." If your agent does not pick a skill up, put "Use the carrydown-ground-truth skill." (or `carrydown-plan-to-github`) in front.

## Do I need a terminal?

Only for one command, the install line in the README's [Getting started](../README.md#getting-started). After that you talk to your agent. If you create a GitHub token, you can save it in a plain text file and give the agent the path, and the agent runs `github_token.py --from-file` for you, so there is no terminal prompt.

## Which agents work?

Any agent that reads Agent Skills. The installer supports more than seventy. The README lists them. The scripts also run by hand with Python.

## What do I need installed?

Node.js 22.20 or later, for the install command. Python 3.9 or later, for the scripts. Nothing else, not even for Word files. Your agent can check these and tell you.

## Isn't this just prompts?

No. The checker is code, and it fails continuous integration when a specification breaks the rules. The board is built through the GitHub API by scripts. The specifications and the plan are files in Git that you can read, diff and review. The prompts are the smallest part.

## Isn't this waterfall?

No. The plan is files in Git, so changing it is cheap. Work units stretch to fit the work and are not fixed-length boxes. Every contradiction found in the document or the plan goes back into the next version of that document. You can plan, build a little, learn and change the plan as often as you need.

## How does this compare with plan mode, spec-driven tools, Superpowers and CCPM?

Plan mode and spec-driven tools plan one task or one feature from a specification. Superpowers is a library of skills for how an agent works. CCPM is a project management workflow that turns requirement documents into GitHub issues. Carrydown carries one agreed ground truth across every task. It dates the plan around named people with their allocation, checks every specification against that plan, fills the board and generates the engineers' skill. It can sit beside any of them.

## What does it cost in tokens?

The planning run reads the whole document once and writes one specification per item, so the cost grows with the number of items. The generated skill loads one specification and the cited sections each time an engineer starts an item, not the whole document. The two skill descriptions are kept short so they stay in every session's listing.

## Does it write the code?

No. It carries the plan down to the point where an engineer and their agent can start work. The engineers' skill then makes each work item start from its specification.

## Does it write my architecture document?

No. The document must exist and be worth trusting. The carrydown skills render it, help you review it with prompts, and cite it everywhere.

## My document is a Word file with no section numbers.

The agent will render it anyway. Specifications work best when sections have numbers, because every item cites the sections it comes from. Ask the agent to propose numbering for the source document. Change the source, not the rendering, and render again.

## What if my ground truth changes?

Edit the source, render again, and run the checker. It reports cited sections that no longer exist. Update `plan.yaml` if dates or dependencies change, then run `scaffold_spec.py --refresh-headers --apply` so every header follows the plan. Rewrite the issue bodies with `github_sync.py --update-bodies` only if you want GitHub to match the files.

## Can I change the plan after the issues exist?

Yes. Change `plan.yaml` and the specifications. New items are added on the next `--apply`. Existing issues are left alone unless you pass `--update-bodies`. Renaming an item is safe: issues are matched by a hidden marker in the body, so a rerun finds the issue under its new label.

## Why work units and not sprints?

Time boxes of equal length force the work to fit the box. Work units take the length the work needs. They have exit gates. The carrydown skills avoid sprint, story point and velocity vocabulary, and the checker rejects it unless you configure otherwise.

## Why are people's names not allowed in specifications?

People change. Names go in `plan.yaml`, and the checker keeps them out of the specification files so the files stay true when someone swaps in. Owners live in the GitHub issues.

## What is an external input?

Something an item needs from work owned outside the team, such as a pilot team, an approval or a review. Items that wait for one say "external input". That work is an external item. The plan does not schedule it, so it is not an issue in the plan. It keeps an id, left as a gap in the numbering, under `external` in `plan.yaml`.

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
