"""Local HTTP fetch for the hub 'Preview' panel.

The hub reverse-proxies a dev server / rendered report running on THIS machine
(`http://127.0.0.1:<port>`) so you can see it in the browser. This is the agent
side: fetch a localhost URL and return the response. Scoped to loopback only
(no SSRF to other hosts) and opt-in on the relay (`--allow-preview`).
"""
from __future__ import annotations

import base64
import urllib.error
import urllib.request

_MAX = 10 * 1024 * 1024                                  # 10 MB cap per response


def fetch(port, path: str = "/", method: str = "GET",
          headers: dict | None = None, body_b64: str | None = None) -> dict:
    port = int(port)
    if not (1 <= port <= 65535):
        raise ValueError("port out of range")
    if not path.startswith("/"):
        path = "/" + path
    url = "http://127.0.0.1:%d%s" % (port, path)         # loopback only
    data = base64.b64decode(body_b64) if body_b64 else None
    req = urllib.request.Request(url, data=data, method=(method or "GET").upper())
    for k, v in (headers or {}).items():
        if k.lower() in ("host", "content-length", "connection", "accept-encoding"):
            continue
        try:
            req.add_header(k, v)
        except Exception:
            pass
    try:
        with urllib.request.urlopen(req, timeout=20) as r:   # noqa: S310 (loopback only)
            body = r.read(_MAX + 1)
            status = getattr(r, "status", 200)
            ctype = r.headers.get("Content-Type", "application/octet-stream")
    except urllib.error.HTTPError as e:
        body = e.read(_MAX + 1)
        status = e.code
        ctype = e.headers.get("Content-Type", "text/plain")
    except Exception as e:
        msg = ("Preview can't reach localhost:%d — is the server running?\n%s" % (port, e)).encode()
        return {"status": 502, "ctype": "text/plain; charset=utf-8",
                "body_b64": base64.b64encode(msg).decode("ascii")}
    if len(body) > _MAX:
        body = body[:_MAX]
    return {"status": status, "ctype": ctype, "body_b64": base64.b64encode(body).decode("ascii")}
