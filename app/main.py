from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from app.routers import catalog, meta, stream, configure
from app.manifest import get_manifest
import os
import traceback
import logging
from datetime import datetime
from app.utils.client_ip import set_client_ip, normalize_ip
from app.utils.credentials import load_credentials

# Configure comprehensive logging with Unicode support
import sys
import tempfile

# Robust logging configuration with fallback when file writing is not permitted
LOG_FILE_PATH = os.getenv('LOG_FILE', os.path.join(tempfile.gettempdir(), 'server_debug.log'))
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'false').lower() in ('1', 'true', 'yes', 'on')
FILE_LOG_ENABLED = False

handlers = []

# Always log to console
console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
handlers.append(console_handler)

# Try to add file handler if enabled
if LOG_TO_FILE:
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
        FILE_LOG_ENABLED = True
    except Exception:
        # Fall back to console-only if file cannot be opened (e.g., permission denied)
        FILE_LOG_ENABLED = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=handlers
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catch-up TV & More for Stremio",
    description="A Python-based Stremio add-on for French live TV and replays",
    version="1.1.0"
)

# Add CORS middleware to allow requests from Stremio
# Note: allow_credentials=False is required when using wildcard origins
# Stremio clients need proper CORS preflight (OPTIONS) handling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when using wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers to clients
)

# Helper: decode viewer IP from a signed token header (if present)
def _ip_from_token(token: str):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        import json as _json
        import base64
        def _b64url_decode(s: str) -> bytes:
            pad = '=' * (-len(s) % 4)
            return base64.urlsafe_b64decode(s + pad)
        payload_b = _b64url_decode(parts[1])
        payload = _json.loads(payload_b.decode('utf-8', errors='ignore'))
        return payload.get('ip')
    except Exception:
        return None

# Custom middleware for comprehensive error logging
@app.middleware("http")
async def log_requests_and_responses(request: Request, call_next):
    """Log all requests and responses with detailed error information"""
    start_time = datetime.now()
    
    # Log the incoming request
    logger.info(f"🔍 REQUEST: {request.method} {request.url}")
    logger.info(f"   Headers: {dict(request.headers)}")
    logger.info(f"   Query Params: {dict(request.query_params)}")

    # Extract and store viewer IP for downstream requests
    try:
        headers = request.headers
        ip_token = headers.get('x-ip-token') or headers.get('X-IP-Token')
        xff = headers.get('x-forwarded-for') or headers.get('X-Forwarded-For')
        cfip = headers.get('cf-connecting-ip') or headers.get('CF-Connecting-IP')
        xreal = headers.get('x-real-ip') or headers.get('X-Real-IP')
        client_conn_ip = request.client.host if request.client else None

        viewer_ip = None
        # Prefer signed token if present
        if ip_token:
            viewer_ip = _ip_from_token(ip_token)
        if not viewer_ip and xff:
            viewer_ip = xff.split(',')[0].strip()
        elif not viewer_ip and cfip:
            viewer_ip = cfip.strip()
        elif not viewer_ip and xreal:
            viewer_ip = xreal.strip()
        elif not viewer_ip and client_conn_ip:
            viewer_ip = client_conn_ip

        viewer_ip = normalize_ip(viewer_ip)

        set_client_ip(viewer_ip)
        logger.info(f"   Viewer-IP: {viewer_ip}")
    except Exception as e:
        logger.warning(f"   Failed to extract viewer IP: {e}")

    try:
        # Process the request
        response = await call_next(request)
        
        # Log the response
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ RESPONSE: {response.status_code} in {process_time:.3f}s")
        # Attempt to log the response content for debugging
        try:
            # Read the response body (works for StreamingResponse, JSONResponse, etc.)
            if hasattr(response, "body_iterator"):
                # For StreamingResponse, we can't access the body directly
                logger.info("   Response Content: <streaming or generator response, not directly loggable>")
            elif hasattr(response, "body"):
                # For JSONResponse and similar
                content = response.body
                if isinstance(content, bytes):
                    try:
                        content_str = content.decode("utf-8")
                    except Exception:
                        content_str = str(content)
                else:
                    content_str = str(content)
                logger.info(f"   Response Content: {content_str[:2000]}{'...' if len(content_str) > 2000 else ''}")
            else:
                logger.info("   Response Content: <unknown response type>")
        except Exception as e:
            logger.error(f"   Could not log response content: {e}")
        
        return response
        
    except Exception as e:
        # Log detailed error information
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ ERROR in {request.method} {request.url} after {process_time:.3f}s")
        logger.error(f"   Error Type: {type(e).__name__}")
        logger.error(f"   Error Message: {str(e)}")
        logger.error("   Full Traceback:")
        logger.error(traceback.format_exc())
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(e),
                "type": type(e).__name__,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url)
            }
        )

# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that logs everything"""
    logger.error("🚨 GLOBAL EXCEPTION HANDLER TRIGGERED")
    logger.error(f"   Request: {request.method} {request.url}")
    logger.error(f"   Exception Type: {type(exc).__name__}")
    logger.error(f"   Exception Message: {str(exc)}")
    logger.error("   Full Traceback:")
    logger.error(traceback.format_exc())
    
    # Log request details
    try:
        body = await request.body()
        if body:
            logger.error(f"   Request Body: {body.decode('utf-8', errors='ignore')[:1000]}...")
    except Exception:
        logger.error("   Request Body: Could not read")
    
    # Log headers
    logger.error(f"   Request Headers: {dict(request.headers)}")
    
    note = "Check logs for full details"
    if FILE_LOG_ENABLED:
        note = f"Check {LOG_FILE_PATH} for full details"
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Unhandled Exception",
            "message": str(exc),
            "type": type(exc).__name__,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url),
            "note": note
        }
    )

# Mount static files for logos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(catalog.router, prefix="", tags=["catalog"])
app.include_router(meta.router, prefix="", tags=["meta"])
app.include_router(stream.router, prefix="", tags=["stream"])
app.include_router(configure.router, prefix="", tags=["configure"])

# --- Startup diagnostics: validate credentials JSON early ---

@app.on_event("startup")
async def startup_diagnostics():
    try:
        logger.info("🔧 Startup diagnostics: loading credentials...")
        creds = load_credentials()
        providers = list(creds.keys()) if isinstance(creds, dict) else []
        # Sanitize output: do not log secrets, only presence and shapes
        summary = {}
        for name, val in (creds.items() if isinstance(creds, dict) else []):
            if isinstance(val, dict):
                summary[name] = sorted([k for k in val.keys()])
            else:
                summary[name] = f"<{type(val).__name__}>"
        logger.info(f"✅ Credentials loaded. Providers present: {providers}")
        logger.info(f"✅ Credentials keys by provider (sanitized): {summary}")
    except Exception as e:
        logger.error(f"❌ Startup diagnostics failed while loading credentials: {e}")


@app.get("/manifest.json")
async def manifest():
    try:
        manifest_data = get_manifest()
        logger.info("✅ Manifest generated successfully")
        return manifest_data
    except Exception as e:
        logger.error(f"❌ Error generating manifest: {e}")
        logger.error(traceback.format_exc())
        raise

@app.get("/")
async def root():
    return {"message": "Catch-up TV & More for Stremio API"}

@app.get("/debug/logs")
async def get_debug_logs():
    """Endpoint to view recent debug logs"""
    if not FILE_LOG_ENABLED:
        return {"error": "File logging is disabled in this environment"}
    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Return last 100 lines
            recent_logs = lines[-100:] if len(lines) > 100 else lines
            return {
                "log_file": LOG_FILE_PATH,
                "total_lines": len(lines),
                "recent_lines": recent_logs,
                "timestamp": datetime.now().isoformat()
            }
    except FileNotFoundError:
        return {"error": "Log file not found", "path": LOG_FILE_PATH}
    except Exception as e:
        return {"error": f"Could not read logs: {e}", "path": LOG_FILE_PATH}

@app.get("/debug/status")
async def get_debug_status():
    """Endpoint to check server status and configuration"""
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "ADDON_BASE_URL": os.getenv('ADDON_BASE_URL', 'Not set'),
            "HOST": os.getenv('HOST', '127.0.0.1'),
            "PORT": os.getenv('PORT', '7860'),
            "LOG_LEVEL": "INFO"
        },
        "logging": {
            "file_enabled": FILE_LOG_ENABLED,
            "log_file_path": LOG_FILE_PATH,
        },
        "note": "Check /debug/logs for details when file logging is enabled"
    }

@app.get("/debug/credentials")
async def debug_credentials():
    """Return sanitized credentials and file/env presence for debugging deployments."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cred_primary = os.path.join(repo_root, 'credentials.json')
    cred_fallback = os.path.join(repo_root, 'credentials-test.json')
    env_present = bool(os.getenv('CREDENTIALS_JSON'))

    info = {
        "files": {
            "credentials.json_exists": os.path.exists(cred_primary),
            "credentials-test.json_exists": os.path.exists(cred_fallback),
            "credentials.json_path": cred_primary,
            "credentials-test.json_path": cred_fallback,
        },
        "env": {
            "CREDENTIALS_JSON_present": env_present,
            "CREDENTIALS_JSON_length": len(os.getenv('CREDENTIALS_JSON', '')) if env_present else 0,
        },
        "providers": {},
        "timestamp": datetime.now().isoformat()
    }

    try:
        creds = load_credentials()
        if isinstance(creds, dict):
            for name, val in creds.items():
                if isinstance(val, dict):
                    info["providers"][name] = sorted(list(val.keys()))
                else:
                    info["providers"][name] = f"<{type(val).__name__}>"
        else:
            info["providers"] = "<non-dict>"
    except Exception as e:
        info["error"] = f"Failed to load credentials: {e}"
    return info
