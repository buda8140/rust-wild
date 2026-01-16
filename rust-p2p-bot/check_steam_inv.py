"""
Проверка Steam инвентаря Rust (App ID: 252490).
"""
import json
import asyncio
import sys
import os
import aiohttp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.steam_guard import SteamGuardManager


async def get_rust_inventory(steam_id: str) -> list:
    """Получение Rust инвентаря через публичный API"""
    url = f"https://steamcommunity.com/inventory/{steam_id}/252490/2"
    params = {'l': 'english', 'count': 100}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, 
                               timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.json()
                items = []
                
                descriptions = {d['classid']: d for d in data.get('descriptions', [])}
                
                for asset in data.get('assets', []):
                    desc = descriptions.get(asset['classid'], {})
                    items.append({
                        'assetid': asset['assetid'],
                        'classid': asset['classid'],
                        'instanceid': asset.get('instanceid', '0'),
                        'name': desc.get('market_hash_name', desc.get('name', 'Unknown')),
                        'tradable': desc.get('tradable', 0) == 1,
                        'marketable': desc.get('marketable', 0) == 1
                    })
                
                return items
            elif resp.status == 403:
                print("Инвентарь приватный!")
                return []
            elif resp.status == 429:
                print("Rate limit! Подождите минуту.")
                return []
            else:
                print(f"Ошибка: {resp.status}")
                return []


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
    print("STEAM RUST INVENTORY")
    print("=" * 50)
    print(f"Account: {guard.account_name}")
    print(f"SteamID: {guard.steam_id}")
    print(f"2FA Code: {guard.generate_code()}")
    print("-" * 50)
    
    # Получаем инвентарь
    items = await get_rust_inventory(guard.steam_id)
    
    if items:
        print(f"\nНайдено предметов: {len(items)}\n")
        
        for item in items:
            tradable = "✓" if item['tradable'] else "✗"
            print(f"[{tradable}] {item['name']}")
            print(f"    AssetID: {item['assetid']}")
        
        # Проверяем Santa Chest Plate
        santa = next((i for i in items if 'Santa' in i['name']), None)
        if santa:
            print("\n" + "=" * 50)
            print("🎅 SANTA CHEST PLATE НАЙДЕН!")
            print(f"   AssetID: {santa['assetid']}")
            print(f"   Tradable: {'Да' if santa['tradable'] else 'Нет'}")
    else:
        print("\nИнвентарь пуст или недоступен")
    
    await guard.close()
    print("\n" + "=" * 50)


if __name__ == '__main__':
    asyncio.run(main())
