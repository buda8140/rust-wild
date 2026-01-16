import asyncio
import json

async def check():
    with open('config/settings.json') as f:
        s = json.load(f)
    
    from src.dmarket_api import DMarketAPI
    api = DMarketAPI(s['dmarket']['public_key'], s['dmarket']['private_key'])
    
    # Баланс
    balance = await api.get_balance()
    print(f"Balance: ${balance['usd']:.2f}")
    
    # Инвентарь
    print("\nInventory:")
    inv = await api.get_inventory('rust')
    print(f"Items: {len(inv)}")
    for item in inv:
        print(f"  - {item.title}: ${item.price_usd:.2f}")
    
    await api.close()

asyncio.run(check())
