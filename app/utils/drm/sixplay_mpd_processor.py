"""MPD manifest processor for 6play DRM content.

Rewrites complex ContentProtection structures into a simplified form
that the MediaFlow proxy can parse without errors.
"""

import xml.etree.ElementTree as ET
from typing import Dict
from urllib.parse import urljoin, urlparse

from app.utils.drm.base import DRMProcessor


class SixPlayMPDProcessor(DRMProcessor):
    """Rewrites 6play MPD manifests to be MediaFlow-compatible."""

    def __init__(self):
        self.namespaces = {
            'mpd': 'urn:mpeg:dash:schema:mpd:2011',
            'cenc': 'urn:mpeg:cenc:2013',
            'mspr': 'urn:microsoft:playready',
        }

    def process(self, url: str, **kwargs) -> str:
        """Rewrite the MPD at *url* to be MediaFlow-compatible.

        Args:
            url: The original MPD URL (used to resolve relative segment URLs).
            **kwargs:
                mpd_content (str): The raw MPD XML string. Required.

        Returns:
            Rewritten MPD as a string (same as :meth:`process_mpd_for_mediaflow`).
        """
        mpd_content = kwargs['mpd_content']
        return self.process_mpd_for_mediaflow(mpd_content, url)

    def process_mpd_for_mediaflow(self, mpd_content: str, mpd_url: str) -> str:
        """Simplify a 6play MPD so MediaFlow can handle it.

        Removes problematic nested ContentProtection elements and keeps
        only the essential DRM info.
        """
        try:
            for prefix, uri in self.namespaces.items():
                ET.register_namespace(prefix, uri)

            root = ET.fromstring(mpd_content)
            base_url = self._get_base_url(mpd_url)
            self._simplify_content_protection(root)
            self._make_urls_absolute(root, base_url)
            return ET.tostring(root, encoding='unicode', xml_declaration=True)
        except Exception as e:
            print(f"[SixPlayMPDProcessor] Error processing MPD: {e}")
            return mpd_content

    def _get_base_url(self, mpd_url: str) -> str:
        parsed = urlparse(mpd_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        path_parts = parsed.path.split('/')
        if len(path_parts) > 1:
            base_url += '/'.join(path_parts[:-1])
        return base_url

    def _simplify_content_protection(self, root: ET.Element):
        content_protections = [
            elem for elem in root.iter()
            if elem.tag.endswith('}ContentProtection') or elem.tag == 'ContentProtection'
        ]
        for cp in content_protections:
            scheme_id = cp.get('schemeIdUri', '')
            if 'mp4protection' in scheme_id:
                for child in list(cp):
                    cp.remove(child)
            elif 'EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED' in scheme_id:
                pssh_element = None
                for child in list(cp):
                    if 'pssh' in child.tag:
                        pssh_element = child
                    else:
                        cp.remove(child)
                if pssh_element is not None and pssh_element.text:
                    pssh_element.text = pssh_element.text.strip()
            elif '9A04F079-9840-4286-AB92-E65BE0885F95' in scheme_id:
                # PlayReady: remove all children — avoids 'str has no .get' errors in MediaFlow
                for child in list(cp):
                    cp.remove(child)
                cp.set('value', cp.get('value', 'MSPR 2.0'))

    def _make_urls_absolute(self, root: ET.Element, base_url: str):
        for elem in root.iter():
            if elem.tag.endswith('}SegmentTemplate'):
                for attr in ['initialization', 'media']:
                    url = elem.get(attr)
                    if url and not url.startswith('http'):
                        if url.startswith('/'):
                            parsed_base = urlparse(base_url)
                            absolute_url = f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
                        else:
                            absolute_url = urljoin(base_url + '/', url)
                        elem.set(attr, absolute_url)


def create_mediaflow_compatible_mpd(original_mpd_content: str, mpd_url: str) -> str:
    """Convenience wrapper — create a MediaFlow-compatible version of a 6play MPD."""
    return SixPlayMPDProcessor().process_mpd_for_mediaflow(original_mpd_content, mpd_url)


def extract_drm_info_from_mpd(mpd_content: str) -> Dict:
    """Extract DRM key IDs and PSSH boxes from an MPD manifest."""
    try:
        root = ET.fromstring(mpd_content)
        drm_info: Dict = {'key_id': None, 'widevine_pssh': None, 'playready_pssh': None}

        for elem in root.iter():
            if not (elem.tag.endswith('}ContentProtection') or elem.tag == 'ContentProtection'):
                continue
            scheme_id = elem.get('schemeIdUri', '')
            if 'mp4protection' in scheme_id:
                default_kid = elem.get('{urn:mpeg:cenc:2013}default_KID')
                if default_kid:
                    drm_info['key_id'] = default_kid
            elif 'EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED' in scheme_id:
                for child in elem:
                    if 'pssh' in child.tag and child.text:
                        drm_info['widevine_pssh'] = child.text.strip()
            elif '9A04F079-9840-4286-AB92-E65BE0885F95' in scheme_id:
                for child in elem:
                    if 'pssh' in child.tag and child.text:
                        drm_info['playready_pssh'] = child.text.strip()

        return drm_info
    except Exception as e:
        print(f"[SixPlayMPDProcessor] Error extracting DRM info: {e}")
        return {}
