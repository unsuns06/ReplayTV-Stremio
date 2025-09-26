#!/usr/bin/env python3
"""
Detailed MyTF1 Proxy Test
Compare direct vs proxy requests and test different header combinations
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

def test_direct_vs_proxy():
    """Compare direct request vs proxy request"""
    print("🔍 Comparing direct vs proxy requests...")

    # Get authentication token first
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
                return
        else:
            print("⚠️ No MyTF1 credentials found")
            return
    except Exception as e:
        print(f"⚠️ Could not get authentication: {e}")
        return

    # Test URL
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

    # Headers exactly as used in MyTF1Provider
    headers = {
        "User-Agent": get_random_windows_ua(),
        "authorization": f"Bearer {auth_token}",
        "referer": "https://www.tf1.fr",
        "origin": "https://www.tf1.fr",
        "accept-language": "fr-FR,fr;q=0.9,en;q=0.8,en-US;q=0.7",
        "accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Charset": "UTF-8,*;q=0.5",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-GPC": "1",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-For": "13.39.233.173",
        "X-Real-IP": "13.39.233.173",
        "CF-Connecting-IP": "13.39.233.173",
        "True-Client-IP": "13.39.233.173",
        "X-Client-IP": "13.39.233.173"
    }

    # Test 1: Direct request
    print("\n" + "="*50)
    print("TEST 1: Direct Request")
    print("="*50)
    print(f"🔗 URL: {dest_with_params}")

    try:
        response = requests.get(dest_with_params, headers=headers, timeout=15)
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
            except json.JSONDecodeError:
                print(f"❌ JSON decode failed: {response.text[:200]}...")
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ ERROR: {e}")

    # Test 2: Proxy request
    print("\n" + "="*50)
    print("TEST 2: Proxy Request")
    print("="*50)
    proxy_base = "https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url="
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
            except json.JSONDecodeError:
                print(f"❌ JSON decode failed: {response.text[:200]}...")
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_different_auth_formats():
    """Test different authentication token formats"""
    print("\n" + "="*50)
    print("TEST 3: Different Auth Formats")
    print("="*50)

    # Get authentication token first
    auth_token = None
    try:
        from app.utils.credentials import get_provider_credentials
        from app.providers.fr.mytf1 import MyTF1Provider

        creds = get_provider_credentials('mytf1')
        if creds and creds.get('login') and creds.get('password'):
            provider = MyTF1Provider()
            if provider._authenticate():
                auth_token = provider.auth_token
                print(f"✅ Got auth token: {auth_token[:20]}...")
            else:
                print("❌ Authentication failed")
                return
        else:
            print("⚠️ No MyTF1 credentials found")
            return
    except Exception as e:
        print(f"⚠️ Could not get authentication: {e}")
        return

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
    proxy_base = "https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url="
    proxied_url = proxy_base + quote(dest_with_params, safe="")

    # Different auth header formats
    auth_formats = [
        ("Bearer token", f"Bearer {auth_token}"),
        ("Authorization header", auth_token),
        ("JWT header", f"JWT {auth_token}"),
        ("Token header", f"Token {auth_token}"),
    ]

    base_headers = {
        "User-Agent": get_random_windows_ua(),
        "referer": "https://www.tf1.fr",
        "origin": "https://www.tf1.fr",
        "accept-language": "fr-FR,fr;q=0.9,en;q=0.8,en-US;q=0.7",
        "accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Charset": "UTF-8,*;q=0.5",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-GPC": "1",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-For": "13.39.233.173",
        "X-Real-IP": "13.39.233.173",
        "CF-Connecting-IP": "13.39.233.173",
        "True-Client-IP": "13.39.233.173",
        "X-Client-IP": "13.39.233.173"
    }

    for auth_name, auth_value in auth_formats:
        print(f"\n🔍 Testing {auth_name}")
        headers = base_headers.copy()
        headers["authorization"] = auth_value

        try:
            response = requests.get(proxied_url, headers=headers, timeout=15)
            print(f"📊 Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'delivery' in data:
                        delivery = data['delivery']
                        delivery_code = delivery.get('code', 'N/A')
                        print(f"✅ Delivery code: {delivery_code}")
                        if delivery_code == 200:
                            print(f"✅ SUCCESS with {auth_name}!")
                            return True
                        elif delivery_code <= 400:
                            print(f"⚠️ Partial success with {auth_name}: {delivery_code}")
                        else:
                            print(f"❌ Failed with {auth_name}: {delivery_code}")
                except json.JSONDecodeError:
                    print(f"❌ JSON decode failed for {auth_name}")
            else:
                print(f"❌ HTTP {response.status_code} for {auth_name}")

        except Exception as e:
            print(f"❌ ERROR for {auth_name}: {e}")

    return False

def test_ip_header_variations():
    """Test different IP header combinations"""
    print("\n" + "="*50)
    print("TEST 4: IP Header Variations")
    print("="*50)

    # Get authentication token first
    auth_token = None
    try:
        from app.utils.credentials import get_provider_credentials
        from app.providers.fr.mytf1 import MyTF1Provider

        creds = get_provider_credentials('mytf1')
        if creds and creds.get('login') and creds.get('password'):
            provider = MyTF1Provider()
            if provider._authenticate():
                auth_token = provider.auth_token
                print(f"✅ Got auth token: {auth_token[:20]}...")
            else:
                print("❌ Authentication failed")
                return
        else:
            print("⚠️ No MyTF1 credentials found")
            return
    except Exception as e:
        print(f"⚠️ Could not get authentication: {e}")
        return

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
    proxy_base = "https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url="
    proxied_url = proxy_base + quote(dest_with_params, safe="")

    # Different IP header combinations
    ip_combinations = [
        ("Minimal IP headers", {
            "X-Forwarded-For": "13.39.233.173",
            "X-Real-IP": "13.39.233.173",
        }),
        ("Standard IP headers", {
            "X-Forwarded-For": "13.39.233.173",
            "X-Real-IP": "13.39.233.173",
            "CF-Connecting-IP": "13.39.233.173",
            "True-Client-IP": "13.39.233.173",
            "X-Client-IP": "13.39.233.173"
        }),
        ("Extended IP headers", {
            "X-Forwarded-For": "13.39.233.173",
            "X-Forwarded-Host": "mediainfo.tf1.fr",
            "X-Forwarded-Proto": "https",
            "X-Real-IP": "13.39.233.173",
            "X-Client-IP": "13.39.233.173",
            "CF-Connecting-IP": "13.39.233.173",
            "True-Client-IP": "13.39.233.173",
            "X-Originating-IP": "13.39.233.173",
            "X-Remote-IP": "13.39.233.173",
            "X-Remote-Addr": "13.39.233.173",
        }),
        ("French ISP headers", {
            "X-Forwarded-For": "13.39.233.173",
            "X-Real-IP": "13.39.233.173",
            "X-Client-IP": "13.39.233.173",
            "X-Forwarded-For": "13.39.233.173",
            "CF-Connecting-IP": "13.39.233.173",
            "True-Client-IP": "13.39.233.173",
            "X-Mme-Client-IP": "13.39.233.173",
            "X-Forwarded-Client-IP": "13.39.233.173"
        }),
    ]

    base_headers = {
        "User-Agent": get_random_windows_ua(),
        "authorization": f"Bearer {auth_token}",
        "referer": "https://www.tf1.fr",
        "origin": "https://www.tf1.fr",
        "accept-language": "fr-FR,fr;q=0.9,en;q=0.8,en-US;q=0.7",
        "accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Charset": "UTF-8,*;q=0.5",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-GPC": "1",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }

    for combo_name, ip_headers in ip_combinations:
        print(f"\n🔍 Testing {combo_name}")
        headers = base_headers.copy()
        headers.update(ip_headers)

        try:
            response = requests.get(proxied_url, headers=headers, timeout=15)
            print(f"📊 Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'delivery' in data:
                        delivery = data['delivery']
                        delivery_code = delivery.get('code', 'N/A')
                        print(f"✅ Delivery code: {delivery_code}")
                        if delivery_code == 200:
                            print(f"✅ SUCCESS with {combo_name}!")
                            return True
                        elif delivery_code <= 400:
                            print(f"⚠️ Partial success with {combo_name}: {delivery_code}")
                        else:
                            print(f"❌ Failed with {combo_name}: {delivery_code}")
                except json.JSONDecodeError:
                    print(f"❌ JSON decode failed for {combo_name}")
            else:
                print(f"❌ HTTP {response.status_code} for {combo_name}")

        except Exception as e:
            print(f"❌ ERROR for {combo_name}: {e}")

    return False

def main():
    """Main test function"""
    print("🚀 Starting Detailed MyTF1 Proxy Test...")

    # Test 1: Direct vs Proxy comparison
    test_direct_vs_proxy()

    # Test 2: Different auth formats
    test_different_auth_formats()

    # Test 3: IP header variations
    test_ip_header_variations()

    print("\n" + "="*50)
    print("TEST COMPLETE")
    print("="*50)

if __name__ == "__main__":
    main()
