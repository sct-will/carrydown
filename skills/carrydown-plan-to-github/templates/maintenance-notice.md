<!--
This file is the single source for the owner and engineer action phrases, the two completion lines and the
maintenance notice. Other files carry word-for-word copies of the blocks below: both SKILL.md files, the
specification README template (templates/spec-README.md, the notice only) and the owner guide. Change the
text here first, then update the copies. tests/test_documentation.py compares them. Remove this comment
when you quote a block.
-->

# Maintenance notice and action phrases

## Owner actions

| What you want to do | What to say |
| --- | --- |
| Create a plan | "Set up a project plan from these documents." |
| Publish the approved plan | "Put the plan on GitHub." |
| Update an existing project | "This changed: [describe the change or provide revised documents]." |

## Engineer actions

| What you want to do | What to say |
| --- | --- |
| Start a work item | "Work on WI-03." |
| Raise a specification problem | "This specification seems wrong because [explanation]." |

## Exact skill name fallback

> "Use carrydown-ground-truth to update this existing project."

## Completion line after planning

> **Your plan is ready for review.**
>
> Review it with your agent. When you approve it, say "Put the plan on GitHub."

## Completion line after publication

> **Your approved project has been published.**
>
> Engineers can start with "Work on [work item ID]."

## The notice

Show this before routine counts and links, at the end of planning and at the end of publication. Keep it in the owner guide and in the generated specification README.

> **Important: when the project changes**
>
> If requirements, architecture or company rules change significantly, or an engineer finds a specification problem, say:
>
> **"This changed: [describe the change or provide revised documents]."**
>
> Your agent will review the existing project, preserve engineer corrections and show proposed updates for approval.
