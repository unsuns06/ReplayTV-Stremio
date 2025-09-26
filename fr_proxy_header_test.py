#!/usr/bin/env python3
"""
French Proxy Header Forwarding Test
Comprehensive test to verify the French proxy properly forwards all headers and parameters
Uses httpbin.org as a reflection service to test header forwarding accuracy
"""

import json
import requests
import time
import urllib.parse
from urllib.parse import urlencode, quote

def get_random_windows_ua():
    """Generate a random Windows User-Agent string."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/109.0',
    ]
    return user_agents[0]  # Use consistent UA for testing

def test_basic_connectivity():
    """Test basic connectivity to httpbin.org via French proxy."""
    print("🔍 Testing basic connectivity...")

    proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="
    test_url = "https://httpbin.org/get"

    headers = {
        "User-Agent": get_random_windows_ua(),
        "Accept": "application/json"
    }

    proxied_url = proxy_base + quote(test_url, safe="")
    print(f"🔗 Testing: {proxied_url}")

    try:
        response = requests.get(proxied_url, headers=headers, timeout=15)
        print(f"📊 Status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('content-type', 'N/A')}")

        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS! Basic connectivity works")
            print(f"✅ Response origin: {data.get('origin', 'N/A')}")
            return True
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_header_forwarding():
    """Test comprehensive header forwarding."""
    print("\n" + "="*60)
    print("🧪 TESTING HEADER FORWARDING")
    print("="*60)

    proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="
    test_url = "https://httpbin.org/headers"

    # Headers we want to test (comprehensive set including MyTF1 headers)
    test_headers = {
        # Basic HTTP headers
        "User-Agent": get_random_windows_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8,en-US;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Charset": "UTF-8,*;q=0.5",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",

        # Referrer and origin
        "Referer": "https://www.tf1.fr",
        "Origin": "https://www.tf1.fr",

        # Security headers
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-GPC": "1",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",

        # Authentication (test token)
        "Authorization": "Bearer eyJhbGciOiJFUzI1NiIsImtpZCI6ImRlZmF1bHQiLCJ0eXAiOiJKV1QifQ.test_token_signature",

        # IP forwarding headers (critical for geo-restricted content)
        "X-Forwarded-For": "13.39.233.173",
        "X-Real-IP": "13.39.233.173",
        "X-Client-IP": "13.39.233.173",
        "CF-Connecting-IP": "13.39.233.173",
        "True-Client-IP": "13.39.233.173",

        # Extended IP headers
        "X-Forwarded-Host": "mediainfo.tf1.fr",
        "X-Forwarded-Proto": "https",
        "X-Originating-IP": "13.39.233.173",
        "X-Remote-IP": "13.39.233.173",
        "X-Remote-Addr": "13.39.233.173",
        "Forwarded": "for=13.39.233.173;proto=https;host=mediainfo.tf1.fr",

        # Custom test headers
        "X-Custom-Test": "CustomValue123",
        "X-Mediaflow-Test": "MediaflowProxyTest",
        "X-Proxy-Test": "FrenchProxyTest2024",
    }

    proxied_url = proxy_base + quote(test_url, safe="")
    print(f"🔗 Testing header forwarding: {proxied_url}")

    try:
        response = requests.get(proxied_url, headers=test_headers, timeout=15)
        print(f"📊 Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            forwarded_headers = data.get('headers', {})

            print("✅ SUCCESS! Headers received by httpbin.org:")
            print("-" * 40)

            # Check key headers
            forwarded_count = 0
            total_count = len(test_headers)

            for header_name, expected_value in test_headers.items():
                forwarded_value = forwarded_headers.get(header_name)
                if forwarded_value:
                    forwarded_count += 1
                    print(f"✅ {header_name}: {forwarded_value}")
                    if forwarded_value != expected_value:
                        print(f"   ⚠️  Value differs: expected '{expected_value}'")
                else:
                    print(f"❌ {header_name}: MISSING")

            print("-" * 40)
            print(f"📊 Forwarding success: {forwarded_count}/{total_count} headers forwarded")

            # Check if critical headers are present
            critical_headers = [
                "Authorization", "X-Forwarded-For", "X-Real-IP",
                "User-Agent", "Referer", "Origin"
            ]

            print("\n🔍 Critical headers check:")
            for critical in critical_headers:
                if critical in forwarded_headers:
                    print(f"✅ {critical}: PRESENT")
                else:
                    print(f"❌ {critical}: MISSING")

            return forwarded_count == total_count

        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_query_parameters():
    """Test query parameter forwarding."""
    print("\n" + "="*60)
    print("🧪 TESTING QUERY PARAMETER FORWARDING")
    print("="*60)

    proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/proxy/"
    test_url = "https://httpbin.org/get"

    # Parameters we want to test
    test_params = {
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
        'format': 'hls',
        'custom_param': 'test_value_123',
        'auth_token': 'eyJhbGciOiJFUzI1NiIsImtpZCI6ImRlZmF1bHQiLCJ0eXAiOiJKV1QifQ.test'
    }

    headers = {
        "User-Agent": get_random_windows_ua(),
        "Accept": "application/json"
    }

    # Build URL with parameters
    param_string = urlencode(test_params)
    full_test_url = test_url + "?" + param_string
    proxied_url = proxy_base + quote(full_test_url, safe="")

    print(f"🔗 Testing parameter forwarding: {proxied_url}")

    try:
        response = requests.get(proxied_url, headers=headers, timeout=15)
        print(f"📊 Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            forwarded_args = data.get('args', {})

            print("✅ SUCCESS! Parameters received by httpbin.org:")
            print("-" * 40)

            forwarded_count = 0
            total_count = len(test_params)

            for param_name, expected_value in test_params.items():
                forwarded_value = forwarded_args.get(param_name)
                if forwarded_value:
                    forwarded_count += 1
                    print(f"✅ {param_name}: {forwarded_value}")
                    if forwarded_value != expected_value:
                        print(f"   ⚠️  Value differs: expected '{expected_value}'")
                else:
                    print(f"❌ {param_name}: MISSING")

            print("-" * 40)
            print(f"📊 Parameter forwarding success: {forwarded_count}/{total_count} parameters forwarded")

            return forwarded_count == total_count

        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_post_requests():
    """Test POST request forwarding."""
    print("\n" + "="*60)
    print("🧪 TESTING POST REQUEST FORWARDING")
    print("="*60)

    proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="
    test_url = "https://httpbin.org/post"

    headers = {
        "User-Agent": get_random_windows_ua(),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJFUzI1NiIsImtpZCI6ImRlZmF1bHQiLCJ0eXAiOiJKV1QifQ.test_post_token",
        "X-Forwarded-For": "13.39.233.173",
        "X-Real-IP": "13.39.233.173"
    }

    # POST data to send
    post_data = {
        "loginID": "test_user",
        "password": "test_password",
        "sessionExpiration": 31536000,
        "targetEnv": "jssdk",
        "include": "identities-all,data,profile,preferences",
        "includeUserInfo": "true",
        "loginMode": "standard",
        "lang": "fr",
        "APIKey": "test_api_key_123",
        "sdk": "js_latest",
        "authMode": "cookie",
        "pageURL": "https://www.tf1.fr",
        "sdkBuild": 13987,
        "format": "json"
    }

    proxied_url = proxy_base + quote(test_url, safe="")
    print(f"🔗 Testing POST forwarding: {proxied_url}")

    try:
        response = requests.post(proxied_url, headers=headers, json=post_data, timeout=15)
        print(f"📊 Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            forwarded_json = data.get('json', {})

            print("✅ SUCCESS! POST data received by httpbin.org:")
            print("-" * 40)

            forwarded_count = 0
            total_count = len(post_data)

            for key, expected_value in post_data.items():
                forwarded_value = forwarded_json.get(key)
                if forwarded_value is not None:
                    forwarded_count += 1
                    print(f"✅ {key}: {forwarded_value}")
                    if forwarded_value != expected_value:
                        print(f"   ⚠️  Value differs: expected '{expected_value}'")
                else:
                    print(f"❌ {key}: MISSING")

            print("-" * 40)
            print(f"📊 POST data forwarding success: {forwarded_count}/{total_count} fields forwarded")

            # Check forwarded headers too
            forwarded_headers = data.get('headers', {})
            print(f"\n📊 Headers forwarded: {len(forwarded_headers)} headers")
            for header_name, header_value in headers.items():
                if header_name in forwarded_headers:
                    print(f"✅ {header_name}: PRESENT")
                else:
                    print(f"❌ {header_name}: MISSING")

            return forwarded_count == total_count

        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_mytf1_real_scenario():
    """Test with a real MyTF1-like scenario."""
    print("\n" + "="*60)
    print("🧪 TESTING MyTF1 REAL SCENARIO")
    print("="*60)

    proxy_base = "https://8cyq9n1ebd.execute-api.eu-west-3.amazonaws.com/prod/?url="

    # Simulate a real MyTF1 mediainfo request
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

    headers = {
        "User-Agent": get_random_windows_ua(),
        "authorization": "Bearer eyJhbGciOiJFUzI1NiIsImtpZCI6ImRlZmF1bHQiLCJ0eXAiOiJKV1QifQ.mytf1_test_token_123",
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
        "X-Client-IP": "13.39.233.173",
        "CF-Connecting-IP": "13.39.233.173",
        "True-Client-IP": "13.39.233.173",
        "X-Forwarded-Host": "mediainfo.tf1.fr",
        "X-Forwarded-Proto": "https"
    }

    full_url = test_url + "?" + urlencode(params)
    proxied_url = proxy_base + quote(full_url, safe="")

    print(f"🔗 Testing MyTF1 scenario: {proxied_url}")

    try:
        response = requests.get(proxied_url, headers=headers, timeout=15)
        print(f"📊 Status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('content-type', 'N/A')}")

        if response.status_code == 200:
            try:
                data = response.json()

                # Check if this looks like a valid MyTF1 response
                if 'delivery' in data:
                    delivery = data['delivery']
                    delivery_code = delivery.get('code', 'N/A')
                    print(f"✅ Got MyTF1-like response: Delivery code {delivery_code}")

                    if delivery_code == 200:
                        print("✅ SUCCESS! MyTF1 scenario works through proxy")
                        return True
                    else:
                        print(f"⚠️  MyTF1 response received but delivery code is {delivery_code}")
                        return False
                else:
                    print("⚠️  Response doesn't look like MyTF1 format")
                    print(f"📊 Response keys: {list(data.keys())}")
                    return False

            except json.JSONDecodeError:
                print("❌ JSON decode failed - not a valid JSON response")
                print(f"❌ Raw response: {response.text[:200]}...")
                return False
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"❌ Response: {response.text[:200]}...")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 French Proxy Header Forwarding Test Suite")
    print("=" * 60)
    print("Testing: https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router")
    print("Target: httpbin.org (reflection service)")
    print("=" * 60)

    results = {}

    # Test 1: Basic connectivity
    print("\n" + "="*50)
    print("TEST 1: Basic Connectivity")
    print("="*50)
    results['connectivity'] = test_basic_connectivity()

    # Test 2: Header forwarding
    results['headers'] = test_header_forwarding()

    # Test 3: Query parameters
    results['parameters'] = test_query_parameters()

    # Test 4: POST requests
    results['post'] = test_post_requests()

    # Test 5: MyTF1 real scenario
    results['mytf1_scenario'] = test_mytf1_real_scenario()

    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)

    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)

    print(f"✅ Tests passed: {passed_tests}/{total_tests}")
    print(f"❌ Tests failed: {total_tests - passed_tests}/{total_tests}")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name: <15} : {status}")

    print("\n" + "="*60)
    print("🔍 RECOMMENDATIONS")
    print("="*60)

    if results['connectivity']:
        print("✅ Basic proxy connectivity: WORKING")
    else:
        print("❌ Basic proxy connectivity: FAILED - Check network/proxy availability")

    if results['headers']:
        print("✅ Header forwarding: WORKING - All headers properly forwarded")
    else:
        print("❌ Header forwarding: PARTIAL - Some headers may be missing")

    if results['parameters']:
        print("✅ Query parameter forwarding: WORKING")
    else:
        print("❌ Query parameter forwarding: FAILED - Parameters not forwarded")

    if results['post']:
        print("✅ POST request forwarding: WORKING")
    else:
        print("❌ POST request forwarding: FAILED - POST data not forwarded")

    if results['mytf1_scenario']:
        print("✅ MyTF1 real scenario: WORKING - Proxy compatible with MyTF1")
    else:
        print("❌ MyTF1 real scenario: FAILED - Proxy issues with MyTF1 requests")

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
