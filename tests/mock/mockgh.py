"""A local mock of the GitHub REST and GraphQL endpoints that the carrydown GitHub scripts use.

It listens on 127.0.0.1 only, on a free port, and keeps everything in memory. Standard
library only. The self test uses it through tests/mock/scenarios.py. Nothing here talks to
GitHub.

What it serves
  REST     /user, /users/<login>, /repos/<owner>/<name> and its labels, issues, sub-issues and
           comments. Owner and repository names may hold letters, digits, "-", "_" and ".".
           Only repositories in S.repos exist; any other answers 404, as GitHub does.
           A label that exists already answers 422. An issue keeps its type.
  GraphQL  enough of Projects (v2) for github_project.py: the project lookup for a user or an
           organization, createProjectV2, linkProjectV2ToRepository, the fields and views query,
           createProjectV2Field, updateProjectV2Field, createProjectV2View, updateProjectV2View,
           the items query, addProjectV2ItemById and updateProjectV2ItemFieldValue. S.gql lists
           the operation of each GraphQL call, so a test can count the writes.

Lists (labels, issues, sub-issues, comments) are paged as GitHub pages them: per_page items a
page, and a Link header that names the next and the last page while there are more. S.link_base
sets the address written into the Link header, so a test can check that only the page number
is taken from it.

Failures can be injected per (method, path regex) as a list of actions, used one per request:
  "502-after"     do the work, then answer 502 (GitHub created the issue but the answer was lost)
  "502"           answer 502 without doing the work
  "401"           answer 401 Bad credentials
  "403-sso"       answer 403 with the X-GitHub-SSO header
  "403-primary"   answer 403 with X-RateLimit-Remaining: 0 (primary rate limit used up)
  "429-primary"   answer 429 with X-RateLimit-Remaining: 0
  "403-secondary" answer 403 "You have exceeded a secondary rate limit" with Retry-After: 1
  "429"           answer 429 Too Many Requests with Retry-After: 1 (a secondary limit)
  "timeout"       wait longer than the client timeout, then answer
  "200-html"      answer 200 with an HTML page, as a captive portal or a proxy does
None in the list lets that request through.
S.redirect maps (method, path regex) to a Location, answered with 302, to test redirects.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

LOGIN = "tester"
NAME = r"[A-Za-z0-9_.-]+"


class State:
    def __init__(self):
        self.labels, self.issues, self.subs, self.comments = [], [], {}, {}
        self.next_id = 1000
        self.private = True
        self.repos = {"o/r"}   # the repositories that exist; any other answers 404
        self.orgs = set()       # logins that are organizations; any other login is a user
        self.fail = {}
        self.redirect = {}
        self.log = []
        self.auth = []   # the Authorization header of each request, so a test can see which token was sent
        self.timeout = 3.0
        self.projects = []
        self.gql = []
        self.seq = 0
        self.link_base = None   # the address in Link headers; None means this server

    def nid(self, prefix):
        self.seq += 1
        return f"{prefix}_{self.seq}"

    def add_issue(self, title, body="", labels=(), state="open", issue_type=None):
        self.next_id += 1
        iss = {"number": len(self.issues) + 1, "id": self.next_id, "node_id": f"I_{self.next_id}", "title": title,
               "body": body, "state": state, "labels": [{"name": n} for n in labels], "html_url": "u"}
        if issue_type:
            iss["type"] = {"name": issue_type}
        self.issues.append(iss)
        return iss

    def add_comment(self, number, body, login=LOGIN):
        lst = self.comments.setdefault(number, [])
        c = {"id": 5000 + sum(len(v) for v in self.comments.values()), "body": body, "html_url": "c", "user": {"login": login}}
        lst.append(c)
        return c


S = State()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj=None, headers=None):
        if getattr(self, "force", None):
            code, obj = self.force, {"message": "Server Error"}
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-OAuth-Scopes", "repo, project")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null")

    def handle_any(self, method):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        S.log.append((method, p))
        S.auth.append(self.headers.get("Authorization", ""))
        for (m, rx), where in list(S.redirect.items()):
            if m == method and re.fullmatch(rx, p):
                self.send_response(302)
                self.send_header("Location", where)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        for (m, rx), acts in list(S.fail.items()):
            if m == method and re.fullmatch(rx, p) and acts:
                act = acts.pop(0)
                if act == "403-sso":
                    return self.send(403, {"message": "Resource protected by organization SAML enforcement. You must grant your Personal Access token access to this organization."},
                                     {"X-GitHub-SSO": "required; url=https://github.com/orgs/o/sso?authorization_request=x"})
                if act == "403-primary":
                    return self.send(403, {"message": "API rate limit exceeded for user ID 1."}, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"})
                if act == "429-primary":
                    return self.send(429, {"message": "API rate limit exceeded for user ID 1."}, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"})
                if act == "403-secondary":
                    return self.send(403, {"message": "You have exceeded a secondary rate limit. Please wait a few minutes before you try again."},
                                     {"Retry-After": "1", "X-RateLimit-Remaining": "4000"})
                if act == "429":
                    return self.send(429, {"message": "Too Many Requests"}, {"Retry-After": "1"})
                if act == "401":
                    return self.send(401, {"message": "Bad credentials"})
                if act == "502":
                    return self.send(502, {"message": "Server Error"})
                if act == "200-html":
                    page = b"<html><body>Sign in to the network</body></html>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(page)))
                    self.end_headers()
                    return self.wfile.write(page)
                if act == "502-after":
                    self.force = 502
                    return self._do(method, p, q)
                if act == "timeout":
                    threading.Event().wait(S.timeout)   # not time.sleep, which a test may speed up
                    return self.send(200, {})
        self._do(method, p, q)

    def page(self, items, q, path):
        """One page of a list, with the Link header GitHub sends while more pages follow."""
        per = max(1, min(100, int(q.get("per_page", ["30"])[0])))
        page = max(1, int(q.get("page", ["1"])[0]))
        last = max(1, -(-len(items) // per))
        headers = {}
        if page < last:
            base = (S.link_base or f"http://{self.headers.get('Host')}") + path
            keep = "".join(f"&{k}={v[0]}" for k, v in q.items() if k not in ("page", "per_page"))
            headers["Link"] = (f'<{base}?per_page={per}{keep}&page={page + 1}>; rel="next", '
                               f'<{base}?per_page={per}{keep}&page={last}>; rel="last"')
        return self.send(200, items[(page - 1) * per: page * per], headers)

    def _do(self, method, p, q):
        if p == "/user":
            return self.send(200, {"login": LOGIN})
        m = re.fullmatch(rf"/users/({NAME})", p)
        if m:
            org = m.group(1) in S.orgs
            return self.send(200, {"login": m.group(1), "type": "Organization" if org else "User", "node_id": "O_1" if org else "U_1"})
        if p == "/graphql":
            b = self.body()
            return self.send(200, graphql(b.get("query") or "", b.get("variables") or {}))
        m = re.match(rf"/repos/({NAME})/({NAME})(/|$)", p)
        if m and f"{m.group(1)}/{m.group(2)}" not in S.repos:
            return self.send(404, {"message": "Not Found"})
        if re.fullmatch(rf"/repos/{NAME}/{NAME}", p):
            return self.send(200, {"private": S.private, "permissions": {"push": True}, "node_id": "R_1"})
        base = rf"/repos/{NAME}/{NAME}"
        if re.fullmatch(base + "/labels", p):
            if method == "GET":
                return self.page(S.labels, q, p)
            b = self.body()
            if any(lb["name"].lower() == str(b.get("name", "")).lower() for lb in S.labels):
                return self.send(422, {"message": "Validation Failed", "errors": [{"resource": "Label", "code": "already_exists", "field": "name"}]})
            S.labels.append(b)
            return self.send(201, S.labels[-1])
        if re.fullmatch(base + "/issues", p):
            if method == "GET":
                want = set(q["labels"][0].split(",")) if "labels" in q else set()
                state = q.get("state", ["open"])[0]
                items = [i for i in reversed(S.issues)
                         if want <= {lb["name"] for lb in i["labels"]} and (state == "all" or i["state"] == state)]
                return self.page(items, q, p)
            b = self.body()
            iss = S.add_issue(b["title"], b.get("body"), b.get("labels") or [], issue_type=b.get("type"))
            return self.send(201, iss)
        m = re.fullmatch(base + r"/issues/(\d+)", p)
        if m:
            if not 1 <= int(m.group(1)) <= len(S.issues):
                return self.send(404, {"message": "Not Found"})
            iss = S.issues[int(m.group(1)) - 1]
            if method == "PATCH":
                iss.update(self.body())
            return self.send(200, iss)
        m = re.fullmatch(base + r"/issues/(\d+)/sub_issues", p)
        if m:
            n = int(m.group(1))
            lst = S.subs.setdefault(n, [])
            if method == "GET":
                return self.page([S.issues[x - 1] for x in lst], q, p)
            cid = self.body()["sub_issue_id"]
            lst.append(next(i["number"] for i in S.issues if i["id"] == cid))
            return self.send(201, S.issues[n - 1])
        m = re.fullmatch(base + r"/issues/(\d+)/comments", p)
        if m:
            n = int(m.group(1))
            if method == "GET":
                return self.page(S.comments.get(n, []), q, p)
            return self.send(201, S.add_comment(n, self.body()["body"]))
        m = re.fullmatch(base + r"/issues/comments/(\d+)", p)
        if m:
            cid = int(m.group(1))
            c = next((c for lst in S.comments.values() for c in lst if c["id"] == cid), None)
            if c is None:
                return self.send(404, {"message": "Not Found"})
            if method == "PATCH":
                c["body"] = self.body()["body"]
            return self.send(200, c)
        return self.send(404, {"message": "Not Found"})

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PATCH(self):
        self.handle_any("PATCH")


# ---------------------------------------------------------------------------
# GraphQL: Projects (v2)
# ---------------------------------------------------------------------------

MUTATIONS = ("createProjectV2Field", "updateProjectV2Field", "createProjectV2View", "updateProjectV2View",
             "createProjectV2", "linkProjectV2ToRepository", "addProjectV2ItemById", "updateProjectV2ItemFieldValue")


def _project(pid):
    return next((x for x in S.projects if x["id"] == pid), None)


def _public(pr):
    return {"id": pr["id"], "title": pr["title"], "number": pr["number"], "url": pr["url"], "closed": pr["closed"]}


def _view_out(v):
    return {"id": v["id"], "name": v["name"], "number": v["number"], "layout": v["layout"], "filter": "",
            "groupByFields": {"nodes": []}, "fields": {"nodes": [{"id": f} for f in v["visible"]]}}


def add_project(title, owner=LOGIN, closed=False):
    """A project with the fields and the view GitHub gives a new one."""
    n = len(S.projects) + 1
    pr = {"id": S.nid("PVT"), "title": title, "number": n, "url": f"https://github.com/users/{owner}/projects/{n}", "closed": closed,
          "fields": [{"id": S.nid("F"), "name": "Title", "dataType": "TITLE"}, {"id": S.nid("F"), "name": "Assignees", "dataType": "ASSIGNEES"},
                     {"id": S.nid("F"), "name": "Status", "dataType": "SINGLE_SELECT", "options": [{"id": S.nid("O"), "name": "Todo"}]}],
          "views": [{"id": S.nid("V"), "name": "View 1", "number": 1, "layout": "TABLE_LAYOUT", "visible": []}],
          "items": []}
    pr["views"][0]["visible"] = [pr["fields"][0]["id"]]
    S.projects.append(pr)
    return pr


def _iterations(cfg):
    return [{"id": S.nid("IT"), "title": i["title"], "startDate": i["startDate"], "duration": i["duration"]} for i in cfg["iterations"]]


def graphql(query, v):
    def ok(data):
        return {"data": data}
    op = next((m for m in MUTATIONS if re.search(r"\b" + m + r"\(", query)), None)
    S.gql.append(op or ("projects" if "projectsV2(" in query else "items" if "items(first:" in query else "fields" if "fields(first:" in query else "other"))
    if op is None and "projectsV2(" in query:
        root = "organization" if "organization(" in query else "user"
        return ok({root: {"projectsV2": {"nodes": [_public(x) for x in S.projects]}}})
    if op is None and "items(first:" in query:
        pr = _project(v.get("p"))
        if pr is None:
            return {"errors": [{"message": "Could not resolve to a node"}]}
        names = {f["id"]: f["name"] for f in pr["fields"]}
        nodes = []
        for it in pr["items"]:
            vals = []
            for fid, val in it["values"].items():
                (k, x), = val.items()
                vals.append({{"iterationId": "iterationId", "singleSelectOptionId": "optionId", "date": "date"}[k]: x, "field": {"name": names[fid]}})
            nodes.append({"id": it["id"], "content": {"number": it["number"]}, "fieldValues": {"nodes": vals}})
        return ok({"node": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": nodes}}})
    if op is None and "fields(first:" in query:
        pr = _project(v.get("p"))
        if pr is None:
            return {"errors": [{"message": "Could not resolve to a node"}]}
        return ok({"node": dict(_public(pr), fields={"nodes": pr["fields"]}, views={"nodes": [_view_out(x) for x in pr["views"]]})})
    if op == "createProjectV2":
        return ok({op: {"projectV2": _public(add_project(v["t"]))}})
    if op == "linkProjectV2ToRepository":
        return ok({op: {"repository": {"id": v.get("r")}}})
    if op == "createProjectV2Field":
        pr = _project(v["p"])
        kind = re.search(r"dataType: (\w+)", query).group(1)
        name = re.search(r'name: "([^"]+)"', query)
        f = {"id": S.nid("F"), "name": name.group(1) if name else v["n"], "dataType": kind}
        if kind == "ITERATION":
            f["configuration"] = {"iterations": _iterations(v["c"]), "completedIterations": []}
        if kind == "SINGLE_SELECT":
            f["options"] = [{"id": S.nid("O"), "name": o["name"]} for o in v["o"]]
        pr["fields"].append(f)
        return ok({op: {"projectV2Field": {"id": f["id"]}}})
    if op == "updateProjectV2Field":
        f = next(f for pr in S.projects for f in pr["fields"] if f["id"] == v["f"])
        f["configuration"] = {"iterations": _iterations(v["c"]), "completedIterations": []}
        return ok({op: {"projectV2Field": {"id": f["id"]}}})
    if op == "createProjectV2View":
        pr = _project(v["p"])
        view = {"id": S.nid("V"), "name": v["n"], "number": len(pr["views"]) + 1, "layout": v["l"], "visible": []}
        pr["views"].append(view)
        return ok({op: {"projectV2View": {"id": view["id"], "name": view["name"], "layout": view["layout"]}}})
    if op == "updateProjectV2View":
        view = next(x for pr in S.projects for x in pr["views"] if x["id"] == v["v"])
        if "n" in v:
            view["name"] = v["n"]
        if "f" in v:
            view["visible"] = list(v["f"])
        return ok({op: {"projectV2View": {"id": view["id"]}}})
    if op == "addProjectV2ItemById":
        pr = _project(v["p"])
        iss = next(i for i in S.issues if i["node_id"] == v["c"])
        item = {"id": S.nid("PVTI"), "number": iss["number"], "values": {}}
        pr["items"].append(item)
        return ok({op: {"item": {"id": item["id"]}}})
    if op == "updateProjectV2ItemFieldValue":
        pr = _project(v["p"])
        item = next(i for i in pr["items"] if i["id"] == v["i"])
        item["values"][v["f"]] = dict(v["v"])
        return ok({op: {"projectV2Item": {"id": item["id"]}}})
    return {"errors": [{"message": "not supported by the mock"}]}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass   # a client that gave up on a slow answer is expected in the timeout scenario


def start():
    srv = Server(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
