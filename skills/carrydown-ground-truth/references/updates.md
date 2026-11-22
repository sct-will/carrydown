# Updating an existing project

Read this when the project already has a plan and something changed: a source document, a requirement, a company rule, or an engineer's finding that a specification is wrong. `SKILL.md` has the steps. This page has the detail.

The commands below are for you. The owner never types them and never sees a proposal id, a digest or a flag. Say what you are doing in one plain sentence, then run the command. The script never calls a model. You read the comparison and the compact index it prints, and you write the proposed patches.

## The comparison and the three versions

Every update compares three versions of the downstream content.

| Version | Where it comes from |
| --- | --- |
| Previous approved | The released plan and specifications, from the active release. |
| Current | The owner's working drafts, with any engineer corrections already in them. |
| Proposed | What the revised source or the accepted clarification calls for. |

On the source side, the script compares the previously reviewed rendering of each source with the current rendering, by source identifier, section and changed block. A rendering of a new version does not make it the reviewed baseline. Only an accepted review does.

| Situation | What you do |
| --- | --- |
| Current content equals previous approved content | Prepare a focused patch. |
| An engineer edit and the source change are compatible | Keep both. Explain the result in one sentence. |
| They conflict | Show both texts and the source passage. Ask the owner. Do not overwrite either. |
| An engineer correction shows a defect in the source | Draft a correction request for the source owner, as a note in the review's "Decisions needed" table (see "Engineer conflicts and source corrections"). The specification keeps the correction. |
| Historical content is incomplete | Say what is missing and require review. |

Never rewrite a whole specification because regeneration is easier. A patch touches only the lines that must change.

## Missing checkpoint

When `status` or `prepare` reports that no reviewed checkpoint exists, say this, word for word:

> A previous complete source checkpoint is unavailable. Review the current sources to establish one. Earlier uncited changes cannot be assessed automatically.

Then offer to review the current sources with the owner so that the review becomes the checkpoint. Do not pretend a comparison ran. Do not guess what the earlier text said.

### The first checkpoint

A project with no reviewed checkpoint gets one this way, after the owner has reviewed the current renderings with you and accepted them:

1. `reconcile.py prepare --root . --apply`. With no checkpoint it finds no changed block, treats every section as history it cannot assess, and saves a proposal that holds only `descriptor.json`. That proposal has nothing to apply and never shows as an unfinished update.
2. `workspace.py checkpoint prepare --root . --descriptor <workspace>/drafts/proposals/CHANGE_ID/descriptor.json --rendering-dir <renderings folder>`, read the preview, then the same command with `--apply`. The renderings folder is `docs/ground-truth` on the yes answer and `<workspace>/renderings` on the no answer. It prints the checkpoint id.
3. `workspace.py checkpoint commit --root . --id CHECKPOINT_ID`, read the preview, then with `--apply`. It commits through an isolated index with the owner's git identity, reads the commit back and only then records it in `workspace.yaml`.
4. If a release is active, bind the checkpoint to it (see "After the owner accepts", step 3). The next `status` compares against this checkpoint.

## Rendering a revised document

`status` compares only the renderings that the project and its private workspace hold. A revised document that the owner names, kept anywhere else, is invisible to it until it is rendered. So run `status` first, as always. "Observable inputs unchanged" right after the owner named a revised document means the document is not rendered yet, not that nothing changed. Render it, then run `status` again.

The version you give `--version`:

1. The document's own version line, when it changed.
2. Otherwise the previous rendering's version with its minor number incremented: 0.3 becomes 0.4, 1 becomes 1.1.
3. Never ask the owner. The number does not change the comparison.

The renderer matches a file to its source by the file name, and names the rendering after it. A revised file whose name is not the source id, such as `architecture-v0.4.docx` for the source `architecture`, takes both `--source-id architecture` and `--name architecture`. With `--source-id` alone it writes a second rendering beside the first. Check that the dry run says `would write docs/ground-truth/architecture.md` (or the rendering's usual name in the workspace).

Run the renderer with `--dry-run` first. For each rendering it would replace it prints:

| Line | What it means |
| --- | --- |
| `previous rendering of <name>: version <v>` | The version of the rendering it replaces. Start from it. |
| `note: <name> changed but keeps version <v>. ...` | Your `--version` repeats the previous one although the content changed. Use the number the note gives, unless the document's own version line says otherwise. |
| `preserved the previous rendering of <name> privately in workspace:renderings/history/` | The previous rendering was copied to the private history before it was replaced. |
| `previous rendering of <name> already recorded in the reviewed checkpoint <id>` | A reviewed checkpoint already holds the previous rendering, so nothing needed copying. |
| `warning: there is no private workspace, so the previous rendering of <name> was not preserved. ...` | Tell the owner. The checkpoint cannot be compared with it later. |

## What counts as changed

The script classifies additions, modifications, removals, moves, renumbering, precedence changes and unreadable content. A section that moved and is word for word the same is a mapping, not a change. An ambiguous mapping goes to the owner.

A formatting change is not an engineering change. A change to a number, a unit, a condition, an exception, a negation or a prohibition is potentially meaningful even when it is one word. Read it before you call it editorial.

## One disposition for every changed block

Every changed block gets exactly one disposition. "No proposed patch" is not "no impact".

| Disposition | Required record |
| --- | --- |
| Update existing work | The affected item and the proposed patch. |
| Add work | The proposed scope and an explicit planning decision by the owner. |
| Assess completed work | The evidence and a follow-up decision by the owner. |
| No downstream impact | The reason and the context that supports it. |
| Defer | The consequence the owner accepts, the affected work and the remaining action. |
| Unresolved | The specific missing decision or evidence. |

A removed requirement does not delete issues and does not rewrite completion history. The owner decides any follow-up work or status change. A deferred change stays visible in the review and in the next status report. It never disappears.

## The proposal files

`prepare --apply` saves the proposal in `<workspace>/drafts/proposals/CHANGE_ID/`. `CHANGE_ID` is the id on the last line of its output, `proposal: <id>`. The folder holds `inputs.json` (the digest of every input), `blocks.json` (the changed blocks), `consumers.json`, `index.json` (owner only, never shared), `proposal.json`, `descriptor.json` (for the checkpoint) and `dispositions.json`. Edit only `dispositions.json`. Every other file is the record of what was compared.

`dispositions.json` is `{"format": 1, "dispositions": [...]}` with one record per changed block. `prepare` writes a `{"block": "<ref>", "disposition": "pending"}` placeholder for each block, and a finished `no-impact` record, marked `"automatic": true`, for a block whose change is formatting only. Show those under "Reviewed and unchanged" in the review, so the owner sees them. Replace every placeholder with one record. `check` reports any `pending` that is left. The fields of each disposition:

| `disposition` | Fields it needs |
| --- | --- |
| `update` | `item` and `patch` |
| `add` | `scope` and `decision` |
| `assess-completed` | `evidence` and `follow_up` |
| `no-impact` | `reason` and `context` |
| `defer` | `consequence`, `affected` and `remaining` |
| `unresolved` | `missing` |

A `patch` is one record or a list of records, each exactly `{"item", "path", "before_sha256", "after_text"}`. `path` is relative to the drafting folder (the project on the yes answer, `<workspace>/drafts` on the no answer), or starts with `project/` or `workspace/`. `before_sha256` is the SHA-256 of the file as it is now, and `after_text` is the whole new file, written from that exact text. One file takes one patch, so combine changes to the same file.

Do not compute the digest or write the record by hand. Write the whole new text of the file to a temporary file outside the project, then let the patch command fill in the record:

```bash
python3 <skill>/scripts/reconcile.py patch --root . --proposal CHANGE_ID --block BLOCK --item WI-03 --path PATH --from NEW_TEXT_FILE
```

It is a dry run until you add `--apply`. It reads the digest of `PATH` as it is now, turns a `pending` block into an `update`, adds the item to the disposition's `item` and replaces the earlier patch of the same file. It refuses a path that cannot be patched, a block that is not in the proposal, a block with another disposition and a file that already has a patch under another block. It writes only `dispositions.json`. The working drafts change only at `apply`.

**One file changed by several blocks.** File its one patch under the block that causes the largest change, and name the other blocks with `--also-block BLOCK`. The command writes them into that disposition's `context`. Each other block still needs its own disposition: `update` with its own patches when it changes other files. When its whole effect sits in a patch filed under another block, give it `no-impact` with the reason "its change is in the patch for PATH filed under BLOCK", so the review shows it as covered and not as unaffected.

**Items you read and left unchanged.** Dispositions are per block. The reason each candidate item stays as it is goes in the review's "Reviewed and unchanged" table, one row per item, not in `dispositions.json`. Only the working plan and the specification Markdown files can be patched. Generated and approved files, the released plan, workspace history and links are refused.

**Items that do not cite the changed section.** The release compiler builds an item's approved context only from the sections the item cites. So `check` reports `citation-missing` for a specification patch filed under a changed block when the item does not cite that block's section after the proposal. A citation of a parent section, or of the whole document, counts. A removed section is skipped, and the blocks named with `--also-block` are checked too. To clear it, add the section to the item's `sections` in the working plan, or add a References line to its specification, in the same proposal. Keep its Ground truth row in step, for the reader. `apply` stops on the finding and writes nothing.

A patch that rewrites or removes a decision entry an engineer recorded is a `decision-conflict` finding. After the owner decides the conflict, record the decision in plain words as `conflict_resolution` on that disposition, and `check` accepts it. A patch that keeps every recorded entry and changes other text needs no `conflict_resolution`. After a release, the release gate lets such a patch replace a specification that holds an engineer's entry only because the proposal recorded that exact file. If the file changes again before `apply`, prepare again.

## Reading the impact index

The prepare command prints a compact index with one row per work item: identifier, title, scope excerpt, acceptance excerpts, source citations, shared contracts, dependencies, recorded decisions and completion state when known. Global conventions appear once.

1. Read the changed material first, with the surrounding source rules it depends on.
2. Read the whole index once. Do not skip rows. Direct consumers come from citations. Indirect consumers come from shared obligations, contracts, integration points and conventions.
3. Name candidate items and say why each is a candidate, including indirect ones. Tell the owner how many candidates there are before you read further.
4. Read the full specification of every candidate, and the contracts it uses. Read only those in full. Do not read every specification of the project.
5. Expand further only when the evidence is incomplete. An excerpt is not enough to say "no impact" when the omitted words could matter. The index records omitted word counts. Open the full item in that case, and add it to the candidates you name.
6. Propose a patch only where content must change. A direct citation can still need no patch.
7. Apply this to architecture and requirements changes as well as governance and standards. A source category ranks where to look first. It never excludes anything.

A scheduling dependency alone does not mean the consumer's specification changes. Distinguish the relationship types.

Completion state is `unknown` for every row, because this skill reads nothing from GitHub. That is expected, not a fault. An engineer's dated entry under "Decisions recorded" is evidence that the item may be finished. When a changed block touches such an item, "assess completed work" becomes a row of the review's "Decisions needed" table with that evidence, and the owner decides the follow-up.

New obligations are assessed even when nothing cites them. Check new uncited obligations, resolved conflicts, changes of applicability or precedence, and completed work.

### Cost

Before you assess, tell the owner what you will read, in one line: the index size in bytes and words, and an approximate token count, labeled approximate. Use the real usage figure afterward when the environment supplies one. Do not promise a count for every project.

If the index is large, process it in bounded batches and account for every row. If the owner has set a budget and the work does not fit, report the assessment as incomplete, name the rows not read and ask whether to continue. Never turn a budget into a clean result, and never say a project has no impact for rows you did not read.

## Independent review prompt

After you draft the patches and the dispositions, run a separate reasoning pass. In an environment that can start a fresh agent, use one. Otherwise run the pass as a distinct step in this conversation: set your draft summary aside and reread the original material first. The reviewer must see the original changed blocks, the candidate list, every "no impact" reason, every proposed patch and every preserved engineer decision. A summary of your reasoning is not enough.

> You are a skeptical reviewer of a proposed project update. You have the original changed source blocks, the compact index, the list of candidate work items, the reasons given for items left unchanged, the proposed patches and the engineer decisions that were kept. Try to show the update is wrong.
>
> 1. Missed consumers. Name any work item, contract or convention that depends on a changed block and is not in the candidate list. Quote the changed words and the item's words.
> 2. Altered exceptions. For each changed number, condition, exception, negation or prohibition, say whether any patch or any "no impact" reason ignores it.
> 3. Global applicability. Does a changed rule, precedence or applicability reach items that never cited it?
> 4. Completed work. Does any change invalidate work already recorded as complete or in progress?
> 5. Preserved decisions. Does any patch overwrite an engineer correction or a recorded decision? Is any claimed compatibility actually a conflict?
> 6. Unsupported patches. Does any patch say more than the source supports?
>
> For each finding give the item, the quoted evidence, why it matters and a proposed fix. Do not praise the update. Do not rewrite it. If you find nothing in a category, say what you checked.

Fold each accepted finding into the proposal and run the check again. Findings are input for the owner's review. People decide substantive interpretation. This pass does not need another provider, a hosted service or automatic delegation.

The pass may run as a separate agent. Give it read access only. Its reads are its own and are not part of the owner's command record of this update. Say in the review that the pass ran as a separate agent.

## The consolidated review

Use `templates/reconcile-review.md`. Lead with the counts sentence, in plain words and only for counts above zero. For example: "Two specifications need updates. One completed item needs a follow-up decision. One engineer correction conflicts with the revised source." Then show the proposed patches, the evidence for unchanged work, the decisions needed, the disclosure effects and the next action. Keep the technical record out of the conversation. Offer it if the owner asks.

Settle real conflicts before you ask for the final approval. Combine compatible questions into one prompt where policy allows. Do not merge distinct permissions. An answer to one permission is not an answer to another. Accepting the update is not permission to disclose anything or to write to GitHub.

## Engineer conflicts and source corrections

An engineer's correction stays in the working draft until the owner decides. When it conflicts with the revised source, the owner chooses one of three things: keep the correction and ask the source owner to fix the source, take the revised source and discard the correction, or write a new passage. Record the choice in the review.

A source correction needs the source owner's decision. The concrete artifact is a drafted note in the review's "Decisions needed" table, kind `request`, addressed to the source owner: what the source says, what is ambiguous or wrong, and the question to settle. Add the sentence "Nothing has been sent." The owner decides whether to send it. That note is enough. Say "I drafted a request. The source document is unchanged." Never say the document was corrected when only a request was drafted.

## Engineer clarification requests

Engineers raise problems with their own agent. Each request is addressed to the plan owner on the work item's issue, and it has a state: `pending`, `accepted`, `declined` or `deferred`.

1. When `status` reports outstanding requests, show them first, before anything else, one line each: the work item, the problem in a sentence, and how long it has waited. If the owner's authorized reads did not run, say that outstanding requests could not be observed and why.
2. The owner decides each one: accepted, declined or deferred. Do not decide for the owner.
3. An accepted request enters the update as a changed input. Run the update path from the impact step with the request as the source of the change. A declined or deferred request stays in the review with the owner's reason.
4. This skill does not write to GitHub. The publishing skill records the decision on the issue, as a comment that starts with `Clarification disposition:` and links the request. The planning skill reads what was last observed from `<workspace>/events/clarifications.json`, through `reconcile.py status`, and reports the time of that observation. Say what the observation shows and when it was taken. A request that shows `pending` may have been decided after that time.
5. Tell the owner that the decision is recorded on the issue by the publishing skill, with its disposition command, after the owner says yes. Until the observation shows the new state, say "not yet recorded on the work item". If there is no observation, say that requests could not be observed, and ask the owner to say "Put the plan on GitHub." or to run the publishing skill's `--clarifications --apply` read first.

A mention or an assignment draws attention. It does not prove the owner was notified. Delivery, the owner's decision and the finished update are three separate states.

## When inputs change during review

If a source or a working draft changes after you prepared the proposal, the proposal is stale. Say this, in plain words: "Something changed while we were reviewing: [which source or draft]. Nothing was applied. I will reassess only the items it affects and show you what differs." Then run `prepare --root . --apply` again, reassess the affected items and show the owner only what changed since the last review. A decision the owner already made on an unaffected item stands.

If `check` or `apply` reports that an input changed, treat it the same way. Never apply a patch to content that is not what you reviewed.

## Observation limits

Say what was observed. A repository that did not change says nothing about a source kept elsewhere. When the owner asks "Is this project up to date?", answer with what `status` checked and what it could not see, and ask for revised material for anything kept elsewhere. Do not say "up to date" while a publication step is pending.

## After the owner accepts

1. Run the apply command as a preview, read it and show the owner which files will change. Then run it with `--apply`. A proposal with no patch is recorded as applied too. If you run the checker afterward, a staffing finding (such as `people.yaml has no entry for person ...`) belongs to the owner's people file in the private workspace. The update does not fix it: name it to the owner in one line and leave `people.yaml` alone.
2. Record the accepted source checkpoint from the same proposal, each command as a preview first and then with `--apply`:

   ```bash
   python3 <skill>/scripts/workspace.py checkpoint prepare --root . --descriptor <workspace>/drafts/proposals/CHANGE_ID/descriptor.json --rendering-dir <renderings folder>
   python3 <skill>/scripts/workspace.py checkpoint commit --root . --id CHECKPOINT_ID
   ```

3. If review found no downstream change, the accepted checkpoint is recorded against the active release without a new release. `reconcile.py status --root . --json` gives the ids under `active_release`. Preview, then add `--apply`:

   ```bash
   python3 <skill>/scripts/workspace.py checkpoint bind --root . --id CHECKPOINT_ID --release-id RELEASE_ID --request-id REQUEST_ID
   ```

   The earlier association stays in the checkpoint's history. This is local bookkeeping, not an approval.
4. If outputs changed, the owner says "Put the plan on GitHub." and `carrydown-plan-to-github` releases and publishes.

## The states to report

At the end, report these states separately, in this order, each with one of its values. Use text labels.

| State | Values |
| --- | --- |
| Draft reconciliation | accepted, or not yet accepted |
| Release | approved, or not yet approved |
| Engineering repository update | pending, or available |
| Issue updates | pending, or verified |
| Board updates | pending, or verified |
| Engineer action | required, with the work items, or none |

A state that is not reached yet is pending, not omitted. Engineers can still hold old material in a checkout or an open conversation. Do not claim that every engineer has received or understood the update. Name the work items whose engineers need to act, and say what they must do: update their checkout, reread the approved changes and reassess their plan.

At a milestone review, the owner can ask the team: "Have any source decisions, requirements, constraints or implementation findings changed since the last review?" This is a human observation point. It does not approve anything and it does not show that every source was checked.

## Recovery

If the owner comes back later, or an update stopped halfway, they say "Resume the project update." Run `status`, pick the saved proposal or the existing publication request, and say where things stand in plain words. Ask the owner only when more than one consequential choice remains. A failure never authorizes a reset, a forced approval, a blind retry or removal of anyone's work.
