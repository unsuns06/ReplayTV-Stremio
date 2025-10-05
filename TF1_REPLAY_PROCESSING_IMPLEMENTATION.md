# TF1 Replay Processing Implementation

## Overview
This implementation adds automatic DRM processing for TF1 replay content using N_m3u8DL-RE with multiple decryption keys extracted via pywidevine.

## Changes Made

### 1. Updated `app/utils/nm3u8_drm_processor.py`
- **Added multi-key support**: The `process_drm_content()` method now accepts both single `key` parameter and multiple `keys` parameter (list)
- **Backward compatible**: Existing single-key usage still works
- **API payload**: Sends either `"key"` or `"keys"` array to the processing API

#### Key Changes:
```python
def process_drm_content(self,
                       url: str,
                       save_name: str,
                       key: str = None,
                       keys: list = None,  # NEW: Support multiple keys
                       quality: str = "best",
                       format: str = "mkv",
                       timeout: int = 1800) -> Dict[str, Any]:
```

### 2. Updated `app/providers/fr/mytf1.py`
Added comprehensive DRM processing for TF1 replay streams:

#### A. Processed File Check (Lines 1033-1051)
- Before processing, checks if file already exists at `https://alphanet06-processor.hf.space/stream/{episode_id}.mp4`
- If exists, returns immediately with direct video URL (no DRM needed)
- Avoids redundant processing

#### B. DRM Key Extraction (Lines 1058-1102)
- Uses `TF1DRMExtractor` from `tf1_drm_key_extractor.py`
- Extracts all DRM keys from the MPD manifest using pywidevine
- Formats keys as `kid:key` pairs for N_m3u8DL-RE
- Example output:
  ```
  ✅ [MyTF1Provider] Extracted 3 DRM key(s)
     KID: abc123... -> KEY: def456...
     KID: ghi789... -> KEY: jkl012...
  ```

#### C. Background Processing Trigger (Lines 1079-1095)
- Triggers `process_drm_simple()` with multiple keys
- Processing happens in background (non-blocking)
- Uses N_m3u8DL-RE command format:
  ```bash
  N_m3u8DL-RE "{video_url}" \
    --save-name "{episode_id}" \
    --select-video best \
    --select-audio all \
    --select-subtitle all \
    -mt \
    -M format=mp4 \
    --log-level OFF \
    --binary-merge \
    --key {kid1}:{key1} \
    --key {kid2}:{key2} \
    --key {kid3}:{key3}
  ```

#### D. Stream Response (Lines 1137-1166)
- **Returns array of 2 streams** (not single stream):
  1. **Primary Stream**: DASH proxy URL for immediate playback (with DRM)
  2. **Secondary Stream**: 
     - If processed file exists: Direct video URL (no DRM)
     - If not exists: "Stream not available" placeholder with processing message
- Includes DRM keys in primary stream for debugging
- User can choose between streams in Stremio
- Processing happens in parallel while user watches via DASH proxy
- Second stream shows clear status: ready or processing

### 3. Updated `requirements.txt`
Added required dependencies:
- `requests>=2.25.0` - For HTTP requests in tf1_drm_key_extractor.py
- `pywidevine>=1.4.0` - For Widevine DRM key extraction

## Workflow

### For TF1 Replay Streams:

1. **Check Processed File**
   - HEAD request to `https://alphanet06-processor.hf.space/stream/{episode_id}.mp4`
   - If 200 OK → Return single stream with direct video URL ✅ (DONE)
   - If 404 → Set `processed_file_exists = False` and continue ⬇️

2. **Extract DRM Keys**
   - Load Widevine device from `app/providers/fr/device.wvd`
   - Fetch MPD manifest and extract PSSH
   - Generate license challenge
   - Request license from TF1 server
   - Parse license and extract all content keys
   - Format as `kid:key` pairs

3. **Trigger Background Processing**
   - POST to `https://alphanet06-processor.hf.space/process`
   - Payload includes:
     - `url`: MPD manifest URL
     - `save_name`: Episode ID
     - `keys`: Array of `kid:key` strings
     - `quality`: "best"
     - `format`: "mp4"
     - `binary_merge`: true
   - Returns immediately with job_id

4. **Return Multiple Streams**
   - Returns **array of 2 streams**:
     - **Stream 1**: DASH proxy URL (immediate playback with DRM)
     - **Stream 2**: 
       - If `processed_file_exists = True`: Direct video URL (ready to play)
       - If `processed_file_exists = False`: "Stream not available" placeholder
   - User can choose which stream to play in Stremio
   - Second stream clearly indicates if it's ready or still processing
   - Next time user requests same episode → processed file is ready (stream 2 shows direct URL)

## Key Features

### ✅ Non-Blocking Processing
- User gets immediate playback via DASH proxy
- Processing happens in background
- No waiting for download to complete

### ✅ Multi-Key Support
- Handles content with multiple DRM keys (video, audio, subtitles)
- Automatically extracts all keys from license
- Passes all keys to N_m3u8DL-RE

### ✅ Smart Caching
- Checks for existing processed files first
- Avoids redundant processing
- Instant playback for previously processed content

### ✅ Graceful Degradation
- If pywidevine not installed → Falls back to DASH proxy only
- If key extraction fails → Still returns DASH proxy stream
- If processing fails → User can still watch via DASH proxy

### ✅ Detailed Logging
- Logs every step of DRM extraction
- Shows extracted keys (for debugging)
- Tracks processing status

## Dependencies

### Required for DRM Processing:
- `pywidevine>=1.4.0` - Widevine CDM implementation
- `requests>=2.25.0` - HTTP client
- Valid Widevine device file at `app/providers/fr/device.wvd`

### Optional:
- If pywidevine not available, falls back to DASH proxy only
- Processing still works, just without automatic key extraction

## Testing

To test the implementation:

1. **Request a TF1 replay episode**
   ```
   GET /stream/cutam:fr:mytf1:episode:{episode_id}
   ```

2. **First Request (No Processed File)**
   - Should extract DRM keys
   - Trigger background processing
   - Return **2 streams**:
     - Stream 1: "DASH Proxy Stream (DRM)" ✅ Works immediately
     - Stream 2: "⏳ Processed Version (Processing in background...)" ⚠️ Stream not available
   - Check logs for key extraction
   - User can play Stream 1 immediately

3. **Second Request (After Processing)**
   - Should find processed file (200 OK)
   - Return **1 stream**: "Processed Version (No DRM)" ✅ Direct video URL
   - No DRM processing needed
   - Instant playback

4. **Check Logs**
   ```
   ✅ [MyTF1Provider] Extracting DRM keys for TF1 replay...
   ✅ [MyTF1Provider] Extracted 3 DRM key(s)
      KID: abc123... -> KEY: def456...
   ✅ [MyTF1Provider] Triggering background DRM processing...
   ✅ [MyTF1Provider] Background processing started successfully
   ```

## Comparison with 6play Implementation

### Similarities:
- Both check for processed files first
- Both trigger background processing
- Both return original stream for immediate playback
- Both use same processing API

### Differences:
- **TF1**: Uses `TF1DRMExtractor` with pywidevine for local key extraction
- **6play**: Uses CDRM API for remote key extraction
- **TF1**: Supports multiple keys per stream
- **6play**: Typically single key per stream
- **TF1**: Returns **array of 2 streams** (DASH proxy + processed file)
- **6play**: Returns single stream (MediaFlow ClearKey or direct DRM)
- **TF1**: User can choose between DRM and processed versions
- **6play**: Single stream approach

## Notes

- **LIVE FEEDS NOT AFFECTED**: This implementation only affects TF1 replay content (episodes)
- **Two streams returned**: User gets choice between DRM stream and processed file
- **Processing is optional**: If it fails, user can still watch via DASH proxy (stream 1)
- **Device file required**: Must have valid `device.wvd` file for key extraction
- **Stream selection**: User can choose in Stremio which stream to play
  - **Stream 1**: Immediate playback with DRM (DASH proxy) - Always works
  - **Stream 2**: 
    - First request: "Stream not available" (processing in background)
    - Second request: Direct video URL (no DRM, instant playback)
- **Clear status indication**: Second stream shows if it's ready or still processing
