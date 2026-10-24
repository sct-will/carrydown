# Start here

This page is for a product manager, a program lead or anyone who owns a plan. You do not need to write code. You run one terminal command to install, then you talk to your coding agent.

**What a coding agent is.** An AI assistant that runs in your editor or terminal and can read and change files on your computer. A chat assistant in a browser will not do, because it cannot reach your files or run the scripts.

**How long it takes.** The interview and the plan review take an hour or two of your attention. The scripts take a few minutes. A senior engineer adds about an hour to review the specifications.

## What you will end up with

You bring a document that says how the project must work, such as an architecture document. You and your agent turn it into:

- a plan with milestones, people, dates and dependencies,
- one specification file for each piece of work (a work item), each tied to the sentences of your document it comes from,
- GitHub issues, one per work item, grouped under one issue per milestone,
- a GitHub Project board with the dates and the people filled in,
- a small skill linked from every issue, so each developer's agent reads the specification before it writes code.

Nothing is written to GitHub until you say yes. Work items are numbered WI-01, WI-02 and so on.

## What you need

1. **A coding agent** (defined above). Claude Code, GitHub Copilot, Cursor, Codex and Gemini CLI all work. Another agent that reads Agent Skills works too.
2. **Node.js.** Node.js is a free program that runs tools written in JavaScript. The install line uses one of them, called `npx`. Get Node.js from https://nodejs.org, choose the version marked LTS, and run its installer. If you are not sure it is installed, ask your agent: "Is Node.js installed? If not, tell me how to install it, or run the install line for me." You also need **Python 3**, which runs the scripts. Your agent can check for it and run the scripts for you.
3. **Your document or documents.** Accepted formats are **.docx** (Word) and **.md** (Markdown). Any mix of architecture, requirements, business analyst notes, governance rules and development standards. Numbered sections help, because every work item cites the sections it comes from. If your document has no numbered sections, ask the agent to propose numbering in the source document, approve it, and have the agent render the document again.
4. **A project folder.** This is any folder that holds a git repository. If you do not have one yet, ask your agent: "Create a project folder with a git repository here." Put your documents inside it, for example in `docs/source`.
5. **A short list of facts.** You can write it as you go. [docs/inputs.md](docs/inputs.md) is the checklist: who does the work, which dates, which repository, who watches the demonstrations, what the program owns.
6. **GitHub access**, for the GitHub step only:
   - permission to create issues, and to create a Project, in the repository's organisation (or your own account). If you do not have it, ask an organisation administrator,
   - a token, which is a long password that lets the scripts act for you. The skill helps you create it. It only needs two permissions, `repo` and `project`,
   - approval of the token for single sign-on, if your organisation enforces it. Step 7 says where to click.

## Step 1. Install

Open a terminal in your project folder and run this one command. It is the only terminal command you need. If you prefer, ask your agent to run it for you.

```bash
npx skills add sct-will/carrydown --all
```

What this does, in plain words.

- `npx` comes with Node.js. It downloads the installer, a tool called `skills`, from the internet and runs it. It may ask you to confirm the download.
- The installer copies the three carrydown skills from GitHub into your project.
- `--all` installs all three skills for every coding agent the installer finds on this computer. It does not create a folder for every possible agent.
- The skills land in the skills folder of each agent, for example `.claude/skills/` for Claude Code. The README has a table of these folders.

To install for one agent only, name it with `-a`. Replace `claude-code` with your agent's name from the README.

```bash
npx skills add sct-will/carrydown --skill '*' -a claude-code
```

Close your agent and open it again so it sees the new skills.

## Step 2. Open your agent in your project folder

"Open your agent in your project folder" means start the agent with your project folder as its working directory. In a terminal, change into the folder and start the agent there. In an editor, open the folder, then open the agent panel.

## Step 3. Say the sentence for each skill

Say these three sentences to your agent, one at a time, as you reach each stage.

| Stage | Say this |
| --- | --- |
| The plan and the specifications | "Set up a project plan from this document." |
| GitHub | "Create the GitHub issues and the board." |
| The developer skill | "Generate the developer skill." |

Name your own files and repository when the agent asks. If your agent does not pick the skill up on its own, put the skill name first, for example "Use the carrydown-ground-truth skill. Set up a project plan from this document." The other two skills are `carrydown-plan-to-github` and `carrydown-dev-skill`.

## Step 4. Answer the interview

After the first sentence the agent asks questions, a few at a time. You can answer in plain words. It asks about:

- your documents, and which one wins if two disagree,
- the people, which part of the work each one owns, their GitHub logins, their start dates and days off,
- the time frame, any pause weeks, and the longest stretch of work you will allow in one block,
- your GitHub repository, whether an Epic issue already exists, and which branch the plan is for,
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
- a load table of how much work each person has in each work unit,
- the critical path, the chain of items that sets the end date,
- the program items kept outside the plan.

Ask it to move things. Ask "what if one of the developers is out in week three?" Say yes when the plan is right. This is your most important step.

## Step 6. Read the specifications, and get a lead reviewer

The agent writes one specification per work item, with helpers in parallel when your agent supports it. Then it runs a checker that compares every file to the plan.

**When a product manager drives this, a senior engineer should spend about an hour as lead reviewer of the generated specifications.** They read them as the person who will build the item and ask: could I start from this file alone? This hour catches wrong assumptions about the existing code, which the agent cannot always see. You read the "Why this work item exists" and "Acceptance criteria" parts. They are short.

The checker runs on your computer, and the agent can add it to continuous integration (CI, the automatic checks on every pull request). In CI it fails loudly: a red mark on any pull request that makes a specification disagree with the plan. Ask: "Add the specification checker to CI."

## Step 7. Put it on GitHub

Say "Create the GitHub issues and the board." The agent will first help you with the token.

**Create the token** in your browser. The agent gives you the link. Choose a classic token, tick the two permissions `repo` and `project`, set an expiry, and copy the token when GitHub shows it. GitHub shows it once.

**Give the token to the scripts.** Pick one way.

- *Preferred, with no terminal.* Paste the token into a plain text file, for example `Downloads/token.txt`. In TextEdit, choose Format, then Make Plain Text, before you save. Tell the agent the file path. Do not paste the token into the chat. The agent runs `github_token.py --from-file <path>`. The script reads the file, stores the token at `~/.config/carrydown/github_token` where only you can read it, checks what the token can do, and tells you to delete your copy. Delete it.
- *Alternative.* You run `github_token.py` yourself in a terminal and type the token at the prompt. The characters do not appear as you type. The script stores and checks it the same way.

**Check the token.** The agent runs `github_token.py --check --repo owner/name`. It says who owns the token, which permissions it has, and whether the repository is reachable. If it says the repository is not reachable, or that you cannot push, you probably lack the organisation permission to create issues and Projects. Ask an organisation administrator for that permission.

**Single sign-on.** If your organisation enforces single sign-on, the token must be approved for it. Go to github.com/settings/tokens, find the token, click its "Configure SSO" button, and click "Authorize" next to the organisation. Then ask the agent to run the check again.

Then the agent will:

1. Run a dry run and show you what it would create. A dry run changes nothing. Read the numbers, for example "1 Epic, 5 sub-epics, 9 work item issues".
2. Ask "Shall I go ahead?" Say yes only when you are ready.
3. Create everything, then check the counts through GitHub.
4. Build the project board and fill in the dates.
5. Give you a short list of settings that GitHub only lets a person click, such as how the board groups its cards, and tell you where.

## Step 8. Make the developer skill

Say "Generate the developer skill." The agent generates a small skill from your specifications and tells you how your team installs it. Send each developer the install line for their agent. After that, a developer starts any item by saying "Work on WI-07" in their editor, and the agent reads the specification first.

## After that

The team follows a rhythm.

- When an item is finished, the developer posts a closing comment on its issue: what they can demonstrate, the evidence, the decisions, and what the other track needs to know.
- Every week the people meet for 30 minutes and run a joint check.
- At the end of each work unit the developers demonstrate the milestone to you, against criteria that were written before the work started. You note pass or fail on the milestone issue.

## If something goes wrong

- A script fails. Ask the agent to show the message and explain it. Nothing is written until you said yes, and no script deletes anything.
- A GitHub step is refused. The most common cause is single sign-on, described in step 7. [docs/faq.md](docs/faq.md) has more.
- You want to change the plan later. Change `plan.yaml` with your agent and rerun the checker. The FAQ explains how to refresh the files and the issues.
- You think you leaked the token. Revoke it at https://github.com/settings/tokens and make a new one. [docs/security.md](docs/security.md) has the details.

## Try the sample first

The folder `sample/expense-approvals/` holds a made-up project: an internal service for expense approvals, with a short architecture document, two people, 11 weeks and a worked plan. Ask your agent:

> Read sample/expense-approvals and walk me through what each carrydown skill produced.

Or run the scripts on the sample against a throwaway repository of your own. The scripts take about four minutes, most of it pauses that keep GitHub from limiting the writes. Reading the dry runs takes longer. [docs/sample-run.md](docs/sample-run.md) shows a real run.

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
