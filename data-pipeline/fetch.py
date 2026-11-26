"""Polite, cached HTTP fetching for the data pipeline (standard library only).

- Every response body is cached under data-pipeline/cache/ keyed by URL, so
  reruns never re-download unless --refresh is passed to the calling script.
- At least MIN_INTERVAL seconds between network requests.
- robots.txt is checked before fetching a URL; disallowed URLs raise
  RobotsDisallowed. Hosts that answer with a bot challenge raise Blocked.
- Generic User-Agent with no personal information.
"""
import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urlparse

USER_AGENT = "Mozilla/5.0 (compatible; unime-data-pipeline/1.0; +non-commercial student project)"
MIN_INTERVAL = 1.5  # seconds between network requests
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

_last_request = 0.0


def _ssl_context():
    try:
        import certifi  # optional
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


_SSL = _ssl_context()
_robots = {}


class RobotsDisallowed(Exception):
    pass


class Blocked(Exception):
    pass


def _throttle():
    global _last_request
    wait = MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _raw_get(url, timeout=60):
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
        return resp.status, resp.read(), resp.geturl()


def robots_allows(url):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            status, body, _ = _raw_get(base + "/robots.txt", timeout=30)
            rp.parse(body.decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            # 4xx: no robots.txt -> allowed; 5xx/403 challenge -> treat as disallowed
            if e.code in (401, 403) or e.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True
        _robots[base] = rp
    return _robots[base].can_fetch(USER_AGENT, url)


def _cache_paths(url):
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return os.path.join(CACHE_DIR, h + ".body"), os.path.join(CACHE_DIR, h + ".meta.json")


def cached_meta(url):
    _, meta_path = _cache_paths(url)
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    return None


def fetch(url, refresh=False):
    """Return the body bytes for url, from cache when available."""
    body_path, meta_path = _cache_paths(url)
    if not refresh and os.path.exists(body_path):
        with open(body_path, "rb") as f:
            return f.read()
    if not robots_allows(url):
        raise RobotsDisallowed(url)
    try:
        status, body, final_url = _raw_get(url)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            raise Blocked(f"{url} -> HTTP {e.code}") from e
        raise
    if b"<title>Just a moment...</title>" in body[:2000]:
        raise Blocked(f"{url} -> bot challenge page")
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(body_path, "wb") as f:
        f.write(body)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"url": url, "final_url": final_url, "status": status,
                   "retrieved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "bytes": len(body)}, f, indent=1)
    return body
