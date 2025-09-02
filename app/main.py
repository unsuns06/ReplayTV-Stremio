from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from app.routers import catalog, meta, stream, configure
from app.manifest import get_manifest
import os
import traceback
import json
import logging
from datetime import datetime

# Configure comprehensive logging with Unicode support
import sys

# Create handlers with proper encoding
file_handler = logging.FileHandler('server_debug.log', encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)

# Set formatters
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catch-up TV & More for Stremio",
    description="A Python-based Stremio add-on for French live TV and replays",
    version="1.0.0"
)

# Add CORS middleware to allow requests from Stremio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware for comprehensive error logging
@app.middleware("http")
async def log_requests_and_responses(request: Request, call_next):
    """Log all requests and responses with detailed error information"""
    start_time = datetime.now()
    
    # Log the incoming request
    logger.info(f"🔍 REQUEST: {request.method} {request.url}")
    logger.info(f"   Headers: {dict(request.headers)}")
    logger.info(f"   Query Params: {dict(request.query_params)}")
    
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
        logger.error(f"   Full Traceback:")
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
    logger.error(f"🚨 GLOBAL EXCEPTION HANDLER TRIGGERED")
    logger.error(f"   Request: {request.method} {request.url}")
    logger.error(f"   Exception Type: {type(exc).__name__}")
    logger.error(f"   Exception Message: {str(exc)}")
    logger.error(f"   Full Traceback:")
    logger.error(traceback.format_exc())
    
    # Log request details
    try:
        body = await request.body()
        if body:
            logger.error(f"   Request Body: {body.decode('utf-8', errors='ignore')[:1000]}...")
    except:
        logger.error(f"   Request Body: Could not read")
    
    # Log headers
    logger.error(f"   Request Headers: {dict(request.headers)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Unhandled Exception",
            "message": str(exc),
            "type": type(exc).__name__,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url),
            "note": "Check server_debug.log for full details"
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
from app.utils.credentials import load_credentials

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
    try:
        with open('server_debug.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Return last 100 lines
            recent_logs = lines[-100:] if len(lines) > 100 else lines
            return {
                "log_file": "server_debug.log",
                "total_lines": len(lines),
                "recent_lines": recent_logs,
                "timestamp": datetime.now().isoformat()
            }
    except FileNotFoundError:
        return {"error": "Log file not found"}
    except Exception as e:
        return {"error": f"Could not read logs: {e}"}

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
        "log_file": "server_debug.log",
        "note": "Check /debug/logs for detailed error information"
    }