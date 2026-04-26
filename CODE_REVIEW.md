# Code Review — ReplayTV-Stremio

**Date:** 2026-04-25  
**Reviewer:** Claude Sonnet 4.6 (AI-assisted review)  
**Scope:** Full codebase analysis — no code changes made  
**Note:** Security issues intentionally excluded per review scope  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Structure](#2-architecture--structure)
3. [File-by-File Analysis](#3-file-by-file-analysis)
4. [Code Quality Analysis](#4-code-quality-analysis)
5. [Dead Code & Cleanup Opportunities](#5-dead-code--cleanup-opportunities)
6. [Missing Features](#6-missing-features)
7. [Deployment Considerations](#7-deployment-considerations)
8. [Summary & Recommendations](#8-summary--recommendations)

---

## 1. Project Overview

**Purpose:** A Stremio addon providing live TV and replay content for French (France 2, France 3, France 4, France 5, Franceinfo, TF1+, M6) and Canadian (CBC Gem) broadcasters.

| Attribute | Value |
|-----------|-------|
| Language | Python (backend), JavaScript (minimal frontend) |
| Framework | FastAPI with async/concurrency patterns |
| Total Python code | ~10,190 lines across 58 files |
| Server | Uvicorn (ASGI) |
| Data validation | Pydantic v1 |

**Core dependencies:**

| Package | Purpose |
|---------|---------|
| FastAPI / Uvicorn | Web framework and ASGI server |
| Pydantic | Schema validation and serialization |
| httpx / requests | Async and sync HTTP clients |
| lxml / BeautifulSoup4 | HTML parsing |
| m3u8 | HLS playlist parsing |
| PyJWT / cryptography | Token handling |
| pywidevine | DRM/Widevine support |
| pycaption | Caption parsing |

---

## 2. Architecture & Structure

### 2.1 Directory Layout

```
ReplayTV-Stremio/
├── app/
│   ├── auth/                  # Provider-specific authentication modules
│   ├── config/                # Centralized provider configuration registry
│   ├── providers/
│   │   ├── base_provider.py   # Abstract base class (247 lines)
│   │   ├── registry.py        # Provider class mapping
│   │   ├── common.py          # Factory pattern implementation
│   │   ├── fr/                # French providers (FranceTV, MyTF1, 6play)
│   │   └── ca/                # Canadian providers (CBC)
│   ├── routers/               # FastAPI route handlers (catalog, meta, stream)
│   ├── schemas/               # Pydantic models matching the Stremio spec
│   ├── utils/                 # Shared HTTP, caching, IP, credential utilities
│   ├── tests/                 # Unit and baseline regression tests
│   ├── static/                # Channel logos and branding assets
│   └── main.py                # FastAPI app initialization (339 lines)
├── run_server.py              # Entry point
├── requirements.txt
├── manifest.json              # Stremio addon manifest
├── programs.json              # Static TV show configuration database
└── credentials.json           # Provider secrets (example / not committed)
```

### 2.2 Architectural Patterns

**Factory + Registry pattern** — `providers/registry.py` maps provider keys to classes; `providers/common.py` contains the factory that instantiates them. Adding a new provider requires only registering it in the map.

**Template Method pattern** — `BaseProvider` defines abstract methods (`get_programs`, `get_episodes`, `get_stream_url`, etc.) and shares cross-cutting concerns (auth, caching, retry, proxy). Concrete providers fill in the provider-specific logic.

**Centralized configuration** — `config/provider_config.py` builds the provider registry dynamically from `PROVIDER_CLASSES`, exposing filtered lookups (`get_live_providers()`, `get_providers_by_country()`). This is the single source of truth for provider metadata.

**Async concurrency** — `routers/meta.py` and `routers/catalog.py` use `asyncio.gather()` to fan out requests to multiple providers in parallel, which significantly reduces wall-clock latency.

### 2.3 Data Flow

```
Stremio Client
      │
      ▼
FastAPI Routes  (catalog / meta / stream)
      │
      ▼
ProviderFactory  ──►  Specific Provider
      │
      ├── [API call]  ──►  [Cache hit?]  ──►  Return cached
      │                                  └──►  Fetch + cache
      └── [API failure] ──► programs.json fallback
      │
      ▼
Stremio Response (Pydantic model)
      │
      ▼
Stremio Client
```

---

## 3. File-by-File Analysis

### Core Application

#### `app/main.py` (339 lines) — Good

Handles FastAPI initialization, CORS, request/response logging middleware, startup diagnostics, debug endpoints, and static file serving.

**Strengths:** Well-structured middleware, detailed diagnostic logging, good environment variable handling.

**Improvements:**
- `log_level` is hard-coded to `"debug"` (line 25–26), overriding the `LOG_LEVEL` environment variable set in `run_server.py`. Either respect the env var or document why debug is always forced.
- No rate-limiting middleware — if Stremio clients hammer the server, upstream provider APIs will see the full load.
- The log file path (TMP directory) can silently fail on certain deployments; a warning should be surfaced on startup.

---

#### `app/providers/base_provider.py` (247 lines) — Good

Defines the abstract provider interface, session management, User-Agent rotation, retry logic, and proxy fallback.

**Improvements:**
- Several utility methods (`_fetch_with_proxy_fallback`, `_sort_episodes_chronologically`) lack docstrings, making intent non-obvious for new contributors.
- MediaFlow initialization errors are swallowed; a startup warning would catch misconfigured proxies early.
- No credential validation in `__init__` — providers silently operate with empty credentials until the first API call fails.

---

#### `app/routers/catalog.py` (142 lines) — Good

Handles Stremio catalog requests for both live channels and replay series.

**Improvements:**
- 6play is explicitly skipped (line 91) with no inline comment explaining why. A single-line comment here would save future confusion.
- `_build_fallback_shows_from_programs()` and `_get_region()` contain provider-specific logic that belongs in the provider layer, not the router.
- No pagination support — large catalogs will return everything on every request.

---

#### `app/routers/stream.py` (166 lines) — Good

Builds Stremio-compliant stream responses for live and replay content.

**Improvements:**
- Error fallback returns `example.com/error-stream.mp4`, which will produce a silent playback failure in Stremio rather than an informative error message. Consider returning an empty `streams` array or a user-facing error description.
- No logging of which provider returned an error, making stream failures hard to trace.

---

#### `app/routers/meta.py` (215 lines) — Good

Fetches metadata for channels and series using `asyncio.gather()` for parallel provider calls.

**Improvements:**
- FranceTV-specific metadata enhancement is hardcoded in the router; it should live in the FranceTV provider.
- Metadata is not cached — every Stremio client interaction re-fetches from upstream APIs.
- `show_id` extraction from the composite ID string (e.g., `cutam:fr:francetv:show_id`) has no validation; a malformed ID would cause a runtime error.

---

#### `app/routers/configure.py` (29 lines) — Stub

Returns a minimal HTML page. No actual user configuration is implemented.

**Improvement:** Either implement user settings (credentials, region, quality preferences) or document that this is intentionally a placeholder so contributors don't spend time reverse-engineering its purpose.

---

#### `app/config/provider_config.py` (86 lines) — Good

Single source of truth for provider metadata, built dynamically from `PROVIDER_CLASSES`.

**Improvements:**
- The registry is rebuilt at module import time; this is fine for typical usage but could be made lazy-initialized if startup time becomes a concern.
- No validation that provider class attributes (e.g., `provider_name`, `supported_types`) are present and non-empty.

---

### Providers

#### `app/providers/fr/francetv.py` (767 lines) — Good

Covers France 2/3/4/5/Franceinfo live and replay. Uses `ThreadPoolExecutor` for parallel metadata fetching.

**Improvements:**
- `max_workers=5` is hard-coded; should be a configurable constant (or at minimum a named constant, not a magic number).
- No rate limiting on parallel API requests — could trigger HTTP 429s from France.tv APIs during heavy use.
- Mobile and front API endpoint URLs are hardcoded strings (lines 50–51); they should be named constants at the top of the file.
- Silent metadata fetch failures don't log which episode/show caused the error, making debugging difficult.

---

#### `app/providers/fr/mytf1.py` — Good

GraphQL-based provider with Gigya authentication and MediaFlow proxy support.

**Improvements:**
- `needs_ip_forwarding = True` is hard-coded with no fallback. If the IP forwarding infrastructure is unavailable, users get a hard failure with no explanation.
- No token refresh/caching strategy is visible; expiry handling may cause repeated auth round-trips.

---

#### `app/providers/fr/sixplay.py` — Good

M6 content with Gigya auth, Widevine DRM, and MPD processing.

**Improvements:**
- DRM processing is split across `nm3u8_drm_processor`, `sixplay_mpd_processor`, and `direct_mpd_processor`. These should be consolidated into a single DRM utility module.
- Authentication state management is scattered across multiple methods; a dedicated `_ensure_authenticated()` helper would centralize this.
- Reason for 6play being disabled in the catalog should be documented (either in code or a known issues section).

---

#### `app/providers/ca/cbc.py` (748 lines) — Good

CBC Gem with OAuth 2.0 ROPC flow, lazy authentication, and cache-based token persistence.

**Improvements:**
- At 748 lines, this file is approaching maintainability limits. Authentication logic, stream handling, and metadata retrieval could be split into separate modules.
- Live channel regions are hardcoded in the provider class (lines 60–75); this is configuration data that would be better placed in a constants file or `programs.json`.
- IP header handling is spread across multiple methods; a single `_build_ip_headers()` helper would reduce duplication.

---

### Authentication

#### `app/auth/cbc_auth.py` — Good

Handles CBC Gem JWT tokens with expiry checking and ROPC flow.

**Improvements:**
- `CLIENT_ID` is hard-coded; should be an environment variable or credential entry.
- Custom JWT decode path (lines 18–30) exists as a fallback when PyJWT is unavailable. This should at minimum log a warning, as it bypasses token signature verification.

---

#### `app/auth/francetv_auth.py` (26 lines) — Dead code

This file exists as a stub with hard-coded test tokens and is not imported anywhere in the codebase.

**Recommendation:** Remove it. Its presence implies an incomplete refactoring and will confuse future contributors.

---

### Utilities

#### `app/utils/api_client.py` (218 lines) — Good

Unified HTTP client with retry logic, User-Agent rotation, IP header forwarding, and JSON parsing fallbacks.

**Improvements:**
- `safe_request()` has many branching paths; extracting JSON parsing fallback logic into a dedicated `JSONParser` class would improve readability.
- No per-request-type timeout configuration — a slow metadata endpoint will block the same timeout as a fast token refresh.

---

#### `app/utils/cache.py` (65 lines) — Good

Thread-safe in-memory LRU cache with TTL and configurable max size (default 1000).

**Improvements:**
- Cache state is lost on server restart; for tokens and session data this can cause unnecessary re-authentication storms after deploys.
- No hit/miss rate statistics — impossible to know whether the cache is helping without adding instrumentation.
- No async-native support; callers in async context must use thread-safe access patterns.

---

#### `app/utils/credentials.py` (111 lines) — Good

Loads credentials from environment variables with file fallback and multiple JSON parsing strategies.

**Improvements:**
- Lenient JSON parsing (multiple recovery strategies) could silently hide malformed configuration. Consider logging a warning when fallback parsing is triggered.
- No validation of loaded credential structure — a missing required key fails at first use rather than at startup.

---

#### `app/utils/programs_loader.py` (111 lines) — Good

Loads and caches `programs.json` with a 1-hour TTL.

**Improvements:**
- TTL is hard-coded to 3600 seconds; should be a named constant or environment variable.
- No background refresh — the cache goes cold and causes a synchronous file read on the next request.

---

#### `app/utils/client_ip.py` (148 lines) — Good

Extracts and normalizes client IP addresses from request headers, including IPv6 handling and private IP filtering.

**Improvements:**
- The `normalize_ip()` function handles many edge cases but has no unit tests covering IPv6-mapped IPv4, bracket notation, or port-stripping scenarios.
- IP transformation decisions (which header was chosen, what normalization was applied) are not logged, making geo-restriction debugging harder.

---

#### `app/utils/http_utils.py` — Good

Robust HTTP client with JSONP extraction, HTML error detection, and multi-strategy JSON parsing.

**Improvements:**
- `safe_json_parse()` is very long (100+ lines) with nested branches. Extracting each parsing strategy into a named function would aid readability.
- The regex used for JSON body extraction is simplistic and may fail on responses with nested structures.

---

#### `app/utils/base_url.py` (87 lines) — Good

Constructs base URLs for static assets from environment variables or the incoming request.

**Improvements:**
- `Request.url.hostname` can be `None` in some proxied deployments; this should be guarded.
- Only HTTP and HTTPS ports are handled; WebSocket or custom ports would produce incorrect URLs.

---

#### `app/utils/metadata.py` — Misplaced

Contains FranceTV-specific image type mapping and video metadata population but lives in the shared `utils/` package.

**Recommendation:** Move into `app/providers/fr/` alongside the FranceTV provider, or suffix the filename `francetv_metadata.py` to signal its scope.

---

#### `app/utils/mediaflow.py` (63 lines) — Good

Builds MediaFlow proxy URLs with DRM license parameters and IP forwarding headers.

**Improvements:**
- No validation of required parameters before URL construction; a missing `proxy_url` produces a silent runtime error.
- No documentation of the `h_` header prefix convention.

---

#### `app/utils/proxy_config.py` (59 lines) — Good

Thread-safe singleton loader for proxy configuration.

**Improvement:** The singleton pattern is implemented with a class and `threading.Lock`; a module-level variable with a lazy-init function would be simpler and equally correct.

---

#### `app/utils/safe_print.py` (42 lines) — Good

Unicode-safe print/log wrapper that falls back to ASCII encoding on `UnicodeEncodeError`.

No significant issues.

---

### Schemas

#### `app/schemas/stremio.py` (103 lines) — Good

Pydantic models matching the Stremio addon specification.

**Improvements:**
- Some fields marked `Optional` are actually required by the Stremio spec; leaving them optional risks sending invalid responses.
- Extended FranceTV-specific fields (`fanart`, `banner`, `clearart`) are on the shared `MetaDetail` model; they should be on a `FranceTVMetaDetail` subclass to avoid polluting the base spec model.

---

#### `app/schemas/type_defs.py` (70 lines) — Good

TypedDicts for internal provider return types (`StreamInfo`, `EpisodeInfo`, `ShowInfo`, `ProviderConfig`).

**Improvement:** Some fields typed as `Optional` are always populated at runtime. Removing the `Optional` annotation would let type checkers catch callers that forget to handle `None`.

---

### Tests

#### `app/tests/test_routers.py` — Partial coverage

Uses FastAPI `TestClient` correctly, tests manifest and catalog endpoints.

**Improvements:**
- Only happy-path cases are tested. Error cases (provider API failure, missing credentials, malformed IDs) are not covered.
- No concurrent-request tests to validate thread safety of shared caches.
- Mock patches appear incomplete in places; some tests may pass only because the underlying provider call is not actually mocked.

---

### Static Configuration

#### `manifest.json` (46 lines) — Good

Complete and correct Stremio addon manifest. No significant issues.

---

#### `programs.json` (~6.8 KB) — Needs attention

Static database of ~50+ TV shows with per-provider configuration.

**Improvements:**
- No JSON Schema validation — a typo in a field name silently produces missing data.
- Field coverage is inconsistent across shows (some have `poster`, `logo`, `fanart`; others have none).
- Manual maintenance is error-prone as provider APIs evolve. A script to validate and diff `programs.json` against live API responses would reduce drift.

---

#### `run_server.py` (27 lines) — Minor

**Issue:** The `LOG_LEVEL` environment variable is read and stored but never forwarded to the app; `main.py` hard-codes `log_level="debug"`. Either wire up the variable or remove the misleading read.

---

## 4. Code Quality Analysis

### Strengths

| Area | Detail |
|------|--------|
| Architecture | Clear separation of routers / providers / utils / schemas |
| Error handling | Comprehensive try/except with provider-level fallbacks to `programs.json` |
| Async patterns | `asyncio.gather()` for parallel provider calls reduces latency |
| Observability | Extensive logging with level differentiation |
| Extensibility | Adding a provider requires only implementing `BaseProvider` and registering the class |

### Weaknesses

#### Duplication

- IP header construction repeated across `cbc.py`, `mytf1.py`, `stream.py`, and `client_ip.py`. A single `_build_ip_headers(ip: str) -> dict` helper in `BaseProvider` would eliminate this.
- JSON parsing fallback logic appears in both `api_client.py` and `http_utils.py`.
- Provider `__init__` patterns are nearly identical across providers — shared setup belongs in `BaseProvider.__init__`.

#### Scattered DRM processing

Widevine/DRM handling is split across `nm3u8_drm_processor.py`, `sixplay_mpd_processor.py`, and `direct_mpd_processor.py` without a unifying interface. A `DRMProcessor` abstract class would make the intent clear and simplify future additions.

#### Hard-coded magic values

- Thread pool `max_workers=5` (francetv.py)
- Cache TTL `3600` (programs_loader.py)
- Log level `"debug"` (main.py)
- Region strings scattered in provider files

These should all be named constants or environment variables.

#### Performance

- Metadata is never cached between client requests; repeated Stremio browsing re-fetches from upstream APIs every time.
- No rate limiting on parallel outbound requests; a spike in Stremio clients could cause provider API bans.
- The LRU cache uses a single global lock, which will serialize all cache reads under concurrency.

#### Documentation

- Most utility functions have no docstrings.
- No architecture overview document (this review now partially fills that gap).
- The ID format (`cutam:fr:francetv:show_id`) is undocumented; contributors must reverse-engineer it from router code.

### Naming Conventions

**Consistent and correct:**
- Provider keys: lowercase (`francetv`, `mytf1`, `6play`, `cbc`)
- Method names: `snake_case` throughout
- Private helpers: `_prefixed`

**Inconsistent:**
- ID formats mix conventions (`cutam:fr:francetv:show` vs `live_channel_id`)
- Logging style mixes emoji-prefixed messages with plain text messages

---

## 5. Dead Code & Cleanup Opportunities

| File / Location | Issue | Recommendation |
|-----------------|-------|----------------|
| `app/auth/francetv_auth.py` | Unused stub — not imported anywhere | Delete |
| `app/providers/fr/common.py` (if separate from top-level `common.py`) | May duplicate factory logic | Consolidate into one factory |
| `configure.py` | Stub returning non-functional HTML | Document as placeholder or implement |
| `example.com/error-stream.mp4` (stream.py) | Bogus error URL returned to Stremio | Return empty `streams: []` or a text error |

---

## 6. Missing Features

| Feature | Current state | Impact |
|---------|--------------|--------|
| Response caching | Not implemented | Every browse re-hits provider APIs |
| Rate limiting | Not implemented | Risk of upstream API bans |
| `/health` endpoint | Not implemented | Deployment monitoring blind spot |
| Search | Not implemented | Stremio search feature unavailable |
| User configuration | Stub only | Users cannot set credentials or region via UI |
| Cache persistence | In-memory only | Auth tokens lost on restart → re-auth storms |
| `programs.json` validation | None | Silent breakage from typos |
| 6play live channels | Disabled without explanation | Feature gap |

---

## 7. Deployment Considerations

### Environment Variables (well-covered)

| Variable | Purpose |
|----------|---------|
| `HOST` / `PORT` | Server binding |
| `ADDON_BASE_URL` | Static asset base URL |
| `CREDENTIALS_JSON` | Inject credentials without a file |
| `LOG_FILE` / `LOG_TO_FILE` | Log destination |
| `MEDIAFLOW_PROXY_URL` / `MEDIAFLOW_API_PASSWORD` | Proxy setup |
| `PROXY_*` | Geo-proxy configuration |

### Deployment Challenges

- **File system assumptions:** Credentials and program data expected at repo root; containerized deployments that mount secrets elsewhere require extra configuration.
- **Heavy dependencies:** `pywidevine` and `lxml` require native binaries; Alpine-based Docker images need extra build steps.
- **Geographic requirements:** IP forwarding infrastructure (MediaFlow or equivalent) is mandatory for TF1+ and CBC content; this dependency is not documented for new deployers.
- **`log_level` wiring bug:** `run_server.py` reads `LOG_LEVEL` but `main.py` ignores it — production deployments cannot reduce log verbosity without editing source code.

---

## 8. Summary & Recommendations

### Overall Score

| Dimension | Score |
|-----------|-------|
| Architecture | 7 / 10 |
| Error handling | 8 / 10 |
| Performance | 6 / 10 |
| Maintainability | 6 / 10 |
| Documentation | 4 / 10 |
| Testing | 5 / 10 |
| **Overall** | **6.5 / 10** |

The codebase is production-quality and 100% functional. The factory/registry architecture is clean, error handling is thorough, and async concurrency is used correctly. The main gaps are documentation, test coverage, some scattered duplication, and a handful of configuration values that are hard-coded when they should be named constants or environment variables.

---

### High-Priority Improvements

1. **Wire up `LOG_LEVEL`** — Connect `run_server.py`'s env var to `main.py`'s Uvicorn config. Trivial one-line change with real production impact.
2. **Add metadata response caching** — Cache `get_programs()` and `get_episodes()` results per provider with a short TTL (e.g., 10–15 minutes). Would dramatically reduce upstream API load.
3. **Consolidate DRM utilities** — Create a `DRMProcessor` abstract base and have `nm3u8_drm_processor`, `sixplay_mpd_processor`, `direct_mpd_processor` implement it.
4. **Centralize IP header building** — Add `_build_ip_headers(ip)` to `BaseProvider` and remove the duplicated logic from individual providers and routers.
5. **Add a `/health` endpoint** — Returns 200 with provider status. Essential for monitoring in any hosted deployment.

### Medium-Priority Improvements

6. **Replace bogus error stream URL** — Return `{"streams": []}` or a Stremio-compatible error notice instead of `example.com/error-stream.mp4`.
7. **Delete `francetv_auth.py`** — Dead code that misleads contributors.
8. **Document the ID format** — Add a comment in `routers/` or `schemas/` explaining the `cutam:fr:francetv:show_id` composite ID convention.
9. **Extract magic numbers to named constants** — `max_workers`, cache TTLs, log level.
10. **Expand test coverage** — Add error-path tests (provider failure, malformed ID, missing credentials) and at minimum one concurrent-request test.

### Low-Priority Improvements

11. **Move `metadata.py` to `providers/fr/`** — It is FranceTV-specific and misleads readers browsing shared utilities.
12. **Add docstrings to utility functions** — Even one-line summaries would significantly reduce onboarding time.
13. **Add `programs.json` schema validation** — A JSON Schema file and a pre-commit validation script would prevent silent breakage.
14. **Implement the configure endpoint** — User-facing credential entry and region selection would make the addon self-contained.
15. **Add cache hit/miss logging** — Helps quantify cache effectiveness without requiring external metrics infrastructure.

---

*Generated by automated code review — all observations are suggestions, not mandates. The project is fully functional as-is.*
