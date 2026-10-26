# Writing the specifications

One file per work item, named `<id>-<slug>.md` and placed in the milestone folder. `scaffold_spec.py --apply --stubs` writes each stub with the right title and header table. You fill the sections.

## What a specification is for

It orients the engineer and their coding agent so that they can finish one item without opening the original documents. It is the part of the ground truth that this item must honor, in the form an engineer starts from.

## Header table

Written by the scaffold script from `plan.yaml`. Do not edit it by hand. After a plan change, run `scaffold_spec.py --refresh-headers --apply`. The rows are: Milestone, Track, Target, Checkpoint (directly after Target), Demonstration, Size, Depends on, Unblocks, Ground truth.

## Sections, in this order

1. Why this work item exists. Three to six sentences. The problem in the ground truth, why it is its own item, what waits without it. Cite sections by number.
2. Outcome. Five to nine bullets of observable results that name files, endpoints, screens or behaviors.
3. Context for the agent. What exists today, which earlier items create what this one needs, which files and functions to read, which commands to run. Mark anything unverified "verify at implementation". Name only things you have seen.
4. Contract (or Protocol for items with no interface, such as a pilot). Copy the exact schemas, tables, rule texts, message texts and error codes from the ground truth. Word for word. Add a short lead-in, not new rules.
5. Implementation guide. Numbered steps in working order. Each names files and the check that proves it.
6. Acceptance criteria. Checkbox lines. Each is provable by a named test or a recorded check. Include criteria that come from governance rules and the development standard.
7. Evidence of completion. Starts with a paragraph beginning `Demo.` that says what can be shown at the checkpoint and how to see it in under two minutes. Then the list of artifacts to attach to the closing comment: pull requests, test suites with the run line, the artifact that proves the outcome, and any redaction.
8. Integration points. One sentence naming the counterpart items on the other track. Then bullets that start with `Crosses the boundary.`, `Joint check.` and `Handoff on close.` The joint check is this item's share of the checkpoint's joint check. Add `Timing.` when the counterpart is due within three working days.
9. Out of scope. What a reasonable person might add and should not, with a pointer to the item that has it, or a note that it is an external item.
10. Watch out for. Traps, ordering risks, security and data rules, contradictions found in the ground truth and which side wins.
11. References. Links to the ground truth sections (use the anchors in the section index), and to dependency and dependent specifications. Every link must resolve.
12. Decisions recorded. `None yet.` At the start. Later the engineer adds dated lines when the implementation departs from the file: `- 2027-03-02. What changed and why, with the pull request number.`

## Voice and rules

- Sentence-case headings. Short sentences. Spell out an acronym on first use in each file.
- No em dashes or en dashes.
- No names of people or handles. Say "the engineer", "the stakeholders", "the Workflow track".
- No AI vendor or model names. Say "the coding agent".
- No sprint vocabulary. Use work units.
- Do not mention the ids of external items.
- Dates are absolute, YYYY-MM-DD.
- Avoid colons inside prose sentences.
- Never guess. A wrong specific detail costs more than an honest "verify at implementation".

## Lengths

Technical items 90 to 260 lines. Run, pilot and documentation items 80 to 160 lines. The checker allows the range in `limits.spec_lines` of `plan.yaml`.

## Writing in batches

1. Make sure `plan.yaml` is approved and the stubs exist.
2. Split the items into batches of two or three. Keep related items in one batch.
3. Fill in `spec-writer-brief.md` once: the project folder, the rendered source paths and precedence, the layout of code the project will have, one paragraph per item. Use the same brief for every batch.
4. In each batch, edit only that batch's stubs. Leave the title and header table alone. Run `check_specs.py --item N` for each item until it is clean.
5. When every batch is done, read every file again. Check contract excerpts against the ground truth. Check that dependency items agree on names and shapes. Run the whole checker.

## Conflicts inside the ground truth

You will find contradictions while writing. Do not paper over them.

- Choose the winner by the source precedence the user gave in the interview.
- State the conflict and the winner in "Watch out for".
- Keep a list for the next version of the ground truth.
- Do not edit the ground truth silently.

## Your review of the set

After the files exist, read them in dependency order. Check that:

- contracts quoted in two files are identical,
- the integration points of a pair of items name the same crossing,
- no acceptance criterion needs a thing that no item creates,
- the ground truth sections cited exist and say what the file claims,
- dates and owners in prose match the header.
