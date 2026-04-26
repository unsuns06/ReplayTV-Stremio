# Refactoring Review — ReplayTV-Stremio

**Date:** 2026-04-25  
**Scope:** Refactoring opportunities only — security issues excluded  
**Reviewer:** Claude Sonnet 4.6 (AI-assisted review)

---

## Table of Contents

1. [Code Duplication](#1-code-duplication)
2. [Overly Long Methods](#2-overly-long-methods)
3. [Unnecessary Complexity](#3-unnecessary-complexity)
4. [Abstraction Gaps](#4-abstraction-gaps)
5. [Inconsistent Patterns](#5-inconsistent-patterns)
6. [Unused Code](#6-unused-code)
7. [God Objects / Oversized Files](#7-god-objects--oversized-files)
8. [Type Safety Gaps](#8-type-safety-gaps)
9. [Naming Inconsistencies](#9-naming-inconsistencies)
10. [Test Quality](#10-test-quality)
11. [Prioritised Action List](#11-prioritised-action-list)

---

## 1. Code Duplication

### 1.1 `_build_stream_headers()` duplicated in provider and base

| | |
|---|---|
| **Files** | `app/providers/base_provider.py:183–194`, `app/providers/fr/mytf1.py:86–107` |
| **Effort** | S |

`BaseProvider._build_stream_headers()` already builds the canonical headers dict; `MyTF1Provider._build_stream_headers()` re-implements it with minor additions (extra request-metadata headers, optional auth token). The override is 22 lines; the base is 12 lines; the overlap is ~80%.

**Fix:** Keep the base version. Override in `MyTF1Provider` by calling `super()._build_stream_headers()` and merging the extra keys, or add an `extra: Dict` parameter to the base method.

---

### 1.2 Proxy-fallback logic implemented twice

| | |
|---|---|
| **Files** | `app/providers/base_provider.py:166–181`, `app/providers/fr/mytf1.py:109–131` |
| **Effort** | S |

Both implementations:
1. Encode the destination URL
2. Prepend the proxy base URL
3. Try the proxied URL
4. Fall back to the direct URL on failure

`MyTF1Provider._fetch_with_proxy_fallback()` adds a check for `delivery.country != 'US'`; the base version checks `delivery.code == 200`. The structural logic is identical.

**Fix:** Parameterise the success predicate in `BaseProvider._fetch_with_proxy_fallback(success_fn=None)`. `MyTF1Provider` passes its own predicate; `BaseProvider` uses the default. Remove the copy from `MyTF1Provider`.

---

### 1.3 `_safe_api_call()` boilerplate in every French provider

| | |
|---|---|
| **Files** | `app/providers/fr/francetv.py:88–90`, `app/providers/fr/mytf1.py:77–84`, `app/providers/fr/sixplay.py:126–135` |
| **Effort** | S |

All three methods are one-liners (or near-one-liners) that just delegate to `self.api_client.get()` / `.post()`. Example:

```python
# francetv.py
def _safe_api_call(self, url, params=None, headers=None, max_retries=3):
    return self.api_client.get(url, params=params, headers=headers, max_retries=max_retries)
```

**Fix:** Delete all three. Call `self.api_client.get()` directly at each call site. The method name adds no clarity.

---

### 1.4 Real-Debrid + processor-URL file checking duplicated

| | |
|---|---|
| **Files** | `app/providers/base_provider.py:132–164` (`_check_processed_file`), `app/providers/fr/mytf1.py:157–216` (`_check_processed_file_locations`) |
| **Effort** | S |

Both methods:
1. Fetch `realdebridfolder` from credentials
2. List its contents via HTTP HEAD/GET
3. Fall through to the N_m3u8DL processor URL

`MyTF1Provider`'s version adds `safe_print` verbosity; logic is otherwise the same.

**Fix:** Remove `BaseProvider._check_processed_file()` and have all providers call the `MyTF1`-style version, or lift it to `BaseProvider` in full and delete the `MyTF1` copy.

---

### 1.5 ThreadPoolExecutor parallel-fetch repeated verbatim

| | |
|---|---|
| **Files** | `app/providers/fr/francetv.py:106–107`, `app/providers/fr/francetv.py:277–278`, `app/providers/fr/mytf1.py:334–336`, `app/providers/fr/sixplay.py:171–172` |
| **Effort** | M |

Four identical three-line blocks:

```python
with ThreadPoolExecutor(max_workers=_PARALLEL_FETCH_WORKERS) as executor:
    results = list(executor.map(fn, items))
```

**Fix:** Add `BaseProvider._parallel_map(fn, items) -> list` that wraps this pattern. Each call site becomes one line.

---

## 2. Overly Long Methods

### 2.1 `MyTF1Provider.get_episode_stream_url()` — ~155 lines

| | |
|---|---|
| **File** | `app/providers/fr/mytf1.py:703–858` |
| **Effort** | L |

A single method that handles: lazy auth, `_check_processed_file_locations`, proxy/direct fetch of stream metadata, DRM key extraction, DASH-proxy URL building, DRM processing trigger, MediaFlow URL generation, and secondary stream list construction. It contains at least 5 nested try-except blocks.

**Fix:** Extract:

| New method | Lines currently |
|---|---|
| `_get_episode_metadata(episode_id)` | 703–730 |
| `_build_drm_streams(video_url, license_url, license_headers)` | 740–820 |
| `_trigger_background_processing(video_url, keys)` | 762–790 |

---

### 2.2 `SixPlayProvider.get_episode_stream_url()` — ~170 lines

| | |
|---|---|
| **File** | `app/providers/fr/sixplay.py:299–504` |
| **Effort** | L |

Handles: stream format selection, HLS vs MPD branching, PSSH extraction, DRM token request, Widevine key extraction (local pywidevine call), MPD rewriting, processed-file fallback, and return. No fewer than 8 distinct try-except scopes.

**Fix:** Extract:

| New method | Concern |
|---|---|
| `_select_best_format(video_data)` | Format selection |
| `_get_drm_token(episode_id)` | Token API call |
| `_resolve_drm_stream(mpd_url, drm_token, key_id)` | Key extraction + stream building |

---

### 2.3 `FranceTVProvider.get_live_stream_url()` — ~100 lines

| | |
|---|---|
| **File** | `app/providers/fr/francetv.py:313–470` |
| **Effort** | M |

Contains three distinct broadcast-ID lookup strategies (mobile API → front API → fallback constants) each in its own try-except, followed by token URL resolution. These are independent concerns stapled together.

**Fix:** Extract `_get_broadcast_id(channel_name) -> Optional[str]` (the lookup cascade), leaving the token/stream logic in the main method.

---

### 2.4 `MainApp.log_requests_and_responses()` middleware — ~92 lines

| | |
|---|---|
| **File** | `app/main.py:99–191` |
| **Effort** | M |

Single async function does: IP extraction from six header types, signed-token IP decode, response body introspection on error, exception logging with traceback, and error JSON construction.

**Fix:** Extract `_extract_viewer_ip(headers, client) -> Optional[str]` (lines 99–124) into `app/utils/client_ip.py`. Extract `_log_error_response(response, logger)` helper.

---

### 2.5 `CBCProvider._authenticate_if_needed()` — ~44 lines

| | |
|---|---|
| **File** | `app/providers/ca/cbc.py:97–140` |
| **Effort** | M |

Mixes three concerns: cache read, credential loading + authentication call, cache write. The body has three nested if-else trees.

**Fix:** Extract `_check_auth_cache() -> bool` and `_store_auth_result(success: bool)`. Reduces the main method to ~10 lines of orchestration.

---

## 3. Unnecessary Complexity

### 3.1 Over-nested try-except in `MyTF1Provider.get_episodes()`

| | |
|---|---|
| **File** | `app/providers/fr/mytf1.py:374–470` |
| **Effort** | M |

```python
try:
    if not self._authenticated and not self._authenticate():
        return []
    try:
        ...
        try:
            # innermost
        except:
            pass
    except:
        return [self._create_fallback_episode(...)]
except Exception as e:
    return [self._create_fallback_episode(...)]
```

Three layers of try-except with identical fallback action. The middle and outer handlers do the same thing.

**Fix:** Flatten to a single try-except at the outer scope. Use early returns instead of nested guards.

---

### 3.2 `_get_region()` and `_get_default_channel()` are unnecessarily abstracted

| | |
|---|---|
| **File** | `app/routers/catalog.py:44–56` |
| **Effort** | S |

```python
def _get_region(provider_name: str) -> str:
    return "ca" if provider_name == "cbc" else "fr"

def _get_default_channel(provider_name: str) -> str:
    return {"francetv": "france2", "mytf1": "tf1", "6play": "m6", "cbc": "dragonsden"}.get(provider_name, "france2")
```

Both are called in exactly one place — `_build_fallback_shows_from_programs()`. Functions of this size have negative ROI as named helpers.

**Fix:** Inline both at the single call site, or move the mapping to `PROVIDER_REGISTRY` config (where per-provider defaults already live).

---

### 3.3 Six-header IP extraction duplicated in middleware vs `client_ip.py`

| | |
|---|---|
| **Files** | `app/main.py:100–124`, `app/utils/client_ip.py:43–76` (`get_public_client_ip`) |
| **Effort** | S |

`client_ip.py` already has `get_public_client_ip(request_headers)` which reads CF-Connecting-IP, True-Client-IP, X-Real-IP, and X-Forwarded-For in priority order. The middleware re-implements the same loop manually, adding a signed-token decode step.

**Fix:** Extend `get_public_client_ip()` to accept an optional token string, and call it from the middleware instead of the bespoke extraction loop.

---

### 3.4 `_log_json_decode_details()` repeats credential-path logic already in `credentials.py`

| | |
|---|---|
| **File** | `app/routers/catalog.py:57–72` |
| **Effort** | S |

The function logs the JSON error, then reconstructs the paths to `credentials.json` and `credentials-test.json` to check their existence — logic already centralised in `app/utils/credentials.py`.

**Fix:** Delete `_log_json_decode_details()`. Log the `JSONDecodeError` inline and delegate credential-path diagnostics to the existing credential-loader debug endpoint.

---

## 4. Abstraction Gaps

### 4.1 Authentication pattern duplicated across all three providers that need login

| | |
|---|---|
| **Files** | `app/providers/fr/mytf1.py:220–305`, `app/providers/fr/sixplay.py:70–124`, `app/providers/ca/cbc.py:97–140` |
| **Effort** | L |

All three follow the same flow:

1. Check if already authenticated (`self._authenticated`)
2. Check cache for valid token
3. Load credentials from `load_credentials()`
4. Call provider-specific auth API
5. Store token, set `self._authenticated = True`
6. Write result to cache with TTL

The only provider-specific part is step 4. Steps 1–3 and 5–6 are identically structured.

**Fix:** Add an `AuthMixin` to `BaseProvider`:

```python
class AuthMixin:
    _auth_cache_key: str      # override in subclass
    _auth_success_ttl: int = 3600
    _auth_failure_ttl: int = 300

    def _authenticate_if_needed(self):
        if self._authenticated:
            return
        cached = cache.get(self._auth_cache_key)
        if cached and cached.get("authenticated"):
            return
        success = self._do_authenticate()   # abstract, provider implements
        cache.set(self._auth_cache_key,
                  {"authenticated": success},
                  ttl=self._auth_success_ttl if success else self._auth_failure_ttl)
        self._authenticated = success
```

Each provider only implements `_do_authenticate() -> bool`.

---

### 4.2 Image URL extraction pattern repeated in three places

| | |
|---|---|
| **Files** | `app/providers/fr/francetv.py:148–161` (show logo), `app/providers/fr/francetv.py:198–221` (channel images), `app/providers/fr/metadata.py:32–88` (`populate_images`) |
| **Effort** | M |

All three blocks:
1. Iterate over a `patterns` list from the API response
2. Match against a `type` field (e.g., `"vignette_16x9"`, `"logo"`)
3. Pick a preferred width key (e.g., `"w:1024"`)
4. Prefix relative URLs with `https://www.france.tv`

**Fix:** Consolidate into `FranceTVImageExtractor.extract(patterns, preferred_types)` in `app/providers/fr/metadata.py` and call from all three sites.

---

### 4.3 No shared interface for live-channel providers

| | |
|---|---|
| **Files** | `app/providers/fr/francetv.py`, `app/providers/fr/mytf1.py`, `app/providers/ca/cbc.py` |
| **Effort** | M |

`BaseProvider.get_live_channels()` returns `[]` by default but the abstract method contract doesn't enforce the dict shape. `francetv` returns `{id, type, name, poster, logo, description}`. `mytf1` returns the same keys. The router builds channel objects from this dict without schema enforcement.

**Fix:** Add a `LiveChannelInfo` TypedDict to `type_defs.py` and annotate `get_live_channels() -> List[LiveChannelInfo]`. Validate in tests.

---

## 5. Inconsistent Patterns

### 5.1 Three different approaches to IP header merging

| | |
|---|---|
| **Files** | `app/providers/base_provider.py:196–208`, `app/routers/stream.py:27–34`, `app/providers/ca/cbc.py:85–95` |
| **Effort** | S |

- `BaseProvider._merge_ip_headers(headers)` — merges via context var
- `stream._merge_headers(provider_headers, include_ip=True)` — separate router helper doing the same
- `CBCProvider._get_headers_with_viewer_ip()` — bespoke version that logs the IP

All three produce the same result. The router variant and the CBC bespoke version are redundant now that `BaseProvider._merge_ip_headers()` exists.

**Fix:** Delete `_merge_headers()` from the router; call `provider._merge_ip_headers(stream_headers)` instead. Collapse `_get_headers_with_viewer_ip()` in CBC to a call to `self._build_ip_headers()`.

---

### 5.2 Cache key naming convention is inconsistent

| | |
|---|---|
| **Files** | `app/routers/catalog.py:98,107`, `app/routers/meta.py:96,162`, `app/providers/ca/cbc.py:148,171,219` |
| **Effort** | S |

| Location | Key used |
|---|---|
| `catalog.py` | `"channels:{p_key}"` |
| `meta.py` | `"channels:{provider_key}"` |
| `meta.py` | `"episodes:{series_id}"` |
| `cbc.py` | `"cbc_shows"` (flat) |
| `cbc.py` | `"cbc_programs"` (flat) |
| `cbc.py` | `"cbc_episodes:{series_id}"` (prefixed differently) |

**Fix:** Define a `CacheKeys` class:

```python
class CacheKeys:
    @staticmethod
    def channels(provider: str) -> str:   return f"channels:{provider}"
    @staticmethod
    def programs(provider: str) -> str:   return f"programs:{provider}"
    @staticmethod
    def episodes(series_id: str) -> str:  return f"episodes:{series_id}"
    @staticmethod
    def stream(episode_id: str) -> str:   return f"stream:{episode_id}"
```

---

### 5.3 Logging style: `safe_print()` vs `logger.*()` mixed within the same codebase

| | |
|---|---|
| **Files** | `app/providers/fr/mytf1.py`, `app/providers/fr/sixplay.py` (heavy `safe_print`), `app/providers/ca/cbc.py`, `app/routers/*.py` (use `logger`) |
| **Effort** | M |

`safe_print()` bypasses the logging level configuration entirely. If `LOG_LEVEL=warning`, the provider's step-by-step trace messages still flood stdout.

**Fix:** Replace `safe_print(...)` with `logger.debug(...)` throughout the providers. `safe_print` should remain only as a last-resort fallback for non-configurable startup messages.

---

### 5.4 Provider attribute naming: `provider_name` vs `provider_key`

| | |
|---|---|
| **Files** | `app/providers/base_provider.py:33,79`, all provider subclasses |
| **Effort** | M |

`provider_name = "francetv"` (class attribute, the registry key) coexists with `provider_key` (abstract property that returns the same string). One is redundant.

**Fix:** Remove the abstract `provider_key` property. Keep `provider_name` (class attribute). Rename it `provider_id` everywhere for clarity ("name" implies human-readable, "id" implies a code key).

---

## 6. Unused Code

### 6.1 `safe_log()` — defined, never called

| | |
|---|---|
| **File** | `app/utils/safe_print.py:16–42` |
| **Effort** | S |

`grep -r "safe_log" app/` returns zero results. The function is 26 lines of dead code.

**Fix:** Delete `safe_log()`.

---

### 6.2 `BaseProvider._check_processed_file()` — overridden and not called via base

| | |
|---|---|
| **File** | `app/providers/base_provider.py:132–164` |
| **Effort** | S |

`MyTF1Provider` has its own fuller version (`_check_processed_file_locations`). `SixPlayProvider` does the same check inline. No provider calls the base version via `super()` or via inheritance.

**Fix:** Delete the base version. Each provider that needs this check owns it entirely.

---

### 6.3 `utils/direct_mpd_processor.py` re-export stub — entire file is boilerplate

| | |
|---|---|
| **File** | `app/utils/direct_mpd_processor.py` |
| **Effort** | S |

After the DRM consolidation (fix #3), this file became a 4-line stub:

```python
from app.utils.drm.direct_mpd_processor import DirectMPDProcessor, get_processed_mpd_content
```

No non-test code imports from the stub path any more (grepping confirms). Same applies to `utils/nm3u8_drm_processor.py` and `utils/sixplay_mpd_processor.py`.

**Fix:** Verify with `grep -r "from app.utils.nm3u8_drm_processor\|from app.utils.sixplay_mpd_processor\|from app.utils.direct_mpd_processor" app/` — delete any stubs that have zero non-stub callers.

---

### 6.4 `test_mpd_processing_only()` in `drm/direct_mpd_processor.py` — empty placeholder

| | |
|---|---|
| **File** | `app/utils/drm/direct_mpd_processor.py` (bottom) |
| **Effort** | S |

```python
def test_mpd_processing_only():
    """Test the MPD processing without MediaFlow to verify it works"""
    # This is a standalone test function
    pass
```

Empty test function in production code.

**Fix:** Delete it. Test logic belongs in `app/tests/`.

---

### 6.5 `resolve_stream()` stubs in FranceTV and MyTF1

| | |
|---|---|
| **Files** | `app/providers/fr/francetv.py` (bottom), `app/providers/fr/mytf1.py` (bottom) |
| **Effort** | S |

Both end with:

```python
def resolve_stream(self, stream_id: str) -> Optional[Dict]:
    safe_print(f"⚠️ [FranceTV] resolve_stream not implemented for {stream_id}")
    return None
```

`resolve_stream()` is already implemented in `BaseProvider` and routes to `get_channel_stream_url()` / `get_episode_stream_url()`. These overrides shadow the working base implementation with a broken stub.

**Fix:** Delete both stubs and let the base implementation handle routing.

---

## 7. God Objects / Oversized Files

### 7.1 `MyTF1Provider` — 1 008 lines

| | |
|---|---|
| **File** | `app/providers/fr/mytf1.py` |
| **Effort** | L |

Single class contains: Gigya auth flow (80 lines), GraphQL program fetching (90 lines), episode parsing (50 lines), episode stream resolution with DRM (155 lines), live stream resolution (75 lines), processed-file check (60 lines), show-metadata fetch (60 lines), custom proxy logic (25 lines).

**Fix:** Split into:

```
app/providers/fr/
  mytf1.py              — MyTF1Provider (orchestrator, ~200 lines)
  mytf1_auth.py         — MyTF1Authenticator
  mytf1_episodes.py     — episode fetching & parsing
  mytf1_streams.py      — stream resolution & DRM
```

---

### 7.2 `SixPlayProvider` — ~1 150 lines

| | |
|---|---|
| **File** | `app/providers/fr/sixplay.py` |
| **Effort** | L |

Similar split needed:

```
app/providers/fr/
  sixplay.py            — SixPlayProvider (orchestrator)
  sixplay_auth.py       — Gigya auth
  sixplay_streams.py    — stream resolution, DRM, MPD handling
```

---

### 7.3 `CBCProvider` — 734 lines

| | |
|---|---|
| **File** | `app/providers/ca/cbc.py` |
| **Effort** | M |

Authentication (~50 lines), show fetching (~35 lines), episode fetching (~100 lines), stream resolution (~80 lines), live channel listing (~50 lines) are all in one class.

**Fix:** Extract `CBCStreamResolver` (~150 lines of stream + auth) into `app/providers/ca/cbc_streams.py`.

---

### 7.4 `http_utils.py` mixes HTTP client, JSON parser, and decorator

| | |
|---|---|
| **File** | `app/utils/http_utils.py` (~389 lines) |
| **Effort** | M |

`RobustHTTPClient` contains: session setup with retry (40 lines), JSON parsing with 5 fallback strategies (130 lines), HTML error detection (20 lines), JSONP extraction (15 lines).

**Fix:** Extract `safe_json_parse()` and its fallback strategies into a separate `app/utils/json_parser.py` module. `RobustHTTPClient` delegates to it.

---

## 8. Type Safety Gaps

### 8.1 `get_episode_stream_url()` returns `Optional[Dict]` instead of `Optional[StreamInfo]`

| | |
|---|---|
| **Files** | All providers, `app/schemas/type_defs.py:9–26` |
| **Effort** | M |

`StreamInfo` TypedDict is defined but not used as the return type annotation on the abstract method or any implementation. Callers in `stream.py` access `info["url"]`, `info["manifest_type"]` etc. without type checking.

**Fix:** Change `BaseProvider.get_episode_stream_url()` return type to `Optional[StreamInfo]`. Update all implementations accordingly. mypy will then catch key typos.

---

### 8.2 Router helper functions lack return-type annotations

| | |
|---|---|
| **Files** | `app/routers/catalog.py:17,43,49,57`, `app/routers/meta.py:21,44,71,131`, `app/routers/stream.py:27,37,53` |
| **Effort** | S |

Most router helper functions have parameter types but no return-type annotations. Example:

```python
def _build_fallback_shows_from_programs(provider_name: str, request: Request):
    # returns List[Dict] but annotation is absent
```

**Fix:** Add `-> List[Dict[str, Any]]`, `-> Optional[Dict]`, etc. to all helpers in the routers.

---

### 8.3 `ProviderConfig` TypedDict has optional fields that are always present

| | |
|---|---|
| **File** | `app/schemas/type_defs.py:62–70` |
| **Effort** | S |

`ProviderConfig` uses `total=False` (all fields optional) but `provider_name`, `display_name`, and `id_prefix` are required for the system to function. A `None` `id_prefix` would cause a runtime crash with no type warning.

**Fix:** Split into required base and optional extension, or use `total=True` for the required fields and a sub-TypedDict for optional ones.

---

## 9. Naming Inconsistencies

### 9.1 `provider_name` (registry key) vs `display_name` (human label) vs `provider_key` (abstract property returning the same as `provider_name`)

| | |
|---|---|
| **Files** | `app/providers/base_provider.py:33,79,93`, `app/config/provider_config.py` |
| **Effort** | M |

Three concepts use overlapping names:
- `provider_name = "francetv"` — the registry ID
- `provider_key` — abstract property that returns the same value as `provider_name`
- `display_name = "France TV"` — the human-readable label

Callers pass `provider_name` to the registry and get back a dict with `provider_name` in it. The abstract `provider_key` is a required override that adds zero value over the class attribute.

**Fix:**
1. Rename class attribute `provider_name` → `provider_id` 
2. Delete the abstract `provider_key` property (use `provider_id` directly everywhere)
3. Keep `display_name` as-is

---

### 9.2 `_handle_*` vs `_build_*` vs `_get_*` naming in the same file

| | |
|---|---|
| **File** | `app/routers/stream.py` |
| **Effort** | S |

- `_handle_channel_stream(id, request)` — does the full request dispatch
- `_handle_series_stream(provider_key, id, request)` — same
- `_build_stream_from_info(info, include_ip)` — constructs an object
- `_build_stream_response(stream_info, provider_name, include_ip)` — also constructs

`_handle_*` is consistent within this file but conflicts with `_build_*` which describes a different level of abstraction. Compare with `meta.py` which uses `_handle_channel_metadata()` and `_handle_series_metadata()` for the same pattern.

**Fix:** The naming within each router is internally consistent; the gap is cross-file. Document the convention: `_handle_*` = route dispatch, `_build_*` = object construction.

---

### 9.3 Episode ID marker inconsistency between providers

| | |
|---|---|
| **Files** | `app/providers/fr/francetv.py:36`, `app/providers/fr/mytf1.py:35`, `app/providers/ca/cbc.py:43` |
| **Effort** | S |

| Provider | `episode_marker` |
|---|---|
| francetv | `"episode:"` |
| mytf1 | `"episode:"` |
| 6play | `"episode:"` |
| cbc | `"episode-"` |

CBC uses a dash where all others use a colon. This is a silent inconsistency caught only by careful string-matching. The Stremio ID format documentation (added in fix #8) now notes this, but the inconsistency itself remains.

**Fix:** Standardise CBC's `episode_marker` to `"episode:"` and update CBC episode ID generation. Run existing CBC tests to confirm no breakage.

---

## 10. Test Quality

### 10.1 Provider test files hit real APIs — no mocking

| | |
|---|---|
| **Files** | `app/tests/test_francetv.py`, `app/tests/test_cbc.py`, `app/tests/test_mytf1.py`, `app/tests/test_sixplay.py` |
| **Effort** | L |

The `test_get_episode_stream_url()` functions in all four provider test files call the real upstream API. These:
- Require live internet access
- Require valid credentials in environment
- Are non-deterministic (content changes, APIs fail)
- Are slow (~10–30 s)
- Pass trivially on machines without credentials (they just return `None`)

**Fix:** Add mocked unit tests alongside the live integration tests. Gate live tests with `@pytest.mark.integration` and skip by default in CI.

---

### 10.2 `resolve_stream()` stubs are never tested

| | |
|---|---|
| **Files** | Dead stubs in `francetv.py`, `mytf1.py` (finding 6.5 above) |
| **Effort** | S |

These override the working base implementation but are tested nowhere. They silently break stream routing for any caller that goes through `resolve_stream()`.

**Fix:** Add a test that calls `provider.resolve_stream(episode_id)` and asserts it delegates correctly (not `None`).

---

### 10.3 No test for `ProviderFactory.create_provider()` with all registered keys

| | |
|---|---|
| **File** | `app/tests/test_routers.py` |
| **Effort** | S |

If a new provider is added to `PROVIDER_REGISTRY` without implementing all abstract methods, the factory will crash at runtime but not in tests.

**Fix:**

```python
@pytest.mark.parametrize("key", PROVIDER_REGISTRY.keys())
def test_provider_factory_instantiates_all_registered_providers(key):
    provider = ProviderFactory.create_provider(key, request=None)
    assert provider is not None
    assert hasattr(provider, "get_programs")
    assert hasattr(provider, "get_episodes")
```

---

### 10.4 Router helper functions are not unit-tested

| | |
|---|---|
| **Files** | `app/routers/meta.py:44–90`, `app/routers/stream.py:27–73` |
| **Effort** | M |

`_build_video_data()`, `_build_series_meta()`, `_build_stream_from_info()` are pure functions with no side effects. They are not tested directly; they only get coverage through full-stack router tests. A bug in field-name casing would not be caught by the current suite.

**Fix:** Move these helpers to `app/utils/` (or `app/schemas/`) and add direct unit tests.

---

## 11. Prioritised Action List

### Phase 1 — Quick Wins (S effort, 1–2 days)

| # | Action | File(s) |
|---|---|---|
| 1 | Delete `safe_log()` | `utils/safe_print.py` |
| 2 | Delete `resolve_stream()` stubs that shadow the base | `francetv.py`, `mytf1.py` |
| 3 | Delete `test_mpd_processing_only()` placeholder | `drm/direct_mpd_processor.py` |
| 4 | Remove `_safe_api_call()` wrappers; call `api_client` directly | `francetv.py`, `mytf1.py`, `sixplay.py` |
| 5 | Delete `BaseProvider._check_processed_file()` | `base_provider.py` |
| 6 | Inline `_get_region()` / `_get_default_channel()` | `routers/catalog.py` |
| 7 | Add return-type annotations to all router helpers | `routers/*.py` |
| 8 | Standardise CBC `episode_marker` to `"episode:"` | `cbc.py` |
| 9 | Add `CacheKeys` helper class | new `utils/cache_keys.py` |
| 10 | Add `@pytest.mark.parametrize` factory smoke test | `test_routers.py` |

---

### Phase 2 — Medium Refactors (M effort, 1–2 weeks)

| # | Action | Impact |
|---|---|---|
| 11 | Extract `_get_broadcast_id()` from `FranceTVProvider.get_live_stream_url()` | Readability |
| 12 | Extract `_check_auth_cache()` / `_store_auth_result()` from `CBCProvider._authenticate_if_needed()` | Readability |
| 13 | Extract `BaseProvider._parallel_map()` for ThreadPoolExecutor pattern | DRY |
| 14 | Consolidate image extraction into `FranceTVImageExtractor` in `providers/fr/metadata.py` | DRY |
| 15 | Extract `safe_json_parse()` into standalone `utils/json_parser.py` | Separation of concerns |
| 16 | Extract IP-extraction logic from `main.py` middleware into `client_ip.py` | Cohesion |
| 17 | Add `LiveChannelInfo` TypedDict; annotate `get_live_channels()` | Type safety |
| 18 | Use `StreamInfo` return type on `get_episode_stream_url()` | Type safety |
| 19 | Replace `safe_print()` with `logger.debug()` in provider files | Respects LOG_LEVEL |
| 20 | Rename `provider_name` → `provider_id`; delete abstract `provider_key` | Clarity |
| 21 | Add `@pytest.mark.integration` to provider tests that hit real APIs | Test reliability |

---

### Phase 3 — Large Refactors (L effort, 2–3 weeks)

| # | Action | Impact |
|---|---|---|
| 22 | Split `MyTF1Provider` (1 008 lines) into orchestrator + auth + episodes + streams | Maintainability |
| 23 | Split `SixPlayProvider` (~1 150 lines) into orchestrator + auth + streams | Maintainability |
| 24 | Add `AuthMixin` base class; have MyTF1, SixPlay, CBC use it | DRY, consistency |
| 25 | Parameterise `_fetch_with_proxy_fallback()` success predicate; remove MyTF1 duplicate | DRY |
| 26 | Mock all provider tests; gate live tests behind `--integration` flag | Test reliability |
| 27 | Move router helpers to utility modules; add direct unit tests | Test coverage |

---

## Summary

| Dimension | Assessment |
|---|---|
| Code duplication | High — proxy logic, auth pattern, image extraction all duplicated |
| Method length | High — 3 methods over 100 lines; 2 over 150 lines |
| Complexity | Medium — nested try-except, but error handling intent is clear |
| Abstraction | Medium — good base class; auth and parallel-fetch gaps |
| Consistency | Medium — logging style and cache keys most inconsistent |
| Dead code | Low — a handful of stubs and unused functions |
| File size | High — two provider files exceed 1 000 lines |
| Type safety | Medium — TypedDicts defined but not enforced at boundaries |
| Naming | Low–Medium — one systemic issue (provider_name/key) |
| Tests | High — no mocking, no factory test, no router helper tests |

**Biggest leverage points for effort invested:**
1. Delete dead code (Phase 1, same day) — removes misleading surface area
2. Split MyTF1 and SixPlay (Phase 3) — the single largest readability gain
3. Replace `safe_print` with `logger.debug` (Phase 2) — makes LOG_LEVEL actually work for provider noise
4. Mock provider tests (Phase 3) — makes CI reliable and fast

---

*Generated by automated code review — all observations are suggestions, not mandates.*
