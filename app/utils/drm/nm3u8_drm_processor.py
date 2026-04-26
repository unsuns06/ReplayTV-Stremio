"""DRM content processor backed by the N_m3u8DL-RE remote API."""

import requests
import time
from typing import Dict, Any

from app.utils.proxy_config import get_proxy_config
from app.utils.drm.base import DRMProcessor


class SimpleDRMProcessor(DRMProcessor):
    """Offloads DRM-protected downloads to a N_m3u8DL-RE API endpoint."""

    def __init__(self, api_url: str = None):
        if api_url is None:
            proxy_config = get_proxy_config()
            api_url = proxy_config.get_proxy('nm3u8_processor')
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()

    def process(self, url: str, **kwargs) -> Dict[str, Any]:
        """Start processing a DRM-protected URL via the remote API.

        Keyword args mirror :meth:`process_drm_content`.
        """
        return self.process_drm_content(
            url=url,
            save_name=kwargs.get('save_name', 'output'),
            key=kwargs.get('key'),
            keys=kwargs.get('keys'),
            quality=kwargs.get('quality', 'best'),
            format=kwargs.get('format', 'mp4'),
            timeout=kwargs.get('timeout', 1800),
        )

    def process_drm_content(self,
                            url: str,
                            save_name: str,
                            key: str = None,
                            keys: list = None,
                            quality: str = "best",
                            format: str = "mkv",
                            timeout: int = 1800) -> Dict[str, Any]:
        """Start a DRM processing job and return immediately.

        Args:
            url: DRM-protected content URL
            save_name: Name for the output file
            key: Single DRM decryption key (deprecated, use keys instead)
            keys: List of DRM decryption keys for multi-key content
            quality: Video quality selection
            format: Output format (mkv, mp4, etc.)
            timeout: Processing timeout in seconds

        Returns:
            Dict with processing results
        """
        payload = {
            "url": url,
            "save_name": save_name,
            "select_video": quality,
            "select_audio": "all",
            "select_subtitle": "all",
            "format": format,
            "log_level": "OFF",
            "binary_merge": True,
        }

        if keys:
            payload["keys"] = keys
        elif key:
            payload["key"] = key
        else:
            return {"success": False, "error": "No decryption key(s) provided"}

        try:
            response = self.session.post(
                f"{self.api_url}/process",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "job_id": data.get('job_id'),
                "status": "processing_started",
                "message": "Processing started in background",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to start processing: {e}"}

    def _monitor_job(self, job_id: str, timeout: int) -> Dict[str, Any]:
        """Monitor a processing job until completion."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.session.get(
                    f"{self.api_url}/jobs/{job_id}",
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()
                status = data.get('status')
                if status == "completed":
                    filename = data.get('filename')
                    file_url = data.get('url')
                    return {
                        "success": True,
                        "filename": filename,
                        "file_size_mb": data.get('file_size_mb'),
                        "file_url": f"{self.api_url}{file_url}",
                        "download_url": f"{self.api_url}/stream/{filename}",
                    }
                elif status == "error":
                    return {"success": False, "error": data.get('error', 'Unknown error')}
                time.sleep(5)
            except Exception:
                pass
        return {"success": False, "error": "Processing timeout"}


def process_drm_simple(url: str, save_name: str, key: str = None, keys: list = None,
                       **kwargs) -> Dict[str, Any]:
    """Convenience wrapper around :class:`SimpleDRMProcessor`."""
    proxy_config = get_proxy_config()
    default_api_url = proxy_config.get_proxy('nm3u8_processor')
    processor = SimpleDRMProcessor(kwargs.get('api_url', default_api_url))
    return processor.process_drm_content(
        url=url,
        save_name=save_name,
        key=key,
        keys=keys,
        quality=kwargs.get('quality', 'best'),
        format=kwargs.get('format', 'mp4'),
        timeout=kwargs.get('timeout', 1800),
    )
