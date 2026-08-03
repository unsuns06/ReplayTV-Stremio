import logging
import html
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import Request
from app.providers.fr.metadata import metadata_processor, image_extractor
from app.utils.base_url import get_base_url, get_logo_url
from app.utils.programs_loader import get_programs_for_provider
from app.providers.base_provider import BaseProvider, LiveProviderMixin, safe_provider_call

logger = logging.getLogger(__name__)

_DESC_PUBLIC = "Chaîne de télévision française de service public"
# (slug, display_name, logo_key, fallback_broadcast_id, description)
_CHANNELS = [
    ("france-2",   "France 2",    "france2",    "006194ea-117d-4bcf-94a9-153d999c59ae", _DESC_PUBLIC),
    ("france-3",   "France 3",    "france3",    "29bdf749-7082-4426-a4f3-595cc436aa0d", _DESC_PUBLIC),
    ("france-4",   "France 4",    "france4",    "9a6a7670-dde9-4264-adbc-55b89558594b", _DESC_PUBLIC),
    ("france-5",   "France 5",    "france5",    "45007886-f3ff-4b3e-9706-1ef1014c5a60", _DESC_PUBLIC),
    ("franceinfo", "franceinfo:", "franceinfo", "35be22fb-1569-43ff-857c-99bf81defa2e", "Chaîne d'information continue française de service public"),
]
_FALLBACK_BROADCAST_IDS = {slug: bid for slug, _, _, bid, _ in _CHANNELS}


class FranceTVProvider(LiveProviderMixin, BaseProvider):
    # Class attributes for BaseProvider
    provider_name = "francetv"
    base_url = "https://www.france.tv"
    country = "fr"
    
    # Metadata
    display_name = "France TV"
    id_prefix = "cutam:fr:francetv"
    episode_marker = "episode:"
    catalog_id = "fr-francetv-replay"
    default_channel = "france2"

    
    def __init__(self, request: Optional[Request] = None):
        # Initialize base class (handles credentials, session, proxy_config, mediaflow)
        super().__init__(request)
        
        # France TV specific API endpoints
        self.api_mobile = "https://api-mobile.yatta.francetv.fr"
        self.api_front = "http://api-front.yatta.francetv.fr"
        
        # Get base URL for static assets
        self.static_base = get_base_url(request)
        
        # Load shows from external programs.json
        self.shows = get_programs_for_provider('francetv')
    
    # get_programs comes from the BaseProvider template: it fetches
    # _get_show_api_metadata for every show in parallel and merges the result
    # through _build_show_metadata below.

    def _build_show_metadata(self, slug: str, info: Dict, extra: Dict = None) -> Dict:
        """Build show metadata via the FranceTV metadata processor.

        Unlike the base dict-merge, FranceTV's API metadata contains raw image
        pattern lists that must be transformed (``populate_images``), so the
        merge is delegated to ``enhance_metadata_with_api``.
        """
        show_metadata = metadata_processor.get_show_metadata(f"{self.id_prefix}:{slug}", info)
        if extra:
            show_metadata = metadata_processor.enhance_metadata_with_api(show_metadata, extra)
            if extra.get('logo'):
                show_metadata['logo'] = extra['logo']
        return show_metadata

    @safe_provider_call(default=None)
    def _get_show_api_metadata(self, show_id: str, show_info: Dict) -> Optional[Dict]:
        show_api_id = show_info.get('api_id') or show_info.get('id', show_id)
        api_url = f"{self.api_front}/standard/publish/taxonomies/{show_api_id}"
        data = self.api_client.get(api_url, params={'platform': 'apps'})
        if not data:
            return None
        images = data.get('media_image', {}).get('patterns', []) if 'media_image' in data else []
        extracted = image_extractor.extract(images, {"logo": "logo"})
        return {
            'images': images,
            'description': data.get('description', ''),
            'text': data.get('seo', ''),
            'logo': extracted.get('logo'),
        }

    def enhance_series_meta(self, series_meta: Dict, show_id: str) -> Dict:
        """Enrich series metadata from the France TV API."""
        try:
            programs = get_programs_for_provider(self.provider_name)
            show_data = programs.get(show_id, {})
            provider_metadata = self._get_show_api_metadata(show_id, show_data)
            if provider_metadata:
                series_meta = metadata_processor.enhance_metadata_with_api(series_meta, provider_metadata)
                if provider_metadata.get('logo'):
                    series_meta['logo'] = provider_metadata['logo']
        except Exception as e:
            logger.warning("Could not enhance series metadata for %s: %s", show_id, e)
        return series_meta

    def _get_channel_images(self, channel_id: str) -> Dict[str, str]:
        """Get poster and logo images for a channel from the FranceTV API.
        
        Args:
            channel_id: Channel identifier (e.g., 'france-2', 'franceinfo')
            
        Returns:
            Dict with 'poster' and 'logo' URLs, or empty strings if not found
        """
        try:
            api_url = f"{self.api_front}/standard/publish/taxonomies/{channel_id}"
            params = {'platform': 'apps'}
            
            data = self.api_client.get(api_url, params=params)
            if not data:
                return {'poster': '', 'logo': ''}
            
            images = data.get('media_image', {}).get('patterns', []) if 'media_image' in data else []
            extracted = image_extractor.extract(images, {"poster": "vignette_3x4", "logo": "logo"})
            return {'poster': extracted.get('poster', ''), 'logo': extracted.get('logo', '')}
            
        except Exception as e:
            logger.error("❌ [FranceTV] Error getting channel images for %s: %s", channel_id, e)
            return {'poster': '', 'logo': ''}
    
    def get_live_channels(self) -> List[Dict]:
        """Get live TV channels with dynamic images from France TV API (parallel fetching)."""
        image_results = dict(self._parallel_map(
            lambda ch: (ch[0], self._get_channel_images(ch[0])), _CHANNELS
        ))
        channels = []
        for slug, name, logo_key, _, desc in _CHANNELS:
            images = image_results.get(slug, {})
            fallback = get_logo_url("fr", logo_key, self.request)
            channels.append({
                "id": f"cutam:fr:francetv:{slug}",
                "type": "channel",
                "name": name,
                "poster": images.get('poster') or fallback,
                "logo": images.get('logo') or fallback,
                "description": desc,
            })
        return channels
    
    def _get_broadcast_id(self, channel_name: str) -> tuple:
        """Look up the live broadcast ID and current programme title for *channel_name*.

        Tries three sources in order:
        1. Mobile API  (``api-mobile.yatta.francetv.fr``)
        2. Front API   (``api-front.yatta.francetv.fr``)
        3. Hard-coded ``fallback_channels`` dict

        Returns:
            ``(broadcast_id, current_program_title)`` — either value may be ``None``.
        """
        broadcast_id = None
        current_program_title = None

        try:
            data = self.api_client.get(
                f"{self.api_mobile}/apps/channels/{channel_name}",
                params={'platform': 'apps'},
            )
            if data:
                for collection in data.get('collections', []):
                    if collection.get('type') == 'live':
                        items = collection.get('items', [])
                        if items:
                            current_program_title = items[0].get('title', '')
                            ch = items[0].get('channel', {})
                            if ch.get('si_id'):
                                broadcast_id = ch['si_id']
                        break
        except Exception as e:
            logger.error("   ⚠️ Mobile API failed: %s", e)

        if not broadcast_id:
            try:
                data = self.api_client.get(f"{self.api_front}/standard/edito/directs")
                if data:
                    for live in data.get('result', []):
                        if live.get('channel') == channel_name:
                            collections = live.get('collection', [])
                            if collections and not current_program_title:
                                current_program_title = collections[0].get('title', '')
                            for m in (collections[0].get('content_has_medias', []) if collections else []):
                                if 'si_direct_id' in m.get('media', {}):
                                    broadcast_id = m['media']['si_direct_id']
                                    break
                            break
            except Exception as e:
                logger.error("   ⚠️ Front API failed: %s", e)

        if not broadcast_id:
            broadcast_id = _FALLBACK_BROADCAST_IDS.get(channel_name)

        return broadcast_id, current_program_title

    @safe_provider_call(default=None)
    def get_channel_stream_url(self, channel_id: str) -> Optional[List[Dict]]:
        logger.debug("🔍 [FranceTV] Getting live stream for %s", channel_id)
        channel_name = channel_id.split(":")[-1]
        broadcast_id, current_program_title = self._get_broadcast_id(channel_name)

        if not broadcast_id:
            logger.error("   ❌ No broadcast ID found for %s", channel_name)
            return None

        video_url = f"https://k7.ftven.fr/videos/{broadcast_id}"
        params = {
            'country_code': 'FR',
            'os': 'androidtv',
            'diffusion_mode': 'tunnel_first',
            'offline': 'false',
        }

        video_data = self.api_client.get(video_url, params=params, max_retries=2)

        if not (video_data and 'video' in video_data):
            logger.error("   ❌ No 'video' key in response or API failed")
            return None

        video_info = video_data['video']
        token_field = video_info.get('token', {})
        if isinstance(token_field, dict):
            url_token = token_field.get('akamai', "https://hdfauth.ftven.fr/esi/TA")
        else:
            url_token = token_field or "https://hdfauth.ftven.fr/esi/TA"

        token_data = self.api_client.get(url_token, params={'format': 'json', 'url': video_info.get('url', '')}, max_retries=2)

        if not (token_data and 'url' in token_data and token_data['url']):
            logger.error("   ❌ Token API failed or no URL found")
            return None

        final_url = token_data['url']
        manifest_type = self._detect_manifest_type(final_url)
        format_label = 'HLS' if manifest_type == 'hls' else 'MPD'
        stream_title = f"[{format_label}] {current_program_title}" if current_program_title else f"[{format_label}] {channel_name.upper()}"
        return [{"url": final_url, "manifest_type": manifest_type, "title": stream_title}]
    

    def _fetch_episodes_raw(self, slug: str) -> Optional[List[Dict]]:
        """Fetch and filter raw episode list from France TV API."""
        show_info = self.shows[slug]
        api_show_id = show_info.get('api_id') or show_info.get('id', slug)
        api_url = f"{self.api_front}/standard/publish/taxonomies/{api_show_id}/contents/"
        params = {'size': 20, 'page': 0, 'filter': "with-no-vod,only-visible", 'sort': "begin_date:desc"}
        data = self.api_client.get(api_url, params=params)
        if not data or 'result' not in data:
            logger.error("❌ [FranceTV] API failed or no result for %s", slug)
            return None
        filtered = [v for v in data['result'] if v.get('type') in ('integrale', 'extrait')]
        return filtered or None

    def _fallback_episodes(self, slug: str) -> List[Dict]:
        logger.warning("⚠️ [FranceTV] Using fallback episode for %s", slug)
        return [self._create_fallback_episode(slug)]
    
    @safe_provider_call(default=None)
    def _parse_episode(self, episode_data: Dict, episode_number: int) -> Optional[Dict]:
        title = episode_data.get('title', episode_data.get('label', 'Unknown Title'))
        raw_description = episode_data.get('text', episode_data.get('description', ''))
        description = html.unescape(raw_description) if raw_description else ''

        # Collect all image patterns from both API sources, then extract in one pass (§13)
        patterns = []
        for m in episode_data.get('content_has_medias', []):
            if m.get('type') == 'image':
                patterns.extend(m.get('media', {}).get('patterns', []))
        patterns.extend(episode_data.get('media_image', {}).get('patterns', []))
        imgs = image_extractor.extract(patterns, {
            'poster': 'vignette_16x9',
            'fanart': 'background_16x9',
            'poster_sq': 'carre',
        })
        poster = imgs.get('poster') or imgs.get('poster_sq')
        fanart = imgs.get('fanart') or imgs.get('poster') or imgs.get('poster_sq')

        broadcast_id = None
        for medium in episode_data.get('content_has_medias', []):
            if medium.get('type') == 'main':
                broadcast_id = medium.get('media', {}).get('si_id')
                break
        if not broadcast_id:
            broadcast_id = episode_data.get('id')
        if not broadcast_id:
            return None

        air_date = episode_data.get('begin_date', '')
        if air_date and 'T' in air_date:
            air_date = air_date.split('T')[0]

        released = ""
        first_pub_date = episode_data.get('first_publication_date', '')
        if first_pub_date:
            try:
                released = datetime.fromisoformat(first_pub_date).strftime('%Y-%m-%dT%H:%M:%S.000Z')
            except Exception:
                released = first_pub_date

        episode_meta = {
            "id": f"cutam:fr:francetv:episode:{broadcast_id}",
            "title": title,
            "description": description,
            "poster": poster,
            "fanart": fanart,
            "broadcast_id": broadcast_id,
            "type": "episode",
            "air_date": air_date,
            "released": released,
            "episode_number": episode_number,
            "season": 1,
            "episode": episode_number
        }
        return metadata_processor.enhance_metadata_with_api(episode_meta, episode_data)
    
    @safe_provider_call(default=None)
    def get_episode_stream_url(self, episode_id: str) -> Optional[List[Dict]]:
        broadcast_id = self._extract_after_marker(episode_id)
        video_url = f"https://k7.ftven.fr/videos/{broadcast_id}"
        params = {
            'country_code': 'FR',
            'os': 'androidtv',
            'diffusion_mode': 'tunnel_first',
            'offline': 'false',
        }
        video_data = self.api_client.get(video_url, params=params, max_retries=2)
        if not (video_data and 'video' in video_data):
            logger.error("❌ [FranceTV] Failed to get video info or API failed")
            return None
        stream_url = video_data['video'].get('url')
        if not stream_url:
            logger.error("❌ [FranceTV] No video URL found")
            return None
        token_data = self.api_client.get(
            "https://hdfauth.ftven.fr/esi/TA",
            params={'format': 'json', 'url': stream_url},
            max_retries=2,
        )
        if not (token_data and token_data.get('url')):
            logger.error("❌ [FranceTV] Failed to get stream URL")
            return None
        return [{"url": token_data['url'], "manifest_type": "hls"}]
