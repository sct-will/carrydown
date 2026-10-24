![carrydown](docs/images/hero.png)

# carrydown

Carrydown carries an enterprise ground-truth document down into a governed plan. From an architecture document, requirements or rules it builds one specification per work item, GitHub sub-epics and issues, a populated GitHub Project board, and a developer skill in every issue. It is a kit of three Agent Skills and a few Python scripts that you drive by talking to your coding agent.

[![Licence](https://img.shields.io/github/license/sct-will/carrydown)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/sct-will/carrydown)](https://github.com/sct-will/carrydown/commits/main)
[![Issues](https://img.shields.io/github/issues/sct-will/carrydown)](https://github.com/sct-will/carrydown/issues)

## Table of contents

- [What it is](#what-it-is)
- [Who it is for](#who-it-is-for)
- [Install](#install)
- [The three skills](#the-three-skills)
- [The flow](#the-flow)
  - [Say it to your agent](#say-it-to-your-agent)
  - [What you get](#what-you-get)
- [Supported agents](#supported-agents)
- [The sample](#the-sample)
  - [Run the scripts by hand](#run-the-scripts-by-hand)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Code of conduct](#code-of-conduct)
- [Security](#security)
- [Licence](#licence)

## What it is

You bring the document a project must obey. You and your agent turn it into a plan with milestones, people, dates and dependencies. Each work item gets a specification tied to the sections of the document it comes from. A checker compares every specification to the plan. After you say yes, the kit creates the issues and the board on GitHub. Planning decisions stay with people. The skills set up, draft to templates, validate and populate.

## Who it is for

- Engineering leaders and product managers who run a project that must follow an architecture document, governance rules and a development standard.
- Teams with two or more people on parallel tracks, working with coding agents in their editors.
- Anyone who wants to answer "which paragraph of the document was this built from?" for every issue.

If you are a product manager, read [START-HERE.md](START-HERE.md). You need one terminal command.

## Install

```bash
npx skills add sct-will/carrydown --all
```

`--all` installs every skill to every agent the installer supports, without asking. To install all three skills for one agent only, name it.

```bash
npx skills add sct-will/carrydown --skill '*' -a claude-code
```

Replace `claude-code` with your agent's name from the table below. Add `-g` to install for your user instead of the current project. Run `npx skills add sct-will/carrydown` with no options to choose from a list. Run `npx skills add sct-will/carrydown --list` to see the skills first.

The installer is the Vercel Labs `skills` command line tool. Its documentation is at https://github.com/vercel-labs/skills. You need Node.js. The scripts in the skills need Python 3.9 or later. Reading Word files needs the `lxml` package (`pip install lxml`).

## The three skills

| Skill | What it does |
| --- | --- |
| `carrydown-ground-truth` | Interviews you for the inputs. Renders your documents to Markdown with stable section anchors. Scaffolds `docs/spec/` with `plan.yaml`. Drafts the plan with you: milestones, work units, tracks, items, dates, dependencies, load table, critical path, program boundary. Writes one milestone file and one specification per item to a template, in parallel where your agent supports it. Runs the checker. Gives review prompts for the document and the plan. |
| `carrydown-plan-to-github` | Walks you through a GitHub token safely. Runs a dry run. After your yes, creates labels, one sub-epic per milestone, one issue per work item with sub-issue links, dependency links and an Epic roll-up comment. Builds a GitHub Project board with a work unit iteration field, track and date fields, and three views. Verifies the counts. Lists what you must click by hand. |
| `carrydown-dev-skill` | Generates the developer skill for your project from the specification folder, with a README that shows each teammate how to install it in their agent. |

## The flow

```text
ground truth documents (.docx or .md)
        |  render_ground_truth.py
        v
docs/ground-truth/*.md  + section index
        |  interview, plan with the human, scaffold_spec.py
        v
docs/spec/plan.yaml  +  README  +  milestone.md  +  one specification per item
        |  check_specs.py  (mechanical review against the plan)
        v
        |  github_sync.py  (dry run first, then --apply)
        v
GitHub: labels, sub-epics, issues, sub-issue links, Epic roll-up
        |  github_project.py  (dry run first, then --apply)
        v
GitHub Project board: Work unit, Track, Complete by, Checkpoint, 3 views
        |  generate_dev_skill.py
        v
docs/dev/skills/<project>-dev/  installed in every developer's agent
```

Planning decisions stay with people. The skills set up, draft to templates, validate and populate.

### Say it to your agent

After installing, open your agent in your project folder and say these three sentences, one at a time, as you reach each stage.

> Set up a project plan from this document.

> Create the GitHub issues and the board.

> Generate the developer skill.

If your agent does not pick the skill up on its own, put the skill name first: "Use the carrydown-ground-truth skill. Set up a project plan from this document." The other two skills are `carrydown-plan-to-github` and `carrydown-dev-skill`.

### What you get

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

On GitHub: labels, one sub-epic per milestone, one issue per work item, a roll-up comment on the Epic, and a project board.

## Supported agents

These agents are tested paths. The name in the second column is the value for `-a`.

| Agent | `-a` value | Project folder | User folder |
| --- | --- | --- | --- |
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `codex` | `.agents/skills/` | `~/.agents/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` |

The installer supports many more agents. The full and current list is in the skills command line tool documentation: https://github.com/vercel-labs/skills/blob/main/docs/agents.md. Run `npx skills add --help` for the options.

Generic path. Any other agent that reads the Agent Skills format (https://agentskills.io) can use the skills. Copy the three folders in `skills/` into the folder where that agent looks for skills, or tell the agent to read `skills/<name>/SKILL.md`.

## The sample

[sample/expense-approvals/](sample/expense-approvals/) is a fictional internal expense approvals service. It has a short architecture document (context, requirements, architecture, two governance rules, a development standard, a business analyst note, interfaces and risks), two people and an advisor, and an 11-week timeline with a pause. The worked output is next to it: `plan.yaml`, five milestones, nine complete specifications, and the generated developer skill. It is a sample to be replaced by your own material. [docs/sample-run.md](docs/sample-run.md) shows a real run of the scripts on it against a throwaway repository.

### Run the scripts by hand

Every script has `--help`, and the ones that write are dry runs unless you pass `--apply`.

| Script | Purpose |
| --- | --- |
| `scripts/render_ground_truth.py` | `.docx` or `.md` to Markdown with a section index and figures. |
| `scripts/scaffold_spec.py` | Create `plan.yaml`, the README, milestone folders and stubs. Refresh headers. |
| `scripts/check_specs.py` | Check specifications against `plan.yaml`. Print the load table and critical path. |
| `scripts/github_token.py` | Create and store a GitHub token safely, and check its scopes. |
| `scripts/github_sync.py` | Labels, sub-epics, issues, links and the Epic comment. |
| `scripts/github_project.py` | The GitHub Project board. |
| `scripts/generate_dev_skill.py` | The developer skill folder. |
| `scripts/sync_skill_assets.py` | Maintainers: copy scripts and templates into each skill folder. |

The installer copies only a skill's folder, so each skill carries its own copy of the scripts and templates it runs. The top-level `scripts/` and `templates/` are the canonical copies.

## Documentation

- [START-HERE.md](START-HERE.md). The product manager path.
- [docs/method.md](docs/method.md). The eight steps.
- [docs/inputs.md](docs/inputs.md). The interview checklist.
- [docs/faq.md](docs/faq.md). Questions and answers.
- [docs/security.md](docs/security.md). Token handling, what is written where, dry run first.
- [docs/sample-run.md](docs/sample-run.md). A real run on the sample.
- [CHANGELOG.md](CHANGELOG.md).

## Contributing

Contributions are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) explains how to report a problem, propose a change, run the checks (`python3 scripts/selftest.py` and `python3 scripts/lint_prose.py`) and get a review. Issue forms and a pull request template guide you. The two workflow files that run those checks are in [docs/workflows/](docs/workflows/README.md) until they are moved to `.github/workflows/`.

## Code of conduct

This project follows the Contributor Covenant. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). To report a problem, open an issue with the Conduct report form.

## Security

Report a vulnerability privately through GitHub. See [SECURITY.md](SECURITY.md). The kit stores only your GitHub token file, and it never prints or commits the token.

## Licence

Code is licensed under the Apache License 2.0, see [LICENSE](LICENSE). The sample document, the templates text, the skills prose, the documents and the images are licensed under Creative Commons Attribution 4.0 International, see [LICENSE-CONTENT.md](LICENSE-CONTENT.md).

Copyright 2026 Will Scott.

Will Scott, Ph.D.
