# JSON Proxy Setup for French TV Providers

## 🎯 Overview

This implementation adds a JSON proxy layer to all French TV provider requests, helping bypass deployment issues that commonly occur when accessing these services from server environments.

## 🚀 Quick Setup

### 1. Create credentials.json

Create a `credentials.json` file in your project root with the following structure:

```json
{
  "json_proxy": {
    "url": "https://f87h6xkw96.execute-api.ca-central-1.amazonaws.com/api/router?url=",
    "timeout": 15,
    "enabled": true
  },
  "francetv": {
    "login": "your_francetv_email@example.com",
    "password": "your_francetv_password"
  },
  "mytf1": {
    "login": "your_mytf1_email@example.com",
    "password": "your_mytf1_password"
  },
  "6play": {
    "login": "your_6play_email@example.com",
    "password": "your_6play_password"
  }
}
```

### 2. Test the Configuration

Run the test script to verify everything is working:

```bash
python test_proxy.py
```

## 🔧 Configuration Options

### JSON Proxy Settings

| Setting | Description | Default | Environment Variable |
|---------|-------------|---------|---------------------|
| `enabled` | Enable/disable the proxy | `true` | `JSON_PROXY_ENABLED` |
| `url` | Proxy service URL | Your AWS Lambda URL | `JSON_PROXY_URL` |
| `timeout` | Request timeout in seconds | `15` | `JSON_PROXY_TIMEOUT` |

### Environment Variable Override

You can override settings using environment variables:

```bash
# Disable proxy
export JSON_PROXY_ENABLED=false

# Use different proxy URL
export JSON_PROXY_URL=https://your-proxy.com/api?url=

# Set custom timeout
export JSON_PROXY_TIMEOUT=30
```

## 🏗️ Architecture

### Components

1. **ProxyConfig** (`app/utils/proxy_config.py`)
   - Manages proxy configuration
   - Validates settings
   - Supports environment variable overrides

2. **JSONProxyClient** (`app/utils/json_proxy.py`)
   - Routes requests through proxy
   - Provides fallback to direct requests
   - Enhanced error handling and JSON parsing

3. **Provider Updates**
   - All French TV providers now use the proxy client
   - Automatic fallback if proxy fails
   - Consistent error handling across providers

### Request Flow

```
Local Request → ProxyConfig Check → JSONProxyClient → Proxy Service → Target API
                    ↓
              Fallback to Direct Request
```

## 📊 How It Works

### 1. Request Interception

All API requests from French TV providers are intercepted by the `JSONProxyClient`.

### 2. Proxy Routing

If the proxy is enabled, requests are routed through your AWS Lambda proxy service:

```
Original: https://api-front.yatta.francetv.fr/...
Proxied: https://f87h6xkw96.execute-api.ca-central-1.amazonaws.com/api/router?url=https%3A//api-front.yatta.francetv.fr/...
```

### 3. Response Processing

The proxy service fetches the response and returns it to your application, bypassing:
- Geographic restrictions
- IP-based rate limiting
- Server IP detection
- User-Agent filtering

### 4. Fallback Mechanism

If the proxy fails or is disabled, requests automatically fall back to direct connections.

## 🧪 Testing

### Test Scripts

1. **test_proxy.py** - Tests proxy configuration and basic functionality
2. **test_api_endpoints.py** - Tests all French TV API endpoints
3. **api_endpoints_list.md** - Reference guide for manual testing

### Manual Testing

Test individual endpoints using curl:

```bash
# Test France TV through proxy
curl -X GET "https://f87h6xkw96.execute-api.ca-central-1.amazonaws.com/api/router?url=http%3A//api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_envoye-special%3Fplatform%3Dapps"

# Test MyTF1 through proxy
curl -X GET "https://f87h6xkw96.execute-api.ca-central-1.amazonaws.com/api/router?url=https%3A//compte.tf1.fr/accounts.webSdkBootstrap%3FapiKey%3D3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk%26pageURL%3Dhttps%253A%252F%252Fwww.tf1.fr%252F%26sd%3Djs_latest%26sdkBuild%3D13987%26format%3Djson"
```

## 🚨 Troubleshooting

### Common Issues

1. **Proxy Not Working**
   - Check `credentials.json` exists and is valid JSON
   - Verify proxy URL is accessible
   - Check environment variables if using them

2. **Authentication Failures**
   - Verify provider credentials are correct
   - Check if proxy service supports POST requests with data
   - Ensure proper headers are being sent

3. **Timeout Issues**
   - Increase timeout in configuration
   - Check proxy service performance
   - Consider using direct requests for time-sensitive operations

### Debug Mode

Enable debug logging to see detailed request/response information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Disable Proxy

To disable the proxy and use direct connections:

```json
{
  "json_proxy": {
    "enabled": false
  }
}
```

Or use environment variable:

```bash
export JSON_PROXY_ENABLED=false
```

## 🔒 Security Considerations

1. **Credentials Protection**
   - Keep `credentials.json` secure and never commit to version control
   - Use environment variables in production
   - Consider using a secrets management service

2. **Proxy Service Security**
   - Ensure your proxy service is secure and authenticated
   - Monitor proxy service usage and costs
   - Implement rate limiting if needed

3. **Request Logging**
   - Be aware that proxy service may log your requests
   - Consider privacy implications for user data

## 📈 Performance Impact

### Benefits

- ✅ Bypasses deployment restrictions
- ✅ Consistent API access across environments
- ✅ Better error handling and retry logic
- ✅ Automatic fallback mechanisms

### Considerations

- ⚠️ Additional latency from proxy routing
- ⚠️ Dependency on external proxy service
- ⚠️ Potential rate limiting from proxy service
- ⚠️ Additional network hops

### Optimization Tips

1. **Caching**: Implement response caching to reduce proxy calls
2. **Batch Requests**: Group multiple requests when possible
3. **Connection Pooling**: Reuse proxy connections
4. **Timeout Tuning**: Adjust timeouts based on your environment

## 🔄 Migration Guide

### From Direct Requests

If you were previously using direct requests, the migration is automatic:

```python
# Old way (still works)
from app.utils.http_utils import http_client
response = http_client.get_json(url)

# New way (with proxy)
from app.utils.json_proxy import proxy_client
response = proxy_client.get_json(url)
```

### From Custom HTTP Clients

Replace your custom HTTP client with the proxy client:

```python
# Before
import requests
response = requests.get(url, headers=headers)

# After
from app.utils.json_proxy import proxy_client
response = proxy_client.get(url, headers=headers)
```

## 📚 API Reference

### JSONProxyClient Methods

- `get(url, **kwargs)` - GET request with proxy fallback
- `post(url, **kwargs)` - POST request with proxy fallback
- `get_json(url, **kwargs)` - GET request returning parsed JSON
- `post_json(url, **kwargs)` - POST request returning parsed JSON
- `safe_json_parse(response, context)` - Safe JSON parsing with error handling

### ProxyConfig Methods

- `is_enabled()` - Check if proxy is enabled
- `get_proxy_url()` - Get configured proxy URL
- `get_timeout()` - Get configured timeout
- `validate_config()` - Validate configuration
- `print_config()` - Print current configuration

## 🎉 Success Indicators

Your JSON proxy is working correctly when:

1. ✅ `test_proxy.py` runs successfully
2. ✅ French TV providers can fetch data
3. ✅ No more "Expecting property name enclosed in double quotes" errors
4. ✅ Consistent API responses across environments
5. ✅ Proper fallback when proxy is disabled

## 🆘 Support

If you encounter issues:

1. Check the configuration using `proxy_config.print_config()`
2. Run the test scripts to isolate problems
3. Check proxy service logs and availability
4. Verify network connectivity and firewall settings
5. Review the troubleshooting section above

---

**Note**: This implementation provides a robust solution for deployment issues while maintaining backward compatibility and offering flexible configuration options.
