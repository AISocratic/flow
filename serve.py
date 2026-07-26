#!/usr/bin/env python3
"""Dev server for flow.html: watches src/, reruns build.sh, live-reloads the browser.

Usage: ./serve.py [port]   (default 8000)
"""
import http.server
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
OUT = "flow.html"

version = 0
lock = threading.Lock()

RELOAD_JS = b"""
<script>
(function () {
  var cur = null;
  setInterval(function () {
    fetch('/__version', {cache: 'no-store'}).then(function (r) { return r.text(); })
      .then(function (v) {
        if (cur === null) { cur = v; return; }
        if (v !== cur) location.reload();
      }).catch(function () {});
  }, 500);
})();
</script>
"""


def snapshot():
    """Map of src file -> mtime."""
    out = {}
    for dirpath, _, files in os.walk(os.path.join(ROOT, "src")):
        for f in files:
            p = os.path.join(dirpath, f)
            try:
                out[p] = os.path.getmtime(p)
            except OSError:
                pass
    return out


def build():
    r = subprocess.run(["./build.sh"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("build failed:\n" + r.stderr, flush=True)
        return False
    print(r.stdout.strip(), flush=True)
    return True


def watch():
    global version
    prev = snapshot()
    while True:
        time.sleep(0.4)
        cur = snapshot()
        if cur != prev:
            prev = cur
            if build():
                with lock:
                    version += 1


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        if self.path.split("?")[0] == "/__version":
            with lock:
                body = str(version).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.split("?")[0] in ("/", "/" + OUT):
            try:
                with open(os.path.join(ROOT, OUT), "rb") as fh:
                    body = fh.read()
            except OSError:
                self.send_error(404, "%s not built yet" % OUT)
                return
            body = body + RELOAD_JS
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        super().do_GET()

    def log_message(self, fmt, *args):
        # quiet the poll: it fires twice a second and would bury real requests
        if "__version" not in " ".join(str(a) for a in args):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    build()
    threading.Thread(target=watch, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("serving http://127.0.0.1:%d  (watching src/)" % PORT, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
