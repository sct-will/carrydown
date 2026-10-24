# Milestones, demonstrations and checkpoints

Progress is shown, not reported. Three things carry it.

## Milestone file

`milestone.md` in the milestone folder becomes the body of the sub-epic on GitHub. The scaffold script writes the header table and the work item table. You write the rest.

- Purpose. Three to six lines. What this milestone gives, written for someone who reads only this page. What could not be shown before. Which decision the demonstration feeds.
- Expected outcomes. Bullets of observable results. The last one restates the exit gate.
- Acceptance criteria. At least three checkbox lines. Each can be seen during the demonstration. Write them now, before the work starts, so nobody can bend them to fit what was built.
- Demonstration expectations. Keep the three lines from the template: who gives it and when, that nothing about the session is automated, and that the outcome is noted as a comment on the sub-epic the same day.
- Work items. The table the scaffold wrote.
- References and Decisions recorded.

The checker confirms these parts exist and that every item of the milestone is listed.

## Demonstration

One per milestone, given by the engineers who built the items to the program. It shows the items of the milestone working together. The exit gate is the pass criterion. The acceptance criteria say what the audience must see.

Do not script or automate the session. The engineers decide what to show. To help them prepare, add a preparation list to the milestone file for their coding agents to use the day before: which environment, which data, which accounts (placeholders only), a dry run. Record the outcome as a comment on the sub-epic with the checkpoint comment template, filled in with pass or fail against each criterion.

## Checkpoint

A 30-minute integration check, weekly, with all tracks present. Not a demonstration. The engineers run the current end-to-end flow and the joint check named for the date in `plan.yaml`. Record it with the `checkpoint-comment.md` template: Shown, Closed since the last checkpoint, Joint check, Blocked or at risk.

Every work item names one checkpoint, on or after its completion date. The joint check is the item's share of the whole: what the two tracks run together to prove their halves meet.

## Closing comment on each issue

When an item closes, the engineer posts the evidence with the `closing-comment.md` template: Demo, Evidence, Decisions, Handoff. The coding agent assembles it from the commands in the specification. The engineer checks it first.

## The rhythm

- Day by day, items close with evidence.
- Weekly, a checkpoint between tracks.
- At the end of each work unit, a demonstration of the milestone against criteria written in advance.
