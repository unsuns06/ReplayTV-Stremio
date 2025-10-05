
"""
Enhanced TF1+ DRM Key Extractor with Advanced Features
Author: Custom implementation based on pywidevine
License: Educational purposes only
"""

import requests
import base64
import json
import re
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs

try:
    from pywidevine.cdm import Cdm
    from pywidevine.device import Device
    from pywidevine.pssh import PSSH
    PYWIDEVINE_AVAILABLE = True
except ImportError:
    PYWIDEVINE_AVAILABLE = False


class TF1DRMExtractor:
    """Advanced DRM key extractor for TF1+ with multiple extraction strategies."""

    def __init__(self, wvd_path: Optional[str] = None):
        """
        Initialize the extractor.

        Args:
            wvd_path: Path to Widevine Device (.wvd) file
        """
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
        """
        Extract PSSH from MPD manifest using multiple methods.

        Args:
            mpd_url: URL to MPD manifest
            verbose: Print debug information

        Returns:
            Base64-encoded PSSH string or None
        """
        if verbose:
            # print(f"[PSSH] Fetching MPD: {mpd_url[:80]}...")
            pass

        try:
            response = self.session.get(mpd_url, timeout=15)
            response.raise_for_status()
            content = response.text

            if verbose:
                # print(f"[PSSH] MPD size: {len(content)} bytes")
                pass

            # Method 1: Parse XML with namespaces
            try:
                root = ET.fromstring(response.content)
                namespaces = {
                    'mpd': 'urn:mpeg:dash:schema:mpd:2011',
                    'cenc': 'urn:mpeg:cenc:2013',
                    'mas': 'urn:marlin:mas:1-0:services:schemas:mpd'
                }

                # Search all ContentProtection elements
                for cp in root.findall('.//{*}ContentProtection'):
                    scheme = cp.get('schemeIdUri', '').lower()

                    # Widevine UUID
                    if 'edef8ba9' in scheme or 'widevine' in scheme:
                        # Check for pssh in child elements
                        for child in cp:
                            if 'pssh' in child.tag.lower():
                                pssh = child.text
                                if pssh and pssh.strip():
                                    if verbose:
                                        # print(f"[PSSH] Found via XML parsing (Method 1)")
                                        pass
                                    return pssh.strip()

                        # Check attributes
                        for attr, value in cp.attrib.items():
                            if 'pssh' in attr.lower() and value:
                                if verbose:
                                    # print(f"[PSSH] Found via XML attribute (Method 1b)")
                                    pass
                                return value.strip()
            except Exception as e:
                if verbose:
                    # print(f"[PSSH] XML parsing failed: {e}")
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
                    if verbose:
                        # print(f"[PSSH] Found via regex (Method 2)")
                        pass
                    return matches[0].strip()

            # Method 3: Look for PSSH box format (starts with AAAA)
            pssh_box_matches = re.findall(r'(AAAA[A-Za-z0-9+/=]{40,})', content)
            if pssh_box_matches:
                if verbose:
                    # print(f"[PSSH] Found PSSH box (Method 3)")
                    pass
                return pssh_box_matches[0]

            # Method 4: Search for base64 blobs near "widevine" or "edef8ba9"
            widevine_section = re.search(
                r'(edef8ba9|widevine).{0,500}([A-Za-z0-9+/=]{100,})',
                content,
                re.IGNORECASE
            )
            if widevine_section:
                potential_pssh = widevine_section.group(2)
                if potential_pssh.startswith('AAAA'):
                    if verbose:
                        # print(f"[PSSH] Found via context search (Method 4)")
                        pass
                    return potential_pssh

            if verbose:
                # print("[PSSH] ERROR: No PSSH found in MPD")
                # print(f"[PSSH] MPD preview: {content[:500]}")
                pass

            return None

        except Exception as e:
            if verbose:
                # print(f"[PSSH] ERROR: {str(e)}")
                pass
            return None

    def load_device(self, verbose: bool = True) -> Optional[Device]:
        """
        Load Widevine device from WVD file.

        Args:
            verbose: Print debug information

        Returns:
            Device object or None
        """
        import os

        paths_to_try = []

        if self.wvd_path:
            paths_to_try.append(self.wvd_path)

        # Common WVD locations
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
                    device = Device.load(path)
                    if verbose:
                        # print(f"[CDM] Loaded device from: {path}")
                        pass
                    return device
                except Exception as e:
                    if verbose:
                        # print(f"[CDM] Failed to load {path}: {e}")
                        pass

        if verbose:
            # print(f"[CDM] ERROR: No valid WVD file found")
            # print(f"[CDM] Searched: {paths_to_try[:3]}")
            pass

        return None

    def get_keys(
        self,
        video_url: str,
        license_url: str,
        verbose: bool = True,
        proxy: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Extract DRM keys from TF1+ video.

        Args:
            video_url: MPD manifest URL
            license_url: Widevine license server URL
            verbose: Print detailed progress
            proxy: Optional proxy URL

        Returns:
            Dictionary mapping KID to KEY
        """
        if not PYWIDEVINE_AVAILABLE:
            # print("[ERROR] pywidevine not installed")
            # print("Install: pip install pywidevine")
            return {}

        if proxy:
            self.session.proxies.update({'http': proxy, 'https': proxy})

        session_id = None

        try:
            # Step 1: Extract PSSH
            # print("\n" + "="*70)
            # print("[1/5] EXTRACTING PSSH FROM MPD")
            # print("="*70)

            pssh_b64 = self.extract_pssh_from_mpd(video_url, verbose)
            if not pssh_b64:
                return {}

            # print(f"[PSSH] {pssh_b64[:60]}...")

            # Step 2: Parse PSSH
            # print("\n" + "="*70)
            # print("[2/5] PARSING PSSH")
            # print("="*70)

            try:
                pssh = PSSH(pssh_b64)
                # print(f"[PSSH] Valid PSSH object created")
                if verbose and hasattr(pssh, 'key_ids') and pssh.key_ids:
                    # print(f"[PSSH] Key IDs found: {len(pssh.key_ids)}")
                    pass
            except Exception as e:
                # print(f"[PSSH] ERROR: Invalid PSSH - {e}")
                return {}

            # Step 3: Load CDM
            # print("\n" + "="*70)
            # print("[3/5] LOADING WIDEVINE CDM")
            # print("="*70)

            device = self.load_device(verbose)
            if not device:
                return {}

            cdm = Cdm.from_device(device)
            # print(f"[CDM] CDM initialized successfully")

            # Step 4: Generate challenge
            # print("\n" + "="*70)
            # print("[4/5] GENERATING LICENSE CHALLENGE")
            # print("="*70)

            session_id = cdm.open()
            # print(f"[CDM] Session opened: {session_id.hex()}")

            challenge = cdm.get_license_challenge(session_id, pssh)
            # print(f"[CDM] Challenge generated: {len(challenge)} bytes")

            if verbose:
                # print(f"[CDM] Challenge preview: {base64.b64encode(challenge)[:80]}...")
                pass

            # Step 5: Request license
            # print("\n" + "="*70)
            # print("[5/5] REQUESTING LICENSE FROM SERVER")
            # print("="*70)

            # print(f"[LICENSE] URL: {license_url[:80]}...")

            # Prepare headers specific to TF1
            headers = self.session.headers.copy()
            headers.update({
                'Content-Type': 'application/octet-stream',
                'Accept': 'application/octet-stream, */*'
            })

            response = self.session.post(
                license_url,
                data=challenge,
                headers=headers,
                timeout=20
            )

            # print(f"[LICENSE] Status: {response.status_code}")
            # print(f"[LICENSE] Response size: {len(response.content)} bytes")

            if response.status_code != 200:
                # print(f"[LICENSE] ERROR: Server returned {response.status_code}")
                # print(f"[LICENSE] Response: {response.text[:300]}")
                return {}

            # Step 6: Parse license and extract keys
            # print("\n" + "="*70)
            # print("[6/6] PARSING LICENSE AND EXTRACTING KEYS")
            # print("="*70)

            cdm.parse_license(session_id, response.content)
            # print(f"[LICENSE] License parsed successfully")

            # Extract keys
            keys_dict = {}
            all_keys = list(cdm.get_keys(session_id))

            # print(f"\n[KEYS] Total keys in license: {len(all_keys)}")

            # print("\n" + "="*70)
            # print("EXTRACTED DECRYPTION KEYS")
            # print("="*70)

            for key in all_keys:
                # Handle key object structure
                if hasattr(key, 'kid') and hasattr(key, 'key'):
                    # Convert UUID to hex string (remove dashes)
                    kid = str(key.kid).replace('-', '')
                    # Convert bytes to hex string
                    key_value = key.key.hex()
                    key_type = getattr(key, 'type', 'CONTENT')
                else:
                    # print(f"[DEBUG] Unexpected key structure: {key}")
                    continue

                if key_type == 'CONTENT':
                    keys_dict[kid] = key_value
                    # print(f"\n[{key_type}]")
                    # print(f"  KID: {kid}")
                    # print(f"  KEY: {key_value}")
                    # print(f"  Combined: {kid}:{key_value}")
                elif verbose:
                    # print(f"\n[{key_type}] {kid}:{key_value}")
                    pass

            # print("\n" + "="*70)

            if not keys_dict:
                # print("\n[WARNING] No CONTENT keys found!")
                pass
            else:
                # print(f"\n[SUCCESS] Extracted {len(keys_dict)} content key(s)")
                pass

            return keys_dict

        except Exception as e:
            # print(f"\n[ERROR] Extraction failed: {str(e)}")
            import traceback
            if verbose:
                # traceback.print_exc()
                pass
            return {}

        finally:
            if session_id and 'cdm' in locals():
                try:
                    cdm.close(session_id)
                    if verbose:
                        # print(f"\n[CDM] Session closed")
                        pass
                except:
                    pass


def get_tf1_keys(video_url: str, license_url: str, wvd_path: str = "device.wvd"):
    """
    Convenience function to extract and print TF1+ DRM keys.

    Args:
        video_url: MPD manifest URL
        license_url: License server URL  
        wvd_path: Path to WVD device file (optional)
    Returns:
        dict: Extracted keys as {kid: key} or empty dict if extraction failed.
    """
    extractor = TF1DRMExtractor(wvd_path)
    keys = extractor.get_keys(video_url, license_url, verbose=True)

    if keys:
        # print("\n" + "="*70)
        print("DRM KEYS:")
        for kid, key in keys.items():
            print(f"{kid}:{key}")
    else:
        print("\n[FAILED] Could not extract keys. Check errors above.")
    return keys


# Test execution
if __name__ == "__main__":
    # print("\n")
    # print("╔" + "="*68 + "╗")
    # print("║" + " "*15 + "TF1+ DRM KEY EXTRACTOR v2.0" + " "*26 + "║")
    # print("╚" + "="*68 + "╝")
    # print()

    # Test URLs from user
    LICENSE_URL = "https://dgmw.prod.p.tf1.fr/acquire?e=1759682440&id=14369222&pla=86400&rn=1&si=a3ad96cf115f2bb996f7bbb8a70d0a511c6e36d4906493acc60275d9a975ed48&ssc=ead54b49-e645-4267-b1fc-552ad1f63f83&ti=gigya&tl=1&ts=e0f35fcf85874718b5b13f0d6165caf2&video_id=1b957b5e-33bd-48de-b9ef-51be19dc30f7"

    VIDEO_URL = "https://vod-das.cdn-0.diff.tf1.fr/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjaXAiOiIzNS4xODAuMTkxLjE2NiIsImNtY2QiOiIiLCJleHAiOjE3NTk2ODI0NDAsImdpZCI6ImUwZjM1ZmNmODU4NzQ3MThiNWIxM2YwZDYxNjVjYWYyIiwiaWF0IjoxNzU5NjY4MDQwLCJpc3MiOiJkZWxpdmVyeSIsIm1heGIiOjI4MDAwMDAsInN0ZW0iOiIvMi9VU1AtMHgwLzkyLzIyLzE0MzY5MjIyL3NzbS83OWE1MTNhYTEyYzgwYWQzOTk2MzFjZjRlNmRkY2NhMmJiODg3ZGJlYjU1MDcyZGU5ZTM5MmU4YjQwMWM2NDBhLmlzbS8xNDM2OTIyMi5tcGQiLCJzdWIiOiJlMGYzNWZjZjg1ODc0NzE4YjViMTNmMGQ2MTY1Y2FmMiJ9.nKXQoo-e9RtDDlWVYHUQwgNeYcH_-cr9e3CdORAVPA8/2/USP-0x0/92/22/14369222/ssm/79a513aa12c80ad399631cf4e6ddcca2bb887dbeb55072de9e392e8b401c640a.ism/14369222.mpd"

    get_tf1_keys(
        video_url=VIDEO_URL,
        license_url=LICENSE_URL
    )
