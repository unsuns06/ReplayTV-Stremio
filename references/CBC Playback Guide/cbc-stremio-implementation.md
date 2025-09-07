# CBC Gem Stremio Addon - Complete Implementation Guide

## Overview

This document provides a complete implementation guide for integrating CBC Gem authentication and streaming capabilities into a Stremio Python addon, based on the yt-dlp CBC extractor analysis.

## Authentication Architecture

CBC Gem uses OAuth 2.0 with Resource Owner Password Credentials (ROPC) flow and implements a multi-token system:

1. **Refresh Token**: Long-lived token for obtaining new access tokens
2. **Access Token**: Short-lived token for API authentication
3. **Claims Token**: Contains user subscription/access rights for content

## Key Components Analysis

### Constants and URLs
```python
CLIENT_ID = 'fc05b0ee-3865-4400-a3cc-3da82c330c23'
SETTINGS_URL = 'https://services.radio-canada.ca/ott/catalog/v1/gem/settings'
SHOW_API_URL = 'https://services.radio-canada.ca/ott/catalog/v2/gem/show/'
VALIDATION_URL = 'https://services.radio-canada.ca/media/validation/v2/'
CLAIMS_URL = 'https://services.radio-canada.ca/ott/subscription/v2/gem/Subscriber/profile'
```

### Authentication Flow
1. Fetch ROPC settings from CBC
2. Login with username/password to get refresh + access tokens
3. Use access token to obtain claims token
4. Use claims token for content access requests

### Content Access Parameters
```python
validation_params = {
    'appCode': 'gem',
    'connectionType': 'hd', 
    'deviceType': 'ipad',
    'multibitrate': 'true',
    'output': 'json',
    'tech': 'hls',
    'manifestVersion': '2',
    'manifestType': 'desktop',
    'idMedia': item_info['idMedia']
}
```

## Critical Issues Found in yt-dlp

Based on GitHub issues analysis, there are current problems with CBC authentication:
- JSON parsing errors when fetching tokens
- Authentication API changes causing failures
- Claims token expiration handling

## Stremio Addon Implementation Strategy

The addon should implement:
1. Configuration page for user credentials
2. Token caching and refresh logic
3. Content discovery and metadata extraction
4. Stream URL resolution with authentication
5. Error handling and user feedback

## Security Considerations

- Store credentials securely
- Implement proper token refresh mechanisms
- Handle authentication failures gracefully
- Respect content geo-restrictions
- Implement rate limiting

## Next Steps

1. Create the complete addon structure
2. Implement authentication classes
3. Add content discovery endpoints
4. Create configuration interface
5. Test with various content types