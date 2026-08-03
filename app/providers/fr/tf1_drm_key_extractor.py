"""
TF1+ DRM Key Extractor
"""

import requests
import re
from typing import Dict, Optional
import xml.etree.ElementTree as ET

try:
    from pywidevine.cdm import Cdm
    from pywidevine.device import Device
    from pywidevine.pssh import PSSH
    PYWIDEVINE_AVAILABLE = True
except ImportError:
    PYWIDEVINE_AVAILABLE = False


class TF1DRMExtractor:
    """DRM key extractor for TF1+ using pywidevine."""

    def __init__(self, wvd_path: Optional[str] = None):
        self.wvd_path = wvd_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Origin': 'https://www.tf1.fr',
            'Referer': 'https://www.tf1.fr/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site'
        })

    def extract_pssh_from_mpd(self, mpd_url: str, verbose: bool = True) -> Optional[str]:
        """Extract PSSH from MPD manifest. Returns base64-encoded PSSH or None."""
        try:
            response = self.session.get(mpd_url, timeout=15)
            response.raise_for_status()
            content = response.text

            # Method 1: Parse XML with namespaces
            try:
                root = ET.fromstring(response.content)
                for cp in root.findall('.//{*}ContentProtection'):
                    scheme = cp.get('schemeIdUri', '').lower()
                    if 'edef8ba9' in scheme or 'widevine' in scheme:
                        for child in cp:
                            if 'pssh' in child.tag.lower():
                                pssh = child.text
                                if pssh and pssh.strip():
                                    return pssh.strip()
                        for attr, value in cp.attrib.items():
                            if 'pssh' in attr.lower() and value:
                                return value.strip()
            except Exception:
                pass

            # Method 2: Regex search for PSSH elements
            pssh_patterns = [
                r'<(?:cenc:)?pssh[^>]*>([A-Za-z0-9+/=]+)</(?:cenc:)?pssh>',
                r'<cenc:pssh[^>]*>\s*([A-Za-z0-9+/=]+)\s*</cenc:pssh>',
                r'"pssh"\s*:\s*"([A-Za-z0-9+/=]+)"',
                r'pssh="([A-Za-z0-9+/=]+)"'
            ]
            for pattern in pssh_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    return matches[0].strip()

            # Method 3: PSSH box format (starts with AAAA)
            pssh_box_matches = re.findall(r'(AAAA[A-Za-z0-9+/=]{40,})', content)
            if pssh_box_matches:
                return pssh_box_matches[0]

            # Method 4: Base64 blob near "widevine" or "edef8ba9"
            widevine_section = re.search(
                r'(edef8ba9|widevine).{0,500}([A-Za-z0-9+/=]{100,})',
                content, re.IGNORECASE
            )
            if widevine_section:
                potential_pssh = widevine_section.group(2)
                if potential_pssh.startswith('AAAA'):
                    return potential_pssh

            return None

        except Exception:
            return None

    def load_device(self, verbose: bool = True) -> Optional[Device]:
        """Load Widevine device from WVD file. Returns Device or None."""
        import os
        paths_to_try = []
        if self.wvd_path:
            paths_to_try.append(self.wvd_path)
        paths_to_try.extend([
            './device.wvd',
            './device_client_id_blob.wvd',
            './client_id.wvd',
            os.path.expanduser('~/.pywidevine/device.wvd'),
            os.path.expanduser('~/device.wvd')
        ])
        for path in paths_to_try:
            if os.path.exists(path):
                try:
                    return Device.load(path)
                except Exception:
                    pass
        return None

    def get_keys(
        self,
        video_url: str,
        license_url: str,
        verbose: bool = True,
        proxy: Optional[str] = None
    ) -> Dict[str, str]:
        """Extract DRM keys from TF1+ video. Returns dict mapping KID to KEY."""
        if not PYWIDEVINE_AVAILABLE:
            return {}
        if proxy:
            self.session.proxies.update({'http': proxy, 'https': proxy})

        session_id = None
        try:
            pssh_b64 = self.extract_pssh_from_mpd(video_url, verbose)
            if not pssh_b64:
                return {}

            try:
                pssh = PSSH(pssh_b64)
            except Exception:
                return {}

            device = self.load_device(verbose)
            if not device:
                return {}

            cdm = Cdm.from_device(device)
            session_id = cdm.open()
            challenge = cdm.get_license_challenge(session_id, pssh)

            headers = self.session.headers.copy()
            headers.update({
                'Content-Type': 'application/octet-stream',
                'Accept': 'application/octet-stream, */*'
            })
            response = self.session.post(license_url, data=challenge, headers=headers, timeout=20)

            if response.status_code != 200:
                return {}

            cdm.parse_license(session_id, response.content)

            keys_dict = {}
            for key in cdm.get_keys(session_id):
                if hasattr(key, 'kid') and hasattr(key, 'key'):
                    kid = str(key.kid).replace('-', '')
                    key_value = key.key.hex()
                    key_type = getattr(key, 'type', 'CONTENT')
                    if key_type == 'CONTENT':
                        keys_dict[kid] = key_value
            return keys_dict

        except Exception:
            return {}
        finally:
            if session_id and 'cdm' in locals():
                try:
                    cdm.close(session_id)
                except Exception:
                    pass
