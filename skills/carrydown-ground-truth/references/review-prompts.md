# Adversarial review prompts

Run these as separate passes, each in a fresh context if you can. The aim is to find faults, not to confirm the work. Give the fresh context the files, not your conclusions. Fold accepted findings into the source, and record the decision. Keep a changelog entry for each version of the ground truth.

## A. The ground truth

Paste or point at the rendered document and use this prompt.

> You are a skeptical reviewer. Read the whole document. Find what is missing, what is wrong and what is contradictory. Be specific and cite section numbers.
>
> 1. Contradictions. Two places that disagree, such as a number, a name, a state, a rule. Quote both.
> 2. Gaps. A behavior that the requirements imply but no section defines. An error that no interface lists. A role that no rule covers. A rule with no owner. A data item with no retention rule.
> 3. Unverifiable claims. Statements about existing code, packages or systems that a person could check but the document does not mark as checked. List what to verify and how.
> 4. Ambiguity. Words an engineer could read two ways: "soon", "large", "secure", "appropriate".
> 5. Governance. For each governance rule and standard, is there a place in the architecture where it is applied and a way to prove it?
> 6. Risks missing. What could make the plan fail that the risk section does not name.
> 7. For each finding give: the section, why it matters, a proposed fix, and your confidence.
>
> Do not praise the document. Do not rewrite it. Return a numbered list sorted by impact.

Verify in flight. Where a claim is about code or a live system, check it by reading the code, running the tests or probing the system, then mark the claim checked or write "verify at implementation".

## B. The plan

The short form of the plan review is this one sentence. Use it first, word for word, on the plan, the load table and the critical path.

> List what is missing, wrong or improvable in this plan, reading it as each engineer would live it week by week.

Then use the longer prompt below to push each finding to a concrete change. Paste `plan.yaml`, the load table, the critical path and the planning review.

> You are a skeptical reviewer of a project plan. Find what is missing, incorrect or improvable. Think about the people who will do the work.
>
> 1. Missing. Parts of the ground truth that no work item covers. Items with no acceptance path. A milestone with no way to demonstrate it. A checkpoint with no joint check.
> 2. Incorrect. Dependencies that are reversed or absent. Dates that precede a dependency. Work on a day off. Items that need an external input but do not say so.
> 3. Improvable. Items longer than five days. Items that span two tracks. Handoffs that could move earlier. Slack before demonstrations.
> 4. Context switching. Where a person jumps between themes on consecutive days. Propose a reordering.
> 5. Load. One person carrying much more than another. One person owning the critical path, so that one absence would move the end date.
> 6. The engineers' experience. Is there a day when someone has nothing to do, or three things due? Does the first week let people start without waiting?
> 7. Milestone composition. Does each milestone prove one user-visible capability end to end, with every track it crosses meeting at a named joint check before the demonstration? Is the reason given for a milestone that stays inside one track true?
> 8. Rationale. Is each stated reason in `rationale`, `joint_demonstration` and `order_rationale` true of the dates and dependencies? Quote the reason and the date or dependency that contradicts it.
> 9. For each finding: the item or milestone, the problem, a concrete change.
>
> Return a numbered list sorted by impact. Do not make the changes.

## C. A specification set

After the specs exist, run this on all of them together.

> Read these specifications as an engineer new to the project would. For each, answer: could I start work from this file alone? Then find (1) contracts quoted differently in two files, (2) integration points where the two items name different crossings, (3) acceptance criteria that need something no item creates, (4) citations of ground truth sections that do not say what the file claims, (5) places where the file invents a name that is not in the ground truth or the code. Quote the lines. Return a numbered list.

## After the reviews

- Decide each finding with the user. Accept, reject or defer.
- Change the source of truth first (the ground truth, then `plan.yaml`), then regenerate what follows from it.
- Run the checker again.
