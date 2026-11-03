# Frequently asked questions

## How do I start each skill?

Planning starts with the first conversation in [start your plan](setup.md#start-your-plan). Publishing starts after review in [prepare for GitHub](plan-owner-guide.md#prepare-for-github). The generated engineers' skill is the last step of publishing.

## npx: command not found

The terminal cannot find the installer command supplied by Node.js. Follow [the installation fix](setup.md#the-install-command-is-missing-or-blocked) for the checks and next action.

## Do I need a terminal?

You use one to install and check the skills. After installation, you work in your agent's chat. The [installation walkthrough](setup.md#install-the-two-skills) explains where to enter the commands and what to select.

## Which agents work?

Use a coding agent that supports Agent Skills and can read and edit project files and run commands. The [agent install list](setup.md#choose-a-coding-agent) provides setup links and supported choices.

## Do I need to install anything?

You need a coding agent, and the agent can do the rest. The first thing each skill does is check for Python 3.9 or newer. If Python is missing, it asks once whether to install it, and installs it from the official source after your yes. You still install Node.js and Git yourself, as the [computer preparation steps](setup.md#prepare-your-computer) show. If you would rather install Python yourself, [follow your system's steps](setup.md#before-anything-python).

## What do I need installed?

A coding agent, Node.js for the installer, Python for the scripts and Git. The [computer preparation steps](setup.md#prepare-your-computer) list versions and checks. Manual installation is available on the same page if you cannot use Node.js.

## What GitHub token permissions are required?

No token is needed to plan locally. Publishing issues and a project board requires a GitHub personal access token. The permissions depend on who owns the board:

| Board owner | Token | Required access |
| --- | --- | --- |
| Organization | Fine-grained token limited to the repository | Repository permissions **Issues: read and write** and **Metadata: read**; organization permission **Projects: read and write** |
| Your user account | Classic token | `repo` and `project` scopes |

GitHub does not currently let fine-grained tokens access user-owned projects. The token cannot give you access that your GitHub account does not already have, and an organization may require administrator approval. Follow [the token walkthrough](plan-owner-guide.md#the-token) to create, check, store and revoke it without putting it in the repository or chat.

## Can carrydown handle confidential documents and governance rules?

Yes, within stated limits. Governance rules, standards and company context go in as ground truth like any other document. Before it renders or copies anything, the agent asks one question: can everyone who can read this repository see all of these documents and your staffing notes? On yes it drafts in the repository as before. On no it drafts in a private workspace on your machine, and only outputs you approve are shared. For what carrydown protects and what it cannot, read the [enterprise security questions](enterprise-security.md). They carry one of three labels on each answer: supported, supported with prerequisites, or planned.

## Do my confidential documents end up in the project repository?

Not unless you say everyone who can read the repository may see them. The project holds the outputs you approved, never a restricted original or its full rendering. Originals are optional in the project even when a document is public, and the checks pass in a clean clone without them. An ignore rule keeps new files out of git, but it does not erase a file that an earlier commit already holds. The inventory command, `release.py inventory`, lists what a legacy project tracks and whether it is in history. Carrydown cannot rewrite history. See [who may see your documents](setup.md#before-you-add-documents-who-may-see-them).

## Can one engineer see a section that another engineer must not?

Not in version 1. The approved context of a work item is committed to the repository, so everyone who can read the repository can read every approved context. Leaving a section out of one item's context hides nothing from a teammate. Work that some of those readers must not see is withheld from the release as a restricted item, or needs a delivery mode that is planned and not available. A private repository is an access boundary for its readers. It does not separate them from each other. See [delivery modes](delivery-modes.md).

## Is the engineers' check a security control?

No. The check that the engineers' skill runs is a convenience and an integrity check in the engineer's own checkout, which the engineer can edit. The controls are the release gate on the plan owner's side and the independent verifier on pull requests, and an engineer can edit neither. The check also learns of a replacement or a withdrawal only after the receipt reaches the default branch the engineer fetches. An offline clone cannot learn it, and the first run in a clone needs a successful refresh.

## Can a released document be recalled?

No. Text already delivered, in a clone, a fork, an issue, a stored copy or an agent transcript, cannot be recalled. A withdrawal stops further publication and tells the engineers' check to stop on the next refresh. It does not remove anything. Immediate revocation is not an embedded-delivery promise.

## How quickly does the independent verifier notice a change?

Its workflow asks GitHub for a run every five minutes, and an administrator can start it by hand. Five minutes is a requested interval and not a deadline: GitHub can delay or drop scheduled runs. GitHub does not expire a successful check, so an outage can leave an old success mergeable, and state can change between a poll and a merge. An organization that needs authorization checked at the exact moment of merge has to add its own control. This reference deployment does not claim to be one. See [the limits in the setup guide](setup.md#limits-to-state-to-your-reviewers).

## Do hosted coding agents work?

They can read the approved contexts from the repository, so they need no local workspace. The engineers' check refreshes with a `git fetch` of the default branch, and whether a hosted environment allows that depends on the host. If the fetch fails, the check applies the offline grace rule or stops. Carrydown's tests do not run inside a hosted agent, so confirm the fetch behavior for yours.

## What are the private path and the organization setup?

The private path is for projects where some documents are not for everyone who can read the repository. It needs shared pieces that an organization administrator installs once: a tooling repository with the independent verifier, a private staging repository for each project, and a GitHub App that reports two required checks. The plan owner then runs a doctor command that says which pieces are verified. Without the organization's part, the private path is not available, and carrydown says so before it uploads anything. The real GitHub acceptance run of this setup has not been performed yet. See [organization setup for private drafting](setup.md#organization-setup-for-private-drafting).

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

Yes. Give the agent the files where you keep them, or keep a local copy in an ignored `docs/source/` folder. Word, Markdown and UTF-8 plain text render directly. The agent can inspect readable PDF, image and other files and create a Markdown rendering with numbered sections and provenance. Review extracted rules, tables and diagram meaning before planning. If one file cannot be read reliably, the agent records the coverage limit and continues with the readable sources. It stops only when none of the intended ground truth can be processed.

## Can skills and work preferences influence assignments?

Yes. The project lead can optionally supply each engineer's skills and preferred work. The agent compares them with the needs of the tracks and work items, proposes a best match and records its reasoning and tradeoffs. Required capabilities, fixed staffing decisions, availability, dependencies and delivery constraints take priority over preferences. The project lead approves the assignments.

Skills and preferences are never required. Missing, partial or ambiguous information does not fail or stop planning. The agent uses the default assignment approach based on tracks, capacity, dependencies and reduced context switching. The checker reports supplied staffing context but does not score or reject a match.

## What if my ground truth changes?

Update the source document, then review the affected plan and specifications with your agent. Follow [change the source document](plan-owner-guide.md#change-the-source-document) for the steps and publishing guidance.

## Can I change the plan after the issues exist?

Yes. Review local changes first, then preview the updates to GitHub. Existing issue bodies are updated only when requested, and issues are never deleted by the scripts. Follow [update the plan](plan-owner-guide.md#update-the-plan).

## Why work units and not sprints?

Time boxes of equal length force the work to fit the box. Work units take the length the work needs. They have exit gates. The carrydown skills avoid sprint, story point and velocity vocabulary, and the checker rejects it unless you configure otherwise.

## Why are people's names not allowed in specifications?

People change, and names are personal. Names, logins, skills, days off and allocations go in a private file on your machine, `people.yaml` in the private workspace, and never in `plan.yaml` or any file in the project. The plan holds ids and tracks. The checker merges the private file when you run it and keeps names out of the specification files so the files stay true when someone swaps in. Owners live in the GitHub issues, and you choose whether logins are published.

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
