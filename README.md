# ReplayTV-Stremio — Catch-up TV & More for Stremio

A Python/FastAPI [Stremio](https://www.stremio.com/) addon serving French and
Canadian live TV and replay (catch-up) content:

| Provider | Country | Live TV | Replays | Account needed |
|---|---|---|---|---|
| **France TV** (france.tv) | 🇫🇷 | ✅ France 2/3/4/5, franceinfo: | ✅ | No |
| **TF1+** (tf1.fr) | 🇫🇷 | ✅ TF1, TMC, TFX, TF1 Séries Films | ✅ | Free TF1+ account |
| **6play** (6play.fr) | 🇫🇷 | — | ✅ | Free 6play account |
| **CBC Gem** (gem.cbc.ca) | 🇨🇦 | — | ✅ | Free CBC account |

The show list served by the catalogs lives in [`programs.json`](programs.json).

## Quick start

```bash
pip install -r requirements.txt
python run_server.py          # serves http://127.0.0.1:7860
```

Then add `http://127.0.0.1:7860/manifest.json` as an addon in Stremio.

Useful endpoints:

| Endpoint | Purpose |
|---|---|
| `/manifest.json` | Stremio addon manifest (generated from the provider registry) |
| `/configure` | Provider credential status page |
| `/configure/status` | Same, as JSON |
| `/health` | Health check: provider config status + cache stats |

## Configuration

### Credentials

Credentials are read from **one** of (first match wins):

1. The `CREDENTIALS_JSON` environment variable (full JSON document — recommended for deployments)
2. `credentials.json` at the project root
3. `credentials-test.json` at the project root (fallback)

```json
{
  "mytf1":  {"login": "user@example.com", "password": "secret"},
  "6play":  {"login": "user@example.com", "password": "secret"},
  "cbcgem": {"login": "user@example.com", "password": "secret"},
  "mediaflow": {"url": "https://my-mediaflow", "password": "secret"},
  "proxies": {
    "fr_default": "https://my-fr-proxy/?url=",
    "nm3u8_processor": "https://my-processor",
    "dash_proxy": "https://my-dash-proxy"
  },
  "realdebridfolder": "https://my-rd-folder/"
}
```

All sections are optional — providers degrade gracefully (FranceTV needs no
credentials at all; DRM content needs the relevant account + proxy entries).

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `HOST` / `PORT` | Bind address for `run_server.py` | `127.0.0.1` / `7860` |
| `ADDON_BASE_URL` | Public base URL for static assets (logos) | derived from request |
| `CREDENTIALS_JSON` | Full credentials document (overrides files) | — |
| `PROXY_<NAME>` | Override a single proxy, e.g. `PROXY_FR_DEFAULT` | from credentials |
| `MEDIAFLOW_PROXY_URL` / `MEDIAFLOW_API_PASSWORD` | MediaFlow proxy (overrides credentials section) | — |
| `LOG_LEVEL` | Logging level | `info` |
| `LOG_TO_FILE` / `LOG_FILE` | Optional file logging | off |
| `ENABLE_DEBUG_ENDPOINTS` | Expose `/debug/*` endpoints | off |

### DRM (optional)

DRM-protected replays (TF1+, 6play) additionally use:

- a `device.wvd` pywidevine device file (looked up at `app/providers/fr/device.wvd`,
  `./device.wvd`, or `~/.pywidevine/device.wvd`),
- the `nm3u8_processor` proxy entry for background processing,
- optionally a Real-Debrid folder (`realdebridfolder`) holding pre-processed files.

Without these, the addon falls back to license-URL streams or HLS variants
where available.

## Architecture

```
routers/ (catalog, meta, stream, configure)     FastAPI endpoints; blocking
   │                                            provider I/O runs in the threadpool
   ▼
providers/factory.py                            per-request instance cache
   │
providers/registry.py ──► config/provider_config.PROVIDER_REGISTRY
   │                                            (derived, single source of truth;
   ▼                                            the manifest is generated from it)
providers/base_provider.BaseProvider            template methods: get_programs /
   ├─ LiveProviderMixin                         get_episodes hooks, header/proxy
   ├─ DRMProcessedFileMixin                     helpers, MediaFlow URL building
   ├─ fr/francetv.py  fr/mytf1.py  fr/sixplay.py  ca/cbc.py
   ▼
utils/                                          api_client (retrying HTTP),
                                                cache + cache_keys (keys & TTLs),
                                                auth_cache (cross-request tokens),
                                                ids (composite-ID parser),
                                                client_ip, drm/, mediaflow, …
```

Key conventions:

- **Composite IDs**: `cutam:{country}:{provider}:{slug}[ :episode:{id} ]` —
  parsed exclusively via `app/utils/ids.parse_stremio_id` (grammar documented
  in `app/schemas/type_defs.py`).
- **Stream contract**: provider stream methods return `Optional[List[StreamInfo]]`,
  never a bare dict (enforced by `tests/test_stream_return_types.py`).
- **Caching**: all shared-cache keys and TTLs are declared in
  `app/utils/cache_keys.py`; auth tokens persist across requests via
  `app/utils/auth_cache.py` with TTLs derived from JWT expiry.
- **Adding a provider**: subclass `BaseProvider` (plus `LiveProviderMixin` /
  `DRMProcessedFileMixin` as needed), set the class attributes
  (`provider_name`, `id_prefix`, `catalog_id`, …), implement the template
  hooks, and register the class in `app/providers/registry.py`. The manifest,
  routing, `/health` and `/configure` pick it up automatically.

## Development

```bash
python -m pytest tests -q                  # run the test suite
python -m pytest tests -q -m "not integration"   # skip real-network tests
python -m ruff check app tests             # lint
```
