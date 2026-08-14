import json
import logging

from typing import Dict, List, Optional
from fastapi import Request
from app.utils.base_url import get_base_url, get_logo_url
from app.utils.drm.pssh_extractor import extract_pssh_from_mpd
from app.utils.encoding import normalize_key_id
from app.utils.user_agent import get_random_windows_ua

from app.utils.programs_loader import get_programs_for_provider
from app.providers.base_provider import BaseProvider, LiveProviderMixin, safe_provider_call
from app.providers.drm_mixin import DRMProcessedFileMixin
from app.utils.auth_cache import load_auth_state, store_auth_state


logger = logging.getLogger(__name__)

class MyTF1Provider(LiveProviderMixin, DRMProcessedFileMixin, BaseProvider):
    # Class attributes for BaseProvider
    provider_name = "mytf1"
    base_url = "https://www.tf1.fr"
    country = "fr"

    # Metadata
    display_name = "TF1+"
    id_prefix = "cutam:fr:mytf1"
    episode_marker = "episode:"
    catalog_id = "fr-mytf1-replay"
    default_channel = "tf1"

    # TF1 mediainfo API version constants — keep in one place so upgrades are a one-line change
    _LIVE_MEDIAINFO_PARAMS = {
        'context': 'MYTF1', 'pver': '5029000', 'platform': 'web',
        'device': 'desktop', 'os': 'windows', 'osVersion': '10.0',
        'topDomain': 'www.tf1.fr', 'playerVersion': '5.29.0',
        'productName': 'mytf1', 'productVersion': '3.37.0', 'format': 'hls',
    }
    _REPLAY_MEDIAINFO_PARAMS = {
        'context': 'MYTF1', 'pver': '5010000', 'platform': 'web',
        'device': 'desktop', 'os': 'linux', 'osVersion': 'unknown',
        'topDomain': 'www.tf1.fr', 'playerVersion': '5.19.0',
        'productName': 'mytf1', 'productVersion': '3.22.0',
    }
    # Artwork field -> GraphQL decoration key. Verified across all 500 programs
    # in the list: 'image' is always type PORTRAIT (700x933 card), 'background'
    # always type BACKGROUND, and 'logo' is the 450x225 logo-programme PNG.
    # There is no LOGO-typed entry — the logo only ever lives under its own key.
    _DECORATION_IMAGES = {
        "logo": "logo",
        "poster": "image",
        "background": "background",
        "fanart": "background",
    }

    _GIGYA_CONSENT_IDS = (
        "1", "2", "3", "4", "10001", "10003", "10005", "10007", "10013",
        "10015", "10017", "10019", "10009", "10011", "13002", "13001",
        "10004", "10014", "10016", "10018", "10020", "10010", "10012",
        "10006", "10008",
    )

        
    @property
    def needs_ip_forwarding(self) -> bool:
        return True
    
    def __init__(self, request: Optional[Request] = None):
        # Initialize base class (handles credentials, session, proxy_config, mediaflow)
        super().__init__(request)
        
        # TF1-specific API configuration
        self.api_key = "3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk"
        self.api_url = "https://www.tf1.fr/graphql/web"
        self.video_stream_url = "https://mediainfo.tf1.fr/mediainfocombo"
        
        # Log MediaFlow configuration for debugging (already set by base class)
        if self.mediaflow_url:
            logger.debug("✅ [MyTF1] MediaFlow configured: %s...", self.mediaflow_url[:30])
        logger.debug("✅ [MyTF1] MediaFlow Password: %s", '***' if self.mediaflow_password else 'None')
        
        # Get base URL for static assets
        self.static_base = get_base_url(request)

        # TF1-specific auth endpoints
        self.accounts_login = "https://compte.tf1.fr/accounts.login"
        self.accounts_bootstrap = "https://compte.tf1.fr/accounts.webSdkBootstrap"
        self.token_gigya_web = "https://www.tf1.fr/token/gigya/web"
        self.license_base_url = 'https://drm-wide.tf1.fr/proxy?id=%s'
        
        # TF1-specific authentication state
        self.auth_token = None

        # Load shows from external programs.json
        self.shows = get_programs_for_provider('mytf1')
    

    def _build_stream_headers(self, auth_token: str = None, **extra) -> Dict:
        """Build TF1-specific headers for video stream requests, extending the base set."""
        return super()._build_stream_headers(
            auth_token=auth_token or self.auth_token,
            **{
                "accept-language": "fr-FR,fr;q=0.9,en;q=0.8,en-US;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Charset": "UTF-8,*;q=0.5",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-GPC": "1",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
                **extra,
            }
        )

    @staticmethod
    def _validate_tf1_delivery(data: Dict) -> bool:
        """Validate proxy delivery response for TF1 stream endpoints."""
        delivery = data.get('delivery', {})
        return delivery.get('code') == 200 and delivery.get('country', 'US') != 'US'

    def _extract_drm_info(self, delivery: Dict, video_id: str) -> tuple:
        """Extract DRM license URL and headers from delivery response."""
        drm = (delivery.get('drms') or [{}])[0]
        license_url = drm.get('url') or self.license_base_url % video_id
        license_headers = {h['k']: h['v'] for h in drm.get('h', []) if h.get('k') and h.get('v')}
        return license_url, license_headers

    
    def _authenticate(self) -> bool:
        """Authenticate with TF1+ using provided credentials with robust error handling"""
        # Reuse a token cached by a previous request (avoids 3 login round-trips
        # per stream request — provider instances are per-request).
        cached = load_auth_state(self.provider_name)
        if cached and cached.get('auth_token'):
            self.auth_token = cached['auth_token']
            self._authenticated = True
            logger.debug("✅ [MyTF1] Using cached auth token")
            return True

        if not self.credentials.get('login') or not self.credentials.get('password'):
            logger.error("❌ [MyTF1] MyTF1 credentials not provided")
            return False

        try:
            logger.debug("✅ [MyTF1] Attempting MyTF1 authentication...")
            
            # Bootstrap
            bootstrap_headers = {
                "referrer": self.base_url
            }
            bootstrap_params = {
                'apiKey': self.api_key,
                'pageURL': 'https%3A%2F%2Fwww.tf1.fr%2F',
                'sd': 'js_latest',
                'sdkBuild': '13987',
                'format': 'json'
            }
            
            # Authentication calls should be DIRECT - not through proxy
            logger.debug("✅ [MyTF1] Making DIRECT bootstrap request to: %s", self.accounts_bootstrap)
            bootstrap_data = self.api_client.get(self.accounts_bootstrap, headers=self._build_ip_headers(bootstrap_headers), params=bootstrap_params)
            if not bootstrap_data:
                logger.error("❌ [MyTF1] Bootstrap failed")
                return False
            
            # Login
            headers_login = {
                "Content-Type": "application/x-www-form-urlencoded",
                "referrer": self.base_url
            }
            
            post_body_login = {
                "loginID": self.credentials['login'],
                "password": self.credentials['password'],
                "sessionExpiration": 31536000,
                "targetEnv": "jssdk",
                "include": "identities-all,data,profile,preferences,",
                "includeUserInfo": "true",
                "loginMode": "standard",
                "lang": "fr",
                "APIKey": self.api_key,
                "sdk": "js_latest",
                "authMode": "cookie",
                "pageURL": self.base_url,
                "sdkBuild": 13987,
                "format": "json"
            }
            
            # Login calls should be DIRECT - not through proxy
            logger.debug("✅ [MyTF1] Making DIRECT login request to: %s", self.accounts_login)
            login_data = self.api_client.post(self.accounts_login, headers=self._build_ip_headers(headers_login), data=post_body_login)
            
            if login_data and login_data.get('errorCode') == 0:
                # Get Gigya token
                headers_gigya = {
                    "content-type": "application/json"
                }
                body_gigya = {
                    "uid": login_data['userInfo']['UID'],
                    "signature": login_data['userInfo']['UIDSignature'],
                    "timestamp": int(login_data['userInfo']['signatureTimestamp']),
                    "consent_ids": list(self._GIGYA_CONSENT_IDS),
                }
                
                # JWT token calls should be DIRECT - not through proxy
                logger.debug("✅ [MyTF1] Making DIRECT JWT token request to: %s", self.token_gigya_web)
                jwt_data = self.api_client.post(self.token_gigya_web, headers=self._build_ip_headers(headers_gigya), data=body_gigya)
                
                if jwt_data and 'token' in jwt_data:
                    self.auth_token = jwt_data['token']
                    self._authenticated = True
                    store_auth_state(
                        self.provider_name,
                        {'auth_token': self.auth_token},
                        token_for_ttl=self.auth_token,
                    )
                    logger.debug("✅ [MyTF1] MyTF1 authentication successful!")
                    logger.debug("✅ [MyTF1] Session token generated: %s...", self.auth_token[:20])
                    return True
                else:
                    logger.error("❌ [MyTF1] Failed to get Gigya token")
            else:
                logger.error("❌ [MyTF1] MyTF1 login failed: %s", login_data.get('errorMessage', 'Unknown error') if login_data else 'No response')
                
        except Exception as e:
            logger.error("❌ [MyTF1] Error during MyTF1 authentication: %s", e)
        
        return False

    # _build_show_metadata: the base implementation already filters None values
    # out of the API-metadata extras, so no override is needed.

    def get_live_channels(self) -> List[Dict]:
        """Get list of live TV channels from TF1+"""
        def ch(name, slug, desc):
            logo = get_logo_url("fr", slug, self.request)
            return {"id": f"cutam:fr:mytf1:{slug}", "type": "channel", "name": name, "poster": logo, "logo": logo, "description": desc}
        return [
            ch("TF1", "tf1", "Première chaîne de télévision privée française"),
            ch("TMC", "tmc", "Chaîne de télévision du groupe TF1"),
            ch("TFX", "tfx", "Chaîne de divertissement du groupe TF1"),
            ch("TF1 Séries Films", "tf1-series-films", "Chaîne dédiée aux séries et films du groupe TF1"),
        ]
    
    def _fetch_episodes_raw(self, slug: str) -> Optional[List[Dict]]:
        """Auth, resolve program via GraphQL, and return raw video items."""
        if not self._authenticated and not self._authenticate():
            logger.error("❌ [MyTF1] MyTF1 authentication failed")
            return None

        headers = {
            'content-type': 'application/json',
            'referer': 'https://www.tf1.fr/programmes-tv',
            'User-Agent': get_random_windows_ua(),
            'origin': self.base_url,
            'accept-language': 'fr-FR,fr;q=0.9',
            'accept': 'application/json, text/plain, */*',
            'authorization': f'Bearer {self.auth_token}'
        }

        program = self._find_program(slug, headers)
        if not program:
            return None

        return self._fetch_raw_video_items(program['slug'], headers)

    def _fallback_episodes(self, slug: str) -> List[Dict]:
        logger.debug("✅ [MyTF1] Using fallback episode for %s", slug)
        return [self._create_fallback_episode(slug)]

    # The programs list is the only TF1 endpoint carrying a show's logo,
    # description and categories — programBySlug returns none of them
    # reliably — and it can only be filtered by channel, never by name or
    # slug.  The unfiltered page (the 500 most prominent programs) is tried
    # first, the four channel lists after.  Every list is cached, so the
    # second show usually costs no request at all.
    _PROGRAM_LIST_FILTERS = (None, "tf1", "tmc", "tfx", "tf1-series-films")

    def _find_program(self, slug: str, headers: Dict = None) -> Optional[Dict]:
        """The TF1 programs-list entry for *slug*.

        programs.json carries TF1's own slug, so that is the match; the name it
        also carries is the fallback for a show TF1 has since re-slugged.  The
        entry holds the artwork and the metadata, so the catalogue, the detail
        page and the episode lookup all resolve a show exactly once.
        """
        show_name = (self.shows.get(slug) or {}).get('name', slug.replace('-', ' ')).lower()
        headers = headers or {
            'content-type': 'application/json',
            'referer': 'https://www.tf1.fr/programmes-tv',
        }
        for channel in self._PROGRAM_LIST_FILTERS:
            for program in self._get_graphql_programs_list(headers, channel) or []:
                if program.get('slug') == slug or program.get('name', '').lower() == show_name:
                    return program
        logger.error("❌ [MyTF1] Program not found for show: %s", slug)
        return None

    def _get_graphql_programs_list(self, headers: Dict, channel_filter: str = None) -> Optional[List[Dict]]:
        """Fetch a TF1 programs list from the GraphQL API, with caching."""
        variables = {
            "context": {
                "persona": "PERSONA_2", "application": "WEB",
                "device": "DESKTOP", "os": "WINDOWS",
            },
            "filter": {"channel": channel_filter} if channel_filter else {},
            "offset": 0,
            "limit": 500,
        }
        params = {'id': '483ce0f', 'variables': json.dumps(variables, separators=(',', ':'))}

        def fetch():
            data = self.api_client.get(self.api_url, headers=self._build_ip_headers(headers),
                                       params=params, max_retries=3)
            if data and 'data' in data and 'programs' in data['data']:
                return data['data']['programs'].get('items', [])
            return None

        return self._cached_payload(f"graphql_programs:{channel_filter or 'all'}", fetch)

    @safe_provider_call(default=None)
    def _fetch_raw_video_items(self, program_slug: str, headers: Dict) -> Optional[List[Dict]]:
        """Fetch a program's raw replay video items from the TF1 GraphQL API."""
        variables = {
            "programSlug": program_slug,
            "offset": 0,
            "limit": 50,
            "sort": {"type": "DATE", "order": "DESC"},
            "types": ["REPLAY"],
        }
        params = {
            'id': 'a6f9cf0e',
            'variables': json.dumps(variables, separators=(',', ':')),
        }
        data = self._fetch_with_proxy_fallback(
            self.api_url, params=params, headers=self._build_ip_headers(headers),
        )
        if data and 'data' in data and data['data'].get('programBySlug'):
            program_data = data['data']['programBySlug']
            video_items = (program_data.get('videos') or {}).get('items') or []
            if video_items:
                logger.debug("✅ [MyTF1] Found %d video items", len(video_items))
                return video_items
            logger.error("❌ [MyTF1] No videos found in programBySlug: %s", list(program_data.keys()))
        else:
            logger.error("❌ [MyTF1] No programBySlug in response: %s", list(data.keys()) if data else 'No data')
        return None

    @safe_provider_call(default=None)
    def _parse_episode(self, video: Dict, episode_number: int) -> Optional[Dict]:
        episode_id = video.get('id')
        title = video.get('decoration', {}).get('label', 'Unknown Title')
        description = video.get('decoration', {}).get('description', '')
        duration = video.get('playingInfos', {}).get('duration', '')
        released = video.get('date', '')

        poster = None
        if 'decoration' in video and 'images' in video['decoration']:
            try:
                images = video['decoration']['images']
                poster = images[1]['sources'][0].get('url', '') if len(images) > 1 else images[0]['sources'][0].get('url', '')
            except (IndexError, KeyError):
                pass
        if not poster and 'image' in video and 'sourcesWithScales' in video['image']:
            poster = video['image']['sourcesWithScales'][0].get('url', '')

        return {
            "id": f"cutam:fr:mytf1:episode:{episode_id}",
            "title": title,
            "description": description,
            "poster": poster,
            "fanart": None,
            "duration": duration,
            "released": released,
            "type": "episode",
            "episode_number": episode_number,
            "season": 1,
            "episode": episode_number
        }
    

    @staticmethod
    def _format_stream_title(manifest_type: str, program: Optional[str], fallback: str) -> str:
        """Format the ``[HLS|MPD] <title>`` label shown in Stremio."""
        label = 'HLS' if manifest_type == 'hls' else 'MPD'
        return f"[{label}] {program}" if program else f"[{label}] {fallback}"

    def _build_live_stream_info(self, mediainfo: Dict, video_id: str, channel_name: str) -> Dict:
        """Assemble the live stream dict from a mediainfo response.

        Shares _extract_drm_info / _build_mediaflow_proxied_url with the
        replay path instead of re-implementing them inline.
        """
        delivery = mediainfo['delivery']
        video_url = delivery['url']
        logger.debug("✅ [MyTF1] Stream URL obtained: %s...", video_url[:50])

        license_url, license_headers = self._extract_drm_info(delivery, video_id)
        manifest_type = self._detect_manifest_type(video_url)
        headers = self._build_stream_headers()

        proxied = self._build_mediaflow_proxied_url(
            video_url, manifest_type,
            extra_headers={'authorization': f"Bearer {self.auth_token}"},
            license_url=license_url, license_headers=license_headers,
        )

        current_program = None
        if 'media' in mediainfo:
            current_program = mediainfo['media'].get('programName') or mediainfo['media'].get('title', '')
            logger.debug("✅ [MyTF1] Current program: %s", current_program)

        stream_info = {
            "url": proxied or video_url,
            "manifest_type": manifest_type,
            "title": self._format_stream_title(manifest_type, current_program, channel_name.upper()),
            "headers": headers,
        }
        if license_url:
            stream_info["licenseUrl"] = license_url
            if license_headers:
                stream_info["licenseHeaders"] = license_headers
        return stream_info

    def get_channel_stream_url(self, channel_id: str) -> Optional[List[Dict]]:
        """Get stream URL for a specific channel with robust error handling and fallbacks"""
        channel_name = channel_id.split(":")[-1]

        try:
            logger.debug("✅ [MyTF1] Getting stream for channel: %s", channel_name)
            if not self._authenticated and not self._authenticate():
                logger.error("❌ [MyTF1] MyTF1 authentication failed")
                return None

            video_id = f'L_{channel_name.upper()}'
            mediainfo = self._fetch_mediainfo(video_id, self._LIVE_MEDIAINFO_PARAMS)

            if not mediainfo:
                logger.error("❌ [MyTF1] MyTF1 API error: No valid JSON from mediainfo (proxy and direct attempts failed)")
                return None

            if mediainfo.get('delivery', {}).get('code', 500) > 400:
                logger.error("❌ [MyTF1] MyTF1 delivery error: %s", mediainfo.get('delivery', {}).get('code'))
                return None

            return [self._build_live_stream_info(mediainfo, video_id, channel_name)]

        except Exception as e:
            logger.error("❌ [MyTF1] Error getting stream for %s: %s", channel_name, e)
            return None

    def _fetch_mediainfo(self, media_id: str, mediainfo_params: Dict) -> Optional[Dict]:
        """Fetch delivery data from the TF1 mediainfo API with proxy fallback."""
        headers = self._build_stream_headers()
        url = f"{self.video_stream_url}/{media_id}"
        return self._fetch_with_proxy_fallback(
            url, params=mediainfo_params.copy(), headers=headers,
            validate=self._validate_tf1_delivery
        )

    def _fetch_episode_delivery(self, episode_id: str) -> Optional[Dict]:
        """Fetch delivery data for a replay episode."""
        return self._fetch_mediainfo(episode_id, self._REPLAY_MEDIAINFO_PARAMS)

    def _extract_drm_keys(self, video_url, license_url, episode_id) -> dict:
        """Extract DRM keys using TF1DRMExtractor. Returns dict of kid:key pairs."""
        drm_keys_dict = {}
        try:
            from app.providers.fr.tf1_drm_key_extractor import TF1DRMExtractor
            logger.debug("✅ [MyTF1] Extracting DRM keys for TF1 replay...")
            
            extractor = TF1DRMExtractor(wvd_path="app/providers/fr/device.wvd")
            drm_keys_dict = extractor.get_keys(
                video_url=video_url,
                license_url=license_url,
                verbose=False
            )
            
            if drm_keys_dict:
                logger.debug("✅ [MyTF1] Extracted %d DRM key(s)", len(drm_keys_dict))
                for kid, key in drm_keys_dict.items():
                    logger.debug("   KID: %s -> KEY: %s", kid, key)
            else:
                logger.warning("⚠️ [MyTF1] No DRM keys extracted")
                
        except ImportError:
            logger.warning("⚠️ [MyTF1] TF1 DRM extractor not available (pywidevine not installed)")
        except Exception as drm_error:
            logger.error("⚠️ [MyTF1] DRM key extraction failed: %s", drm_error)
            
        return drm_keys_dict

    def _select_drm_key(self, video_url: str, drm_keys: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Pick the single ``key_id``/``key`` pair MediaFlow decrypts with.

        MediaFlow takes one pair, a license can carry several. With one key
        there is nothing to choose; with several, the manifest's ``default_KID``
        decides (one extra manifest fetch, only in that case).
        """
        if not drm_keys:
            return None
        kid = next(iter(drm_keys))
        if len(drm_keys) > 1:
            _pssh, _mpd, drm_info = extract_pssh_from_mpd(video_url, "MyTF1")
            default_kid = normalize_key_id((drm_info or {}).get('key_id'))
            if default_kid in drm_keys:
                kid = default_kid
            else:
                logger.warning("⚠️ [MyTF1] default_KID %s not in license (%d key(s)) — using first",
                               default_kid, len(drm_keys))
        return {"key_id": kid, "key": drm_keys[kid]}

    def _build_direct_stream(self, video_url, license_url, license_headers, headers,
                             drm_keys, manifest_type: str = 'mpd') -> Dict:
        """MediaFlow-proxied stream straight from the TF1 CDN.

        With a locally extracted Widevine key MediaFlow decrypts the CENC
        segments itself; without one it is pointed at the TF1 license proxy.
        """
        key_params = self._select_drm_key(video_url, drm_keys)
        if key_params:
            logger.debug("✅ [MyTF1] Direct stream decrypted by MediaFlow (KID %s)", key_params["key_id"])
            license_url = license_headers = None

        proxied = self._build_mediaflow_proxied_url(
            video_url, manifest_type,
            extra_headers={'authorization': f"Bearer {self.auth_token}"},
            license_url=license_url, license_headers=license_headers,
            extra_params=key_params,
        )
        stream = {
            "url": proxied or video_url,
            "manifest_type": manifest_type,
            "title": f"🌐 [{manifest_type.upper()}] Direct source (MediaFlow)",
            "headers": headers,
        }
        if license_url:
            stream["licenseUrl"] = license_url
            if license_headers:
                stream["licenseHeaders"] = license_headers
        return stream

    def _build_mediaflow_stream(self, video_url, license_url, license_headers, headers, manifest_type: str) -> list:
        """Build MediaFlow-proxied stream for HLS/non-DRM content."""
        base = {
            "manifest_type": manifest_type, "headers": headers,
            **({"licenseUrl": license_url} if license_url else {}),
            **({"licenseHeaders": license_headers} if license_headers else {}),
        }
        proxied = self._build_mediaflow_proxied_url(
            video_url, manifest_type,
            extra_headers={'authorization': f"Bearer {self.auth_token}"},
            license_url=license_url, license_headers=license_headers,
        )
        return [{"url": proxied or video_url, **base}]

    def get_episode_stream_url(self, episode_id: str) -> Optional[List[Dict]]:
        """Get streams for a replay episode: pre-processed file(s) *and* the direct source.

        The TorBox/Real-Debrid copy is listed first when it exists; the
        MediaFlow-proxied original is always offered alongside it, so playback
        works before (or without) background DRM processing.
        """
        actual_id = self._extract_after_marker(episode_id)

        try:
            existing = self._check_processed_file(actual_id) or []

            if not self._authenticated and not self._authenticate():
                return existing or None

            delivery_data = self._fetch_episode_delivery(actual_id)
            if not delivery_data or delivery_data.get('delivery', {}).get('code', 500) > 400:
                return existing or None

            video_url = delivery_data['delivery']['url']
            license_url, license_headers = self._extract_drm_info(delivery_data['delivery'], actual_id)
            headers = self._build_stream_headers()
            manifest_type = self._detect_manifest_type(video_url)

            if manifest_type == 'mpd' and license_url:
                drm_keys = self._extract_drm_keys(video_url, license_url, actual_id)
                streams = [self._build_direct_stream(
                    video_url, license_url, license_headers, headers, drm_keys, manifest_type
                )]
                # Don't re-download something that is already processed.
                if drm_keys and not existing:
                    try:
                        streams.append(self._start_drm_processing(
                            video_url, actual_id,
                            keys=[f"{kid}:{key}" for kid, key in drm_keys.items()],
                        ))
                    except Exception as e:
                        logger.error("⚠️ [MyTF1] Background processing failed: %s", e)
                return existing + streams

            return existing + self._build_mediaflow_stream(
                video_url, license_url, license_headers, headers, manifest_type
            )
        except Exception as e:
            logger.error("❌ [MyTF1] Error getting episode stream: %s", e, exc_info=True)
            return None

    @staticmethod
    def _decoration_url(decoration: Dict, key: str) -> Optional[str]:
        """Largest source URL of a decoration image — sources come size-descending."""
        sources = (decoration.get(key) or {}).get('sources') or []
        return (sources[0].get('url') or None) if sources else None

    @safe_provider_call(default={})
    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Dict:
        program = self._find_program(show_id)
        if not program:
            return {}
        decoration = program.get('decoration') or {}
        candidates = {field: [self._decoration_url(decoration, key)]
                      for field, key in self._DECORATION_IMAGES.items()}
        # ponytail: no rating here — TF1 rates videos, not programs, and reading
        # one would cost a second request per show. Falls back to DEFAULT_RATING.
        candidates.update({
            'description': [decoration.get('description')],
            'channel': [(program.get('mainChannel') or {}).get('label')],
            'genres': [[c['label'] for c in program.get('categories') or [] if c.get('label')]],
            'year': [int(program['releaseYear']) if str(program.get('releaseYear')).isdigit() else None],
        })
        return self._pick_fields(candidates, show_info)
    
