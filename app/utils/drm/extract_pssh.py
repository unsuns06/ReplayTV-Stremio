"""Fetch a DASH MPD document and extract the first PSSH box.

Moved from ``app/providers/fr/extract_pssh.py`` — this is generic DRM
tooling with no provider-specific logic, so it lives in the shared DRM
utilities package (previously ``app/utils/drm`` imported it *from* the
providers package, inverting the dependency direction).
"""

from __future__ import annotations

import base64
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, Union
from urllib.request import Request, urlopen
from urllib.parse import quote

from app.utils.proxy_config import get_proxy_config

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/dash+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_TIMEOUT = 30
WIDEVINE_SYSTEM_ID = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"


@dataclass
class PsshRecord:
    source: str
    parent: str
    base64_text: str
    raw_length: int
    system_id: Optional[str]


def fetch_mpd(url: str) -> bytes:
    """Fetch MPD document using the geo proxy to bypass geoblocking."""
    proxy_config = get_proxy_config()
    proxy_base_url = proxy_config.get_proxy("fr_default")
    if not proxy_base_url:
        raise ValueError("fr_default proxy not configured in credentials")

    proxy_url = proxy_base_url + quote(url, safe='')
    request = Request(proxy_url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read()


def parse_mpd(xml_payload: bytes) -> ET.Element:
    try:
        return ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        raise ValueError(f"Unable to parse MPD XML: {exc}") from exc


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def decode_pssh(base64_text: str, parent: ET.Element, source: str) -> Optional[PsshRecord]:
    cleaned = "".join(base64_text.split())
    if not cleaned:
        return None

    try:
        raw = base64.b64decode(cleaned)
    except (base64.binascii.Error, ValueError):
        return None

    system_id: Optional[str] = None
    if len(raw) >= 28:
        system_bytes = raw[12:28]
        try:
            system_id = str(uuid.UUID(bytes=system_bytes))
        except ValueError:
            system_id = system_bytes.hex()

    return PsshRecord(
        source=source,
        parent=local_name(parent.tag),
        base64_text=cleaned,
        raw_length=len(raw),
        system_id=system_id,
    )


def iter_pssh(root: ET.Element) -> Iterable[PsshRecord]:
    for element in root.iter():
        for attr_key, attr_val in element.attrib.items():
            if local_name(attr_key).lower() == "pssh":
                record = decode_pssh(attr_val, element, "attribute")
                if record:
                    yield record

        if local_name(element.tag).lower() == "pssh":
            text = (element.text or "").strip()
            if text:
                record = decode_pssh(text, element, "element")
                if record:
                    yield record


def extract_first_pssh(
    url: str, include_mpd: bool = False
) -> Union[Optional[PsshRecord], Tuple[Optional[PsshRecord], Optional[bytes]]]:
    """Return the Widevine PSSH if the manifest has one, else the first PSSH.

    6play's live manifests list the PlayReady box first, and a Widevine CDM
    rejects it with a 400 — so system ID decides, not document order.
    """
    xml_bytes = fetch_mpd(url)
    root = parse_mpd(xml_bytes)
    records = list(iter_pssh(root))
    record = next(
        (r for r in records if (r.system_id or "").lower() == WIDEVINE_SYSTEM_ID),
        records[0] if records else None,
    )
    return (record, xml_bytes) if include_mpd else record
