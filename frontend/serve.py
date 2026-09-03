"""Static file server for the FlowMatch frontend (no build step, no Node.js -
docs/DECISIONS.md #2). Same pattern as app/frontend/serve.py."""

import functools
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5600
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIRECTORY)

if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler) as httpd:
        print("Serving FlowMatch frontend at http://127.0.0.1:{}".format(PORT))
        httpd.serve_forever()
