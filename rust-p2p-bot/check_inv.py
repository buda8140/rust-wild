"""Тест вывода предмета из DMarket в Steam"""
import asyncio
import json
import uuid

async def main():
    with open('config/settings.json') as f:
        s = json.load(f)
    
    from src.dmarket_api import DMarketAPI
    api = DMarketAPI(s['dmarket']['public_key'], s['dmarket']['private_key'])
    
    # Баланс
    balance = await api.get_balance()
    print(f"Balance: ${balance['usd']:.2f}")
    
    # Получаем предметы
    print("\n=== User Items ===")
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
        link_id = extra.get('linkId')
        withdrawable = extra.get('withdrawable', False)
        
        print(f"\n- {title}")
        print(f"  itemId: {item_id}")
        print(f"  linkId: {link_id}")
        print(f"  withdrawable: {withdrawable}")
        
        if withdrawable:
            print(f"\n=== Trying to withdraw {title} ===")
            
            # Согласно документации DMarket:
            # POST /exchange/v1/withdraw-assets
            # Body: {"assets": [{"id": "..."}], "requestId": "uuid"}
            
            session = await api._get_session()
            request_id = str(uuid.uuid4())
            
            # Пробуем разные форматы
            variants = [
                # Формат из документации
                {"assets": [{"id": item_id}], "requestId": request_id},
                {"assets": [{"id": link_id}], "requestId": request_id},
                # Альтернативные форматы
                {"assets": [{"itemId": item_id}], "requestId": request_id},
                {"assets": [{"assetId": item_id}], "requestId": request_id},
                {"assets": [item_id], "requestId": request_id},
                {"assets": [link_id], "requestId": request_id},
            ]
            
            for body in variants:
                body_str = json.dumps(body)
                headers = api._sign_request('POST', '/exchange/v1/withdraw-assets', body_str)
                
                async with session.post(
                    f"{api.BASE_URL}/exchange/v1/withdraw-assets",
                    headers=headers,
                    data=body_str
                ) as resp:
                    text = await resp.text()
                    status = resp.status
                    
                    if status == 200:
                        print(f"SUCCESS! Body: {json.dumps(body, indent=2)}")
                        print(f"Response: {text}")
                        await api.close()
                        return
                    else:
                        # Показываем только уникальные ошибки
                        key = list(body['assets'][0].keys())[0] if isinstance(body['assets'][0], dict) else 'string'
                        print(f"  {key}: {status} - {text[:100]}")
    
    await api.close()

asyncio.run(main())
