# Installing the developer skill

Each person installs the skill once, in the agent they use. Then they start a new session.

## With the skills command line tool

The tool needs Node.js. Run one line from the project root. Add `-g` to install for your user instead of the project. The tool copies the folder, so run it again after the skill changes.

```bash
npx skills add <repository tree url of the skill folder> -a claude-code
npx skills add <repository tree url of the skill folder> -a github-copilot
npx skills add <repository tree url of the skill folder> -a cursor
npx skills add <repository tree url of the skill folder> -a codex
npx skills add <repository tree url of the skill folder> -a gemini-cli
npx skills add <repository tree url of the skill folder> -a bob
```

The tree url looks like `https://github.com/<owner>/<repo>/tree/<branch>/<dev_skill_path>`. For a private repository the tool uses the Git credentials already on the computer. `npx skills add --help` lists every option, and https://skills.sh lists every supported agent.

## By copying or linking the folder

A symbolic link keeps the skill in step with `git pull`. From the repository root on macOS or Linux:

```bash
ln -s "$(pwd)/<dev_skill_path>" <skills folder>/<skill name>
```

On Windows, from a Command Prompt with Developer Mode on:

```bat
mklink /D <skills folder>\<skill name> %CD%\<dev_skill_path with backslashes>
```

Where each agent looks for skills:

| Agent | Project folder | User folder |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `.agents/skills/` | `~/.copilot/skills/` |
| Cursor | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `.agents/skills/` | `~/.gemini/skills/` |
| IBM Bob | `.bob/skills/` | `~/.bob/skills/` |
| Any other agent that reads Agent Skills | its project skills folder | its user skills folder |

A project folder is shared with the team when it is committed. A user folder is private to one person.

## Without installing

Say to the agent: "Read `<dev_skill_path>/SKILL.md` and follow it for work item <id>." This works in any agent that can read files.

## Generic path

If your agent is not listed, find its documentation for skills or custom instructions. The Agent Skills format is a folder with a `SKILL.md` that has `name` and `description` in its frontmatter. Put the folder where the agent looks, or point the agent at the file.

## Check that it works

Start a new session. Name the first item, for example "Work on <first id>." The agent should open the specification for that id, read the sections of the ground truth it cites, and state a short plan before it writes code.

## Team rollout

1. One person installs and runs the smoke test.
2. The team lead sends the line for each agent in use.
3. Each person installs and runs the smoke test. Anyone for whom it fails posts the agent name and the first thing the agent said.
4. Add the install line to the project README.
