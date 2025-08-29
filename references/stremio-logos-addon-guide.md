<?xml version="1.0" encoding="UTF-8"?>
<document type="markdown">
<![CDATA[
# Embedding Logos in a Stremio Addon

This guide provides a step-by-step breakdown for serving and displaying logos from `app/static/logos` in the menu posters of a Stremio addon written in Python.

## Table of Contents
1. Project Structure
2. Serving Static Files
3. Preparing Logos
4. Updating the Addon Manifest
5. Referencing Logos in Posters
6. Code Examples
7. Testing and Deployment

## 1. Project Structure
Organize your addon directory as follows:

```
my_stremio_addon/
├── app/
│   ├── static/
│   │   └── logos/
│   │       ├── channel1.png
│   │       └── channel2.png
│   ├── __init__.py
│   ├── server.py
│   └── manifest.json
└── requirements.txt
```

## 2. Serving Static Files
1. Use a web framework (e.g., Flask or FastAPI) to serve static assets from `app/static`.
2. Configure the static folder at application startup.

```python
from flask import Flask, send_from_directory
import os

app = Flask(__name__, static_folder='static')

@app.route('/static/logos/<path:filename>')
def serve_logo(filename):
    return send_from_directory(os.path.join(app.root_path, 'static/logos'), filename)
```

## 3. Preparing Logos
- Place each logo PNG in `app/static/logos`.
- Filenames should match the channel or menu item ID for consistency.
- Recommended size: 256×256 pixels.

## 4. Updating the Addon Manifest
In `manifest.json`, ensure the `logo` field in each resource entry points to the served URL:

```json
{
  "id": "channel1",
  "type": "tv",
  "name": "Channel 1",
  "logo": "http://<YOUR_DOMAIN>/static/logos/channel1.png",
  "poster": "http://<YOUR_DOMAIN>/static/logos/channel1.png"
}
```

## 5. Referencing Logos in Posters
- Stremio uses the `poster` URL to display menu images.
- Use the same logo URL or generate a composite poster via an image service if needed.

## 6. Code Examples
### server.py
```python
from flask import Flask, send_from_directory, jsonify
import os

app = Flask(__name__, static_folder='static')

# Serve logos
@app.route('/static/logos/<path:filename>')
def serve_logo(filename):
    return send_from_directory(os.path.join(app.root_path, 'static/logos'), filename)

# Manifest endpoint
def get_manifest():
    domain = os.getenv('ADDON_DOMAIN', 'localhost:5000')
    channels = []
    for fname in os.listdir(os.path.join(app.root_path, 'static/logos')):
        cid, _ = os.path.splitext(fname)
        url = f"http://{domain}/static/logos/{fname}"
        channels.append({
            'id': cid,
            'type': 'tv',
            'name': cid.title(),
            'logo': url,
            'poster': url
        })
    return {'resources': channels}

@app.route('/manifest.json')
def manifest():
    return jsonify(get_manifest())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## 7. Testing and Deployment
1. Start the server: `python server.py`.
2. Verify `http://localhost:5000/static/logos/channel1.png` returns the logo.
3. Load the addon in Stremio via `manifest.json` URL.
4. Confirm menu posters display the logos.

**End of guide.**
]]>
</document>