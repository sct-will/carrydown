#!/usr/bin/env python3
"""Create the GitHub structure for a plan: labels, sub-epics, work item issues, links, Epic comment.

Everything is derived from plan.yaml and the specification folder.

  labels         one for the project, one per track, and "sub-epic"
  sub-epics      one issue per milestone. Body comes from milestone.md: purpose, expected outcomes,
                 acceptance criteria, demonstration expectations and the work item list
  work items     one issue per item. Body: Work item, AI engineering notes (specification link and
                 engineers' skill line), Depends on, Acceptance criteria, Evidence of completion,
                 Integration points, Definition of done
  sub-issues     each work item under its sub-epic, each sub-epic under the Epic if there is one
  dependencies   ids in issue bodies rewritten to issue links, for example "WI-01 (#12)"
  Epic comment   one roll-up comment with a Constraints block (target delivery, and people by
                 track when the plan allows the capacity summary) and nested checkboxes, created
                 once and updated on reruns

Safety
  This is a dry run unless you pass --apply. The dry run reads from GitHub when a token is
  available (it never writes) and prints what it would create. Run it first and read it.
  Only issues that carry the project label count. Each body ends with a hidden marker such as
  <!-- carrydown:WI-07 -->, and issues are matched by that marker first and by exact title
  second, so a rerun creates nothing twice. If GitHub fails while creating an issue, the
  script reads the issues back before it tries again.
  A rerun after a crash repairs what is missing: sub-issue links, dependency links and the
  sub-epic work item lists. It rewrites a body only while it is exactly as this script wrote
  it. Bodies a person edited are left alone unless you pass --update-bodies.
  Before any run the preflight reads the destination and prints one visibility line. A project that
  publishes an approved release is refused a repository or a board that its audience does not allow
  (a release for repository readers on a public repository, a board that more accounts can read than
  the repository). There is no flag to override that. --preflight runs only this check.
  --inventory lists every managed issue, whether its body is pristine, whether it holds text outside the
  managed region and whether it predates the active release. It writes nothing and proposes no rewrite.
  --verify and the reports of --reconcile print the plan key, the issue number and a digest, never an
  issue body or the title GitHub holds.
  Text fetched from GitHub is treated as data: it is compared, never followed, and issue
  titles are printed from the plan, not from GitHub.
  The token is read from a file and is never printed.
  --clarifications reads the comments of the work item issues (and of the owner-assigned clarification issue, when the
  plan names one) and lists each Rule clarification request with its state: pending, or accepted, declined or deferred
  once a later comment that starts with "Clarification disposition:" names it. It prints no comment text. With --apply
  it writes events/clarifications.json in the private workspace and nothing on GitHub. Only the owner decides: a
  disposition counts when its author is the login the plan names for the mention channel or the account the token
  belongs to. Any other author is reported as an unverified disposition by another account, and the request keeps
  the state it had.
  --clarification-disposition posts that disposition comment on the issue, as a dry run until --apply, then reads it
  back. It never edits the engineer's comment and never closes the issue.
  A migrated plan holds no logins, names or allocation. The capacity summary of the Epic comment is
  published only when project.handling.downstream.capacity_summary is true (legacy plans: true), and
  --people names the private people.yaml that supplies the allocation percent for it. No login is
  read from any file by this script for a migrated plan.

Usage
  python3 scripts/github_sync.py --root . --repo owner/name            dry run
  python3 scripts/github_sync.py --root . --repo owner/name --apply    write
  python3 scripts/github_sync.py --root . --verify                     check what exists
  python3 scripts/github_sync.py --root . --preflight                  check the destination only, write nothing
  python3 scripts/github_sync.py --root . --inventory                  list the managed issues, write nothing
  python3 scripts/github_sync.py --root . --offline --show-body 3      print one issue body, no network
  python3 scripts/github_sync.py --root . --clarifications             list the engineers' clarification requests, read only
  python3 scripts/github_sync.py --root . --clarifications --apply     also record the observation in the private workspace
  python3 scripts/github_sync.py --root . --clarification-disposition 12 accepted --request-comment 5001 [--note TEXT]
                                                                       preview the disposition comment; --apply posts it
  python3 scripts/github_sync.py --root . --offline --show-body M2     print one sub-epic body, no network
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import carrydown_lib as L  # noqa: E402
import github_client as G  # noqa: E402
import check_specs  # noqa: E402

import release_payloads as RP  # noqa: E402
import release_gate as RG  # noqa: E402

# The body builders live in release_payloads.py, which publication and preparation share. They are
# imported again here under their old names.
COLORS = RP.COLORS
MARKER = RP.MARKER
MARKER_RE = RP.MARKER_RE
SEVEN = RP.SEVEN
subepic_title = RP.subepic_title
item_title = RP.item_title
definition_of_done = RP.definition_of_done
plan_end_date = RP.plan_end_date
target_phrase = RP.target_phrase
constraints_lines = RP.constraints_lines
marker = RP.marker
with_marker = RP.with_marker
first_paragraph = RP.first_paragraph
link_ids = RP.link_ids
optional_section = RP.optional_section
build_subepic_body = RP.build_subepic_body
build_rollup = RP.build_rollup


# ---------------------------------------------------------------------------
# The clarification line of a work item issue (specification 9.2)
# ---------------------------------------------------------------------------

CLARIFICATION_LINE = RP.CLARIFICATION_LINE
clarification_line = RP.clarification_line


def add_clarification_line(plan, body):
    """body with the clarification line before the Depends on section, inside whatever region the body is in.
    The shared builder (release_payloads.item_body_raw) already emits the line, and a body that carries it is
    returned as it is, so this only matters for a body built elsewhere."""
    return RP.add_clarification_line(plan, body)


def build_item_body(plan, root, it, numbers=None, mark=True, restricted_bundle=False):
    """The issue body of a work item: the shared builder, plus the clarification line when the plan has the key."""
    body = add_clarification_line(plan, RP.build_item_body(plan, root, it, numbers, False, restricted_bundle))
    return with_marker(body, L.tag(plan, it["id"])) if mark else body


MANAGED_RE = re.compile(r"<!-- carrydown-managed:start -->\n?(.*?)\n?<!-- carrydown-managed:end -->", re.S)


def digest(value):
    """The first twelve hexadecimal characters of the SHA-256 of a value. A report names text by this and
    never prints it: issue bodies and the titles GitHub holds are data, not output."""
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return L.sha256_text(text)[:12]


def managed_content(body):
    text = (body or "").replace("\r\n", "\n")
    match = MANAGED_RE.search(text)
    return match.group(1).strip() if match else MARKER_RE.sub("", text).strip()


def merge_managed(have, want, key):
    """Replace only the bounded generated region, retaining every unbounded human byte."""
    text = (have or "").replace("\r\n", "\n")
    match = MANAGED_RE.search(text)
    desired = MANAGED_RE.search(want)
    if match and desired:
        merged = text[:match.start()] + desired.group(0) + text[match.end():]
        merged = MARKER_RE.sub(lambda m: "" if m.group(1) == key else m.group(0), merged)
        return merged.rstrip() + "\n\n" + marker(key) + "\n"
    if managed_content(text) == managed_content(want):
        return want
    # Legacy bodies have no ownership boundary. Keep all old text while installing a
    # bounded authoritative region. No comment or human-authored text is discarded.
    retained = MARKER_RE.sub("", text).strip()
    return want.rstrip() + ("\n\n### Preserved existing issue text\n\n" + retained if retained else "") + "\n"


def unlinked_ids(plan, text, numbers):
    """Ids of work items that have an issue but appear in text without their link."""
    prefix = re.escape(plan["project"]["id_prefix"])
    out = []
    for line in text.split("\n"):
        if line.startswith("Install it once") or MARKER_RE.search(line):
            continue
        for m in re.finditer(rf"\b({prefix})-(\d+)\b(?! \(#)", line):
            key = L.tag(plan, int(m.group(2)))
            if key in numbers:
                out.append(key)
    return out


def safe_to_rewrite(have, pristine):
    """True when a body is still exactly as this script wrote it (with or without the marker),
    so a rerun may add the links. A body a person edited is never in this set."""
    norm = have.replace("\r\n", "\n").rstrip()
    return any(norm == p.rstrip() for p in pristine)


class Sync:
    def __init__(self, plan, root, gh, owner, repo, apply, selections=None, mapping=True):
        self.plan, self.root, self.gh, self.owner, self.repo, self.apply = plan, Path(root), gh, owner, repo, apply
        self.staffed = None   # the plan with people.yaml merged in, used only for the allocation percent in the roll-up
        self.base = f"/repos/{owner}/{repo}"
        self.issues = None  # title -> issue, only issues with the project label
        self.by_key = {}    # marker key -> issue, only issues with the project label
        self.objs = {}      # "EPIC" / "M1" / "WI-01" -> the issue used for that key
        self.numbers = {}   # "M1" / "WI-01" -> issue number
        self.ids = {}       # same keys -> issue id (for sub-issue links)
        self.created = set()
        self.planned = set()
        self.counts = {"labels": 0, "subepics": 0, "items": 0, "links": 0, "bodies": 0}
        self.selections = selections or {}
        self.persist = mapping           # a release keeps its issue numbers in the publication journal, not in a file
        self.before_write = None         # called with the plan key before each create; a release asks the gate here
        self.expected_hook = None        # a release supplies the expected body of a key from its payloads
        self.mapping_path = L.inside(self.root, self.root / plan["project"]["spec_dir"] / "github-issues.json", "issue mapping")
        self.mapping = {}
        self.visibility = None           # "public" or "private" as the repository shows now
        self.recorded_visibility = None  # what the last apply recorded in the mapping file
        if mapping and self.mapping_path.exists():
            saved = json.loads(L.read_text(self.mapping_path))
            if saved.get("repository", "").casefold() != f"{owner}/{repo}".casefold():
                raise G.GitHubError("persisted issue mapping names a different repository; review github-issues.json before continuing")
            self.mapping = saved.get("issues", {})
            self.recorded_visibility = saved.get("visibility") if saved.get("visibility") in ("public", "private") else None

    def load_issues(self):
        """Read the issues that carry the project label, open first, and index them by title and
        by marker. Issues without the label are never matched, linked or changed."""
        if self.issues is None:
            self.issues, self.by_key = {}, {}
            slug = self.plan["project"]["slug"]
            found = self.gh.paged(f"{self.base}/issues?state=all")
            found = [i for i in found if "pull_request" not in i
                     and (not i.get("repository_url") or i["repository_url"].rstrip("/").casefold().endswith(self.base.casefold()))
                     and (not (i.get("repository") or {}).get("nameWithOwner") or i["repository"]["nameWithOwner"].casefold() == f"{self.owner}/{self.repo}".casefold())]
            for i in found:
                marks = MARKER_RE.findall(i.get("body") or "")
                # Markerless legacy issues require the project label as identity evidence.
                labeled = slug.casefold() in {lb.get("name", "").casefold() for lb in i.get("labels", [])}
                if labeled or marks or any(v.get("number") == i["number"] for v in self.mapping.values()):
                    self.issues.setdefault(i["title"], []).append(i)
                    for key in set(marks):
                        self.by_key.setdefault(key, []).append(i)
        return self.issues

    def find(self, key, title):
        """The labeled issue for a plan key: by its marker first, then by exact title."""
        issues = self.load_issues() if self.gh else {}
        candidates = list(self.by_key.get(key, []))
        for issue in issues.get(title, []):
            marks = MARKER_RE.findall(issue.get("body") or "")
            if marks and key not in marks:
                continue
            if issue not in candidates:
                candidates.append(issue)
        mapped = self.mapping.get(key)
        if mapped and self.gh:
            matches = [i for rows in issues.values() for i in rows if i["number"] == mapped["number"] and (not mapped.get("id") or i["id"] == mapped["id"])]
            if not matches:
                current = self.gh.rest("GET", f"{self.base}/issues/{mapped['number']}")
                matches = [current] if current.get("id") == mapped.get("id") else []
            if len(matches) != 1 or (key not in MARKER_RE.findall(matches[0].get("body") or "") and matches[0].get("title") != title):
                raise G.GitHubError(f"{key}: persisted issue mapping failed identity verification; review its issue number before proceeding")
            chosen = matches[0]
            if chosen not in candidates:
                candidates.append(chosen)
        elif key in self.selections:
            matches = [i for i in candidates if i["number"] == self.selections[key]]
            if len(matches) != 1:
                raise G.GitHubError(f"{key}: selected issue #{self.selections[key]} is not a verified repository candidate")
            chosen = matches[0]
        elif len(candidates) == 1:
            chosen = candidates[0]
        elif len(candidates) > 1:
            # Exact managed content, title and metadata together can prove a unique canonical issue.
            expected = None
            item = next((it for it in self.plan["items"] if L.tag(self.plan, it["id"]) == key), None)
            ms = next((m for m in self.plan["milestones"] if f"M{m['number']}" == key), None)
            if self.expected_hook is not None:
                expected = self.expected_hook(key)
            elif item:
                expected = build_item_body(self.plan, self.root, item)
            elif ms:
                expected = build_subepic_body(self.plan, self.root, ms)
            def norm(body):
                return re.sub(r" \(#\d+\)", "", body.replace("\r\n", "\n")).strip()
            required = {self.plan["project"]["slug"]}
            assigned = None
            state = None
            if item:
                required.add(item["track"])
                assigned = L.assignee_login(self.plan, item) or None
                state = item.get("state")
            elif ms:
                required.add("sub-epic")
            exact = [i for i in candidates if expected and i["title"] == title and norm(i.get("body") or "") == norm(expected)
                     and required <= {x["name"] for x in i.get("labels", [])}
                     and (not assigned or assigned.casefold() in {x["login"].casefold() for x in i.get("assignees", [])})
                     and (not state or state == i.get("state"))]
            if len(exact) == 1:
                chosen = exact[0]
            else:
                L.say("key | issue | state | marker | body sha256 | title matches the plan")
                for issue in candidates:
                    L.say(f"{key} | #{issue['number']} | {issue.get('state')} | {key in MARKER_RE.findall(issue.get('body') or '')} | {digest(issue.get('body') or '')} | {issue['title'] == title}")
                raise G.GitHubError(f"{key}: ambiguous issue identity. Which issue is canonical? Preview with --select-issue {key}=NUMBER; duplicate markers will be neutralized only with --apply")
        else:
            return None
        expected_keys = {"EPIC"} | {f"M{m['number']}" for m in self.plan["milestones"]} | {L.tag(self.plan, it["id"]) for it in self.plan["items"]}
        extra_keys = (set(MARKER_RE.findall(chosen.get("body") or "")) & expected_keys) - {key}
        if extra_keys:
            L.say(f"key | issue | conflicting managed markers\n{key} | #{chosen['number']} | {sorted(extra_keys)}")
            if self.selections.get(key) != chosen["number"]:
                raise G.GitHubError(f"{key}: issue #{chosen['number']} carries several plan identities. Which identity should it retain? Preview --select-issue {key}={chosen['number']} to retain {key} and neutralize {sorted(extra_keys)}")
            L.say(f"  #{chosen['number']}: neutralize conflicting managed markers {sorted(extra_keys)}; retain {key}")
            if self.apply:
                body = MARKER_RE.sub(lambda match: f"<!-- carrydown-duplicate:{match.group(1)}:retained-{key} -->" if match.group(1) in extra_keys else match.group(0), chosen.get("body") or "")
                self.gh.rest("PATCH", f"{self.base}/issues/{chosen['number']}", {"body": body})
                chosen["body"] = body
        self.mapping[key] = {"number": chosen["number"], "id": chosen["id"]}
        for other in candidates:
            if other["number"] == chosen["number"] or key not in MARKER_RE.findall(other.get("body") or ""):
                continue
            L.say(f"  {key}: neutralize duplicate managed marker on #{other['number']}; canonical #{chosen['number']}; comments, state and human text preserved")
            if self.apply:
                body = (other.get("body") or "").replace(marker(key), f"<!-- carrydown-duplicate:{key}:canonical-{chosen['number']} -->")
                self.gh.rest("PATCH", f"{self.base}/issues/{other['number']}", {"body": body})
                other["body"] = body
        return chosen

    def save_mapping(self):
        if self.apply and self.persist:
            doc = {"repository": f"{self.owner}/{self.repo}", "issues": self.mapping}
            if self.visibility:
                doc["visibility"] = self.visibility      # what --verify compares with, so a change is reported
            text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
            rel = self.mapping_path.relative_to(self.root.resolve()).as_posix() if self.root.resolve() in self.mapping_path.parents else str(self.mapping_path)
            RG.require("draft", rel, L.sha256_text(text), "engineering-repo", self.root)
            L.write_text(self.mapping_path, text)

    def desired_labels(self):
        return RP.desired_labels(self.plan)

    def labels(self):
        have = {l["name"].lower() for l in self.gh.paged(f"{self.base}/labels")} if self.gh else set()
        for name, color, desc in self.desired_labels():
            if name.lower() in have:
                L.say(f"  label exists: {name}")
                continue
            L.say(f"  {'create' if self.apply else 'would create'} label: {name}")
            if self.apply:
                self.gh.rest("POST", f"{self.base}/labels", {"name": name, "color": color, "description": desc})
            self.counts["labels"] += 1

    def remember(self, key, iss):
        self.objs[key] = iss
        self.numbers[key], self.ids[key] = iss["number"], iss["id"]
        self.mapping[key] = {"number": iss["number"], "id": iss["id"]}
        self.save_mapping()

    def create_or_find(self, title, body, labels, assignees, key, issue_type=""):
        """Find the issue for key, or create it. Titles printed are the plan's, never GitHub's."""
        iss = self.find(key, title)
        if iss:
            self.remember(key, iss)
            L.say(f"  exists #{iss['number']}: {title}")
            return iss, False
        L.say(f"  {'create' if self.apply else 'would create'}: {title}")
        if not self.apply:
            self.planned.add(key)
            return None, True
        if self.before_write is not None:
            self.before_write(key)
        payload = {"title": title, "body": body, "labels": labels}
        if assignees:
            payload["assignees"] = assignees
        if issue_type:
            payload["type"] = issue_type
        for attempt in (1, 2):
            try:
                iss = self.gh.rest("POST", f"{self.base}/issues", payload)
                break
            except G.GitHubError as e:
                if e.kind not in ("server", "network"):
                    raise
                # GitHub may have created the issue and lost the answer: read back before trying again
                L.say(f"    GitHub answered with an error ({e.status or e.kind}). Reading the issues back before trying again.")
                self.issues = None
                iss = self.find(key, title)
                if iss:
                    L.say(f"    found it after the error: #{iss['number']}")
                    break
                if attempt == 2:
                    raise
        for index, lookup in ((self.issues, title), (self.by_key, key)):
            rows = index.setdefault(lookup, [])
            if not any(row["id"] == iss["id"] for row in rows):
                rows.append(iss)
        self.remember(key, iss)
        self.created.add(key)
        time.sleep(0.8)
        L.say(f"    -> #{iss['number']}")
        return iss, True

    def ensure_sub(self, parent_key, child_key):
        parent, child = self.numbers.get(parent_key), self.ids.get(child_key)
        if not parent or not child:
            return
        subs = {s["number"] for s in self.gh.paged(f"{self.base}/issues/{parent}/sub_issues")}
        if self.numbers[child_key] in subs:
            return
        L.say(f"  link #{self.numbers[child_key]} under #{parent}")
        self.gh.rest("POST", f"{self.base}/issues/{parent}/sub_issues", {"sub_issue_id": child})
        self.counts["links"] += 1
        time.sleep(0.5)



# ---------------------------------------------------------------------------
# Publishing an approved release (specification D4, D5)
# ---------------------------------------------------------------------------

def release_mode(root):
    """True when the project has a handling policy or an enrollment, so GitHub writes need an approved release."""
    return not RG._is_legacy(RG.project_state(root))


def release_state(pub, s, gh, kind, key, issue):
    """The managed state of one issue-like target as read back now, and its digest."""
    import release_sync as RSY
    payload = pub.payload(kind, key)[1]
    state = RSY.issue_state(managed_content, gh, s.base, payload, issue)
    return state, RSY.managed_digest(state)


def release_expected(pub, s, kind, key):
    payload = pub.payload(kind, key)[1]
    return payload, pub.text_for(payload, s.numbers)


def release_check(pub, s, gh, skip_comment):
    """Read GitHub and compare every target with its approved payload. Returns True when all match."""
    ok = True
    L.say("\nVerification (read only)")
    labels = {x["name"].lower() for x in gh.paged(f"{s.base}/labels")}
    for (kind, key), (path, payload, sha) in sorted(pub.payloads.items()):
        if kind in ("issue", "subepic", "epic"):
            found = s.find(key, payload["title"])      # every number is known before any body is compared
            if found:
                s.remember(key, found)
    for (kind, key), (path, payload, sha) in sorted(pub.payloads.items()):
        if kind == "label":
            present = payload["name"].lower() in labels
            L.say(f"  label {payload['name']}: " + ("present" if present else "MISSING"))
            ok &= present
            continue
        if kind in ("issue", "subepic", "epic"):
            issue = s.find(key, payload["title"])
            if not issue:
                L.say(f"  MISSING {kind}: {key}")
                ok = False
                continue
            s.remember(key, issue)
            want = pub.text_for(payload, s.numbers).strip()
            have = managed_content(issue.get("body"))
            wanted_labels = {x.casefold() for x in payload["labels"]}
            has_labels = {x["name"].casefold() for x in issue.get("labels", [])}
            wanted_assignees = {x.casefold() for x in payload["assignees"]}
            has_assignees = {x["login"].casefold() for x in issue.get("assignees", [])}
            problems = []
            if issue["title"] != payload["title"]:
                problems.append("title")
            if have != want:
                problems.append("body")
            if not wanted_labels <= has_labels:
                problems.append("labels")
            if not wanted_assignees <= has_assignees:
                problems.append("assignees")
            L.say(f"  {key} #{issue['number']}: " + ("matches the approved payload" if not problems else "DIFFERS in " + ", ".join(problems)))
            ok &= not problems
    epic = s.numbers.get("EPIC")
    if ("epic-comment", "rollup") in pub.payloads and epic and not skip_comment:
        com = own_rollups(gh, s.base, epic)
        payload = pub.payloads[("epic-comment", "rollup")][1]
        want = pub.text_for(payload, s.numbers)
        good = bool(com) and com[0]["body"].replace("\r\n", "\n") == want
        L.say("  Epic roll-up comment: " + ("matches the approved payload" if good else "MISSING or different"))
        ok &= good
    L.say("verification " + ("passed" if ok else "FAILED"))
    return ok


def release_run(a, root, gh):
    """The release path of github_sync (D4, D5): payloads from the snapshot, substitutions only, a journal,
    and the release gate asked before every write. Returns an exit status, or None for a legacy project."""
    import release_sync as RSY
    try:
        pub = RSY.open_publication(root, a, gh)
    except RSY.PublicationRefused as e:
        L.say(e.line())
        return 1
    if pub is None:
        return None
    owner, repo = pub.repository.split("/", 1)
    if a.repo and a.repo.casefold() != pub.repository.casefold():
        L.say("target-identity-mismatch: --repo names another repository than the one this release approved")
        return 1
    selections = {}
    for selection in a.select_issue:
        match = re.fullmatch(r"([A-Za-z0-9_-]+)=([1-9][0-9]*)", selection)
        if not match:
            L.die("--select-issue must be KEY=NUMBER")
        selections[match[1]] = int(match[2])
    L.say("")
    L.say(f"carrydown github_sync  {'APPLY' if a.apply else 'VERIFY (read only)' if a.verify else 'DRY RUN (nothing will be written)'}  (approved release)")
    L.say(f"repository: {pub.repository} (numeric id {pub.repository_id})    request: {pub.rid}")
    pf = RSY.preflight_for(pub)          # reads only; refuses before any write
    for line in pf.lines:
        L.say(line)
    kinds = {}
    for (kind, key) in pub.payloads:
        kinds[kind] = kinds.get(kind, 0) + 1
    L.say("payloads: " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())))
    s = Sync(pub.plan, Path(root), gh, owner, repo, a.apply, selections, mapping=False)
    s.expected_hook = lambda key: with_marker(pub.text_for(pub.payload(RSY.kind_of(key), key)[1], s.numbers), key)
    RSY.install_guard(gh, root, pub, s)
    status, js = gh.rest_status("GET", s.base)
    if status == 404 or not isinstance(js, dict):
        L.say(f"repository {pub.repository} was not found, or the token cannot see it.")
        return 1
    if a.verify:
        report, changed = RSY.visibility_report(pub.journal.visibility, pf.visibility)
        for line in report:
            L.say(line)
        return 0 if release_check(pub, s, gh, a.skip_comment) and not changed else 1
    if a.apply:
        pub.journal.record_visibility(pf.visibility)
    # nothing is written until every approved login resolves and every needed label is approved or present
    for login in sorted({x for (_k, _key), (_p, payload, _s) in pub.payloads.items() for x in payload.get("assignees", [])}):
        st, _ = gh.rest_status("GET", f"/users/{login}")
        if st == 404:
            L.say("assignee-unresolved: an approved assignee login does not resolve to a GitHub user. Nothing was written.")
            return 1
    have_labels = {x["name"].lower() for x in gh.paged(f"{s.base}/labels")}
    approved_labels = {payload["name"].lower() for (k, _key), (_p, payload, _s) in pub.payloads.items() if k == "label"}
    needed = {x.lower() for (k, _key), (_p, payload, _s) in pub.payloads.items() if k in ("issue", "subepic", "epic") for x in payload["labels"]}
    absent = sorted(needed - have_labels - approved_labels)
    if absent:
        L.say(f"destination-not-allowed: {len(absent)} label(s) are neither on GitHub nor approved for creation in this release. Nothing was written.")
        return 1
    # resume: a target completed under this request must still read back as it was published
    for jkey, entry in sorted(pub.journal.targets.items()):
        if entry.get("state") != "completed":
            continue
        kind, key = jkey.split("/", 1)
        if (kind, key) not in pub.payloads or kind not in ("issue", "subepic", "epic"):
            continue
        status, issue = gh.rest_status("GET", f"{s.base}/issues/{entry.get('number')}")
        if status != 200:
            L.say(f"target changed since publication: {key}")
            return 1
        _, digest = release_state(pub, s, gh, kind, key, issue)
        if digest != entry.get("managed_state_sha256"):
            L.say(f"target changed since publication: {key}")
            return 1
    # a replacement: a target an earlier request published and nobody has edited since may be updated to the
    # new approved payload. One that was edited stops the run, as a changed completed target does.
    approved_update = set()
    others = pub.journal.others()
    for (kind, key) in sorted(pub.payloads):
        jkey = f"{kind}/{key}"
        mine = pub.journal.get(jkey)
        if kind not in ("issue", "subepic", "epic") or (mine and mine.get("state") == "completed") or not others.get(jkey):
            continue
        prior = [e for e in others[jkey] if e.get("state") == "completed" and e.get("number")]
        if not prior:
            continue
        status, issue = gh.rest_status("GET", f"{s.base}/issues/{prior[-1]['number']}")
        if status != 200:
            L.say(f"target changed since publication: {key}")
            return 1
        _, digest = release_state(pub, s, gh, kind, key, issue)
        # the earlier request's payload decides what its published state looked like, so compare against it
        if digest != prior[-1].get("managed_state_sha256"):
            L.say(f"target changed since publication: {key}")
            return 1
        approved_update.add(key)
    L.say("\nLabels")
    for (kind, key), (_p, payload, _s) in sorted(pub.payloads.items()):
        if kind != "label":
            continue
        if payload["name"].lower() in have_labels:
            L.say(f"  label exists: {payload['name']}")
            continue
        L.say(f"  {'create' if a.apply else 'would create'} label: {payload['name']}")
        if a.apply:
            gh.rest("POST", f"{s.base}/labels", {"name": payload["name"], "color": payload["color"], "description": payload["description"]})
            pub.journal.start(f"label/{key}", payload_sha256=pub.payload(kind, key)[2])
            pub.journal.complete(f"label/{key}", pub.payload(kind, key)[2], RSY.managed_digest({"name": payload["name"], "color": payload["color"], "description": payload["description"]}))
            s.counts["labels"] += 1
    order = [("epic", k) for (kd, k) in sorted(pub.payloads) if kd == "epic"] + \
            [("subepic", k) for (kd, k) in sorted(pub.payloads) if kd == "subepic"] + \
            [("issue", k) for (kd, k) in sorted(pub.payloads) if kd == "issue"]
    epic_number = pub.plan["project"].get("epic")
    if epic_number and not any(k == "epic" for k, _ in order):
        s.remember("EPIC", gh.rest("GET", f"{s.base}/issues/{epic_number}"))
    for kind, key in order:
        payload = pub.payload(kind, key)[1]
        body = with_marker(pub.text_for(payload, s.numbers), key)
        iss, new = s.create_or_find(payload["title"], body, payload["labels"], payload["assignees"], key, a.issue_type if kind == "issue" else "")
        if iss and a.apply:
            pub.journal.start(f"{kind}/{key}", github_id=iss["id"], number=iss["number"], node_id=iss.get("node_id"),
                              payload_sha256=pub.payload(kind, key)[2])
    if not a.apply:
        kinds = [kind for kind, _ in order]
        new = [kind for kind, key in order if key in s.planned]
        L.say("\nSummary")
        L.say(f"{kinds.count('epic') + (1 if epic_number and 'epic' not in kinds else 0)} Epic, {kinds.count('subepic')} sub-epics, "
              f"{kinds.count('issue')} work item issues")
        L.say(f"  to create now: {new.count('epic')} Epic, {new.count('subepic')} sub-epics, {new.count('issue')} work item issues. "
              "Already on GitHub: the rest.")
        L.say("\nDry run complete. Read it, then add --apply to write.")
        return 0
    L.say("\nLinks")
    for kind, key in order:
        parent = pub.payload(kind, key)[1].get("relationships", {}).get("parent")
        if parent and parent in s.numbers and key in s.numbers:
            s.ensure_sub(parent, key)
    L.say("\nLinking dependency ids and work item lists")
    for kind in ("subepic", "issue"):
        for k, key in order:
            if k != kind:
                continue
            payload = pub.payload(kind, key)[1]
            cur = s.objs[key]
            want = with_marker(pub.text_for(payload, s.numbers), key)
            have = (cur.get("body") or "").replace("\r\n", "\n")
            first = pub.text_for(payload, {})
            pristine = [with_marker(first, key), first, pub.text_for(payload, s.numbers)]
            if want != have and (key in s.created or key in approved_update or a.update_bodies or safe_to_rewrite(have, pristine)):
                merged = merge_managed(have, want, key)
                pub.check_sent(payload, s.numbers, managed_content(merged))
                gh.rest("PATCH", f"{s.base}/issues/{cur['number']}", {"body": merged})
                cur["body"] = merged
                s.counts["bodies"] += 1
                L.say(f"  updated {key} #{cur['number']}")
                time.sleep(0.4)
    if ("epic-comment", "rollup") in pub.payloads and "EPIC" in s.numbers and not a.skip_comment:
        L.say("\nEpic roll-up comment")
        payload = pub.payloads[("epic-comment", "rollup")][1]
        text = pub.text_for(payload, s.numbers)
        existing = own_rollups(gh, s.base, s.numbers["EPIC"])
        if existing:
            if existing[0]["body"].replace("\r\n", "\n") != text:
                gh.rest("PATCH", f"{s.base}/issues/comments/{existing[0]['id']}", {"body": text})
                L.say(f"  updated comment {existing[0]['html_url']}")
            else:
                L.say("  comment already up to date")
            comment = existing[0]
        else:
            comment = gh.rest("POST", f"{s.base}/issues/{s.numbers['EPIC']}/comments", {"body": text})
            L.say(f"  posted comment {comment['html_url']}")
        pub.journal.start("epic-comment/rollup", github_id=comment["id"], payload_sha256=pub.payloads[("epic-comment", "rollup")][2])
        pub.journal.complete("epic-comment/rollup", pub.payloads[("epic-comment", "rollup")][2], RSY.managed_digest({"body": text}))
    for kind, key in order:
        issue = gh.rest("GET", f"{s.base}/issues/{s.numbers[key]}")
        _, digest = release_state(pub, s, gh, kind, key, issue)
        pub.journal.complete(f"{kind}/{key}", pub.payload(kind, key)[2], digest)
    L.say("\nSummary")
    L.say(f"  labels created: {s.counts['labels']}, bodies rewritten: {s.counts['bodies']}, new sub-issue links: {s.counts['links']}")
    ok = release_check(pub, s, gh, a.skip_comment)
    L.say(f"Next: python3 {Path(__file__).resolve().parent / 'github_project.py'} to build the board. Then run this script with --verify.")
    return 0 if ok else 1


def preflight_command(a, root, plan):
    """--preflight: resolve the destination, print its visibility line and every refusal, write nothing."""
    import release_sync as RSY
    token = G.read_token(a.token_file, required=True)
    gh = G.GitHub(token)
    L.say("")
    L.say("carrydown github_sync  PREFLIGHT (reads only; nothing will be written)")
    if release_mode(root):
        pub = RSY.open_publication(root, a, gh)
        L.say(f"repository: {pub.repository} (numeric id {pub.repository_id})    request: {pub.rid}")
        pf = RSY.preflight_for(pub)
        for line in pf.lines:
            L.say(line)
        L.say("preflight passed: the destinations are the approved ones and their audience matches. No write was made.")
        return 0
    owner, repo = L.repo_parts(plan, a.repo)
    status, _js = gh.rest_status("GET", f"/repos/{owner}/{repo}")
    if status != 200:
        L.say(f"repository {owner}/{repo} was not found, or the token cannot see it.")
        return 1
    _vis, line = RSY.legacy_visibility(gh, f"/repos/{owner}/{repo}")
    L.say(line)
    L.say("preflight: this project has no release policy (legacy), so there is no approved audience to compare with. No write was made.")
    return 0


UNMANAGED_NOTE = ("An issue with text outside its managed region keeps that text when the managed region is replaced: replacing the region "
                  "does not remove it. Changes need a reviewed migration and approved updates. You decide, issue by issue. This report proposes no rewrite.")


def issue_inventory(s, key, issue, title, want_pristine, current_digest, completed_digest, has_release=False):
    """One line about a managed issue: pristine or edited, text outside the managed region, and whether
    its content predates the active release. It names the key, the number and fixed words only.
    has_release is True when an active release exists; completed_digest is what that release recorded
    for the issue after it published it, or None when it has not published it."""
    body = (issue.get("body") or "").replace("\r\n", "\n")
    has_region = bool(MANAGED_RE.search(body))
    if has_region:
        outside = MANAGED_RE.sub("", body, count=1)
        outside = MARKER_RE.sub("", outside).strip()
        unmanaged = bool(outside)
    else:
        unmanaged = bool(MARKER_RE.sub("", body).strip()) and not safe_to_rewrite(body, want_pristine)
    pristine = safe_to_rewrite(body, want_pristine)
    if completed_digest is None:
        age = "predates the active release (the active release has not published it)" if has_release else "predates the active release (there is no active release)"
    elif current_digest == completed_digest:
        age = "matches what the active release published"
    else:
        age = "differs from what the active release published"
    return (f"  {key} #{issue['number']}: " + ("body is pristine" if pristine else "body was edited or is older than the generator")
            + "; " + ("unmanaged text present" if unmanaged else "no text outside the managed region")
            + "; " + age + f"; body sha256 {digest(body)}"), unmanaged


def inventory_command(a, root, plan):
    """--inventory: every managed issue of the plan, read-only."""
    import release_sync as RSY
    token = G.read_token(a.token_file, required=True)
    gh = G.GitHub(token)
    L.say("")
    L.say("carrydown github_sync  INVENTORY (reads only; nothing will be written)")
    pub, why = None, ""
    if release_mode(root):
        try:
            pub = RSY.open_publication(root, a, gh)
        except RSY.PublicationRefused as e:
            why = e.code
    if pub is not None:
        plan = pub.plan
        owner, repo = pub.repository.split("/", 1)
        L.say(f"repository: {pub.repository}    active request: {pub.rid}")
    else:
        owner, repo = L.repo_parts(plan, a.repo)
        plan["project"]["repo"] = f"{owner}/{repo}"
        L.say(f"repository: {owner}/{repo}    active release: none" + (f" ({why})" if why else ""))
    status, _js = gh.rest_status("GET", f"/repos/{owner}/{repo}")
    if status != 200:
        L.say(f"repository {owner}/{repo} was not found, or the token cannot see it.")
        return 1
    root = Path(root)
    s = Sync(plan, root, gh, owner, repo, False, {}, mapping=pub is None)
    rows = []
    if not plan["project"].get("epic"):
        rows.append(("EPIC", plan["project"]["epic_title"], "epic", None))
    rows += [(f"M{m['number']}", subepic_title(plan, m), "subepic", m) for m in plan["milestones"]]
    rows += [(L.tag(plan, it["id"]), item_title(plan, it), "issue", it) for it in plan["items"]]
    issues = {}
    unmatched = {}
    for key, title, _kind, _obj in rows:
        try:
            issue = s.find(key, title)
        except G.GitHubError as e:
            unmatched[key] = str(e).split(". ")[0]       # names the key and the problem, never an issue's text
            continue
        if issue:
            s.remember(key, issue)         # every number is known before a pristine form is built
            issues[key] = issue
    found = pristine = unmanaged_count = missing = 0
    for key, title, kind, obj in rows:
        issue = issues.get(key)
        if key in unmatched:
            missing += 1
            L.say(f"  {key}: not matched to one issue ({unmatched[key]})")
            continue
        if not issue:
            if key != "EPIC":
                missing += 1
                L.say(f"  {key}: no issue found")
            continue
        found += 1
        completed = current = None
        try:
            if pub is not None and (kind, key) in pub.payloads:
                payload = pub.payloads[(kind, key)][1]
                first = pub.text_for(payload, {})
                want = [with_marker(first, key), first, pub.text_for(payload, s.numbers), with_marker(pub.text_for(payload, s.numbers), key)]
                entry = pub.journal.get(f"{kind}/{key}")
                if entry and entry.get("state") == "completed":
                    completed = entry.get("managed_state_sha256")
                    current = release_state(pub, s, gh, kind, key, issue)[1]
            elif kind == "epic":
                want = [with_marker(f"Parent Epic for {plan['project']['name']}. The sub-epics and work items are linked below as sub-issues.\n", key)]
            elif kind == "subepic":
                want = [build_subepic_body(plan, root, obj), build_subepic_body(plan, root, obj, mark=False),
                        build_subepic_body(plan, root, obj, s.numbers, mark=False), build_subepic_body(plan, root, obj, s.numbers)]
            else:
                want = [build_item_body(plan, root, obj), build_item_body(plan, root, obj, mark=False),
                        build_item_body(plan, root, obj, s.numbers, mark=False), build_item_body(plan, root, obj, s.numbers)]
        except (L.TextError, OSError, KeyError):
            want = []
        line, unmanaged = issue_inventory(s, key, issue, title, want, current, completed, has_release=pub is not None)
        pristine += safe_to_rewrite((issue.get("body") or "").replace("\r\n", "\n"), want)
        unmanaged_count += unmanaged
        L.say(line)
    L.say("")
    L.say(f"{found} managed issue(s) found, {missing} missing; {pristine} pristine; {unmanaged_count} with text outside the managed region.")
    if unmanaged_count:
        L.say(UNMANAGED_NOTE)
    L.say("Nothing was written.")
    return 0


# ---------------------------------------------------------------------------
# Engineer clarification requests (specification 9.2 and 9.3)
# ---------------------------------------------------------------------------
#
# An engineer's request is a comment on the work item issue whose first line is "Rule clarification request". The
# owner's decision is a later comment on the same issue whose first line is "Clarification disposition: accepted",
# "declined" or "deferred" and that names the request. Both are ordinary comments, so the issue conversation is the
# only record. Nothing here edits or deletes a comment, closes an issue or keeps a database. Comment text is data: it
# is matched, never followed, and it is never printed. A report names the item, the issue number, the state, the age
# and the link.

REQUEST_HEADING = "Rule clarification request"
DISPOSITION_STATES = ("accepted", "declined", "deferred")
DISPOSITION_HEADING = "Clarification disposition:"
_DISPOSITION_RE = re.compile(r"^[\W_]*clarification disposition\s*:\s*(accepted|declined|deferred)\b", re.I)
OBSERVATION_REL = "events/clarifications.json"
OBSERVATION_FORMAT = 1
NOTE_LIMIT = 500
NOT_RECORDED = "The observation was not recorded."


def first_line(body):
    """The first line of a comment that holds text, trimmed."""
    for line in (body or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip():
            return line.strip()
    return ""


def is_request(body):
    """True when the first line of a comment is the Rule clarification request heading. Leading markdown marks (a
    heading hash, bold, a quote bar) are ignored, and so is whatever follows the words after a break such as a colon."""
    text = re.sub(r"^[\s#>*_`]+", "", first_line(body)).lower()
    heading = REQUEST_HEADING.lower()
    return text.startswith(heading) and not text[len(heading):len(heading) + 1].isalnum()


def disposition_state(body):
    """accepted, declined or deferred when the first line of a comment is a clarification disposition, else None."""
    match = _DISPOSITION_RE.match(first_line(body))
    return match.group(1).lower() if match else None


def _named_comment_ids(body):
    """The comment ids a disposition names: a comment link (issuecomment-ID), or a Request line that is only an id."""
    text = (body or "").replace("\r\n", "\n")
    ids = {int(x) for x in re.findall(r"issuecomment-([0-9]{1,18})", text)}
    ids |= {int(x) for x in re.findall(r"(?im)^\s*request\s*:\s*(?:comment\s*)?#?([0-9]{1,18})\s*$", text)}
    return ids


def _quoted_lines(body):
    """The lines after the first, with a leading quote bar removed. A disposition may quote a request's heading line."""
    seen_first, out = False, set()
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        if not seen_first:
            seen_first = bool(line.strip())
            continue
        text = re.sub(r"^[\s>]+", "", line).strip()
        if text:
            out.add(text)
    return out


def _author(comment):
    """The login of a comment's author, lower case, or "" when the comment names none."""
    user = comment.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return login.casefold() if isinstance(login, str) else ""


def conversation_requests(comments, permitted=None):
    """The requests of one issue conversation, oldest first, as dicts with the request comment, its state, the
    comment that decided it and the dispositions that were ignored. A request is pending until a later disposition
    names it, by its comment id or by quoting its heading line (the quote counts only when exactly one earlier
    request has that heading line). The latest disposition that names a request is the one that applies.

    permitted is None, or the set of lower case logins whose dispositions count (the owner decides, specification
    4). With a set, a disposition written by any other account decides nothing: the request stays as it was and the
    comment is listed in the row's "unverified" list. With None every disposition counts."""
    requests = [(i, c, first_line(c.get("body"))) for i, c in enumerate(comments) if is_request(c.get("body"))]
    rows = [{"comment": c, "state": "pending", "decided": None, "unverified": []} for _i, c, _h in requests]
    for i, comment in enumerate(comments):
        state = disposition_state(comment.get("body"))
        if state is None:
            continue
        before = [k for k, (at, _c, _h) in enumerate(requests) if at < i]
        ids, quoted = _named_comment_ids(comment.get("body")), _quoted_lines(comment.get("body"))
        hits = {k for k in before if requests[k][1].get("id") in ids}
        by_heading = [k for k in before if requests[k][2] in quoted]
        if len(by_heading) == 1:
            hits.add(by_heading[0])
        counts = permitted is None or _author(comment) in permitted
        for k in hits:
            if counts:
                rows[k].update(state=state, decided=comment)
            else:
                rows[k]["unverified"].append(comment)
    return rows


UNVERIFIED = "unverified disposition by another account"


def permitted_deciders(a, plans, gh):
    """The lower case logins whose disposition comments count (the owner decides, specification 4): the login the
    plan names for the mention channel, the one person the owner chose to receive requests, and the account the
    token belongs to, read once from GitHub, because the owner runs this command with their own token. The release
    approvers of project.handling are not owners of the plan's scope and are not counted; a released plan does not
    carry them anyway. A read that fails adds nobody. Nothing is read offline: the commands that call this refuse
    --offline."""
    found = set()
    for plan in plans:
        project = (plan or {}).get("project") or {}
        block = project.get("clarification")
        if isinstance(block, dict) and block.get("channel") == "mention" and isinstance(block.get("login"), str) and RP._LOGIN_OK.match(block["login"]):
            found.add(block["login"].casefold())
    if not getattr(a, "offline", False):
        try:
            me = gh.whoami()
        except G.GitHubError:
            me = None
        login = me.get("login") if isinstance(me, dict) else None
        if isinstance(login, str) and login:
            found.add(login.casefold())
    return found


def _login_text(comment):
    """The author's login for a report line, only when it has the shape of a login."""
    user = comment.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return login if isinstance(login, str) and RP._LOGIN_OK.match(login) else "unknown"


def _comment_url(owner, repo, number, comment):
    """The link to a comment: GitHub's own html_url when it is a plain https link, else the canonical form."""
    url = str(comment.get("html_url") or "")
    if re.fullmatch(r"https://[^\s]+", url):
        return url
    return f"https://github.com/{owner}/{repo}/issues/{number}#issuecomment-{comment.get('id')}"


def _age(created, now):
    """A short age such as 2 hours or 5 days, or unknown."""
    import datetime as dt
    try:
        then = dt.datetime.strptime(str(created), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return "unknown"
    seconds = max(0, int((now - then).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    if seconds < 2 * 86400:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


def _created_at(created):
    """A comment's creation time as YYYY-MM-DDTHH:MM:SSZ in UTC, or None when GitHub gave none that can be read.
    GitHub answers in UTC with a Z; an offset such as +02:00 is converted."""
    import datetime as dt
    text = str(created or "")
    for pattern in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            when = dt.datetime.strptime(text, pattern)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def _request_item(plan, body, default):
    """The work item id a request names on its first lines, as the plan writes it, or default. Used only for a
    request on the shared clarification issue, which belongs to no one work item."""
    prefix = re.escape(str(plan["project"].get("id_prefix") or ""))
    known = {int(it["id"]) for it in plan["items"]}
    head = "\n".join((body or "").replace("\r\n", "\n").split("\n")[:12])
    for m in re.finditer(rf"\b{prefix}-0*([0-9]{{1,6}})\b", head, re.I):
        if int(m.group(1)) in known:
            return L.tag(plan, int(m.group(1)))
    return default


def clarification_scope(a, root, plan, gh):
    """(plan, owner, repo, publication, why) for a clarification command: the released plan and the approved
    repository when the project has an active release, else the working plan and its repository."""
    import release_sync as RSY
    pub, why = None, ""
    if release_mode(root):
        try:
            pub = RSY.open_publication(root, a, gh)
        except RSY.PublicationRefused as e:
            why = e.code
    if pub is not None and pub.plan is not None:
        if a.repo and a.repo.casefold() != pub.repository.casefold():
            L.die("target-identity-mismatch: --repo names another repository than the one this release approved", 1)
        owner, repo = pub.repository.split("/", 1)
        return pub.plan, owner, repo, pub, why
    owner, repo = L.repo_parts(plan, a.repo)
    plan["project"]["repo"] = f"{owner}/{repo}"
    return plan, owner, repo, None, why


def _clarification_issue(plan):
    """The number of the owner-assigned clarification issue when the plan names one, else None."""
    block = (plan.get("project") or {}).get("clarification")
    if isinstance(block, dict) and block.get("channel") == "issue":
        number = block.get("issue")
        if isinstance(number, int) and not isinstance(number, bool) and number > 0:
            return number
    return None


def write_observation(root, doc):
    """Write the observation into the private workspace, through the release gate, replacing the earlier one.
    Returns (path, "") or (None, reason) when the project has no usable workspace."""
    ws, why = L.workspace_root(root)
    if ws is None:
        return None, why
    text = json.dumps(doc, indent=2) + "\n"
    folder, path = ws / "events", ws / "events" / "clarifications.json"
    if Path(os.path.realpath(folder)) != Path(os.path.realpath(ws)) / "events" or (os.path.lexists(path) and (path.is_symlink() or not path.is_file())):
        return None, "unsafe-artifact-path"
    RG.require("candidate", OBSERVATION_REL, L.sha256_text(text), "workspace", root)
    folder.mkdir(parents=True, exist_ok=True)
    temp = folder / ".clarifications.json.tmp"
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)
    return path, ""


def clarifications_command(a, root, plan):
    """--clarifications: every Rule clarification request on the work item issues, with its state. Reads GitHub.
    With --apply it writes the observation file in the private workspace. It never writes to GitHub."""
    import datetime as dt
    token = G.read_token(a.token_file, required=True)
    gh = G.GitHub(token)
    L.say("")
    L.say("carrydown github_sync  CLARIFICATIONS (reads GitHub; nothing is written there)")
    working = plan
    plan, owner, repo, pub, why = clarification_scope(a, root, plan, gh)
    permitted = permitted_deciders(a, (plan, working), gh)
    L.say(f"repository: {owner}/{repo}    active release: " + (pub.rid if pub is not None else "none" + (f" ({why})" if why else "")))
    base = f"/repos/{owner}/{repo}"
    status, _js = gh.rest_status("GET", base)
    if status != 200:
        L.say(f"repository {owner}/{repo} was not found, or the token cannot see it.")
        return 1
    root = Path(root)
    s = Sync(plan, root, gh, owner, repo, False, {}, mapping=pub is None)
    targets, unmatched = [], []
    for it in plan["items"]:
        key = L.tag(plan, it["id"])
        try:
            issue = s.find(key, item_title(plan, it))
        except G.GitHubError as e:
            unmatched.append(key)
            L.say(f"  {key}: not matched to one issue ({str(e).split('. ')[0][:120]})")
            continue
        if issue:
            targets.append((key, issue["number"]))
    shared = _clarification_issue(plan)
    if shared is not None and all(n != shared for _k, n in targets):
        targets.append(("", shared))
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for key, number in targets:
        status, issue = gh.rest_status("GET", f"{base}/issues/{number}")
        if status != 200 or not isinstance(issue, dict) or "pull_request" in issue:
            L.say(f"  issue #{number}: not found, or not an issue; skipped")
            if not key:
                unmatched.append(f"#{number}")
            continue
        for found in conversation_requests(gh.paged(f"{base}/issues/{number}/comments"), permitted):
            c = found["comment"]
            rows.append({"issue": number, "item": key or _request_item(plan, c.get("body"), ""), "state": found["state"],
                         "url": _comment_url(owner, repo, number, c), "comment_id": int(c["id"]),
                         "created_at": _created_at(c.get("created_at")),
                         "decided_url": _comment_url(owner, repo, number, found["decided"]) if found["decided"] else None,
                         "decided_by": _login_text(found["decided"]) if found["decided"] else None,
                         "_age": _age(c.get("created_at"), now),
                         "_unverified": [(_login_text(u), _comment_url(owner, repo, number, u)) for u in found["unverified"]]})
    rows.sort(key=lambda r: (r["issue"], r["comment_id"]))
    L.say("")
    if rows:
        L.say("item | issue | state | age | link")
        for r in rows:
            L.say(f"{r['item'] or '-'} | #{r['issue']} | {r['state']} | {r['_age']} | {r['url']}")
        for r in rows:
            for who, link in r["_unverified"]:
                L.say(f"{r['item'] or '-'} | #{r['issue']} | {UNVERIFIED} ({who}): {link}. It is ignored, so the request stays {r['state']}. "
                      "The owner can decide it with --clarification-disposition.")
        counts = {st: sum(1 for r in rows if r["state"] == st) for st in ("pending",) + DISPOSITION_STATES}
        L.say(f"{len(rows)} request(s): " + ", ".join(f"{n} {st}" for st, n in counts.items()))
        if counts["pending"]:
            L.say("A pending request waits for the plan owner. Decide it, then record the decision on the issue with --clarification-disposition.")
    else:
        L.say(f"No clarification requests on {len(targets)} issue(s).")
    if unmatched:
        L.say(f"{len(unmatched)} issue(s) could not be read ({', '.join(unmatched[:6])}), so the list may be incomplete. {NOT_RECORDED}")
        return 1
    doc = {"format": OBSERVATION_FORMAT, "observed": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "repository": f"{owner}/{repo}", "requests": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]}
    if not a.apply:
        L.say("Nothing was recorded. Add --apply to save this observation in the private workspace. It writes no file in the repository and nothing on GitHub.")
        return 0
    path, why = write_observation(root, doc)
    if path is None:
        reason = "This project has no private workspace." if why in ("workspace-unavailable", "workspace-inside-repository") else f"The workspace folder is not safe to write ({why})."
        L.say(f"{NOT_RECORDED} {reason}")
        return 0
    L.say(f"Recorded the observation in the private workspace: {OBSERVATION_REL}")
    return 0


def disposition_text(state, request_url, note=""):
    """The disposition comment: its heading, the link to the request and, when the owner gave one, a short note."""
    lines = [f"{DISPOSITION_HEADING} {state}", f"Request: {request_url}"]
    if note:
        lines.append(f"Note: {note}")
    return "\n".join(lines)


def disposition_command(a, root, plan):
    """--clarification-disposition ISSUE STATE --request-comment ID: post the owner's decision on a request as a
    comment on the issue, then read it back. A dry run unless --apply. It never edits the engineer's comment."""
    raw_issue, state = a.clarification_disposition
    state = state.strip().lower()
    if state not in DISPOSITION_STATES:
        L.die(f"the state must be one of {', '.join(DISPOSITION_STATES)}, got {state[:20]!r}. A request nobody has decided is pending, and that is not posted")
    number_text = raw_issue.strip().lstrip("#")
    if not re.fullmatch(r"[1-9][0-9]{0,9}", number_text):
        L.die("the issue must be an issue number, for example 12")
    number = int(number_text)
    if a.request_comment is None:
        L.die("--request-comment is required: the id of the engineer's comment, the number after issuecomment- at the end of its link")
    note = (a.note or "").strip()
    if len(note) > NOTE_LIMIT or re.search(r"[\x00-\x1f\x7f]", note):
        L.die(f"--note must be one line of at most {NOTE_LIMIT} characters. Keep private details out of it: the comment becomes part of the issue")
    token = G.read_token(a.token_file, required=True)
    gh = G.GitHub(token)
    L.say("")
    L.say(f"carrydown github_sync  CLARIFICATION DISPOSITION  {'APPLY' if a.apply else 'DRY RUN (nothing will be posted)'}")
    working = plan
    plan, owner, repo, pub, why = clarification_scope(a, root, plan, gh)
    permitted = permitted_deciders(a, (plan, working), gh)
    base = f"/repos/{owner}/{repo}"
    L.say(f"repository: {owner}/{repo}")
    status, issue = gh.rest_status("GET", f"{base}/issues/{number}")
    if status != 200 or not isinstance(issue, dict) or "pull_request" in issue:
        L.say(f"issue #{number} was not found in {owner}/{repo}. Nothing was posted.")
        return 1
    item_keys = {L.tag(plan, it["id"]) for it in plan["items"]}
    if not (set(MARKER_RE.findall(issue.get("body") or "")) & item_keys) and number != _clarification_issue(plan):
        L.say(f"issue #{number} is neither a work item issue of this project nor its clarification issue, so nothing was posted there.")
        return 1
    found = next((r for r in conversation_requests(gh.paged(f"{base}/issues/{number}/comments"), permitted) if r["comment"].get("id") == a.request_comment), None)
    if found is None:
        L.say(f"comment {a.request_comment} on issue #{number} is not a Rule clarification request. Nothing was posted. "
              "List the requests with --clarifications, and use the number after issuecomment- at the end of the link.")
        return 1
    text = disposition_text(state, _comment_url(owner, repo, number, found["comment"]), note)
    L.say(f"request {a.request_comment} on issue #{number} reads as {found['state']} now. The comment below records it as {state}.")
    for other in found["unverified"]:
        L.say(f"{UNVERIFIED} ({_login_text(other)}): {_comment_url(owner, repo, number, other)}. It is ignored.")
    L.say("")
    for line in text.split("\n"):
        L.say("  | " + line)
    L.say("")
    if found["state"] == state:
        L.say(f"It is already recorded as {state}, so there is nothing to post.")
        return 0
    if not a.apply:
        L.say("Dry run complete. Read the comment, then add --apply to post it. The engineer's comment is not edited and the issue stays open.")
        return 0
    try:
        posted = gh.rest("POST", f"{base}/issues/{number}/comments", {"body": text})
    except G.GitHubError as e:
        if e.kind not in ("server", "network"):
            raise
        L.say(f"GitHub answered with an error ({e.status or e.kind}). Reading the comments back to see whether it was posted.")
        posted = next((c for c in gh.paged(f"{base}/issues/{number}/comments") if (c.get("body") or "").replace("\r\n", "\n") == text), None)
        if posted is None:
            raise
    row = next((r for r in conversation_requests(gh.paged(f"{base}/issues/{number}/comments"), permitted) if r["comment"].get("id") == a.request_comment), None)
    decided = row["decided"] if row else None
    if not (row and row["state"] == state and decided is not None and decided.get("id") == posted.get("id")
            and (decided.get("body") or "").replace("\r\n", "\n") == text):
        L.say(f"NOT verified: the comment was sent, but reading issue #{number} back does not show the request as {state}. "
              "Run --clarifications to see what is there before you post it again.")
        return 1
    L.say(f"Posted, and verified by reading it back: {_comment_url(owner, repo, number, posted)}")
    L.say(f"Request {a.request_comment} on issue #{number} now reads as {state}. The issue stays open.")
    return 0


def run(argv=None):
    import release_sync as RSY
    try:
        return _run(argv)
    except G.GitHubError as e:
        return G.report(e)
    except RSY.PublicationRefused as e:
        print(f"error: {e.line()}", file=sys.stderr)
        return 1


def _run(argv=None):
    ap = argparse.ArgumentParser(
        description="Create labels, sub-epics, work item issues, links and the Epic roll-up comment from plan.yaml. Dry run unless --apply.",
        epilog="The token is read from --token-file, CARRYDOWN_GITHUB_TOKEN or ~/.config/carrydown/github_token. It is never printed.",
    )
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--plan", help="path to plan.yaml (default: <root>/docs/spec/plan.yaml)")
    ap.add_argument("--repo", help="owner/name. Overrides project.repo in plan.yaml")
    ap.add_argument("--token-file", help="file that holds the GitHub token")
    ap.add_argument("--apply", action="store_true", help="write to GitHub. Without it nothing is written")
    ap.add_argument("--preflight", action="store_true", help="check the destination (visibility, identity, board readers) and exit. Writes nothing")
    ap.add_argument("--inventory", action="store_true", help="list every managed issue: pristine or not, text outside the managed region, older than the active release. Writes nothing")
    ap.add_argument("--offline", action="store_true", help="do not call GitHub at all, even to read")
    ap.add_argument("--verify", action="store_true", help="read GitHub and check that the structure matches the plan, then exit")
    ap.add_argument("--create-epic", action="store_true", help="create a parent Epic issue when project.epic is empty")
    ap.add_argument("--update-bodies", action="store_true", help="also rewrite the bodies of issues that already exist")
    ap.add_argument("--skip-comment", action="store_true", help="do not post or update the Epic roll-up comment")
    ap.add_argument("--skip-check", action="store_true", help="do not run the specification checker first")
    ap.add_argument("--people", help="path to people.yaml. Only the capacity summary in the Epic comment uses it, to say how many percent each track "
                                     "is allocated, and only when the plan allows the capacity summary. Logins are never read from it. "
                                     "Default: people.yaml in the private workspace named by .carrydown/local.yaml, when there is one")
    ap.add_argument("--issue-type", default=None, help="GitHub issue type for work items, for example Task (organizations only)")
    ap.add_argument("--show-body", metavar="ID", help="print the issue body for one work item or sub-epic and exit (no network). Accepts WI-07, 7 or M2")
    ap.add_argument("--select-issue", action="append", default=[], metavar="KEY=NUMBER", help="select a canonical issue from the ambiguity table; preview first")
    ap.add_argument("--reconcile", action="store_true", help="preview managed issue drift; add --apply to repair it and verify")
    ap.add_argument("--clarifications", action="store_true",
                    help="list the engineers' Rule clarification requests on the work item issues and their state (pending, accepted, declined or deferred). "
                         "Reads GitHub and prints no comment text. With --apply it records the observation in the private workspace, and writes nothing on GitHub")
    ap.add_argument("--clarification-disposition", nargs=2, metavar=("ISSUE", "STATE"),
                    help="record the owner's decision on a request: post a 'Clarification disposition' comment on the issue. STATE is accepted, declined or deferred. "
                         "Needs --request-comment. A dry run that prints the exact comment unless --apply, which posts it and reads it back")
    ap.add_argument("--request-comment", type=int, metavar="ID", help="with --clarification-disposition: the id of the engineer's comment, the number after issuecomment- in its link")
    ap.add_argument("--note", help="with --clarification-disposition: one short owner note, at most 500 characters on one line. It becomes part of the issue")
    a = ap.parse_args(argv)
    import release_sync as RSY
    if a.offline and (a.apply or a.verify):
        L.die(f"--offline cannot be combined with {'--apply' if a.apply else '--verify'}: both need GitHub. "
              "Leave out --offline to write or verify, or leave out the other flag for an offline dry run")
    if a.apply and a.verify:
        L.die("--apply and --verify are separate runs. Run --apply first, then --verify")
    for flag, name in ((a.preflight, "--preflight"), (a.inventory, "--inventory")):
        if flag and (a.apply or a.verify or a.offline or a.reconcile or (a.preflight and a.inventory)):
            L.die(f"{name} only reads. It cannot be combined with --apply, --verify, --offline, --reconcile or the other read-only flag")
    if a.request_comment is not None or a.note is not None:
        if not a.clarification_disposition:
            L.die("--request-comment and --note belong to --clarification-disposition ISSUE STATE")
    if a.clarifications or a.clarification_disposition:
        mixed = [name for flag, name in ((a.verify, "--verify"), (a.reconcile, "--reconcile"), (a.preflight, "--preflight"), (a.inventory, "--inventory"),
                                         (a.show_body is not None, "--show-body"), (a.create_epic, "--create-epic"), (a.update_bodies, "--update-bodies"),
                                         (a.clarifications and bool(a.clarification_disposition), "--clarifications with --clarification-disposition")) if flag]
        if mixed:
            L.die(f"{'--clarifications' if a.clarifications else '--clarification-disposition'} is its own run and cannot be combined with {mixed[0]}")
        if a.offline and a.clarifications:
            L.say("offline: nothing read from GitHub")
            return 0
        if a.offline:
            L.die("--clarification-disposition needs GitHub to read the request and to read the comment back. Leave out --offline")
    if a.issue_type is not None and not a.issue_type.strip():
        L.die("--issue-type is empty. Give the issue type, such as Task, or leave out --issue-type")
    a.issue_type = (a.issue_type or "").strip()
    if a.show_body is not None and not a.show_body.strip():
        L.die("--show-body is empty. Give a work item id such as WI-07 or 7, or M and a milestone number such as M2")

    root = L.project_root(a.root)
    plan_path = L.find_plan(root, a.plan)
    if not L.exists(plan_path):
        L.die(f"no plan at {plan_path}")
    plan, problems = L.load_plan(plan_path, root)
    if problems:
        L.say("plan.yaml has problems:")
        for p in problems:
            L.say("  - " + p)
        return 1
    if a.show_body is not None:
        # the body links the specification on GitHub, so it needs the repository, from --repo or the plan
        if a.repo is not None or not plan["project"].get("repo"):
            if a.repo is None:
                L.die("--show-body needs the repository for the links in the body. Set project.repo in plan.yaml or pass --repo owner/name")
            plan["project"]["repo"] = "/".join(L.repo_parts(plan, a.repo))
        sm = re.fullmatch(r"\s*[Mm]0*([0-9]+)\s*", str(a.show_body))
        if sm:
            ms = {m["number"]: m for m in plan["milestones"]}.get(int(sm.group(1)))
            if not ms:
                example = f"for example M{plan['milestones'][0]['number']}" if plan["milestones"] else "the plan has no milestones yet"
                L.die(f"no milestone {a.show_body}. Use M followed by the milestone number, {example}")
            L.say(build_subepic_body(plan, root, ms))
            return 0
        # the same id forms as check_specs.py --item: 7, 07, WI-07 and wi-7
        it = L.item_by_id(plan).get(L.item_number(plan, a.show_body))
        if not it:
            example = f"for example {L.tag(plan, plan['items'][0]['id'])}" if plan["items"] else "the plan has no items yet"
            L.die(f"no item with id {a.show_body}. Use the tag ({example}) or the number, or M and a milestone number")
        L.say(build_item_body(plan, root, it))
        return 0
    if a.preflight or a.inventory:
        return preflight_command(a, root, plan) if a.preflight else inventory_command(a, root, plan)
    if a.clarifications:
        return clarifications_command(a, root, plan)
    if a.clarification_disposition:
        return disposition_command(a, root, plan)
    if not a.offline and release_mode(root):
        # a project with a handling policy publishes only an approved release, from its snapshot
        token = G.read_token(a.token_file, required=a.apply or a.verify)
        if token:
            rc = release_run(a, root, G.GitHub(token))
            if rc is not None:
                return rc
        else:
            L.say("this project publishes an approved release, which needs a token to verify. Showing the plan only; nothing is read from GitHub.")
    staffed = None
    if plan["_modern"] and L.downstream_flags(plan)["capacity_summary"]:
        merged, _ = L.load_plan_with_people(plan_path, root, people_path=a.people)
        staffed = merged if merged.get("_people_overlay") else None
    if not a.skip_check:
        rc = check_specs.main(["--root", str(root), "--plan", str(plan_path), "--quiet"] + (["--people", a.people] if a.people else []))
        if rc != 0:
            L.say("The checker found problems, so nothing was sent to GitHub. Run check_specs.py to see them and fix them, then run this again.")
            return 1
    owner, repo = L.repo_parts(plan, a.repo)
    plan["project"]["repo"] = f"{owner}/{repo}"
    proj = plan["project"]
    gh = None
    unchecked = "--offline"
    if not a.offline:
        token = G.read_token(a.token_file, required=a.apply or a.verify)
        if token:
            gh = G.GitHub(token)
            import release_sync as RSY
            RSY.install_guard(gh, root)        # a legacy project: the gate is asked and answers legacy
        else:
            unchecked = "no token"
    L.say("")
    L.say(f"carrydown github_sync  {'APPLY' if a.apply else 'VERIFY (read only)' if a.verify else 'DRY RUN (nothing will be written)'}")
    plan_shown = plan_path.relative_to(root) if root in plan_path.parents else plan_path.name
    L.say(f"repository: {owner}/{repo}    plan: {plan_shown}")
    L.say(f"{len(plan['milestones'])} milestones, {len(plan['items'])} work items, {len(plan['tracks'])} tracks, {len(plan['external']['items'])} external items kept outside the plan")
    L.say("Constraints (they go into the Epic comment, and the target into every sub-epic):")
    for line in constraints_lines(plan, staffed):
        L.say("  " + line)
    if gh is None:
        L.say(f"not checked against GitHub ({unchecked}): showing the plan only, nothing is read from GitHub")
        if unchecked == "no token":
            L.say(f"To compare with what is on GitHub, set up a token: python3 {G.TOKEN_SCRIPT}")
    selections = {}
    for selection in a.select_issue:
        match = re.fullmatch(r"([A-Za-z0-9_-]+)=([1-9][0-9]*)", selection)
        if not match:
            L.die("--select-issue must be KEY=NUMBER")
        selections[match[1]] = int(match[2])
    s = Sync(plan, root, gh, owner, repo, a.apply, selections)
    s.staffed = staffed
    if gh:
        status, js = gh.rest_status("GET", s.base)
        if status == 404:
            L.say(f"repository {owner}/{repo} was not found, or the token cannot see it.")
            if a.apply or a.verify:
                return 1
            gh = s.gh = None
            unchecked = "repository not reachable"
        else:
            s.visibility, line = RSY.legacy_visibility(gh, s.base)
            L.say(line)
            if not a.apply:
                L.say("repository found. Reading existing labels and issues.")
    if a.verify:
        return verify(s, plan, root, a.skip_comment)
    if a.reconcile:
        if not gh:
            L.die("--reconcile requires GitHub read access; use --offline for the creation preview")
        return reconcile(s, plan, root, a.skip_comment)

    L.say("\nLabels")
    if gh:
        s.labels()
    else:
        for name, _, desc in s.desired_labels():
            L.say(f"  would create label if missing: {name}")

    epic = proj.get("epic")
    if epic and gh:
        e = gh.rest("GET", f"{s.base}/issues/{epic}")
        s.remember("EPIC", e)
        L.say(f"\nEpic: #{epic} (project.epic in plan.yaml)")
    elif a.create_epic and not epic:
        L.say("\nEpic")
        body = with_marker(f"Parent Epic for {proj['name']}. The sub-epics and work items are linked below as sub-issues.\n", "EPIC")
        s.create_or_find(proj["epic_title"], body, [proj["slug"]], [], "EPIC")
    elif not epic:
        L.say("\nEpic: none. Sub-epics will be created without a parent. Use --create-epic to create one.")

    L.say("\nSub-epics")
    for ms in plan["milestones"]:
        s.create_or_find(subepic_title(plan, ms), build_subepic_body(plan, root, ms), [proj["slug"], "sub-epic"], [], f"M{ms['number']}")
    L.say("\nWork items")
    for it in plan["items"]:
        t = L.tag(plan, it["id"])
        assignee = L.assignee_login(plan, it)
        s.create_or_find(item_title(plan, it), build_item_body(plan, root, it), [proj["slug"], it["track"]], [assignee] if assignee else [], t, a.issue_type)
    if not a.apply:
        n_epic = 1 if "EPIC" in s.planned else 0
        n_sub = sum(1 for k in s.planned if re.fullmatch(r"M\d+", k))
        n_it = len(s.planned) - n_epic - n_sub
        has_epic = bool(epic) or a.create_epic
        L.say("\nSummary")
        L.say(f"{1 if has_epic else 0} Epic, {len(plan['milestones'])} sub-epics, {len(plan['items'])} work item issues")
        if gh:
            L.say(f"  to create now: {n_epic} Epic, {n_sub} sub-epics, {n_it} work item issues. Already on GitHub: the rest.")
        else:
            L.say(f"  not checked against GitHub ({unchecked}), so this counts every issue as new: {n_epic} Epic, {n_sub} sub-epics, {n_it} work item issues.")
        L.say("Would then link each work item under its sub-epic" + (" and each sub-epic under the Epic" if epic or a.create_epic else "") + ",")
        L.say("rewrite dependency ids in the bodies to issue links, update the sub-epic work item lists,")
        L.say("and " + ("post" if not a.skip_comment and (epic or a.create_epic) else "skip") + " the Epic roll-up comment.")
        for it in plan["items"]:
            L.say(f"  {L.tag(plan, it['id'])}  {it['track']:<12} {it['complete_by']}  depends: {', '.join(L.tag(plan, d) for d in it['depends']) or '-'}" + (f"  external input: {it['external_input']}" if it['external_input'] else ""))
        L.say("\nDry run complete. Read it, then add --apply to write.")
        return 0

    L.say("\nLinks")
    epic_key = "EPIC" if "EPIC" in s.numbers else None
    for ms in plan["milestones"]:
        if epic_key:
            s.ensure_sub(epic_key, f"M{ms['number']}")
    for it in plan["items"]:
        s.ensure_sub(f"M{it['milestone']}", L.tag(plan, it["id"]))
    L.say("\nLinking dependency ids and work item lists")
    for ms in plan["milestones"]:
        key = f"M{ms['number']}"
        cur = s.objs[key]
        want = build_subepic_body(plan, root, ms, s.numbers)
        have = (cur.get("body") or "").replace("\r\n", "\n")
        pristine = [build_subepic_body(plan, root, ms), build_subepic_body(plan, root, ms, mark=False),
                    build_subepic_body(plan, root, ms, s.numbers, mark=False)]
        if want != have and (key in s.created or a.update_bodies or safe_to_rewrite(have, pristine)):
            merged = merge_managed(have, want, key)
            gh.rest("PATCH", f"{s.base}/issues/{cur['number']}", {"body": merged})
            cur["body"] = merged
            s.counts["bodies"] += 1
            L.say(f"  updated work item list in #{cur['number']}")
            time.sleep(0.4)
    for it in plan["items"]:
        t = L.tag(plan, it["id"])
        cur = s.objs[t]
        want = build_item_body(plan, root, it, s.numbers)
        have = (cur.get("body") or "").replace("\r\n", "\n")
        is_new = t in s.created
        pristine = [build_item_body(plan, root, it), build_item_body(plan, root, it, mark=False),
                    build_item_body(plan, root, it, s.numbers, mark=False)]
        if want != have and (is_new or a.update_bodies or safe_to_rewrite(have, pristine)):
            merged = merge_managed(have, want, t)
            gh.rest("PATCH", f"{s.base}/issues/{cur['number']}", {"body": merged})
            cur["body"] = merged
            s.counts["bodies"] += 1
            L.say(f"  linked dependencies in #{cur['number']} {t}")
            time.sleep(0.4)
    if not a.skip_comment and epic_key:
        L.say("\nEpic roll-up comment")
        num = s.numbers["EPIC"]
        text = build_rollup(plan, s.numbers, num, s.staffed)
        existing = own_rollups(gh, s.base, num)
        if existing:
            if existing[0]["body"].replace("\r\n", "\n") != text:
                gh.rest("PATCH", f"{s.base}/issues/comments/{existing[0]['id']}", {"body": text})
                L.say(f"  updated comment {existing[0]['html_url']}")
            else:
                L.say("  comment already up to date")
        else:
            c = gh.rest("POST", f"{s.base}/issues/{num}/comments", {"body": text})
            L.say(f"  posted comment {c['html_url']}")
    elif not epic_key:
        L.say("\nNo Epic, so no roll-up comment. The sub-epics hold their own work item lists.")
    L.say("\nSummary")
    L.say(f"  labels created: {s.counts['labels']}")
    sub_epic_numbers = [str(s.numbers["M%d" % m["number"]]) for m in plan["milestones"]]
    L.say("  sub-epics: #" + ", #".join(sub_epic_numbers))
    L.say(f"  work items: {len(plan['items'])} ({s.numbers[L.tag(plan, plan['items'][0]['id'])]} to {max(s.numbers[L.tag(plan, i['id'])] for i in plan['items'])})")
    L.say(f"  new sub-issue links: {s.counts['links']}, bodies rewritten: {s.counts['bodies']}")
    L.say(f"Next: python3 {Path(__file__).resolve().parent / 'github_project.py'} to build the board. Then run this script with --verify.")
    # Creation also reconciles managed metadata and verifies before claiming success.
    return reconcile(s, plan, root, a.skip_comment)


def expected_issues(s, plan, root):
    """Resolve every expected identity before generating issue links."""
    expected = []
    epic = plan["project"].get("epic")
    if epic:
        s.remember("EPIC", s.gh.rest("GET", f"{s.base}/issues/{epic}"))
    else:
        found = s.find("EPIC", plan["project"]["epic_title"])
        if found:
            s.remember("EPIC", found)
    if "EPIC" in s.objs and "EPIC" in MARKER_RE.findall(s.objs["EPIC"].get("body") or ""):
        expected.append(("EPIC", s.objs["EPIC"], None, None))
    for ms in plan["milestones"]:
        key = f"M{ms['number']}"
        issue = s.find(key, subepic_title(plan, ms))
        if issue:
            s.remember(key, issue)
        expected.append((key, issue, ms, None))
    for item in plan["items"]:
        key = L.tag(plan, item["id"])
        issue = s.find(key, item_title(plan, item))
        if issue:
            s.remember(key, issue)
        expected.append((key, issue, None, item))
    return expected


def issue_drift(s, plan, root):
    rows, problems = [], []
    expected = expected_issues(s, plan, root)
    for key, issue, ms, item in expected:
        if not issue:
            problems.append(f"{key}: issue missing; run the creation dry run")
            continue
        if key == "EPIC":
            title = plan["project"]["epic_title"]
            body = with_marker(f"Parent Epic for {plan['project']['name']}. The sub-epics and work items are linked below as sub-issues.\n", key)
        else:
            title = item_title(plan, item) if item else subepic_title(plan, ms)
            body = build_item_body(plan, root, item, s.numbers) if item else build_subepic_body(plan, root, ms, s.numbers)
        patch = {}
        differences = []
        if issue["title"] != title:
            patch["title"] = title
            differences.append(("title", title, issue["title"]))
        if managed_content(issue.get("body")) != managed_content(body) or MARKER_RE.findall(issue.get("body") or "").count(key) != 1:
            patch["body"] = merge_managed(issue.get("body"), body, key)
            differences.append(("managed body and marker", body, issue.get("body")))
        required = {plan["project"]["slug"]}
        if key != "EPIC":
            required.add(item["track"] if item else "sub-epic")
        actual = {x["name"] for x in issue.get("labels", [])}
        if not {x.casefold() for x in required} <= {x.casefold() for x in actual}:
            patch["labels"] = sorted(required | actual)
            differences.append(("required labels", sorted(required), sorted(actual)))
        wanted_login = L.assignee_login(plan, item) or None
        assigned = {x["login"] for x in issue.get("assignees", [])}
        if wanted_login and wanted_login.casefold() not in {x.casefold() for x in assigned}:
            patch["assignees"] = sorted(assigned | {wanted_login})
            differences.append(("assignee", wanted_login, sorted(assigned)))
        wanted_state = item.get("state") if item else None
        if wanted_state and issue.get("state") != wanted_state:
            patch["state"] = wanted_state
            differences.append(("state", wanted_state, issue.get("state")))
        elif issue.get("state") not in ("open", "closed"):
            problems.append(f"{key} #{issue['number']}: unexpected issue state {issue.get('state')!r}")
        parent_key = f"M{item['milestone']}" if item else "EPIC" if key != "EPIC" else None
        parent = s.objs.get(parent_key)
        status, actual_parent = s.gh.rest_status("GET", f"{s.base}/issues/{issue['number']}/parent")
        if status not in (200, 404):
            problems.append(f"{key} #{issue['number']}: cannot verify parent (HTTP {status})")
        move = parent if parent and (status != 200 or actual_parent.get("id") != parent["id"]) else None
        if move:
            differences.append(("parent", parent["number"], actual_parent.get("number") if status == 200 else None))
        for field, want, actual_value in differences:
            if field in ("parent", "state"):
                line = f"  {key} #{issue['number']} {field}: expected {want!r}, actual {actual_value!r}"
            else:
                # text from GitHub, and the plan's text it is compared with, are named by digest only
                line = f"  {key} #{issue['number']} {field}: differs (expected sha256 {digest(want)}, actual sha256 {digest(actual_value)})"
            line = G.redact(line, getattr(s.gh, "_token", None))
            line = re.sub(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,255}", "<redacted>", line)
            L.say(line)
        if patch or move:
            rows.append((key, issue, patch, move))
    return rows, problems


def reconcile(s, plan, root, skip_comment=False):
    actions, problems = issue_drift(s, plan, root)
    for problem in problems:
        L.say("  blocked: " + problem)
    L.say(f"reconciliation: {len(actions)} issue(s) with managed drift")
    if problems:
        return 1
    if not s.apply:
        return 0
    for key, issue, patch, parent in actions:
        if patch:
            s.gh.rest("PATCH", f"{s.base}/issues/{issue['number']}", patch)
        if parent:
            s.gh.rest("POST", f"{s.base}/issues/{parent['number']}/sub_issues", {"sub_issue_id": issue["id"], "replace_parent": True})
    s.save_mapping()
    s.issues = None
    # Re-read rather than trusting mutation responses, including partial failures.
    remaining, problems = issue_drift(s, plan, root)
    if remaining or problems:
        L.say("reconciliation verification FAILED; rerun the dry run to resume")
        return 1
    return verify(s, plan, root, skip_comment)


def own_rollups(gh, base, num):
    """Roll-up comments on the Epic written by the token's own account. A comment from anyone
    else is ignored, even when it carries the marker."""
    me = gh.whoami().get("login")
    return [c for c in gh.paged(f"{base}/issues/{num}/comments")
            if MARKER in (c.get("body") or "") and (c.get("user") or {}).get("login") == me]


def verify(s, plan, root, skip_comment=False):
    gh = s.gh
    L.say("\nVerification (read only)")
    ok = True
    if s.visibility:
        if s.recorded_visibility and s.recorded_visibility != s.visibility:
            L.say(f"  visibility CHANGED since the last apply: was {s.recorded_visibility}, now {s.visibility}. Reassess where this plan is published")
            ok = False
        else:
            L.say(f"  visibility: {s.visibility}" + (" (unchanged since the last apply)" if s.recorded_visibility else " (no earlier record)"))
    drift, problems = issue_drift(s, plan, root)
    for problem in problems:
        L.say("  - " + problem)
    ok &= not drift and not problems
    labels = {l["name"].lower() for l in gh.paged(f"{s.base}/labels")}
    want_labels = [n for n, _, _ in s.desired_labels()]
    miss = [n for n in want_labels if n.lower() not in labels]
    L.say(f"  labels: {len(want_labels) - len(miss)} of {len(want_labels)} present" + (f", missing {miss}" if miss else ""))
    ok &= not miss
    sub_ok = 0
    item_ok = 0
    link_total = 0
    for ms in plan["milestones"]:
        t = subepic_title(plan, ms)
        iss = s.find(f"M{ms['number']}", t)
        if not iss:
            L.say(f"  MISSING sub-epic: {t}")
            ok = False
            continue
        sub_ok += 1
        s.remember(f"M{ms['number']}", iss)
    for it in plan["items"]:
        t = item_title(plan, it)
        iss = s.find(L.tag(plan, it["id"]), t)
        if not iss:
            L.say(f"  MISSING work item: {t}")
            ok = False
            continue
        item_ok += 1
        s.remember(L.tag(plan, it["id"]), iss)
    L.say(f"  sub-epics: {sub_ok} of {len(plan['milestones'])}")
    L.say(f"  work item issues: {item_ok} of {len(plan['items'])}")
    lists_bad = 0
    for ms in plan["milestones"]:
        key = f"M{ms['number']}"
        if key not in s.numbers:
            continue
        mine = [L.tag(plan, it["id"]) for it in plan["items"] if it["milestone"] == ms["number"] and L.tag(plan, it["id"]) in s.numbers]
        subs = {x["number"] for x in gh.paged(f"{s.base}/issues/{s.numbers[key]}/sub_issues")}
        want = {s.numbers[t] for t in mine}
        link_total += len(subs & want)
        # Each expected issue's parent is checked above. Other children belong to people.
        if not subs >= want:
            L.say(f"  sub-issues of #{s.numbers[key]}: expected {sorted(want)}, found {sorted(subs)}")
            ok = False
        body = managed_content(s.objs[key].get("body"))
        unlisted = [t for t in mine if f"#{s.numbers[t]} {t}" not in body]
        if unlisted:
            lists_bad += 1
            L.say(f"  work item list of #{s.numbers[key]} lacks the issue numbers of {', '.join(unlisted)}")
    L.say(f"  sub-issue links work item to sub-epic: {link_total} of {len(plan['items'])}")
    L.say(f"  sub-epic work item lists with every issue number: {sub_ok - lists_bad} of {sub_ok}")
    ok &= lists_bad == 0
    bad = 0
    unlinked_total = 0
    for it in plan["items"]:
        key = L.tag(plan, it["id"])
        if key not in s.objs:
            continue
        body = managed_content(s.objs[key].get("body"))
        heads = [l[4:] for l in body.split("\n") if l.startswith("### ")]
        if not all(h in heads for h in SEVEN):
            bad += 1
            L.say(f"  body of #{s.numbers[key]} {key} lacks a required heading")
        unlinked = sorted(set(unlinked_ids(plan, body, s.numbers)))
        if unlinked:
            unlinked_total += 1
            L.say(f"  body of #{s.numbers[key]} {key} has unlinked ids: {', '.join(unlinked)}")
    L.say(f"  bodies with all seven headings: {item_ok - bad} of {item_ok}")
    L.say(f"  bodies with every dependency id linked: {item_ok - unlinked_total} of {item_ok}")
    ok &= bad == 0 and unlinked_total == 0
    epic = plan["project"].get("epic") or (s.find("EPIC", plan["project"]["epic_title"]) or {}).get("number")
    if epic:
        subs = {x["number"] for x in gh.paged(f"{s.base}/issues/{epic}/sub_issues")}
        want = {s.numbers[f"M{m['number']}"] for m in plan["milestones"] if f"M{m['number']}" in s.numbers}
        L.say(f"  sub-epics under Epic #{epic}: {len(subs & want)} of {len(want)}")
        ok &= subs >= want
        if skip_comment:
            # a board built with --skip-comment has no roll-up comment, so it is not asked for
            L.say("  Epic roll-up comment: not checked (--skip-comment)")
        else:
            com = own_rollups(gh, s.base, epic)
            L.say(f"  Epic roll-up comment: {'present' if com else 'missing'}")
            ok &= bool(com)
    L.say("verification " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(run())
