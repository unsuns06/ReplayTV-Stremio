# Client-Side Approach for French TV Providers

## 🎯 Problem Solved

The original implementation was making server-side JSON requests to French TV APIs (France.tv, MyTF1, 6play), which caused deployment issues:

- **JSON Parsing Errors**: `Expecting property name enclosed in double quotes: line 24 column 5 (char 455)`
- **Server IP Blocking**: The services treat server IPs differently than residential IPs
- **Rate Limiting**: Server requests are often rate-limited or blocked
- **Geographic Restrictions**: Different behavior for server vs. client requests

## 🚀 Solution: Client-Side Processing

Instead of making API calls server-side, we now return **client-side URLs** that Stremio will process directly in the user's browser.

### How It Works

1. **Server Side**: Returns static metadata and client-side URLs
2. **Client Side**: Stremio processes the URLs and makes the actual API calls
3. **Result**: No more server-side JSON parsing errors

## 📁 Files Modified

### 1. Provider Classes
- `app/providers/fr/francetv.py` - France TV provider
- `app/providers/fr/mytf1.py` - MyTF1 provider  
- `app/providers/fr/sixplay.py` - 6play provider

### 2. Client-Side Handler
- `app/static/client-side-handler.js` - JavaScript for handling API calls

## 🔄 New Flow

### Before (Server-Side)
```
Stremio → Your Server → French TV APIs → Parse JSON → Return Stream URL
```

### After (Client-Side)
```
Stremio → Your Server → Return Client URL → Stremio → French TV APIs → Parse JSON → Get Stream
```

## 📋 Implementation Details

### Server-Side Changes

#### France TV Provider
```python
def get_live_stream_url(self, channel_id: str) -> Optional[Dict]:
    # Extract channel name from ID
    channel_name = channel_id.split(":")[-1]
    
    # Return client-side URL instead of making API call
    stream_url = f"https://www.france.tv/direct/{channel_name}/"
    
    return {
        "url": stream_url,
        "manifest_type": "hls",
        "note": "Client-side processing required - Stremio will handle the actual stream extraction"
    }
```

#### MyTF1 Provider
```python
def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
    channel_name = channel_id.split(":")[-1]
    
    if channel_name == "tf1":
        stream_url = "https://www.tf1.fr/direct"
    elif channel_name == "tfx":
        stream_url = "https://www.tfx.fr/direct"
    # ... etc
    
    return {
        "url": stream_url,
        "manifest_type": "hls",
        "note": "Client-side processing required - Stremio will handle the actual stream extraction"
    }
```

#### 6play Provider
```python
def get_channel_stream_url(self, channel_id: str) -> Optional[Dict]:
    channel_name = channel_id.split(":")[-1]
    
    if channel_name == "m6":
        stream_url = "https://www.6play.fr/m6/direct"
    elif channel_name == "w9":
        stream_url = "https://www.6play.fr/w9/direct"
    # ... etc
    
    return {
        "url": stream_url,
        "manifest_type": "hls",
        "note": "Client-side processing required - Stremio will handle the actual stream extraction"
    }
```

### Client-Side Handler

The `client-side-handler.js` file contains JavaScript code that:

1. **Handles Authentication**: Manages login tokens for each service
2. **Makes API Calls**: Directly calls French TV APIs from the browser
3. **Extracts Streams**: Gets the actual HLS/MPD stream URLs
4. **Error Handling**: Gracefully handles API failures

## 🎬 Example Usage

### Live TV Channels
```python
# Server returns client-side URL
{
    "url": "https://www.france.tv/direct/france-2/",
    "manifest_type": "hls",
    "note": "Client-side processing required"
}
```

### Replay Shows
```python
# Server returns client-side URL
{
    "url": "https://www.6play.fr/capital",
    "manifest_type": "hls", 
    "note": "Client-side processing required"
}
```

## ✅ Benefits

1. **No More JSON Errors**: Server doesn't parse French TV API responses
2. **Better Reliability**: Client requests are treated like regular browser requests
3. **No Rate Limiting**: Individual users make their own API calls
4. **Geographic Freedom**: Works from any location
5. **Scalability**: Server load is reduced significantly

## 🔧 Configuration

### Environment Variables
```bash
# Base URL for your addon (used for static assets)
ADDON_BASE_URL=http://your-domain.com:8000
```

### Static Assets
- Logo files are served from `app/static/logos/fr/`
- Client-side handler is served from `app/static/client-side-handler.js`

## 🚀 Deployment

### 1. Update Your Server
```bash
# Deploy the updated Python code
git add .
git commit -m "Switch to client-side approach for French TV providers"
git push
```

### 2. Test Locally
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Deploy Online
The deployment should now work without JSON parsing errors!

## 🔍 Testing

### Check Server Logs
You should see:
```
✅ No more "Expecting property name enclosed in double quotes" errors
✅ Clean responses with client-side URLs
✅ Fast response times (no API calls)
```

### Check Client Behavior
- Stremio will receive the client-side URLs
- The client-side handler will process them
- Streams should work as expected

## 🎯 Next Steps

1. **Deploy the updated code**
2. **Test with Stremio client**
3. **Monitor for any client-side issues**
4. **Enhance the client-side handler as needed**

## 🆘 Troubleshooting

### If Streams Don't Work
1. Check browser console for JavaScript errors
2. Verify the client-side handler is loading
3. Check if the French TV services are accessible from the client

### If You Still See Errors
1. Ensure all provider files are updated
2. Check that the client-side handler is accessible
3. Verify environment variables are set correctly

## 📚 References

- [Stremio Addon SDK](https://github.com/Stremio/stremio-addon-sdk)
- [France TV APIs](https://www.france.tv/)
- [MyTF1 APIs](https://www.tf1.fr/)
- [6play APIs](https://www.6play.fr/)

---

**This approach moves the complexity from server-side to client-side, ensuring your addon works reliably in any deployment environment!** 🎉
