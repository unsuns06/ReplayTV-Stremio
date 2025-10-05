#!/usr/bin/env python3
"""
Simple DRM Content Processor
Processes DRM-protected content using N_m3u8DL-RE API
"""

import requests
import time
import json
from typing import Optional, Dict, Any


class SimpleDRMProcessor:
    """Simple DRM content processor"""

    def __init__(self, api_url: str = "https://alphanet06-processor.hf.space"):
        """Initialize with API URL"""
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()

    def process_drm_content(self,
                           url: str,
                           save_name: str,
                           key: str,
                           quality: str = "best",
                           format: str = "mkv",
                           timeout: int = 1800) -> Dict[str, Any]:
        """
        Process DRM-protected content

        Args:
            url: DRM-protected content URL
            save_name: Name for the output file
            key: DRM decryption key
            quality: Video quality selection
            format: Output format (mkv, mp4, etc.)
            timeout: Processing timeout in seconds

        Returns:
            Dict with processing results
        """
        # Trigger processing silently
        payload = {
            "url": url,
            "save_name": save_name,
            "key": key,
            "select_video": quality,
            "select_audio": "all",
            "select_subtitle": "all",
            "format": format,
            "log_level": "OFF",
            "binary_merge": True
        }

        try:
            # Start processing
            response = self.session.post(
                f"{self.api_url}/process",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            job_id = data.get('job_id')

            # Return immediately without monitoring - processing happens in background
            return {
                "success": True,
                "job_id": job_id,
                "status": "processing_started",
                "message": "Processing started in background"
            }

        except requests.RequestException as e:
            return {
                "success": False,
                "error": f"Failed to start processing: {e}"
            }

    def _monitor_job(self, job_id: str, timeout: int) -> Dict[str, Any]:
        """Monitor processing job until completion"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.session.get(
                    f"{self.api_url}/jobs/{job_id}",
                    timeout=10
                )
                response.raise_for_status()

                data = response.json()
                status = data.get('status')

                if status == "completed":
                    filename = data.get('filename')
                    file_url = data.get('url')
                    file_size = data.get('file_size_mb')

                    return {
                        "success": True,
                        "filename": filename,
                        "file_size_mb": file_size,
                        "file_url": f"{self.api_url}{file_url}",
                        "download_url": f"{self.api_url}/stream/{filename}"
                    }

                elif status == "error":
                    error = data.get('error', 'Unknown error')
                    return {
                        "success": False,
                        "error": error
                    }

                # Still processing - wait silently
                time.sleep(5)

            except requests.RequestException as e:
                # Silent failure handling - don't print progress
                pass

        return {
            "success": False,
            "error": "Processing timeout"
        }


def process_drm_simple(url: str, save_name: str, key: str = None, keys: list = None, **kwargs) -> Dict[str, Any]:
    """
    Simple function to process DRM content

    Args:
        url: DRM-protected content URL
        save_name: Name for the output file
        key: DRM decryption key (single key)
        keys: List of DRM decryption keys (multiple keys)
        **kwargs: Additional arguments (quality, format, timeout, api_url)

    Returns:
        Dict with processing results
    """
    # Handle multiple keys for TF1
    if keys and len(keys) > 0:
        # For multiple keys, we'll process with the first key and add the rest as additional keys
        primary_key = keys[0]
        # Create a combined key string with all keys
        combined_key = keys[0]
        for additional_key in keys[1:]:
            combined_key += f" --key {additional_key}"

        # Update the save_name to indicate multiple keys
        save_name = f"{save_name}_multi_key"

        processor = SimpleDRMProcessor(kwargs.get('api_url', 'https://alphanet06-processor.hf.space'))

        return processor.process_drm_content(
            url=url,
            save_name=save_name,
            key=combined_key,
            quality=kwargs.get('quality', 'best'),
            format=kwargs.get('format', 'mkv'),
            timeout=kwargs.get('timeout', 1800)
        )
    elif key:
        processor = SimpleDRMProcessor(kwargs.get('api_url', 'https://alphanet06-processor.hf.space'))

        return processor.process_drm_content(
            url=url,
            save_name=save_name,
            key=key,
            quality=kwargs.get('quality', 'best'),
            format=kwargs.get('format', 'mp4'),
            timeout=kwargs.get('timeout', 1800)
        )
    else:
        return {"success": False, "error": "No decryption key provided"}


# Example usage (for testing)
# if __name__ == "__main__":
#     result = process_drm_simple(
#         url="https://example.com/drm-content.mpd",
#         save_name="my_video",
#         key="your_drm_key_here",
#         quality="best",
#         format="mp4"
#     )
#
#     if result["success"]:
#         print(f"Success! File ready for download: {result['download_url']}")
#     else:
#         print(f"Failed: {result['error']}")
