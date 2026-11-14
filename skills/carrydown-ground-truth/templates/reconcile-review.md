# Update review

The agent fills this page once per update and shows the owner everything above "Technical record". The owner reads and decides from the parts marked "Owner reads". The technical record is kept separately for maintainers and for the audit trail. Do not paste it into the owner conversation. Remove these instructions when writing the review.

## Lead sentence

Owner reads. One sentence with the counts, written in plain words. Name a count only when it is above zero. Use this shape and change the numbers and nouns to match.

> Two specifications need updates. One completed item needs a follow-up decision. One engineer correction conflicts with the revised source.

If nothing needs an update, say so and give the reason in one sentence. Do not write "up to date" while a publication step is pending.

## Proposed updates

Owner reads. One row per work item or file that would change. Show the smallest change that does the job. Do not rewrite a whole specification.

| Item | What changes | Why | Source block |
| --- | --- | --- | --- |

## Reviewed and unchanged

Owner reads. One row per item the agent looked at and left alone, so the owner can see that "no patch" was a decision with a reason.

| Item | Reason it stays as it is |
| --- | --- |

Also show, in one row, the source passages the comparison recorded as no downstream impact because only their formatting changed (white space, emphasis or heading level), for example "Formatting only: 2 passages of the architecture document. No words, numbers or conditions changed." The owner can ask to see them. If one of them did change a word, a number or a condition, treat it as a real change instead.

## Decisions needed

Owner reads. Group the rows. Each row names the decision that makes the question necessary and the choices the owner has. Resolve conflicts here before asking for the final approval.

| Kind | Item | What needs deciding | Choices |
| --- | --- | --- | --- |

Kinds: conflict (an engineer correction against the revised source), completed work (finished work the change may affect), deferral (a change the owner chooses not to apply now), added work (new scope that needs an explicit planning decision), request (an engineer clarification request the owner accepts, declines or defers), unresolved (a missing decision or evidence).

## Disclosure effects

Owner reads. Say whether the update changes what is shared, with whom or where. If nothing changes, say that nothing new is disclosed. A decision on one permission is not a decision on another.

## Next action

Owner reads. One plain sentence that names the next step and who takes it. Normally: approve the update, then say "Put the plan on GitHub." Say what is still pending.

## Technical record

Record only. Kept separately from the owner conversation, in the private workspace. Never put source text, staffing details or restricted headings in a public report.

| Field | Value |
| --- | --- |
| Proposal | The proposal reference the prepare command printed. |
| Source digests | Reviewed checkpoint and current renderings, by source identifier. |
| Draft digests | Working drafts at preparation time. |
| Changed blocks | Count by disposition: update, add, completed work, no impact, defer, unresolved. |
| Index measure | Bytes, words and approximate tokens (approximate) of the compact index and of the material read. Batches used. |
| Observation limits | Sources not observed, unreadable content, missing checkpoint. |
| Check result | The result of the check command and the time it ran. |
