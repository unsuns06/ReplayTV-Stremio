#!/usr/bin/env python3
"""
Base URL utility for serving static assets
Handles proper URL construction for deployed environments
"""

import os
from typing import Optional
from fastapi import Request


def get_base_url(request: Optional[Request] = None) -> str:
    """
    Get the base URL for serving static assets.
    
    Priority order:
    1. ADDON_BASE_URL environment variable (if set)
    2. Constructed from current request (if available)
    3. Default fallback
    
    Args:
        request: FastAPI Request object (optional)
        
    Returns:
        Base URL string for serving static assets
    """
    # First try environment variable
    env_base_url = os.getenv('ADDON_BASE_URL')
    if env_base_url:
        return env_base_url.rstrip('/')
    
    # If we have a request, construct from it
    if request:
        # Get the scheme (http/https)
        scheme = request.url.scheme
        
        # Get the host and port
        host = request.url.hostname
        port = request.url.port
        
        # Construct base URL
        if port and port not in [80, 443]:
            base_url = f"{scheme}://{host}:{port}"
        else:
            base_url = f"{scheme}://{host}"
        
        return base_url
    
    # Fallback to default
    return 'http://localhost:7860'


def get_static_url(path: str, request: Optional[Request] = None) -> str:
    """
    Get a complete URL for a static asset.
    
    Args:
        path: Path to the static asset (e.g., "static/logos/fr/france2.png")
        request: FastAPI Request object (optional)
        
    Returns:
        Complete URL for the static asset
    """
    base_url = get_base_url(request)
    
    # Ensure path starts with /
    if not path.startswith('/'):
        path = f"/{path}"
    
    return f"{base_url}{path}"


def get_logo_url(provider: str, channel: str, request: Optional[Request] = None) -> str:
    """
    Get a complete URL for a channel logo.
    
    Args:
        provider: Provider name (e.g., "fr")
        channel: Channel name (e.g., "france2")
        request: FastAPI Request object (optional)
        
    Returns:
        Complete URL for the channel logo
    """
    logo_path = f"static/logos/{provider}/{channel}.png"
    return get_static_url(logo_path, request)
