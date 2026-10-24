# {{tag}} {{label}}

{{header}}

## Why this work item exists

TODO: Two to five sentences. Name the problem in the ground truth that this item solves, why it is a separate item, and what breaks or waits without it. Cite sections by number. The Ground truth row in the header above lists the sections the item is built from; the body may cite other sections for context.

## Outcome

TODO: A bullet list of what exists when the item is done. Each bullet names a file, endpoint, table, screen or behaviour that someone can point at.

## Context for the agent

TODO: Facts the coding agent needs before it writes code. What exists today, which files and functions to read, which commands to run, which details are unverified and must be checked ("verify at implementation"). Name only files and functions you have seen.

## Contract

TODO: Copy the exact schemas, field tables, message texts and rules from the ground truth that this item must honour. Quote them faithfully. Do not paraphrase a schema. Use "## Protocol" instead of "## Contract" for items that have no interface, such as a pilot or a measurement.

## Implementation guide

TODO: Numbered steps in the order an engineer would do them. Each step names the files to touch and the check that proves the step.

## Acceptance criteria

- [ ] TODO: One checkbox per criterion. Each is provable by a named test or a recorded check.
- [ ] TODO: Add the criteria that come from governance rules and the development standard.

## Evidence of completion

Demo. TODO: What can be shown at the checkpoint that could not be shown before, and the shortest way to see it, in under two minutes.

Attach to the closing comment on the issue, in the template from the folder README.

- The pull request or requests.
- TODO: The test suites by file, with the run line.
- TODO: The artifact that proves the outcome: a response body, a screenshot, a record table, a diff.

The coding agent produces these from the commands above. The engineer checks them before posting.

## Integration points

TODO: One sentence naming the counterpart items on the other track, by id and label, or say that no item on the other track depends on this one.

- Crosses the boundary. TODO: The concrete thing that passes between the tracks, such as a schema file, an endpoint, a package or a fixture folder.
- Joint check. TODO: What the engineers on both tracks run together at the checkpoint named in the header.
- Handoff on close. TODO: What the engineer on this item tells the engineer on the counterpart item in the closing comment, or "none".

## Out of scope

TODO: What a reasonable person might add to this item and should not. Point to the item that has it, or say it is an external item.

## Watch out for

TODO: The traps. Contradictions found in the ground truth, ordering risks, security and data rules, flaky tests.

## References

- TODO: The ground truth sections cited in the header, as links into the rendered document.
- TODO: The specifications of the items in Depends on and Unblocks.

## Decisions recorded

None yet.
