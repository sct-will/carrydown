# Other installation options

This page is for a plan owner who wants a different installation scope, needs to name the agent explicitly or cannot install Node.js. Most people use [the default route in the setup guide](setup.md#install-the-two-skills) instead.

The default route in the setup guide installs both skills for one agent in one project. Use these options only if you want a different scope, need to select an agent explicitly or cannot use the installer. After an alternative installation, continue with [check the installation](setup.md#check-the-installation), or [start your plan](setup.md#start-your-plan) after a manual installation.

## Choose where to install

**This project is the recommended starting point.** The skills are available in the project folder where you run the command. Open that folder whenever you use carrydown.

**All your projects is a personal installation.** It makes the skills available to your agent across projects on this computer. It does not install them for other people. Choose one scope; you do not need to run both commands.

Open your agent's entry below for complete commands. Each command selects both carrydown skills and the named agent. You still review the installer's confirmation.

<details>
<summary>Claude Code</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent claude-code
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent claude-code --global
```

</details>

<details>
<summary>GitHub Copilot</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent github-copilot
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent github-copilot --global
```

</details>

<details>
<summary>Cursor</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent cursor
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent cursor --global
```

</details>

<details>
<summary>Codex</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent codex
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent codex --global
```

</details>

<details>
<summary>Gemini CLI</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent gemini-cli
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent gemini-cli --global
```

</details>

<details>
<summary>IBM Bob</summary>

**This project:** run this from your project folder.

```bash
npx skills add sct-will/carrydown --skill '*' --agent bob
```

**All your projects:** run this instead for a personal installation.

```bash
npx skills add sct-will/carrydown --skill '*' --agent bob --global
```

</details>

## Manual install, without Node.js

<details>
<summary>Installation steps and destination folders</summary>

Use this route if you cannot install Node.js. You still need a coding agent, Python and Git to use carrydown for planning. Skip the `npx` commands in the setup guide.

1. Open [the carrydown repository](https://github.com/sct-will/carrydown) in your browser. Choose **Code**, then **Download ZIP**.
2. Extract the downloaded archive. Open the extracted folder, then open `skills`. It contains `carrydown-ground-truth` and `carrydown-plan-to-github`.
3. Find your agent in the destination table below. Choose the project column for this project, or the home column for a personal installation. Create the destination folders if they do not exist. On Windows, your home folder is usually under `C:\Users\` followed by your account name.
4. Copy both complete skill folders into that destination. Copy their contents together, including `SKILL.md`, `scripts`, `templates` and `references`. Copying only `SKILL.md` leaves the scripts out.
5. If folders beginning with a dot are hidden, press Command, Shift and Period in macOS Finder. In Windows File Explorer, enable **Hidden items** in the View menu. On many Linux file managers, Control and H shows hidden files.
6. Open each copied skill folder and confirm that `SKILL.md` and its supporting folders are inside. For example, a project installation using the shared skills folder has `.agents/skills/carrydown-ground-truth/SKILL.md` and `.agents/skills/carrydown-plan-to-github/SKILL.md`.
7. Close and reopen your agent in the project folder. Continue at [start your plan](setup.md#start-your-plan). If the agent does not recognize the first skill, use the explicit start phrase in [the setup guide's help](setup.md#the-agent-does-not-see-the-skills).

A dot at the beginning of a folder name means it may be hidden. `~/` means your home folder, such as `/Users/your-name/` on macOS or `C:\Users\your-name\` on Windows.

| Agent | Inside your project folder | Inside your home folder |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `.agents/skills/` | `~/.copilot/skills/` |
| Cursor | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `.agents/skills/` | `~/.gemini/skills/` |
| IBM Bob | `.bob/skills/` | `~/.bob/skills/` |

</details>

<details>
<summary>Preview the skills or install for every agent</summary>

**Preview before installing.** This lists the skills available from carrydown. It does not install them.

```bash
npx skills add sct-will/carrydown --list
```

**Install for every supported agent.** This installs both skills for all agents at project scope and skips the installer's confirmation prompts. Use it only when you want that broader installation.

```bash
npx skills add sct-will/carrydown --all
```

For the usual installation, use the default route in the setup guide.

</details>
