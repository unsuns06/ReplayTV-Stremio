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

def safe_log(logger, level: str, message: str):
    """Safely log messages with Unicode support"""
    try:
        if level.upper() == 'INFO':
            logger.info(message)
        elif level.upper() == 'ERROR':
            logger.error(message)
        elif level.upper() == 'WARNING':
            logger.warning(message)
        elif level.upper() == 'DEBUG':
            logger.debug(message)
        else:
            logger.info(message)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe version
        safe_message = message.encode('ascii', errors='replace').decode('ascii')
        if level.upper() == 'INFO':
            logger.info(safe_message)
        elif level.upper() == 'ERROR':
            logger.error(safe_message)
        elif level.upper() == 'WARNING':
            logger.warning(safe_message)
        elif level.upper() == 'DEBUG':
            logger.debug(safe_message)
        else:
            logger.info(safe_message)
