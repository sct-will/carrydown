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
- [ ] The conventions match the specification README and `plan.yaml`.
- [ ] The definition of done matches what the issues say.
- [ ] Commands run: copy each into a terminal in a scratch clone.
- [ ] Nothing in it names a person.

## References

- [ ] `work-items.md` lists every item once, with the right dates and file paths.
- [ ] Every file path in `work-items.md` exists.
- [ ] `contracts.md` lists each Contract or Protocol section with its file. Add the shared contracts that matter most.
- [ ] `ground-truth-map.md` has the headings with line numbers. The anchors match the rendering. Add topics where useful.

## README

- [ ] The install lines use the right repository and branch.
- [ ] The table of skills folders matches the agents the engineers use.
- [ ] It says the specification folder is canonical.

## Smoke test

Install the skill in one agent, start a new session and name the first item, for example "Work on <first id>". The agent should name the specification file, read it, and read only the cited sections of the ground truth. If it does not, fix the description.
