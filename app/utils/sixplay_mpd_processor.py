"""
Custom MPD processor for 6play DRM content that handles complex ContentProtection structures.
This bypasses MediaFlow parsing issues by creating a simplified, compatible manifest.
"""

import xml.etree.ElementTree as ET
from typing import Dict
from urllib.parse import urljoin, urlparse


class SixPlayMPDProcessor:
    """Custom MPD processor for 6play that creates MediaFlow-compatible manifests"""
    
    def __init__(self):
        self.namespaces = {
            'mpd': 'urn:mpeg:dash:schema:mpd:2011',
            'cenc': 'urn:mpeg:cenc:2013',
            'mspr': 'urn:microsoft:playready'
        }
    
    def process_mpd_for_mediaflow(self, mpd_content: str, mpd_url: str) -> str:
        """
        Process 6play MPD to create a simplified version that MediaFlow can handle.
        Removes problematic nested ContentProtection elements and keeps only essential DRM info.
        """
        try:
            # Register namespaces
            for prefix, uri in self.namespaces.items():
                ET.register_namespace(prefix, uri)
            
            # Parse the MPD
            root = ET.fromstring(mpd_content)
            
            # Extract base URL from the MPD URL
            base_url = self._get_base_url(mpd_url)
            
            # Process all ContentProtection elements
            self._simplify_content_protection(root)
            
            # Fix relative URLs to be absolute
            self._make_urls_absolute(root, base_url)
            
            # Create simplified MPD
            simplified_mpd = ET.tostring(root, encoding='unicode', xml_declaration=True)
            
            return simplified_mpd
            
        except Exception as e:
            print(f"[SixPlayMPDProcessor] Error processing MPD: {e}")
            # Return original if processing fails
            return mpd_content
    
    def _get_base_url(self, mpd_url: str) -> str:
        """Extract base URL from MPD URL"""
        parsed = urlparse(mpd_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        # Include path up to the last directory
        path_parts = parsed.path.split('/')
        if len(path_parts) > 1:
            base_path = '/'.join(path_parts[:-1])
            base_url += base_path
        return base_url
    
    def _simplify_content_protection(self, root: ET.Element):
        """
        Simplify ContentProtection elements to avoid MediaFlow parsing issues.
        Keep only the essential attributes and remove problematic nested elements.
        """
        # Find all ContentProtection elements
        content_protections = []
        for elem in root.iter():
            if elem.tag.endswith('}ContentProtection') or elem.tag == 'ContentProtection':
                content_protections.append(elem)
        
        for cp in content_protections:
            scheme_id = cp.get('schemeIdUri', '')
            
            # Keep basic CENC protection (this usually works fine)
            if 'mp4protection' in scheme_id:
                # Remove any child elements to simplify
                for child in list(cp):
                    cp.remove(child)
                continue
            
            # For Widevine (EDEF8BA9)
            elif 'EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED' in scheme_id:
                # Keep only the PSSH box, remove other children
                pssh_element = None
                for child in list(cp):
                    if 'pssh' in child.tag:
                        pssh_element = child
                    else:
                        cp.remove(child)
                
                # If we have a PSSH, make sure it's properly formatted
                if pssh_element is not None:
                    # Ensure the PSSH text is properly formatted
                    if pssh_element.text:
                        # Clean up any whitespace
                        pssh_element.text = pssh_element.text.strip()
            
            # For PlayReady (9A04F079)
            elif '9A04F079-9840-4286-AB92-E65BE0885F95' in scheme_id:
                # This is the problematic one - simplify drastically
                # Remove all children to avoid the 'str' object has no attribute 'get' error
                for child in list(cp):
                    cp.remove(child)
                
                # Keep only basic attributes
                cp.set('value', cp.get('value', 'MSPR 2.0'))
    
    def _make_urls_absolute(self, root: ET.Element, base_url: str):
        """Convert relative URLs to absolute URLs"""
        # Find SegmentTemplate elements and make URLs absolute
        for elem in root.iter():
            if elem.tag.endswith('}SegmentTemplate'):
                # Fix initialization and media URLs
                for attr in ['initialization', 'media']:
                    url = elem.get(attr)
                    if url and not url.startswith('http'):
                        # Make relative URL absolute
                        if url.startswith('/'):
                            # Absolute path - add scheme and host
                            parsed_base = urlparse(base_url)
                            absolute_url = f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
                        else:
                            # Relative path - join with base
                            absolute_url = urljoin(base_url + '/', url)
                        
                        elem.set(attr, absolute_url)


def create_mediaflow_compatible_mpd(original_mpd_content: str, mpd_url: str) -> str:
    """
    Create a MediaFlow-compatible version of the 6play MPD.
    This is the main function to call from the provider.
    """
    processor = SixPlayMPDProcessor()
    return processor.process_mpd_for_mediaflow(original_mpd_content, mpd_url)


def extract_drm_info_from_mpd(mpd_content: str) -> Dict:
    """
    Extract DRM information from the MPD for license URL construction.
    Returns key_id and other necessary DRM info.
    """
    try:
        root = ET.fromstring(mpd_content)
        
        drm_info = {
            'key_id': None,
            'widevine_pssh': None,
            'playready_pssh': None
        }
        
        # Find ContentProtection elements
        for elem in root.iter():
            if elem.tag.endswith('}ContentProtection'):
                scheme_id = elem.get('schemeIdUri', '')
                
                # Extract key ID from CENC protection
                if 'mp4protection' in scheme_id:
                    default_kid = elem.get('{urn:mpeg:cenc:2013}default_KID')
                    if default_kid:
                        drm_info['key_id'] = default_kid
                
                # Extract Widevine PSSH
                elif 'EDEF8BA9-79D6-4ACE-A3C8-27DCD51D21ED' in scheme_id:
                    for child in elem:
                        if 'pssh' in child.tag and child.text:
                            drm_info['widevine_pssh'] = child.text.strip()
                
                # Extract PlayReady PSSH
                elif '9A04F079-9840-4286-AB92-E65BE0885F95' in scheme_id:
                    for child in elem:
                        if 'pssh' in child.tag and child.text:
                            drm_info['playready_pssh'] = child.text.strip()
        
        return drm_info
        
    except Exception as e:
        print(f"[SixPlayMPDProcessor] Error extracting DRM info: {e}")
        return {}
