# Engineers' skill for Expense approvals

The engineers' skill for the Expense approvals work in this repository. It follows the Agent Skills format, a folder with a `SKILL.md` and reference files, so any coding agent that supports skills can load it.

When an engineer asks the agent to work on a work item by id (WI-01), or touches the files an item names, the skill gives the agent the steps to orient on the item, the project conventions, the definition of done and the test commands. Its reference files hold the work item index, the contract headings and the map of approved source sections. Its `scripts/check_context.py` checks that the approved context and the specification of an item can be used before the agent reads them.

## Why use it

Without the skill, a coding agent tends to invent function names, skip the feature flag, drift from the contracts or work from memory instead of the specification. When you ask it to work on a work item id, the skill orients the agent on that one item. It reads the specification and the approved context of the item, then the project conventions, before it changes code. The approved context is one file, `docs/context/<id>.md`, with the exact text of the source sections the item must honor. You review every change.

## What to say to your agent

| What you want to do | What to say |
| --- | --- |
| Start a work item | "Work on WI-01." |
| Raise a specification problem | "This specification seems wrong because [explanation]." |

The agent drafts the second one as a `Rule clarification request` and shows it to you. It is delivered only after you say yes and an authorized tool can post it. Until then it is labeled "not sent".

## What is in this folder

| File | Contents |
| --- | --- |
| `SKILL.md` | How to orient on a work item, the project conventions and tests, the definition of done, and when to read each reference. |
| `references/work-items.md` | The 9 work items with track, date, dependencies and specification path, and the external items. |
| `references/contracts.md` | Where each contract is defined and the headings of every Contract or Protocol section. |
| `references/ground-truth-map.md` | The source sections inside the approved contexts, by source id and section number, and the sections each work item holds. It names no original file. |
| `scripts/check_context.py` | The check an engineer runs for one work item id. It prints a short block and exits 0, or prints one of six messages and stops. |

## Install

Choose one option. Install it once per computer or once per project. Then start a new session in your agent so it picks up the skill.

### Option 1, the skills command line tool

Run one line for your agent, in your own terminal. An agent that reads this file prints the line for you and does not run it. Add `-g` to install for your user account instead of this project, and keep the `-a` value: without it, `-g` writes into the folder of every agent the tool supports. The tool copies the folder, so run the line again after the skill changes.

```bash
npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a claude-code
npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a github-copilot
npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a cursor
npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a codex
npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a gemini-cli
npx skills add https://github.com/sct-will/carrydown-sample/tree/main/docs/dev/skills/expense-approvals-dev -a bob
```

The general form is `npx skills add <repository tree url for this folder> -a <agent>`. The agent names come from the skills tool; run `npx skills add --help` or see [the installer's list of agents](https://github.com/vercel-labs/skills/blob/main/docs/agents.md) for the full list. If the repository is private, the tool uses the Git credentials already configured on your computer.

### Option 2, copy or link the folder

A symlink keeps the installed skill in step with the repository, so `git pull` updates it. On macOS or Linux, write the absolute path of the repository in place of `<absolute path of the repository>`:

```bash
ln -s "<absolute path of the repository>/docs/dev/skills/expense-approvals-dev" <skills folder>/expense-approvals-dev
```

On Windows, from a Command Prompt with Developer Mode on:

```bat
mklink /D <skills folder>\expense-approvals-dev "<absolute path of the repository>\docs\dev\skills\expense-approvals-dev"
```

`<skills folder>` is where your agent looks for skills:

| Agent | Project folder | User folder |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `.agents/skills/` | `~/.agents/skills/` |
| Cursor | `.agents/skills/` | `~/.agents/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `.agents/skills/` | `~/.agents/skills/` |
| IBM Bob | `.bob/skills/` | `~/.bob/skills/` |
| Any other agent that reads Agent Skills | its skills folder | its user skills folder |

### Option 3, no installation

Ask your agent: "Read docs/dev/skills/expense-approvals-dev/SKILL.md and follow it for work item WI-01." This works in any agent that can read files.

## The approved inputs, and the check that guards them

Each work item has a bundle in `docs/context/`: `<id>.md` for the agent and `<id>.bundle.json` beside it. The Markdown holds the verbatim text of the source sections the item cites, the decisions that settle a conflict between them, the other items that cite the same sections and what the text may be used for. The plan owner approved this text for everyone who can read this repository. Anyone with read access can read every bundle, so nothing is hidden from a teammate by leaving it out of an item's bundle.

The first command your agent runs for a work item is the check, before it reads anything:

```bash
python3 docs/dev/skills/expense-approvals-dev/scripts/check_context.py WI-01
```

On Windows, from a Command Prompt or PowerShell in the repository:

```bat
py -3 docs\dev\skills\expense-approvals-dev\scripts\check_context.py WI-01
```

If the command is not found, or Python is older than 3.9, the agent follows `references/preflight.md` in the skill folder: it checks Python, offers to install it, and runs the check again.

The check works in this order. It reads only this repository, and its one network use is a `git fetch` of the default branch with the Git credentials you already have.

1. Local validity, offline. The bundle files exist, the Markdown matches the digest in its sidecar, every source section the specification cites is in the bundle, and a receipt in `docs/release/` marked active lists both files with the same digests.
2. The approved inputs, offline. One active receipt must also list, with the same digests, the specification of the item, the released plan, the specification folder README, the `SKILL.md` and `README.md` of this skill, and the whole specification of every other work item that the specification names under "Integration points" or "References". Where the project lets engineers record decisions, your specification may differ from its approved text by new dated entries under "Decisions recorded" and nothing else. The check reads the approved text from git history, and only a version whose digest matches the receipt counts. It records the digest of your entries as evidence. That digest is not an approval. Where the project takes changes as requests, any change to an approved specification fails the check.
3. Freshness. It fetches the default branch and reads the receipts there. A release that was superseded or withdrawn makes the inputs stale. A receipt that is newer and terminal is never replaced by an older active one in your checkout.
4. Offline grace. If the fetch fails, it carries on only when your last good refresh is on record for this repository and this release and is no older than the grace period in the receipt (7 days by default). It then prints `warning: freshness not confirmed; within offline grace`. With no record, or past the grace period, the context is stale. The first time you run the check in a clone there is no record, so that first fetch has to succeed: a new clone gets no grace before one successful refresh. A refresh counts only when the check read the receipts on the default branch and found the bundle in them. Fetching some other branch does not count.
5. Expiry. The receipt may carry an expiry date, compared with your computer's clock.
6. The approved delta. After a good fetch the check compares the approved inputs with the ones it recorded at your last check of this item. If any changed, it prints which files changed and the changed passages, read from git history, then tells the agent to reassess the implementation plan. If your clone holds no copy of the previous version, it says so, and the agent loads the current approved inputs in full. The check never pulls, merges or changes a file in your working tree.

**What the check is and is not.** The check lives in your checkout, so you can edit it. It is a convenience and an integrity check for you. It is not a security control. The controls are the release gate that runs on the plan owner's side and the independent check on pull requests. Text already copied into a clone, a transcript or an agent session cannot be recalled. The check cannot learn of a release or a withdrawal your clone has not seen, which is why it refreshes first and allows only a short, recorded grace period when it cannot.

## When the project changes

The plan owner can change the project after planning: a requirement is revised, a company rule changes or an engineer's correction is accepted. Approved updates reach you through the repository. Run the check again for your work item, for example when you start a session or before you open a pull request. If the approved inputs changed since your last check, it prints the delta, and your agent reassesses the implementation plan before it writes more code. A change does not reach an agent that is already running until the check runs again. Pull the default branch the normal reviewed way. The check never does it for you.

The plan owner's notice about when to tell the agent that the project changed is in `docs/spec/README.md`. It is not repeated here.

## If you are blocked

The check prints one of six messages and stops. It never prints withheld text, the headings of restricted sources, private paths or the names of approvers.

| First line of the message | What happened | What you do |
| --- | --- | --- |
| `carrydown: no approved context for <ID>` | There is no bundle for the item, the bundle fails its integrity check, or no active release lists it. The id may also be unknown. | Ask the plan owner to release the item. |
| `carrydown: the approved context for <ID> is stale` | Its release was superseded, withdrawn or has expired, the default branch does not confirm it, or freshness could not be confirmed within the offline grace period. The next line gives the reason. | Ask the plan owner to re-release, or connect to the network and run the check again. |
| `carrydown: <ID> cites an obligation that is not in its approved context` | The specification cites a source section that the bundle does not contain. | Ask the plan owner. Do not guess the rule. |
| `carrydown: <ID> has a restricted destination that this project does not publish` | The plan owner published a placeholder that says this item is handled outside this project. | Follow the owner's approved instruction in the placeholder. |
| `carrydown: the specification for <ID> does not match its approved release` | The specification file is missing, there is more than one, the release does not list it, it differs from the approved text outside the notes this project allows, or git holds no copy of the approved text to compare with. The next lines name the file and the reason. | Restore the approved file. If a rule looks wrong, draft a request (below). Do not edit around the check. |
| `carrydown: the approved inputs for <ID> come from more than one release` | The files you hold match different releases, so no single release covers them all. Or two active releases list the item and disagree, so you cannot tell which one is in force. | Pull the default branch the normal way so every approved file comes from one release, then run the check again. If the reason says two active releases, ask the plan owner to supersede or withdraw one of them. |

Exit codes: 0 means ready, 10, 11, 12, 13, 14 and 15 are the six messages in the order above. An id the project does not know gets the first message, which does not say whether private work exists.

## Requesting a change to a rule

Do not edit a bundle, a receipt or a source. If you think a rule in the approved context is wrong, unclear or missing, say so to the plan owner and carry on only with what the bundle permits.

- Ask your agent to draft a comment on the work item issue titled `Rule clarification request`, with the section number and your question. The agent posts it only after you give permission, and only with a tool you have authorized. The generated skill holds no token and cannot post by itself.
- This project allows engineers to append a dated entry under "Decisions recorded" in the work item file, in your pull request. The next release reassesses it.
- The plan owner updates the sources, prepares and approves a new release, and exports it. A new release supersedes the old one, and your next check picks it up.

Where a request goes. The plan owner has not named a recipient for requests, and this skill does not know the owner's login. Address the request to "the plan owner" in a comment on the issue of the work item. Do not guess a person from the name of the organization or the repository. A request stays `pending` until the plan owner marks it `accepted`, `declined` or `deferred` on the issue.

## How the skill relates to the specification folder

The specification folder `docs/spec/` is canonical. It holds the conventions, the schedule, the index and one file per work item. The skill carries the conventions and points at those files. It does not replace them.

- The conventions and definition of done in `SKILL.md` are copied from `docs/spec/README.md` and `plan.yaml`. A pull request that changes them there updates `SKILL.md` in the same pull request.
- The contracts reference lists headings. The owning work item file holds the contract.
- The map of approved source sections is generated from the bundles. When a release adds or removes a section, the plan owner refreshes the map.
- Owners, status and dates of record live in the GitHub issues.
