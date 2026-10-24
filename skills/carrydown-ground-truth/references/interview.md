# Interview guide

Run this interview before you write anything. The user may be a product manager, so use plain words, ask a few questions at a time, and explain why you ask. Offer a default for every question. Read the answers back as one summary and wait for a yes.

Never ask the user to paste a secret. A GitHub token is handled later by `carrydown-plan-to-github`, in a hidden prompt.

## Step 1 of 6. The ground truth

Begin your reply with `carrydown: interview, step 1 of 6`. Before the questions below, ask this: "Can you create a Project in your GitHub organisation? If you are not sure, we carry on. It only matters at the GitHub step, and an organisation admin can grant it later."

Ask.

1. Which documents hold the truth for this project? Any mix of architecture, requirements, business analyst notes, governance rules and development standards. Word files and Markdown files both work. Give me the paths.
2. If two documents disagree, which one wins? A good default: governance rules, then the development standard, then the architecture, then requirements, then notes.
3. Is each document final enough to plan from? Which version is it?
4. Are the sections numbered? Specifications cite sections by number. If not, ask whether you may propose numbering for the source document.

Why you ask: the plan is only as good as the document it is carried from. Say so if the document looks thin, and offer the review prompts in `review-prompts.md`.

## Step 2 of 6. The people

Begin with `carrydown: interview, step 2 of 6`.

Ask.

1. Who will do the work? A name or handle for each person.
2. Which track does each person own? A track is a lane of work, for example back end, front end, data, platform. Each person owns one track.
3. When does each person start, and which days are they off?
4. Is there anyone who advises and owns no items, such as a security reviewer or a policy owner?
5. Who is the program lead or product owner, who decides when the plan is final?

Explain: names stay in `plan.yaml`. The checker keeps them out of the specifications so the files stay valid when people change.

## Step 3 of 6. The time frame

Begin with `carrydown: interview, step 3 of 6`.

Ask.

1. Is there a target date, or a number of weeks? Which is firm?
2. Are there pauses, such as holidays, offsites or a freeze?
3. What is the longest a work unit may run? A work unit is a time box with its own length. A default: no longer than three weeks.
4. How often can the people meet for a short integration check? A default: weekly, 30 minutes.

## Step 4 of 6. GitHub

Begin with `carrydown: interview, step 4 of 6`.

Ask. Do not touch GitHub in this skill.

1. Which organisation or user, and which repository, will hold the issues?
2. Does a parent Epic issue already exist? If yes, its number. If no, may the plan script create one later?
3. Which labels already exist that the plan should reuse or avoid?
4. Do the people have GitHub logins for assignment? If yes, collect them.

## Step 5 of 6. Agents, demonstrations and the program boundary

Begin with `carrydown: interview, step 5 of 6`.

Ask.

1. Which agentic editors does the team use? Any editor or command line agent that reads Agent Skills works. The README lists the ones the installer knows.
2. Who watches the milestone demonstrations, and how long can they give? A default: 45 minutes, once per milestone.
3. What must the audience see to say "this milestone is done"? Write down their words. They become acceptance criteria.

### The program boundary

Ask.

1. What work does the program own and keep outside the development plan? Examples: recruiting pilot teams, approvals, security review, legal text, procurement.
2. Which development items wait for one of these? Those items carry a "program input" note.

Explain: program items get an id gap and are never numbered inside the plan. Specifications mention them only as "the program input".

## Step 6 of 6. Engineering conventions

Begin with `carrydown: interview, step 6 of 6`.

Ask.

1. What command runs the tests? Lint? Format?
2. Is new behaviour hidden behind a feature flag? What is its name and its default?
3. Which branch do changes merge to? Is there a pull request size or review rule?
4. Are there rules for secrets, logs or personal data that every change must obey?
5. Where does the existing code live that the work touches, if any?

These answers become the definition of done in every issue and in the developer skill.

## The summary to read back

Write it as a short list the user can correct.

- Ground truth: files, winner on conflict, version.
- People and tracks, start dates, days off, advisors.
- Time frame and pauses, longest work unit, checkpoint rhythm.
- Repository, Epic, labels, logins.
- Agents in use.
- Demonstration audience and what they must see.
- Program-owned work and the items that wait for it.
- Conventions: test, lint, flag, branch, extra rules.

Say: "If this is right, I will render the documents and draft the plan. Nothing is written to GitHub." Then wait.

Offer the dry run for every script. Offer the sample if the user is unsure what the output looks like.
