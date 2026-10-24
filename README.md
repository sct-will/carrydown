![carrydown](docs/images/hero.png)

# carrydown

Turn your architecture document into a plan your team and its AI coding agents can follow: dated milestones, one spec per task tied to the paragraph it came from, GitHub issues, a filled project board, and a skill that makes each developer's agent read the spec first.

<!-- Static badges, because the dynamic ones show "repo not found" while the repository is private.
On publish day switch back to these dynamic badges:
https://img.shields.io/github/license/sct-will/carrydown
https://img.shields.io/github/last-commit/sct-will/carrydown
https://img.shields.io/github/issues/sct-will/carrydown -->
[![Licence: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE) [![Content: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-blue)](LICENSE-CONTENT.md) [![Agent Skills](https://img.shields.io/badge/Agent%20Skills-3%20skills-teal)](https://agentskills.io) [![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](#requirements-and-access) [![Open in Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sct-will/carrydown)

## See it in 60 seconds

No install. A fictional expense-approvals service, run end to end.

![A rendering of the project board as a table grouped by work unit](docs/images/board-table.png)

*A rendering of the sample output: the board as a table, grouped by work unit.*

![A rendering of the project board as a roadmap](docs/images/board-roadmap.png)

*A rendering of the sample output: the roadmap, with work units of different lengths.*

![A rendering of one issue next to the specification file it links to](docs/images/issue-and-spec.png)

*A rendering of the sample output: one issue and the spec file the agent reads first.*

- [The sample output page](docs/sample.md)
- [A spec file from the sample (WI-03)](sample/expense-approvals/docs/spec/m2-route-to-approvers/wi-03-routing-engine.md)
- [The live issues](https://github.com/sct-will/carrydown-sample/issues)
- [The live board](https://github.com/users/sct-will/projects/2)
- [The plan summary](docs/sample.md#plan)

## Install in one line

```bash
npx skills add sct-will/carrydown --all
```

Restart your agent.

## Getting started

1. Open your coding agent in your project folder. No folder yet? Say:

   > Make a folder called my-plan with a git repository and work there.

   You will see: the agent creating the folder and starting work in it.

2. Say:

   > Install carrydown for this agent: run npx skills add sct-will/carrydown --skill '*' -a \<your agent\>. If Node.js or Python 3 is missing, stop and tell me how to install it.

   Then restart the agent. You will see: the installer listing three skills.

3. Say:

   > Do you have the carrydown-ground-truth skill?

   You will see: yes, and its start sentence.

4. Put your .docx or .md file in `docs/source/`. Say:

   > Set up a project plan from docs/source/\<file\>.

   You will see: "carrydown: interview, step 1 of 6" and a few questions.

5. Answer, or say "use your default". Then say:

   > Show me the load table and the critical path.

   Then:

   > Yes, the plan is right.

   You will see: the schedule, the load table, the critical path, and the checker reporting 0 findings.

6. Say:

   > Create the GitHub issues and the board.

   Open the token link the agent gives you. Read the dry-run counts, then say:

   > Go ahead.

   You will see: "1 Epic, N sub-epics, N work item issues" and then the board link.

7. Say:

   > Generate the developer skill.

   Send each developer the install line it prints. You will see: the skill folder and the install line per agent.

The long form, with the interview, the review hour, the token and the team rhythm, is [docs/plan-owner-guide.md](docs/plan-owner-guide.md).

## How it works

![How carrydown works](docs/images/flow.png)

Planning decisions stay with people. The skills set up, draft to templates, validate and populate.

**`carrydown-ground-truth`**
- Interviews you, renders your documents to Markdown with stable section anchors, and scaffolds `docs/spec/` with `plan.yaml`.
- Drafts the plan with you: milestones, work units, tracks, dates, dependencies, load table, critical path, program boundary.
- Writes one specification per work item to a template, runs the checker, and gives review prompts for the document and the plan.

**`carrydown-plan-to-github`**
- Walks you through a GitHub token safely and runs a dry run before anything is written.
- After your yes, creates labels, one sub-epic per milestone, one issue per work item with sub-issue links, dependency links and an Epic roll-up comment.
- Builds the project board with work unit, track and date fields and three views, verifies the counts, and lists what you click by hand.

**`carrydown-dev-skill`**
- Generates the developer skill for your project from the specification folder.
- The skill makes each developer's agent read the spec, the cited sections and the conventions before it changes code.
- Its README shows each teammate how to install it in their agent.

## What you get

```text
docs/
  ground-truth/        rendered Markdown, section index, figures
  spec/
    plan.yaml          the schedule as data
    README.md          conventions, schedule, comment templates, index
    m1-.../            one folder per milestone
      milestone.md     the sub-epic content
      <id>-<slug>.md   one specification per work item
  dev/skills/<project>-dev/
    SKILL.md  README.md  references/
```

On GitHub: labels, one Epic, one sub-epic per milestone, one issue per work item as a sub-issue of its sub-epic, an Epic roll-up comment, and a project board with the Work unit, Track, Complete by and Checkpoint fields and Table, Board and Roadmap views.

## Install options

- `--all` installs the three skills for every coding agent found on this computer, without asking. The installer adds folders such as `.claude/` and `.agents/` to your project. Commit only the ones your team uses.
- `-a <agent>` installs for one agent. Example: `npx skills add sct-will/carrydown --skill '*' -a claude-code`.
- `-g` installs for your user instead of the current project.
- `--list` shows the skills without installing them. With no options the installer lets you choose from a list.

| Agent | `-a` value | Project folder | User folder |
| --- | --- | --- | --- |
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `codex` | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` |
| IBM Bob | `bob` | `.bob/skills/` | `~/.bob/skills/` |

The installer supports many more agents. The full and current list is in its documentation: https://github.com/vercel-labs/skills/blob/main/docs/agents.md.

Generic path. Any other agent that reads the Agent Skills format (https://agentskills.io) can use the skills. Copy the three folders in `skills/` into the folder where that agent looks for skills, or tell the agent to read `skills/<name>/SKILL.md`.

No Node.js? Skip the installer. Copy the three folders in `skills/` into your agent's skills folder from the table above. They are self-contained.

## Requirements and access

- **Node.js**, only to run the install line. Get it from https://nodejs.org (choose LTS). Nothing in the skills needs it after that.
- **Python 3.9 or later**, to run the scripts. Check with `python3 --version`. Nothing else to install, not even for Word files.
- **GitHub permission** to create issues in the repository and to create a Project in the organisation or account. Ask an organisation admin if you do not have it. Planning works without it. Only the GitHub step needs it.
- **Single sign-on (SSO).** If your organisation enforces it, authorise the token: github.com/settings/tokens, click the token's "Configure SSO" button, click "Authorize" next to the organisation.
- **A token**, created with the pre-filled link https://github.com/settings/tokens/new?scopes=repo,project&description=carrydown. It ticks `repo` and `project`. A fine-grained token also works for a project owned by an organisation, with Issues read and write, Metadata read, and the organisation permission Projects read and write. It does not work for a project owned by a user account. Use a classic token there.

## Run the scripts yourself

No agent and no token needed for these three commands.

```bash
git clone https://github.com/sct-will/carrydown.git
cd carrydown
python3 scripts/check_specs.py --root sample/expense-approvals --report
python3 scripts/github_sync.py --root sample/expense-approvals --offline
python3 scripts/github_project.py --root sample/expense-approvals --offline
```

Or open the repository in Codespaces. It opens on the sample output and runs the first two commands for you.

| Script | Purpose |
| --- | --- |
| `scripts/render_ground_truth.py` | `.docx` or `.md` to Markdown with a section index and figures. |
| `scripts/scaffold_spec.py` | Create `plan.yaml`, the README, milestone folders and stubs. Refresh headers. Add the checker to CI. |
| `scripts/check_specs.py` | Check specifications against `plan.yaml`. Print the load table and critical path. |
| `scripts/github_token.py` | Create and store a GitHub token safely, and check what it can do. |
| `scripts/github_sync.py` | Labels, sub-epics, issues, links and the Epic comment. |
| `scripts/github_project.py` | The GitHub Project board. |
| `scripts/generate_dev_skill.py` | The developer skill folder. |
| `scripts/selftest.py` | The repository's own checks, with no token. |
| `scripts/lint_prose.py` | The prose style checks. |
| `scripts/sync_skill_assets.py` | Maintainers: copy scripts and templates into each skill folder. |

Every script has `--help`. The ones that write are dry runs unless you pass `--apply`. The installer copies only a skill's folder, so each skill carries its own copy of the scripts and templates it runs. The top-level `scripts/` and `templates/` are the canonical copies.

## FAQ

**Does it write code?** No. It carries the plan down to the point where a developer and their agent can start. The developer skill then makes each work item start from its specification.

**What does it send to GitHub?** Issue titles and bodies built from your specification files, labels, and project fields. Nothing is sent without `--apply`. The scripts talk only to `api.github.com`. See [docs/security.md](docs/security.md).

**Can I use Jira?** Not yet. The GitHub scripts are for GitHub only. The specification folder and `plan.yaml` are plain files that another tool can read.

**What if my document has no section numbers?** Ask the agent to propose numbering in the source document, approve it, and have the agent render the document again. Specifications cite sections by number.

**How do I remove it?** Run `npx skills remove`, or delete the three skill folders. The files under `docs/` in your project are yours.

More answers, including "npx: command not found", are in [docs/faq.md](docs/faq.md).

## Words used here

<details>
<summary>Eight terms</summary>

- **Ground truth.** The document or documents the project must obey: architecture, requirements, rules, standards.
- **Work item.** The smallest piece of work a person can finish, show and close. It has one specification and one issue.
- **Work unit.** A time block with its own length and an exit gate. It replaces the fixed-length sprint.
- **Sub-epic.** A GitHub issue for one milestone, placed under the Epic. Its work items are sub-issues.
- **Load table.** A table of how much work each person has in each work unit.
- **Critical path.** The longest chain of items that depend on each other. It sets the earliest finish date.
- **Exit gate.** The one sentence that must be true for a work unit to count as done.
- **Program item.** Work the program owns outside the plan, such as recruiting a pilot team or getting an approval.

</details>

## Contributing

Contributions are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) explains how to report a problem, propose a change, run the checks (`python3 scripts/selftest.py` and `python3 scripts/lint_prose.py`) and get a review. Issue forms and a pull request template guide you. The two workflow files that run those checks are in [docs/workflows/](docs/workflows/README.md) until they are moved to `.github/workflows/`.

## Code of conduct

This project follows the Contributor Covenant. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). To report a problem, open an issue with the Conduct report form.

## Security

Report a vulnerability privately through GitHub. See [SECURITY.md](SECURITY.md). The carrydown skills store only your GitHub token file, and it never prints or commits the token.

## Licence

Code is licensed under the Apache License 2.0, see [LICENSE](LICENSE). The sample document, the templates text, the skills prose, the documents and the images are licensed under Creative Commons Attribution 4.0 International, see [LICENSE-CONTENT.md](LICENSE-CONTENT.md).

Copyright 2026 Will Scott.

Will Scott, Ph.D.
