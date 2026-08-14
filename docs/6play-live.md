# 6play live feeds — how they are made to play

Reference write-up of the exact chain used by `SixPlayProvider.get_channel_stream_url()`
to turn a Stremio `channel` id into a playable live stream. Written after the fact from
the working implementation; every URL, header and quirk below is one that mattered.

Code: `app/providers/fr/sixplay.py`, `app/auth/sixplay_auth.py`,
`app/utils/drm/*`, `app/utils/mediaflow.py`.
Kodi reference the design was cross-checked against: `6play-ref.py` (Catch-up TV & More).

---

## 0. TL;DR of the pipeline

```
channel id  →  Gigya login  →  JWT (6cloud)  →  live JSON (channel assets)
            →  pick DASH asset (+ resolve redirect)
            →  upfront-token (DRMtoday auth, per channel)
            →  fetch MPD → PSSH + default_KID
            →  pywidevine CDM → license request to lic.drmtoday.com → content key
            →  MediaFlow /proxy/mpd/manifest.m3u8?…&key_id=…&key=…  →  Stremio
```

The key insight that made live work at all: **do not hand Stremio a DRM manifest**.
Stremio's player has no Widevine CDM. We license the stream ourselves with a local CDM,
extract the raw content key, and give MediaFlow the `key_id:key` pair so it decrypts the
CENC segments server-side and re-serves plain HLS. The player never sees DRM.

---

## 1. Channel table (`_LIVE_CHANNELS`)

Four channels, each a 4-tuple `(slug, display name, 6play live key, description)`:

| slug   | name | live key |
|--------|------|----------|
| `m6`   | M6   | `M6`     |
| `w9`   | W9   | `W9`     |
| `6ter` | 6ter | `6T`     |
| `gulli`| Gulli| `gulli`  |

The live key is the slug upper-cased **except** `6ter → 6T` and `gulli → gulli`
(lower-case). Those two renames are API-side and are the reason the key is stored in the
table instead of being computed. Same rule as `get_live_url()` in `6play-ref.py:574`.

Stremio ids are `cutam:fr:6play:<slug>`; `_extract_slug()` takes the last colon segment.
`get_live_channels()` publishes them as `type: "channel"` catalog entries with logos from
`app/static/logos/fr/<slug>.png`.

---

## 2. Authentication (required — live is never free)

Replay can fall through to unauthenticated HLS. Live cannot: `get_channel_stream_url()`
hard-fails if `account_id`/`login_token` are missing, because the upfront token endpoint
is scoped to the account id.

### 2.1 Gigya login (`SixPlayAuth.login()`)

1. **API key discovery** — GET `https://www.6play.fr/connexion`, regex `main-(.*?)\.bundle\.js`
   for the bundle hash, GET that bundle, regex `"eu1.gigya.com",key:"(.*?)"`.
   Falls back to the hard-coded key
   `3_hH5KBv25qZTd_sURpixbQW6a4OsiIzIEF2Ei_2H7TXTGLJb_1Hr4THKZianCQhWK` when either regex
   misses (it has been stable for a long time, but the scrape is there for the day it isn't).
2. **Login** — POST `https://login-gigya.m6.fr/accounts.login` form-encoded:
   `loginID`, `password`, `apiKey`, `format=jsonp`, `callback=jsonp_3bbusffr388pem4`,
   with `Referer: https://www.6play.fr/connexion`.
   The response is JSONP; the wrapper `jsonp_3bbusffr388pem4(` … `);` is stripped by string
   replace before `json.loads`. Success is `"UID" in response`; the useful fields are
   `UID`, `UIDSignature`, `signatureTimestamp`.
3. **JWT exchange** — GET `https://front-auth.6cloud.fr/v2/platforms/m6group_web/getJwt`
   with headers:
   ```
   x-auth-gigya-signature:           <UIDSignature>
   x-auth-gigya-signature-timestamp: <signatureTimestamp>
   x-auth-gigya-uid:                 <UID>
   x-auth-device-id:                 _luid_<uuid from MAC>
   x-customer-name:                  m6web
   ```
   Response `{"token": "<JWT>"}`. That JWT is `login_token`; `UID` is `account_id`.

### 2.2 Caching the tokens

Provider instances are per-request, so without caching every play would re-login (3 HTTP
round-trips + a JS bundle download). `store_auth_state("6play", …, token_for_ttl=jwt)`
puts `{account_id, login_token}` in the shared cache with a TTL derived from the JWT `exp`
claim minus a 5-minute buffer (`app/utils/auth_cache.py`), defaulting to 4h if the claim is
unreadable. `_authenticate()` checks `load_auth_state()` first.

`credentials.json` section is `"6play": {"login": ..., "password": ...}`; `_authenticate()`
also accepts a pre-provisioned `account_id` + `login_token` pair, which is what was used to
test the live path before the Gigya scrape was wired up.

---

## 3. Live entry lookup (`_fetch_live_entry`)

```
GET https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live
    ?channel=<LIVE_KEY>&with=service_display_images,nextdiffusion,extra_data
Headers: User-Agent: <random Windows UA>, x-customer-name: m6web
```

Note the **android middleware** host, not the web API. The web API demands more headers and
returns geo-blocked shapes more aggressively; the android one is what the Kodi plugin uses
(`URL_LIVE_JSON`, `6play-ref.py:93`) and it is the one that answers reliably.

Response shape: `{"<LIVE_KEY>": [ { "title": …, "live": {"assets": [...]}, … } ]}` —
i.e. the JSON is keyed by the *live key*, not by the slug. Take `[0]`, then
`entry["live"]["assets"]`. `entry["title"]` becomes the stream title shown in Stremio
(current programme name), falling back to the channel name.

The whole call is wrapped in `@safe_provider_call(default=None)` so a schema change
degrades to "no live entry" instead of a 500.

---

## 4. Asset selection (`_select_best_asset(assets, is_live=True)`)

Assets are dicts with `type`, `video_quality` (`hd`/`sd`) and `full_physical_path`.

Preference order differs between live and replay — this ordering was arrived at
empirically:

| mode   | order |
|--------|-------|
| live   | `http_h264` → `usp_dashcenc_h264` → `dashcenc` |
| replay | `usp_dashcenc_h264` → `dashcenc` → `http_h264` |

Live tries plain HLS (`http_h264`) first because when 6play publishes one for a channel it
is unencrypted and needs none of section 5–7; in practice the four channels above only
publish `usp_dashcenc_h264`, so the DASH+Widevine path is the one that actually runs. Within
a type, `hd` beats `sd`.

**The redirect quirk:** `usp_dashcenc_h264` URLs are 302 redirectors. The final signed MPD
URL must be resolved *before* it is used, because the PSSH fetch and MediaFlow both need the
real host. So:

```python
resp = self.api_client.raw_request('HEAD', url, allow_redirects=False)
if resp is not None and 'location' in resp.headers:
    url = resp.headers['location']
```

Failure here is swallowed (bare `except: pass`) — some CDN edges answer HEAD with 405, in
which case the original URL still works.

Returns `(url, 'mpd')` or `(url, 'hls')`.

---

## 5. DRM upfront token (`_fetch_live_drm_token`)

DRMtoday will not issue a license without a per-asset auth token from 6cloud:

```
GET https://drm.6cloud.fr/v1/customers/m6web/platforms/m6group_web
        /services/6play/users/<account_id>/live/dashcenc_<LIVE_KEY>/upfront-token
Headers: X-Customer-Name: m6web
         X-Client-Release: 5.103.3
         Authorization: Bearer <login_token>
```

Response `{"token": "<jwt-ish blob>"}`. Two things that are easy to get wrong:

* The path segment is `dashcenc_<LIVE_KEY>` — the `dashcenc_` prefix is literal and the key
  is the *live key* (`dashcenc_6T`, not `dashcenc_6ter`).
* Live and replay use **different service segments**: live is `services/6play/users/…/live/…`,
  replay is `services/m6replay/users/…/videos/<id>/…`. Both share
  `_fetch_upfront_token()`; only the path differs.
* `X-Client-Release` is required. Without it the endpoint 400s.

---

## 6. PSSH and KID from the MPD (`_extract_mpd_drm_info`)

`extract_pssh_from_mpd(url, "SixPlay")` (`app/utils/drm/pssh_extractor.py`):

1. `extract_first_pssh(mpd_url, include_mpd=True)` downloads the manifest and walks every
   `ContentProtection` element for a `cenc:pssh` child, base64-decoding it into a
   `PsshRecord(source, parent, base64_text, raw_length, system_id)`.
2. `extract_drm_info_from_mpd(mpd_text)` separately reads
   `{urn:mpeg:cenc:2013}default_KID` off the Widevine `ContentProtection`
   (system id `edef8ba9-79d6-4ace-a3c8-27dcd51d21ed`).
3. If no `<cenc:pssh>` element existed but a `widevine_pssh` string was recovered, a
   `PsshRecord` is synthesised from it.

`normalize_key_id()` then coerces the KID to 32-char lowercase hex, accepting hex with
dashes, standard base64 or urlsafe base64 — 6play's manifests have shipped it in more than
one of those forms.

---

## 7. Getting the content key (`_extract_widevine_key`)

This is the step that replaced an external key-extraction API (CDRM). Everything is local:

1. Load a provisioned Widevine device: `app/providers/fr/device.wvd`, then `./device.wvd`,
   then `~/.pywidevine/device.wvd` — first one that loads wins.
2. `PSSH(pssh_b64)` → `Cdm.from_device(device)` → `cdm.open()` →
   `cdm.get_license_challenge(session_id, pssh)`.
3. POST the raw challenge bytes to
   `https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true` with:
   ```
   User-Agent:      Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36
   x-dt-auth-token: <upfront token from §5>
   Content-Type:    application/octet-stream
   ```
   **The User-Agent is pinned and non-negotiable.** DRMtoday refuses licenses for other UAs;
   this is the single most common cause of a silent live failure. It is the same constant
   (`DRM_UA`) for replay and live, and it is *not* rotated by `get_random_windows_ua()` like
   every other request in the codebase.
   `?specConform=true` makes DRMtoday return a standard Widevine license instead of its
   wrapped JSON form.
4. `cdm.parse_license(session_id, response.content)`, then collect `cdm.get_keys()` filtered
   to `type == 'CONTENT'` into `{kid_hex: key_hex}`.
5. Prefer the key whose KID equals the MPD's `default_KID`; a live license can carry several
   KIDs (audio/video, or rotation overlap) and picking the first one gives a key that decrypts
   nothing. Log a warning and fall back to the first only if the wanted KID is absent.
6. `cdm.close(session_id)` in `finally`.

Returns `"<kid_hex>:<key_hex>"`.

### Normalisation trap

`_acquire_decryption_key()` calls
`normalize_decryption_key(raw_key, raw_key.split(':', 1)[0])` — it normalises against the
KID **the license actually returned**, not the one requested. If those differ and you pass
the requested KID, `normalize_decryption_key` finds no matching pair, falls through to its
"any 32 hex chars" regex, and happily returns *the KID itself* as if it were the key. That
produced a stream that loaded and then rendered garbage, which took a while to diagnose.

---

## 8. Key caching across the live period (`_live_decryption_key`)

Licensing on every play request is slow and burns DRMtoday quota. The key is cached under
`CacheKeys.provider_resource("6play", f"live_key:{key_id_hex}")` with `CacheTTL.STREAM`
(30 min).

Cache key is the **KID, not the channel** — deliberately. When 6play rotates keys it
publishes a new `default_KID` in the manifest, which misses the cache and re-licenses on its
own. No rotation schedule to track, no invalidation logic. Marked in-code with a `ponytail:`
comment; the upgrade path if 6play ever ships multiple KIDs per manifest is a per-Period key
map.

---

## 9. Handing it to MediaFlow (`_build_live_stream_info`)

```python
license_url     = "https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true"
license_headers = {"x-dt-auth-token": drm_token, "User-Agent": DRM_UA}
key_params      = {"key_id": key_id_hex, "key": key}   # only when the key was extracted

proxied = self._build_mediaflow_proxied_url(url, 'mpd',
                                            license_url=license_url,
                                            license_headers=license_headers,
                                            extra_params=key_params)
```

`build_mediaflow_url()` produces
`<base>/proxy/mpd/manifest.m3u8?d=<mpd>&api_password=<pwd>&h_<hdr>=…&license_url=…&license_h_<hdr>=…&key_id=…&key=…`.

* `h_*` params are the headers MediaFlow sends to the **origin** (rotating UA, referer/origin
  `https://www.6play.fr`).
* `license_h_*` are the headers it sends to the **license server** — including the pinned
  `User-Agent` again, since MediaFlow's own default UA would be rejected.
* `key_id` / `key` are the fast path: with them MediaFlow decrypts CENC locally and never
  contacts DRMtoday. The `license_url` pair is kept as a **fallback** for when key extraction
  failed (no `device.wvd`, license error, KID mismatch) so MediaFlow can still try to license
  it itself.
* Endpoint is `/proxy/mpd/manifest.m3u8` for `mpd`, `/proxy/hls/manifest.m3u8` for `hls` —
  either way MediaFlow re-serves HLS, which is what Stremio's player is happy with.

Final stream dict returned to the router:

```python
{
  "url":           proxied or url,          # unproxied fallback if MediaFlow is unconfigured
  "manifest_type": "mpd",
  "title":         "[MPD] <current programme or channel name>",
  "headers":       self._build_stream_headers(),
  "licenseUrl":    license_url,             # only when DRM applies
  "licenseHeaders": license_headers,
}
```

`app/routers/stream.py:_handle_channel_stream` routes `type == "channel"` ids to the
provider matched by `id_prefix`, runs the (blocking) provider call in a threadpool, and wraps
the result in the Stremio `StreamResponse`.

MediaFlow config lives in `credentials.json` under `"mediaflow": {"url", "password"}`. If it
is absent the raw MPD URL is returned and playback will fail on DRM — that is intentional,
so the misconfiguration is visible rather than silently degraded.

---

## 9b. The same trick applied to replay (`_build_direct_stream`)

Replay episodes now offer the **direct source through MediaFlow as an extra stream**,
alongside — never instead of — the TorBox/Real-Debrid processed file:

* `get_episode_stream_url()` no longer returns early when `_check_processed_file()` finds a
  copy. It appends the direct stream to it, so Stremio shows both.
* `_handle_mpd_stream(..., start_processing=not existing)` — background DRM processing is
  still kicked off for episodes that have no processed copy yet, and is *not* re-queued for
  ones that do.
* The DRM steps are identical to live (§5–§7), only the upfront-token path differs
  (`services/m6replay/users/<uid>/videos/<episode_id>/upfront-token`). The extracted key is
  handed to MediaFlow as `key_id`/`key`; if extraction fails, `license_url` +
  `license_h_x-dt-auth-token` are sent instead so MediaFlow licenses it itself.
* The Widevine key cache is shared: `_cached_decryption_key()` (formerly
  `_live_decryption_key`) keyed on `provider:6play:wv_key:<KID>`, 30-min TTL.
* Stream ordering in Stremio: processed file (`✅ [TorBox] DRM-Free Video`) → direct source
  (`🌐 [MPD] Direct source (MediaFlow)`) → processing placeholder if one was started.
* With MediaFlow unconfigured the direct stream is simply omitted (and for a plain HLS asset
  the raw URL is returned as before).

Tests: `tests/test_sixplay_direct.py`.

### Known blocker: MediaFlow must resolve root-relative segment paths

Live and replay manifests are packaged differently:

| | `SegmentTemplate initialization=` | `<BaseURL>` |
|---|---|---|
| live (`sr-m6web.live.6cloud.fr`) | `segment_$RepresentationID$_…_init.mp4` (relative) | absent |
| replay (`th2-edge-0x.cdn.bedrock.tech`) | `/m6web/output/…/essence_….dash` (**root-relative**) | absent |

A MediaFlow build that derives the segment base from the manifest's *directory*
and concatenates produces
`…/static/` + `/m6web/output/…` → `…/static//m6web/output/…` → **403 from the CDN**.
Live is unaffected because its paths are relative, so the same concat happens to be right.

Current upstream `mediaflow_proxy/utils/mpd_utils.py` only prepends a per-representation
`<BaseURL>` (absent here) and resolves with `urljoin`, which yields the correct origin-root
URL — so the fix is to **update the MediaFlow instance**. The 403 is not geo: the corrected
URL returns 200 with no token and no French exit node, and the malformed one returns 403
even from a Paris IP.

---

## 10. Failure modes seen, and what they look like

| Symptom | Cause |
|---|---|
| `Live streams need 6play credentials` | no `account_id`/`login_token` — Gigya login failed or credentials missing |
| upfront-token 400 | missing `X-Client-Release` header |
| upfront-token 401/403 | expired JWT — cached past its `exp`, or wrong `dashcenc_<KEY>` segment |
| license server 403 | wrong User-Agent (not `DRM_UA`), or stale/mismatched `x-dt-auth-token` |
| stream loads, video is garbage | KID/key mismatch — the `normalize_decryption_key` trap in §7 |
| `No PSSH found in MPD manifest` | redirect not resolved, so the MPD fetched was the redirector body |
| 404 on live JSON | slug used instead of the live key (`6ter` vs `6T`) |
| plays for ~30 min then stalls | key rotation with a still-cached key — resolves itself on the next KID; if not, drop the `wv_key:` cache entry |
| MediaFlow 403s every segment, manifest was fine | segment URL contains `/static//m6web/…` — outdated MediaFlow, see §9b. Not geo, not the token |

---

## 11. Reproducing by hand

```bash
# 1. Gigya login (JSONP)
curl -s -X POST https://login-gigya.m6.fr/accounts.login \
  -H 'Referer: https://www.6play.fr/connexion' \
  -d 'loginID=USER&password=PASS&apiKey=3_hH5KBv25qZTd_sURpixbQW6a4OsiIzIEF2Ei_2H7TXTGLJb_1Hr4THKZianCQhWK&format=jsonp&callback=cb'

# 2. JWT
curl -s https://front-auth.6cloud.fr/v2/platforms/m6group_web/getJwt \
  -H 'x-auth-gigya-signature: SIG' -H 'x-auth-gigya-signature-timestamp: TS' \
  -H 'x-auth-gigya-uid: UID' -H 'x-auth-device-id: _luid_x' -H 'x-customer-name: m6web'

# 3. live assets
curl -s 'https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live?channel=M6&with=service_display_images,nextdiffusion,extra_data' \
  -H 'x-customer-name: m6web'

# 4. upfront token
curl -s 'https://drm.6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/6play/users/UID/live/dashcenc_M6/upfront-token' \
  -H 'X-Customer-Name: m6web' -H 'X-Client-Release: 5.103.3' -H 'Authorization: Bearer JWT'

# 5. resolve the redirect, then key + play locally
curl -sI 'https://.../usp_dashcenc_h264...'     # take Location:
./N_m3u8DL-RE "<final .mpd>" --key <kid>:<key> --save-name m6 -M format=mkv
```

Step 5's `N_m3u8DL-RE` line is the same command `_print_download_command()` logs on the
replay path — it is the quickest way to confirm a key is correct outside the addon.
