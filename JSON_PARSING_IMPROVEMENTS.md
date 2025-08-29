# JSON Parsing Improvements for Hugging Face Spaces Deployment

## Problem Summary
The application was experiencing JSON parsing errors when deployed on Hugging Face Spaces:
```
Error getting France.tv channels: Expecting property name enclosed in double quotes: line 24 column 5 (char 455)
Error getting TF1 channels: Expecting property name enclosed in double quotes: line 24 column 5 (char 455)
Error getting France TV replay shows: Expecting property name enclosed in double quotes: line 24 column 5 (char 455)
```

## Root Cause
The French TV providers (France TV, MyTF1, 6play) were using direct `.json()` calls from the requests library, which fail when the API returns malformed JSON responses. This commonly happens in cloud environments where:
- APIs return single quotes instead of double quotes
- Keys are unquoted
- HTML error pages are returned instead of JSON
- JSONP responses are wrapped in function calls

## Solution Implemented

### 1. Enhanced HTTP Utils (`app/utils/http_utils.py`)
- **Robust JSON Parsing**: Added `safe_json_parse()` method with comprehensive error handling
- **Lenient Parsing Strategies**: Multiple fallback strategies for malformed JSON:
  - Quote fixing (single quotes → double quotes)
  - Unquoted key fixing
  - JSON extraction from larger responses
  - JSONP wrapper removal
- **Detailed Error Logging**: Comprehensive console output for debugging including:
  - Error location (line, column)
  - Response content preview
  - Common issue identification (HTML, Cloudflare, rate limiting, etc.)
  - Full response headers

### 2. Provider Updates
Updated all French TV providers to use the robust HTTP client:

#### France TV Provider (`app/providers/fr/francetv.py`)
- Replaced all `.json()` calls with `http_client.safe_json_parse()`
- Added proper error handling and fallbacks
- Enhanced context information for debugging

#### MyTF1 Provider (`app/providers/fr/mytf1.py`)
- Replaced all `.json()` calls with `http_client.safe_json_parse()`
- Added proper error handling and fallbacks
- Enhanced context information for debugging

#### 6play Provider (`app/providers/fr/sixplay.py`)
- Replaced all `.json()` calls with `http_client.safe_json_parse()`
- Added proper error handling and fallbacks
- Enhanced context information for debugging

### 3. Error Handling Features
- **Graceful Degradation**: When JSON parsing fails, providers return empty lists/None instead of crashing
- **Context-Aware Logging**: Each API call includes descriptive context for easier debugging
- **Multiple Recovery Strategies**: Automatic attempts to fix common JSON issues
- **Console Output**: Immediate visibility of parsing issues for debugging

## Benefits

### For Development
- **Better Debugging**: Detailed error messages show exactly what's wrong
- **Fault Tolerance**: Application continues running even with malformed API responses
- **Context Information**: Clear identification of which API call is failing

### For Production (Hugging Face Spaces)
- **Improved Reliability**: Handles malformed JSON responses gracefully
- **Better User Experience**: Services continue working even with API issues
- **Easier Troubleshooting**: Detailed logs help identify and fix issues quickly

## Testing
The enhanced JSON parsing successfully handles:
- ✅ Single quotes instead of double quotes
- ✅ Unquoted property names
- ✅ HTML error pages
- ✅ JSONP responses
- ✅ Malformed JSON with syntax errors

## Usage
All providers now automatically use the enhanced parsing. No code changes are needed in the router files - the error handling is transparent to the calling code.

## Future Improvements
- Add more sophisticated JSON repair strategies
- Implement response caching for failed requests
- Add metrics for parsing success/failure rates
- Consider implementing retry logic for transient API issues
