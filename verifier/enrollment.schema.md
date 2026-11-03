# Enrollment file reference

`enrollment.yaml` sits at the top of the tooling repository. It is the trust baseline of the private
drafting path: it says which engineering repositories are protected, who may approve a release for
them, where their staging repository is, which paths the verifier governs, and which facts an
administrator vouches for. Only release owners and administrators can write to the tooling repository,
and its default branch is protected, so a project cannot change its own policy.

Read the file as data. The verifier never executes it, and the launcher reads it from a checkout of the
tooling repository's protected default branch. The commit of that checkout is the `policy_commit_sha`.

## File layout

```yaml
format: 1                     # an integer. A reader refuses a format it does not know.
host: github.com              # the GitHub host. Every repository below lives on it.
tooling_repository_id: 4100   # the numeric id of the repository that holds this file
repositories:                 # one entry per enrolled engineering repository
  - ...                       # see the example below
```

The launcher finds the verifier commits with a line search, so write each entry in block style: one key
per line, and `verifier_sha:` on a line of its own with the full commit id. Flow style (`{a: 1}`) is fine
inside a value, never for the entry itself.

## Fields of an entry

| Field | Meaning |
| --- | --- |
| `repository`, `repository_id` | The engineering repository. The numeric id decides. A renamed repository keeps its enrollment. A different repository that takes the old name has a different id and is not enrolled. |
| `enrollment_id` | The stable identity of the project: the SHA-256 (Secure Hash Algorithm, 256 bits) of the canonical JSON (JavaScript Object Notation) of `{"host", "tooling_repository_id", "repository_id"}`. It does not change when the policy changes. |
| `policy_sha256` | The SHA-256 of the canonical JSON of this entry with only `policy_sha256` left out. It changes when any permission changes, which forces reassessment of every earlier approval. |
| `staging_repository`, `staging_repository_id` | The private repository where release candidates are approved. |
| `staging_workflow_sha256` | The SHA-256 of the installed `.github/workflows/open-release-request.yml`. The doctor and the staging check compare the installed file with it. |
| `staging_readers` | The intended readership of the staging repository: `user_ids` (numeric account ids) and `approved_service_ids` (the Apps allowed to read it). Anyone else with effective access blocks the first upload. |
| `approvers` | Accounts whose approval can authorize disclosure: `id` (the authority) and `login` (a display and lookup hint). |
| `administrators` | Accounts that may sign attestations. |
| `allowed_targets` | The destinations a release may name. Each is an exact identity: host, numeric repository id and, for a board, the owner id and the project node id. An approval selects a subset. |
| `governed_paths` | The path patterns the verifier governs in the engineering repository. `**` crosses folders, `*` does not. `docs/release/` is always governed. |
| `engineer_edits` | For a governed pattern, `request-only` or `allowed`. With `request-only`, which is the default, an engineer cannot change an exported specification without a new release. With `allowed`, a change that touches only "Decisions recorded" of an exported specification is permitted. |
| `reuse_unchanged_preview` | Whether the owner's preview may collapse artifacts that did not change. It never removes the approval. |
| `offline_grace_days` | How long the engineers' skill may proceed on local validity alone after its last successful refresh. |
| `verifier_sha` | The full commit id of the verifier code. It is an earlier commit than the policy commit. The code never names its own commit or the latest policy. |
| `verifier_app_id` | The numeric id of the verifier App. Both required checks must come from this integration, not merely carry the right name. |
| `check_health_max_age_seconds` | How old the last complete scan may be before owner-side writes refuse. The default is 900. |
| `attestations` | Facts an administrator vouches for. See below. |

## Attestations

An attestation is accepted for a component only when all of these hold: its `component` is the one being
checked, every key of the component's subject appears with the same value in its `subject`, `by_id` is an
`administrators` id, `at` has passed, `expires_at` has not, and it is in the protected history of this
file. A `by_id` alone is not proof. During setup, record the tooling pull request review or the
configuration audit entry that shows who approved it in `note`. An attestation covers an inspectable
configuration or access fact. It never replaces a content hash, an approval identity, an event state,
an expiry or the verifier's scan health, and the doctor never turns an unreadable live fact into success
with a generic attestation.

| Component | Subject keys | What it vouches for |
| --- | --- | --- |
| `staging-readers` | `repository_id`, `reader_ids`, `service_ids` (exactly) | The effective readers of the staging repository, including Apps that the API does not list for a person's token. A change to the reader set changes the subject and so ends the attestation. |
| `ruleset-coverage` | `repository_id`, `integration_id` | The engineering ruleset requires `carrydown-release-verifier` from the verifier App, when the owner's token cannot read rulesets. |
| `runtime-isolation` | `repository_id` | The organization's agent environment cannot read an owner's workspace. Carrydown cannot prove it. |
| `verifier-isolation` | `repository_id`, `staging_repository_id` | The engineering and staging repositories hold no verifier workflow and none of the verifier App's secrets, when secret names are not readable. |
| `destination-readers` | `repository_id`, `owner_id`, `project_id` | The readers of a board, which the API does not list. |

## Example

The digests in this example are real: `enrollment_id` and `policy_sha256` follow from the other fields,
and `staging_workflow_sha256` is the digest of the template in `templates/staging/`. The ids are
fictional. A test parses this block and checks every rule above.

```yaml
format: 1
host: github.com
tooling_repository_id: 4100
repositories:
  - repository: acme/expense-approvals
    repository_id: 4200
    enrollment_id: b410cc8a81a2a84096c8ada4a62793256606e4409384b0d1755ccbafd3264118
    policy_sha256: 8b160e57c71901798efaa31d84c45e37373b4f4a738ac02a37f975da18ba85e1
    staging_repository: acme/expense-approvals-releases
    staging_repository_id: 4300
    staging_workflow_sha256: f1712db0d1808fe662331700ff11a73821606ba445995e521da819c2eb113049
    staging_readers:
      user_ids: [12345, 78674552]
      approved_service_ids: [carrydown-app-installation]
    approvers: [{id: 78674552, login: sct-will}]
    administrators: [{id: 12345, login: org-admin-login}]
    allowed_targets:
      engineering: {host: github.com, repository_id: 4200, repository: acme/expense-approvals}
      board: {host: github.com, repository_id: 4200, owner_id: 4400, project_id: PVT_example}
    governed_paths: ["docs/spec/**", "docs/context/**", "docs/release/**", "docs/dev/skills/**", "docs/ground-truth/**"]
    engineer_edits: {docs/spec/**: request-only}
    reuse_unchanged_preview: false
    offline_grace_days: 7
    verifier_sha: 9f3c1d5a7b2e4086c3d1f0a9b8e7d6c5b4a39281
    verifier_app_id: 123456
    check_health_max_age_seconds: 900
    attestations:
      - component: ruleset-coverage
        by_id: 12345
        at: "2027-01-10T09:00:00Z"
        expires_at: "2027-02-10T09:00:00Z"
        subject: {repository_id: 4200, integration_id: 123456, ruleset_id: 4500}
        note: "Ruleset 'carrydown release' requires check 'carrydown-release-verifier' from the App on main"
      - component: runtime-isolation
        by_id: 12345
        at: "2027-01-10T09:05:00Z"
        expires_at: "2027-02-10T09:05:00Z"
        subject: {repository_id: 4200, environment_id: managed-engineering-agents}
        note: "Engineering agents run as users without read access to owner workspaces"
```

## Rules the verifier applies to this file

- The file must be the file at the head of the tooling repository's protected default branch. A copy from
  another branch, or from a commit that is no longer the head, is refused (`policy-revision-mismatch`).
- Each entry is checked before use: the repository id, the stable `enrollment_id`, the recomputed
  `policy_sha256`, the account ids, the pinned commit and the governed paths. A malformed entry is
  `policy-pointer-mismatch`.
- A request and an event record the `policy_commit_sha` and `policy_sha256` they were made under. An
  older policy is accepted for an audit only from an ancestor of the protected head with a matching
  digest. New content writes need the request's digest to equal the current one.
- A project is never legacy once it has an entry. Deleting `.carrydown/release-policy.yaml` or the
  handling block fails the check (`policy-pointer-mismatch`, `enrolled-project-missing-handling`).
