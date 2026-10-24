# Plan owner guide

The long form for the plan owner: the engineering manager or product manager who owns the plan. You do not need to write code. The short form is the README: [Getting started](../README.md#getting-started) has the install line, and [What it sounds like](../README.md#what-it-sounds-like) has the sentences you say to your agent and what it replies. This guide does not repeat them. It explains what happens between them, what to review and what to ask for in advance.

## Who runs what

| Role | What they do | Which skill |
| --- | --- | --- |
| Plan owner | The engineering manager or product manager who owns the plan. Brings the ground truth and the constraints, answers the interview, reviews the generated plan and specifications with the agent, says yes before anything is written to GitHub, and gives the engineers the generated skill. | `carrydown-ground-truth`, then `carrydown-plan-to-github` |
| Engineers | The people building the work items, each with their own coding agent. They install the generated skill once, start an item by naming it, post evidence when it closes, and give the demonstrations. | The skill that `carrydown-plan-to-github` generates for the project |

Two skills you install, one skill is generated for your engineers. The demonstrations are watched by the people accountable for the outcome, who decide pass or fail against criteria written before the work. They run nothing.

The agent has no role. It drafts for the plan owner, reads for the engineers and carries the ground truth between them.

## What you will end up with

You bring a document that says how the project must work, such as an architecture document. You and your agent turn it into:

- a plan with milestones, people, dates and dependencies,
- one specification file for each piece of work (a work item), each tied to the sections of your document it comes from,
- GitHub issues, one per work item, grouped under one issue per milestone,
- a GitHub Project board with the dates and the people filled in,
- a small skill linked from every issue, so each engineer's agent reads the specification before it writes code.

Nothing is written to GitHub until you say yes. Work items are numbered WI-01, WI-02 and so on.

Two inputs: the ground truth documents, which are required, and your project constraints, which are optional. Constraints are the people with their percent allocation and the target date or number of weeks plus breaks, in any combination. Give both and the plan fits them. Give one and the agent backs into the other. Give neither and it proposes a default and asks. Allocation is assumed to be 100 percent for everyone. The agent asks you once to confirm, and you only name a figure for someone who is lower.

How long it takes. The interview and the plan review take an hour or two of your attention. Reviewing the specifications with the agent takes about another hour. The scripts take a few minutes.

## Before you start

Things to ask for now, because they can take days:

- **Permission to create a Project** in your GitHub organisation, and to create issues in the repository. Ask an organisation administrator. If you do not have it yet, planning carries on. You only need it at the GitHub step.
- **Single sign-on approval.** If your organisation enforces single sign-on (SSO), your token must be approved for it. You do that yourself in two clicks (see "The token" below), but some organisations route it through an administrator.
- **Node.js and Python 3** on the computer where your agent runs. Node.js runs the install line once, and Python runs the scripts. Your agent can check both, and [setup.md](setup.md) has the steps for each system.

Things to gather:

- Your document or documents, as .docx or .md files, in `docs/source/` in your project folder. If the document has no numbered sections, ask the agent to propose numbering in the source document, approve it, and have the agent render the document again.
- A project folder that is a git repository. The agent can create it for you.
- The facts the interview asks for. [inputs.md](inputs.md) lists them so you can prepare.

## The interview

The agent asks questions in six steps. Each reply starts with the line "carrydown: interview, step N of 6" so you know where you are. The steps cover:

1. your documents, and which one wins if two disagree,
2. your constraints, if any: the people, their tracks, their percent allocation (assumed 100, confirmed once), GitHub logins, start dates and days off,
3. the target as a date or a number of weeks, if you have one, the breaks, and the longest stretch of work you allow in one block,
4. your GitHub repository, the branch, and whether an Epic issue exists,
5. which agents the engineers use, who watches the demonstrations, and what work is owned outside the team,
6. how the engineers run tests and lint, and whether they use a feature flag.

You can answer in plain words. If you do not know an answer, say "use your default" or "decide later". The agent reads everything back as a summary. Correct it, then say yes. Nothing is written before that.

## Reviewing the plan

The agent drafts. You decide. It shows you:

- the **milestones**, each with an exit gate you can check at a demonstration,
- the **work units** (the time blocks), with dates and your pauses,
- every **work item** with an owner, a date, what it depends on and a size such as "Small, about 2 days" (the load table reads the number after "about"),
- the **load table**, how much work each person has in each work unit as a percentage of the capacity their allocation gives them, with any work unit over 100 percent flagged,
- the **critical path**, the chain of items that sets the end date, and whether it meets your target,
- the **work the plan does not schedule**, owned outside the team and left as gaps in the numbering,
- the **rationale**: for each milestone, why it holds its items and what the engineers show together at its demonstration, and for each track, why its items are in this order,
- the **planning review**, the last block of the checker report, which lists the tracks each milestone covers, items with no slack before their checkpoint, theme switches, critical path owners and the load ratio.

Questions worth asking:

- What if one of the engineers is out in week three?
- Which item can slip a week without moving the end date? Which cannot?
- Does anyone have nothing to do, or three things due, on any day?
- Which items wait for work owned outside the team?
- Which milestone has the weakest exit gate?
- Is each stated reason true of the dates? Pick one and check it against the schedule.

Ask the agent to move things, then ask for the load table and the critical path again. Say that the plan is right only when it is. This is your most important step.

## Reviewing the specifications

Before anything goes to GitHub, you review the generated specifications with the agent, for about an hour. There is no separate reviewer. Ask the agent to take you through them one at a time, and read each as the engineer who will build the item: could they start from this file alone? Begin with "Why this work item exists" and "Acceptance criteria". They are short. Ask the agent to show you the existing code a specification relies on, because a wrong assumption about that code is the mistake it is most likely to make. Ask for changes in plain words. The agent edits the files and runs the checker again.

The checker compares every specification to the plan. It runs on your computer, and the agent can add it to continuous integration (CI, the automatic checks on every pull request). In CI it fails loudly: a red mark on any pull request that makes a specification disagree with the plan. Ask the agent to add the specification checker to CI.

## The token

A token is a long password that lets the scripts create issues and a Project for you. The agent gives you the link. Open it yourself.

1. **Pick the kind.** If an organisation owns the board, create a fine-grained token at https://github.com/settings/personal-access-tokens/new for the one repository, with Issues read and write, Metadata read, and the organisation permission Projects read and write. Only if your own user account owns the board, use a classic token from the pre-filled link https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown. It ticks `repo` and `project` for you.
2. **Set the expiry to 7 days.** Click Generate token. Copy the token. GitHub shows it once.
3. **Save it in a plain text file outside your project**, for example `Downloads/token.txt`. In TextEdit, choose Format, then Make Plain Text, before you save.
4. **Tell the agent the file path.** Do not paste the token into the chat. The agent never opens the file. It runs the token script with `--from-file`. The script reads the file, stores the token at `~/.config/carrydown/github_token` where only you can read it, and checks what the token can do. It keeps your file.
5. **Delete your file.** It still holds the token in plain text.
6. **Read the check.** The agent runs the check. It says who owns the token, what it can do and whether the repository is reachable.

When the plan and the board are on GitHub, revoke the token at github.com/settings/tokens. Make a new one if you need it again.

Instead of steps 3 to 5 you can run the token script yourself in a terminal and type the token at the prompt. The characters do not appear as you type.

If the check fails, it names the fix:

- **Single sign-on.** Go to github.com/settings/tokens, find the token, click its "Configure SSO" button, and click "Authorize" next to your organisation. Then ask the agent to run the check again.
- **Missing organisation permission.** Ask an organisation administrator for permission to create issues and Projects.

If you think the token leaked, revoke it at github.com/settings/tokens and make a new one. [security.md](security.md) has the details.

## The GitHub step

The agent runs a dry run first. A dry run changes nothing. It prints a summary line like "1 Epic, 5 sub-epics, 9 work item issues". Read the numbers, then say whether to go ahead. After the write it checks the counts through GitHub, builds the board and fills in the dates. Then it gives you a short list of settings that GitHub only lets a person click, such as how the board groups its cards, and tells you where. Last, it generates the engineers' skill and gives you the install line to send each engineer.

## After that

The engineers follow a rhythm.

- When an item is finished, the engineer posts a closing comment on its issue: what they can demonstrate, the evidence, the decisions, and what the other track needs to know.
- Every week the engineers meet for 30 minutes and run a joint check.
- At the end of each work unit the engineers demonstrate the milestone to the people accountable for the outcome, against criteria that were written before the work started. They decide pass or fail, and the outcome is noted on the milestone issue the same day.

To change the plan later, change `plan.yaml` with your agent and run the checker again. [faq.md](faq.md) explains how to refresh the files and the issues.

## If something goes wrong

- A script fails. Ask the agent to show the message and explain it. Nothing is written until you said yes, and no script deletes anything.
- `npx: command not found`. Node.js is missing. See [faq.md](faq.md).
- A GitHub step is refused. The usual cause is single sign-on or a missing organisation permission. The token check names the fix.
- The agent does not pick up a skill. Put the skill name in front of the sentence, as the [FAQ](faq.md#how-do-i-start-each-skill) shows.
- You want to start over. Delete the `docs/spec/` folder in your project and ask again. The scripts never touch your source documents.

## Glossary

- **Ground truth.** The document or documents the project must obey, such as an architecture document, requirements, rules and standards.
- **Agent Skills.** An open format for packaging instructions for a coding agent as a folder with a `SKILL.md` file.
- **Epic.** A parent GitHub issue that stands for the whole project.
- **Sub-epic.** An issue for one milestone, placed under the Epic.
- **Sub-issue.** An issue placed under another issue. Each work item is a sub-issue of its sub-epic.
- **Iteration field.** A GitHub Project field that groups items into time blocks with start dates and lengths. Here it is called Work unit.
- **YAML.** A plain text format for structured data. `plan.yaml` holds the plan in it.
- **Load table.** A table of how much work each person has in each work unit.
- **Critical path.** The longest chain of items that depend on each other. It sets the earliest finish date.
- **Exit gate.** The one sentence that must be true for a work unit to count as done.
- **Work unit.** A time block with its own length and an exit gate. It replaces the fixed-length sprint.
- **Checkpoint.** A short weekly meeting where the tracks run a check together to prove their halves fit.
- **Demonstration.** A meeting at the end of a work unit where the engineers show the stakeholders the milestone working, against criteria written in advance.
- **Work the plan does not schedule.** Work owned outside the team, such as recruiting a pilot team or getting an approval. It keeps an id, left as a gap in the numbering, and is listed under `program` in `plan.yaml`. An item that waits for it carries a "program input" note.
