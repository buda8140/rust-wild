"""
Проверка Steam инвентаря через авторизованную сессию.
Обходит rate limit используя cookies авторизации.
"""
import json
import asyncio
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.steam_guard import SteamGuardManager


async def main():
    # Загружаем настройки
    config_path = os.path.join(BASE_DIR, 'config/settings.json')
    with open(config_path, 'r') as f:
        settings = json.load(f)
    
    mafile_path = settings['steam']['mafile_path']
    if mafile_path.startswith('..'):
        mafile_path = os.path.normpath(os.path.join(BASE_DIR, mafile_path))
    
    guard = SteamGuardManager(mafile_path)
    
    print("=" * 50)
    print("STEAM RUST INVENTORY (Authorized)")
    print("=" * 50)
    print(f"Account: {guard.account_name}")
    print(f"SteamID: {guard.steam_id}")
    print(f"2FA Code: {guard.generate_code()}")
    print("-" * 50)
    
    # Получаем сессию с авторизацией
    session = await guard._get_session()
    
    # Rust App ID = 252490, Context = 2
    url = f"https://steamcommunity.com/inventory/{guard.steam_id}/252490/2"
    params = {'l': 'english', 'count': 100}
    
    headers = guard._get_headers()
    cookies = guard._get_cookies()
    
    print(f"\nЗапрос инвентаря...")
    print(f"URL: {url}")
    
    import aiohttp
    async with session.get(url, params=params, headers=headers, cookies=cookies,
                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
        print(f"Status: {resp.status}")
        
        if resp.status == 200:
            data = await resp.json()
            
            assets = data.get('assets', [])
            descriptions = data.get('descriptions', [])
            
            print(f"Assets: {len(assets)}")
            print(f"Descriptions: {len(descriptions)}")
            
            if assets:
                # Создаем map описаний
                desc_map = {}
                for d in descriptions:
                    desc_map[d['classid']] = {
                        'name': d.get('market_hash_name', d.get('name', 'Unknown')),
                        'tradable': d.get('tradable', 0) == 1,
                        'marketable': d.get('marketable', 0) == 1
                    }
                
                print("\n📦 ПРЕДМЕТЫ:")
                for asset in assets:
                    info = desc_map.get(asset['classid'], {'name': 'Unknown', 'tradable': False})
                    tradable = "✓" if info['tradable'] else "✗"
                    print(f"  [{tradable}] {info['name']}")
                    print(f"      AssetID: {asset['assetid']}")
                
                # Ищем Santa
                for asset in assets:
                    info = desc_map.get(asset['classid'], {})
                    if 'Santa' in info.get('name', ''):
                        print("\n" + "=" * 50)
                        print("🎅 SANTA CHEST PLATE НАЙДЕН!")
                        print(f"   AssetID: {asset['assetid']}")
                        print(f"   Tradable: {'Да' if info.get('tradable') else 'Нет'}")
            else:
                print("\nИнвентарь пуст")
                
        elif resp.status == 429:
            print("Rate limit! Ждём...")
            # Пробуем через 5 секунд
            await asyncio.sleep(5)
            async with session.get(url, params=params, headers=headers, cookies=cookies,
                                   timeout=aiohttp.ClientTimeout(total=30)) as resp2:
                print(f"Retry status: {resp2.status}")
                if resp2.status == 200:
                    data = await resp2.json()
                    print(f"Assets: {len(data.get('assets', []))}")
        else:
            text = await resp.text()
            print(f"Error: {text[:500]}")
    
    await guard.close()
    print("\n" + "=" * 50)


if __name__ == '__main__':
    asyncio.run(main())
