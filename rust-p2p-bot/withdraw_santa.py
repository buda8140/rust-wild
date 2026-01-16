"""Вывод Santa Chest Plate из DMarket в Steam"""
import asyncio
import json
import uuid

async def main():
    with open('config/settings.json') as f:
        s = json.load(f)
    
    from src.dmarket_api import DMarketAPI
    api = DMarketAPI(s['dmarket']['public_key'], s['dmarket']['private_key'])
    
    # Получаем инвентарь
    print("Getting inventory...")
    path = "/exchange/v1/user/items?gameId=rust&currency=USD&limit=50"
    data = await api._request('GET', path)
    
    if not data or 'objects' not in data:
        print("No items found")
        await api.close()
        return
    
    items = data.get('objects', [])
    print(f"Found {len(items)} items")
    
    for item in items:
        item_id = item.get('itemId')
        title = item.get('title')
        extra = item.get('extra', {})
        withdrawable = extra.get('withdrawable', False)
        inMarket = extra.get('inMarket', False)
        
        print(f"\n- {title}")
        print(f"  itemId: {item_id}")
        print(f"  withdrawable: {withdrawable}")
        print(f"  inMarket: {inMarket}")
        print(f"  extra: {json.dumps(extra, indent=4)}")
        
        if withdrawable and not inMarket:
            print(f"\n=== Withdrawing {title} ===")
            
            # Формат: {"assets": [{"id": "itemId"}], "requestId": "uuid"}
            body = {
                "assets": [{"id": item_id}],
                "requestId": str(uuid.uuid4())
            }
            
            result = await api._request('POST', '/exchange/v1/withdraw-assets', body)
            print(f"Result: {result}")
            
            if result:
                print(f"✓ Withdraw initiated!")
                print(f"  Transfer ID: {result.get('transferId')}")
            else:
                print(f"✗ Withdraw failed")
    
    await api.close()

asyncio.run(main())
