# Brief for specification writers

Copy this brief, fill in the fields in angle brackets once, and use the same text for every batch of items along with its item ids. Remove this paragraph.

---

You are completing work item specification files for <project name>. Each file orients an engineer and the coding agent in their editor so they can finish one work item without opening the original documents. Write only the files assigned to you. Do not edit any other file. Do not run git commands that change state. Do not install anything.

## Read first, in this order

1. `<spec folder>/README.md`, the conventions, schedule and comment templates.
2. `<spec folder>/plan.yaml`, the plan. Do not change it.
3. `<rendered source paths in precedence order>`, the ground truth. Use each section index. For a long document read only the sections your items cite, with `sed -n 'START,ENDp'` and the line numbers in its index file.
4. Your assigned stub files. Each has the correct title and header table and a skeleton with TODO lines. Do not edit the title or the header table.
5. The code your item touches, if the project has code today: <list the key files and folders>. Read it before you cite it.

## Layout of the code to be written

<List the folders and files the project will have, one line each. Writers must not invent other top-level folders. Say which files exist today and which items create the rest.>

## Template

Sections in this exact order and with these exact headings: Why this work item exists, Outcome, Context for the agent, Contract (or Protocol for items with no interface), Implementation guide, Acceptance criteria, Evidence of completion, Integration points, Out of scope, Watch out for, References, Decisions recorded.

- Evidence of completion starts with a paragraph that begins `Demo.` and ends with the sentences about attaching to the closing comment (see the stub).
- Integration points has bullets that begin `Crosses the boundary.`, `Joint check.` and `Handoff on close.`
- Acceptance criteria are checkbox lines `- [ ] ...`, each provable by a named test or a recorded check.
- Contract excerpts are copied word for word from the ground truth.
- Decisions recorded is exactly `None yet.`

Length: <usual range, for example 90 to 150 lines>.

## Rules

- Sentence-case headings. Short sentences. Spell out an acronym on first use.
- No em dashes or en dashes. No colons inside prose sentences.
- No names of people or handles. Say "the engineer", "the stakeholders", "the <track> track".
- No AI vendor, model or tool names. Say "the coding agent".
- No sprint vocabulary. Dates are absolute.
- Never mention these ids of external items, owned outside the team: <external item ids>. Refer to an external input in words.
- Every command, flag, path and function you name must come from the ground truth, the layout above or code you have read. If a detail cannot be verified, write "verify at implementation" and say what to look for.
- Remove every TODO marker.

## Per-item guidance

<One paragraph per item: what it builds, which sections it cites, which earlier items it depends on, which later items it unblocks, known traps and conflicts in the ground truth and which side wins.>

## Check your work

Run `python3 <skill>/scripts/check_specs.py --root <project root> --item N` for each of your ids until it reports 0 findings for them. Findings about other items are not yours.

## Report

List each file with its line count and the checker result. Name anything in the ground truth that was ambiguous or contradictory. Keep it short.
