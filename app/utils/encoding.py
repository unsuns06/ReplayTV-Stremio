"""
Encoding utilities for DRM and stream processing.
Extracted from sixplay.py to be shared across providers.
"""

import base64
import re
from typing import Optional

from app.utils.safe_print import safe_print


def pad_base64(value: str) -> str:
    """Pad base64 strings to a valid length."""
    if not value:
        return value
    missing_padding = len(value) % 4
    if missing_padding:
        value += '=' * (4 - missing_padding)
    return value


def normalize_key_id(key_id: Optional[str]) -> Optional[str]:
    """
    Return the key ID as 32-char lowercase hex if possible.
    Handles both hex and base64 encoded key IDs.
    """
    if not key_id:
        return None
    
    # Remove common prefixes/formatting
    key_id = key_id.strip().lower()
    key_id = key_id.replace('-', '').replace(' ', '')
    
    # Check if already hex
    if re.match(r'^[0-9a-f]{32}$', key_id):
        return key_id
    
    # Try base64 decode
    try:
        padded = pad_base64(key_id.upper() if key_id.isupper() else key_id)
        decoded = base64.b64decode(padded)
        if len(decoded) == 16:
            return decoded.hex()
    except:
        pass
    
    # Try URL-safe base64
    try:
        decoded = base64.urlsafe_b64decode(pad_base64(key_id))
        if len(decoded) == 16:
            return decoded.hex()
    except:
        pass
    
    safe_print(f"⚠️ Could not normalize key ID: {key_id}")
    return None


def ensure_hex_key(key_value: Optional[str]) -> Optional[str]:
    """
    Coerce provided key data into a 32-character hex string.
    Handles hex, base64, and mixed formats.
    """
    if not key_value:
        return None
    
    key_value = key_value.strip()
    
    # Already 32-char hex
    if re.match(r'^[0-9a-fA-F]{32}$', key_value):
        return key_value.lower()
    
    # Remove any prefix like "key:" 
    if ':' in key_value:
        parts = key_value.split(':')
        for part in parts:
            part = part.strip()
            if re.match(r'^[0-9a-fA-F]{32}$', part):
                return part.lower()
    
    # Try base64 decode
    try:
        decoded = base64.b64decode(pad_base64(key_value))
        if len(decoded) == 16:
            return decoded.hex()
    except:
        pass
    
    # Try URL-safe base64
    try:
        decoded = base64.urlsafe_b64decode(pad_base64(key_value))
        if len(decoded) == 16:
            return decoded.hex()
    except:
        pass
    
    safe_print(f"⚠️ Could not ensure hex key: {key_value[:20]}...")
    return None


def hex_to_base64url(hex_value: Optional[str]) -> Optional[str]:
    """Convert hex strings to base64url without padding."""
    if not hex_value:
        return None
    
    try:
        # Normalize hex
        hex_clean = hex_value.lower().replace('-', '').replace(' ', '')
        if not re.match(r'^[0-9a-f]+$', hex_clean):
            return None
        
        raw_bytes = bytes.fromhex(hex_clean)
        b64_url = base64.urlsafe_b64encode(raw_bytes).rstrip(b'=').decode('utf-8')
        return b64_url
    except Exception as e:
        safe_print(f"⚠️ hex_to_base64url error: {e}")
        return None


def normalize_decryption_key(
    raw_key: Optional[str], 
    key_id_hex: Optional[str]
) -> Optional[str]:
    """
    Extract the matching hex key from various key string formats.
    
    Handles formats like:
    - "kid:key"
    - "key_id:key_value" 
    - Just the key value
    - Multiple keys separated by newlines
    """
    if not raw_key:
        return None
    
    def match_candidate(kid_candidate: Optional[str], key_candidate: Optional[str]) -> Optional[str]:
        """Check if this kid:key pair matches our target key_id."""
        if not key_candidate:
            return None
        
        normalized_kid = normalize_key_id(kid_candidate) if kid_candidate else None
        normalized_key = ensure_hex_key(key_candidate)
        
        if not normalized_key:
            return None
        
        # If we have a target key_id, check for match
        if key_id_hex and normalized_kid:
            if normalized_kid.lower() == key_id_hex.lower():
                return normalized_key
            return None
        
        # No target or no kid in response - return key if valid
        return normalized_key
    
    raw_key = raw_key.strip()
    
    # Check for multiple lines (common in CDRM responses)
    lines = raw_key.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Format: kid:key
        if ':' in line:
            parts = line.split(':', 1)
            result = match_candidate(parts[0], parts[1] if len(parts) > 1 else None)
            if result:
                return result
        else:
            # Single value - could be just the key
            result = ensure_hex_key(line)
            if result:
                return result
    
    # Fallback: try to extract 32-char hex anywhere in string
    hex_match = re.search(r'[0-9a-fA-F]{32}', raw_key)
    if hex_match:
        return hex_match.group(0).lower()
    
    safe_print(f"⚠️ Could not normalize decryption key from: {raw_key[:50]}...")
    return None
