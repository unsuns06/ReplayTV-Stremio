# French Proxy Header Forwarding Fix

## Problem Identified
The French proxy strips critical headers required for MyTF1 authentication:
- **Authorization** header (authentication tokens)
- **X-Forwarded-For** and related IP headers
- **Referer**, **Origin**, and security headers
- **Custom headers** like X-Mediaflow-Test

## Root Cause
The AWS API Gateway (HTTP API) has restrictive default settings that filter out headers for security and CORS reasons.

## Solution Options

### Option 1: HTTP API Gateway Configuration (Recommended)

#### 1.1 Enable CORS Configuration
In your AWS HTTP API Gateway console:

1. **Navigate to your API** → **tvff3tyk1e**
2. **Go to "CORS"** in the left navigation
3. **Enable CORS** for your route
4. **Add allowed headers**:
   ```
   Authorization
   X-Forwarded-For
   X-Real-IP
   X-Client-IP
   CF-Connecting-IP
   True-Client-IP
   Referer
   Origin
   Sec-Fetch-*
   X-*
   ```

#### 1.2 Route Configuration
For your `/router` route:
1. **Integration Request** settings
2. **Enable "Override HTTP request headers"**
3. **Add mapping** for all headers you want to forward

### Option 2: Lambda Function Modification

#### 2.1 Current Lambda Structure
Your lambda function likely looks like this:
```javascript
exports.handler = async (event) => {
    const targetUrl = event.queryStringParameters?.url;

    const response = await fetch(targetUrl, {
        method: event.requestContext.http.method,
        headers: event.headers, // This is where headers get filtered
        body: event.body
    });

    return {
        statusCode: response.status,
        headers: response.headers,
        body: await response.text()
    };
};
```

#### 2.2 Fixed Lambda Function
```javascript
exports.handler = async (event) => {
    const targetUrl = event.queryStringParameters?.url;

    // Create headers object with ALL headers
    const headers = {};

    // Copy all headers from the request
    if (event.headers) {
        Object.keys(event.headers).forEach(key => {
            // Allow specific headers or use whitelist approach
            const allowedHeaders = [
                'authorization', 'x-forwarded-for', 'x-real-ip', 'x-client-ip',
                'cf-connecting-ip', 'true-client-ip', 'referer', 'origin',
                'user-agent', 'accept', 'accept-language', 'accept-encoding',
                'cache-control', 'pragma', 'sec-fetch-dest', 'sec-fetch-mode',
                'sec-fetch-site', 'dnt', 'upgrade-insecure-requests'
            ];

            // Allow all headers starting with X-
            if (allowedHeaders.includes(key.toLowerCase()) || key.toLowerCase().startsWith('x-')) {
                headers[key] = event.headers[key];
            }
        });
    }

    // Add custom headers for MediaFlow if needed
    if (event.headers && event.headers['x-mediaflow-proxy']) {
        headers['X-Mediaflow-Proxy'] = event.headers['x-mediaflow-proxy'];
    }

    const response = await fetch(targetUrl, {
        method: event.requestContext.http.method,
        headers: headers,
        body: event.body
    });

    return {
        statusCode: response.status,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Authorization,X-Forwarded-For,X-Real-IP,Referer,Origin,Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        body: await response.text()
    };
};
```

### Option 3: API Gateway Resource Policy

#### 3.1 Create Resource Policy
Add a resource policy to your API Gateway to allow specific headers:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": "*",
            "Action": "execute-api:Invoke",
            "Resource": "arn:aws:apigateway:eu-west-3::tvff3tyk1e/*",
            "Condition": {
                "StringLike": {
                    "aws:RequestHeader.X-Forwarded-For": "*"
                }
            }
        }
    ]
}
```

## Recommended Approach

### Step 1: Quick Fix (Lambda Only)
1. **Deploy the modified lambda function** above
2. **Test with httpbin.org** to verify header forwarding
3. **Update MyTF1 provider** to remove fallback logic if proxy works perfectly

### Step 2: Comprehensive Fix (API Gateway + Lambda)
1. **Configure CORS** in API Gateway console
2. **Enable header override** in integration request
3. **Deploy updated lambda** with header mapping
4. **Test thoroughly** with various endpoints

### Step 3: Verification
Run the test suite again:
```bash
python fr_proxy_header_test.py
```

Expected result: All headers should be forwarded correctly.

## Files to Update

### 1. Lambda Function (Deploy to AWS)
- Update your existing lambda with the enhanced header forwarding logic

### 2. MyTF1 Provider (Local)
- Once proxy headers work, you can remove the direct fallback
- Or keep hybrid approach for reliability

## Testing Strategy

1. **Deploy lambda fix**
2. **Run header test suite**:
   ```bash
   python fr_proxy_header_test.py
   ```
3. **Test MyTF1 streams**:
   ```bash
   python test_mytf1_fix.py
   ```
4. **Verify all headers forwarded**
5. **Monitor for any regression**

## Expected Outcome

After implementing the fix:
- ✅ All 30/30 headers forwarded
- ✅ Authentication headers preserved
- ✅ IP forwarding headers preserved
- ✅ MyTF1 authentication works through proxy
- ✅ No more 403 errors from proxy
- ✅ Geo-restriction bypass maintained

This should resolve the authentication issues completely while maintaining the proxy's geo-bypass functionality.
