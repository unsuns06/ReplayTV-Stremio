#!/usr/bin/env python3
"""
Test script to extract all API endpoints from French TV providers
Use this to test with online proxies to debug deployment issues
"""

import json
import requests
from typing import Dict, List

def test_francetv_endpoints():
    """Test France TV API endpoints"""
    print("=" * 60)
    print("FRANCE TV API ENDPOINTS")
    print("=" * 60)
    
    # Test endpoints
    endpoints = [
        {
            "name": "France TV Front API - Envoyé Spécial",
            "url": "http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_envoye-special",
            "params": {"platform": "apps"},
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        },
        {
            "name": "France TV Front API - Cash Investigation",
            "url": "http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_cash-investigation",
            "params": {"platform": "apps"},
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }
    ]
    
    for endpoint in endpoints:
        print(f"\n🔍 Testing: {endpoint['name']}")
        print(f"URL: {endpoint['url']}")
        print(f"Headers: {json.dumps(endpoint['headers'], indent=2)}")
        print(f"Params: {json.dumps(endpoint['params'], indent=2)}")
        
        try:
            response = requests.get(
                endpoint['url'], 
                params=endpoint['params'], 
                headers=endpoint['headers'], 
                timeout=10
            )
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"Response Preview: {response.text[:200]}...")
            
            # Try to parse JSON
            try:
                json_data = response.json()
                print("✅ JSON parsed successfully")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                print(f"Error at line {e.lineno}, column {e.colno}")
                print(f"Context: {response.text[max(0, e.pos-50):e.pos+50]}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

def test_mytf1_endpoints():
    """Test MyTF1 API endpoints"""
    print("\n" + "=" * 60)
    print("MYTF1 API ENDPOINTS")
    print("=" * 60)
    
    endpoints = [
        {
            "name": "MyTF1 Bootstrap",
            "url": "https://compte.tf1.fr/accounts.webSdkBootstrap",
            "params": {
                'apiKey': '3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk',
                'pageURL': 'https%3A%2F%2Fwww.tf1.fr%2F',
                'sd': 'js_latest',
                'sdkBuild': '13987',
                'format': 'json'
            },
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
                'referrer': 'https://www.tf1.fr/'
            }
        },
        {
            "name": "MyTF1 GraphQL API",
            "url": "https://www.tf1.fr/graphql/web",
            "params": {},
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
                'Content-Type': 'application/json'
            },
            "data": {
                "query": """
                query GetPrograms($first: Int!, $after: String) {
                    programs(first: $first, after: $after) {
                        edges {
                            node {
                                id
                                title
                                description
                            }
                        }
                    }
                }
                """,
                "variables": {"first": 10, "after": None}
            }
        }
    ]
    
    for endpoint in endpoints:
        print(f"\n🔍 Testing: {endpoint['name']}")
        print(f"URL: {endpoint['url']}")
        print(f"Headers: {json.dumps(endpoint['headers'], indent=2)}")
        print(f"Params: {json.dumps(endpoint['params'], indent=2)}")
        
        if 'data' in endpoint:
            print(f"Data: {json.dumps(endpoint['data'], indent=2)}")
        
        try:
            if 'data' in endpoint:
                response = requests.post(
                    endpoint['url'], 
                    params=endpoint['params'], 
                    headers=endpoint['headers'], 
                    json=endpoint['data'],
                    timeout=10
                )
            else:
                response = requests.get(
                    endpoint['url'], 
                    params=endpoint['params'], 
                    headers=endpoint['headers'], 
                    timeout=10
                )
            
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"Response Preview: {response.text[:200]}...")
            
            # Try to parse JSON
            try:
                json_data = response.json()
                print("✅ JSON parsed successfully")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                print(f"Error at line {e.lineno}, column {e.colno}")
                print(f"Context: {response.text[max(0, e.pos-50):e.pos+50]}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

def test_sixplay_endpoints():
    """Test 6play API endpoints"""
    print("\n" + "=" * 60)
    print("6PLAY API ENDPOINTS")
    print("=" * 60)
    
    endpoints = [
        {
            "name": "6play Login",
            "url": "https://login.6play.fr/accounts.login",
            "params": {},
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'referer': 'https://www.6play.fr/connexion'
            },
            "data": {
                "loginID": "test@example.com",  # Use test credentials
                "password": "testpassword",
                "apiKey": "3_hH5KBv25qZTd_sURpixbQW6a4OsiIzIEF2Ei_2H7TXTGLJb_1Hr4THKZianCQhWK",
                "format": "jsonp",
                "callback": "jsonp_3bbusffr388pem4"
            }
        },
        {
            "name": "6play Video API",
            "url": "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/videos/12345",
            "params": {"csa": "6", "with": "clips,freemiumpacks"},
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
            }
        },
        {
            "name": "6play Live API",
            "url": "https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/live",
            "params": {"channel": "M6", "with": "service_display_images,nextdiffusion,extra_data"},
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
            }
        },
        {
            "name": "6play Algolia Search",
            "url": "https://nhacvivxxk-dsn.algolia.net/1/indexes/*/queries",
            "params": {},
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'x-algolia-api-key': '6ef59fc6d78ac129339ab9c35edd41fa',
                'x-algolia-application-id': 'NHACVIVXXK',
            },
            "data": {
                'requests': [
                    {
                        'indexName': 'rtlmutu_prod_bedrock_layout_items_v2_m6web_main',
                        'query': 'Capital',
                        'params': 'clickAnalytics=true&hitsPerPage=10&facetFilters=[["metadata.item_type:program"], ["metadata.platforms_assets:m6group_web"]]',
                    }
                ]
            }
        }
    ]
    
    for endpoint in endpoints:
        print(f"\n🔍 Testing: {endpoint['name']}")
        print(f"URL: {endpoint['url']}")
        print(f"Headers: {json.dumps(endpoint['headers'], indent=2)}")
        print(f"Params: {json.dumps(endpoint['params'], indent=2)}")
        
        if 'data' in endpoint:
            print(f"Data: {json.dumps(endpoint['data'], indent=2)}")
        
        try:
            if 'data' in endpoint:
                response = requests.post(
                    endpoint['url'], 
                    params=endpoint['params'], 
                    headers=endpoint['headers'], 
                    data=endpoint['data'] if 'format' in endpoint.get('data', {}) else None,
                    json=endpoint['data'] if 'format' not in endpoint.get('data', {}) else None,
                    timeout=10
                )
            else:
                response = requests.get(
                    endpoint['url'], 
                    params=endpoint['params'], 
                    headers=endpoint['headers'], 
                    timeout=10
                )
            
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"Response Preview: {response.text[:200]}...")
            
            # Try to parse JSON
            try:
                json_data = response.json()
                print("✅ JSON parsed successfully")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                print(f"Error at line {e.lineno}, column {e.colno}")
                print(f"Context: {response.text[max(0, e.pos-50):e.pos+50]}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

def generate_curl_commands():
    """Generate curl commands for manual testing"""
    print("\n" + "=" * 60)
    print("CURL COMMANDS FOR MANUAL TESTING")
    print("=" * 60)
    
    print("\n# France TV - Envoyé Spécial")
    print("curl -X GET 'http://api-front.yatta.francetv.fr/standard/publish/taxonomies/france-2_envoye-special?platform=apps' \\")
    print("  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'")
    
    print("\n# MyTF1 - Bootstrap")
    print("curl -X GET 'https://compte.tf1.fr/accounts.webSdkBootstrap?apiKey=3_hWgJdARhz_7l1oOp3a8BDLoR9cuWZpUaKG4aqF7gum9_iK3uTZ2VlDBl8ANf8FVk&pageURL=https%3A%2F%2Fwww.tf1.fr%2F&sd=js_latest&sdkBuild=13987&format=json' \\")
    print("  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36' \\")
    print("  -H 'Referer: https://www.tf1.fr/'")
    
    print("\n# 6play - Video API")
    print("curl -X GET 'https://android.middleware.6play.fr/6play/v2/platforms/m6group_androidmob/services/6play/videos/12345?csa=6&with=clips,freemiumpacks' \\")
    print("  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'")
    
    print("\n# 6play - Algolia Search")
    print("curl -X POST 'https://nhacvivxxk-dsn.algolia.net/1/indexes/*/queries' \\")
    print("  -H 'Content-Type: application/x-www-form-urlencoded' \\")
    print("  -H 'x-algolia-api-key: 6ef59fc6d78ac129339ab9c35edd41fa' \\")
    print("  -H 'x-algolia-application-id: NHACVIVXXK' \\")
    print("  -d 'requests=[{\"indexName\":\"rtlmutu_prod_bedrock_layout_items_v2_m6web_main\",\"query\":\"Capital\",\"params\":\"clickAnalytics=true&hitsPerPage=10&facetFilters=[[\"metadata.item_type:program\"], [\"metadata.platforms_assets:m6group_web\"]]\"}]'")

def main():
    """Run all tests"""
    print("🧪 FRENCH TV PROVIDERS API TESTING TOOL")
    print("Use this to test API endpoints with online proxies")
    print("=" * 60)
    
    # Test all endpoints
    test_francetv_endpoints()
    test_mytf1_endpoints()
    test_sixplay_endpoints()
    
    # Generate curl commands
    generate_curl_commands()
    
    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
    print("\n💡 TIPS FOR TESTING WITH ONLINE PROXIES:")
    print("1. Use the curl commands above with services like:")
    print("   - https://httpbin.org/ (test basic requests)")
    print("   - https://webhook.site/ (inspect full requests)")
    print("   - https://requestbin.com/ (capture and analyze)")
    print("2. Test from different geographic locations")
    print("3. Compare responses between local and proxy requests")
    print("4. Check for rate limiting or IP blocking")
    print("5. Look for HTML error pages instead of JSON")

if __name__ == "__main__":
    main()

