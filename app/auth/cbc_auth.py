#!/usr/bin/env python3
# cbc_auth.py

import os
import json
import base64
from uuid import uuid4
from urllib.parse import urlparse, parse_qs

import requests

# -----------------------------------------------------------------------------
# Configuration constants
# -----------------------------------------------------------------------------

API_KEY = '3f4beddd-2061-49b0-ae80-6f1f2ed65b37'
SCOPES = (
    'openid offline_access '
    'https://rcmnb2cprod.onmicrosoft.com/84593b65-0ef6-4a72-891c-d351ddd50aab/media-validation '
    'https://rcmnb2cprod.onmicrosoft.com/84593b65-0ef6-4a72-891c-d351ddd50aab/profile'
)

AUTHORIZE_LOGIN = (
    'https://login.cbc.radio-canada.ca/bef1b538-1950-4283-9b27-b096cbc18070/'
    'B2C_1A_ExternalClient_FrontEnd_Login_CBC/oauth2/v2.0/authorize'
)
SELF_ASSERTED = (
    'https://login.cbc.radio-canada.ca/bef1b538-1950-4283-9b27-b096cbc18070/'
    'B2C_1A_ExternalClient_FrontEnd_Login_CBC/SelfAsserted'
)
CONFIRM_LOGIN = (
    'https://login.cbc.radio-canada.ca/bef1b538-1950-4283-9b27-b096cbc18070/'
    'B2C_1A_ExternalClient_FrontEnd_Login_CBC/api/SelfAsserted/confirmed'
)
SIGNIN_LOGIN = (
    'https://login.cbc.radio-canada.ca/bef1b538-1950-4283-9b27-b096cbc18070/'
    'B2C_1A_ExternalClient_FrontEnd_Login_CBC/api/CombinedSigninAndSignup/confirmed'
)
TOKEN_URL = 'https://services.radio-canada.ca/ott/cbc-api/v2/token'
PROFILE_URL = 'https://services.radio-canada.ca/ott/subscription/v2/gem/subscriber/profile'

AUTH_FILE = os.path.expanduser('~/.cbc_auth.json')
COOKIE_FILE = os.path.expanduser('~/.cbc_cookies.json')

# -----------------------------------------------------------------------------
# Helpers to save and load tokens & cookies
# -----------------------------------------------------------------------------

def save_tokens(access_token: str, claims_token: str):
    data = {'access_token': access_token, 'claims_token': claims_token}
    with open(AUTH_FILE, 'w') as f:
        json.dump(data, f)

def load_tokens():
    if not os.path.exists(AUTH_FILE):
        return None, None
    data = json.load(open(AUTH_FILE))
    return data.get('access_token'), data.get('claims_token')

def save_cookies(session: requests.Session):
    # Persist cookies to disk as JSON
    with open(COOKIE_FILE, 'w') as f:
        json.dump(session.cookies.get_dict(), f)

def load_cookies(session: requests.Session):
    if os.path.exists(COOKIE_FILE):
        cookies = json.load(open(COOKIE_FILE))
        session.cookies.update(cookies)

# -----------------------------------------------------------------------------
# Core authorization flow (Azure AD B2C)
# -----------------------------------------------------------------------------

class CBCAuth:
    def __init__(self):
        self.session = requests.Session()
        load_cookies(self.session)

    def _get_nonce_and_state(self):
        """Generate nonce, state (base64-encoded payload)."""
        nonce = str(uuid4())
        tid = str(uuid4())
        state_payload = f'{tid}|{{"action":"login","returnUrl":"/","fromSubscription":false}}'
        state = base64.b64encode(state_payload.encode()).decode()
        return nonce, state

    def authorize_step1(self):
        """Step 1: initiate authorization, get gateway request ID."""
        nonce, state = self._get_nonce_and_state()
        params = {
            'client_id': 'fc05b0ee-3865-4400-a3cc-3da82c330c23',
            'nonce': nonce,
            'redirect_uri': 'https://gem.cbc.ca/auth-changed',
            'scope': SCOPES,
            'response_type': 'id_token token',
            'response_mode': 'fragment',
            'state': state,
            'state_value': state,
            'ui_locales': 'en',
        }
        r = self.session.get(AUTHORIZE_LOGIN, params=params)
        r.raise_for_status()
        if 'x-ms-gateway-requestid' not in r.headers:
            raise RuntimeError("Missing gateway-request ID in step 1 response")
        save_cookies(self.session)
        return r.headers['x-ms-gateway-requestid']

    def authorize_step2_self_asserted(self, tx: str, username: str, password: str = None):
        """Step 2: submit username (and optionally password) to SelfAsserted endpoint."""
        cookies = self.session.cookies.get_dict()
        headers = {'x-csrf-token': cookies.get('x-ms-cpim-csrf', '')}
        params = {'tx': tx, 'p': 'B2C_1A_ExternalClient_FrontEnd_Login_CBC'}
        data = {'request_type': 'RESPONSE', 'email': username}
        if password:
            data['password'] = password
        r = self.session.post(SELF_ASSERTED, params=params, headers=headers, data=data)
        r.raise_for_status()
        save_cookies(self.session)
        return True

    def authorize_step3_confirmed(self, tx: str):
        """Step 3: confirm login, retrieve new gateway request ID."""
        cookies = self.session.cookies.get_dict()
        params = {
            'tx': tx,
            'p': 'B2C_1A_ExternalClient_FrontEnd_Login_CBC',
            'csrf_token': cookies.get('x-ms-cpim-csrf', '')
        }
        r = self.session.get(CONFIRM_LOGIN, params=params)
        r.raise_for_status()
        if 'x-ms-gateway-requestid' not in r.headers:
            raise RuntimeError("Missing gateway-request ID in step 3 response")
        save_cookies(self.session)
        return r.headers['x-ms-gateway-requestid']

    def authorize_step4_signin(self, tx: str):
        """Step 4: finalize sign-in, obtain access_token & id_token from redirect."""
        cookies = self.session.cookies.get_dict()
        params = {
            'tx': tx,
            'p': 'B2C_1A_ExternalClient_FrontEnd_Login_CBC',
            'csrf_token': cookies.get('x-ms-cpim-csrf', ''),
            'rememberMe': 'true',
        }
        r = self.session.get(SIGNIN_LOGIN, params=params, allow_redirects=False)
        if r.status_code != 302 or 'location' not in r.headers:
            raise RuntimeError("Sign-in redirect failed")
        # Parse tokens out of URL fragment
        fragment = urlparse(r.headers['location']).fragment
        values = parse_qs(fragment)
        access_token = values.get('access_token', [None])[0]
        id_token     = values.get('id_token', [None])[0]
        if not access_token or not id_token:
            raise RuntimeError("Missing tokens in step 4 fragment")
        save_cookies(self.session)
        return access_token, id_token

    def fetch_claims_token(self, access_token: str):
        """Use the Bearer access token to get the x-claims-token."""
        headers = {'Authorization': f'Bearer {access_token}'}
        r = self.session.get(PROFILE_URL, headers=headers, params={'device':'web'})
        r.raise_for_status()
        data = r.json()
        return data.get('claimsToken')

    def authenticate(self, username: str, password: str):
        """
        Perform the full multi-step login:
          1. authorize → tx1
          2. self-asserted (email) → submit username
          3. confirmed → tx2
          4. self-asserted (password) → finalize credentials
          5. sign-in → obtain access_token & id_token
          6. fetch claimsToken
          7. save both tokens to disk
        """
        # Step 1
        tx1 = self.authorize_step1()

        # Step 2: send username (no password)
        # Derive the tx argument from cookies
        trans_cookie = self.session.cookies.get('x-ms-cpim-trans', '')
        tx_arg = 'StateProperties=' + base64.b64encode(
            json.dumps({"TID": json.loads(base64.b64decode(trans_cookie)).get("C_ID")}).encode()
        ).decode().rstrip('=')
        self.authorize_step2_self_asserted(tx_arg, username)

        # Step 3
        tx2 = self.authorize_step3_confirmed(tx_arg)

        # Step 4: send password
        self.authorize_step2_self_asserted(tx_arg, username, password)

        # Step 5: final sign-in
        access_token, id_token = self.authorize_step4_signin(tx_arg)

        # Step 6: fetch claimsToken
        claims_token = self.fetch_claims_token(access_token)

        # Step 7: persist
        save_tokens(access_token, claims_token)
        print("Authentication successful. Tokens saved to:", AUTH_FILE)

# -----------------------------------------------------------------------------
# Usage example
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import getpass

    print("CBC Gem Authentication")
    user = input("CBC Gem email: ").strip()
    pwd  = getpass.getpass("Password: ")
    auth = CBCAuth()
    auth.authenticate(user, pwd)