from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from app.routers import catalog, meta, stream, configure
from app.manifest import get_manifest
import os
import logging
from datetime import datetime
from app.utils.client_ip import set_ip_from_request
from app.utils.credentials import load_credentials

# Configure comprehensive logging with Unicode support
import sys
import tempfile

# Windows consoles default to cp1252, which cannot encode the emoji used in
# log messages — every such line would raise UnicodeEncodeError inside the
# logging handler.  Reconfigure both std streams to UTF-8 (errors="replace"
# keeps logging alive even if the terminal still can't render a character).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

_LOG_LEVEL_STR = os.getenv('LOG_LEVEL', 'info').lower()
_LOG_LEVEL = getattr(logging, _LOG_LEVEL_STR.upper(), logging.INFO)

# Robust logging configuration with fallback when file writing is not permitted
LOG_FILE_PATH = os.getenv('LOG_FILE', os.path.join(tempfile.gettempdir(), 'server_debug.log'))
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'false').lower() in ('1', 'true', 'yes', 'on')
FILE_LOG_ENABLED = False

handlers = []

# Always log to console (stdout was reconfigured to UTF-8 above)
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
    level=_LOG_LEVEL,
    handlers=handlers
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("🔧 Startup diagnostics: loading credentials...")
        creds = load_credentials()
        providers = list(creds.keys()) if isinstance(creds, dict) else []
        summary = {}
        for name, val in (creds.items() if isinstance(creds, dict) else []):
            if isinstance(val, dict):
                summary[name] = sorted(val.keys())
            else:
                summary[name] = f"<{type(val).__name__}>"
        logger.info("✅ Credentials loaded. Providers present: %s", providers)
        logger.info("✅ Credentials keys by provider (sanitized): %s", summary)
    except Exception as e:
        logger.error("❌ Startup diagnostics failed while loading credentials: %s", e)
    yield


app = FastAPI(
    title="Catch-up TV & More for Stremio",
    description="A Python-based Stremio add-on for French live TV and replays",
    version="1.1.0",
    lifespan=lifespan,
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

@app.middleware("http")
async def log_requests_and_responses(request: Request, call_next):
    start_time = datetime.now()
    logger.debug("REQUEST: %s %s", request.method, request.url)
    try:
        set_ip_from_request(request.headers, request.client.host if request.client else None)
    except Exception as e:
        logger.warning("Failed to extract viewer IP: %s", e)
    # Unhandled exceptions propagate to the global exception handler below,
    # which owns the 500 response — the middleware only logs timing.
    response = await call_next(request)
    logger.debug("RESPONSE: %s in %.3fs", response.status_code, (datetime.now() - start_time).total_seconds())
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception in %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Unhandled Exception",
            "message": str(exc),
            "type": type(exc).__name__,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url),
        }
    )

# Mount static files for logos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(catalog.router, prefix="", tags=["catalog"])
app.include_router(meta.router, prefix="", tags=["meta"])
app.include_router(stream.router, prefix="", tags=["stream"])
app.include_router(configure.router, prefix="", tags=["configure"])


@app.get("/manifest.json")
async def manifest():
    try:
        manifest_data = get_manifest()
        logger.info("Manifest generated successfully")
        return manifest_data
    except Exception:
        logger.exception("Error generating manifest")
        raise

@app.get("/")
async def root():
    return {"message": "Catch-up TV & More for Stremio API"}

@app.get("/health")
async def health():
    """Health check endpoint for deployment monitoring."""
    from app.config.provider_config import PROVIDER_REGISTRY
    from app.utils.cache import cache as _cache
    providers_status = {}
    try:
        creds = load_credentials()
        for key, cfg in PROVIDER_REGISTRY.items():
            creds_key = cfg.get("credentials_key", key)
            providers_status[key] = "configured" if creds.get(creds_key) else "unconfigured"
    except Exception as e:
        providers_status = {"error": str(e)}
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "log_level": _LOG_LEVEL_STR.upper(),
        "providers": providers_status,
        "cache": _cache.stats(),
    }


if os.getenv("ENABLE_DEBUG_ENDPOINTS"):
    @app.get("/debug/logs")
    async def get_debug_logs():
        if not FILE_LOG_ENABLED:
            return {"error": "File logging is disabled"}
        try:
            with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            recent = lines[-100:] if len(lines) > 100 else lines
            return {"log_file": LOG_FILE_PATH, "total_lines": len(lines), "recent_lines": recent, "timestamp": datetime.now().isoformat()}
        except FileNotFoundError:
            return {"error": "Log file not found", "path": LOG_FILE_PATH}
        except Exception as e:
            return {"error": f"Could not read logs: {e}"}

    @app.get("/debug/status")
    async def get_debug_status():
        return {
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "environment": {"ADDON_BASE_URL": os.getenv('ADDON_BASE_URL', 'Not set'), "LOG_LEVEL": _LOG_LEVEL_STR.upper()},
            "logging": {"file_enabled": FILE_LOG_ENABLED, "log_file_path": LOG_FILE_PATH},
        }

    @app.get("/debug/credentials")
    async def debug_credentials():
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        cred_primary = os.path.join(repo_root, 'credentials.json')
        cred_fallback = os.path.join(repo_root, 'credentials-test.json')
        env_present = bool(os.getenv('CREDENTIALS_JSON'))
        info = {
            "files": {"credentials.json_exists": os.path.exists(cred_primary), "credentials-test.json_exists": os.path.exists(cred_fallback)},
            "env": {"CREDENTIALS_JSON_present": env_present, "CREDENTIALS_JSON_length": len(os.getenv('CREDENTIALS_JSON', '')) if env_present else 0},
            "providers": {}, "timestamp": datetime.now().isoformat()
        }
        try:
            creds = load_credentials()
            if isinstance(creds, dict):
                info["providers"] = {name: sorted(val.keys()) if isinstance(val, dict) else f"<{type(val).__name__}>" for name, val in creds.items()}
            else:
                info["providers"] = "<non-dict>"
        except Exception as e:
            info["error"] = f"Failed to load credentials: {e}"
        return info
