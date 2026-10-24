# Drafting the plan with the human

You draft. The user decides. Stop for a yes after each step.

## 1. Read the ground truth

Read the rendered document, using its section index. Make a plain list of what must exist when the project is done, in the document's words, with section numbers. Note every contract, rule and standard. Note every statement that is unverified or contradicted. Show the list to the user and correct it.

## 2. Milestones

A milestone is a step the program can see working. Each one has:

- a name that says what the user can do after it,
- an exit gate, one sentence that a person can check live at the demonstration,
- acceptance criteria that you write now, before the work starts.

Aim for three to six milestones. Order them so that the first proves the whole path with the least behaviour, and the last proves the project can be released and run. Put contracts that two tracks share into the first milestone.

## 3. Work units

A work unit is a time box with its own length. Do not use the words sprint, story point or velocity. A work unit holds one milestone. Lengths differ: a short one for a thin first slice, a long one for the core. A rule of thumb is one to three weeks. Pauses sit between work units as breaks and are listed under `breaks` in `plan.yaml`.

Check: the sum of the work units plus breaks fits the time frame, and no work unit is longer than the user's limit.

## 4. Work items

A work item is the smallest piece of work that a person can finish, show and close. Aim for two to five days. Each has:

- an id, a number that stays fixed. Leave gaps for program-owned items,
- a short label in plain words,
- a milestone, a track and an owner on that track,
- a size such as "Medium, about 3 days" (the load table reads "about N days"),
- the ground truth sections it cites,
- dependencies by id.

Split an item if it spans two tracks or runs past five days. Merge items that cannot be shown separately.

## 5. Dates and order

- Set a completion date for each item inside its work unit, on a working day, not a day off of the owner.
- Use each person's percent allocation. A person's capacity in a work unit is their working days, minus days off, times their allocation. An item sized "about 4 days" needs about 4 divided by the allocation in working days: 4 days at 60 percent is nearly 7 working days of calendar time. Never plan a person past 100 percent of their allocated capacity in a work unit. The checker reports the load as a percentage of allocated capacity and flags any work unit over 100 percent.
- Check the end against the target. The checker prints the target and whether the critical path meets it.
- A dependency finishes on or before the item that needs it.
- Put the shared contract first, so both tracks can start from it.
- Keep a person on one theme at a time. Group related items for the same person in adjacent days to cut context switching.
- Leave slack before each checkpoint and before each demonstration.
- Alternate the checkpoint dates so that every item has a checkpoint on or after its completion date.

## 6. Checkpoints

A checkpoint is a short weekly integration check with both tracks present. Each has a date, a name and a joint check: what the tracks run together to prove their halves meet. Every item names one checkpoint. Demonstration dates are also checkpoints.

## 7. Load table and critical path

Run:

```bash
python3 <skill>/scripts/check_specs.py --root . --report
```

It prints the schedule, each person's allocation, their sized days against allocated capacity per work unit (with a flag over 100 percent), the critical path, the target and whether the critical path meets it, and the checkpoints. Read it with the user. A load of 100 percent or more leaves no slack, so aim for about 80 percent at most. If one person carries much more than the other, move items across tracks where the skills allow, or stretch the date. If the critical path runs through one person, say so and ask whether to change it.

## 8. The program boundary

Program-owned work stays outside the plan. Give each such item an id from the gap (for example 5 and 10) and list it under `program.items`. In an item that waits for one, set `program_input` to a phrase that says what is needed, without the id. Specifications never mention a program id. The checker fails if they do.

## 9. Review the plan

Use the plan review prompt in `review-prompts.md`. Fold in the findings the user accepts. Record rejected findings in your own notes, not in the specs.

## 10. Fill in plan.yaml

Write the decisions into `docs/spec/plan.yaml`. The annotated `plan.yaml` template in the templates folder inside this skill shows every field. Then run the checker. Ask the user to read the schedule and to say yes before you scaffold the folder.
