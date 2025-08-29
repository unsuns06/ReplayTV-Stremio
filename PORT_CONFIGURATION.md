# Port Configuration Guide

This document explains how to configure the server port for the ReplayTV Stremio addon.

## Configuration System

The addon now uses a centralized configuration system based on environment variables. This makes it easy to change the port without modifying multiple files.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `7860` | Server port number |
| `HOST` | `0.0.0.0` (Docker) / `127.0.0.1` (local) | Server host |
| `ADDON_BASE_URL` | `http://localhost:7860` | Base URL used for static assets and API responses |

### Configuration Files

1. **`.env.example`** - Template with default values
2. **`.env`** - Local environment configuration (copy from .env.example)

## How to Change the Port

### Method 1: Environment Variables (Recommended)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and change the PORT value:
   ```
   PORT=8080
   ADDON_BASE_URL=http://localhost:8080
   ```

3. Start the server:
   ```bash
   python run_server.py
   ```

### Method 2: Environment Variable Override

Set the environment variable directly:

**Windows:**
```cmd
set PORT=8080 && set ADDON_BASE_URL=http://localhost:8080 && python run_server.py
```

**Linux/Mac:**
```bash
PORT=8080 ADDON_BASE_URL=http://localhost:8080 python run_server.py
```

### Method 3: Docker Compose

Edit `docker-compose.yml` environment section:
```yaml
environment:
  - PORT=8080
  - ADDON_BASE_URL=http://localhost:8080
```

## Files Updated for Port Agnostic Configuration

The following files now use environment variables instead of hardcoded ports:

- `run_server.py` - Main server startup script
- `Dockerfile` - Docker container configuration
- `docker-compose.yml` - Docker compose service definition
- `package.json` - NPM scripts now use run_server.py
- `app/routers/catalog.py` - Uses ADDON_BASE_URL environment variable
- `app/routers/meta.py` - Uses ADDON_BASE_URL environment variable
- `app/providers/fr/francetv.py` - Uses ADDON_BASE_URL environment variable
- `app/providers/fr/mytf1.py` - Uses ADDON_BASE_URL environment variable
- `app/providers/fr/sixplay.py` - Uses ADDON_BASE_URL environment variable

## Testing the Configuration

1. Start the server:
   ```bash
   python run_server.py
   ```

2. Test the manifest endpoint:
   ```bash
   curl http://localhost:7860/manifest.json
   ```

3. Test the root endpoint:
   ```bash
   curl http://localhost:7860/
   ```

## Stremio Installation

When installing the addon in Stremio, use the manifest URL with your configured port:

```
http://localhost:7860/manifest.json
```

Or if deployed remotely:
```
https://your-domain.com/manifest.json
```

## Troubleshooting

### Port Already in Use
If you get a "port already in use" error:

1. Check what's using the port:
   ```bash
   netstat -ano | findstr :7860
   ```

2. Choose a different port in your `.env` file:
   ```
   PORT=7861
   ADDON_BASE_URL=http://localhost:7861
   ```

### Addon Not Working in Stremio
Make sure the `ADDON_BASE_URL` matches the URL where your server is accessible from Stremio.

For local development:
```
ADDON_BASE_URL=http://localhost:7860
```

For remote deployment:
```
ADDON_BASE_URL=https://your-domain.com
```
