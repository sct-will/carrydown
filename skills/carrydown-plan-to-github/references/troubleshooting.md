# Troubleshooting

Each script prints the HTTP status and GitHub's message with the token removed. Match it here.

| Symptom | Cause | Fix |
| --- | --- | --- |
| `No GitHub token found` | No token file or environment variable. | Run `python3 <skill>/scripts/github_token.py`. |
| HTTP 401 `Bad credentials` | Token wrong, revoked or expired. | Create a new token and store it again. |
| HTTP 403 or 404 on an organization repository, message mentions SSO or SAML | The token is not authorized for the organization. | For a classic token, give the user [their GitHub tokens page](https://github.com/settings/tokens) to open, then Configure SSO. |
| HTTP 404 on the repository | Wrong name, or the token cannot see it. | Check `owner/name`. Check that the token can reach the repository: a fine-grained token with that repository selected, or a classic token with `repo`. |
| HTTP 403 `Resource not accessible by personal access token` | A fine-grained token lacks a permission. | Add Issues read and write, and for projects the organization permission Projects read and write. User-owned projects need a classic token. |
| HTTP 403 `secondary rate limit` | Too many writes too fast. | The script waits and retries. If it still fails, wait a few minutes and rerun. It resumes. |
| HTTP 422 on a sub-issue link | The issue is already a sub-issue of another parent, or a hierarchy limit was hit. | Remove the old parent in GitHub, rerun. |
| `Could not resolve to a User` or `Organization` | `--owner` is wrong. | Pass the user or organization login. |
| `Resource not accessible` on a GraphQL project call | Missing project permission. | A fine-grained token needs the organization permission Projects read and write. A classic token needs `project`. |
| Issue created without a label | The label did not exist and the account may not create labels. | Create the label, rerun. |
| Assignee missing on an issue | The login is not a collaborator on the repository. | Add them as collaborator, or leave `github` empty in `plan.yaml`. |
| Work unit iterations differ from the plan | The project existed with other dates. | Rerun with `--reconfigure-iterations`, then rerun to refill values. |
| An issue title still shows the old name after a rename in `plan.yaml` | The script finds issues by their hidden marker and never changes a title, not even with `--update-bodies`. Renaming is safe and makes no duplicate. | Edit the title on GitHub by hand if you want the new name there. |

## Safe reruns

Every script can be rerun. The sync script skips existing issues. The project script skips existing fields, views and values. If a run stopped half way, run the dry run, read what is left, and run with `--apply` again.

## Undoing

The scripts do not delete anything. To undo, tell the user to close the issues and delete the project or repository in the GitHub interface themselves.
