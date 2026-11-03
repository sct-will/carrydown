# Review and publish your plan

Use this guide once the skills are installed and your agent is starting the interview. It takes you through answering the questions, reviewing the drafts, publishing to GitHub and updating the plan later.

If you have not installed carrydown, follow [Install carrydown and start your first plan](setup.md) first. Once the interview begins, continue here. Reference pages provide optional background.

Already have a draft? Skip to [reviewing the plan](#reviewing-the-plan). Approved and ready to publish? Skip to [release what the engineers will see](#release-what-the-engineers-will-see) and [prepare for GitHub](#prepare-for-github).

[Answer the interview](#what-the-agent-asks-you) | [Review the plan](#reviewing-the-plan) | [Second-pass review](#the-second-pass-agent-review) | [Review the specifications](#reviewing-the-specifications) | [Release](#release-what-the-engineers-will-see) | [Prepare for GitHub](#prepare-for-github) | [Publish](#the-github-step) | [Hand off](#hand-the-work-to-engineers) | [Update the plan](#update-the-plan) | [Get help](#if-something-goes-wrong)

## Who runs what

| Role | What they do |
| --- | --- |
| Plan owner | An engineering manager, product manager or other person responsible for the plan. Answers the interview, reviews the drafts, approves publishing and gives the engineers their generated skill. |
| Engineers | Install the generated skill, work from their specifications and demonstrate completed work. |
| Stakeholders | The people accountable for the outcome. Watch demonstrations and decide whether the acceptance criteria have been met. They run nothing. |

The agent drafts, checks and populates. You decide the owners, dates, scope and order.

## What the agent asks you

The interview starts with step 0, the question about who may see your documents, and then has six steps. Replies start with `carrydown: interview, step N of 6`, with the current step number in place of `N`. These questions tell you what to have ready:

| The agent asks | You answer with |
| --- | --- |
| Step 0, before it renders anything or asks about people: can everyone who can read this repository see all of these documents and your staffing notes? | Yes or no. On no, which documents are restricted (the default is all of them), who may approve sharing them (GitHub logins, the default is you) and whether the raw inputs are kept after a release (the default is kept, in the private workspace and never in the repository). |
| Which documents must the project obey, and which wins if two disagree? | File paths, and the winner |
| Who does the work, which part of the system does each person own, from when, and at what share of their time? | Names, a track each (a lane of work one engineer owns, such as back end or front end), allocation percentages, start dates, days off. The agent saves these to a private file on your machine, and the plan holds only ids and tracks. |
| Should skills or work preferences influence the proposed assignments? | Optional skills and preferred work for any or all engineers. Leave them out when unknown. |
| When must it ship, or how many weeks do you have? | A date, a number of weeks, or "derive the date" |
| Which repository, and which coding agents do the engineers use? | owner/repo and the agents |
| What must the stakeholders see at each milestone demonstration to call it done? | Their words, which become acceptance criteria |
| How is the code built, tested and merged here? | The commands and the branch rule |

Your source files are required. Give the agent the technical document and broader context where you keep them. You do not need to copy them into the project, and a confidential document should stay where it is. If you want a local folder, use `docs/source/` and put it in `.gitignore` first. The agent inventories Word, Markdown, plain text, PDF, image and other readable files, then creates reviewable Markdown renderings. It reports a file that is already inside the project without calling it safe. It identifies unreadable files and continues with the rest. It stops only when no intended source can be processed. On the yes answer it writes the renderings under `docs/ground-truth/`. On the no answer it writes every rendering into the private workspace, including those of documents you call shareable. For what each answer means in practice, read [who may see your documents](setup.md#before-you-add-documents-who-may-see-them). Team size, allocation and target dates can be undecided. If you have a team and no date, the agent derives a date. If you have a date and no team, it proposes the capacity needed. If neither is known, it proposes a starting point and asks you to confirm it. Skills and work preferences are always optional. If you supply them, the agent proposes a best match and explains it. If they are missing or unclear, the agent uses the default assignment approach and continues.

Allocation is the share of each person's working time available for this plan. The agent assumes 100 percent and asks you to confirm. For someone available three days in five, say 60 percent. Mention start dates, days off, breaks, work owned outside the team and any existing parent epic. An epic is the parent GitHub issue for the whole plan.

Names and personal facts are private on both answers. The agent writes them to `people.yaml` in your private workspace, with the same ids as the plan, and shows you the path. The load table, the dates and the name checks run on your machine, where that file is. In a clean clone, such as the checks that run on every pull request, those checks say `people overlay not loaded: capacity, dates and names not checked` and skip. That is expected.

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

## Release what the engineers will see

A release turns your approved plan and specifications into exact content and records your decision about it. Nothing reaches the repository or GitHub before that. The release is the first thing the agent does after you say "Put the plan on GitHub." and after the token is set up. **On the yes answer you answer one extra line, in the same prompt as the GitHub question you always answered.** The agent runs the rest, and you never type a command, a request id, a repository id, an audience or a destination. You decide. The agent shows the preview, runs the commands and reports what they print.

**What you see on the yes answer.**

1. You approve the plan at the end of planning, as before: "The plan and specifications are correct."
2. After "Put the plan on GitHub." and the token, the agent shows a short preview in plain language: what will be shared, with whom, where, and what remains private. It then lists what changed since the previous release and anything unresolved. Carrydown checks by machine that every cited section is in a work item's approved context. Whether that context is enough to do the work is your review, so read a few as the engineer would.
3. It asks two lines in one prompt. "These exact outputs may be shared with everyone who can read this repository" is the one new line. When the repository is public it says "published publicly" instead, because everyone can read it. "Carrydown may create or update these GitHub items", with the counts, is the question you always answered before anything was written to GitHub. It now covers the issues and the board in one answer, and it names the board when carrydown has to create it. A yes to one line is never a yes to the other.
4. After your yes the agent creates the empty board if it does not exist yet, builds the exact content, records your approval and writes the approved files, a small receipt and the engineers' skill into your working tree. You commit and push as you do today, once. The approval is your own confirmation. It is labeled not authenticated, and no protected claim is made for it. If any file changed after you saw the preview, nothing is written and the agent shows you the new preview.

<details>
<summary>What the agent runs for you on the yes answer</summary>

Every command that writes is a dry run until `--apply`.

```bash
python3 scripts/release.py release --root .            # the preview and the lines to ask; writes nothing to the project or GitHub
python3 scripts/release.py release --root . --apply    # after your yes: the empty board if needed, then prepare, your approval and the export
```

The command reads the repository's numeric id with the GitHub token, derives the audience from the repository's visibility and looks the board up by the plan's project title under the account that owns it. The dry run keeps a digest of the preview in your private workspace, and `--apply` approves only content and a scope that match it. The release id names the exact content. The request id names one permission decision over it: this content, for this audience, these destinations and these downstream uses. The same content can have several requests, for instance for a second audience, and approving one never approves another. If a retry finds the same content and scope, it reuses the saved request, and an approval you gave earlier is never copied into a new one.

`export` refuses to overwrite a file you edited since the release (`working-copy-differs`). After the first release `docs/spec/plan.yaml` in the project is the released plan, exactly as approved: it lists each source by id, name and version, and it is what a clean clone and the checks on every pull request read. Your working plan, with its comments and source paths, moves to `drafts/plan.yaml` in your private workspace, and the agent edits that one from then on. The specifications stay in the project.

</details>

**What stops a release.** Credentials, private paths and staffing fields in an output can never be released. A copied passage from a restricted source, or a phrase your organization listed, can be released only with an exception you approve by name, and it appears in the preview. The renderer also stops for a Word marking that disagrees with your answer, and for hidden or tracked text you have not resolved.

**When something changes.** A change to the plan, a specification or a source after approval needs a new preview and a new approval. The agent runs `release.py diff` to name the work items it touches. A private source edit is not visible to the engineers until you release again. The new request replaces the old one, the new receipt names the one it replaces, and the old receipt stays as superseded. Never edit a file under `docs/context/` or `docs/release/` by hand. To end a release, ask the agent to withdraw it, and give a reason. The withdrawn content can no longer be published, and nothing else changes with it.

**What to tell the engineers.** They learn of a replacement or a withdrawal only when its receipt reaches the default branch they fetch, and an engineer working offline cannot learn of it until the next refresh. An engineer can work offline for the grace period in the receipt (7 days by default) after a successful refresh of that clone. Text already delivered, in a clone, a fork or an agent transcript, cannot be recalled. [The enterprise security questions](enterprise-security.md) give the plain-language limits to share with your security team.

<details>
<summary>If you answered no: the private path</summary>

The approval is not a chat answer. After the preview, the agent uploads the candidate to your private staging repository once your organization's checks pass, and asks your permission to write to GitHub first. A trusted workflow in the staging repository opens a pull request, so you are not its author. You review its final revision in GitHub and approve it. If anyone adds a commit afterward, GitHub dismisses your review and you approve the new revision. You merge with a merge commit. Carrydown verifies your review through GitHub before it exports anything. It then creates a new branch in an isolated copy of your repository, copies only the approved files and the receipt, commits as you, and prints the push and `gh pr create` commands, which it does not run. Creating the engineering pull request is its own write and needs your yes. Your organization's administrator sets this up once. The steps and the commands are in [the owner's release commands](setup.md#step-7-the-owners-release-commands).

On this path a restricted work item that you marked with a summary is left out of everything and shown as an external item with only your summary.

</details>

## Prepare for GitHub

You can draft and review locally before publishing. If permissions may take time, ask for them during the review. Before you publish, you need:

- A GitHub repository, identified as `owner/repository`, and the branch that will hold the planning files.
- Your approval of the plan. The release in the previous section happens after you say "Put the plan on GitHub." Publishing writes only what that release approved, and every publishing command checks the approval again before it writes.
- Permission to create issues in that repository and a project board in the account or organization that will own it. On the yes answer the release creates the empty board when it does not exist yet, so you do not create it yourself.
- The parent epic's issue number, if one exists, or approval to create one.
- Engineers' GitHub usernames, if the issues should be assigned to them. They are kept in the private staffing file. Whether they are published is a separate choice, shown in the preview under "With whom", and publishing how much of each person's time goes to the plan is another separate choice.
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

For what publication to GitHub does and cannot do, read [the enterprise security questions](enterprise-security.md) before this step. Issue bodies are visible to everyone who can read the repository, and earlier disclosures cannot be undone.

1. **Approve the release, then put the files in the repository.** The agent shows the release preview and asks the two lines described in [release what the engineers will see](#release-what-the-engineers-will-see). The export puts the approved files, the receipt and the engineers' skill in your working tree, or on a new branch on the no answer. Commit and push them to the intended branch. Each issue links its specification there, so the file must be available first. The agent checks this. You can ask it to commit and push for you, or have your engineering team do that.
2. **Review the issues dry run.** A dry run previews the changes. The agent first runs the destination preflight, which prints one visibility line for each target and refuses a destination the approved audience does not allow. It then prints counts such as "1 Epic, 5 sub-epics, 9 work item issues" and names the repository. Check the destination, counts and proposed content. For an approved release your yes to the external-write line already covers this run; the agent asks again only if the dry run shows something that line did not name. For a project without a release policy, say whether to proceed. If a run stops partway, a rerun resumes from the saved list of what was published and creates nothing twice. If someone edited a managed part of an issue on GitHub, the run stops with `target changed since publication` for your decision and never rewrites it.
3. **Review the board dry run.** Check its owner, name, fields and dates. For an approved release it is covered by the same external-write line. For a project without a release policy the board has a separate approval.
4. **Finish the board settings.** After publishing, the agent verifies the results and gives you the board link. It lists settings you must choose in GitHub, such as grouping and sorting. Follow that list to finish the view.
5. **Review the engineers' skill.** The agent generates it from your specifications and the approved contexts, and asks you to review the project conventions. It is part of the release, so it arrived with the export and was in the commit of step 1. If you edit its `SKILL.md` or `README.md` by hand, the next release keeps your edits; commit and push them as usual.

You are ready to hand off when the issues link to their specifications, the board shows the plan and the generated skill is available on the intended branch. If a destination is public, review the content for publication before approving the write.

## Hand the work to engineers

The agent supplies a complete installation command for your project's generated skill. Send that command and the board link to the engineers. They install the generated skill once in their coding agents. Each starts an item by naming its identifier, for example "Work on [work item ID]". Their agent first runs the skill's check on the item's approved context, then reads the specification and that context, which holds the exact text of every source section the item cites, and applies the recorded decisions before planning code. It does not open the source documents. When the check cannot proceed it prints one of four plain messages and stops: no approved context for the item, the approved context is stale, the item cites an obligation that is not in its context, or the item has a restricted destination that the project does not publish. The engineers' README lists them with what to do. The check runs in the engineer's own checkout, so it is a convenience and an integrity check, not the control. The controls are your release process and the independent verifier on pull requests.

The engineers follow three rhythms:

- **Each work item:** post a closing comment with what they can demonstrate, the evidence, decisions and anything another track needs to know.
- **Each checkpoint:** meet for the planned integration check and run the joint check, the test that proves the tracks fit together. Post the result.
- **Each milestone:** demonstrate the completed capability to the stakeholders against its written acceptance criteria. Record pass or fail on the milestone's sub-epic.

The stakeholders decide whether the outcome meets the criteria. You keep the plan current as the team learns.

## Update the plan

Open the same project in your coding agent and describe what changed. Review the affected items and dates before publishing another update. You can use these prompts.

### Change people, dates or dependencies

> Update the plan for these changes. Show me the effects on each person's load, the critical path and the checkpoints. Refresh the specification headers and run the checker. Show me the differences before changing GitHub.

Give the names, availability, dates or dependencies that changed. The agent updates your working plan for the ids, tracks and dates (`docs/spec/plan.yaml` before the first release, `drafts/plan.yaml` in the private workspace after it), and the private staffing file for the personal facts. It refreshes the affected specification headers and checks the files. Read the revised schedule and approve it only when it fits. A change after approval needs a new release before it reaches the engineers or GitHub.

### Change the source document

> The source document has changed. Render it again, identify the affected specifications and update the plan with me. Run the checker before we publish anything.

Edit the source document rather than its rendered copy. The checker flags citations to sections that no longer exist; review the affected content with the agent as well. A valid section number alone does not prove that a specification still matches the revised document. Carrydown records the content digest and version of each source. After you render the new version, `release.py preview` and `release.py diff` name the work items whose approved context would change, and the old release stays in force until you approve a new one. Carrydown cannot see a change to a document's permissions in your own document system, so check that yourself whenever you change who may read a source.

### Reapprove or withdraw a release

> Show me what changed since the active release, then prepare a new request.

A new request replaces the active one in a single reviewed step. You can also approve the same content again, for example for another audience. That makes a new request with a fresh nonce and leaves every earlier approval and its history as it was. To stop a release, withdraw it with a reason code. The withdrawal is a reviewed state change too, and the receipt-only export publishes it without allowing any content to be published. See [the owner's release commands](setup.md#step-7-the-owners-release-commands).

### Publish an approved update

> Show me a dry run to bring GitHub up to date with this approved plan. Include the existing issue bodies that need updating.

Export and commit the new release first. The synchronization scripts match existing issues, add new items and leave existing bodies unchanged unless an update is requested. Ask the agent to show which bodies it would rewrite. Approve the issue and board updates after their previews. The ordinary sync does not delete issues or change issue titles. After a second-pass review, the separate `github_repair.py` command can preview and repair generated titles, the plan owner's assignment, track labels and parent links using the saved pre-repair plan. Human title changes and retired work require your decision. Read the [published-plan repair procedure](../skills/carrydown-plan-to-github/references/plan-review-repair.md) before applying it.

If specifications or engineering conventions changed, ask the agent to refresh the engineers' skill too. Review, commit and push that change, then have the engineers update their installed copy.

## If something goes wrong

- **The agent does not recognize a stage.** Name its skill explicitly: "Use the carrydown-ground-truth skill" for planning, or "Use the carrydown-plan-to-github skill" for publishing. Then describe what you want to do.
- **A checker reports findings.** Ask the agent to explain each finding and fix the plan or specifications with you. Ask for a clean check before publishing.
- **A release command is refused.** The refusal is a fixed reason code, such as `not-approved`, `working-copy-differs`, `approval-scope-mismatch`, `withdrawn`, `superseded`, `expired`, `mixed-release` or `staging-access-not-verified`. Ask the agent to say what the code means and what you can do. None of them has a bypass. Do not look for one: do not edit a file under `docs/context/` or `docs/release/`, regenerate approved files to clear a mismatch, or ask for an approval to be forced. Prepare a new request instead.
- **A publishing step is refused.** Ask the agent to explain the token or permission check. Confirm the repository, board owner and any single sign-on authorization. Do not paste a token into chat.
- **A publishing run stops partway through.** Ask the agent to inspect what exists and show another dry run. A rerun matches existing issues and repairs missing links. Review the preview before approving it.
- **You want to rebuild the draft.** Ask the agent to show the proposed changes and preserve reviewed work before replacing files.

For installation problems, use the [setup guide's troubleshooting](setup.md#when-something-does-not-work). The [planning method](method.md) and [security guide](security.md) provide optional background.

## Glossary

- **Ground truth.** The document or documents the project must obey, such as an architecture document, requirements, rules and standards.
- **Private workspace.** An owner-only, versioned folder on your machine, outside the project. It holds the staffing file, restricted documents and their renderings, drafts and every release record. Carrydown never copies it anywhere.
- **Approved context.** One file per work item, `docs/context/<id>.md`, with the exact text of the source sections the item cites. You approve it for everyone who can read the repository.
- **Release.** Approved content, named by its release id, together with one permission decision, named by its request id.
- **Receipt.** The small public file in `docs/release/` that names a release, its state and its expiry.
- **Staging repository.** A private repository where a release candidate is reviewed and approved before anything reaches the engineering repository. The private path only.
- **Tooling repository and enrollment.** The organization's protected repository that holds the independent verifier and the list of repositories that use the private path. The private path only.
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
