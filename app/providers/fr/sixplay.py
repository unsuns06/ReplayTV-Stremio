import logging
import re
import os

from typing import Dict, List, Optional
from app.auth.sixplay_auth import SixPlayAuth
from app.utils.drm.pssh_extractor import extract_pssh_from_mpd
from app.utils.encoding import normalize_key_id, normalize_decryption_key
from app.utils.user_agent import get_random_windows_ua
from app.utils.programs_loader import get_programs_for_provider
from app.utils.auth_cache import load_auth_state, store_auth_state
from app.utils.base_url import get_logo_url
from app.utils.cache import cache
from app.utils.cache_keys import CacheKeys, CacheTTL
from app.providers.base_provider import BaseProvider, LiveProviderMixin, safe_provider_call
from app.providers.drm_mixin import DRMProcessedFileMixin


logger = logging.getLogger(__name__)

# DRMtoday only issues licenses to this UA — same value for replay and live.
DRM_UA = ("Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36")
DRM_LICENSE_URL = "https://lic.drmtoday.com/license-proxy-widevine/cenc/"
UPFRONT_TOKEN_BASE = "https://drm.6cloud.fr/v1/customers/m6web/platforms/m6group_web"
# Every 6play image is addressed by its external_key (see URL_IMG in 6play-ref.py).
IMAGE_URL = "https://images.6play.fr/v1/images/{}/raw"


class SixPlayProvider(LiveProviderMixin, DRMProcessedFileMixin, BaseProvider):
    # Class attributes for BaseProvider
    provider_name = "6play"
    base_url = "https://www.6play.fr"
    country = "fr"
    
    # Metadata
    display_name = "6play"
    id_prefix = "cutam:fr:6play"
    episode_marker = "episode:"
    catalog_id = "fr-6play-replay"
    default_channel = "m6"

    # Artwork field -> 6play image role. Anything already set in programs.json
    # takes precedence; the API only fills what is missing.
    # Roles are tried in order: not every program publishes a fullColorLogo
    # (66 minutes Grand Format has only the plain "logo").
    _IMAGE_ROLES = {
        "logo": ("logo", "fullColorLogo"),
        "poster": ("cover",),
        "background": ("jumbotron",),
        "fanart": ("jumbotron",),
    }

    # Live channels: (slug, display name, 6play live key, description).
    # The live key is the slug upper-cased except for the two the API renames.
    _LIVE_CHANNELS = (
        ("m6", "M6", "M6", "Chaîne généraliste du groupe M6"),
        ("w9", "W9", "W9", "Chaîne de divertissement du groupe M6"),
        ("6ter", "6ter", "6T", "Chaîne familiale du groupe M6"),
        ("gulli", "Gulli", "gulli", "Chaîne jeunesse du groupe M6"),
    )


    def __init__(self, request=None):
        # Initialize base class (handles credentials, session, mediaflow, proxy_config)
        super().__init__(request)
        
        # 6play-specific API endpoints
        self.api_url = "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play"
        self.auth_url = "https://login-gigya.m6.fr/accounts.login"
        self.token_url = "https://6cloud.fr/v1/customers/m6web/platforms/m6group_web/services/6play/users"
        self.live_url = "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live"
        self.api_key = "3_hH5KBv25qZTd_sURpixbQW6a4OsiIzIEF2Ei_2H7TXTGLJb_1Hr4THKZianCQhWK"
        
        # 6play-specific authentication state
        self.account_id = None
        self.login_token = None
        self._auth_attempted = False
        
        # Load shows from external programs.json
        self.shows = get_programs_for_provider('6play')

    def _authenticate(self) -> bool:
        """Authenticate the session for 6play using real Gigya authentication.

        This implementation follows the Kodi plugin approach:
        - Uses Gigya API for real authentication
        - Obtains JWT tokens for DRM content access
        - Falls back gracefully for unauthenticated access to free content
        - Caches authentication state to avoid repeated logins
        """
        try:
            if self._authenticated:
                return True
            if self._auth_attempted:
                return False

            # Reuse tokens cached by a previous request (provider instances are
            # per-request, so instance state alone would force a re-login).
            cached = load_auth_state(self.provider_name)
            if cached and cached.get('account_id') and cached.get('login_token'):
                self.account_id = cached['account_id']
                self.login_token = cached['login_token']
                self._authenticated = True
                logger.debug("✅ [SixPlay] Using cached auth tokens")
                return True

            username = (self.credentials or {}).get("username") or (self.credentials or {}).get("login")
            password = (self.credentials or {}).get("password")

            # If tokens are pre-provisioned, use them directly
            preset_account_id = (self.credentials or {}).get("account_id")
            preset_login_token = (self.credentials or {}).get("login_token")
            if preset_account_id and preset_login_token:
                self.account_id = preset_account_id
                self.login_token = preset_login_token
                self._authenticated = True
                logger.debug("✅ [SixPlay] Using preset 6play account_id/login_token from credentials")
                return True

            # If no credentials provided, allow unauthenticated access (HLS-only paths may still work)
            if not username or not password:
                logger.warning("⚠️ [SixPlay] No 6play credentials found; continuing without authentication")
                logger.warning("⚠️ [SixPlay] Note: DRM content will not be accessible without valid credentials")
                self._authenticated = True  # Mark as 'handled' so callers can proceed to non-DRM paths
                return True

            # Perform real authentication using Gigya API
            auth = SixPlayAuth(username=username, password=password)
            if auth.login():
                # Get real authentication data
                auth_data = auth.get_auth_data()
                if auth_data:
                    self.account_id, self.login_token = auth_data
                    self._authenticated = True
                    store_auth_state(
                        self.provider_name,
                        {'account_id': self.account_id, 'login_token': self.login_token},
                        token_for_ttl=self.login_token,
                    )
                    logger.debug("✅ [SixPlay] 6play authentication succeeded")
                    logger.debug("🔑 [SixPlay] Account ID: %s", self.account_id)
                    logger.debug("🔑 [SixPlay] JWT Token: %s...", self.login_token[:20])
                    return True

            logger.error("❌ [SixPlay] 6play authentication failed")
            self._auth_attempted = True
            return False
        except Exception as e:
            logger.error("❌ [SixPlay] Authentication error: %s", e)
            self._auth_attempted = True
            return False
    

    
    def _fetch_episodes_raw(self, slug: str) -> Optional[List[Dict]]:
        """Resolve program_id for slug, then return the raw video list."""
        program_id = (self.shows.get(slug) or {}).get('api_id')
        if program_id:
            logger.debug("✅ [SixPlay] Using hardcoded program ID: %s", program_id)
        else:
            program_id = self._find_program_id(slug)
        if not program_id:
            logger.error("❌ [SixPlay] No program ID found for show: %s", slug)
            return None
        return self._fetch_raw_videos(program_id)

    def get_episode_stream_url(self, episode_id: str) -> Optional[List[Dict]]:
        """Get streams for a 6play episode: pre-processed file(s) *and* the direct source.

        The TorBox/Real-Debrid copy is listed first when it exists; the
        MediaFlow-proxied original is always offered alongside it so playback
        works before (or without) background DRM processing.
        """
        actual_episode_id = self._extract_after_marker(episode_id)
        try:
            existing = self._check_processed_file(actual_episode_id) or []

            if not self._authenticated and not self._authenticate():
                logger.error("❌ [SixPlay] 6play authentication failed")
                return existing or None

            video_assets = self._fetch_video_assets(actual_episode_id)
            if not video_assets:
                return existing or None

            url, fmt = self._select_best_asset(video_assets)
            if not url:
                logger.warning("⚠️ [SixPlay] No stream URL found for %s", actual_episode_id)
                return existing or None
            logger.debug("✅ [SixPlay] Selected %s stream", fmt.upper() if fmt else "unknown")
            if fmt == 'hls':
                direct = self._build_direct_stream(url, 'hls')
                return existing + [direct or {"url": url, "manifest_type": "hls"}]
            # Don't re-download something that is already processed.
            return existing + self._handle_mpd_stream(
                url, actual_episode_id, start_processing=not existing,
            )

        except Exception as e:
            logger.error("❌ [SixPlay] Error getting stream for %s: %s", actual_episode_id, e)
            return None

    def _fetch_video_assets(self, episode_id: str) -> Optional[List[Dict]]:
        """Call the 6play video API and return the assets list for the episode."""
        headers = self._merge_ip_headers({"User-Agent": get_random_windows_ua()})
        url = (
            f"https://android.middleware.6play.fr/6play/v2/platforms/"
            f"m6group_androidmob/services/6play/videos/{episode_id}"
            f"?csa=6&with=clips,freemiumpacks"
        )
        response = self.api_client.raw_request('GET', url, headers=headers)
        if response is None or response.status_code != 200:
            status = response.status_code if response is not None else "no response"
            logger.error("❌ [SixPlay] Video API error %s for %s", status, episode_id)
            return None
        clips = response.json().get('clips', [])
        if not clips:
            logger.error("❌ [SixPlay] No clips in API response for %s", episode_id)
            return None
        return clips[0].get('assets') or None

    def _fetch_drm_token(self, episode_id: str) -> Optional[str]:
        """Fetch the per-episode DRM upfront token from 6cloud."""
        return self._fetch_upfront_token(
            f"services/m6replay/users/{self.account_id}/videos/{episode_id}/upfront-token"
        )

    def _fetch_live_drm_token(self, live_key: str) -> Optional[str]:
        """Fetch the per-channel live DRM upfront token from 6cloud."""
        return self._fetch_upfront_token(
            f"services/6play/users/{self.account_id}/live/dashcenc_{live_key}/upfront-token"
        )

    def _fetch_upfront_token(self, path: str) -> Optional[str]:
        """Fetch a DRM upfront token from 6cloud (``path`` is appended to the API base)."""
        if not self.account_id or not self.login_token:
            return None
        try:
            headers = self._merge_ip_headers({
                'X-Customer-Name': 'm6web',
                'X-Client-Release': '5.103.3',
                'Authorization': f'Bearer {self.login_token}',
            })
            response = self.api_client.raw_request('GET', f"{UPFRONT_TOKEN_BASE}/{path}", headers=headers)
            if response is not None and response.status_code == 200:
                token = response.json()["token"]
                logger.debug("✅ [SixPlay] DRM token obtained")
                return token
            logger.error(
                "❌ [SixPlay] DRM token request failed: %s",
                response.status_code if response is not None else "no response",
            )
            return None
        except Exception as e:
            logger.error("❌ [SixPlay] DRM token fetch error: %s", e)
            return None

    def _build_drm_license_info(self, drm_token: str) -> Dict:
        """Build the licenseUrl / licenseHeaders dict for DRM-protected streams."""
        license_url = (
            f"{DRM_LICENSE_URL}"
            f"|Content-Type=&User-Agent={DRM_UA}"
            f"&Host=lic.drmtoday.com&x-dt-auth-token={drm_token}"
            f"|R{{SSM}}|JBlicense"
        )
        return {
            "licenseUrl": license_url,
            "licenseHeaders": {"User-Agent": DRM_UA},
            "drm_token": drm_token,
            "drm_protected": True,
        }

    # Background DRM processing + placeholder streams come from DRMProcessedFileMixin.

    def _extract_mpd_drm_info(self, video_url: str):
        """Extract PSSH and key ID from an MPD manifest, return (pssh_record, key_id_hex, base_stream)."""
        pssh_record, _mpd_text, drm_info = extract_pssh_from_mpd(video_url, "SixPlay")
        key_id_hex = normalize_key_id((drm_info or {}).get('key_id'))
        if key_id_hex:
            logger.debug("[SixPlay] MPD default_KID: %s", key_id_hex)

        stream: Dict = {"url": video_url, "manifest_type": "mpd"}
        if key_id_hex:
            stream["default_kid"] = key_id_hex
        if pssh_record:
            stream.update({
                "pssh": pssh_record.base64_text,
                "pssh_system_id": pssh_record.system_id,
                "pssh_source": pssh_record.source,
            })
            logger.debug("[SixPlay] PSSH included in stream")
        else:
            logger.warning("[SixPlay] No PSSH found in MPD manifest")
        return pssh_record, key_id_hex, stream

    def _acquire_decryption_key(self, pssh_record, key_id_hex: str, drm_token: str) -> Optional[str]:
        """Try to extract and normalize a Widevine decryption key. Returns normalized key or None."""
        if not pssh_record or not drm_token:
            return None
        raw_key = self._extract_widevine_key(pssh_record.base64_text, drm_token, key_id_hex)
        if not raw_key:
            logger.error("[SixPlay] CDRM did not return a Widevine key")
            return None
        # Normalize against the KID actually returned, not the requested one: on a
        # mismatch normalize_decryption_key falls back to a bare 32-hex search and
        # would hand back the KID itself as if it were the key.
        normalized = normalize_decryption_key(raw_key, raw_key.split(':', 1)[0])
        if not normalized:
            logger.error("[SixPlay] Unable to normalize Widevine key")
        return normalized

    def _handle_mpd_stream(self, video_url: str, episode_id: str,
                           start_processing: bool = True) -> List[Dict]:
        """Orchestrate MPD/DASH DRM flow: extract PSSH, acquire key, build streams."""
        pssh_record, key_id_hex, stream = self._extract_mpd_drm_info(video_url)
        drm_token = self._fetch_drm_token(episode_id)

        decryption_key = self._cached_decryption_key(pssh_record, key_id_hex, drm_token)
        streams = []
        direct = self._build_direct_stream(video_url, 'mpd', key_id_hex, decryption_key, drm_token)
        if direct:
            streams.append(direct)

        if decryption_key:
            stream["decryption_key"] = decryption_key
            self._print_download_command(video_url, decryption_key, episode_id)
            placeholder = self._start_drm_processing(video_url, episode_id, key=decryption_key) if start_processing else None
            if placeholder:
                streams.append(placeholder)
            # streams can be empty if MediaFlow is unconfigured — fall back to the raw manifest.
            return streams or [stream]

        # No key: hand the player the raw manifest and let it license the stream.
        if drm_token:
            stream.update(self._build_drm_license_info(drm_token))
        else:
            logger.warning("[SixPlay] No DRM token — returning basic MPD stream")
        streams.append(stream)
        return streams

    def _build_direct_stream(self, video_url: str, fmt: str, key_id_hex: Optional[str] = None,
                             key: Optional[str] = None,
                             drm_token: Optional[str] = None) -> Optional[Dict]:
        """MediaFlow-proxied stream straight from 6play's CDN. None if MediaFlow is off.

        Same mechanics as the live path: when the Widevine key was extracted
        locally MediaFlow decrypts the CENC segments itself (``key_id``/``key``);
        otherwise it is pointed at DRMtoday to license the stream on its own.
        """
        license_url = license_headers = key_params = None
        if key and key_id_hex:
            key_params = {"key_id": key_id_hex, "key": key}
        elif drm_token:
            license_url = f"{DRM_LICENSE_URL}?specConform=true"
            license_headers = {"x-dt-auth-token": drm_token, "User-Agent": DRM_UA}

        proxied = self._build_mediaflow_proxied_url(
            video_url, fmt, license_url=license_url, license_headers=license_headers,
            extra_params=key_params,
        )
        if not proxied:
            logger.debug("⚠️ [SixPlay] MediaFlow not configured — no direct source stream")
            return None

        stream = {
            "url": proxied,
            "manifest_type": fmt,
            "title": f"🌐 [{fmt.upper()}] Direct source (MediaFlow)",
            "headers": self._build_stream_headers(),
        }
        if license_url:
            stream["licenseUrl"] = license_url
            stream["licenseHeaders"] = license_headers
        return stream

    # ------------------------------------------------------------------
    # Live channels
    # ------------------------------------------------------------------

    def get_live_channels(self) -> List[Dict]:
        """Get list of live TV channels from 6play."""
        channels = []
        for slug, name, _live_key, desc in self._LIVE_CHANNELS:
            logo = get_logo_url("fr", slug, self.request)
            channels.append({
                "id": f"cutam:fr:6play:{slug}",
                "type": "channel",
                "name": name,
                "poster": logo,
                "logo": logo,
                "description": desc,
            })
        return channels

    @safe_provider_call(default=None)
    def _fetch_live_entry(self, live_key: str) -> Optional[Dict]:
        """Return the current live diffusion entry for a channel, or None."""
        headers = self._merge_ip_headers({
            'User-Agent': get_random_windows_ua(),
            'x-customer-name': 'm6web',
        })
        params = {'channel': live_key, 'with': 'service_display_images,nextdiffusion,extra_data'}
        response = self.api_client.raw_request('GET', self.live_url, headers=headers, params=params)
        if response is None or response.status_code != 200:
            status = response.status_code if response is not None else "no response"
            logger.error("❌ [SixPlay] Live API error %s for %s", status, live_key)
            return None
        entries = response.json().get(live_key) or []
        if not entries:
            logger.error("❌ [SixPlay] No live entry for channel %s", live_key)
            return None
        return entries[0]

    def get_channel_stream_url(self, channel_id: str) -> Optional[List[Dict]]:
        """Get the live stream for a 6play channel (DASH+Widevine via MediaFlow)."""
        slug = self._extract_slug(channel_id)
        channel = next((c for c in self._LIVE_CHANNELS if c[0] == slug), None)
        if not channel:
            logger.error("❌ [SixPlay] Unknown live channel: %s", slug)
            return None
        _slug, name, live_key, _desc = channel

        try:
            if not self._authenticated and not self._authenticate():
                logger.error("❌ [SixPlay] 6play authentication failed")
                return None
            if not (self.account_id and self.login_token):
                logger.error("❌ [SixPlay] Live streams need 6play credentials (no account_id/login_token)")
                return None

            entry = self._fetch_live_entry(live_key)
            assets = ((entry or {}).get('live') or {}).get('assets')
            if not assets:
                logger.error("❌ [SixPlay] No live assets for %s", live_key)
                return None

            url, fmt = self._select_best_asset(assets, is_live=True)
            if not url:
                logger.error("❌ [SixPlay] No usable live asset for %s", live_key)
                return None

            return [self._build_live_stream_info(url, fmt, live_key, entry, name)]

        except Exception as e:
            logger.error("❌ [SixPlay] Error getting live stream for %s: %s", slug, e)
            return None

    def _cached_decryption_key(self, pssh_record, key_id_hex: str, drm_token: str) -> Optional[str]:
        """Widevine content key, cached by KID (used by both live and replay).

        ponytail: the cache is keyed on the MPD's ``default_KID``, so a key
        rotation publishes a new KID, misses the cache and re-licenses by
        itself — no rotation schedule to track. If 6play ever ships several
        KIDs in one manifest, switch to a per-Period key map here.
        """
        if not (pssh_record and key_id_hex and drm_token):
            return None
        cache_key = CacheKeys.provider_resource(self.provider_name, f"wv_key:{key_id_hex}")
        cached = cache.get(cache_key)
        if cached:
            logger.debug("✅ [SixPlay] Live key served from cache (KID %s)", key_id_hex)
            return cached
        key = self._acquire_decryption_key(pssh_record, key_id_hex, drm_token)
        if key:
            cache.set(cache_key, key, ttl=CacheTTL.STREAM)
        return key

    def _build_live_stream_info(self, url: str, fmt: str, live_key: str,
                                entry: Dict, channel_name: str) -> Dict:
        """Assemble the live stream dict, adding DRM license info for DASH assets."""
        license_url = license_headers = None
        key_params = None
        if fmt == 'mpd':
            drm_token = self._fetch_live_drm_token(live_key)
            if drm_token:
                license_url = f"{DRM_LICENSE_URL}?specConform=true"
                license_headers = {"x-dt-auth-token": drm_token, "User-Agent": DRM_UA}
                pssh_record, key_id_hex, _ = self._extract_mpd_drm_info(url)
                key = self._cached_decryption_key(pssh_record, key_id_hex, drm_token)
                if key:
                    # MediaFlow decrypts the CENC segments itself with this pair.
                    key_params = {"key_id": key_id_hex, "key": key}
                    logger.debug("✅ [SixPlay] Live key extracted: %s:%s", key_id_hex, key)
                else:
                    logger.warning("⚠️ [SixPlay] No live Widevine key — falling back to license URL")
            else:
                logger.warning("⚠️ [SixPlay] No live DRM token — stream will likely not play")

        proxied = self._build_mediaflow_proxied_url(
            url, fmt, license_url=license_url, license_headers=license_headers,
            extra_params=key_params,
        )
        program = (entry or {}).get('title')
        stream = {
            "url": proxied or url,
            "manifest_type": fmt,
            "title": f"[{fmt.upper()}] {program or channel_name}",
            "headers": self._build_stream_headers(),
        }
        if license_url:
            stream["licenseUrl"] = license_url
            stream["licenseHeaders"] = license_headers
        return stream

    def _select_best_asset(self, assets: List[Dict], is_live: bool = False):
        """Pick the best (url, format) from asset list. Returns (url, 'hls'|'mpd') or (None, None)."""
        type_order = ('http_h264', 'usp_dashcenc_h264', 'dashcenc') if is_live else \
                     ('usp_dashcenc_h264', 'dashcenc', 'http_h264')
        quality_rank = {'hd': 1, 'sd': 0}
        for atype in type_order:
            matches = [
                (quality_rank.get((a.get('video_quality') or 'sd').lower(), 0), a)
                for a in assets if atype in a.get('type', '')
            ]
            if not matches:
                continue
            best = sorted(matches, key=lambda x: x[0], reverse=True)[0][1]
            url = best.get('full_physical_path', '')
            if not url:
                continue
            fmt = 'hls' if 'http_h264' in atype else 'mpd'
            if 'usp_dashcenc_h264' in atype:
                try:
                    resp = self.api_client.raw_request('HEAD', url, allow_redirects=False)
                    if resp is not None and 'location' in resp.headers:
                        url = resp.headers['location']
                except Exception:
                    pass
            return url, fmt
        return None, None

    def _extract_widevine_key(self, pssh_value: str, drm_token: str,
                              key_id_hex: Optional[str] = None) -> Optional[str]:
        """Extract Widevine decryption key using local pywidevine CDM.

        Sends the license challenge directly to lic.drmtoday.com with the
        supplied DRM token — no external key-extraction API required.
        When *key_id_hex* is given, the matching key is preferred over the
        first one (a license can carry several KIDs).
        Returns a ``kid:key_hex`` string on success, or None on failure.
        """
        try:
            from pywidevine.cdm import Cdm
            from pywidevine.device import Device
            from pywidevine.pssh import PSSH
        except ImportError:
            logger.error("❌ [SixPlay] pywidevine not installed — cannot extract Widevine key")
            return None

        # Locate the WVD device file
        wvd_candidates = [
            "app/providers/fr/device.wvd",
            "./device.wvd",
            os.path.expanduser("~/.pywidevine/device.wvd"),
        ]
        device = None
        for path in wvd_candidates:
            if os.path.exists(path):
                try:
                    device = Device.load(path)
                    logger.debug("✅ [SixPlay] WVD device loaded from %s", path)
                    break
                except Exception as load_err:
                    logger.warning("⚠️ [SixPlay] Failed to load WVD %s: %s", path, load_err)

        if not device:
            logger.error("❌ [SixPlay] No valid WVD device file found")
            return None

        session_id = None
        try:
            logger.debug("🔑 [SixPlay] Extracting Widevine key (local pywidevine)...")
            logger.debug("📋   PSSH: %s...", pssh_value[:50])

            pssh = PSSH(pssh_value)
            cdm = Cdm.from_device(device)
            session_id = cdm.open()

            challenge = cdm.get_license_challenge(session_id, pssh)
            logger.debug("📋 [SixPlay] License challenge generated: %d bytes", len(challenge))

            license_url = f"{DRM_LICENSE_URL}?specConform=true"
            headers = {
                "User-Agent": DRM_UA,
                "x-dt-auth-token": drm_token,
                "Content-Type": "application/octet-stream",
            }

            response = self.session.post(license_url, data=challenge, headers=headers, timeout=15)
            logger.debug("📋 [SixPlay] License server: %s", response.status_code)

            if response.status_code != 200:
                logger.error("❌ [SixPlay] License server error %s: %s", response.status_code, response.text[:300])
                return None

            cdm.parse_license(session_id, response.content)

            content_keys = {
                str(k.kid).replace('-', '').lower(): k.key.hex()
                for k in cdm.get_keys(session_id)
                if getattr(k, 'type', None) == 'CONTENT'
            }
            if not content_keys:
                logger.error("❌ [SixPlay] No CONTENT keys found in license response")
                return None

            wanted = (key_id_hex or '').lower()
            if wanted and wanted not in content_keys:
                logger.warning("⚠️ [SixPlay] KID %s absent from license (%d key(s)) — using first",
                               wanted, len(content_keys))
            kid_hex = wanted if wanted in content_keys else next(iter(content_keys))
            logger.debug("✅ [SixPlay] Widevine key extracted: %s:%s", kid_hex, content_keys[kid_hex])
            return f"{kid_hex}:{content_keys[kid_hex]}"

        except Exception as e:
            logger.error("❌ [SixPlay] Widevine key extraction failed: %s", e)
            return None
        finally:
            if session_id is not None and 'cdm' in locals():
                try:
                    cdm.close(session_id)
                except Exception:
                    pass

    def _print_download_command(self, video_url: str, decryption_key: str, content_id: str):
        """Print N_m3u8DL-RE download command with decryption key.
        
        Args:
            video_url: URL to the MPD manifest
            decryption_key: Widevine decryption key
            content_id: Content identifier for save name
        """
        try:
            # Clean content ID for filename
            clean_name = content_id.replace(":", "_").replace("/", "_").replace("\\", "_")
            
            # Truncate URL for display (keep first 100 chars)
            display_url = video_url[:100] + "..." if len(video_url) > 100 else video_url
            
            logger.debug("\n📥 N_m3u8DL-RE Download Command:")
            logger.debug('./N_m3u8DL-RE "%s" --save-name "%s" --select-video best --select-audio all --select-subtitle all -mt -M format=mkv --log-level OFF --binary-merge --key %s', video_url, clean_name, decryption_key)
            logger.debug("\n🔗 URL: %s", display_url)
            logger.debug("🔑 Key: %s", decryption_key)
            logger.debug("💾 Save as: %s", clean_name)
            
        except Exception as e:
            logger.error("❌ [SixPlay] Error printing download command: %s", e)


    @safe_provider_call(default={})
    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Dict:
        program_id = show_info.get('api_id') or self._find_program_id(show_id)
        if not program_id:
            return {}
        program_data = self._cached_payload(
            f"program:{program_id}", lambda: self._fetch_program(show_id, program_id)
        )
        return self._images_from_program(program_data, show_info) if program_data else {}

    def _fetch_program(self, show_id: str, program_id: str) -> Optional[Dict]:
        url = f"{self.api_url}/programs/{program_id}?with=links,subcats,rights"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = self.api_client.raw_request('GET', url, headers=self._merge_ip_headers(headers))
        if response is None or response.status_code != 200:
            status = response.status_code if response is not None else "no response"
            logger.error("❌ [SixPlay] Failed to get program data for %s: %s", show_id, status)
            return None
        return response.json()

    def _images_from_program(self, program_data: Dict, show_info: Dict) -> Dict:
        """Map the 6play program payload onto show fields. Precedence: _pick_fields."""
        keys = {
            img.get('role'): img.get('external_key')
            for img in (program_data.get('images') or [])
            if img.get('external_key')
        }
        candidates = {field: [IMAGE_URL.format(keys[r]) for r in roles if r in keys]
                      for field, roles in self._IMAGE_ROLES.items()}
        diffusions = program_data.get('next_diffusions') or []
        # No channel field exists: the upcoming broadcast names it ("M6"), and
        # the service code ("m6replay") covers shows with nothing scheduled.
        service = (program_data.get('service_display') or {}).get('code') or ''
        genre = (program_data.get('program_type_wording') or {}).get('singular') or ''
        year = program_data.get('year_production') or ''
        candidates.update({
            'description': [program_data.get('description'), program_data.get('summary')],
            'channel': [diffusions[0].get('channel') if diffusions else None,
                        service.replace('replay', '').upper() or None],
            'genres': [[genre.capitalize()] if genre else None],
            'year': [int(year) if str(year).isdigit() else None],
            'rating': [(program_data.get('csa') or {}).get('label')],
        })
        return self._pick_fields(candidates, show_info)
    
    def _find_program_id(self, show_id: str) -> Optional[str]:
        """Cached wrapper around :meth:`_resolve_program_id`.

        The lookup pulls the whole first-letter program list (limit=999), and a
        single detail-page load asks for the ID twice — once for the episodes,
        once for the artwork. Cache it for the programs TTL.
        """
        key = CacheKeys.provider_resource(self.provider_name, f"program_id:{show_id}")
        program_id = cache.get(key)
        if program_id is None:
            program_id = self._resolve_program_id(show_id)
            if program_id:
                cache.set(key, program_id, ttl=CacheTTL.PROGRAMS)
        return program_id

    def _resolve_program_id(self, show_id: str) -> Optional[str]:
        """Find the program ID for a given show using the 6play programs API.

        Strategy:
        1. Look up the show's display name from programs.json (e.g. "66 minutes").
        2. Query the 6play programs API filtered by the first letter of that name
           (inspired by the Catch-up TV & More plugin's URL_ALL_PROGRAMS approach).
        3. Match the API's ``title`` against the show name (exact then partial).
        4. Fall back to Algolia search if the programs API fails.
        """

        # ------------------------------------------------------------------
        # Resolve the human-readable show name from programs.json
        # ------------------------------------------------------------------
        show_name = None
        if show_id in self.shows:
            show_name = self.shows[show_id].get('name')
        if not show_name:
            # Derive a reasonable search term from the slug
            show_name = show_id.replace('-', ' ')

        def _normalize(s: str) -> str:
            """Lowercase, collapse hyphens/colons/extra spaces for comparison."""
            return re.sub(r'\s+', ' ', s.lower().replace('-', ' ').replace(':', ' ')).strip()

        norm_search = _normalize(show_name)

        # ------------------------------------------------------------------
        # Strategy 1 – 6play programs API (universal, no hard-coded mapping)
        # ------------------------------------------------------------------
        try:
            first_letter = show_name[0].lower() if show_name else 'a'
            # '@' is used by the API for names starting with a digit / special char
            if not first_letter.isalpha():
                first_letter = '@'

            programs_url = (
                "https://android.middleware.6play.fr/6play/v2/platforms/"
                "m6group_androidmob/services/6play/programs"
            )
            params = {
                'limit': '999',
                'offset': '0',
                'csa': '6',
                'firstLetter': first_letter,
                'with': 'rights',
            }
            headers = {
                'User-Agent': get_random_windows_ua(),
                'x-customer-name': 'm6web',
            }

            logger.debug("🔍 [SixPlay] Searching programs API for '%s' (letter=%s)", show_name, first_letter)
            response = self.api_client.raw_request('GET',
                programs_url,
                params=params,
                headers=self._merge_ip_headers(headers),
                timeout=10,
            )

            if response is not None and response.status_code == 200:
                programs = response.json()
                partial_match = None

                for prog in programs:
                    prog_title = prog.get('title', '')
                    prog_id = str(prog.get('id', ''))
                    norm_title = _normalize(prog_title)

                    if norm_title == norm_search:
                        logger.debug("✅ [SixPlay] Programs API exact match: '%s' (ID: %s)", prog_title, prog_id)
                        return prog_id
                    if not partial_match and (norm_search in norm_title or norm_title in norm_search):
                        partial_match = (prog_id, prog_title)

                if partial_match:
                    logger.debug("✅ [SixPlay] Programs API partial match: '%s' (ID: %s)", partial_match[1], partial_match[0])
                    return partial_match[0]

                logger.warning("⚠️ [SixPlay] Programs API returned no match for '%s', trying Algolia…", show_name)
            else:
                status = response.status_code if response is not None else "no response"
                logger.warning("⚠️ [SixPlay] Programs API HTTP %s, trying Algolia…", status)
        except Exception as e:
            logger.error("⚠️ [SixPlay] Programs API error: %s, trying Algolia…", e)

        # ------------------------------------------------------------------
        # Strategy 2 – Algolia search (fallback)
        # ------------------------------------------------------------------
        try:
            algolia_hosts = [
                'nhacvivxxk-dsn.algolia.net',
                'NHACVIVXXK-1.algolianet.com',
                'NHACVIVXXK-2.algolianet.com',
                'NHACVIVXXK-3.algolianet.com',
            ]
            search_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'x-algolia-api-key': '6ef59fc6d78ac129339ab9c35edd41fa',
                'x-algolia-application-id': 'NHACVIVXXK',
            }
            search_data = {
                'requests': [{
                    'indexName': 'rtlmutu_prod_bedrock_layout_items_v2_m6web_main',
                    'query': show_name,
                    'params': 'clickAnalytics=true&hitsPerPage=10&facetFilters=[["metadata.item_type:program"], ["metadata.platforms_assets:m6group_web"]]',
                }]
            }

            response = None
            for host in algolia_hosts:
                try:
                    logger.debug("🔍 [SixPlay] Trying Algolia host: %s", host)
                    response = self.session.post(
                        f'https://{host}/1/indexes/*/queries',
                        headers=self._merge_ip_headers(search_headers),
                        json=search_data,
                        timeout=5,
                    )
                    if response.status_code == 200:
                        break
                except Exception as e:
                    logger.error("⚠️ [SixPlay] Error with Algolia host %s: %s", host, e)

            if not response or response.status_code != 200:
                logger.error("❌ [SixPlay] All Algolia hosts failed or returned error")
                return None

            data = response.json()
            partial_match = None

            for result in data.get('results', []):
                for hit in result.get('hits', []):
                    title = hit['item']['itemContent']['title']
                    program_id = str(hit['content']['id'])
                    norm_title = _normalize(title)
                    if norm_title == norm_search:
                        logger.debug("✅ [SixPlay] Algolia exact match: '%s' (ID: %s)", title, program_id)
                        return program_id
                    if not partial_match and (norm_search in norm_title or norm_title in norm_search):
                        partial_match = (program_id, title)

            if partial_match:
                logger.debug("✅ [SixPlay] Algolia partial match: '%s' (ID: %s)", partial_match[1], partial_match[0])
                return partial_match[0]

            logger.error("❌ [SixPlay] No program ID found for show '%s' (slug=%s)", show_name, show_id)
            return None
        except Exception as e:
            logger.error("❌ [SixPlay] Error finding program ID for %s: %s", show_id, e)
            return None
    
    @safe_provider_call(default=None)
    def _fetch_raw_videos(self, program_id: str) -> Optional[List[Dict]]:
        url = (
            f"https://android.middleware.6play.fr/6play/v2/platforms/"
            f"m6group_androidmob/services/6play/programs/{program_id}"
            f"/videos?csa=6&with=clips,freemiumpacks&type=vi&limit=999&offset=0"
        )
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = self.api_client.raw_request('GET', url, headers=self._merge_ip_headers(headers))
        if response is not None and response.status_code == 200:
            return response.json() or None
        logger.error(
            "❌ [SixPlay] Failed to get episodes: %s",
            response.status_code if response is not None else "no response",
        )
        return None
    
    @safe_provider_call(default=None)
    def _parse_episode(self, video: Dict, episode_number: int) -> Optional[Dict]:
        video_id = str(video.get('id', ''))
        title = video.get('title', '')
        description = video.get('description', '')
        duration = video.get('duration', '')
        poster = fanart = None
        for img in video.get('images', []):
            if img.get('role') in ['vignette', 'carousel'] and img.get('external_key'):
                poster = fanart = IMAGE_URL.format(img['external_key'])
                break
        broadcast_date, released = None, ""
        if video.get('clips'):
            first_diff = video['clips'][0].get('product', {}).get('first_diffusion', '')
            if first_diff:
                broadcast_date = first_diff[:10]
                released = first_diff.replace(' ', 'T') + '.000Z'
        if not released and video.get('publication_date'):
            pub_date = video['publication_date']
            broadcast_date = broadcast_date or pub_date[:10]
            released = pub_date.replace(' ', 'T') + '.000Z'
        episode_info = {
            "id": f"cutam:fr:6play:episode:{video_id}",
            "type": "episode",
            "title": title,
            "description": description,
            "poster": poster,
            "fanart": fanart,
            "episode": episode_number,
            "duration": duration,
            "broadcast_date": broadcast_date,
        }
        if released:
            episode_info["released"] = released
        return episode_info

