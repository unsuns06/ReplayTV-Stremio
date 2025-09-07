#!/usr/bin/env python3
"""
Test script to verify the background image is included
"""

import requests
import json

def test_background_image():
    """Test the background image in meta endpoint"""
    print("🖼️ Testing background image in meta endpoint...")
    
    try:
        response = requests.get('http://localhost:7860/meta/series/cutam:ca:cbc:dragons-den.json')
        
        if response.status_code == 200:
            data = response.json()
            meta = data.get('meta', {})
            
            print(f"Series: {meta.get('name', 'No name')}")
            print(f"Type: {meta.get('type', 'No type')}")
            print(f"Background URL: {meta.get('background', 'No background')}")
            print(f"Poster URL: {meta.get('poster', 'No poster')}")
            print(f"Logo URL: {meta.get('logo', 'No logo')}")
            
            # Check if background is the correct URL
            expected_bg = "https://images.gem.cbc.ca/v1/synps-cbc/show/perso/cbc_dragons_den_ott_program_v12.jpg"
            actual_bg = meta.get('background', '')
            
            if expected_bg in actual_bg:
                print("✅ Background image URL is correct!")
            else:
                print("❌ Background image URL is incorrect")
                print(f"Expected: {expected_bg}")
                print(f"Actual: {actual_bg}")
            
            print("\n✅ Background image test completed!")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_background_image()




