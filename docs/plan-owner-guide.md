# Review and publish your plan

Use this guide once the skills are installed and your agent is starting the interview. It takes you through answering the questions, reviewing the drafts, publishing to GitHub and updating the plan later.

If you have not installed carrydown, follow [Install carrydown and start your first plan](setup.md) first. Once the interview begins, continue here. Reference pages provide optional background.

Already have a draft? Skip to [reviewing the plan](#reviewing-the-plan). Ready to publish? Skip to [prepare for GitHub](#prepare-for-github).

[Answer the interview](#what-the-agent-asks-you) | [Review the plan](#reviewing-the-plan) | [Second-pass review](#the-second-pass-agent-review) | [Review the specifications](#reviewing-the-specifications) | [Prepare for GitHub](#prepare-for-github) | [Publish](#the-github-step) | [Hand off](#hand-the-work-to-engineers) | [Update the plan](#update-the-plan) | [Get help](#if-something-goes-wrong)

## Who runs what

| Role | What they do |
| --- | --- |
| Plan owner | An engineering manager, product manager or other person responsible for the plan. Answers the interview, reviews the drafts, approves publishing and gives the engineers their generated skill. |
| Engineers | Install the generated skill, work from their specifications and demonstrate completed work. |
| Stakeholders | The people accountable for the outcome. Watch demonstrations and decide whether the acceptance criteria have been met. They run nothing. |

The agent drafts, checks and populates. You decide the owners, dates, scope and order.

## What the agent asks you

The interview has six steps. Replies start with `carrydown: interview, step N of 6`, with the current step number in place of `N`. These questions tell you what to have ready:

| The agent asks | You answer with |
| --- | --- |
| Which documents must the project obey, and which wins if two disagree? | File paths, and the winner |
| Who does the work, which part of the system does each person own, from when, and at what share of their time? | Names, a track each (a lane of work one engineer owns, such as back end or front end), allocation percentages, start dates, days off |
| Should skills or work preferences influence the proposed assignments? | Optional skills and preferred work for any or all engineers. Leave them out when unknown. |
| When must it ship, or how many weeks do you have? | A date, a number of weeks, or "derive the date" |
| Which repository, and which coding agents do the engineers use? | owner/repo and the agents |
| What must the stakeholders see at each milestone demonstration to call it done? | Their words, which become acceptance criteria |
| How is the code built, tested and merged here? | The commands and the branch rule |

Your source files are required. Put the technical document and broader context in `docs/source/`. The agent inventories Word, Markdown, plain text, PDF, image and other readable files, then creates reviewable Markdown renderings. It identifies unreadable files and continues with the rest. It stops only when no intended source can be processed. Team size, allocation and target dates can be undecided. If you have a team and no date, the agent derives a date. If you have a date and no team, it proposes the capacity needed. If neither is known, it proposes a starting point and asks you to confirm it. Skills and work preferences are always optional. If you supply them, the agent proposes a best match and explains it. If they are missing or unclear, the agent uses the default assignment approach and continues.

Allocation is the share of each person's working time available for this plan. The agent assumes 100 percent and asks you to confirm. For someone available three days in five, say 60 percent. Mention start dates, days off, breaks, work owned outside the team and any existing parent epic. An epic is the parent GitHub issue for the whole plan.

Confirm engineering commands and branch rules with the engineering team, or mark them "decide later". The agent summarizes your answers before writing the plan. Review and correct the summary before approving it.

If your document has no numbered sections, ask the agent to propose numbering in the source document. Review those changes before it renders the document for planning.

Optional preparation: the [detailed inputs checklist](inputs.md) includes examples, defaults and a form to copy. You can also answer the questions as the agent asks them.

## Reviewing the plan

The agent drafts. You decide. It shows you:

- the **milestones**, each with an exit gate you can check at a demonstration,
- the **work units** (the time blocks), with dates and your breaks,
- every **work item** with an owner, a date, what it depends on and a size such as "Small, about 2 days" (the load table reads the number after "about"),
- the **load table**, how much work each person has in each work unit as a percentage of the capacity their allocation gives them, with any work unit over 100 percent flagged,
- the **critical path**, the chain of items that sets the end date, and whether it meets your target,
- the **work outside the plan**, owned outside the team and left as gaps in the numbering,
- the **rationale**: for each milestone, why it holds its items and what the engineers show together at its demonstration, and for each track, why its items are in this order,
- the **planning review**, the last block of the checker report, which lists the tracks each milestone covers, items with no slack before their checkpoint, theme switches, critical path owners and the load ratio.

Questions worth asking:

- What if one of the engineers is out in week three?
- Which item can slip a week without moving the end date? Which cannot?
- Does anyone have nothing to do, or three things due, on any day?
- Which items wait for work owned outside the team?
- Which milestone has the weakest exit gate?
- Is each stated reason true of the dates? Pick one and check it against the schedule.

After schedule changes, review the updated load table and critical path before approving the plan.

## The second-pass agent review

After the finished plan and specifications pass the ordinary checker, the agent makes a separate adversarial review. It returns to the source material and confirmed constraints, then challenges coverage, dependencies, people, allocation, tracks, supplied skill and preference matches, milestone composition and timing. It also considers improvements and their tradeoffs. Missing skills or preferences are valid and do not create a finding. This is a distinct pass, even when a fresh agent context is unavailable.

Read `docs/spec/plan-review.md`, or the same file in your configured specification directory. Its coverage table shows which requirements and review areas were assessed. Its findings table gives evidence, reasoning, likelihood, impact, confidence and a proposed change. The decision table records what you accept, reject or defer and how accepted repairs were verified.

You decide changes to owners, dates, scope and order. The agent applies the repairs you accept, updates affected specifications and milestone content, refreshes generated headers and reruns the checker and schedule report. Review the repaired plan and remaining risks before final approval. A clean checker or an agent review with no findings is not a guarantee that the plan is right.

For an existing local plan, say "Review this plan with the second-pass prompt." For a published plan, say "Review and repair the published plan." The published-plan path saves the old plan, reviews actual GitHub artifacts and previews external repairs after the local changes are accepted. It preserves issue numbers and human edits. The agent records any update that remains publication pending.

## Reviewing the specifications

Review each generated specification with the agent before publishing. Check whether an engineer could start work from the file alone. Begin with "Why this work item exists" and "Acceptance criteria", then verify assumptions against any existing code the specification relies on. Request revisions as needed. The agent edits the files and runs the checker again.

The checker compares every specification to the plan. It runs on your computer, and the agent can add it to continuous integration (CI, the automatic checks on every pull request). In CI it fails loudly: a red mark on any pull request that makes a specification disagree with the plan. Ask the agent to add the specification checker to CI.

## Prepare for GitHub

You can draft and review locally before publishing. If permissions may take time, ask for them during the review. Before you publish, you need:

- A GitHub repository, identified as `owner/repository`, and the branch that will hold the planning files.
- Permission to create issues in that repository and a project board in the account or organization that will own it.
- The parent epic's issue number, if one exists, or approval to create one.
- Engineers' GitHub usernames, if the issues should be assigned to them.
- A GitHub token, prepared in the next section. If your organization uses single sign-on (SSO), it may require authorization or administrator approval.

When you are ready, tell the agent:

> Put the plan on GitHub.

The second skill checks the files and prerequisites before proceeding with publication.

## The token

Use a GitHub personal access token to authorize issue and project creation. Open the token creation link supplied by the agent.

| Board owner | Token | Required access |
| --- | --- | --- |
| Organization | Fine-grained token limited to the repository | Repository permissions **Issues: read and write** and **Metadata: read**; organization permission **Projects: read and write** |
| Your user account | Classic token | `repo` and `project` scopes |

These are GitHub permissions. The token can act only within the access your GitHub account already has. An organization may also require administrator approval for a fine-grained token. GitHub recommends fine-grained tokens when they support the task, but [fine-grained tokens cannot access projects owned by a user account](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#fine-grained-personal-access-tokens-limitations).

1. **Pick the kind.** If an organization owns the board, create a fine-grained token on [GitHub's new fine-grained token page](https://github.com/settings/personal-access-tokens/new) for the one repository, with Issues read and write, Metadata read, and the organization permission Projects read and write. Only if your own user account owns the board, use a classic token from [the pre-filled classic token page](https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown). It ticks `repo` and `project` for you.
2. **Set the expiry to 7 days.** Click Generate token. Copy the token. GitHub shows it once.
3. **Save it in a plain text file outside your project**, for example `Downloads/token.txt`. In TextEdit, choose Format, then Make Plain Text, before you save.
4. **Tell the agent the file path.** Do not paste the token into the chat. The agent never opens the file. It runs the token script with `--from-file`. The script reads the file, stores the token at `~/.config/carrydown/github_token` where only you can read it, and checks what the token can do. It keeps your file.
5. **Read the check.** The agent runs the check. It says who owns the token, what it can do and whether the repository is reachable.
6. **Delete your file.** It still holds the token in plain text.

When the plan and the board are on GitHub, revoke the token on [your GitHub tokens page](https://github.com/settings/tokens). Make a new one if you need it again.

Instead of steps 3, 4 and 6 you can run the token script yourself in a terminal and type the token at the prompt. The characters do not appear as you type.

If the check fails, it names the fix:

- **Single sign-on.** Go to [your GitHub tokens page](https://github.com/settings/tokens), find the token, click its "Configure SSO" button, and click "Authorize" next to your organization. Then ask the agent to run the check again.
- **Missing organization permission.** Ask an organization administrator for permission to create issues and Projects.

If you think the token leaked, revoke it on [your GitHub tokens page](https://github.com/settings/tokens) and make a new one. [security.md](security.md) has the details.

## The GitHub step

1. **Put the reviewed files in the repository.** Commit and push the plan and specification folder to the intended branch. Each issue links its specification there, so the file must be available first. The agent checks this. You can ask it to commit and push for you, or have your engineering team do that.
2. **Review the issues dry run.** A dry run previews the changes. The agent prints counts such as "1 Epic, 5 sub-epics, 9 work item issues" and names the repository. Check the destination, counts and proposed content. Say whether to proceed.
3. **Review the board dry run.** The board has a separate preview and approval. Check its owner, name, fields and dates before saying yes.
4. **Finish the board settings.** After publishing, the agent verifies the results and gives you the board link. It lists settings you must choose in GitHub, such as grouping and sorting. Follow that list to finish the view.
5. **Review the engineers' skill.** The agent generates it from your specifications and asks you to review the project conventions. Commit and push this folder too, so engineers can install it from the repository.

You are ready to hand off when the issues link to their specifications, the board shows the plan and the generated skill is available on the intended branch. If a destination is public, review the content for publication before approving the write.

## Hand the work to engineers

The agent supplies a complete installation command for your project's generated skill. Send that command and the board link to the engineers. They install the generated skill once in their coding agents. Each starts an item by naming its identifier, for example "Work on [work item ID]". Their agent reads the specification, resolves each citation to the correct rendered source and applies the recorded source precedence before planning code.

The engineers follow three rhythms:

- **Each work item:** post a closing comment with what they can demonstrate, the evidence, decisions and anything another track needs to know.
- **Each checkpoint:** meet for the planned integration check and run the joint check, the test that proves the tracks fit together. Post the result.
- **Each milestone:** demonstrate the completed capability to the stakeholders against its written acceptance criteria. Record pass or fail on the milestone's sub-epic.

The stakeholders decide whether the outcome meets the criteria. You keep the plan current as the team learns.

## Update the plan

Open the same project in your coding agent and describe what changed. Review the affected items and dates before publishing another update. You can use these prompts.

### Change people, dates or dependencies

> Update the plan for these changes. Show me the effects on each person's load, the critical path and the checkpoints. Refresh the specification headers and run the checker. Show me the differences before changing GitHub.

Give the names, availability, dates or dependencies that changed. The agent updates `docs/spec/plan.yaml`, refreshes the affected specification headers and checks the files. Read the revised schedule and approve it only when it fits.

### Change the source document

> The source document has changed. Render it again, identify the affected specifications and update the plan with me. Run the checker before we publish anything.

Edit the source document rather than its rendered copy. The checker flags citations to sections that no longer exist; review the affected content with the agent as well. A valid section number alone does not prove that a specification still matches the revised document.

### Publish an approved update

> Show me a dry run to bring GitHub up to date with this approved plan. Include the existing issue bodies that need updating.

Commit and push the revised planning files first. The synchronization scripts match existing issues, add new items and leave existing bodies unchanged unless an update is requested. Ask the agent to show which bodies it would rewrite. Approve the issue and board updates after their previews. The ordinary sync does not delete issues or change issue titles. After a second-pass review, the separate `github_repair.py` command can preview and repair generated titles, the plan owner's assignment, track labels and parent links using the saved pre-repair plan. Human title changes and retired work require your decision. Read the [published-plan repair procedure](../skills/carrydown-plan-to-github/references/plan-review-repair.md) before applying it.

If specifications or engineering conventions changed, ask the agent to refresh the engineers' skill too. Review, commit and push that change, then have the engineers update their installed copy.

## If something goes wrong

- **The agent does not recognize a stage.** Name its skill explicitly: "Use the carrydown-ground-truth skill" for planning, or "Use the carrydown-plan-to-github skill" for publishing. Then describe what you want to do.
- **A checker reports findings.** Ask the agent to explain each finding and fix the plan or specifications with you. Ask for a clean check before publishing.
- **A publishing step is refused.** Ask the agent to explain the token or permission check. Confirm the repository, board owner and any single sign-on authorization. Do not paste a token into chat.
- **A publishing run stops partway through.** Ask the agent to inspect what exists and show another dry run. A rerun matches existing issues and repairs missing links. Review the preview before approving it.
- **You want to rebuild the draft.** Ask the agent to show the proposed changes and preserve reviewed work before replacing files.

For installation problems, use the [setup guide's troubleshooting](setup.md#when-something-does-not-work). The [planning method](method.md) and [security guide](security.md) provide optional background.

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
- **Track.** A lane of work one engineer owns, such as back end or front end. Each work item belongs to one track.
- **Checkpoint.** A dated integration check between the tracks, listed under `checkpoints` in `plan.yaml`. Each one runs a joint check, and each work item names the checkpoint it must be done by.
- **Joint check.** The test a checkpoint runs, written in one sentence in the plan: what the tracks run together to prove the parts they built fit, such as a report going from the form to the database.
- **Joint demonstration.** What the engineers whose tracks meet show together at the end of a milestone, one demonstration of the completed items working as one. The plan says what each of them shows.
- **Demonstration.** A meeting at the end of a work unit where the engineers show the stakeholders the milestone working, against criteria written in advance.
- **External item.** Work outside the plan, owned outside the team, such as recruiting a pilot team or getting an approval. It keeps an id, left as a gap in the numbering, and is listed under `external` in `plan.yaml`. An item that waits for it carries an "external input" note.
