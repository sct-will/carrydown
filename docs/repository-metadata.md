# Repository metadata proposal

A proposal for the maintainer to apply by hand. Nothing here has been written to GitHub. It sets the repository's description, homepage, topics and social preview to match the README, and proposes the first screen of the sample repository's README.

## sct-will/carrydown

**Description** (129 characters, the tagline on the README hero image, so the repository page, search results and link previews all say the same thing):

```text
An AI agent plans the project around real people, then carries the architecture to every issue and every engineer's coding agent.
```

The current description, a longer line that also gives an out-of-date count of the skills, is a third tagline and should go.

**Homepage:** `[ARTICLE URL]`, the published article, once it is live. Until then, leave the field empty rather than pointing it at the sample.

**Topics** (ten, all lowercase with hyphens, as GitHub requires):

1. `agent-skills`
2. `coding-agents`
3. `ai-agents`
4. `spec-driven-development`
5. `project-planning`
6. `github-projects`
7. `software-architecture`
8. `ai-governance`
9. `product-management`
10. `requirements-traceability`

Compared with today's six topics, this keeps `agent-skills`, `github-projects` and `spec-driven-development`, replaces the broad `architecture`, `enterprise` and `planning` with terms people search for, and adds `product-management` so the product managers and designers the README speaks to can find it.

**Skills badge:** the Agent Skills badge under the README title reads `2 skills`: two skills you install, one skill is generated for your engineers. The badge address is `https://img.shields.io/badge/Agent%20Skills-2%20skills-teal`.

**Social preview image:** upload [`docs/images/social-preview.png`](images/social-preview.png) in Settings, General, Social preview. It is the README hero at 4800 by 2400 pixels, the 2 to 1 ratio GitHub asks for, and about 420 KB, under the 1 MB limit. The README itself shows the same hero at 3 to 1, [`docs/images/hero.png`](images/hero.png), so the install line sits higher on the page. Both carry the name, the tagline, the canonical phrase and the install line, so a shared link reads on its own.

**How to apply.** The description, homepage and topics can be set in one command by someone with admin rights. The social preview has no command and is uploaded in the settings page.

```bash
gh repo edit sct-will/carrydown \
  --description "An AI agent plans the project around real people, then carries the architecture to every issue and every engineer's coding agent." \
  --homepage "[ARTICLE URL]" \
  --remove-topic architecture,enterprise,planning \
  --add-topic agent-skills,coding-agents,ai-agents,spec-driven-development,project-planning,github-projects,software-architecture,ai-governance,product-management,requirements-traceability
```

## sct-will/carrydown-sample

**Description:** `What carrydown made from one fictional architecture document: a dated plan, specifications, issues and a public board.`

**Homepage:** `https://github.com/users/sct-will/projects/2`, the public board, so the first link on the repository page is the result.

### Proposed first screen of its README

The text below replaces everything above the "Renderings" section of the sample README. The renderings, the live links, the dry run and the plan report stay below it as they are. It uses the same look, try and install order as the main README, and no terminal commands, which live only in the main repository's CONTRIBUTING.md.

```markdown
# Expense approvals, a carrydown sample

This is what [carrydown](https://github.com/sct-will/carrydown) made from one document. The ground truth is a short architecture document for a fictional expense approvals service, with its requirements, two governance rules, a development standard and a business analyst note, and the company, the people and the dates are invented. Everything else here is real output of the skills: the plan, one specification per work item, the engineers' skill, and on GitHub the issues and a public project board.

Start with one work item. WI-03, the approval routing engine, is a GitHub issue whose AI engineering notes link to its specification, and that specification cites sections 3.4, 3.5 and 7.1 of the document. That chain, from issue to specification to paragraph, is what an engineer's coding agent reads before it changes code.

[![Work item WI-03 as a GitHub issue, beside the specification file its AI engineering notes link to, which cites ground truth sections 3.4, 3.5 and 7.1.](docs/images/issue-9.png)](https://github.com/sct-will/carrydown-sample/issues/9)

**Look.** Open the [public board](https://github.com/users/sct-will/projects/2), click WI-03, then follow its specification link to the sections it cites. No account and no install.

**Try.** [Open carrydown in a Codespace](https://codespaces.new/sct-will/carrydown), a ready-made computer in your browser. As it starts it runs the checker on a copy of this sample and prints the schedule, the load table and the critical path, then a dry run of the issues it would create.

**Install.** Run `npx skills add sct-will/carrydown` in a project folder, put `ground-truth/architecture.md` from this repository in `docs/source/`, and tell your agent "Set up a project plan from this document." Compare your plan with this one. Nothing is written to GitHub until you say yes.
```
