#!/usr/bin/env python3
"""
N_m3u8DL-RE API Test Script
Tests the processing endpoint with a specific command
"""

import requests
import time
import sys
from datetime import datetime
from typing import Optional

class N_m3u8DLTester:
    def __init__(self, api_url: str):
        """Initialize tester with API URL."""
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()

    def log(self, message: str, level: str = "INFO"):
        """Print timestamped log message."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def check_health(self) -> bool:
        """Check if the API is healthy and tools are available."""
        self.log("Checking API health...")
        try:
            response = self.session.get(f"{self.api_url}/health", timeout=10)
            response.raise_for_status()

            data = response.json()
            self.log(f"API Status: {data['status']}")

            tools = data.get('tools', {})
            all_available = True

            for tool, status in tools.items():
                status_icon = "✅" if status == "available" else "❌"
                self.log(f"  {status_icon} {tool}: {status}")
                if status != "available":
                    all_available = False

            return all_available

        except requests.RequestException as e:
            self.log(f"Health check failed: {e}", "ERROR")
            return False

    def trigger_processing(self, url: str, save_name: str, key: str, 
                          select_video: str = "best",
                          select_audio: str = "all",
                          select_subtitle: str = "all",
                          format: str = "mkv",
                          log_level: str = "OFF",
                          additional_args: Optional[list] = None) -> Optional[str]:
        """Trigger file processing and return job ID."""

        self.log("Triggering processing request...")

        payload = {
            "url": url,
            "save_name": save_name,
            "key": key,
            "select_video": select_video,
            "select_audio": select_audio,
            "select_subtitle": select_subtitle,
            "format": format,
            "log_level": log_level
        }

        if additional_args:
            payload["additional_args"] = additional_args

        try:
            response = self.session.post(
                f"{self.api_url}/process",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            job_id = data.get('job_id')

            self.log(f"✅ Processing started!")
            self.log(f"   Job ID: {job_id}")
            self.log(f"   Expected filename: {data.get('estimated_filename')}")

            return job_id

        except requests.RequestException as e:
            self.log(f"Failed to trigger processing: {e}", "ERROR")
            if hasattr(e.response, 'text'):
                self.log(f"Response: {e.response.text}", "ERROR")
            return None

    def check_job_status(self, job_id: str) -> Optional[dict]:
        """Check the status of a job."""
        try:
            response = self.session.get(
                f"{self.api_url}/jobs/{job_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            self.log(f"Failed to check job status: {e}", "ERROR")
            return None

    def monitor_job(self, job_id: str, check_interval: int = 5, timeout: int = 1800) -> bool:
        """Monitor job until completion or timeout."""

        self.log(f"Monitoring job {job_id}...")
        self.log(f"Check interval: {check_interval}s, Timeout: {timeout}s")

        start_time = time.time()
        last_status = None

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                self.log(f"Timeout reached ({timeout}s)", "ERROR")
                return False

            # Get job status
            status_data = self.check_job_status(job_id)
            if not status_data:
                self.log("Failed to get job status", "ERROR")
                return False

            current_status = status_data.get('status')

            # Only log if status changed
            if current_status != last_status:
                self.log(f"Status: {current_status}")
                last_status = current_status

            # Check if completed
            if current_status == "completed":
                self.log("✅ Processing completed successfully!", "SUCCESS")

                filename = status_data.get('filename')
                file_url = status_data.get('url')
                file_size = status_data.get('file_size_mb')

                self.log(f"   Filename: {filename}")
                self.log(f"   File size: {file_size} MB")
                self.log(f"   URL: {self.api_url}{file_url}")

                return True

            # Check if error
            elif current_status == "error":
                self.log("❌ Processing failed!", "ERROR")

                error = status_data.get('error')
                stderr = status_data.get('stderr')
                stdout = status_data.get('stdout')

                self.log(f"   Error: {error}", "ERROR")
                if stderr:
                    self.log(f"   Stderr: {stderr[:500]}", "ERROR")  # First 500 chars
                if stdout:
                    self.log(f"   Stdout: {stdout[:500]}", "ERROR")

                return False

            # Still processing
            else:
                # Print progress indicator
                print(".", end="", flush=True)
                time.sleep(check_interval)

    def verify_file_access(self, filename: str) -> bool:
        """Verify that the processed file is accessible."""

        self.log(f"Verifying file access: {filename}")

        file_url = f"{self.api_url}/stream/6play/{filename}"

        try:
            # Send HEAD request to check if file exists
            response = self.session.head(file_url, timeout=10)

            if response.status_code == 200:
                content_length = response.headers.get('Content-Length')
                content_type = response.headers.get('Content-Type')

                self.log(f"✅ File is accessible!")
                self.log(f"   URL: {file_url}")
                self.log(f"   Content-Type: {content_type}")
                if content_length:
                    size_mb = int(content_length) / (1024 * 1024)
                    self.log(f"   Size: {size_mb:.2f} MB")

                return True
            else:
                self.log(f"❌ File not accessible (HTTP {response.status_code})", "ERROR")
                return False

        except requests.RequestException as e:
            self.log(f"Failed to verify file access: {e}", "ERROR")
            return False

    def list_all_files(self) -> list:
        """List all available files."""
        self.log("Listing all available files...")

        try:
            response = self.session.get(f"{self.api_url}/files", timeout=10)
            response.raise_for_status()

            data = response.json()
            files = data.get('files', [])

            self.log(f"Found {len(files)} file(s):")
            for f in files:
                self.log(f"   • {f['filename']} ({f['size_mb']} MB)")

            return files

        except requests.RequestException as e:
            self.log(f"Failed to list files: {e}", "ERROR")
            return []

    def run_full_test(self, url: str, save_name: str, key: str, **kwargs) -> bool:
        """Run a complete test cycle."""

        self.log("=" * 70)
        self.log("Starting N_m3u8DL-RE API Test")
        self.log("=" * 70)

        # Step 1: Health check
        if not self.check_health():
            self.log("Health check failed - aborting test", "ERROR")
            return False

        self.log("")

        # Step 2: Trigger processing
        job_id = self.trigger_processing(url, save_name, key, **kwargs)
        if not job_id:
            self.log("Failed to trigger processing - aborting test", "ERROR")
            return False

        self.log("")

        # Step 3: Monitor job
        success = self.monitor_job(job_id)
        if not success:
            self.log("Processing failed or timed out", "ERROR")
            return False

        self.log("")

        # Step 4: Verify file access
        filename = f"{save_name}.{kwargs.get('format', 'mkv')}"
        if not self.verify_file_access(filename):
            self.log("File verification failed", "ERROR")
            return False

        self.log("")

        # Step 5: List all files
        self.list_all_files()

        self.log("")
        self.log("=" * 70)
        self.log("✅ TEST COMPLETED SUCCESSFULLY!")
        self.log("=" * 70)

        return True

# REAL-DATA TEST VALUES
def main():
    """Main test function."""

    # Configuration - UPDATE THESE VALUES
    API_URL = "https://alphanet06-processor.hf.space"  # UPDATE THIS!

    # Test parameters matching your command
    TEST_CONFIG = {
        "url": "https://par5-edge-05.cdn.bedrock.tech/m6web/output/d/5/3/d53727ced0e827d7bb94cc06de7538b47d63c5e1/static/13141002_be86cce5bac3ab6950c2fa69da7a3d48_android_mobile_dash_upTo1080p_720p_vbr_cae_drm_software.mpd?st=RYHoMeobgpxkk7p9cuKNRQ&e=1759563844",
        "save_name": "clip_13141002",
        "key": "f01b16c0f7ca5aa0b843645a44b4210a",
        "select_video": "best",
        "select_audio": "all",
        "select_subtitle": "all",
        "format": "mkv",
        "log_level": "OFF"
    }

    # Check if API_URL was updated
    if "your-username" in API_URL or "your-space" in API_URL:
        print("❌ ERROR: Please update API_URL in the script with your actual Hugging Face Space URL")
        print("   Example: https://username-spacename.hf.space")
        sys.exit(1)

    # Create tester and run
    tester = N_m3u8DLTester(API_URL)
    success = tester.run_full_test(**TEST_CONFIG)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
