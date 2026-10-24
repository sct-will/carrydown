# Review checklist for a generated skill

Go through this with the user before you call the skill done.

## Frontmatter

- [ ] `name` is lowercase with hyphens and matches the folder name.
- [ ] `description` starts with "Use when".
- [ ] `description` is under 1,024 characters. The generator prints the length.
- [ ] `description` has no colon followed by a space (some parsers read it as a new key).
- [ ] `description` names the triggers a developer would use: the ids, the file names, the folders.

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
- [ ] The table of skills folders matches the agents your team uses.
- [ ] It says the specification folder is canonical.

## Smoke test

Install the skill in one agent, start a new session and name the first item, for example "Work on <first id>". The agent should name the specification file, read it, and read only the cited sections of the ground truth. If it does not, fix the description.
