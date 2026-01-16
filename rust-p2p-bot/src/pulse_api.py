"""
Pulse API модуль для анализа цен и поиска спреда.
https://api-pulse.tradeon.space

Правильные значения priceType:
- "Sell" - цена продажи на маркете (мы покупаем по этой цене)
- "Buy" - цена покупки на маркете (мы продаём по этой цене)
"""

import aiohttp
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger


@dataclass
class MarketPrice:
    """Цена на конкретном маркете"""
    market: str
    price: float
    price_usd: float
    count: int
    is_overstock: bool


@dataclass
class CompareResult:
    """Результат сравнения цен между маркетами"""
    item_name: str
    first_market: MarketPrice
    second_market: MarketPrice
    spread_percent: float
    spread_usd: float


@dataclass
class BestDeal:
    """Лучшая сделка"""
    item_name: str
    buy_market: str
    sell_market: str
    buy_price: float
    sell_price: float
    spread_percent: float
    spread_usd: float


class PulseAPI:
    """
    Работа с Pulse TradeOn API.
    
    Стоимость операций:
    - CompareTables: 2 токена
    - BaseInfo: 2 токена
    - AdvancedInfo: 2 токена
    - GetHistory: 7 токенов
    - CompareBestOffers: 3 токена
    """
    
    BASE_URL = "https://api-pulse.tradeon.space"
    
    # Поддерживаемые маркеты для Rust
    MARKETS = ['Dmarket', 'LootFarm', 'TradeItTrade', 'TradeItStore']
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.tokens_used = 0
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии"""
        if self._session is None or self._session.closed:
            headers = {
                'Api-Key': self.api_key,
                'Content-Type': 'application/json'
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
        
    async def close(self):
        """Закрытие сессии"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def compare_tables(
        self,
        first_market: str,
        second_market: str,
        game: str = "Rust",
        currency: str = "USD",
        min_price: float = 0.50,
        max_price: float = 5.00,
        skip: int = 0,
        take: int = 100,
        exclude_overstock: bool = True
    ) -> List[CompareResult]:
        """
        Сравнение цен между двумя площадками.
        Стоимость: 2 токена
        
        Логика:
        - firstMarket с priceType="Sell" = цена по которой мы ПОКУПАЕМ
        - secondMarket с priceType="Buy" = цена по которой мы ПРОДАЁМ
        
        Args:
            first_market: Маркет для покупки (Dmarket, LootFarm, TradeItTrade)
            second_market: Маркет для продажи
            game: Игра (Rust, CsGo, Dota2)
            currency: Валюта (USD, EUR, RUB)
            min_price: Минимальная цена покупки
            max_price: Максимальная цена покупки
            skip: Пропустить записей
            take: Взять записей
            exclude_overstock: Исключить overstock
            
        Returns:
            Список результатов сравнения, отсортированный по спреду
        """
        session = await self._get_session()
        
        payload = {
            "game": game,
            "currency": currency,
            "firstMarket": first_market,
            "secondMarket": second_market,
            "firstMarketOptions": {
                "firstMarketPriceType": "Sell",  # Цена продажи = мы покупаем
                "firstMarketPriceFilter": {
                    "minValue": min_price,
                    "maxValue": max_price
                }
            },
            "secondMarketOptions": {
                "secondMarketPriceType": "Buy"  # Цена покупки = мы продаём
            },
            "paginationRequest": {
                "skipCount": skip,
                "takeCount": take,
                "orderParameters": {
                    "key": "profitPercent",
                    "sortOrder": "Descending"
                }
            },
            "displaySoldOutItems": False
        }
        
        if exclude_overstock:
            payload["isOverstock"] = False
        
        try:
            url = f"{self.BASE_URL}/public-api/item/compare-tables"
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                self.tokens_used += 2
                
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Pulse API error: {resp.status} - {error_text}")
                    return []
                    
                data = await resp.json()
                
                if not isinstance(data, list):
                    logger.warning(f"Unexpected response type: {type(data)}")
                    return []
                
                results = []
                for item in data:
                    if not item:
                        continue
                    
                    # Проверка на None для firstMarketInfo
                    first_info = item.get('firstMarketInfo')
                    if first_info is None:
                        continue
                    
                    # Проверка на None для secondMarketInfo
                    second_info = item.get('secondMarketInfo')
                    if second_info is None:
                        continue
                    
                    buy_price = first_info.get('priceUsd', 0) or 0
                    sell_price = second_info.get('priceUsd', 0) or 0
                    
                    # Пропускаем если цены нулевые
                    if buy_price <= 0 or sell_price <= 0:
                        continue
                    
                    # Проверка overstock
                    first_overstock = first_info.get('overstockInfo') or {}
                    second_overstock = second_info.get('overstockInfo') or {}
                    
                    first_limit = first_overstock.get('limit', 999) or 999
                    first_count = first_overstock.get('currentCount', 0) or 0
                    second_limit = second_overstock.get('limit', 999) or 999
                    second_count = second_overstock.get('currentCount', 0) or 0
                    
                    first_is_overstock = first_count >= first_limit
                    second_is_overstock = second_count >= second_limit
                    
                    spread_usd = sell_price - buy_price
                    spread_percent = (spread_usd / buy_price) * 100 if buy_price > 0 else 0
                    
                    results.append(CompareResult(
                        item_name=item.get('marketHashName', ''),
                        first_market=MarketPrice(
                            market=first_market,
                            price=buy_price,
                            price_usd=buy_price,
                            count=first_info.get('bestOfferCount', 0) or 0,
                            is_overstock=first_is_overstock
                        ),
                        second_market=MarketPrice(
                            market=second_market,
                            price=sell_price,
                            price_usd=sell_price,
                            count=second_info.get('bestOfferCount', 0) or 0,
                            is_overstock=second_is_overstock
                        ),
                        spread_percent=spread_percent,
                        spread_usd=spread_usd
                    ))
                
                logger.info(f"Found {len(results)} items: {first_market} -> {second_market}")
                return results
                
        except Exception as e:
            logger.error(f"Error in compare_tables: {e}")
            return []

    async def get_best_spread_item(
        self,
        min_price: float = 0.50,
        max_price: float = 5.00,
        min_spread_percent: float = 10.0
    ) -> Optional[BestDeal]:
        """
        Находит предмет с наибольшим спредом среди ВСЕХ комбинаций площадок.
        
        Args:
            min_price: Минимальная цена покупки
            max_price: Максимальная цена покупки
            min_spread_percent: Минимальный спред в процентах
            
        Returns:
            Лучшая сделка или None
        """
        # Комбинации: откуда покупаем -> куда продаём
        market_pairs = [
            ('Dmarket', 'LootFarm'),
            ('Dmarket', 'TradeItTrade'),
            ('LootFarm', 'Dmarket'),
            ('LootFarm', 'TradeItTrade'),
            ('TradeItTrade', 'Dmarket'),
            ('TradeItTrade', 'LootFarm'),
        ]
        
        best_deal: Optional[BestDeal] = None
        best_spread = min_spread_percent
        
        for buy_market, sell_market in market_pairs:
            results = await self.compare_tables(
                first_market=buy_market,
                second_market=sell_market,
                min_price=min_price,
                max_price=max_price,
                take=20,
                exclude_overstock=True
            )
            
            for result in results:
                # Пропускаем если overstock на любом маркете
                if result.first_market.is_overstock or result.second_market.is_overstock:
                    continue
                    
                # Пропускаем если нет в наличии
                if result.first_market.count <= 0:
                    continue
                    
                # Только положительный спред
                if result.spread_percent <= 0:
                    continue
                    
                if result.spread_percent > best_spread:
                    best_spread = result.spread_percent
                    best_deal = BestDeal(
                        item_name=result.item_name,
                        buy_market=buy_market,
                        sell_market=sell_market,
                        buy_price=result.first_market.price_usd,
                        sell_price=result.second_market.price_usd,
                        spread_percent=result.spread_percent,
                        spread_usd=result.spread_usd
                    )
                    
        if best_deal:
            logger.info(f"Best deal: {best_deal.item_name} "
                       f"({best_deal.buy_market} ${best_deal.buy_price:.2f} -> "
                       f"{best_deal.sell_market} ${best_deal.sell_price:.2f}, "
                       f"+{best_deal.spread_percent:.1f}%)")
        else:
            logger.warning("No profitable deals found")
            
        return best_deal
    
    async def get_supported_markets(self) -> List[str]:
        """Получение списка поддерживаемых маркетов"""
        session = await self._get_session()
        try:
            url = f"{self.BASE_URL}/public-api/info/supported-markets"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('markets', [])
        except Exception as e:
            logger.error(f"Error getting supported markets: {e}")
        return []
    
    def get_tokens_used(self) -> int:
        """Получение количества использованных токенов"""
        return self.tokens_used
    
    def reset_tokens_counter(self):
        """Сброс счетчика токенов"""
        self.tokens_used = 0


# Тестирование модуля
async def test_pulse_api():
    """Тест Pulse API"""
    import json
    
    with open('config/settings.json', 'r') as f:
        settings = json.load(f)
    
    api = PulseAPI(settings['pulse']['api_key'])
    
    try:
        # Тест сравнения таблиц
        print("Testing compare_tables (Dmarket -> LootFarm)...")
        results = await api.compare_tables(
            first_market='Dmarket',
            second_market='LootFarm',
            min_price=0.50,
            max_price=5.00,
            take=10
        )
        
        print(f"Found {len(results)} items:")
        for r in results[:5]:
            print(f"  {r.item_name}: ${r.first_market.price_usd:.2f} -> ${r.second_market.price_usd:.2f} (+{r.spread_percent:.1f}%)")
        
        # Тест поиска лучшей сделки
        print("\nSearching for best deal across all markets...")
        best = await api.get_best_spread_item(min_price=0.50, max_price=5.00)
        
        if best:
            print(f"\nBest deal found:")
            print(f"  Item: {best.item_name}")
            print(f"  Buy on {best.buy_market}: ${best.buy_price:.2f}")
            print(f"  Sell on {best.sell_market}: ${best.sell_price:.2f}")
            print(f"  Spread: +{best.spread_percent:.1f}% (${best.spread_usd:.2f})")
        
        print(f"\nTokens used: {api.get_tokens_used()}")
        
    finally:
        await api.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_pulse_api())
