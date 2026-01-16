"""Полная проверка статуса предмета и трейдов"""
import asyncio
import json
import aiohttp

async def main():
    with open('config/settings.json') as f:
        s = json.load(f)
    
    from src.dmarket_api import DMarketAPI
    from src.steam_guard import SteamGuardManager
    
    api = DMarketAPI(s['dmarket']['public_key'], s['dmarket']['private_key'])
    guard = SteamGuardManager('config/mafile.json')
    
    print("=" * 60)
    print("ПОЛНАЯ ПРОВЕРКА СТАТУСА")
    print("=" * 60)
    
    # 1. Баланс DMarket
    print("\n[1] DMarket Balance:")
    balance = await api.get_balance()
    if balance:
        print(f"    USD: ${balance['usd']:.2f}")
    
    # 2. Steam Guard код
    print("\n[2] Steam Guard:")
    code = guard.generate_code()
    print(f"    Current 2FA Code: {code}")
    print(f"    SteamID: {guard.steam_id}")
    
    # 3. Проверяем инвентарь DMarket (exchange API)
    print("\n[3] DMarket Inventory (exchange API):")
    path = "/exchange/v1/user/items?gameId=rust&currency=USD&limit=50"
    data = await api._request('GET', path)
    if data and 'objects' in data:
        items = data['objects']
        print(f"    Found {len(items)} items")
        for item in items:
            extra = item.get('extra', {})
            print(f"    - {item.get('title')}")
            print(f"      itemId: {item.get('itemId')}")
            print(f"      withdrawable: {extra.get('withdrawable')}")
            print(f"      inMarket: {extra.get('inMarket')}")
    else:
        print("    No items found")
    
    # 4. Проверяем marketplace inventory
    print("\n[4] DMarket Inventory (marketplace API):")
    for status in ['default', 'in_transfer', 'traded']:
        path = f"/marketplace-api/v1/user-inventory?GameID=rust&BasicFilters.InGameStatus={status}&Limit=20"
        data = await api._request('GET', path)
        if data and data.get('Items'):
            print(f"    Status '{status}': {len(data['Items'])} items")
            for item in data['Items'][:2]:
                print(f"      - {item.get('Title')} | AssetID: {item.get('AssetID')}")
    
    # 5. Проверяем историю операций
    print("\n[5] Recent Operations:")
    path = "/marketplace-api/v1/user-operations?Limit=10"
    data = await api._request('GET', path)
    if data and 'Items' in data:
        for op in data['Items'][:5]:
            print(f"    - {op.get('Type')}: {op.get('Title')} | Status: {op.get('Status')}")
    
    # 6. Проверяем активные трансферы
    print("\n[6] Active Transfers:")
    path = "/exchange/v1/user/transfers?limit=10"
    data = await api._request('GET', path)
    if data:
        transfers = data.get('objects', data.get('transfers', []))
        if transfers:
            for t in transfers:
                print(f"    - {t}")
        else:
            print(f"    Response: {json.dumps(data)[:200]}")
    
    # 7. Проверяем Steam инвентарь напрямую
    print("\n[7] Steam Inventory (Rust):")
    steam_id = guard.steam_id
    try:
        async with aiohttp.ClientSession() as session:
            # Rust App ID = 252490
            url = f"https://steamcommunity.com/inventory/{steam_id}/252490/2?l=english&count=50"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    inv_data = await resp.json()
                    assets = inv_data.get('assets', [])
                    descriptions = inv_data.get('descriptions', [])
                    print(f"    Found {len(assets)} Rust items in Steam")
                    
                    # Создаем словарь описаний
                    desc_map = {}
                    for d in descriptions:
                        key = f"{d.get('classid')}_{d.get('instanceid')}"
                        desc_map[key] = d.get('market_hash_name', d.get('name', 'Unknown'))
                    
                    for asset in assets[:5]:
                        key = f"{asset.get('classid')}_{asset.get('instanceid')}"
                        name = desc_map.get(key, 'Unknown')
                        print(f"      - {name} (assetid: {asset.get('assetid')})")
                else:
                    text = await resp.text()
                    print(f"    Error {resp.status}: {text[:100]}")
    except Exception as e:
        print(f"    Error: {e}")
    
    # 8. Проверяем подтверждения Steam
    print("\n[8] Steam Confirmations:")
    confirmations = await guard.fetch_confirmations()
    if confirmations:
        print(f"    Found {len(confirmations)} pending confirmations!")
        for conf in confirmations:
            print(f"    - {conf.headline} ({conf.type_name})")
            print(f"      ID: {conf.id}, Creator: {conf.creator_id}")
    else:
        print("    No confirmations (or need auth)")
    
    print("\n" + "=" * 60)
    
    await api.close()
    await guard.close()

if __name__ == '__main__':
    asyncio.run(main())
