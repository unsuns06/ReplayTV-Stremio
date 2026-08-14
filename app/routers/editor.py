"""The programs.json editor, served as the addon's homepage.

These routes write to programs.json, so they answer to loopback only — a
deployed instance still gets the plain JSON greeting at ``/``.  Set
``enable_remote_editor`` to lift that if you know what you are exposing
(lower-case: Hugging Face Spaces reject capitals in variable names, and
os.getenv is case-sensitive everywhere except Windows).

The catalogue endpoints exist because a browser cannot call the provider APIs
itself: none of them send CORS headers.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List

import requests
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)
router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROGRAMS = PROJECT_ROOT / "programs.json"
EDITOR_PAGE = PROJECT_ROOT / "app" / "static" / "editor.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _is_local(request: Request) -> bool:
    if os.getenv("enable_remote_editor"):
        return True
    return bool(request.client) and request.client.host in LOOPBACK


def get(url: str, params: Dict = None, headers: Dict = None) -> Dict:
    response = requests.get(url, params=params, timeout=45,
                            headers={"User-Agent": UA, **(headers or {})})
    response.raise_for_status()
    return response.json()


def parallel(fn, items) -> List:
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(fn, items))


# ---------------------------------------------------------------------------
# One "every show this provider offers" reader per provider.  Each returns
# {slug, name, channel} rows whose slug is what the addon will put in
# programs.json — the provider's own identifier, never a display name.
# ---------------------------------------------------------------------------

def catalogue_6play() -> Dict[str, Dict]:
    """6play only lists programs one initial letter at a time ('@' = digits)."""
    url = ("https://android.middleware.6play.fr/6play/v2/platforms/"
           "m6group_androidmob/services/6play/programs")
    pages = parallel(
        lambda letter: get(url, {"limit": 999, "offset": 0, "csa": 6,
                                 "firstLetter": letter, "with": "rights"},
                           {"x-customer-name": "m6web"}),
        ["@", *"abcdefghijklmnopqrstuvwxyz"],
    )
    return {program["code"]: {"slug": program["code"],
                              "name": program.get("title", ""), "channel": ""}
            for page in pages for program in page if program.get("code")}


# The same lists app/providers/fr/mytf1.py searches, so the editor can only
# offer shows the addon is able to resolve.  TF1 has 4471 programs and pages
# 500 at a time, and its only filter is the channel.
TF1_LISTS = (None, "tf1", "tmc", "tfx", "tf1-series-films")


def catalogue_mytf1() -> Dict[str, Dict]:
    def by_channel(channel):
        variables = {
            "context": {"persona": "PERSONA_2", "application": "WEB",
                        "device": "DESKTOP", "os": "WINDOWS"},
            "filter": {"channel": channel} if channel else {},
            "offset": 0, "limit": 500,
        }
        data = get("https://www.tf1.fr/graphql/web",
                   {"id": "483ce0f",
                    "variables": json.dumps(variables, separators=(",", ":"))},
                   {"referer": "https://www.tf1.fr/programmes-tv"})
        return ((data.get("data") or {}).get("programs") or {}).get("items") or []

    return {
        program["slug"]: {"slug": program["slug"], "name": program.get("name", ""),
                          "channel": (program.get("mainChannel") or {}).get("label", "")}
        for items in parallel(by_channel, TF1_LISTS)
        for program in items if program.get("slug")
    }


# France TV addresses a show as <channel>_<slug>; app/providers/fr/francetv.py
# rebuilds that from these five channels, so a programme filed under anything
# else (sport/…, la1ere/…, documentaires/…) is not offered.
FRANCETV_CHANNELS = ("france-2", "france-3", "france-4", "france-5", "franceinfo")
FRANCETV_PROGRAMS = "http://api-front.yatta.francetv.fr/standard/publish/channels"


def catalogue_francetv() -> Dict[str, Dict]:
    def by_channel(channel):
        # Each channel's list leans towards that channel but is not limited to
        # it, so all five are read and unioned. Page 0 says how many follow.
        url = f"{FRANCETV_PROGRAMS}/{channel}/programs/"
        first = get(url, {"platform": "apps", "size": 100, "page": 0})
        rest = parallel(
            lambda page: get(url, {"platform": "apps", "size": 100, "page": page}).get("result") or [],
            range(1, (first.get("cursor") or {}).get("last", 0) + 1),
        )
        return [*(first.get("result") or []), *(row for page in rest for row in page)]

    rows = {}
    for programs in parallel(by_channel, FRANCETV_CHANNELS):
        for program in programs:
            channel, _, slug = (program.get("url_complete") or "").partition("/")
            if channel in FRANCETV_CHANNELS and slug:
                rows[slug] = {"slug": slug, "name": program.get("label", ""),
                              "channel": channel}
    return rows


def catalogue_cbc() -> Dict[str, Dict]:
    data = get("https://services.radio-canada.ca/ott/catalog/v2/gem/category/shows",
               {"device": "web", "pageNumber": 1, "pageSize": 500},
               {"Accept": "application/json", "Referer": "https://gem.cbc.ca/",
                "Origin": "https://gem.cbc.ca"})
    return {show["url"]: {"slug": show["url"], "name": show.get("title", ""),
                          "channel": "CBC"}
            for show in data["content"][0]["items"]["results"] if show.get("url")}


CATALOGUES = {
    "6play": catalogue_6play,
    "mytf1": catalogue_mytf1,
    "francetv": catalogue_francetv,
    "cbc": catalogue_cbc,
}
_cache: Dict[str, List[Dict]] = {}


def catalogue(provider: str) -> List[Dict]:
    """Every show a provider offers, sorted by name. Fetched once per run."""
    if provider not in _cache:
        rows = CATALOGUES[provider]()
        _cache[provider] = sorted(rows.values(), key=lambda row: row["name"].lower())
    return _cache[provider]


# ---------------------------------------------------------------------------
# programs.json
# ---------------------------------------------------------------------------

def _fields(obj: Dict) -> str:
    return ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
                     for k, v in obj.items())


def dump_programs(data: Dict) -> str:
    """Serialise in the file's own layout: one show per line, 2-space indent."""
    head = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
                      for k, v in data.items() if k != "shows")
    shows = ",\n".join("    { " + _fields(show) + " }" for show in data["shows"])
    return "{\n" + head + ',\n  "shows": [\n' + shows + "\n  ]\n}\n"


CORE = ("provider", "slug", "name")


def validate(payload) -> List[Dict]:
    """Return the shows to write, or raise ValueError.  This overwrites a real
    file, so nothing unchecked gets through."""
    if not isinstance(payload, dict) or not isinstance(payload.get("shows"), list):
        raise ValueError("expected an object with a 'shows' list")
    seen = set()
    shows = []
    for i, show in enumerate(payload["shows"]):
        if not isinstance(show, dict):
            raise ValueError(f"show {i} is not an object")
        clean = {}
        for field in CORE:
            value = show.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"show {i}: '{field}' is required")
            clean[field] = value.strip()
        if clean["provider"] not in CATALOGUES:
            raise ValueError(f"show {i}: unknown provider '{clean['provider']}'")
        key = (clean["provider"], clean["slug"])
        if key in seen:
            raise ValueError(f"duplicate show: {clean['provider']}/{clean['slug']}")
        seen.add(key)
        # Any other field the file already pinned (an artwork URL, a genre
        # override) is kept verbatim; the editor just does not offer to add one.
        for field, value in show.items():
            if field not in clean and field != "enabled":
                clean[field] = value
        if show.get("enabled") is False:
            clean["enabled"] = False
        shows.append(clean)
    return shows


# ---------------------------------------------------------------------------

_FORBIDDEN = JSONResponse({"error": "The programs editor is local-only"}, status_code=403)


@router.get("/")
async def homepage(request: Request):
    """The editor locally, the plain API greeting anywhere else."""
    if not _is_local(request):
        return {"message": "Catch-up TV & More for Stremio API"}
    return FileResponse(EDITOR_PAGE, media_type="text/html")


@router.get("/api/programs")
async def read_programs(request: Request):
    if not _is_local(request):
        return _FORBIDDEN
    return Response(PROGRAMS.read_text(encoding="utf-8"),
                    media_type="application/json; charset=utf-8")


@router.post("/api/programs")
async def write_programs(request: Request):
    if not _is_local(request):
        return _FORBIDDEN
    data = json.loads(PROGRAMS.read_text(encoding="utf-8"))
    try:
        data["shows"] = validate(await request.json())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    # newline="" — the repo keeps programs.json in LF, and the default would
    # rewrite every line as CRLF on Windows.
    PROGRAMS.write_text(dump_programs(data), encoding="utf-8", newline="")
    logger.info("✅ [Editor] Saved %d shows to programs.json", len(data["shows"]))
    return {"saved": len(data["shows"]), "path": str(PROGRAMS)}


@router.get("/api/catalogue/{provider}")
async def read_catalogue(provider: str, request: Request):
    if not _is_local(request):
        return _FORBIDDEN
    if provider not in CATALOGUES:
        return JSONResponse({"error": f"unknown provider '{provider}'"}, status_code=404)
    try:
        return await run_in_threadpool(catalogue, provider)
    except Exception as exc:
        logger.error("❌ [Editor] %s catalogue failed: %s", provider, exc)
        return JSONResponse({"error": f"{provider}: {exc}"}, status_code=502)
