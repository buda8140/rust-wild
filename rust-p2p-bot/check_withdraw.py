"""Проверка статуса вывода и Steam трейдов"""
import asyncio
import json

async def main():
    with open('config/settings.json') as f:
        s = json.load(f)
    
    from src.dmarket_api import DMarketAPI
    from src.steam_guard import SteamGuardManager
    
    # DMarket
    api = DMarketAPI(s['dmarket']['public_key'], s['dmarket']['private_key'])
    
    print("=== DMarket Status ===")
    balance = await api.get_balance()
    print(f"Balance: ${balance['usd']:.2f}")
    
    # Проверяем инвентарь
    items = await api.get_inventory('rust')
    print(f"Items in inventory: {len(items)}")
    for item in items:
        print(f"  - {item.title}: ${item.price_usd:.2f}")
    
    # Steam Guard - проверяем подтверждения
    print("\n=== Steam Guard Confirmations ===")
    sg = SteamGuardManager('config/mafile.json')
    
    # Генерируем код
    code = sg.generate_code()
    print(f"Current 2FA code: {code}")
    
    # Пробуем получить подтверждения
    confirmations = await sg.fetch_confirmations()
    if confirmations:
        print(f"Found {len(confirmations)} confirmations:")
        for conf in confirmations:
            print(f"  - {conf}")
    else:
        print("No confirmations found (or need Steam login)")
    
    await api.close()

asyncio.run(main())
