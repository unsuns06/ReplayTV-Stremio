from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class ConfigResponse(BaseModel):
    addonCatalogs: bool = True

@router.get("/configure")
async def configure():
    return {
        "message": "Configure your addon settings"
    }

@router.get("/configure/configure.html")
async def configure_html():
    # Return a simple HTML form for configuration
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Configure Catch-up TV & More</title>
    </head>
    <body>
        <h1>Configure Addon</h1>
        <p>No configuration available at the moment.</p>
    </body>
    </html>
    """