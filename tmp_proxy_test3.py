import requests, urllib.parse
base = "https://tvff3tyk1e.execute-api.eu-west-3.amazonaws.com/api/router?url="
dest = "https://mediainfo.tf1.fr/mediainfocombo/L_TF1"
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
dest_with = dest + '?' + urllib.parse.urlencode(params)
url = base + urllib.parse.quote(dest_with, safe='')
resp = requests.get(url)
print(resp.status_code)
print(resp.text[:200])
