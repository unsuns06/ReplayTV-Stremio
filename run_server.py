#!/usr/bin/env python
import uvicorn
import sys
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Add the current directory to Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    # Get configuration from environment variables with fallbacks
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "7860"))
    log_level = os.getenv("LOG_LEVEL", "debug").lower()
    
    # Run the uvicorn server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        # Watch programs.json as well — uvicorn's reloader only looks at *.py,
        # so a show added through tools/programs-editor stayed invisible until
        # the 1-hour programs-file cache expired. Restarting also drops the
        # in-memory catalogue caches, which is what makes the change show up.
        reload_dirs=[project_root],
        reload_includes=["programs.json"],
        log_level=log_level,
        access_log=True
    )