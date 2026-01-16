"""
Принятие трейд-оффера по ссылке.
"""
import json
import time
import requests
import re

# Загружаем токен
with open('../SDA.1.0.15/maFiles/76561199113719186.maFile', 'r') as f:
    mafile = json.load(f)

STEAM_ID = str(mafile['Session']['SteamID'])
ACCESS_TOKEN = mafile['Session']['AccessToken']

print(f"Account: {mafile['account_name']}")

# ID трейда из ссылки
TRADE_OFFER_ID = "8781872705"

# Создаем сессию с авторизацией
session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Устанавливаем cookies авторизации
for domain in ['steamcommunity.com', 'store.steampowered.com']:
    session.cookies.set('steamLoginSecure', f"{STEAM_ID}%7C%7C{ACCESS_TOKEN}", domain=domain)

# Сначала получаем sessionid
print("\nGetting session...")
resp = session.get('https://steamcommunity.com/', timeout=15)
session_id = session.cookies.get('sessionid', domain='steamcommunity.com')

if not session_id:
    # Генерируем
    import secrets
    session_id = secrets.token_hex(12)
    session.cookies.set('sessionid', session_id, domain='steamcommunity.com')

print(f"Session ID: {session_id}")

# Открываем страницу трейда
print(f"\nOpening trade offer {TRADE_OFFER_ID}...")
trade_url = f"https://steamcommunity.com/tradeoffer/{TRADE_OFFER_ID}/"
trade_resp = session.get(trade_url, timeout=15)
print(f"Status: {trade_resp.status_code}")

# Проверяем что мы авторизованы
if 'g_steamID' in trade_resp.text:
    steam_id_match = re.search(r'g_steamID\s*=\s*"(\d+)"', trade_resp.text)
    if steam_id_match:
        print(f"Logged in as: {steam_id_match.group(1)}")

# Ищем partner ID
partner_match = re.search(r'g_ulTradePartnerSteamID\s*=\s*[\'"]?(\d+)[\'"]?', trade_resp.text)
partner_id = partner_match.group(1) if partner_match else None
print(f"Partner ID: {partner_id}")

# Принимаем трейд
print(f"\nAccepting trade...")
accept_url = f"https://steamcommunity.com/tradeoffer/{TRADE_OFFER_ID}/accept"

accept_data = {
    'sessionid': session_id,
    'serverid': '1',
    'tradeofferid': TRADE_OFFER_ID,
    'partner': partner_id or '',
    'captcha': ''
}

headers = {
    'Referer': trade_url,
    'Origin': 'https://steamcommunity.com',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest'
}

accept_resp = session.post(accept_url, data=accept_data, headers=headers, timeout=15)
print(f"Accept status: {accept_resp.status_code}")
print(f"Response: {accept_resp.text}")

try:
    result = accept_resp.json()
    if result.get('tradeid'):
        print(f"\n✓ Trade accepted! Trade ID: {result['tradeid']}")
    elif result.get('needs_mobile_confirmation'):
        print(f"\n! Trade needs mobile confirmation")
    elif result.get('strError'):
        print(f"\n✗ Error: {result['strError']}")
    else:
        print(f"\nResult: {result}")
except:
    pass
