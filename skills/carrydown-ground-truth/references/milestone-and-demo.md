# Milestones, demonstrations and checkpoints

Progress is shown, not reported. Three things carry it.

## Milestone file

`milestone.md` in the milestone folder becomes the body of the sub-epic on GitHub. The scaffold script writes the header table and the work item table. You write the rest.

- Purpose. Three to six lines. What this milestone gives, written for someone who reads only this page. What could not be shown before. Which decision the demonstration feeds.
- Why these items form this milestone. Written by the scaffold from `rationale` in `plan.yaml`, with the items per track and their themes, and `single_track_reason` when there is one. Change the text in `plan.yaml` and run `scaffold_spec.py --refresh-headers --apply`, not in this file.
- Expected outcomes. Bullets of observable results. The last one restates the exit gate.
- Acceptance criteria. At least three checkbox lines. Each can be seen during the demonstration. Write them now, before the work starts, so nobody can bend them to fit what was built.
- Joint demonstration. Written by the scaffold from `joint_demonstration` in `plan.yaml`, with the tracks that give it and the joint check for the demonstration date. Change it in `plan.yaml` too.
- Demonstration expectations. Keep the three lines from the template: who gives it and when, that nothing about the session is automated, and that the outcome is noted as a comment on the sub-epic the same day.
- Work items. The table the scaffold wrote.
- References and Decisions recorded.

The checker confirms these parts exist and that every item of the milestone is listed.

## Demonstration

One per milestone, given by the engineers who built the items to the stakeholders. It shows the items of the milestone working together. The exit gate is the pass criterion. The acceptance criteria say what the stakeholders must see.

The demonstration is joint. The engineers whose tracks meet in the milestone give it together, each showing their half of the same run, so the stakeholders see the halves meet rather than two separate shows. `joint_demonstration` in `plan.yaml` says what they show together, in one or two sentences, for example "The Experience engineer submits a report in the web client. The Workflow engineer shows the stored state from the same run." The checkpoint on the demonstration date names each of those tracks in its joint check. A milestone that stays inside one track still has a joint demonstration: the other engineers take part and say what they show.

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
