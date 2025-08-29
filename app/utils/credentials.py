import json
import os

def load_credentials():
    """Load credentials from credentials.json file"""
    credentials_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'credentials.json')
    
    if os.path.exists(credentials_path):
        with open(credentials_path, 'r') as f:
            return json.load(f)
    else:
        return {}

def get_provider_credentials(provider_name):
    """Get credentials for a specific provider"""
    credentials = load_credentials()
    return credentials.get(provider_name, {})