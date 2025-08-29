# 🐛 Comprehensive Debugging Guide

## 🎯 **What Was Added**

I've implemented a **comprehensive error logging system** that will capture and log **everything** that goes wrong in your server, including:

- ✅ **All HTTP requests and responses**
- ✅ **Full error tracebacks**
- ✅ **Request headers and parameters**
- ✅ **Response times and status codes**
- ✅ **Provider-specific errors**
- ✅ **JSON parsing failures**
- ✅ **API call details**

## 📁 **Files Enhanced**

### 1. **Main App** (`app/main.py`)
- 🔍 **Request/Response Middleware** - Logs every request and response
- 🚨 **Global Exception Handler** - Catches all unhandled errors
- 📝 **Comprehensive Logging** - Both file and console output
- 🐛 **Debug Endpoints** - View logs and server status

### 2. **Catalog Router** (`app/routers/catalog.py`)
- 📺 **Provider-specific logging** - Track each French TV provider
- 🔄 **Fallback logging** - When APIs fail, log what happened
- 📊 **Success metrics** - Count of channels/shows returned

### 3. **Stream Router** (`app/routers/stream.py`)
- 🎬 **Stream request logging** - Track every stream request
- 🎯 **Provider identification** - Know which provider is being used
- ⚠️ **Warning logging** - When streams aren't available

## 🚀 **How to Use the Debug System**

### **1. Start Your Server**
```bash
python run_server.py
```

### **2. Check the Log File**
All errors are automatically saved to `server_debug.log` in your project root.

### **3. View Logs in Real-Time**
```bash
# Watch the log file in real-time
tail -f server_debug.log

# Or view the last 50 lines
tail -50 server_debug.log
```

### **4. Use Debug Endpoints**
Your server now has debug endpoints:

- **`/debug/status`** - Check server status and configuration
- **`/debug/logs`** - View recent log entries (last 100 lines)

## 🔍 **What You'll See in the Logs**

### **Request Logging**
```
🔍 REQUEST: GET http://localhost:7860/catalog/channel/fr-live.json
   Headers: {'host': 'localhost:7860', 'user-agent': 'Stremio/4.4.0'}
   Query Params: {}
```

### **Provider Success**
```
📺 Processing live TV channels request
🇫🇷 Getting France.tv channels...
✅ France.tv returned 5 channels
📺 Getting TF1 channels...
✅ TF1 returned 3 channels
🎬 Getting 6play channels...
✅ 6play returned 4 channels
📊 Total channels returned: 12
✅ RESPONSE: 200 in 0.234s
```

### **Provider Errors**
```
❌ Error getting France.tv channels: Expecting property name enclosed in double quotes: line 24 column 5 (char 455)
   Full traceback:
   Traceback (most recent call last):
     File "app/routers/catalog.py", line 45, in get_catalog
       francetv_channels = francetv.get_live_channels()
   ...
```

### **Stream Request Logging**
```
🔍 STREAM REQUEST: type=channel, id=cutam:fr:francetv:france-2
📺 Processing live stream request for channel: cutam:fr:francetv:france-2
🎯 Using France TV provider for channel: cutam:fr:francetv:france-2
✅ France TV returned stream info: hls
```

## 🐛 **Debugging Common Issues**

### **1. JSON Parsing Errors**
When you see:
```
❌ Error getting France.tv channels: Expecting property name enclosed in double quotes: line 24 column 5 (char 455)
```

**What it means**: The French TV API returned malformed JSON
**What to do**: Check the provider's `_safe_api_call` method logs for the actual response

### **2. Provider Authentication Failures**
When you see:
```
❌ Error getting TF1+ replay shows: Authentication failed
```

**What it means**: MyTF1 credentials are invalid or expired
**What to do**: Check your `credentials.json` file

### **3. Stream Not Available**
When you see:
```
⚠️ France TV returned no stream info for channel: cutam:fr:francetv:france-2
```

**What it means**: The provider couldn't get a valid stream URL
**What to do**: Check the provider's stream extraction logs

## 📊 **Monitoring Your Server**

### **Check Server Status**
```bash
curl http://localhost:7860/debug/status
```

Response:
```json
{
  "status": "running",
  "timestamp": "2024-01-15T10:30:00",
  "environment": {
    "ADDON_BASE_URL": "http://localhost:8000",
    "HOST": "127.0.0.1",
    "PORT": "7860",
    "LOG_LEVEL": "INFO"
  },
  "log_file": "server_debug.log"
}
```

### **View Recent Logs**
```bash
curl http://localhost:7860/debug/logs
```

## 🔧 **Advanced Debugging**

### **1. Increase Log Level**
To see even more detail, modify `app/main.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server_debug.log'),
        logging.StreamHandler()
    ]
)
```

### **2. Filter Logs by Provider**
```bash
# Only see France TV related logs
grep "France" server_debug.log

# Only see errors
grep "❌" server_debug.log

# Only see warnings
grep "⚠️" server_debug.log
```

### **3. Monitor Specific Endpoints**
```bash
# Watch catalog requests
grep "CATALOG REQUEST" server_debug.log

# Watch stream requests
grep "STREAM REQUEST" server_debug.log
```

## 🎯 **What to Look For**

### **Good Signs** ✅
- `✅ RESPONSE: 200 in X.XXXs` - Fast, successful responses
- `✅ Provider returned X channels/shows` - APIs working
- `✅ Stream info returned` - Streams available

### **Warning Signs** ⚠️
- `⚠️ Provider returned no stream info` - API working but no content
- `⚠️ Using fallback shows` - API failed, using static data
- `⚠️ Unknown request type` - Unexpected requests

### **Problem Signs** ❌
- `❌ Error getting provider data` - API calls failing
- `❌ JSON parse error` - Malformed responses
- `❌ Authentication failed` - Credential issues

## 🚀 **Deployment Debugging**

When deployed online, you'll see:

1. **IP addresses** in request logs
2. **User-Agent strings** from Stremio clients
3. **Response times** to identify slow endpoints
4. **Error patterns** specific to your deployment environment

## 📝 **Example Debug Session**

```bash
# 1. Start server
python run_server.py

# 2. In another terminal, watch logs
tail -f server_debug.log

# 3. Make a request from Stremio
# 4. Watch the logs show:
#    - Request details
#    - Provider calls
#    - Success/failure
#    - Response time

# 5. If there's an error, you'll see:
#    - Full traceback
#    - Request context
#    - Error details
```

## 🎉 **Benefits**

With this debug system, you can now:

- 🔍 **See exactly what's happening** in real-time
- 🐛 **Identify the root cause** of any issue
- 📊 **Monitor performance** and response times
- 🚨 **Catch errors early** before they affect users
- 📝 **Have a complete audit trail** of all requests

---

**Your server now has enterprise-grade debugging capabilities!** 🚀

When you encounter any issues, the logs will tell you exactly what went wrong, where it happened, and why. No more guessing about what's failing!

