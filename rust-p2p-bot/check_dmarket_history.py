"""Проверка истории операций DMarket"""
import asyncio
import json

async def main():
    with open('config/settings.json') as f:
        s = json.load(f)
    
    from src.dmarket_api import DMarketAPI
    api = DMarketAPI(s['dmarket']['public_key'], s['dmarket']['private_key'])
    
    print("DMarket History Check")
    print("=" * 60)
    
    # 1. Баланс
    balance = await api.get_balance()
    print(f"\nBalance: ${balance['usd']:.2f}")
    
    # 2. История покупок (closed targets)
    print("\n[1] Closed Targets (purchases):")
    path = "/marketplace-api/v1/user-targets/closed?GameID=rust&Limit=10"
    data = await api._request('GET', path)
    if data:
        print(f"    Response keys: {list(data.keys())}")
        trades = data.get('Trades', data.get('Items', []))
        for t in trades[:5]:
            print(f"    - {t.get('Title', t.get('title', 'Unknown'))}")
            print(f"      Status: {t.get('Status', t.get('status', 'N/A'))}")
    
    # 3. История через exchange API
    print("\n[2] Exchange history:")
    path = "/exchange/v1/user/offers?gameId=rust&status=closed&limit=10"
    data = await api._request('GET', path)
    if data:
        print(f"    Response: {json.dumps(data)[:300]}")
    
    # 4. Проверяем все возможные endpoints для истории
    print("\n[3] Trying various history endpoints:")
    
    endpoints = [
        "/account/v1/operations?limit=10",
        "/exchange/v1/user/transactions?limit=10",
        "/marketplace-api/v1/user-offers/closed?GameID=rust&Limit=10",
    ]
    
    for ep in endpoints:
        data = await api._request('GET', ep)
        if data:
            print(f"\n    {ep}:")
            print(f"    Keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
            print(f"    Preview: {json.dumps(data)[:200]}")
    
    # 5. Проверяем withdraw статус
    print("\n[4] Looking for Santa Chest Plate withdraw:")
    
    # Попробуем найти через разные API
    path = "/exchange/v1/user/items?gameId=rust&currency=USD&limit=100&status=pending"
    data = await api._request('GET', path)
    if data:
        print(f"    Pending items: {json.dumps(data)[:300]}")
    
    await api.close()

if __name__ == '__main__':
    asyncio.run(main())
