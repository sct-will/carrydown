"""A local mock of the GitHub REST endpoints that github_sync.py and github_token.py use.

It listens on 127.0.0.1 only, on a free port, and keeps everything in memory. Standard
library only. The self test uses it through tests/mock/scenarios.py. Nothing here talks to
GitHub.

Failures can be injected per (method, path regex) as a list of actions, used one per request:
  "502-after"    do the work, then answer 502 (GitHub created the issue but the answer was lost)
  "403-sso"      answer 403 with the X-GitHub-SSO header
  "403-primary"  answer 403 with X-RateLimit-Remaining: 0 (primary rate limit used up)
  "timeout"      wait longer than the client timeout, then answer
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

LOGIN = "tester"


class State:
    def __init__(self):
        self.labels, self.issues, self.subs, self.comments = [], [], {}, {}
        self.next_id = 1000
        self.private = True
        self.fail = {}
        self.log = []
        self.timeout = 3.0

    def add_issue(self, title, body="", labels=(), state="open"):
        self.next_id += 1
        iss = {"number": len(self.issues) + 1, "id": self.next_id, "node_id": f"I_{self.next_id}", "title": title,
               "body": body, "state": state, "labels": [{"name": n} for n in labels], "html_url": "u"}
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
        for (m, rx), acts in list(S.fail.items()):
            if m == method and re.fullmatch(rx, p) and acts:
                act = acts.pop(0)
                if act == "403-sso":
                    return self.send(403, {"message": "Resource protected by organization SAML enforcement. You must grant your Personal Access token access to this organization."},
                                     {"X-GitHub-SSO": "required; url=https://github.com/orgs/o/sso?authorization_request=x"})
                if act == "403-primary":
                    return self.send(403, {"message": "API rate limit exceeded for user ID 1."}, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"})
                if act == "502-after":
                    self.force = 502
                    return self._do(method, p, q)
                if act == "timeout":
                    threading.Event().wait(S.timeout)   # not time.sleep, which a test may speed up
                    return self.send(200, {})
        self._do(method, p, q)

    def _do(self, method, p, q):
        if p == "/user":
            return self.send(200, {"login": LOGIN})
        if re.fullmatch(r"/users/\w+", p):
            return self.send(200, {"type": "User", "node_id": "U_1"})
        if p == "/graphql":
            q = self.body()["query"]
            if "projectsV2(" in q:   # the project lookup: no projects yet
                return self.send(200, {"data": {"user": {"projectsV2": {"nodes": []}}}})
            return self.send(200, {"errors": [{"message": "not supported by the mock"}]})
        if re.fullmatch(r"/repos/(\w+)/(\w+)", p):
            return self.send(200, {"private": S.private, "permissions": {"push": True}, "node_id": "R_1"})
        base = r"/repos/\w+/\w+"
        if re.fullmatch(base + "/labels", p):
            if method == "GET":
                page = int(q.get("page", ["1"])[0])
                return self.send(200, S.labels[(page - 1) * 100: page * 100])
            S.labels.append(self.body())
            return self.send(201, S.labels[-1])
        if re.fullmatch(base + "/issues", p):
            if method == "GET":
                page = int(q.get("page", ["1"])[0])
                want = set(q["labels"][0].split(",")) if "labels" in q else set()
                state = q.get("state", ["open"])[0]
                items = [i for i in reversed(S.issues)
                         if want <= {lb["name"] for lb in i["labels"]} and (state == "all" or i["state"] == state)]
                return self.send(200, items[(page - 1) * 100: page * 100])
            b = self.body()
            iss = S.add_issue(b["title"], b.get("body"), b.get("labels") or [])
            return self.send(201, iss)
        m = re.fullmatch(base + r"/issues/(\d+)", p)
        if m:
            iss = S.issues[int(m.group(1)) - 1]
            if method == "PATCH":
                iss.update(self.body())
            return self.send(200, iss)
        m = re.fullmatch(base + r"/issues/(\d+)/sub_issues", p)
        if m:
            n = int(m.group(1))
            lst = S.subs.setdefault(n, [])
            if method == "GET":
                return self.send(200, [S.issues[x - 1] for x in lst])
            cid = self.body()["sub_issue_id"]
            lst.append(next(i["number"] for i in S.issues if i["id"] == cid))
            return self.send(201, S.issues[n - 1])
        m = re.fullmatch(base + r"/issues/(\d+)/comments", p)
        if m:
            n = int(m.group(1))
            if method == "GET":
                return self.send(200, S.comments.get(n, []))
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


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass   # a client that gave up on a slow answer is expected in the timeout scenario


def start():
    srv = Server(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
