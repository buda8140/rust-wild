"""
P2P Trading Bot для Rust скинов.
Автоматическая торговля между TradeIt.gg, DMarket и Loot.Farm.

Запуск:
    python main.py
    
Или с аргументами:
    python main.py --test        # Тестовый режим (без реальных сделок)
    python main.py --no-telegram # Без Telegram бота
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from loguru import logger

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/bot_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG"
)

# Импорт модулей
from src.steam_guard import SteamGuardManager
from src.pulse_api import PulseAPI
from src.dmarket_api import DMarketAPI
from src.lootfarm import LootFarmBot
from src.tradeit import TradeItBot
from src.trading_logic import TradingEngine
from src.telegram_bot import TradingTelegramBot, start_telegram_bot


class P2PTradingBot:
    """Главный класс бота"""
    
    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = config_path
        self.settings = self._load_settings()
        
        # Модули
        self.steam_guard: SteamGuardManager = None
        self.pulse: PulseAPI = None
        self.dmarket: DMarketAPI = None
        self.lootfarm: LootFarmBot = None
        self.tradeit: TradeItBot = None
        self.trading_engine: TradingEngine = None
        self.telegram_bot: TradingTelegramBot = None
        
        # Состояние
        self.is_running = False
        self.test_mode = False
        
    def _load_settings(self) -> dict:
        """Загрузка настроек"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    async def init_modules(self):
        """Инициализация всех модулей"""
        logger.info("Initializing modules...")
        
        # Steam Guard
        logger.info("Loading Steam Guard...")
        self.steam_guard = SteamGuardManager(
            self.settings['steam']['mafile_path']
        )
        
        # Тест генерации кода
        code = self.steam_guard.generate_code()
        logger.info(f"Steam Guard code: {code}")
        
        # Pulse API
        logger.info("Initializing Pulse API...")
        self.pulse = PulseAPI(
            self.settings['pulse']['api_key']
        )
        
        # DMarket API
        logger.info("Initializing DMarket API...")
        self.dmarket = DMarketAPI(
            self.settings['dmarket']['public_key'],
            self.settings['dmarket']['private_key']
        )
        
        # Loot.Farm
        logger.info("Initializing Loot.Farm bot...")
        self.lootfarm = LootFarmBot()
        
        # TradeIt.gg
        logger.info("Initializing TradeIt.gg bot...")
        self.tradeit = TradeItBot()
        
        # Trading Engine
        logger.info("Initializing Trading Engine...")
        self.trading_engine = TradingEngine(
            steam_guard=self.steam_guard,
            pulse=self.pulse,
            dmarket=self.dmarket,
            lootfarm=self.lootfarm,
            tradeit=self.tradeit,
            settings=self.settings
        )
        
        logger.info("All modules initialized!")
        
    async def init_telegram(self):
        """Инициализация Telegram бота"""
        logger.info("Initializing Telegram bot...")
        
        self.telegram_bot = TradingTelegramBot(
            token=self.settings['telegram']['bot_token'],
            trading_engine_instance=self.trading_engine
        )
        
        # Устанавливаем callbacks для уведомлений
        self.trading_engine.set_callbacks(
            on_deal_found=self._on_deal_found,
            on_deal_completed=self._on_deal_completed,
            on_error=self._on_error
        )
        
    async def _on_deal_found(self, deal):
        """Callback при нахождении сделки"""
        if self.telegram_bot and hasattr(self.telegram_bot, 'admin_chat_id') and self.telegram_bot.admin_chat_id:
            text = (
                f"🔍 <b>Найдена сделка!</b>\n\n"
                f"📦 {deal.item_name}\n"
                f"💵 Купить на {deal.source_market}: ${deal.buy_price:.2f}\n"
                f"💰 Продать на {deal.target_market}: ${deal.sell_price:.2f}\n"
                f"📈 Спред: +{deal.spread_percent:.1f}% (${deal.spread_usd:.2f})"
            )
            await self.telegram_bot.bot.send_message(
                chat_id=self.telegram_bot.admin_chat_id,
                text=text
            )
            
    async def _on_deal_completed(self, result):
        """Callback при завершении сделки"""
        if self.telegram_bot and hasattr(self.telegram_bot, 'send_trade_notification'):
            await self.telegram_bot.send_trade_notification(
                item_name=result.deal.item_name,
                buy_market=result.deal.source_market,
                buy_price=result.deal.buy_price,
                sell_market=result.deal.target_market,
                sell_price=result.deal.sell_price,
                profit=result.profit
            )
            
    async def _on_error(self, error: str):
        """Callback при ошибке"""
        if self.telegram_bot and hasattr(self.telegram_bot, 'admin_chat_id') and self.telegram_bot.admin_chat_id:
            text = f"⚠️ <b>Ошибка:</b>\n\n<code>{error}</code>"
            await self.telegram_bot.bot.send_message(
                chat_id=self.telegram_bot.admin_chat_id,
                text=text
            )
            
    async def test_connections(self):
        """Тестирование подключений"""
        logger.info("Testing connections...")
        
        # Тест Steam Guard
        logger.info("Testing Steam Guard...")
        code = self.steam_guard.generate_code()
        logger.info(f"  Steam Guard code: {code}")
        
        steam_time = await self.steam_guard.get_steam_time()
        logger.info(f"  Steam server time: {steam_time}")
        
        # Тест DMarket
        logger.info("Testing DMarket API...")
        balance = await self.dmarket.get_balance()
        if balance:
            logger.info(f"  DMarket balance: ${balance['usd']:.2f}")
        else:
            logger.warning("  DMarket: Failed to get balance")
            
        # Тест Pulse API
        logger.info("Testing Pulse API...")
        results = await self.pulse.compare_tables(
            first_market='Dmarket',
            second_market='LootFarm',
            min_price=0.50,
            max_price=3.00,
            take=5
        )
        logger.info(f"  Pulse API: Found {len(results)} items")
        
        # Тест Loot.Farm JSON API
        logger.info("Testing Loot.Farm prices...")
        prices = await self.lootfarm.fetch_prices()
        logger.info(f"  Loot.Farm: {len(prices)} items in price list")
        
        logger.info("Connection tests completed!")
        
    async def run_test_trade(self):
        """Запуск тестовой сделки (без реального исполнения)"""
        logger.info("Running test trade...")
        
        # Поиск лучшей сделки
        deal = await self.trading_engine.find_best_deal()
        
        if deal:
            logger.info(f"Test deal found:")
            logger.info(f"  Item: {deal.item_name}")
            logger.info(f"  Buy on {deal.source_market}: ${deal.buy_price:.2f}")
            logger.info(f"  Sell on {deal.target_market}: ${deal.sell_price:.2f}")
            logger.info(f"  Spread: +{deal.spread_percent:.1f}% (${deal.spread_usd:.2f})")
            
            if not self.test_mode:
                logger.info("Executing deal...")
                result = await self.trading_engine.execute_deal(deal)
                
                if result.success:
                    logger.info(f"Deal completed! Profit: ${result.profit:.2f}")
                else:
                    logger.error(f"Deal failed: {result.error}")
        else:
            logger.warning("No profitable deals found")
            
    async def run(self, with_telegram: bool = True):
        """Запуск бота"""
        self.is_running = True
        
        try:
            # Инициализация
            await self.init_modules()
            
            # Тест подключений
            await self.test_connections()
            
            if with_telegram:
                await self.init_telegram()
                
            # Запуск задач
            tasks = []
            
            # Trading loop
            if not self.test_mode:
                tasks.append(asyncio.create_task(
                    self.trading_engine.run_trading_loop()
                ))
                
            # Telegram bot
            if with_telegram and self.telegram_bot:
                tasks.append(asyncio.create_task(
                    self.telegram_bot.run()
                ))
                
            # Steam Guard monitor
            tasks.append(asyncio.create_task(
                self.steam_guard.monitor_confirmations(interval=5)
            ))
            
            logger.info("Bot is running! Press Ctrl+C to stop.")
            
            # Ждем завершения
            await asyncio.gather(*tasks)
            
        except asyncio.CancelledError:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise
        finally:
            await self.shutdown()
            
    async def shutdown(self):
        """Корректное завершение"""
        logger.info("Shutting down...")
        
        self.is_running = False
        
        if self.trading_engine:
            self.trading_engine.stop()
            
        if self.steam_guard:
            await self.steam_guard.close()
            
        if self.pulse:
            await self.pulse.close()
            
        if self.dmarket:
            await self.dmarket.close()
            
        if self.lootfarm:
            await self.lootfarm.close()
            
        if self.tradeit:
            await self.tradeit.close()
            
        logger.info("Shutdown complete")


def main():
    """Точка входа"""
    parser = argparse.ArgumentParser(description='P2P Trading Bot для Rust скинов')
    parser.add_argument('--test', action='store_true', help='Тестовый режим (без реальных сделок)')
    parser.add_argument('--no-telegram', action='store_true', help='Без Telegram бота')
    parser.add_argument('--test-trade', action='store_true', help='Запустить одну тестовую сделку')
    parser.add_argument('--test-connections', action='store_true', help='Только тест подключений')
    parser.add_argument('--telegram', action='store_true', help='Запустить только Telegram бота (для теста)')
    parser.add_argument('--run-full', action='store_true', help='Запустить полный бот (торговля + Telegram)')
    
    args = parser.parse_args()
    
    # Создаем папку для логов
    os.makedirs('logs', exist_ok=True)
    
    # Создаем бота
    bot = P2PTradingBot()
    bot.test_mode = args.test
    
    if args.test:
        logger.info("Running in TEST MODE - no real trades will be executed")
        
    # Запуск
    async def run_with_cleanup(coro):
        """Запуск с корректным закрытием сессий"""
        try:
            await bot.init_modules()
            await coro()
        finally:
            await bot.shutdown()
    
    try:
        if args.test_connections:
            asyncio.run(run_with_cleanup(bot.test_connections))
        elif args.test_trade:
            asyncio.run(run_with_cleanup(bot.run_test_trade))
        elif args.telegram:
            # Только Telegram бот для теста
            async def run_telegram_only():
                await bot.init_modules()
                telegram_bot = TradingTelegramBot(
                    token=bot.settings['telegram']['bot_token'],
                    trading_engine_instance=bot.trading_engine
                )
                logger.info("🤖 Telegram bot started! Send /start to your bot")
                await telegram_bot.run()
            asyncio.run(run_telegram_only())
        elif args.run_full:
            # Полный бот: торговля + Telegram
            asyncio.run(bot.run(with_telegram=True))
        else:
            asyncio.run(bot.run(with_telegram=not args.no_telegram))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
