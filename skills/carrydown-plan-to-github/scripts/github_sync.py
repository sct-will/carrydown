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
  --apply to a public repository is refused unless you pass --allow-public.
  Text fetched from GitHub is treated as data: it is compared, never followed, and issue
  titles are printed from the plan, not from GitHub.
  The token is read from a file and is never printed.
  A migrated plan holds no logins, names or allocation. The capacity summary of the Epic comment is
  published only when project.handling.downstream.capacity_summary is true (legacy plans: true), and
  --people names the private people.yaml that supplies the allocation percent for it. No login is
  read from any file by this script for a migrated plan.

Usage
  python3 scripts/github_sync.py --root . --repo owner/name            dry run
  python3 scripts/github_sync.py --root . --repo owner/name --apply    write
  python3 scripts/github_sync.py --root . --verify                     check what exists
  python3 scripts/github_sync.py --root . --offline --show-body 3      print one issue body, no network
  python3 scripts/github_sync.py --root . --offline --show-body M2     print one sub-epic body, no network
"""
import argparse
import json
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
build_item_body = RP.build_item_body
optional_section = RP.optional_section
build_subepic_body = RP.build_subepic_body
build_rollup = RP.build_rollup


MANAGED_RE = re.compile(r"<!-- carrydown-managed:start -->\n?(.*?)\n?<!-- carrydown-managed:end -->", re.S)


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
        if mapping and self.mapping_path.exists():
            saved = json.loads(L.read_text(self.mapping_path))
            if saved.get("repository", "").casefold() != f"{owner}/{repo}".casefold():
                raise G.GitHubError("persisted issue mapping names a different repository; review github-issues.json before continuing")
            self.mapping = saved.get("issues", {})

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
                L.say("key | issue | state | marker | title | labels | assignees")
                for issue in candidates:
                    L.say(f"{key} | #{issue['number']} | {issue.get('state')} | {key in MARKER_RE.findall(issue.get('body') or '')} | {issue['title']} | {[x['name'] for x in issue.get('labels', [])]} | {[x['login'] for x in issue.get('assignees', [])]}")
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
            text = json.dumps({"repository": f"{self.owner}/{self.repo}", "issues": self.mapping}, indent=2, sort_keys=True) + "\n"
            rel = self.mapping_path.relative_to(self.root.resolve()).as_posix() if self.root.resolve() in self.mapping_path.parents else str(self.mapping_path)
            RG.require("draft", rel, L.sha256_text(text), "engineering-repo", self.root)
            L.write_text(self.mapping_path, json.dumps({"repository": f"{self.owner}/{self.repo}", "issues": self.mapping}, indent=2, sort_keys=True) + "\n")

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
        return 0 if release_check(pub, s, gh, a.skip_comment) else 1
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
        L.say("\nSummary")
        L.say(f"  to create now: {len(s.planned)} of {len(order)} issue(s). The rest are on GitHub already.")
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
            if want != have and (key in s.created or a.update_bodies or safe_to_rewrite(have, pristine)):
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
    ap.add_argument("--allow-public", action="store_true", help="allow --apply to a public repository. Issue bodies carry text from your ground truth")
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
    a = ap.parse_args(argv)
    if a.offline and (a.apply or a.verify):
        L.die(f"--offline cannot be combined with {'--apply' if a.apply else '--verify'}: both need GitHub. "
              "Leave out --offline to write or verify, or leave out the other flag for an offline dry run")
    if a.apply and a.verify:
        L.die("--apply and --verify are separate runs. Run --apply first, then --verify")
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
            public = js.get("private") is False
            if public and a.apply and not a.allow_public:
                L.die(f"{owner}/{repo} is public. Issue bodies carry text from your ground truth. Rerun with --allow-public if that is intended.")
            if not a.apply:
                L.say(f"repository found (private: {js.get('private')}). Reading existing labels and issues.")
            if public and not a.allow_public and not a.verify:
                L.say(f"note: {owner}/{repo} is public, and issue bodies carry text from your ground truth. --apply will need --allow-public.")
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
            line = f"  {key} #{issue['number']} {field}: expected {want!r}, actual {actual_value!r}"
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
