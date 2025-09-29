#!/usr/bin/env python3
"""Fetch a DASH MPD document and emit only the first PSSH box."""

from __future__ import annotations

import base64
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.request import Request, urlopen
from urllib.parse import quote

DEFAULT_URL = "https://par5-edge-02.cdn.bedrock.tech/m6web/output/d/5/3/d53727ced0e827d7bb94cc06de7538b47d63c5e1/static/13141002_be86cce5bac3ab6950c2fa69da7a3d48_android_mobile_dash_upTo1080p_720p_vbr_cae_drm_software.mpd?st=p8V_S420xaTpa0KLXa2wDQ&e=1759214048"
PROXY_URL = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/dash+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_TIMEOUT = 30


@dataclass
class PsshRecord:
    source: str
    parent: str
    base64_text: str
    raw_length: int
    system_id: Optional[str]


def fetch_mpd(url: str) -> bytes:
    """Fetch MPD document using proxy to bypass geoblocking."""
    # Use proxy to bypass geoblocking
    proxy_url = PROXY_URL + quote(url, safe='')
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


def extract_first_pssh(url: str) -> Optional[PsshRecord]:
    xml_bytes = fetch_mpd(url)
    root = parse_mpd(xml_bytes)
    for record in iter_pssh(root):
        return record
    return None


def main(url: str) -> int:
    record = extract_first_pssh(url)
    if not record:
        raise RuntimeError("PSSH not found")

    print(record.base64_text)
    return 0


if __name__ == "__main__":
    target = DEFAULT_URL
    if len(sys.argv) > 1:
        target = sys.argv[1]

    sys.exit(main(target))
