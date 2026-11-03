# Review checklist for the engineers' skill

Go through this with the user before you call the skill done.

## Frontmatter

- [ ] `name` is lowercase with hyphens and matches the folder name.
- [ ] `description` says what the skill does, then "Use when" and the triggers.
- [ ] `description` is short. The generator targets under 250 characters and warns above 300, because long descriptions are the first to be dropped when an agent lists many skills. It prints the length.
- [ ] `description` stays inside its quotes. The generator quotes it, so a colon is safe. Keep the quotes if you edit it.
- [ ] `description` names the triggers an engineer would use: the ids, the file names, the folders.

## SKILL.md

- [ ] The orient steps name the right paths for this project.
- [ ] The example id and example path exist.
- [ ] Step 4 runs `scripts/check_context.py <ID>`, reads `docs/context/<id>.md` on exit 0 and stops with the message on any other exit. It tells the agent not to open `docs/ground-truth/` or any source.
- [ ] The conventions match the specification README and `plan.yaml`.
- [ ] The definition of done matches what the issues say.
- [ ] Commands run: copy each into a terminal in a scratch clone.
- [ ] Nothing in it names a person.
- [ ] The rule on change requests matches the project's setting: where engineers may not edit approved text, the last orient step asks for a `Rule clarification request` comment and posts nothing without the engineer's permission.

## References

- [ ] `work-items.md` lists every item once, with the right dates and file paths.
- [ ] Every file path in `work-items.md` exists.
- [ ] `contracts.md` lists each Contract or Protocol section with its file and points to the bundles. Add the shared contracts that matter most.
- [ ] `ground-truth-map.md` lists only source sections that appear in at least one approved context, by source id and section number. It names no original file, no version and no coverage limit.

## README

- [ ] The install lines use the right repository and branch.
- [ ] The table of skills folders matches the agents the engineers use.
- [ ] It says the specification folder is canonical.
- [ ] It says what a bundle holds, that every reader of the repository can read every bundle, and that the check is a convenience in the engineer's own checkout and not a security control.
- [ ] It lists the four block messages with what to do, the offline grace rule and that a new clone needs one successful refresh first, and the Windows form of the command.

## Smoke test

Install the skill in one agent, start a new session and name the first item, for example "Work on <first id>". The agent should name the specification file, read it, run the context check, and read the approved context of the item. It should not open `docs/ground-truth/` or any source document. If it does, fix the description or the orient step.
