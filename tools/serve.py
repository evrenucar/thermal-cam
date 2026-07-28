#!/usr/bin/env python3
"""Local server for thermal-cam: docs, tools, and a drop box for your ideas.

    python3 tools/serve.py [port]        # default 8765

Serves the whole repo, so every page is reachable from one origin:

    /docs/index.html      project home
    /docs/emulator.html   the emulator
    /docs/status.html     live status board
    /tools/grill.html     design questions
    /tools/overview.html  code review

Endpoints:
    POST /save    -> tools/answers/<form>-<stamp>.json   (grill answers)
    POST /inbox   -> appends to tools/INBOX.md           (ideas, tasks, feedback)

The inbox is fire-and-forget: it appends and returns immediately. Nothing you
send interrupts work in progress -- it queues up to be read at the next
checkpoint.

Attachments arrive as data: URIs and are decoded to real files, so images can be
opened rather than read as base64.

Stdlib only, on purpose: this runs on a Pi with nothing installed.
"""

import base64
import http.server
import json
import re
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
ANSWERS = TOOLS / "answers"
INBOX = TOOLS / "INBOX.md"

MAX_BODY = 64 * 1024 * 1024

SAFE = re.compile(r"[^A-Za-z0-9_-]")            # form stem: no dots at all
SAFE_FILE = re.compile(r"[^A-Za-z0-9._-]")      # attachment: keep the extension
DATA_URI = re.compile(r"^data:([\w.+-]+/[\w.+-]+);base64,(.*)$", re.S)

EXT = {
    "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
    "image/webp": "webp", "image/svg+xml": "svg", "application/pdf": "pdf",
    "text/plain": "txt",
}


def save_attachments(payload, stem, outdir):
    """Replace data: URIs in payload with written-out filenames. Returns count."""
    written = 0
    outdir.mkdir(exist_ok=True)
    for answer in payload.get("answers", []):
        for att in answer.get("attachments", []):
            m = DATA_URI.match(att.get("data", "") or "")
            if not m:
                continue
            mime, b64 = m.group(1), m.group(2)
            try:
                blob = base64.b64decode(b64)
            except (ValueError, TypeError):
                continue
            written += 1
            # Keep the extension readable, but never let ".." or a slash through.
            name = SAFE_FILE.sub("_", att.get("name") or "").lstrip(".")
            name = name or "paste-%d" % written
            if "." not in name:
                name = "%s.%s" % (name, EXT.get(mime, "bin"))
            out = outdir / ("%s-%02d-%s" % (stem, written, name))
            out.write_bytes(blob)
            att["data"] = None          # keep the JSON readable
            att["file"] = out.name
            att["bytes"] = len(blob)
    return written


class Server(http.server.ThreadingHTTPServer):
    # HTTPServer defaults this to 1. On Windows SO_REUSEADDR lets a second
    # process bind a port that is already in use -- so two servers sit on the
    # same port and you cannot tell which one answered. That turns "stale server
    # from another folder" into a silent wrong-files bug. Refuse instead.
    allow_reuse_address = False


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")   # status.json must not go stale
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if self.path.endswith((".json", ".html", ".js")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"ok": False, "error": "body must be 1..%d bytes" % MAX_BODY})
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json(400, {"ok": False, "error": "bad JSON: %s" % e})
            return None
        if not isinstance(payload, dict):
            self._json(400, {"ok": False, "error": "expected a JSON object"})
            return None
        return payload

    # ---- POST /inbox : ideas, tasks, feedback -----------------------------
    def do_inbox(self, payload):
        text = str(payload.get("text", "")).strip()
        kind = SAFE.sub("", str(payload.get("kind", "note"))) or "note"
        if not text and not payload.get("answers"):
            self._json(400, {"ok": False, "error": "empty"})
            return

        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        stem = "inbox-" + time.strftime("%Y%m%d-%H%M%S")
        n = save_attachments(payload, stem, ANSWERS)

        files = [a.get("file") for ans in payload.get("answers", [])
                 for a in ans.get("attachments", []) if a.get("file")]

        entry = ["", "## %s  ·  %s" % (stamp, kind), "", text or "_(attachment only)_"]
        if files:
            entry += ["", "Attached: " + ", ".join("`tools/answers/%s`" % f for f in files)]
        entry += ["", "- [ ] unread", ""]

        try:
            new = not INBOX.exists()
            with INBOX.open("a", encoding="utf-8") as f:
                if new:
                    f.write("# Inbox\n\nIdeas, tasks and feedback dropped from the "
                            "browser. Newest at the bottom.\n")
                f.write("\n".join(entry) + "\n")
        except OSError as e:
            self._json(500, {"ok": False, "error": "write failed: %s" % e})
            return

        print("  INBOX [%s] %s%s" % (kind, text[:70].replace("\n", " "),
                                     " (+%d file%s)" % (n, "s" * (n != 1)) if n else ""))
        self._json(200, {"ok": True, "path": "tools/INBOX.md", "attachments": n})

    # ---- POST /save : grill answers ---------------------------------------
    def do_save(self, payload):
        ANSWERS.mkdir(exist_ok=True)
        form = SAFE.sub("", str(payload.get("form", "answers"))) or "answers"
        stem = "%s-%s" % (form, time.strftime("%Y%m%d-%H%M%S"))
        try:
            n = save_attachments(payload, stem, ANSWERS)
            path = ANSWERS / (stem + ".json")
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            self._json(500, {"ok": False, "error": "write failed: %s" % e})
            return
        rel = path.relative_to(ROOT).as_posix()
        print("  saved %s%s" % (rel, " (+%d attachment%s)" % (n, "s" * (n != 1)) if n else ""))
        self._json(200, {"ok": True, "path": rel, "attachments": n})

    def do_POST(self):
        route = {"/save": self.do_save, "/inbox": self.do_inbox}.get(self.path)
        if not route:
            self._json(404, {"ok": False, "error": "no such endpoint"})
            return
        payload = self._body()
        if payload is not None:
            route(payload)

    def log_message(self, fmt, *args):
        if args and "POST" in str(args[0]):
            sys.stderr.write("  %s\n" % (fmt % args))


def main():
    port = 8765
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            sys.exit("usage: %s [port]" % sys.argv[0])

    # This machine runs several agents and dev servers at once. Rather than die
    # on a taken port -- or worse, leave someone else's stale server on the port
    # you expected -- walk up until we own one outright.
    srv, wanted = None, port
    for candidate in range(port, port + 20):
        try:
            srv = Server(("127.0.0.1", candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if srv is None:
        sys.exit("ports %d-%d are all taken; pass a free one" % (wanted, wanted + 19))

    if port != wanted:
        print("  note: %d was taken by something else, using %d" % (wanted, port))

    base = "http://127.0.0.1:%d" % port
    print("thermal-cam server -> %s/" % base)
    for rel in ["docs/index.html", "docs/emulator.html", "docs/status.html",
                "tools/grill.html", "tools/overview.html"]:
        if (ROOT / rel).exists():
            print("    %s/%s" % (base, rel))
    print("  serving  %s" % ROOT)          # so a stale server from elsewhere is obvious
    print("  inbox    %s" % INBOX)
    print("  ctrl-c to stop\n")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
