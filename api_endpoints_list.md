# French TV Providers - API Endpoints for Testing

## 🎯 Key Endpoints to Test with Online Proxies

### France TV (francetv)
```
GET http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_envoye-special?platform=apps
GET http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_cash-investigation?platform=apps
GET http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_complement-d-enquete?platform=apps
```

**Headers:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
```

### MyTF1 (mytf1)
```
GET https://compte.tf1.fr/accounts.webSdkBootstrap?apiKey=3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk&pageURL=https%3A%2F%2Fwww.tf1.fr%2F&sd=js_latest&sdkBuild=13987&format=json

POST https://www.tf1.fr/graphql/web
```

**Headers:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36
Referer: https://www.tf1.fr/
Content-Type: application/json
```

### 6play (sixplay)
```
GET https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/videos/12345?csa=6&with=clips,freemiumpacks

GET https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live?channel=M6&with=service_display_images,nextdiffusion,extra_data

POST https://nhacvivxxk-dsn.algolia.net/1/indexes/*/queries
```

**Headers:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36
Content-Type: application/x-www-form-urlencoded
x-algolia-api-key: 6ef59fc6d78ac129339ab9c35edd41fa
x-algolia-application-id: NHACVIVXXK
```

## 🧪 Testing Tools

### Online Proxy Services
- **httpbin.org** - Test basic HTTP requests
- **webhook.site** - Inspect full requests and responses
- **requestbin.com** - Capture and analyze requests
- **postman.com** - API testing platform
- **insomnia.rest** - API client for testing

### Geographic Testing
- **ipinfo.io** - Check your IP location
- **whatismyipaddress.com** - IP geolocation
- **tunnelbear.com** - VPN for location testing

## 🔍 What to Look For

### Expected Behavior (Local)
- JSON responses with proper formatting
- HTTP 200 status codes
- Content-Type: application/json

### Problematic Behavior (Deployed)
- HTML error pages instead of JSON
- HTTP 403/429/500 status codes
- Content-Type: text/html
- JSON with unquoted property names
- Rate limiting responses
- Geographic blocking

### Common Error Patterns
```
Expecting property name enclosed in double quotes: line 24 column 5 (char 455)
```
This suggests:
1. HTML error pages being returned
2. Malformed JSON from the services
3. Different response format for server IPs

## 🚀 Quick Test Commands

### Test France TV
```bash
curl -X GET "http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_envoye-special?platform=apps" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
```

### Test MyTF1
```bash
curl -X GET "https://compte.tf1.fr/accounts.webSdkBootstrap?apiKey=3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk&pageURL=https%3A%2F%2Fwww.tf1.fr%2F&sd=js_latest&sdkBuild=13987&format=json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36" \
  -H "Referer: https://www.tf1.fr/"
```

### Test 6play
```bash
curl -X GET "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/videos/12345?csa=6&with=clips,freemiumpacks" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
```

## 📊 Response Analysis

### Check Response Type
```bash
# Look for HTML content
grep -i "<html\|<title\|error\|forbidden\|unauthorized" response.txt

# Look for JSON structure
grep -o '"[^"]*":' response.txt | head -10

# Check for malformed JSON
python -m json.tool response.txt 2>&1 | head -20
```

### Common Issues Found
1. **Cloudflare Protection** - Returns HTML challenge pages
2. **Rate Limiting** - JSON with error messages
3. **Geographic Blocking** - Different responses for server IPs
4. **User-Agent Filtering** - Blocks certain User-Agent strings
5. **IP Reputation** - Server IPs treated differently than residential IPs

## 🛠️ Potential Solutions

### 1. Rotate User-Agents
Use different browser User-Agent strings for each request

### 2. Add Request Delays
Implement delays between requests to avoid rate limiting

### 3. Use Residential Proxies
Route requests through residential IP addresses

### 4. Implement Retry Logic
Retry failed requests with exponential backoff

### 5. Cache Responses
Cache successful responses to reduce API calls

### 6. Fallback to Static Data
Use static metadata when APIs fail

