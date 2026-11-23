# Recording storyboard

A plan for a silent screen recording, sixty seconds long, that shows the sample going from an architecture document to a filled GitHub board. It is to be made later, for the README, the article and the launch posts. Nothing here has been recorded yet.

## What the recording must be

- **Silent, with captions burned in.** Each caption stays on screen for at least two seconds per five words, in large type with strong contrast against its background. A text transcript, the captions below in order, sits next to the recording wherever it is posted, so a screen reader user gets the same story.
- **Real.** Record the fictional sample with the real skills, against a throwaway repository. The script output on screen is what the scripts print. Where waiting is cut, a small "sped up" mark shows in a corner, because the GitHub writes take about three and a half minutes in a real run.
- **Safe.** The token step is never on screen. Record with a fresh project folder, close every other tab and notification, and show no personal account names beyond the throwaway repository. Show only the fictional sample: its company, its two people and its numbers are invented. No real document, name, path or staffing record appears, and the workspace folder on screen is a throwaway one.
- **Honest about what is private.** The plan owner's tables, such as the load table, are shown as the plan owner's private view, and the recording says so in its caption. What reaches the repository is shown separately: the approved files and the receipt. The recording does not show the plan holding names, because the committed plan holds ids and tracks only.
- **Small and calm.** Under 5 MB as an MP4, 1280 by 720, with a still first frame that works as a poster image. No flashing, no fast zooms; cuts and gentle scrolls only.
- **Agent neutral.** Use a plain terminal or editor theme and crop away product branding, since the skills work in any agent that reads the Agent Skills format.

## Order of the story

The question about who may see the documents comes before the agent renders anything or asks about people. The recording follows that order. The sample's answer is yes, because its fictional documents are approved for everyone who can read the repository. The private path is a different recording, because it needs an organization's setup.

## Shots

| # | Time | On screen | Caption |
| --- | --- | --- | --- |
| 1 | 0 to 6 s | The sample's architecture document open in the editor, scrolling slowly past numbered sections to section 3.5. | Carry your architecture document into a plan, specifications and a GitHub board. |
| 2 | 6 to 12 s | The agent chat. The plan owner types "Set up a project plan from this document." The reply starts with `carrydown: interview, step 0 of 6` and asks "Can everyone who can read this repository see all of these documents and your staffing notes?" The plan owner types yes, and the agent prints its two summary lines, the sources and where drafting happens. | Before anything is copied, the agent asks who may see the documents. |
| 3 | 12 to 18 s | A quick run of interview answers: two people, one of them at 60 percent, a target of 2027-04-23. The agent says it saved them to a private file on the plan owner's machine, and shows that path. Then the agent's summary and the plan owner's yes. | Your people and their time go to a private file on your machine. |
| 4 | 18 to 23 s | The plan owner types "Show me the load table and the critical path." The load table appears; a soft highlight rests on the row for the person at 60 percent, then on "No person is over 100 percent of allocated capacity in any work unit." | The plan fits your people. The load table stays on your machine. |
| 5 | 23 to 28 s | The critical path block, `WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11`, and the line saying it meets the target with 2 days to spare. | The critical path shows what would slip, before it does. |
| 6 | 28 to 37 s | The plan owner types "Release the plan." The four-question preview scrolls by: what will be shared, with whom, where, and what remains private. The plan owner answers the disclosure line. The export prints the approved files and one receipt. | You see what will be shared, with whom and where, then approve exact files. |
| 7 | 37 to 43 s | The plan owner types "Put the plan on GitHub." The visibility line for the repository prints, then the dry run scrolls by and stops on `1 Epic, 5 sub-epics, 9 work item issues`. | A dry run first. Nothing reaches GitHub until you say yes. |
| 8 | 43 to 51 s | "Go ahead." The "sped up" mark shows. Cut to the browser: the project board, grouped by work unit, with tracks and dates filled in. The mouse pointer opens WI-03 and its AI engineering notes come into view. | Issues and a board, with tracks and dates already filled in. |
| 9 | 51 to 60 s | The specification link opens the WI-03 file; the "Ground truth" row is highlighted, then the approved context file `docs/context/wi-03.md` opens beside it. Final card: the tagline, `npx skills add sct-will/carrydown` and `github.com/sct-will/carrydown`. | An AI agent plans the project around real people, then carries the architecture to every issue and every engineer's coding agent. |

## Transcript

To post beside the recording, in this order:

1. Carry your architecture document into a plan, specifications and a GitHub board.
2. Before anything is copied, the agent asks who may see the documents.
3. Your people and their time go to a private file on your machine.
4. The plan fits your people. The load table stays on your machine.
5. The critical path shows what would slip, before it does.
6. You see what will be shared, with whom and where, then approve exact files.
7. A dry run first. Nothing reaches GitHub until you say yes.
8. Issues and a board, with tracks and dates already filled in.
9. An AI agent plans the project around real people, then carries the architecture to every issue and every engineer's coding agent. Install with `npx skills add sct-will/carrydown`.

The sample is fictional: the company, the people and the dates are invented, and the plan, issues and board are what the skills produced.

## Images and captions already in the repository

The pictures below show the fictional sample. None shows a path, a staffing record or a real account name. The README diagram was redrawn and the issue screenshot retaken after the confidentiality controls. The other pictures were made before them and are kept until they are redrawn or retaken.

| Image | Where it appears | Status |
| --- | --- | --- |
| `docs/images/handoff.png` and `handoff.svg` | The README "How it works" section | Current. Redrawn on 2026-11-22. It shows four stages: your documents and team constraints, the agent's draft, your review and approval, and each coding agent's approved handoff. The approved source excerpts pass through your approval, and a return arrow shows the reviewed update path. It shows no path or staffing record. |
| `docs/images/second-pass-review.png` and `.svg` | `docs/method.md` | Current. It shows the review of the plan and does not mention where sources live. |
| `docs/images/issue-9.png` | The README sample section | Current. Retaken on 2026-11-23 from the live issue after the sample repository was published again from the current release. The author's avatar and login are replaced by a generic avatar and an invented plan owner login in the rendered page before the capture; the issue content is unchanged, and the README caption says so. It shows no path or staffing record. |
| `docs/images/board.png` | Nowhere since November 2026, when the README sample section was shortened to one picture; kept for the recording | Current. It shows tracks, dates and checkpoints, and no name or login. |
| `docs/images/social-preview.png` | The repository social preview | Current. It carries the tagline only. |
