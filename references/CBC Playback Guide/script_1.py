# Now let's save the CBC extractor code to a file for analysis
with open('cbc_extractor.py', 'w', encoding='utf-8') as f:
    import requests
    url = "https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/cbc.py"
    response = requests.get(url)
    f.write(response.text)

print("CBC extractor saved to file for analysis")

# Let's also analyze the key authentication functions
print("\n" + "="*50)
print("KEY AUTHENTICATION FUNCTIONS ANALYSIS")
print("="*50)

print("""
Based on the CBC extractor code, here are the key authentication components:

1. CLIENT_ID: 'fc05b0ee-3865-4400-a3cc-3da82c330c23'

2. OAuth 2.0 Flow:
   - Uses ROPC (Resource Owner Password Credentials) flow
   - Endpoint: services.radio-canada.ca/ott/catalog/v1/gem/settings
   - Token endpoint: from ropc settings URL
   - Scopes: from ropc settings

3. Token Types:
   - Refresh Token: Long-lived token for getting new access tokens
   - Access Token: Short-lived token for API access
   - Claims Token: Contains user subscription/access claims

4. Key Methods:
   - _call_oauth_api(): Handles OAuth token requests
   - _perform_login(): Initial login with username/password
   - _fetch_access_token(): Gets/refreshes access token
   - _fetch_claims_token(): Gets claims token for content access

5. Authentication Flow:
   a. Get ROPC settings
   b. Login with username/password to get refresh/access tokens
   c. Use access token to get claims token
   d. Use claims token in x-claims-token header for content requests

6. Content Access:
   - Endpoint: services.radio-canada.ca/media/validation/v2/
   - Requires x-claims-token header for premium content
   - Parameters: appCode, connectionType, deviceType, multibitrate, output, tech, manifestType, idMedia
""")

# Let's extract the key authentication parts for the Stremio addon
key_parts = {
    'client_id': 'fc05b0ee-3865-4400-a3cc-3da82c330c23',
    'settings_url': 'https://services.radio-canada.ca/ott/catalog/v1/gem/settings',
    'show_api_url': 'https://services.radio-canada.ca/ott/catalog/v2/gem/show/',
    'validation_url': 'https://services.radio-canada.ca/media/validation/v2/',
    'claims_url': 'https://services.radio-canada.ca/ott/subscription/v2/gem/Subscriber/profile'
}

print("\nKey URLs and Constants:")
for k, v in key_parts.items():
    print(f"{k}: {v}")

print("\nAuthentication analysis complete!")