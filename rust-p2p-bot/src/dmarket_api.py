"""
DMarket API модуль для торговли скинами.
Использует Ed25519 подпись для аутентификации.
"""

import time
import json
import aiohttp
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder
from loguru import logger


@dataclass
class DMarketItem:
    """Предмет на DMarket"""
    item_id: str
    asset_id: str
    title: str
    price_usd: float
    price_cents: int
    image: str
    tradable: bool
    game_id: str


@dataclass
class DMarketOffer:
    """Оффер на маркете"""
    offer_id: str
    title: str
    price_usd: float
    price_cents: int
    amount: int
    game_id: str


class DMarketAPI:
    """
    Работа с DMarket Trading API.
    
    Документация: https://docs.dmarket.com/
    """
    
    BASE_URL = "https://api.dmarket.com"
    
    # Game IDs
    GAMES = {
        'rust': 'rust',
        'csgo': 'a8db',
        'dota2': '9a92',
        'tf2': 'tf2'
    }
    
    def __init__(self, public_key: str, private_key: str):
        """
        Инициализация API клиента.
        
        Args:
            public_key: Публичный ключ API
            private_key: Приватный ключ API (hex)
        """
        self.public_key = public_key
        self.private_key = private_key
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Создаем ключ подписи из приватного ключа
        # Приватный ключ DMarket = seed (32 bytes) + public (32 bytes) = 64 bytes hex = 128 chars
        private_bytes = bytes.fromhex(private_key[:64])  # Берем только seed часть
        self.signing_key = SigningKey(private_bytes)
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        """Закрытие сессии"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Подпись запроса по схеме Ed25519.
        
        Args:
            method: HTTP метод (GET, POST, etc.)
            path: Путь запроса (без домена)
            body: Тело запроса (для POST/PATCH)
            
        Returns:
            Заголовки с подписью
        """
        timestamp = str(int(time.time()))
        
        # Формируем строку для подписи
        string_to_sign = method + path + body + timestamp
        
        # Подписываем
        signed = self.signing_key.sign(string_to_sign.encode('utf-8'))
        signature = signed.signature.hex()
        
        return {
            'X-Api-Key': self.public_key,
            'X-Request-Sign': f'dmar ed25519 {signature}',
            'X-Sign-Date': timestamp,
            'Content-Type': 'application/json'
        }

    async def _request(self, method: str, path: str, body: dict = None) -> Optional[dict]:
        """
        Выполнение подписанного запроса.
        
        Args:
            method: HTTP метод
            path: Путь API
            body: Тело запроса
            
        Returns:
            JSON ответ или None
        """
        session = await self._get_session()
        body_str = json.dumps(body) if body else ""
        headers = self._sign_request(method, path, body_str)
        
        url = f"{self.BASE_URL}{path}"
        
        try:
            if method == 'GET':
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"DMarket API error: {resp.status} - {error}")
                        return None
                    return await resp.json()
                    
            elif method == 'POST':
                async with session.post(url, headers=headers, data=body_str, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status not in [200, 201]:
                        error = await resp.text()
                        logger.error(f"DMarket API error: {resp.status} - {error}")
                        return None
                    return await resp.json()
                    
            elif method == 'PATCH':
                async with session.patch(url, headers=headers, data=body_str, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"DMarket API error: {resp.status} - {error}")
                        return None
                    return await resp.json()
                    
            elif method == 'DELETE':
                async with session.delete(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"DMarket API error: {resp.status} - {error}")
                        return None
                    return await resp.json()
                    
        except Exception as e:
            logger.error(f"DMarket request error: {e}")
            return None

    async def get_balance(self) -> Optional[Dict[str, float]]:
        """
        Получение баланса аккаунта.
        
        Returns:
            {'usd': float, 'dmc': float} или None
        """
        data = await self._request('GET', '/account/v1/balance')
        
        if data:
            usd = float(data.get('usd', 0)) / 100  # Центы в доллары
            dmc = float(data.get('dmc', 0)) / 100
            logger.info(f"DMarket balance: ${usd:.2f} USD, {dmc:.2f} DMC")
            return {'usd': usd, 'dmc': dmc}
        return None

    async def get_inventory(self, game_id: str = "rust") -> List[DMarketItem]:
        """
        Получение инвентаря пользователя на DMarket.
        Использует /exchange/v1/user/items - правильный endpoint для купленных предметов.
        
        Args:
            game_id: ID игры (rust, csgo, dota2, tf2)
            
        Returns:
            Список предметов
        """
        # Используем exchange API - там видны купленные предметы
        path = f"/exchange/v1/user/items?gameId={game_id}&currency=USD&limit=100"
        data = await self._request('GET', path)
        
        items = []
        if data and 'objects' in data:
            for item in data['objects']:
                extra = item.get('extra', {})
                items.append(DMarketItem(
                    item_id=item.get('itemId', ''),
                    asset_id=extra.get('linkId', ''),  # linkId для некоторых операций
                    title=item.get('title', ''),
                    price_usd=float(item.get('price', {}).get('USD', 0)) / 100,
                    price_cents=int(item.get('price', {}).get('USD', 0)),
                    image=item.get('image', ''),
                    tradable=extra.get('tradable', False),
                    game_id=game_id
                ))
            logger.info(f"Found {len(items)} items in DMarket inventory")
        return items

    async def get_market_items(
        self,
        game_id: str = "rust",
        title: str = None,
        price_from: int = 0,
        price_to: int = 300,
        limit: int = 50
    ) -> List[DMarketOffer]:
        """
        Получение предметов с маркета.
        
        Args:
            game_id: ID игры
            title: Название предмета (поиск)
            price_from: Мин. цена в центах
            price_to: Макс. цена в центах
            limit: Лимит результатов
            
        Returns:
            Список офферов
        """
        path = f"/exchange/v1/market/items?gameId={game_id}&limit={limit}&currency=USD"
        path += f"&priceFrom={price_from}&priceTo={price_to}"
        
        if title:
            path += f"&title={title}"
            
        path += "&orderBy=price&orderDir=asc"
        
        data = await self._request('GET', path)
        
        offers = []
        if data and 'objects' in data:
            for item in data['objects']:
                offers.append(DMarketOffer(
                    offer_id=item.get('extra', {}).get('offerId', ''),
                    title=item.get('title', ''),
                    price_usd=float(item.get('price', {}).get('USD', 0)) / 100,
                    price_cents=int(item.get('price', {}).get('USD', 0)),
                    amount=item.get('amount', 1),
                    game_id=game_id
                ))
            logger.info(f"Found {len(offers)} market offers")
        return offers

    async def buy_item(self, offer_id: str, price_cents: int) -> Optional[str]:
        """
        Покупка предмета с маркета.
        
        Args:
            offer_id: ID оффера
            price_cents: Цена в центах
            
        Returns:
            ID транзакции или None
        """
        body = {
            "offers": [
                {
                    "offerId": offer_id,
                    "price": {
                        "amount": str(price_cents),
                        "currency": "USD"
                    }
                }
            ]
        }
        
        data = await self._request('PATCH', '/exchange/v1/offers-buy', body)
        
        if data:
            logger.info(f"Successfully bought item, offer_id: {offer_id}")
            return data.get('txId')
        return None

    async def create_sell_offer(
        self,
        asset_id: str,
        price_cents: int
    ) -> Optional[str]:
        """
        Создание оффера на продажу.
        
        Args:
            asset_id: ID ассета
            price_cents: Цена в центах
            
        Returns:
            ID оффера или None
        """
        body = {
            "Offers": [
                {
                    "AssetID": asset_id,
                    "Price": {
                        "Currency": "USD",
                        "Amount": str(price_cents)
                    }
                }
            ]
        }
        
        data = await self._request('POST', '/marketplace-api/v1/user-offers/create', body)
        
        if data and 'Result' in data:
            results = data['Result']
            if results and len(results) > 0:
                offer_id = results[0].get('CreateOffer', {}).get('OfferID')
                logger.info(f"Created sell offer: {offer_id}")
                return offer_id
        return None

    async def withdraw_to_steam(self, asset_ids: List[str]) -> Optional[str]:
        """
        Вывод предметов в Steam инвентарь.
        
        Args:
            asset_ids: Список itemId предметов (из /exchange/v1/user/items)
            
        Returns:
            transferId или None
        """
        import uuid
        
        # Формат DMarket API: {"assets": [{"id": "itemId"}], "requestId": "uuid"}
        body = {
            "assets": [{"id": asset_id} for asset_id in asset_ids],
            "requestId": str(uuid.uuid4())
        }
        
        data = await self._request('POST', '/exchange/v1/withdraw-assets', body)
        
        if data:
            transfer_id = data.get('transferId')
            logger.info(f"Withdraw initiated: {transfer_id}")
            return transfer_id
        return None

    async def deposit_from_steam(self, asset_ids: List[str]) -> Optional[str]:
        """
        Депозит предметов из Steam на DMarket.
        
        Args:
            asset_ids: Список Steam asset IDs
            
        Returns:
            ID операции или None
        """
        body = {
            "AssetID": asset_ids
        }
        
        data = await self._request('POST', '/marketplace-api/v1/deposit-assets', body)
        
        if data:
            operation_id = data.get('operationId')
            logger.info(f"Deposit initiated: {operation_id}")
            return operation_id
        return None

    async def get_user_offers(self, game_id: str = "rust") -> List[DMarketOffer]:
        """
        Получение активных офферов пользователя.
        
        Args:
            game_id: ID игры
            
        Returns:
            Список офферов
        """
        path = f"/marketplace-api/v1/user-offers?GameID={game_id}&Status=OfferStatusActive"
        data = await self._request('GET', path)
        
        offers = []
        if data and 'Items' in data:
            for item in data['Items']:
                offers.append(DMarketOffer(
                    offer_id=item.get('OfferID', ''),
                    title=item.get('Title', ''),
                    price_usd=float(item.get('Price', {}).get('USD', 0)) / 100,
                    price_cents=int(item.get('Price', {}).get('USD', 0)),
                    amount=1,
                    game_id=game_id
                ))
            logger.info(f"Found {len(offers)} active user offers")
        return offers

    async def cancel_offer(self, offer_id: str) -> bool:
        """
        Отмена оффера.
        
        Args:
            offer_id: ID оффера
            
        Returns:
            True если успешно
        """
        body = {
            "OfferID": [offer_id]
        }
        
        data = await self._request('DELETE', '/marketplace-api/v1/user-offers', body)
        return data is not None

    async def search_item_by_name(
        self,
        name: str,
        game_id: str = "rust",
        limit: int = 10
    ) -> List[DMarketOffer]:
        """
        Поиск предмета по названию.
        
        Args:
            name: Название предмета
            game_id: ID игры
            limit: Лимит результатов
            
        Returns:
            Список офферов
        """
        return await self.get_market_items(
            game_id=game_id,
            title=name,
            price_from=0,
            price_to=100000,  # $1000 max
            limit=limit
        )


# Тестирование
async def test_dmarket_api():
    """Тест DMarket API"""
    with open('config/settings.json', 'r') as f:
        settings = json.load(f)
    
    api = DMarketAPI(
        settings['dmarket']['public_key'],
        settings['dmarket']['private_key']
    )
    
    # Тест баланса
    print("Testing get_balance...")
    balance = await api.get_balance()
    if balance:
        print(f"Balance: ${balance['usd']:.2f} USD")
    
    # Тест инвентаря
    print("\nTesting get_inventory...")
    inventory = await api.get_inventory('rust')
    print(f"Inventory items: {len(inventory)}")
    for item in inventory[:3]:
        print(f"  - {item.title}: ${item.price_usd:.2f}")
    
    # Тест маркета
    print("\nTesting get_market_items...")
    offers = await api.get_market_items(
        game_id='rust',
        price_from=50,  # $0.50
        price_to=300,   # $3.00
        limit=10
    )
    print(f"Market offers: {len(offers)}")
    for offer in offers[:5]:
        print(f"  - {offer.title}: ${offer.price_usd:.2f}")
    
    await api.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_dmarket_api())
