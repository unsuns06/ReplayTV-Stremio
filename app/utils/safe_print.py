#!/usr/bin/env python3
"""
Safe printing utility to handle Unicode characters gracefully
"""


def safe_print(message: str):
    """Safely print messages with Unicode support"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe version
        safe_message = message.encode('ascii', errors='replace').decode('ascii')
        print(safe_message)

