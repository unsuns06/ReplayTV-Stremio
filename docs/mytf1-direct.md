# MyTF1 replay — direct source through MediaFlow

Same method as the 6play paths (see [`6play-live.md`](6play-live.md) §5–§9b): license the
DASH stream with a local Widevine CDM, hand MediaFlow the raw content key, let it decrypt
CENC server-side and re-serve plain HLS. Only the provider-specific bits differ.

Code: `app/providers/fr/mytf1.py` (`get_episode_stream_url`, `_build_direct_stream`,
`_select_drm_key`), `app/providers/fr/tf1_drm_key_extractor.py`.
Tests: `tests/test_mytf1_direct.py`.

## Pipeline

```
episode id → Gigya/TF1 auth (Bearer JWT) → mediainfo delivery (url + drms)
           → TF1DRMExtractor: PSSH from MPD → license POST to drm-wide.tf1.fr → {kid: key}
           → MediaFlow /proxy/mpd/manifest.m3u8?d=<mpd>&key_id=…&key=…&h_authorization=Bearer …
```

## Differences from 6play

| | 6play | MyTF1 |
|---|---|---|
| license server | `lic.drmtoday.com` + `x-dt-auth-token` (pinned UA) | `drm-wide.tf1.fr/proxy?id=<video>` + headers from `delivery.drms[0].h` |
| auth on segment requests | none | `h_authorization: Bearer <JWT>` passed through MediaFlow |
| CDN token | `?st=…&e=…` on the manifest | JWT in the URL path, carries `cip` (client IP) — upstream URLs 403 from anywhere else, which is expected |
| segment paths in MPD | root-relative (`/m6web/…`) — trips old MediaFlow builds | relative — unaffected |

## Stream list returned

1. `✅ [TorBox] DRM-Free Video` / `✅ [RD] …` — the pre-processed file, when one exists.
2. `🌐 [MPD] Direct source (MediaFlow)` — **always** present now (it replaced the dash.js
   `dash_proxy` player stream, which is no longer used; the `proxies.dash_proxy` credential
   entry is now dead config).
3. `⏳ DRM-Free Video (Processing…)` — only when keys were extracted *and* no processed file
   exists yet, so nothing is re-downloaded.

If key extraction fails, the direct stream is still returned, pointed at the TF1 license
server (`license_url` + `license_h_*`) so MediaFlow can license it itself. If MediaFlow is
unconfigured, the raw manifest URL is returned instead.

## Multiple keys

MediaFlow accepts exactly one `key_id`/`key` pair, a TF1 license can return several. One key
→ use it. More than one → fetch the manifest once and pick the key matching its
`default_KID` (`_select_drm_key`).

## Verified end-to-end (2026-08-14)

`sept-a-huit`, episode `5933a3c5-…`:

```
key extracted        64f952d2872e5c34bd02682751dbbe75:ce11d0c81ec014e35baa9a312a20618a
master playlist      200 (5 video variants + 1 audio)
video/audio playlist 200
segment via MediaFlow 200, 4.1 MB, boxes: ftyp/moof/mdat, avc1
                      no pssh, senc, sinf, encv, saiz → decrypted
segment fetched direct 403 (CDN token is IP-bound — normal, MediaFlow is the client)
```
