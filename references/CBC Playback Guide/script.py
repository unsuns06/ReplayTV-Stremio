# Let me try to fetch the CBC extractor source code directly using requests
import requests

# Try to fetch the CBC extractor source code from GitHub
url = "https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/cbc.py"

try:
    response = requests.get(url)
    if response.status_code == 200:
        print("Successfully fetched CBC extractor code")
        print("Content length:", len(response.text))
        print("\n" + "="*50)
        print("CBC EXTRACTOR SOURCE CODE:")
        print("="*50)
        print(response.text)
    else:
        print(f"Failed to fetch: Status code {response.status_code}")
        print("Response:", response.text[:500])
except Exception as e:
    print(f"Error fetching CBC extractor: {e}")