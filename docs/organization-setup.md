# Organization setup for private drafting

This page is for the organization administrator who sets up the private path once, and for a plan owner who answered no to the question about who may see the documents.

Read this page only when the answer to "Can everyone who can read this repository see all of these documents and your staffing notes?" is no. The "yes" path needs none of it. The private path adds three pieces that an organization administrator installs once, and a short enrollment for each project:

- **A tooling repository.** It holds the independent verifier and the enrollment file. Only release owners and administrators can write to it.
- **A staging repository for each project.** It holds release candidates while the plan owner approves them, before anything reaches the engineering repository.
- **A verifier App.** A GitHub App that reports two required checks. It has its own credential, which only the tooling repository holds.

The plan owner then runs two checks, the offline and the live doctor, and reads one short table. Engineers see one required check on their pull requests.

## What the administrator needs first

- Permission to create repositories and a GitHub App in the organization, and to manage rulesets and Actions settings on the engineering and staging repositories.
- A plan that supports the features below. Before you offer this path, prove on your plan that App-specific required checks, repository rulesets, the up-to-date branch requirement, pull requests opened by Actions and the App permissions work. GitHub.com and GitHub Enterprise Cloud can use this setup when verified. GitHub Enterprise Server is unverified until you test it on your server version.
- The numeric ids of the repositories and accounts. For a repository, `gh api repos/OWNER/NAME --jq .id`. For an account, `gh api users/LOGIN --jq .id`. Logins are hints. The numeric id is the authority.
- Time to read what you install. This page links no code that you should install unread.

## Step 1: create the tooling repository

1. Create a private repository, by default `carrydown-tooling`: `gh repo create OWNER/carrydown-tooling --private`.
2. Limit write access to the release owners and administrators. Protect the default branch with a ruleset that requires a pull request review, blocks force pushes and deletion, and allows no bypass. Changes to the verifier or to the enrollment then go through review.
3. Copy two folders, whole, from a clone of the carrydown repository into the tooling repository: `scripts/` and `verifier/`. They are the pinned verifier code. Do not copy from an installed skill. An installed skill carries only the scripts it runs, and the verifier also needs `release_engineering.py` and `release_scan.py`, which no skill carries. Copy `verifier/carrydown-release-verify.yml` to `.github/workflows/carrydown-release-verify.yml` in the tooling repository. Merge that commit first. It is the commit that the enrollment pins as the verifier code, and the enrollment goes in a later commit.
4. Read `.github/workflows/carrydown-release-verify.yml` before you merge it. It checks out the policy and the code into separate folders, proves the code checkout is exactly the pinned commit, and runs the verifier with `python3 -I`. Its actions are pinned by full commit SHA (Secure Hash Algorithm). Confirm each pinned commit against the action's release page.

## Step 2: create the verifier App

1. Create a GitHub App owned by the organization. Turn webhooks off. Grant only these repository permissions: Contents read, Pull requests read, Checks write and Metadata read.
2. Install it on the tooling repository and on each engineering and staging repository you enroll. Grant no other repository.
3. Write down the App's numeric id. It becomes `verifier_app_id` in the enrollment, and both required checks must come from this App.
4. Generate a private key. Store the App id and the key as two repository secrets of the tooling repository only, named `CARRYDOWN_APP_ID` and `CARRYDOWN_APP_PRIVATE_KEY`. Never use an organization secret, and never store them in an engineering or staging repository. With the GitHub command line, `gh secret set CARRYDOWN_APP_PRIVATE_KEY --repo OWNER/carrydown-tooling < key.pem` reads the key from the file, so it never appears on a command line. Delete the file afterward.

The verifier mints a short-lived installation token from these two secrets at the start of every run. It never prints the token.

## Step 3: create the staging repository and its rules

For each engineering repository:

1. Create a private repository for release candidates. The plan owner's `python3 scripts/workspace.py init --root . --answer no --apply` prints the exact commands. The staging repository receives snapshots and manifests only, never originals or staffing records.
2. Copy `templates/staging/open-release-request.yml` to `.github/workflows/open-release-request.yml` on its default branch. Another administrator reviews it, and nobody edits it afterward, because the enrollment pins its digest: `shasum -a 256 .github/workflows/open-release-request.yml`. The workflow runs from the default branch on a schedule and on manual dispatch. It lists the `request/*` and `state/*` branches as data and opens a pull request for each, with `contents: read` and `pull-requests: write` only. It never runs or imports a file from a candidate branch. The plan owner's `release.py approve --github` dispatches it when the owner's permissions allow, and otherwise the schedule picks the branch up. A delay is normal, and a wait that ends without a pull request leaves a pending candidate and no approval.
3. Under Settings, Actions, General, allow GitHub Actions to create pull requests. This is how the owner is not the author of the request.
4. Allow merge commits only. Squash and rebase would stop the verifier from comparing the reviewed head with the merged tree.
5. Create the rulesets. Print them with the App's id filled in, then import each JSON file under Settings, Rules, Rulesets:

   ```bash
   python3 verifier/verify_release.py ruleset --kind staging --app-id <app id> > staging-ruleset.json
   python3 verifier/verify_release.py ruleset --kind engineering --app-id <app id> > engineering-ruleset.json
   ```

   The staging ruleset requires one approving review, dismisses stale approvals when new commits arrive, restricts force pushes and deletion, allows no bypass, requires the `carrydown-staging-verifier` check from the App, and requires branches to be up to date before merging. It sets `require_last_push_approval` to false on purpose. The plan owner pushes the candidate and may be the only authorized human. Do not turn that setting on. The engineering ruleset requires `carrydown-release-verifier` from the same App, blocks force pushes and deletion, and allows no bypass.
6. Check who can read the staging repository. The permitted set is the plan owner, the approved disclosure reviewers, the necessary organization administrators and specifically approved services. Include organization base permissions, teams, outside collaborators, repository administrators, installed Apps and deploy keys. Private visibility alone is not evidence of that set.

## Step 4: enroll the project

1. Add an entry to `enrollment.yaml` in the tooling repository. [The enrollment reference](../verifier/enrollment.schema.md) lists every field with a worked example. Set `verifier_sha` to the commit from step 1 and `verifier_app_id` to the App id.
2. Fill in the two digests. `python3 verifier/verify_release.py digests --policy-file enrollment.yaml` prints the `enrollment_id` and `policy_sha256` each entry should carry, and says whether the file already holds them. Run it again after every edit. Any change to a permission changes the policy digest, and that forces reassessment of every earlier approval.
3. Merge the enrollment through a reviewed pull request. The merge commit is the policy commit. It must be later than the verifier commit.
4. In the engineering repository, add the pointer `.carrydown/release-policy.yaml`:

   ```yaml
   format: 1
   tooling_repository: OWNER/carrydown-tooling
   enrollment_id: <the enrollment_id of the entry>
   ```

   The pointer is only a pointer. The verifier resolves the project by the repository's numeric id and compares the pointer with the enrollment. Deleting the pointer or the handling block fails the check. It never turns an enrolled project into a legacy one.

## Step 5: attest what the plan owner cannot inspect

Some facts cannot be read with an ordinary token: the Apps installed on the staging repository, the readers of a project board, the engineering rulesets when the owner lacks administrative read access, the secret names of a repository, and the organization's agent environment. An administrator can vouch for each fact with a scoped attestation in the enrollment, [described in the reference](../verifier/enrollment.schema.md#attestations). Rules that always hold:

- The author must be one of the enrollment's administrators, by numeric id, and the attestation must sit in the protected history of `enrollment.yaml`. Record the tooling pull request review that approved it in `note`.
- The subject must match the exact component. A change to the reader set, the repository or the App makes the old attestation stop matching.
- It has an expiry. Choose a lifetime you will keep renewing. Carrydown supplies no attestation that never expires.
- It never replaces a live content hash, an approval identity, an event state, an expiry or the verifier's scan health.

An expired or missing attestation blocks the first upload to staging, not the later audit. Renew it before it lapses.

## Step 6: run the doctor

The doctor has two forms. Both print a short table of components with a status of verified, not verifiable or missing.

```bash
python3 scripts/workspace.py doctor --root .
python3 scripts/release.py doctor --root .
```

- **The offline doctor** (`workspace.py doctor`) checks the workspace permissions, that the workspace is outside the repository, the ignore rules and the local plan schema. It makes no network call. It lists every remote component as not verifiable, because the first skill holds no token code.
- **The live doctor** (`release.py doctor`) adds the remote components, read with the owner's token: the enrollment found by the repository's numeric id, the pinned verifier commit and the absence of a verifier credential in the engineering and staging repositories, the staging repository's identity, privacy and effective readers, the installed request workflow against its enrolled digest, both rulesets (including the App that owns each required check), the approver and administrator accounts, the destinations, the verifier's scan health and the runtime-isolation attestation. It ends with two lines that say whether a private upload to staging is allowed and whether export and publication are allowed. The same checks run again before every upload, export and publication.

On the private path every mandatory component must be verified before anything is uploaded or released. A not verifiable or missing component blocks the step that needs it and names the reason code. On the "yes" path the remote checks are informational.

From an installed skill, `workspace.py` is in the `scripts/` folder of `carrydown-ground-truth` and `release.py` is in the `scripts/` folder of `carrydown-plan-to-github`. The examples use the paths of a carrydown clone.

The owner's token needs read access only for the doctor: Metadata, Contents, Pull requests and Administration (read) on the engineering and staging repositories, and Actions (read) on the tooling repository. It reads rulesets, collaborators, deploy keys and the verifier's last completed run.

The doctor also reports the verifier's health. A scan counts as healthy when its last completed run covered every open pull request and is no older than `check_health_max_age_seconds` (900 seconds by default). When the verifier is stale, owner-side writes refuse and the doctor tells you to restore it or to run the workflow by hand. The health check is an operational safeguard. It cannot expire a check that GitHub already shows as successful.

## Step 7: the owner's release commands

This step is for the private path. A yes-path owner does not need it: the agent runs the release for you, and [the plan owner guide](plan-owner-guide.md#release-what-the-engineers-will-see) shows what it runs. On the private path too, the agent runs these commands and shows you each dry run, and you never type a request id. They are listed so you and your administrator can see what happens. Every command that writes is a dry run until `--apply`. Run these from the project root.

```bash
python3 scripts/release.py preview --root .
python3 scripts/release.py prepare --root .
python3 scripts/release.py prepare --root . --apply
```

`preview` answers four questions in order: what will be shared, with whom, where, and what remains private. It then lists the changes since the last release. `prepare --apply` writes only into the private workspace. It prints two ids. The release id names the exact content. The request id names one permission decision over that content. The same content can have several requests, and approving one never approves another.

Run the live doctor, then upload the candidate, review it in GitHub and export.

```bash
python3 scripts/release.py doctor --root .
python3 scripts/release.py approve --root . --github
python3 scripts/release.py approve --root . --github --apply
```

None of these commands needs a request id: `approve` takes the request `prepare` saved last, `export` and `withdraw` the active request, and `export-state` the request the most recent state change ended. Each prints the id it uses, and `--request <request id>` names another one. The dry run of `approve --github` checks the staging repository without pushing anything. The `--apply` run first repeats the live checks, then pushes the branch `request/<request id>` to the staging repository with your own git credentials. No token goes into a URL. It waits up to two minutes for the staging workflow to open the pull request. A timeout prints `candidate uploaded; approval request pending` and the retry command. That is neither an approval nor a reason to upload again. In GitHub, review the final revision of the pull request, approve it and merge it with a merge commit. Then export:

```bash
python3 scripts/release.py export --root .
python3 scripts/release.py export --root . --apply
```

`export --apply` verifies the approval through the GitHub API before it writes anything. It makes an isolated worktree on a new branch `carrydown/request-<request id>`, copies only the approved files and the receipt, and commits as you. It prints the push and `gh pr create` commands. The agent names the branch and the destination and runs them only after your yes, because pushing and creating the engineering pull request are a separate write.

When something changes, `release.py diff --root .` names the work items a change touches, and a new `preview`, `prepare` and approval follow. To end the active request, run `release.py withdraw --root . --reason <code>` and `--apply`, approve the state change the same way, then `release.py export-state --root . --apply` to publish the terminal receipt. [Recover a plan or publication](recovery.md#resume-an-interrupted-release) says how to resume each step if it is interrupted.

Minimum GitHub access for these commands:

| Command | Access it needs |
| --- | --- |
| `doctor`, `approve --github`, `export`, `export-state` on the "no" path | The read-only token above, for the checks. Your git credentials with write access to the staging repository, to push the candidate branch. |
| Pushing the export branch and opening the engineering pull request | Your git credentials with write access to the engineering repository, and your own `gh` sign-in to create the pull request. |
| Publishing issues and the board with `carrydown-plan-to-github` | The token in [the plan owner guide](plan-owner-guide.md#the-token): Issues read and write, Metadata read, and Projects read and write. |

## Who holds which credential

| Credential | Held by | Can do |
| --- | --- | --- |
| The plan owner's token | The owner's machine, never a repository | Read the facts above. The owner's git credentials push candidate branches to staging. |
| The verifier App's key | Secrets of the tooling repository only | Read contents and pull requests of enrolled repositories and write checks. |
| The staging workflow's `GITHUB_TOKEN` | The staging repository's Actions run | Read contents and write pull requests, so it can open a request. Nothing else. |
| Engineering repositories | Nothing | They hold no verifier workflow and no verifier secret. The doctor checks this. |

## Limits to state to your reviewers

- **Five minutes is a requested interval, not a deadline.** GitHub documents that scheduled runs can be delayed or dropped. An administrator can run the workflow by hand with Run workflow, and an optional webhook hosted by the organization can request an earlier run. Neither removes queueing or the race below.
- **A successful check can outlive its inputs.** GitHub does not expire an old success. If the scheduler stops, an old success can stay mergeable. The scan health check makes owner-side writes refuse when the verifier is stale. It does not invalidate a success that already exists.
- **State can change between a poll and a merge.** The reference deployment promises verification at the observed revisions. It does not promise continuous authorization or immediate revocation at the moment of merge. An organization that needs fresh authorization enforced at the exact merge must supply its own trusted merge controller. This deployment does not claim to be one.
- **Withdrawal reaches engineers only after the receipt update merges.** Staging state is authoritative at once for owner-side writes. Engineers learn it from the receipts on their fetched default branch.
- **Runtime isolation is attested, not proven.** The tests prove that an engineering clone carries no workspace locator or withheld text. They do not prove that an engineer's agent cannot read an owner-only folder. The runtime-isolation attestation records an administrator's claim about the real environment.

## Acceptance on real GitHub

Status: **not yet performed.** The fake-API tests cover the logic of every item below. They cannot show how GitHub counts reviews or which identity authored the request, so this run is a release prerequisite. The plan owner runs it only after explicitly authorizing it. Use a dedicated test organization, a fictional candidate, one human owner, the real App and the exported rulesets. Do not delete any resource the run creates.

Run these steps in order, and record the outcome of each in the table.

1. Install the tooling repository, the App, the staging repository and the engineering repository as above. Run the live doctor. Every component must be verified.
2. Prepare a fictional candidate, approve it with `release.py approve --root . --github --apply`, and confirm that the request pull request was opened by the Actions identity, not by the owner.
3. As the owner, approve the final head. Push another commit and confirm the approval is dismissed as stale. Approve the new head again.
4. Confirm that `require_last_push_approval` is off and that the owner, who pushed the branch, can approve it.
5. Confirm that `carrydown-staging-verifier` passes only after the authorized review of the final head, and fails before it.
6. Merge with a merge commit. Confirm that activation happened: the request is active and `release.py export` accepts it.
7. Export, open the engineering pull request, and confirm that `carrydown-release-verifier` passes. Then change one byte of an exported file and confirm the check fails.
8. Prepare a replacement, approve and merge it, and confirm the first request becomes superseded in one batch and the engineering receipts update.
9. Withdraw the active request. Confirm the receipt-only pull request passes and that a content publication stays refused.
10. Stop the scheduled workflow, wait past `check_health_max_age_seconds`, and confirm the doctor reports the scan health as missing. Restart it.

Three facts to plan for before the run:

- **A second GitHub account.** The engineering pull requests of steps 7 to 9 need a second account, with write access to the engineering repository, to approve and merge them. The engineering ruleset requires one approving review, the owner opens those pull requests, and GitHub does not let one person approve their own pull request.
- **The tooling ruleset comes last.** For the same reason, in this run the ruleset that protects the tooling repository's default branch is created at the end of organization step 5, after the verifier commit, the enrollment and the attestations are merged, not in organization step 1. With one human, a reviewed pull request on the tooling repository could not be approved before that. The end state is the one the organization steps describe.
- **An enrollment without a board target is unproven.** A run that publishes no board enrolls only the `engineering` target. Whether such an enrollment passes every check has been read in the code, not shown on real GitHub.

Record the results here when the run is done.

| Item | Record |
| --- | --- |
| Date of the run | Not yet performed |
| Platform and plan | Not yet performed |
| Repository ids (tooling, engineering, staging) | Not yet performed |
| App id and permissions | Not yet performed |
| Ruleset ids and the settings they hold | Not yet performed |
| Request opened by the Actions identity (step 2) | Not yet performed |
| Owner approval and stale-review dismissal (step 3) | Not yet performed |
| Last-pusher setting off (step 4) | Not yet performed |
| Staging check outcomes (step 5) | Not yet performed |
| Merge activation (step 6) | Not yet performed |
| Engineering check outcomes (step 7) | Not yet performed |
| Replacement (step 8) | Not yet performed |
| Receipt-only withdrawal (step 9) | Not yet performed |
| Scan health and scheduler behavior (step 10) | Not yet performed |
| Sanitized check outcomes (ids and reason codes only) | Not yet performed |

### Run it with the runner

The repository carries a runner for this section: `tests/acceptance/live_github_run.py`. It covers the seven organization setup steps and the ten acceptance steps above, in order. It does what a program can do, stops for what needs a person, checks each result through `gh api`, and appends one record per step to a file. It needs the `gh` command line tool, signed in as an owner of the throwaway organization. It never reads, prints or logs a token, it never deletes a resource, and it refuses an organization unless you pass `--throwaway`.

```bash
python3 tests/acceptance/live_github_run.py doctor --org NAME
python3 tests/acceptance/live_github_run.py plan
python3 tests/acceptance/live_github_run.py run --org NAME --throwaway --record run.jsonl --apply
python3 tests/acceptance/live_github_run.py render --record run.jsonl
```

`doctor` prints which preconditions are verified. `plan` lists the 17 steps and marks which are automatic and which need a person. `run` without `--apply` only reads. With `--apply` it writes to the throwaway organization, and the plan owner authorizes that explicitly first. The run pauses at each human step, prints what to do and what to confirm, waits for you to press enter, and checks the state again before it goes on. Those steps are creating the verifier App in a browser, vouching for the attestations, approving the staging pull requests as the owner, and approving and merging the engineering pull requests with a second account, because GitHub does not let an author approve their own pull request. A run that stops resumes with the same command, and `--from STEP` starts at a step. `render` prints the table above from the records, with the same rows in the same order. Paste it in place of the table. A row with no record stays "Not yet performed".
