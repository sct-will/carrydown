# Interview guide

Contents: [The two inputs](#the-two-inputs) · [Step 1, the ground truth](#step-1-of-6-the-ground-truth) · [Step 2, the people](#step-2-of-6-the-people-optional) · [Step 3, the target and the breaks](#step-3-of-6-the-target-and-the-breaks-optional) · [Step 4, GitHub](#step-4-of-6-github) · [Step 5, agents, demonstrations and work outside the plan](#step-5-of-6-agents-demonstrations-and-work-outside-the-plan) · [Step 6, engineering conventions](#step-6-of-6-engineering-conventions) · [The summary to read back](#the-summary-to-read-back)

Run this interview before you write anything. The user may be a product manager, so use plain words, ask a few questions at a time, and explain why you ask. Offer a default for every question. Read the answers back as one summary and wait for a yes.

## The two inputs

1. **The ground truth documents.** Required. Step 1 below. Without them you do not draft anything, and you say so.
2. **The project constraints.** Optional, in any combination. After the documents, ask one question: "What constraints do you have? The people, the target date or weeks, both, or neither for now." Steps 2 and 3 below collect the details.

The rule: if the user gives the people and a target, the plan fits them. If the user gives one, you back into the other. If the user gives neither, you propose a default and ask. Name the mode you are in (Fit, Derive the date, Derive the capacity, or Neither given) so the user knows what you will do. The modes are in `planning.md`.

The user does not type the allocation. Ask once, in one line: "I will assume everyone is allocated full time to this plan. Is that right, or should any of them be lower?" Confirmation means 100 for everyone. Named figures replace the default for those people.

Never ask the user to paste a secret. A GitHub token is handled later by `carrydown-plan-to-github`, through a file the user names or a hidden prompt.

## Step 1 of 6. The ground truth

Begin your reply with `carrydown: interview, step 1 of 6`. Before the questions below, ask this: "Can you create a Project in your GitHub organisation? If you are not sure, we carry on. It only matters at the GitHub step, and an organisation admin can grant it later."

Ask.

1. Which documents hold the truth for this project? Any mix of architecture, requirements, business analyst notes, governance rules and development standards. Word files and Markdown files both work. Ask: "Give me the paths."
2. If two documents disagree, which one wins? A good default: governance rules, then the development standard, then the architecture, then requirements, then notes.
3. Is each document final enough to plan from? Which version is it?
4. Are the sections numbered? Specifications cite sections by number. If not, ask whether you may propose numbering for the source document.

Why you ask: the plan is only as good as the document it is carried from. Say so if the document looks thin, and offer the review prompts in `review-prompts.md`.

## Step 2 of 6. The people (optional)

Begin with `carrydown: interview, step 2 of 6`.

Ask.

1. Who will do the work? A name or handle for each person.
2. Which track does each person own? A track is a lane of work, for example back end, front end, data, platform. Each person owns one track.
   Then ask which parts of the system each track touches, a few words each, such as "web client", "notification worker" or "export job". These become the themes. The plan keeps each person on one theme at a time, so they switch context less.
3. When does each person start, and which days are they off?
   Then, in one line, confirm the percent allocation: "I will assume everyone is allocated full time to this plan. Is that right, or should any of them be lower?" Do not ask for a figure per person unless the answer is no. If the answer is no, ask for the figure for each person who is lower. A person at 60 percent has three working days in five for this plan.
4. Is there anyone who advises and owns no items, such as someone from security or the author of a policy?

Explain: names stay in `plan.yaml`. The checker keeps them out of the specifications so the files stay valid when people change.

## Step 3 of 6. The target and the breaks (optional)

Begin with `carrydown: interview, step 3 of 6`.

Ask.

1. What is the target: a date, or a number of working weeks? Which is firm? If there is none yet, say so. The plan will derive the date from the critical path. If it is weeks, the target date is worked out from the start of the first work unit, and each break adds its weeks.
2. Are there breaks, such as holidays, offsites or a freeze? Give each as a date range. "None" is an answer.
3. What is the longest a work unit may run? A work unit is a time box with its own length. A default: no longer than three weeks.
4. How often can the people meet for a short integration check? A default: weekly, 30 minutes.

## Step 4 of 6. GitHub

Begin with `carrydown: interview, step 4 of 6`.

Ask. Do not touch GitHub in this skill.

1. Which organisation or user, and which repository, will hold the issues?
2. Does a parent Epic issue already exist? If yes, its number. If no, may the plan script create one later?
3. Which labels already exist that the plan should reuse or avoid?
4. Do the people have GitHub logins for assignment? If yes, collect them.

## Step 5 of 6. Agents, demonstrations and work outside the plan

Begin with `carrydown: interview, step 5 of 6`.

Ask.

1. Which agentic editors do the engineers use? Any editor or command line agent that reads Agent Skills works. The README lists the ones the installer knows.
2. Who are the people accountable for the outcome, who watch the milestone demonstrations and decide pass or fail, and how long can they give? A default: 45 minutes, once per milestone.
3. What must the audience see to say "this milestone is done"? Write down their words. They become acceptance criteria.
4. Who gives each demonstration? A default: the engineers whose tracks meet in the milestone, together, each showing their half of the same run. Ask whether anyone else must take part, such as an advisor.

### Work outside the plan

Ask.

1. What work is owned outside the team and kept out of the development plan? Examples: recruiting pilot teams, approvals, security review, legal text, procurement.
2. Which development items wait for one of these? Those items carry an "external input" note.

Explain: each piece is an external item, listed under `external` in `plan.yaml`. Each gets an id gap and is never numbered inside the plan. Specifications mention it only as "the external input".

## Step 6 of 6. Engineering conventions

Begin with `carrydown: interview, step 6 of 6`.

Ask.

1. What command runs the tests? Lint? Format?
2. Is new behaviour hidden behind a feature flag? What is its name and its default?
3. Which branch do changes merge to? Is there a pull request size or review rule?
4. Are there rules for secrets, logs or personal data that every change must obey?
5. Where does the existing code live that the work touches, if any?

These answers become the definition of done in every issue and in the engineers' skill.

## The summary to read back

Write it as a short list the user can correct.

- Ground truth: files, winner on conflict, version.
- People and tracks, start dates, days off, advisors.
- Parts of the system each track touches (the themes).
- Time frame and pauses, longest work unit, checkpoint rhythm.
- Repository, Epic, labels, logins.
- Agents in use.
- Demonstration audience, what they must see, and who gives each demonstration.
- Work outside the plan, owned outside the team, and the items that wait for it.
- Conventions: test, lint, flag, branch, extra rules.

Say: "If this is right, I will render the documents and draft the plan. Nothing is written to GitHub." Then wait.

Offer the dry run for every script.

If the user wants to see the whole flow first, give them the browser links to open themselves, never a local folder. Do not open the links with a browser tool. An install copies only this skill folder, so the sample is not on their computer. The sample repository is https://github.com/sct-will/carrydown-sample. Its README holds the renderings and the sample output, and the repository has the live issues and the public board.
