#!/usr/bin/env python
import uvicorn
import sys
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Add the current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
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
        log_level=log_level,
        access_log=True
    )