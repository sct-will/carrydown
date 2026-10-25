# Review and repair a published plan

Load this reference only when the user asks to review or repair an existing published plan, or accepts the offer to review an older plan. It is separate from normal first publication and the engineers' skill-only shortcut.

## Review before repair

1. Locate the current canonical plan, specifications, confirmed constraints and actual GitHub artifacts. Keep a copy of the pre-repair `plan.yaml` inside the project's documentation folder, for example `docs/spec/review-baseline/plan.yaml`. Preserve it until publication is verified. Do not reconstruct it from the repaired plan later.
2. Load `../templates/plan-review-prompt.md` when starting the second pass. Load `../templates/plan-review-report.md` only when writing its tables. Follow the review, owner decision and accepted-repair sequence there. Source files and confirmed constraints remain authoritative; GitHub is a downstream view.
3. For local repairs, use the installed ground-truth skill's scaffold and writing references. This skill does not ship the scaffold. Review generated changes and narrative content, then run the ordinary checker and its separate report. The checker must pass before publication.
4. Inspect existing GitHub bodies and comments for human edits. Compare the affected issue fields, parent links and board values with the repaired plan. Record each proposed external update in the repair table, including its current value, intended value and risk. Retired work and changed project identity need an explicit owner decision; do not delete or reuse identifiers.

## Publish the accepted repairs

The owner reviews the local changes first. Follow the ordinary publication preconditions for committing and pushing canonical files, token handling and public repositories. A review finding is not authorization to write to GitHub. Show each stage's dry run and obtain approval for its apply run. Approval already given for a named local change set does not need to be requested again for each local edit.

### Existing issue metadata

The separate repair command handles generated titles, the assigned engineer, track labels and native parent links. It requires the pre-repair plan so it can preserve unrelated assignments and labels and detect titles a person changed. It does not write bodies, comments, issue state or board fields. It creates and deletes nothing.

```bash
python3 <skill>/scripts/github_repair.py --root . --before docs/spec/review-baseline/plan.yaml
```

Read the preview. Resolve any blocked title, missing marker, outside parent or retired item before applying. For a moved item, repair its parent before running the normal issue synchronization; a normal creation run is not a reparenting command. If the destination milestone or a track label does not exist, preview its creation with an available authorized GitHub tool and obtain approval first. Then preview the metadata repair again. Do not run a full creation sync while an existing item still belongs to a different parent. If that staged creation cannot be performed with the available tools, record the precise update as publication pending. Keep the saved plan for retries.

After approval, run the same repair command with `--apply`, then run it separately with `--verify`. For a public repository, explain that the destination is public, obtain explicit publication approval and include `--allow-public` on the apply run. If a run stops after some writes, read back the results and preview again; the command finds the same issue numbers on rerun.

### Bodies, dependencies and epic roll-ups

Preview `github_sync.py` from the normal flow. Dependencies are specification and issue-body links; the script does not manage native blocked-by relationships. For each changed item or milestone, compare the proposed body with the actual body and preserve human edits, checkmarks and evidence.

`--update-bodies` can replace all generated issue bodies in that run. Use it only after the owner has reviewed that full replacement set and confirmed that no human changes will be lost. When bodies contain human edits, prepare a merged body for each affected issue, show its diff, and use an available authorized GitHub tool to update that issue after approval. If no suitable tool is available, give the owner the exact merge and record publication pending; do not silently overwrite the body or report the repair as verified.

After the bodies are reconciled, preview the ordinary sync without `--update-bodies` to refresh the owned epic roll-up and missing links. Apply after approval, then run its `--verify`. Comments and issue state remain intact. Do not recreate an issue to change its body or parent.

### Board and engineers' skill

Preview `github_project.py` against the existing board, with its original owner and `--project-number` when known. Show current and intended values from the review alongside the configuration preview. The existing apply path updates differing managed dates, tracks and work units. If iteration dates changed, preview and explain `--reconfigure-iterations` before applying it. Missing Track options need a separate reviewed configuration change; do not claim that a warning created them. Apply only after approval, then run `--verify` and resolve every reported difference.

Load `engineers-skill-maintenance.md` only if the local repair affects generated references or conventions. Preview reference regeneration, apply the accepted changes and review any broader regeneration needed for new or retired items. Preserve hand edits and follow the existing commit and push permissions.

## Finish with evidence

Recheck each accepted finding, affected source reference and downstream artifact. Metadata verification, issue verification and board verification have different scopes; none alone proves the whole repair. Record their results in the review report. Keep unresolved or deferred items and accepted risks visible, and distinguish local verification from publication pending. Stop for the owner's next decision if verification reveals another substantive change.
