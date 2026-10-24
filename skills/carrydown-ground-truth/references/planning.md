# Drafting the plan with the plan owner

You draft. The user decides. Stop for a yes after each step.

## The modes

The ground truth is required. The project constraints, the people with their percent allocation and the target, are optional. The rule: give both and the plan fits them. Give one and the skill backs into the other. Give neither and the skill proposes a default and asks. Say plainly which mode you are in.

- **Fit.** The people and the target are both given. Plan to fit them. Flag any person over 100 percent of allocated capacity in a work unit, and any target miss. Do not move the target silently. Show the options: cut scope, add people, move the date.
- **Derive the date.** The people are given and there is no target. Plan with the people. The plan's end date is the critical path end. Report it as the "derived target" and write it into `plan.yaml` as `target: {date: <end date>, derived: true}`. Ask whether the date is acceptable.
- **Derive the capacity.** The target is given and there are no people. Propose tracks and a head count at 100 percent that meets the date. Write them into `plan.yaml` as `people` entries with `derived: true` and placeholder names such as "Engineer 1" and "Engineer 2". Tell the user to replace them with real people and to say if anyone is below 100 percent.
- **Neither given.** Propose a default team of two tracks, "Engineer 1" and "Engineer 2" at 100 percent, and a derived date. Mark both as derived. Show them and ask the user to confirm or to give real constraints.

After any mode, run the checker. Its summary line says what is derived, for example "2 people derived, target derived". When the user gives real people or a real target, replace the derived entries and remove `derived: true`.

## 1. Read the ground truth

Read the rendered document, using its section index. Make a plain list of what must exist when the project is done, in the document's words, with section numbers. Note every contract, rule and standard. Note every statement that is unverified or contradicted. Show the list to the user and correct it.

## 2. Milestones

A milestone is a step the stakeholders can see working. Each one has:

- a name that says what the product's users can do after it,
- an exit gate, one sentence that a person can check live at the demonstration,
- acceptance criteria that you write now, before the work starts.

Aim for three to six milestones. Put contracts that two tracks share into the first milestone.

### Milestone composition

Three rules decide what goes into a milestone. Apply every one of them each time.

1. A milestone is the thinnest vertical slice that proves one user-visible capability end to end. Name it for what a user can do after it. The first milestone proves the whole path with the least behavior. The last proves the project can be released and run.
2. A milestone holds items from every track the capability crosses. The tracks meet at a checkpoint before the demonstration, and its `joint_check` says what they run together there. The joint check names each track that meets there. A milestone that stays inside one track says why, in `single_track_reason`.
3. The exit gate is one sentence the stakeholders can check live. The engineers whose tracks meet give the demonstration together, and the plan says what they show together, in `joint_demonstration`.

A milestone that fails one of these is split, merged or explained before you go on. The checker's planning review lists the tracks each milestone covers and whether its demonstration's joint check names them.

## 3. Work units

A work unit is a time box with its own length. Do not use the words sprint, story point or velocity. A work unit holds one milestone. Lengths differ: a short one for a thin first slice, a long one for the core. A rule of thumb is one to three weeks. Pauses sit between work units as breaks and are listed under `breaks` in `plan.yaml`.

Check: the sum of the work units plus breaks fits the time frame, and no work unit is longer than the user's limit.

## 4. Work items

A work item is the smallest piece of work that an engineer can finish, show and close. Aim for two to five days. Each has:

- an id, a number that stays fixed. Leave gaps for the external items,
- a short label in plain words,
- a milestone, a track and an owner on that track,
- a theme, a short label for the part of the system it touches, such as "web client" or "export job",
- a size such as "Medium, about 3 days" (the load table reads "about N days"),
- the ground truth sections it cites,
- dependencies by id.

Split an item if it spans two tracks or runs past five days. Merge items that cannot be shown separately.

## 5. Dates and order

- Set a completion date for each item inside its work unit, on a working day, not a day off of the owner.
- Use each person's percent allocation. A person's capacity in a work unit is their working days, minus days off, times their allocation. An item sized "about 4 days" needs about 4 divided by the allocation in working days: 4 days at 60 percent is nearly 7 working days of calendar time. Never plan a person past 100 percent of their allocated capacity in a work unit, and aim for about 80. Days off and breaks are real: no item is due on one, and none is planned through one. The checker reports the load as a percentage of allocated capacity and flags any work unit over 100 percent.
- Check the end against the target. The checker prints the target and whether the critical path meets it.
- A dependency finishes on or before the item that needs it.
- Inside each milestone, put the shared contract first, so both tracks can start from it without waiting. Read the first week of each work unit: nobody is idle.
- Keep each engineer's consecutive items in one part of the system, one theme. Group related items for the same person in adjacent days to cut context switching. The planning review counts each owner's theme switches by date and says which fall inside a milestone. Explain any switch you keep in the track's `order_rationale`.
- Leave slack before each checkpoint and before each demonstration. An item that completes on its checkpoint date has none. The planning review lists such items.
- Alternate the checkpoint dates so that every item has a checkpoint on or after its completion date.

## 6. Checkpoints

A checkpoint is a dated integration check between the tracks, with every track present. Each has a date, a name and a joint check: the one-sentence test of what the tracks run together to prove the parts they built fit. Every item names one checkpoint. Demonstration dates are also checkpoints.

## 7. Load table and critical path

Run:

```bash
python3 <skill>/scripts/check_specs.py --root . --report
```

It prints the schedule, each person's allocation, their sized days against allocated capacity per work unit (with a flag over 100 percent), the critical path, the target and whether the critical path meets it, the checkpoints and the planning review. Read it with the user. A load of 100 percent or more leaves no slack, so aim for about 80 percent at most. If one person carries much more than the other, move items across tracks where the skills allow, or stretch the date. The planning review flags a load ratio above two to one. Check who owns each item on the critical path, because one absent owner there would move the end date. If it runs through one person, the plan says so and offers an alternative, in that track's `order_rationale`. Ask the user whether to change it.

## 8. Work outside the plan

Work owned outside the team stays outside the plan, as id gaps. Each such piece is an external item. Give it an id from the gap (for example 5 and 10) and list it under `external.items`. In an item that waits for one, set `external_input` to a phrase that says what is needed, without the id. Specifications never mention these ids. The checker fails if they do.

## 9. Review the plan

Read the plan with the user, adversarially and week by week, before anything is scaffolded. Use the plan review prompt in `review-prompts.md`. Fold in the findings the user accepts. Record rejected findings in your own notes, not in the specs.

## 10. Record the rationale

Write down why the plan is composed the way it is, where anyone can argue with it. Each reason must be true of the dates.

- For each milestone, `rationale`: why these items form it, in two to four sentences. `joint_demonstration`: what the engineers whose tracks meet show together, in one or two sentences. `single_track_reason`, only when all its items are on one track.
- For each track, `order_rationale`: why its items are in this order. Name each theme switch you keep, and the critical path risk with its alternative when it falls on this track.
- No names of people. The scaffold copies the text into `milestone.md` and the README, where the checker rejects names.

The checker fails while any of these is missing. Show the user the planning review block of `check_specs.py --report` and go through each line with them.

## 11. Fill in plan.yaml

Write the decisions into `docs/spec/plan.yaml`. The annotated `plan.yaml` template in the templates folder inside this skill shows every field. Then run the checker. Ask the user to read the schedule and to say yes before you scaffold the folder.
