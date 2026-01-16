"""
Trading Engine - основная логика P2P трейдинга.
Координирует все модули для автоматической торговли.
"""

import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from .steam_guard import SteamGuardManager
from .pulse_api import PulseAPI, BestDeal
from .dmarket_api import DMarketAPI
from .lootfarm import LootFarmBot
from .tradeit import TradeItBot


class Market(Enum):
    """Поддерживаемые маркеты"""
    DMARKET = "Dmarket"
    LOOTFARM = "LootFarm"
    TRADEIT = "TradeItTrade"


@dataclass
class Deal:
    """Структура сделки"""
    item_name: str
    source_market: str
    target_market: str
    buy_price: float
    sell_price: float
    spread_percent: float
    spread_usd: float
    item_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DealResult:
    """Результат выполнения сделки"""
    success: bool
    deal: Deal
    profit: float = 0.0
    error: Optional[str] = None
    buy_trade_id: Optional[str] = None
    sell_trade_id: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class TradingStats:
    """Статистика торговли"""
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_profit: float = 0.0
    total_volume: float = 0.0
    start_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    tokens_used: int = 0


class TradingEngine:
    """
    Основной движок P2P трейдинга.
    
    Координирует:
    - Поиск выгодных сделок через Pulse API
    - Покупку на одной площадке
    - Продажу на другой площадке
    - Автоподтверждение трейдов через Steam Guard
    """
    
    def __init__(
        self,
        steam_guard: SteamGuardManager,
        pulse: PulseAPI,
        dmarket: DMarketAPI,
        lootfarm: LootFarmBot,
        tradeit: TradeItBot,
        settings: Dict[str, Any]
    ):
        self.steam_guard = steam_guard
        self.pulse = pulse
        self.dmarket = dmarket
        self.lootfarm = lootfarm
        self.tradeit = tradeit
        self.settings = settings
        
        self.is_running = False
        self.is_paused = False
        self.stats = TradingStats()
        
        # Callbacks для уведомлений
        self._on_deal_found: Optional[Callable] = None
        self._on_deal_completed: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        
        # Настройки торговли
        self.min_price = settings.get('trading', {}).get('min_price', 0.50)
        self.max_price = settings.get('trading', {}).get('max_price', 3.00)
        self.min_spread = settings.get('trading', {}).get('min_spread_percent', 10)
        self.check_interval = settings.get('trading', {}).get('check_interval_seconds', 30)
        
    def set_callbacks(
        self,
        on_deal_found: Callable = None,
        on_deal_completed: Callable = None,
        on_error: Callable = None
    ):
        """Установка callback функций для уведомлений"""
        self._on_deal_found = on_deal_found
        self._on_deal_completed = on_deal_completed
        self._on_error = on_error

    async def get_all_balances(self) -> Dict[str, float]:
        """
        Получение балансов со всех площадок.
        
        Returns:
            {'dmarket': float, 'lootfarm': float, 'tradeit': float}
        """
        balances = {
            'dmarket': 0.0,
            'lootfarm': 0.0,
            'tradeit': 0.0,
            'total': 0.0
        }
        
        try:
            # DMarket
            dm_balance = await self.dmarket.get_balance()
            if dm_balance:
                balances['dmarket'] = dm_balance.get('usd', 0.0)
                
            # Loot.Farm
            balances['lootfarm'] = await self.lootfarm.get_balance()
            
            # TradeIt.gg
            balances['tradeit'] = await self.tradeit.get_balance()
            
            balances['total'] = sum([
                balances['dmarket'],
                balances['lootfarm'],
                balances['tradeit']
            ])
            
            logger.info(f"Balances: DMarket=${balances['dmarket']:.2f}, "
                       f"LootFarm=${balances['lootfarm']:.2f}, "
                       f"TradeIt=${balances['tradeit']:.2f}")
                       
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            
        return balances

    async def find_best_deal(self) -> Optional[Deal]:
        """
        Поиск лучшей сделки через Pulse API.
        Сравнивает ВСЕ комбинации площадок.
        
        Returns:
            Deal или None
        """
        
        # Все возможные комбинации
        combinations = [
            ('TradeItTrade', 'Dmarket'),
            ('TradeItTrade', 'LootFarm'),
            ('Dmarket', 'TradeItTrade'),
            ('Dmarket', 'LootFarm'),
            ('LootFarm', 'TradeItTrade'),
            ('LootFarm', 'Dmarket'),
        ]
        
        best_deal = None
        max_spread = self.min_spread
        
        for source, target in combinations:
            logger.info(f"Checking {source} -> {target}...")
            
            try:
                # Сравниваем через Pulse API
                results = await self.pulse.compare_tables(
                    first_market=source,
                    second_market=target,
                    min_price=self.min_price,
                    max_price=self.max_price,
                    take=20,
                    exclude_overstock=True
                )
                
                for result in results:
                    # Фильтры
                    if result.first_market.is_overstock:
                        continue
                    if result.second_market.is_overstock:
                        continue
                    if result.first_market.count <= 0:
                        continue
                    if result.spread_percent <= 0:
                        continue
                        
                    # Нашли лучший спред?
                    if result.spread_percent > max_spread:
                        max_spread = result.spread_percent
                        best_deal = Deal(
                            item_name=result.item_name,
                            source_market=source,
                            target_market=target,
                            buy_price=result.first_market.price_usd,
                            sell_price=result.second_market.price_usd,
                            spread_percent=result.spread_percent,
                            spread_usd=result.spread_usd
                        )
                        
            except Exception as e:
                logger.error(f"Error checking {source} -> {target}: {e}")
                continue
        
        if best_deal:
            logger.success(
                f"Best deal: {best_deal.item_name} "
                f"({best_deal.source_market} ${best_deal.buy_price:.2f} -> "
                f"{best_deal.target_market} ${best_deal.sell_price:.2f}, "
                f"+{best_deal.spread_percent:.1f}%)"
            )
            
            if self._on_deal_found:
                await self._on_deal_found(best_deal)
        else:
            logger.warning("No profitable deals found")
        
        return best_deal

    async def _buy_on_dmarket(self, item_name: str, max_price: float) -> Optional[str]:
        """Покупка на DMarket"""
        try:
            # Ищем предмет
            offers = await self.dmarket.search_item_by_name(item_name, limit=5)
            
            for offer in offers:
                if offer.price_usd <= max_price:
                    # Покупаем
                    tx_id = await self.dmarket.buy_item(offer.offer_id, offer.price_cents)
                    if tx_id:
                        logger.info(f"Bought on DMarket: {item_name} for ${offer.price_usd:.2f}")
                        return tx_id
                        
        except Exception as e:
            logger.error(f"Error buying on DMarket: {e}")
            
        return None

    async def _buy_on_lootfarm(self, item_name: str, max_price: float) -> Optional[str]:
        """Покупка/обмен на Loot.Farm"""
        try:
            # Проверяем наличие
            available = await self.lootfarm.check_item_availability(item_name)
            if not available:
                logger.warning(f"Item not available on Loot.Farm: {item_name}")
                return None
                
            # Создаем обмен (нужны свои предметы для обмена)
            # Пока возвращаем None - нужна реализация логики обмена
            logger.warning("Loot.Farm buy not fully implemented yet")
            return None
            
        except Exception as e:
            logger.error(f"Error buying on Loot.Farm: {e}")
            
        return None

    async def _buy_on_tradeit(self, item_name: str, max_price: float) -> Optional[str]:
        """Покупка на TradeIt.gg"""
        try:
            success = await self.tradeit.buy_item(item_name, max_price)
            if success:
                logger.info(f"Bought on TradeIt.gg: {item_name}")
                return "tradeit_purchase"
                
        except Exception as e:
            logger.error(f"Error buying on TradeIt.gg: {e}")
            
        return None

    async def _sell_on_dmarket(self, item_name: str, price: float) -> Optional[str]:
        """Продажа на DMarket"""
        try:
            # Получаем инвентарь
            inventory = await self.dmarket.get_inventory()
            
            for item in inventory:
                if item.title == item_name and item.tradable:
                    # Создаем оффер на продажу
                    price_cents = int(price * 100)
                    offer_id = await self.dmarket.create_sell_offer(item.asset_id, price_cents)
                    if offer_id:
                        logger.info(f"Listed on DMarket: {item_name} for ${price:.2f}")
                        return offer_id
                        
        except Exception as e:
            logger.error(f"Error selling on DMarket: {e}")
            
        return None

    async def _sell_on_lootfarm(self, item_name: str, price: float) -> Optional[str]:
        """Продажа/обмен на Loot.Farm"""
        try:
            # Создаем обмен
            trade_id = await self.lootfarm.create_trade(
                my_items=[item_name],
                bot_items=[]  # Получаем баланс
            )
            if trade_id:
                logger.info(f"Trade created on Loot.Farm: {item_name}")
                return trade_id
                
        except Exception as e:
            logger.error(f"Error selling on Loot.Farm: {e}")
            
        return None

    async def _sell_on_tradeit(self, item_name: str, price: float) -> Optional[str]:
        """Продажа на TradeIt.gg"""
        try:
            success = await self.tradeit.sell_item(item_name, price)
            if success:
                logger.info(f"Listed on TradeIt.gg: {item_name} for ${price:.2f}")
                return "tradeit_listing"
                
        except Exception as e:
            logger.error(f"Error selling on TradeIt.gg: {e}")
            
        return None

    async def execute_deal(self, deal: Deal) -> DealResult:
        """
        Выполнение сделки.
        
        1. Покупка на source площадке
        2. Ожидание подтверждения Steam Guard
        3. Ожидание появления в инвентаре
        4. Продажа на target площадке
        5. Ожидание подтверждения
        
        Args:
            deal: Сделка для выполнения
            
        Returns:
            DealResult
        """
        start_time = datetime.now()
        result = DealResult(success=False, deal=deal)
        
        try:
            logger.info(f"Executing deal: {deal.item_name}")
            
            # 1. Покупка на source площадке
            buy_trade_id = None
            
            if deal.source_market == Market.DMARKET.value or deal.source_market == 'Dmarket':
                buy_trade_id = await self._buy_on_dmarket(deal.item_name, deal.buy_price * 1.05)
            elif deal.source_market == Market.LOOTFARM.value or deal.source_market == 'LootFarm':
                buy_trade_id = await self._buy_on_lootfarm(deal.item_name, deal.buy_price * 1.05)
            elif deal.source_market == Market.TRADEIT.value or deal.source_market == 'TradeItTrade':
                buy_trade_id = await self._buy_on_tradeit(deal.item_name, deal.buy_price * 1.05)
                
            if not buy_trade_id:
                result.error = f"Failed to buy on {deal.source_market}"
                logger.error(result.error)
                return result
                
            result.buy_trade_id = buy_trade_id
            
            # 2. Ожидание и подтверждение Steam Guard
            logger.info("Waiting for Steam Guard confirmation...")
            await asyncio.sleep(5)
            
            accepted = await self.steam_guard.accept_all_confirmations()
            logger.info(f"Accepted {accepted} confirmations")
            
            # 3. Ожидание появления в инвентаре
            logger.info("Waiting for item to appear in inventory...")
            await asyncio.sleep(30)  # Steam может задерживать
            
            # 4. Продажа на target площадке
            sell_trade_id = None
            
            if deal.target_market == Market.DMARKET.value or deal.target_market == 'Dmarket':
                sell_trade_id = await self._sell_on_dmarket(deal.item_name, deal.sell_price * 0.95)
            elif deal.target_market == Market.LOOTFARM.value or deal.target_market == 'LootFarm':
                sell_trade_id = await self._sell_on_lootfarm(deal.item_name, deal.sell_price * 0.95)
            elif deal.target_market == Market.TRADEIT.value or deal.target_market == 'TradeItTrade':
                sell_trade_id = await self._sell_on_tradeit(deal.item_name, deal.sell_price * 0.95)
                
            if not sell_trade_id:
                result.error = f"Failed to sell on {deal.target_market}"
                logger.error(result.error)
                return result
                
            result.sell_trade_id = sell_trade_id
            
            # 5. Ожидание подтверждения продажи
            await asyncio.sleep(5)
            accepted = await self.steam_guard.accept_all_confirmations()
            
            # Успех!
            result.success = True
            result.profit = deal.spread_usd
            result.duration_seconds = (datetime.now() - start_time).total_seconds()
            
            # Обновляем статистику
            self.stats.total_trades += 1
            self.stats.successful_trades += 1
            self.stats.total_profit += result.profit
            self.stats.total_volume += deal.buy_price
            self.stats.last_trade_time = datetime.now()
            
            logger.info(f"Deal completed! Profit: ${result.profit:.2f} "
                       f"(+{deal.spread_percent:.1f}%) in {result.duration_seconds:.0f}s")
                       
            if self._on_deal_completed:
                await self._on_deal_completed(result)
                
        except Exception as e:
            result.error = str(e)
            self.stats.failed_trades += 1
            logger.error(f"Deal execution error: {e}")
            
            if self._on_error:
                await self._on_error(str(e))
                
        return result

    async def run_single_trade(self) -> Optional[DealResult]:
        """
        Выполнение одной торговой операции.
        
        Returns:
            DealResult или None
        """
        deal = await self.find_best_deal()
        
        if deal:
            return await self.execute_deal(deal)
            
        return None

    async def monitor_incoming_trades(self, interval: int = 10):
        """
        Мониторинг входящих трейд-офферов от площадок.
        Автоматически принимает трейды от известных ботов.
        """
        logger.info(f"Starting incoming trade monitor (interval: {interval}s)")
        
        # Известные боты площадок (можно расширить)
        known_bots = {
            'DMarket': [],  # SteamID ботов DMarket
            'LootFarm': [],  # SteamID ботов Loot.Farm
            'TradeIt': []   # SteamID ботов TradeIt
        }
        
        while self.is_running:
            try:
                # Проверяем подтверждения
                confirmations = await self.steam_guard.fetch_confirmations()
                
                for conf in confirmations:
                    # Автоматически подтверждаем все трейды
                    # (в продакшене можно добавить проверку creator_id)
                    logger.info(f"Auto-accepting: {conf.headline}")
                    await self.steam_guard.accept_confirmation(conf)
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error in trade monitor: {e}")
                
            await asyncio.sleep(interval)

    async def run_trading_loop(self):
        """
        Основной цикл торговли.
        Работает пока is_running = True.
        """
        self.is_running = True
        self.stats.start_time = datetime.now()
        
        logger.info("Starting trading loop...")
        
        # Запускаем мониторинг подтверждений в фоне
        confirmation_task = asyncio.create_task(
            self.monitor_incoming_trades(interval=5)
        )
        
        try:
            while self.is_running:
                if self.is_paused:
                    await asyncio.sleep(1)
                    continue
                    
                try:
                    # Ищем сделку
                    deal = await self.find_best_deal()
                    
                    if deal:
                        # Выполняем сделку
                        result = await self.execute_deal(deal)
                        
                        if not result.success:
                            logger.warning(f"Deal failed: {result.error}")
                            
                    # Обновляем счетчик токенов
                    self.stats.tokens_used = self.pulse.get_tokens_used()
                    
                except Exception as e:
                    logger.error(f"Error in trading loop: {e}")
                    
                # Ждем перед следующей итерацией
                await asyncio.sleep(self.check_interval)
                
        finally:
            confirmation_task.cancel()
            try:
                await confirmation_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Trading loop stopped")

    def start(self):
        """Запуск торговли"""
        self.is_running = True
        self.is_paused = False
        logger.info("Trading started")

    def stop(self):
        """Остановка торговли"""
        self.is_running = False
        logger.info("Trading stopped")

    def pause(self):
        """Пауза торговли"""
        self.is_paused = True
        logger.info("Trading paused")

    def resume(self):
        """Возобновление торговли"""
        self.is_paused = False
        logger.info("Trading resumed")

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики"""
        uptime = None
        if self.stats.start_time:
            uptime = (datetime.now() - self.stats.start_time).total_seconds()
            
        return {
            'total_trades': self.stats.total_trades,
            'successful_trades': self.stats.successful_trades,
            'failed_trades': self.stats.failed_trades,
            'total_profit': self.stats.total_profit,
            'total_volume': self.stats.total_volume,
            'avg_profit': self.stats.total_profit / max(1, self.stats.successful_trades),
            'success_rate': self.stats.successful_trades / max(1, self.stats.total_trades) * 100,
            'uptime_seconds': uptime,
            'tokens_used': self.stats.tokens_used,
            'is_running': self.is_running,
            'is_paused': self.is_paused
        }


# Тестирование
async def test_trading_engine():
    """Тест Trading Engine"""
    with open('config/settings.json', 'r') as f:
        settings = json.load(f)
    
    # Инициализация модулей
    steam_guard = SteamGuardManager(settings['steam']['mafile_path'])
    pulse = PulseAPI(settings['pulse']['api_key'])
    dmarket = DMarketAPI(
        settings['dmarket']['public_key'],
        settings['dmarket']['private_key']
    )
    lootfarm = LootFarmBot()
    tradeit = TradeItBot()
    
    # Создаем движок
    engine = TradingEngine(
        steam_guard=steam_guard,
        pulse=pulse,
        dmarket=dmarket,
        lootfarm=lootfarm,
        tradeit=tradeit,
        settings=settings
    )
    
    # Тест получения балансов
    print("Testing get_all_balances...")
    balances = await engine.get_all_balances()
    print(f"Balances: {balances}")
    
    # Тест поиска сделки
    print("\nTesting find_best_deal...")
    deal = await engine.find_best_deal()
    if deal:
        print(f"Found deal: {deal.item_name}")
        print(f"  Buy on {deal.source_market}: ${deal.buy_price:.2f}")
        print(f"  Sell on {deal.target_market}: ${deal.sell_price:.2f}")
        print(f"  Spread: +{deal.spread_percent:.1f}%")
    
    # Закрываем
    await pulse.close()
    await dmarket.close()
    await lootfarm.close()
    await tradeit.close()
    await steam_guard.close()


if __name__ == '__main__':
    asyncio.run(test_trading_engine())
