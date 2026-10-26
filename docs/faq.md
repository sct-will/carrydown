# Frequently asked questions

## How do I start each skill?

Planning starts with the first conversation in [start your plan](setup.md#start-your-plan). Publishing starts after review in [prepare for GitHub](plan-owner-guide.md#prepare-for-github). The generated engineers' skill is the last step of publishing.

## npx: command not found

The terminal cannot find the installer command supplied by Node.js. Follow [the installation fix](setup.md#the-install-command-is-missing-or-blocked) for the checks and next action.

## Do I need a terminal?

You use one to install and check the skills. After installation, you work in your agent's chat. The [installation walkthrough](setup.md#install-the-two-skills) explains where to enter the commands and what to select.

## Which agents work?

Use a coding agent that supports Agent Skills and can read and edit project files and run commands. The [agent install list](setup.md#choose-a-coding-agent) provides setup links and supported choices.

## What do I need installed?

A coding agent, Node.js for the installer, Python for the scripts and Git. The [computer preparation steps](setup.md#prepare-your-computer) list versions and checks. Manual installation is available on the same page if you cannot use Node.js.

## Isn't this just prompts?

No. The checker is code, and it fails continuous integration when a specification breaks the rules. The board is built through the GitHub application programming interface (API) by scripts. The specifications and the plan are files in Git that you can read, diff and review. The prompts are the smallest part.

## Isn't this waterfall?

No. The plan is files in Git, so changing it is cheap. Work units stretch to fit the work and are not fixed-length boxes. Every contradiction found in the document or the plan goes back into the next version of that document. You can plan, build a little, learn and change the plan as often as you need.

## How does this compare with plan mode, spec-driven tools, Superpowers and Claude Code Project Management (CCPM)?

Plan mode and spec-driven tools plan one task or one feature from a specification. Superpowers is a library of skills for how an agent works. CCPM is a project management workflow that turns requirement documents into GitHub issues. The carrydown skills carry one agreed ground truth across every task. They date the plan around named people with their allocation, check every specification against that plan, fill the board and generate the engineers' skill. They can sit beside any of those tools.

## What does it cost in AI usage?

Here cost means your agent's model usage, the amount of text the AI model reads and writes. It is separate from the GitHub token.

The planning run reads the whole document once and writes one specification per item, so the cost grows with the number of items. The generated skill loads one specification and the cited sections each time an engineer starts an item, not the whole document. The two skill descriptions are kept short so they stay in every session's listing.

## Does it write the code?

No. It carries the plan down to the point where an engineer and their agent can start work. The engineers' skill then makes each work item start from its specification.

## Does it write my architecture document?

No. The document must exist and be worth trusting. The carrydown skills render it, help you review it with prompts, and cite it everywhere.

## My document is a Word file with no section numbers.

The agent can render it. Numbered sections make citations easier to maintain. Ask the agent to propose numbering in the source document and review it before planning.

## Can the ground truth include PDF, images or plain text?

Yes. Put the files together in `docs/source/`. Word, Markdown and UTF-8 plain text render directly. The agent can inspect readable PDF, image and other files and create a Markdown rendering with numbered sections and provenance. Review extracted rules, tables and diagram meaning before planning. If one file cannot be read reliably, the agent records the coverage limit and continues with the readable sources. It stops only when none of the intended ground truth can be processed.

## What if my ground truth changes?

Update the source document, then review the affected plan and specifications with your agent. Follow [change the source document](plan-owner-guide.md#change-the-source-document) for the steps and publishing guidance.

## Can I change the plan after the issues exist?

Yes. Review local changes first, then preview the updates to GitHub. Existing issue bodies are updated only when requested, and issues are never deleted by the scripts. Follow [update the plan](plan-owner-guide.md#update-the-plan).

## Why work units and not sprints?

Time boxes of equal length force the work to fit the box. Work units take the length the work needs. They have exit gates. The carrydown skills avoid sprint, story point and velocity vocabulary, and the checker rejects it unless you configure otherwise.

## Why are people's names not allowed in specifications?

People change. Names go in `plan.yaml`, and the checker keeps them out of the specification files so the files stay true when someone swaps in. Owners live in the GitHub issues.

## What is an external input?

Something an item needs from work owned outside the team, such as a pilot team, an approval or a review. Items that wait for one say "external input". That work is an external item. The plan does not schedule it, so it is not an issue in the plan. It keeps an id, left as a gap in the numbering, under `external` in `plan.yaml`.

## What does the board script leave for me to click?

The agent gives you a list after it creates the board. It includes view settings such as grouping, sorting and roadmap dates, plus workflows. Finish those settings in GitHub as part of [the publishing steps](plan-owner-guide.md#the-github-step).

## Why do the work units show as breaks in the roadmap?

Between two iterations with a gap in the dates, GitHub shows a break. The scripts leave the gaps from your `breaks` list.

## Can I use Jira or another tracker?

The GitHub scripts are for GitHub only. The specification folder and `plan.yaml` are plain files, so another tool can read them. Contributions are welcome.

## Why not PyYAML?

So the scripts run on a stock Python with no installation. `plan.yaml` uses a small subset of YAML, a plain text format for settings, described at the top of `scripts/carrydown_lib.py`.

## How do I remove it?

`npx skills remove`, or delete the skill folders. The files under `docs/` in your project are yours.

## Where do I report a bug or a security issue?

Report a bug with [the bug report form](https://github.com/sct-will/carrydown/issues/new?template=bug_report.yml) on the carrydown repository. Leave out any token, password or private document text.

Report a security issue privately. Do not open a public issue for it. Use GitHub private vulnerability reporting through [the private report form](https://github.com/sct-will/carrydown/security/advisories/new) on the carrydown repository. Only the maintainer can read what you send. [SECURITY.md](../SECURITY.md) says what to put in the report and when to expect a reply.
