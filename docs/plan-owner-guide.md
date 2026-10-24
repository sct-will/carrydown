# Plan owner guide

The long form for a product manager, a program lead or anyone who owns a plan. You do not need to write code. The short form is the [Getting started](../README.md#getting-started) section of the README. It holds the install line and the three sentences you say to your agent. This guide does not repeat them. It explains what happens between them, what to review and what to ask for in advance.

## Who runs what

| Role | What they do | Which skill |
| --- | --- | --- |
| Plan owner | The engineering lead or product manager who owns the plan. Gives the documents and any constraints, answers the interview, approves the plan, says yes before anything is written to GitHub, and generates the developer skill. | `carrydown-ground-truth`, `carrydown-plan-to-github`, `carrydown-dev-skill` |
| Lead reviewer | A senior engineer who spends about an hour reading the generated specifications as the person who will build them. | Reviews the output of `carrydown-ground-truth` |
| Engineers | The people building the work items, each with their own coding agent. They start an item by naming it, for example "Work on WI-07". | The generated developer skill, made by `carrydown-dev-skill` |
| Program | The people who watch the demonstrations and decide pass or fail. They run nothing. They attend. | None |

## What you will end up with

You bring a document that says how the project must work, such as an architecture document. You and your agent turn it into:

- a plan with milestones, people, dates and dependencies,
- one specification file for each piece of work (a work item), each tied to the sections of your document it comes from,
- GitHub issues, one per work item, grouped under one issue per milestone,
- a GitHub Project board with the dates and the people filled in,
- a small skill linked from every issue, so each developer's agent reads the specification before it writes code.

Nothing is written to GitHub until you say yes. Work items are numbered WI-01, WI-02 and so on.

Two inputs: the ground truth documents, which are required, and your project constraints, which are optional. Constraints are the people with their percent allocation and the target date or number of weeks plus breaks, in any combination. Give both and the plan fits them. Give one and the agent backs into the other. Give neither and it proposes a default and asks. Allocation is assumed to be 100 percent for everyone. The agent asks you once to confirm, and you only name a figure for someone who is lower.

How long it takes. The interview and the plan review take an hour or two of your attention. The scripts take a few minutes. A senior engineer adds about an hour to review the specifications.

## Before you start

Things to ask for now, because they can take days:

- **Permission to create a Project** in your GitHub organisation, and to create issues in the repository. Ask an organisation administrator. If you do not have it yet, planning carries on. You only need it at the GitHub step.
- **Single sign-on approval.** If your organisation enforces single sign-on (SSO), your token must be approved for it. You do that yourself in two clicks (see "The token" below), but some organisations route it through an administrator.
- **Node.js and Python 3** on the computer where your agent runs. The README's Prerequisites section says what each is for. Your agent can check both.

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
5. which agents your team uses, who watches the demonstrations, and what the program owns and keeps outside the plan,
6. how the team runs tests and lint, and whether it uses a feature flag.

You can answer in plain words. If you do not know an answer, say "use your default" or "decide later". The agent reads everything back as a summary. Correct it, then say yes. Nothing is written before that.

## Reviewing the plan

The agent drafts. You decide. It shows you:

- the **milestones**, each with an exit gate you can check at a demonstration,
- the **work units** (the time blocks), with dates and your pauses,
- every **work item** with an owner, a date and what it depends on,
- the **load table**, how much work each person has in each work unit as a percentage of the capacity their allocation gives them, with any work unit over 100 percent flagged,
- the **critical path**, the chain of items that sets the end date, and whether it meets your target,
- the **program items** kept outside the plan.

Questions worth asking:

- What if one of the developers is out in week three?
- Which item can slip a week without moving the end date? Which cannot?
- Does anyone have nothing to do, or three things due, on any day?
- Which items wait for something the program owns?
- Which milestone has the weakest exit gate?

Ask the agent to move things, then ask for the load table and the critical path again. Say that the plan is right only when it is. This is your most important step.

## The lead reviewer hour

When a product manager drives, a senior engineer should spend about an hour as lead reviewer of the generated specifications. They read them as the person who will build the item and ask: could I start from this file alone? This catches wrong assumptions about the existing code, which the agent cannot always see.

You read the "Why this work item exists" and "Acceptance criteria" parts of a few specifications. They are short. Ask the agent to open one for you.

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

The agent runs a dry run first. A dry run changes nothing. It prints a summary line like "1 Epic, 5 sub-epics, 9 work item issues". Read the numbers, then say whether to go ahead. After the write it checks the counts through GitHub, builds the board and fills in the dates. Then it gives you a short list of settings that GitHub only lets a person click, such as how the board groups its cards, and tells you where.

## After that

The team follows a rhythm.

- When an item is finished, the developer posts a closing comment on its issue: what they can demonstrate, the evidence, the decisions, and what the other track needs to know.
- Every week the people meet for 30 minutes and run a joint check.
- At the end of each work unit the developers demonstrate the milestone to you, against criteria that were written before the work started. You note pass or fail on the milestone issue.

To change the plan later, change `plan.yaml` with your agent and run the checker again. [faq.md](faq.md) explains how to refresh the files and the issues.

## If something goes wrong

- A script fails. Ask the agent to show the message and explain it. Nothing is written until you said yes, and no script deletes anything.
- `npx: command not found`. Node.js is missing. See [faq.md](faq.md).
- A GitHub step is refused. The usual cause is single sign-on or a missing organisation permission. The token check names the fix.
- The agent does not pick up a skill. Put the skill name in front of the sentence, as the README says.
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
- **Demonstration.** A meeting at the end of a work unit where the people show the milestone working, against criteria written in advance.
- **Program item.** Work the program owns outside the development plan, such as recruiting a pilot team or getting an approval.
