import json
import time
import struct
import hmac
import hashlib
import requests
from base64 import b64decode, b64encode

print("Loading maFile...")

with open('../SDA.1.0.15/maFiles/76561199113719186.maFile', 'r') as f:
    mafile = json.load(f)

STEAM_ID = str(mafile['Session']['SteamID'])
ACCESS_TOKEN = mafile['Session']['AccessToken']
REFRESH_TOKEN = mafile['Session']['RefreshToken']
DEVICE_ID = mafile['device_id']
IDENTITY_SECRET = b64decode(mafile['identity_secret'])

print(f"Account: {mafile['account_name']}")
print(f"SteamID: {STEAM_ID}")

def generate_confirmation_key(identity_secret, tag, timestamp):
    data = struct.pack('>Q', timestamp) + tag.encode('ascii')
    return b64encode(hmac.new(identity_secret, data, hashlib.sha1).digest()).decode('ascii')

def get_steam_time():
    try:
        resp = requests.post('https://api.steampowered.com/ITwoFactorService/QueryTime/v1/', data={}, timeout=10)
        return int(resp.json().get('response', {}).get('server_time', time.time()))
    except:
        return int(time.time())

# Сначала обновляем токен через RefreshToken
print("\nRefreshing access token...")
refresh_resp = requests.post(
    'https://api.steampowered.com/IAuthenticationService/GenerateAccessTokenForApp/v1/',
    data={'refresh_token': REFRESH_TOKEN, 'steamid': STEAM_ID},
    timeout=15
)
print(f"Refresh status: {refresh_resp.status_code}")
print(f"Refresh response: {refresh_resp.text[:500]}")

try:
    refresh_data = refresh_resp.json().get('response', {})
    if refresh_data.get('access_token'):
        ACCESS_TOKEN = refresh_data['access_token']
        print(f"\n✓ Got new access token: {ACCESS_TOKEN[:50]}...")
        
        # Сохраняем новый токен в maFile
        mafile['Session']['AccessToken'] = ACCESS_TOKEN
        with open('../SDA.1.0.15/maFiles/76561199113719186.maFile', 'w') as f:
            json.dump(mafile, f)
        print("✓ Saved new token to maFile")
    else:
        print(f"✗ No access token in response")
except Exception as e:
    print(f"Error: {e}")

print("\nGetting Steam time...")
ts = get_steam_time()
print(f"Steam time: {ts}")

print("\nCreating session with new token...")
session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36'
session.cookies.set('steamLoginSecure', f"{STEAM_ID}%7C%7C{ACCESS_TOKEN}", domain='steamcommunity.com')
session.cookies.set('mobileClient', 'android', domain='steamcommunity.com')

print("\nFetching confirmations...")
params = {
    'p': DEVICE_ID,
    'a': STEAM_ID,
    'k': generate_confirmation_key(IDENTITY_SECRET, 'conf', ts),
    't': ts,
    'm': 'react',
    'tag': 'conf'
}

resp = session.get('https://steamcommunity.com/mobileconf/getlist', params=params, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

try:
    data = resp.json()
    if data.get('success'):
        confs = data.get('conf', [])
        print(f"\n✓ Found {len(confs)} confirmations!")
        
        for conf in confs:
            print(f"\n  {conf.get('headline')} ({conf.get('type_name')})")
            ts = get_steam_time()
            ap = {'op': 'allow', 'p': DEVICE_ID, 'a': STEAM_ID,
                  'k': generate_confirmation_key(IDENTITY_SECRET, 'allow', ts),
                  't': ts, 'm': 'react', 'tag': 'allow', 'cid': conf['id'], 'ck': conf['nonce']}
            r = session.get('https://steamcommunity.com/mobileconf/ajaxop', params=ap, timeout=15)
            print(f"  Accept: {r.text}")
            time.sleep(1)
    elif data.get('needauth'):
        print("\n✗ Still need auth - refresh token may be expired too")
except Exception as e:
    print(f"Error: {e}")
