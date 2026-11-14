# Troubleshooting

Each script prints the HTTP status and GitHub's message with the token removed. Match it here.

| Symptom | Cause | Fix |
| --- | --- | --- |
| `No GitHub token found` | No token file or environment variable. | Ask the user to run `python3 <skill>/scripts/github_token.py` in their own terminal and paste the token at the hidden prompt. |
| `token file not found` | The path given to `--token-file` does not exist. The stored token is not used in its place. | Check the path, or leave out `--token-file`. |
| `can be read by other users` | The token file has a loose mode, such as 644. | Run the `chmod 600 <path>` the message names. |
| `does not hold a GitHub personal access token` | The file or variable holds something else, or a second line. | Store the token again with `github_token.py`. Nothing was sent. |
| `redirected to another host` | GitHub answered with a redirect to a different host. The token was not sent there. | Check the repository and owner names. |
| HTTP 401 `Bad credentials` | Token wrong, revoked or expired. | Create a new token and store it again. |
| HTTP 403 or 404 on an organization repository, message mentions SSO or SAML | The token is not authorized for the organization. | For a classic token, give the user [their GitHub tokens page](https://github.com/settings/tokens) to open, then Configure SSO. A fine-grained token made for the organization avoids this, so prefer one. |
| HTTP 404 on the repository | Wrong name, or the token cannot see it. | Check `owner/name`. Check that the token can reach the repository: a fine-grained token with that repository selected, or a classic token with `repo`. |
| HTTP 403 `Resource not accessible by personal access token` | A fine-grained token lacks a permission. | Add Issues read and write, and for projects the organization permission Projects read and write. User-owned projects need a classic token. |
| HTTP 403 `secondary rate limit` | Too many writes too fast. | The script waits and retries. If it still fails, wait a few minutes and rerun. It resumes. |
| HTTP 422 on a sub-issue link | The issue is already a sub-issue of another parent, or a hierarchy limit was hit. | Remove the old parent in GitHub, rerun. |
| `Could not resolve to a User` or `Organization` | `--owner` is wrong. | Pass the user or organization login. |
| `Resource not accessible` on a GraphQL project call | Missing project permission. | A fine-grained token needs the organization permission Projects read and write. A classic token needs `project`. |
| Issue created without a label | The label did not exist and the account may not create labels. | Create the label, rerun. |
| Assignee missing on an issue | The login is not a collaborator on the repository. | Add them as collaborator, or leave `github` empty in `plan.yaml`. |
| Work unit iterations differ from the plan | The project existed with other dates. | Rerun with `--reconfigure-iterations`, then rerun to refill values. |
| A clarification request still shows `pending` after the owner decided | The decision was not recorded as a comment on the issue, or its first line is not exactly `Clarification disposition: accepted`, `Clarification disposition: declined` or `Clarification disposition: deferred`. The comment must also come after the request and name it, by a link that ends in `issuecomment-` and the request's comment id, or on a `Request:` line. A comment that names another request does not apply to this one. | Record it with `github_sync.py --clarification-disposition ISSUE STATE --request-comment ID`, as a dry run first and then with `--apply`. It writes the first line and the link for you. Then run `--clarifications` again. |
| A disposition from an account that is not the owner is ignored | The list prints `unverified disposition by another account` with the comment link, and the request keeps the state it had, usually `pending`. Only a decision by the login the plan names for the mention channel or by the account the token belongs to counts. The comment is never written into the observation as a decision. | Check who wrote the comment. If the owner meant it, post the decision from the owner's own account, or run `github_sync.py --clarification-disposition ISSUE STATE --request-comment ID` with the owner's token, as a dry run first and then with `--apply`. Then run `--clarifications` again. |
| The clarification observation is older than the owner expects | `<workspace>/events/clarifications.json` is a snapshot. It changes only when `github_sync.py --clarifications --apply` runs. A decision or a new request made later is not in it. | Run `github_sync.py --root . --clarifications --apply` and read the observation time again. Without a private workspace the script prints the list and says it was not recorded. |
| An issue title still shows the old name after a rename in `plan.yaml` | The script finds issues by their hidden marker and never changes a title, not even with `--update-bodies`. Renaming is safe and makes no duplicate. | Edit the title on GitHub by hand if you want the new name there. |

## Safe reruns

Every script can be rerun. The sync script skips existing issues. The project script skips existing fields, views and values. If a run stopped half way, run the dry run, read what is left, and run with `--apply` again.

## Undoing

The scripts do not delete anything. To undo, tell the user to close the issues and delete the project or repository in the GitHub interface themselves.
