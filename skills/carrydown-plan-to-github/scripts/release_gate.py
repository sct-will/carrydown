#!/usr/bin/env python3
"""The release gate: the one module every command that writes outside the private workspace calls
first. Standard library only. Offline. It never reads a token and never talks to a network.

Write classes
  draft       a working file written into the engineering repository while drafting
  candidate   a file written into the private workspace
  release     approved content: repository artifacts, issue bodies, labels, board values, comments
  state-only  regenerated receipts that report an authenticated withdrawal or supersession

Today the gate is a stub. Every call returns legacy(no-handling-policy), so no command changes
behavior. The release work package replaces the body of check with the real decision. There is no
command-line flag and no environment variable that bypasses the gate, and none will be added.

This module is imported by the other scripts. Run with --help to see this text.
"""
import argparse
import sys
from typing import NamedTuple, Optional

WRITE_CLASSES = ("draft", "candidate", "release", "state-only")
OUTCOMES = ("legacy", "allow", "deny")

# The fixed reason codes. The gate and the verifier print these and never attach content.
REASON_CODES = frozenset("""
not-approved approval-not-found approval-not-on-final-revision approver-not-authorized approval-scope-mismatch
unauthenticated-release sha256-mismatch working-copy-differs destination-not-allowed audience-visibility-mismatch
superseded withdrawn expired could-not-refresh mixed-release unapproved-substitution assignee-unresolved
drafting-is-private no-handling-policy enrolled-project-missing-handling policy-pointer-mismatch
workspace-unavailable workspace-inside-repository setup-not-verified restricted-destination-unsupported
governed-file-without-release exception-not-permitted
approval-mechanism-unsupported staging-access-not-verified destination-access-not-verified target-identity-mismatch
receipt-projection-mismatch state-history-invalid state-only-content-write policy-revision-mismatch
verifier-code-mismatch verifier-unhealthy evidence-unavailable inputs-changed-during-verification
unsafe-artifact-path artifact-operation-unsupported schema-view-mismatch
""".split())


class Decision(NamedTuple):
    """The gate's answer. allowed says whether the write may go ahead. outcome is legacy, allow or
    deny. code is a fixed reason code. request_id names the approval that authorized the write,
    when there is one."""
    allowed: bool
    outcome: str
    code: str
    request_id: Optional[str]


def check(write_class, artifact_path, content_digest, destination, root, *,
          request_id=None, event_id=None, verified_context=None):
    """Ask whether a write is permitted. Call this before every write outside the private workspace.

    write_class is one of WRITE_CLASSES. artifact_path is the file or the target key, content_digest
    the lowercase SHA-256 of the bytes to be written, destination the target identity, and root the
    project folder. request_id and event_id name the approval and the state batch in play.
    verified_context holds the policy, approval, event replay and target identities that a
    network-capable command verified; a receipt or a caller-supplied flag is not one.

    The stub returns legacy(no-handling-policy) for every valid write class, so callers behave as
    they always did. An unknown write class is a bug in the caller and raises ValueError."""
    if write_class not in WRITE_CLASSES:
        raise ValueError(f"unknown write class {write_class!r}. Use one of: {', '.join(WRITE_CLASSES)}")
    return Decision(True, "legacy", "no-handling-policy", request_id)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="The release gate for commands that write outside the private workspace. A library: "
                    "import it and call check(). There is no flag that bypasses it. Today it returns "
                    "legacy(no-handling-policy) for every call.")
    ap.parse_args(argv)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
