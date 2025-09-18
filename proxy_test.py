from app.providers.fr.mytf1 import MyTF1Provider
import urllib.parse, requests

p = MyTF1Provider()
p._authenticate()
params = {
    'context': 'MYTF1',
    'pver': '5029000',
    'platform': 'web',
    'device': 'desktop',
    'os': 'windows',
    'osVersion': '10.0',
    'topDomain': 'https://www.tf1.fr',
    'playerVersion': '5.29.0',
    'productName': 'mytf1',
    'productVersion': '3.37.0',
    'format': 'hls'
}
base = 'https://mediainfo.tf1.fr/mediainfocombo/L_TF1'
dest = base + '?' + urllib.parse.urlencode(params)
proxy = 'https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url=' + urllib.parse.quote(dest, safe='')
headers = {
    'User-Agent': 'Mozilla/5.0',
    'authorization': f'Bearer {p.auth_token}',
    'referer': 'https://www.tf1.fr',
    'origin': 'https://www.tf1.fr'
}
resp = requests.get(proxy, headers=headers)
print('status', resp.status_code)
print('body', resp.text[:200])
print('headers', resp.headers)
