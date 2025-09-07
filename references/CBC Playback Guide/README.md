# CBC Gem Stremio Addon - Complete Implementation

## Overview

This is a complete Stremio addon implementation that replicates the CBC Gem authentication and streaming functionality from yt-dlp. The addon allows users to stream CBC Gem content directly through Stremio with full authentication support.

## Features

- **Complete OAuth 2.0 Authentication**: Implements the same ROPC flow as yt-dlp
- **Token Management**: Automatic refresh token handling and claims token acquisition
- **Content Discovery**: Metadata extraction and show/episode parsing
- **Stream Resolution**: Direct HLS stream URL resolution with authentication headers
- **Geo-restriction Handling**: Proper error handling for Canadian-only content
- **Configuration Interface**: Web-based setup for user credentials
- **Caching**: Intelligent token caching to minimize API calls

## Files Structure

```
cbc_stremio_addon/
├── cbc_auth.py                 # Complete authentication module
├── cbc_stremio_addon.py        # Main Flask application 
├── cbc_url_parser.py          # URL parsing utilities
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── docker/                   # Optional Docker deployment
    ├── Dockerfile
    └── docker-compose.yml
```

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- CBC Gem account (Canadian account required)
- Canadian IP address or VPN

### Local Development

1. **Clone/Download the files**:
   ```bash
   # Ensure all files are in the same directory
   ls -la
   # Should show: cbc_auth.py, cbc_stremio_addon.py, etc.
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the addon**:
   ```bash
   python cbc_stremio_addon.py
   ```

4. **Configure credentials**:
   - Open http://localhost:7000/configure
   - Enter your CBC Gem email and password
   - Copy the generated install URL

5. **Install in Stremio**:
   - Open Stremio
   - Go to Addons
   - Paste the install URL in "Add addon" field

### Production Deployment

#### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:7000 cbc_stremio_addon:app
```

#### Using Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 7000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:7000", "cbc_stremio_addon:app"]
```

Build and run:
```bash
docker build -t cbc-stremio .
docker run -p 7000:7000 cbc-stremio
```

## How It Works

### Authentication Flow

1. **ROPC Settings**: Fetches OAuth configuration from CBC
2. **Password Login**: Exchanges username/password for refresh + access tokens
3. **Claims Token**: Uses access token to get claims token with user permissions
4. **Content Access**: Uses claims token in `x-claims-token` header for stream requests

### Content Resolution

1. **URL Parsing**: Converts CBC Gem URLs to internal show IDs
2. **Metadata Fetching**: Gets show information from CBC catalog API
3. **Stream Resolution**: Resolves media ID to HLS stream URL
4. **Authentication**: Adds required authentication headers

### Key Components

#### CBCAuthenticator Class
- Handles complete OAuth 2.0 flow
- Token refresh and expiration management
- JWT decoding and validation
- API request authentication

#### CBCGemExtractor Class
- Content metadata extraction
- Show/episode information parsing
- Stream URL resolution
- Error handling for geo-restrictions

## API Endpoints

The addon implements the standard Stremio addon protocol:

- `GET /manifest.json` - Addon manifest
- `GET /configure` - Configuration interface
- `GET /{config}/catalog/{type}/{id}.json` - Content catalog
- `GET /{config}/meta/{type}/{id}.json` - Content metadata
- `GET /{config}/stream/{type}/{id}.json` - Stream URLs

## Configuration

Users configure the addon through a web interface that generates install URLs with embedded credentials:

```
https://your-addon.com/email=user@example.com&password=secret/manifest.json
```

## Error Handling

The addon handles various CBC API errors:

- **Error Code 1**: Geo-restriction (Canada only)
- **Error Code 35**: Authentication required
- **HTTP 400**: Invalid credentials
- **JWT Expiry**: Automatic token refresh

## Security Considerations

1. **Credential Storage**: Uses URL-embedded config (secure for personal use)
2. **Token Security**: Implements proper JWT validation
3. **API Rate Limiting**: Includes session management and caching
4. **HTTPS Required**: Should be deployed with SSL certificate

## Limitations

1. **Geo-restriction**: Content only accessible from Canada
2. **Personal Use**: Addon is designed for individual account use
3. **CBC API Changes**: May break if CBC modifies their authentication system
4. **Content Availability**: Some content may require CBC Gem Premium

## Troubleshooting

### Common Issues

1. **Authentication Failures**:
   - Verify credentials are correct
   - Check if account is locked due to multiple failed attempts
   - Ensure Canadian IP address

2. **Stream Not Loading**:
   - Check if content requires premium subscription
   - Verify authentication tokens are valid
   - Check logs for specific error messages

3. **Empty Catalog**:
   - Catalog implementation is basic in this version
   - Direct URL input works better for specific content

### Debug Mode

Enable debug logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Token Inspection

Check stored tokens:
```python
auth = CBCAuthenticator()
print(f"Access token valid: {not auth._is_jwt_expired(auth.access_token)}")
print(f"Claims token valid: {not auth._is_jwt_expired(auth.claims_token)}")
```

## Development

### Adding Features

1. **Enhanced Catalog**: Implement popular shows/trending content
2. **Search**: Add search functionality using CBC API
3. **Subtitles**: Extract subtitle tracks from stream data
4. **Categories**: Add genre-based browsing

### Testing

Test with various CBC Gem URLs:
```bash
python cbc_url_parser.py
```

## Legal Notice

This addon is for personal use only. Users must have valid CBC Gem accounts and comply with CBC's terms of service. The addon does not store, redistribute, or modify any CBC content - it only provides authenticated access to streams that users are already entitled to access.

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Verify your CBC Gem account works in browser
3. Check addon logs for specific error messages
4. Ensure you're using a Canadian IP address

## Credits

This implementation is based on the excellent work done by the yt-dlp project team, specifically their CBC extractor implementation. The authentication flow and API endpoints were analyzed and replicated from their codebase.