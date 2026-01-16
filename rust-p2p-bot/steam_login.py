"""
Авторизация в Steam для подтверждения трейдов.
Сохраняет cookies в файл для повторного использования.
"""
import asyncio
import json
import os
import time
import aiohttp
from src.steam_guard import SteamGuardManager

COOKIES_FILE = 'config/steam_cookies.json'

async def login_and_save_cookies(username: str, password: str):
    """Авторизация и сохранение cookies"""
    guard = SteamGuardManager('config/mafile.json')
    
    print(f"Logging in as {username}...")
    print(f"2FA Code: {guard.generate_code()}")
    
    # Используем steam библиотеку если доступна
    try:
        import sys
        sys.path.insert(0, '../steam-master')
        from steam.webauth import MobileWebAuth
        
        code = guard.generate_code()
        print(f"Using 2FA code: {code}")
        
        auth = MobileWebAuth(username, password)
        session = auth.login(twofactor_code=code)
        
        # Сохраняем cookies
        cookies = dict(session.cookies)
        cookies['_login_time'] = int(time.time())
        
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f, indent=2)
        
        print(f"Successfully logged in! Cookies saved to {COOKIES_FILE}")
        print(f"Cookies: {list(cookies.keys())}")
        
        return True
        
    except ImportError:
        print("steam library not available")
        print("Install it: pip install steam")
        return False
    except Exception as e:
        print(f"Login failed: {e}")
        return False

async def test_confirmations_with_cookies():
    """Тест получения подтверждений с сохранёнными cookies"""
    if not os.path.exists(COOKIES_FILE):
        print(f"No cookies file found: {COOKIES_FILE}")
        print("Run login first!")
        return
    
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    
    guard = SteamGuardManager('config/mafile.json')
    
    # Получаем время Steam
    timestamp = await guard.get_steam_time()
    conf_key = guard.generate_confirmation_key('conf', timestamp)
    
    params = {
        'p': guard.device_id,
        'a': guard.steam_id,
        'k': conf_key,
        't': timestamp,
        'm': 'android',
        'tag': 'conf'
    }
    
    print(f"Checking confirmations...")
    print(f"SteamID: {guard.steam_id}")
    print(f"Device: {guard.device_id}")
    
    async with aiohttp.ClientSession(cookies=cookies) as session:
        url = 'https://steamcommunity.com/mobileconf/getlist'
        
        async with session.get(url, params=params) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if data.get('success'):
                confs = data.get('conf', [])
                print(f"\nFound {len(confs)} confirmations!")
                for conf in confs:
                    print(f"  - {conf.get('headline')} ({conf.get('type_name')})")
            elif data.get('needauth'):
                print("\nCookies expired or invalid. Need to login again.")
    
    await guard.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) >= 3:
        # Login mode: python steam_login.py username password
        username = sys.argv[1]
        password = sys.argv[2]
        asyncio.run(login_and_save_cookies(username, password))
    else:
        # Test mode: python steam_login.py
        asyncio.run(test_confirmations_with_cookies())
