# Start here

This page is for a product manager, a program lead or anyone who owns a plan. You do not need to write code. You run one terminal command to install, then you talk to your coding agent.

## What you will end up with

You bring a document that says how the project must work, such as an architecture document. You and your agent turn it into:

- a plan with milestones, people, dates and dependencies,
- one specification file for each piece of work (a work item), each tied to the sentences of your document it comes from,
- GitHub issues, one per work item, grouped under one issue per milestone,
- a GitHub Project board with the dates and the people filled in,
- a small skill linked from every issue, so each developer's agent reads the specification before it writes code.

Nothing is written to GitHub until you say yes. Work items are numbered WI-01, WI-02 and so on.

## What you need

1. **A coding agent** on your computer. Claude Code, GitHub Copilot, Cursor, Codex and Gemini CLI all work. Another agent that reads Agent Skills works too.
2. **Node.js** for the install line. If you are not sure it is installed, ask your agent: "Is Node.js installed? If not, tell me how to install it, or run the install line for me." You also need **Python 3** for the scripts. Your agent can check and run the scripts for you.
3. **Your document or documents.** Accepted formats are **.docx** (Word) and **.md** (Markdown). Any mix of architecture, requirements, business analyst notes, governance rules and development standards. Numbered sections help, because every work item cites the sections it comes from.
4. **A short list of facts.** You can write it as you go. [docs/inputs.md](docs/inputs.md) is the checklist: who does the work, which dates, which repository, who watches the demonstrations, what the program owns.
5. **GitHub access**, for the GitHub step only:
   - permission to create issues, and to create a Project, in the repository's organisation (or your own account),
   - a token, which is a long password that lets the scripts act for you. The skill helps you create it. It only needs two permissions, `repo` and `project`,
   - approval of the token for single sign-on, if your organisation enforces it. The skill tells you where to click.

## Step 1. Install

Open a terminal in your project folder and run this one command. It is the only terminal command you need. If you prefer, ask your agent to run it for you.

```bash
npx skills add sct-will/carrydown --all
```

It installs the three skills. The command above installs them for every agent the installer knows. To install them for your agent only, run this instead and replace `claude-code` with your agent's name (the README lists the names).

```bash
npx skills add sct-will/carrydown --skill '*' -a claude-code
```

Close your agent and open it again so it sees the new skills.

## Step 2. Open your agent in your project folder

Put your documents somewhere in the folder, for example in `docs/source`.

## Step 3. Say the sentence for each skill

Say these three sentences to your agent, one at a time, as you reach each stage. Name your own files and repository when it asks.

| Stage | Say this |
| --- | --- |
| The plan and the specifications | "Set up a project plan from this document." |
| GitHub | "Create the GitHub issues and the board." |
| The developer skill | "Generate the developer skill." |

Each sentence starts the matching skill. If your agent does not pick the skill up on its own, add its name: "Use the carrydown-ground-truth skill. Set up a project plan from docs/source/architecture.docx."

## Step 4. Answer the interview

After the first sentence the agent asks questions, a few at a time. You can answer in plain words. It asks about:

- your documents, and which one wins if two disagree,
- the people, which part of the work each one owns, their start dates and days off,
- the time frame, any pause weeks, and the longest stretch of work you will allow in one block,
- your GitHub repository, and whether an Epic issue (a parent issue) already exists,
- which agents your team uses,
- who watches the demonstrations, and what they need to see,
- what the program owns and keeps outside the plan, such as recruiting a pilot team or getting an approval,
- how the team runs tests and lint, and whether it uses a feature flag.

If you do not know an answer, say "decide later" or "use your default". The agent reads everything back as a summary. Correct it, then say yes.

## Step 5. Look at the plan and approve it

The agent drafts the plan. You decide. It shows you:

- the milestones, each with an exit gate you can check at a demonstration,
- the work units (the time blocks), with their dates and your pauses,
- every work item with an owner, a date and what it depends on,
- a table of how much work each person has in each work unit,
- the critical path, the chain of items that sets the end date,
- the program items kept outside the plan.

Ask it to move things. Ask "what if one of the developers is out in week three?" Say yes when the plan is right. This is your most important step.

## Step 6. Read the specifications, and get a lead reviewer

The agent writes one specification per work item, with helpers in parallel when your agent supports it. Then it runs a checker that compares every file to the plan.

**When a product manager drives this, a senior engineer should spend about an hour as lead reviewer of the generated specifications.** They read them as the person who will build the item and ask: could I start from this file alone? This hour catches wrong assumptions about the existing code, which the agent cannot always see. You read the "Why this work item exists" and "Acceptance criteria" parts. They are short.

The checker runs on your computer, and the agent can add it to continuous integration (CI, the automatic checks on every pull request). In CI it fails loudly: a red mark on any pull request that makes a specification disagree with the plan. Ask: "Add the specification checker to CI."

## Step 7. Put it on GitHub

Say "Create the GitHub issues and the board." The agent will:

1. Show you how to create a GitHub token in your browser and which two permissions to tick.
2. Ask you to save the token in a plain text file, for example in your Downloads folder, and to tell it the file path. Do not paste the token into the chat. The agent stores it safely and tells you to delete your copy.
3. Run a dry run and show you what it would create. A dry run changes nothing. Read the numbers, for example "1 Epic, 5 sub-epics, 9 work item issues".
4. Ask "Shall I go ahead?" Say yes only when you are ready.
5. Create everything, then check the counts through GitHub.
6. Build the project board and fill in the dates.
7. Give you a short list of settings that GitHub only lets a person click, such as how the board groups its cards, and tell you where.

If your organisation uses single sign-on, the agent tells you the one extra step for the token.

## Step 8. Make the developer skill

Say "Generate the developer skill." The agent generates a small skill from your specifications and tells you how your team installs it. Send each developer the install line for their agent. After that, a developer starts any item by saying "Work on WI-07" in their editor, and the agent reads the specification first.

## After that

The team follows a rhythm.

- When an item is finished, the developer posts a closing comment on its issue: what they can demonstrate, the evidence, the decisions, and what the other track needs to know.
- Every week the people meet for 30 minutes and run a joint check.
- At the end of each work unit the developers demonstrate the milestone to you, against criteria that were written before the work started. You note pass or fail on the milestone issue.

## If something goes wrong

- A script fails. Ask the agent to show the message and explain it. Nothing is written until you said yes, and no script deletes anything.
- A GitHub step is refused. The most common cause is single sign-on. [docs/faq.md](docs/faq.md) and the plan-to-github skill explain it.
- You want to change the plan later. Change `plan.yaml` with your agent and rerun the checker. The FAQ explains how to refresh the files and the issues.
- You think you leaked the token. Revoke it at https://github.com/settings/tokens and make a new one. [docs/security.md](docs/security.md) has the details.

## Try the sample first

The folder `sample/expense-approvals/` holds a made-up project: an internal service for expense approvals, with a short architecture document, two people, 11 weeks and a worked plan. Ask your agent:

> Read sample/expense-approvals and walk me through what each carrydown skill produced.

Or run the whole flow on the sample against a throwaway repository of your own. The scripts take about four minutes, most of it pauses that keep GitHub from limiting the writes. Reading the dry runs takes longer. [docs/sample-run.md](docs/sample-run.md) shows a real run.
