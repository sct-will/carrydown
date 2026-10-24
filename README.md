# carrydown

Carry an enterprise ground-truth document down into a governed plan: one specification per work item, GitHub sub-epics and issues, a populated GitHub Project board, and a developer skill in every issue.

It is a kit of three Agent Skills and a few Python scripts. You talk to your coding agent. The agent interviews you, drafts the plan, writes the specifications to a template, checks them mechanically, and, after you say yes, builds the GitHub structure.

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

Replace `claude-code` with your agent's name from the list below. Add `-g` to install for your user instead of the current project. Run `npx skills add sct-will/carrydown` with no options to choose from a list. Run `npx skills add sct-will/carrydown --list` to see the skills first.

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

## Say it to your agent

After installing, open your agent in your project folder and say:

> Use the carrydown-ground-truth skill. My ground truth is in docs/source/architecture.docx. Carry it down into a plan.

Then:

> Use the carrydown-plan-to-github skill. Put this plan in your-org/your-repo.

Then:

> Use the carrydown-dev-skill skill. Generate the developer skill.

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

On GitHub: labels, one sub-epic per milestone, one issue per work item, a roll-up comment on the Epic, and a project board.

## The sample

[sample/expense-approvals/](sample/expense-approvals/) is a fictional internal expense approvals service. It has a short architecture document (context, requirements, architecture, two governance rules, a development standard, a business analyst note, interfaces and risks), two people and an advisor, and an 11-week timeline with a pause. The worked output is next to it: `plan.yaml`, five milestones, nine complete specifications, and the generated developer skill. It is a sample to be replaced by your own material. [docs/sample-run.md](docs/sample-run.md) shows a real run of the scripts on it against a throwaway repository.

## Run the scripts by hand

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

## Supported agents

These are the agents the skills installer supports at the time of writing, from its documentation at https://github.com/vercel-labs/skills/blob/main/docs/agents.md. The list grows. Run `npx skills add --help` for the current one. The name in the second column is the value for `-a`.

| Agent | `--agent` value | Project folder | User folder |
| --- | --- | --- | --- |
| AiderDesk | `aider-desk` | `.aider-desk/skills/` | `~/.aider-desk/skills/` |
| Amp, Replit, Universal | `amp`, `replit`, `universal` | `.agents/skills/` | `~/.config/agents/skills/` |
| Antigravity | `antigravity` | `.agents/skills/` | `~/.gemini/antigravity/skills/` |
| Antigravity CLI | `antigravity-cli` | `.agents/skills/` | `~/.gemini/antigravity-cli/skills/` |
| AstrBot | `astrbot` | `data/skills/` | `~/.astrbot/data/skills/` |
| Autohand Code CLI | `autohand-code` | `.autohand/skills/` | `~/.autohand/skills/` |
| Augment | `augment` | `.augment/skills/` | `~/.augment/skills/` |
| IBM Bob | `bob` | `.bob/skills/` | `~/.bob/skills/` |
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| OpenClaw | `openclaw` | `skills/` | `~/.openclaw/skills/` |
| Cline, Codex, Dexto, fx, Kimi Code CLI, Loaf, Pi, Sarvam Code, Warp, Zed | `cline`, `codex`, `dexto`, `fx`, `kimi-code-cli`, `loaf`, `pi`, `sarvam-code`, `warp`, `zed` | `.agents/skills/` | `~/.agents/skills/` |
| CodeArts Agent | `codearts-agent` | `.codeartsdoer/skills/` | `~/.codeartsdoer/skills/` |
| CodeBuddy | `codebuddy` | `.codebuddy/skills/` | `~/.codebuddy/skills/` |
| Codemaker | `codemaker` | `.codemaker/skills/` | `~/.codemaker/skills/` |
| Code Studio | `codestudio` | `.codestudio/skills/` | `~/.codestudio/skills/` |
| Command Code | `command-code` | `.commandcode/skills/` | `~/.commandcode/skills/` |
| Continue | `continue` | `.continue/skills/` | `~/.continue/skills/` |
| Cortex Code | `cortex` | `.cortex/skills/` | `~/.snowflake/cortex/skills/` |
| Crush | `crush` | `.crush/skills/` | `~/.config/crush/skills/` |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` |
| Deep Agents | `deepagents` | `.agents/skills/` | `~/.deepagents/agent/skills/` |
| Devin for Terminal | `devin` | `.devin/skills/` | `~/.config/devin/skills/` |
| Droid | `droid` | `.agents/skills/` | `~/.factory/skills/` |
| Eve | `eve` | `agent/skills/` | N/A (project-only) |
| Firebender | `firebender` | `.agents/skills/` | `~/.firebender/skills/` |
| ForgeCode | `forgecode` | `.forge/skills/` | `~/.forge/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` |
| Goose | `goose` | `.goose/skills/` | `~/.config/goose/skills/` |
| Grok Build | `grok` | `.grok/skills/` | `~/.grok/skills/` |
| Hermes Agent | `hermes-agent` | `.hermes/skills/` | `~/.hermes/skills/` |
| inference.sh | `inference-sh` | `.inferencesh/skills/` | `~/.inferencesh/skills/` |
| Jazz | `jazz` | `.jazz/skills/` | `~/.jazz/skills/` |
| Junie | `junie` | `.junie/skills/` | `~/.junie/skills/` |
| iFlow CLI | `iflow-cli` | `.iflow/skills/` | `~/.iflow/skills/` |
| Kilo Code | `kilo` | `.agents/skills/` | `~/.kilo/skills/` |
| Kimchi | `kimchi` | `.kimchi/skills/` | `~/.config/kimchi/harness/skills/` |
| Kiro CLI | `kiro-cli` | `.kiro/skills/` | `~/.kiro/skills/` |
| Kode | `kode` | `.kode/skills/` | `~/.kode/skills/` |
| Lingma | `lingma` | `.lingma/skills/` | `~/.lingma/skills/` |
| MCPJam | `mcpjam` | `.mcpjam/skills/` | `~/.mcpjam/skills/` |
| MiniMax Code | `minimax-code` | `.minimax/skills/` | `~/.minimax/skills/` |
| Mistral Vibe | `mistral-vibe` | `.vibe/skills/` | `~/.vibe/skills/` |
| Moxby | `moxby` | `.moxby/skills/` | `~/.moxby/skills/` |
| Mux | `mux` | `.mux/skills/` | `~/.mux/skills/` |
| OpenCode | `opencode` | `.agents/skills/` | `~/.config/opencode/skills/` |
| OpenHands | `openhands` | `.openhands/skills/` | `~/.openhands/skills/` |
| Ona | `ona` | `.ona/skills/` | `~/.ona/skills/` |
| Posit Assistant | `posit-assistant` | `.posit/assistant/skills/` | `~/.posit/assistant/skills/` |
| Qoder | `qoder` | `.qoder/skills/` | `~/.qoder/skills/` |
| Qoder CN | `qoder-cn` | `.qoder/skills/` | `~/.qoder-cn/skills/` |
| Qwen Code | `qwen-code` | `.qwen/skills/` | `~/.qwen/skills/` |
| Reasonix | `reasonix` | `.reasonix/skills/` | `~/.reasonix/skills/` |
| Rovo Dev | `rovodev` | `.rovodev/skills/` | `~/.rovodev/skills/` |
| Roo Code | `roo` | `.roo/skills/` | `~/.roo/skills/` |
| Tabnine CLI | `tabnine-cli` | `.tabnine/agent/skills/` | `~/.tabnine/agent/skills/` |
| Terramind | `terramind` | `.terramind/skills/` | `~/.terramind/skills/` |
| Tinycloud | `tinycloud` | `.tinycloud/skills/` | `~/.tinycloud/skills/` |
| Trae | `trae` | `.trae/skills/` | `~/.trae/skills/` |
| Trae CN | `trae-cn` | `.trae/skills/` | `~/.trae-cn/skills/` |
| Windsurf | `windsurf` | `.windsurf/skills/` | `~/.codeium/windsurf/skills/` |
| ZCode | `zcode` | `.zcode/skills/` | `~/.zcode/skills/` |
| Zencoder, Zenflow | `zencoder`, `zenflow` | `.zencoder/skills/` | `~/.zencoder/skills/` |
| Neovate | `neovate` | `.neovate/skills/` | `~/.neovate/skills/` |
| Pochi | `pochi` | `.pochi/skills/` | `~/.pochi/skills/` |
| PromptScript | `promptscript` | `.agents/skills/` | N/A (project-only) |
| AdaL | `adal` | `.adal/skills/` | `~/.adal/skills/` |

Any other agent that reads the Agent Skills format (https://agentskills.io) can use the skills by placing the three skill folders where it looks for skills, or by being told to read `skills/<name>/SKILL.md`.

## Documents

- [START-HERE.md](START-HERE.md). The product manager path.
- [docs/method.md](docs/method.md). The eight steps.
- [docs/inputs.md](docs/inputs.md). The interview checklist.
- [docs/faq.md](docs/faq.md). Questions and answers.
- [docs/security.md](docs/security.md). Token handling, what is written where, dry run first.
- [docs/sample-run.md](docs/sample-run.md). A real run on the sample.
- [CHANGELOG.md](CHANGELOG.md).

## Licences

Code is licensed under the Apache License 2.0, see [LICENSE](LICENSE). The sample document, the templates text and the images are licensed under Creative Commons Attribution 4.0 International, see [LICENSE-CONTENT.md](LICENSE-CONTENT.md). Copyright 2026 Will Scott.
