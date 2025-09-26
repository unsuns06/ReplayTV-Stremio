#!/usr/bin/env python3
"""
Simple MyTF1 Proxy Test
Test the proxy with minimal setup to isolate issues
"""

import json
import requests
import time
import os
import urllib.parse
from urllib.parse import urlencode, quote, unquote

def get_random_windows_ua():
    """Generates a random Windows User-Agent string."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    ]
    return user_agents[0]  # Use consistent UA for testing

def test_proxy_basic():
    """Test basic proxy connectivity"""
    print("🔍 Testing basic proxy connectivity...")

    proxy_base = "https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url="
    test_url = "https://httpbin.org/get"

    headers = {
        "User-Agent": get_random_windows_ua(),
        "Accept": "application/json"
    }

    # Test different encoding approaches
    encodings = [
        ("Standard quote", quote(test_url, safe="")),
        ("No safe chars", quote(test_url)),
        ("Double encode", quote(quote(test_url, safe=""), safe="")),
    ]

    for encoding_name, encoded_url in encodings:
        proxied_url = proxy_base + encoded_url
        print(f"🔍 Testing {encoding_name}: {proxied_url}")

        try:
            response = requests.get(proxied_url, headers=headers, timeout=15)
            print(f"📊 Status: {response.status_code}")
            print(f"📊 Content: {response.text[:200]}...")

            if response.status_code == 200:
                print(f"✅ {encoding_name} SUCCESS!")
                return True
            else:
                print(f"❌ {encoding_name} FAILED: {response.status_code}")
        except Exception as e:
            print(f"❌ {encoding_name} ERROR: {e}")

    return False

def test_mytf1_proxy():
    """Test MyTF1 proxy with minimal headers"""
    print("\n🔍 Testing MyTF1 proxy...")

    proxy_base = "https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url="
    test_url = "https://mediainfo.tf1.fr/mediainfocombo/L_TF1"

    params = {
        'context': 'MYTF1',
        'pver': '5029000',
        'platform': 'web',
        'device': 'desktop',
        'os': 'windows',
        'osVersion': '10.0',
        'topDomain': 'www.tf1.fr',
        'playerVersion': '5.29.0',
        'productName': 'mytf1',
        'productVersion': '3.37.0',
        'format': 'hls'
    }

    dest_with_params = test_url + ("?" + urlencode(params) if params else "")

    headers = {
        "User-Agent": get_random_windows_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "referer": "https://www.tf1.fr",
        "origin": "https://www.tf1.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-For": "13.39.233.173",
        "X-Real-IP": "13.39.233.173",
        "CF-Connecting-IP": "13.39.233.173",
        "True-Client-IP": "13.39.233.173",
        "X-Client-IP": "13.39.233.173"
    }

    # Test different encoding approaches
    encodings = [
        ("Standard quote", quote(dest_with_params, safe="")),
        ("No safe chars", quote(dest_with_params)),
        ("Force decode then encode", quote(dest_with_params.replace('%3A', ':').replace('%2F', '/'), safe="")),
    ]

    for encoding_name, encoded_url in encodings:
        proxied_url = proxy_base + encoded_url
        print(f"\n🔍 Testing {encoding_name}")
        print(f"🔗 URL: {proxied_url}")

        try:
            response = requests.get(proxied_url, headers=headers, timeout=15)
            print(f"📊 Status: {response.status_code}")
            print(f"📊 Content-Type: {response.headers.get('content-type', 'N/A')}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ SUCCESS! Response keys: {list(data.keys()) if data else 'No keys'}")
                    if 'delivery' in data:
                        delivery = data['delivery']
                        print(f"✅ Delivery code: {delivery.get('code', 'N/A')}")
                        print(f"✅ Delivery URL: {delivery.get('url', 'N/A')[:50] if delivery.get('url') else 'N/A'}...")
                        if delivery.get('country'):
                            print(f"✅ Country: {delivery['country']}")
                    return True
                except json.JSONDecodeError:
                    print(f"❌ JSON decode failed: {response.text[:200]}...")
            else:
                print(f"❌ FAILED: {response.status_code}")
                print(f"❌ Response: {response.text[:200]}...")

        except Exception as e:
            print(f"❌ ERROR: {e}")

    return False

def test_with_auth_token():
    """Test MyTF1 proxy with authentication token"""
    print("\n🔍 Testing MyTF1 proxy with authentication...")

    # Try to get auth token
    auth_token = None
    try:
        from app.utils.credentials import get_provider_credentials
        from app.providers.fr.mytf1 import MyTF1Provider

        creds = get_provider_credentials('mytf1')
        if creds and creds.get('login') and creds.get('password'):
            print("✅ Found MyTF1 credentials")
            provider = MyTF1Provider()
            if provider._authenticate():
                auth_token = provider.auth_token
                print(f"✅ Got auth token: {auth_token[:20]}...")
            else:
                print("❌ Authentication failed")
        else:
            print("⚠️ No MyTF1 credentials found")
    except Exception as e:
        print(f"⚠️ Could not get authentication: {e}")

    if not auth_token:
        print("⚠️ Using test token")
        auth_token = "test_token"

    proxy_base = "https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url="
    test_url = "https://mediainfo.tf1.fr/mediainfocombo/L_TF1"

    params = {
        'context': 'MYTF1',
        'pver': '5029000',
        'platform': 'web',
        'device': 'desktop',
        'os': 'windows',
        'osVersion': '10.0',
        'topDomain': 'www.tf1.fr',
        'playerVersion': '5.29.0',
        'productName': 'mytf1',
        'productVersion': '3.37.0',
        'format': 'hls'
    }

    dest_with_params = test_url + ("?" + urlencode(params) if params else "")

    headers = {
        "User-Agent": get_random_windows_ua(),
        "authorization": f"Bearer {auth_token}",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "referer": "https://www.tf1.fr",
        "origin": "https://www.tf1.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-For": "13.39.233.173",
        "X-Real-IP": "13.39.233.173",
        "CF-Connecting-IP": "13.39.233.173",
        "True-Client-IP": "13.39.233.173",
        "X-Client-IP": "13.39.233.173"
    }

    # Test with standard encoding
    proxied_url = proxy_base + quote(dest_with_params, safe="")
    print(f"🔗 URL: {proxied_url}")

    try:
        response = requests.get(proxied_url, headers=headers, timeout=15)
        print(f"📊 Status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('content-type', 'N/A')}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ SUCCESS! Response keys: {list(data.keys()) if data else 'No keys'}")
                if 'delivery' in data:
                    delivery = data['delivery']
                    print(f"✅ Delivery code: {delivery.get('code', 'N/A')}")
                    print(f"✅ Delivery URL: {delivery.get('url', 'N/A')[:50] if delivery.get('url') else 'N/A'}...")
                    if delivery.get('country'):
                        print(f"✅ Country: {delivery['country']}")
                return True
            except json.JSONDecodeError:
                print(f"❌ JSON decode failed: {response.text[:200]}...")
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ ERROR: {e}")

    return False

def main():
    """Main test function"""
    print("🚀 Starting MyTF1 Simple Proxy Test...")

    # Test 1: Basic proxy connectivity
    print("\n" + "="*50)
    print("TEST 1: Basic Proxy Connectivity")
    print("="*50)
    basic_works = test_proxy_basic()

    # Test 2: MyTF1 proxy without auth
    print("\n" + "="*50)
    print("TEST 2: MyTF1 Proxy (no auth)")
    print("="*50)
    mytf1_works = test_mytf1_proxy()

    # Test 3: MyTF1 proxy with auth
    print("\n" + "="*50)
    print("TEST 3: MyTF1 Proxy (with auth)")
    print("="*50)
    auth_works = test_with_auth_token()

    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"✅ Basic proxy works: {basic_works}")
    print(f"✅ MyTF1 proxy (no auth) works: {mytf1_works}")
    print(f"✅ MyTF1 proxy (with auth) works: {auth_works}")

    if basic_works and mytf1_works:
        print("✅ Proxy is working correctly!")
    else:
        print("❌ Proxy has issues")

if __name__ == "__main__":
    main()
