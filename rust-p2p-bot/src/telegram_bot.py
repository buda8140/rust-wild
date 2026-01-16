"""
Telegram Bot для мониторинга и управления торговлей.
Отправляет уведомления о сделках, показывает балансы и статистику.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger


# Конфигурация
BOT_TOKEN = "8441168945:AAFjcsas9wObkYwh2TQhLaekj5agix2aBCk"

# Глобальные переменные
trading_engine = None
trade_history = []
total_profit = 0.0


class TradingTelegramBot:
    """Telegram бот для управления торговлей"""
    
    def __init__(self, token: str, trading_engine_instance):
        self.bot = Bot(token=token, parse_mode="HTML")
        self.dp = Dispatcher()
        self.trading_engine = trading_engine_instance
        self.admin_chat_id = None
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("Telegram bot initialized")
    
    def _register_handlers(self):
        """Регистрация всех обработчиков"""
        
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            """Команда /start"""
            self.admin_chat_id = message.chat.id
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
                    InlineKeyboardButton(text="📊 История", callback_data="history")
                ],
                [
                    InlineKeyboardButton(text="⚙️ Статус", callback_data="status"),
                    InlineKeyboardButton(text="🚀 Лучший спред", callback_data="best_spread")
                ],
                [
                    InlineKeyboardButton(text="✅ Включить", callback_data="start_trade"),
                    InlineKeyboardButton(text="❌ Выключить", callback_data="stop_trade")
                ],
                [
                    InlineKeyboardButton(text="📈 Статистика", callback_data="stats"),
                    InlineKeyboardButton(text="❓ Помощь", callback_data="help")
                ]
            ])
            
            await message.answer(
                "╔════════════════════════════════════╗\n"
                "║   🤖 RUST TRADING BOT              ║\n"
                "║   Автоматическая торговля скинами  ║\n"
                "╚════════════════════════════════════╝\n\n"
                "Выбери действие:",
                reply_markup=keyboard
            )
            
            logger.info(f"New user: {message.from_user.id}")
        
        @self.dp.message(Command("status"))
        async def cmd_status(message: types.Message):
            """Текущий статус"""
            try:
                balances = await self.trading_engine.get_all_balances()
                stats = self.trading_engine.get_stats()
                
                status_text = f"""
<b>📊 СТАТУС ПЛАТФОРМ</b>

<b>💵 Балансы:</b>
• TradeIt.gg: <code>${balances['tradeit']:.2f}</code>
• DMarket: <code>${balances['dmarket']:.2f}</code>
• Loot.Farm: <code>${balances['lootfarm']:.2f}</code>

<b>🤖 Статус бота:</b>
• Активен: <code>{'ДА ✅' if stats['is_running'] else 'НЕТ ❌'}</code>
• Пауза: <code>{'ДА ⏸️' if stats['is_paused'] else 'НЕТ ▶️'}</code>

<b>💰 Итого:</b>
• Баланс: <code>${balances['total']:.2f}</code>
• Прибыль: <code>${stats['total_profit']:.2f}</code>
• Сделок: <code>{stats['total_trades']}</code>
                """
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="↻ Обновить", callback_data="status")]
                ])
                
                await message.answer(status_text, reply_markup=keyboard)
                
            except Exception as e:
                await message.answer(f"❌ Ошибка: {str(e)}")
                logger.error(f"Status error: {e}")
        
        @self.dp.message(Command("balance"))
        async def cmd_balance(message: types.Message):
            """Получить балансы"""
            try:
                balances = await self.trading_engine.get_all_balances()
                
                balance_text = f"""
<b>💰 ТЕКУЩИЕ БАЛАНСЫ</b>

TradeIt.gg:
  💵 USD: <code>${balances['tradeit']:.2f}</code>
  
DMarket:
  💵 USD: <code>${balances['dmarket']:.2f}</code>
  
Loot.Farm:
  💵 USD: <code>${balances['lootfarm']:.2f}</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ИТОГО: <code>${balances['total']:.2f}</code>
                """
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="↻ Обновить", callback_data="balance"),
                        InlineKeyboardButton(text="← Назад", callback_data="start")
                    ]
                ])
                
                await message.answer(balance_text, reply_markup=keyboard)
                
            except Exception as e:
                await message.answer(f"❌ Ошибка: {str(e)}")
                logger.error(f"Balance error: {e}")
        
        @self.dp.message(Command("stats"))
        async def cmd_stats(message: types.Message):
            """Статистика"""
            stats = self.trading_engine.get_stats()
            
            uptime_str = "N/A"
            if stats['uptime_seconds']:
                hours = int(stats['uptime_seconds'] // 3600)
                minutes = int((stats['uptime_seconds'] % 3600) // 60)
                uptime_str = f"{hours}ч {minutes}м"
            
            stats_text = f"""
<b>📈 СТАТИСТИКА</b>

<b>Сегодня:</b>
• Сделок: <code>{stats['total_trades']}</code>
• Успешных: <code>{stats['successful_trades']}</code>
• Неудачных: <code>{stats['failed_trades']}</code>
• Успех: <code>{stats['success_rate']:.1f}%</code>

<b>Финансы:</b>
• Общая прибыль: <code>${stats['total_profit']:.2f}</code>
• Ср. прибыль/трейд: <code>${stats['avg_profit']:.2f}</code>
• Объем торгов: <code>${stats['total_volume']:.2f}</code>

<b>Использовано токенов:</b>
• Pulse API: <code>{stats['tokens_used']} / 10000</code>
• Осталось: <code>{10000 - stats['tokens_used']}</code>

<b>⏱️ Время работы:</b>
• Uptime: <code>{uptime_str}</code>
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data="start")]
            ])
            
            await message.answer(stats_text, reply_markup=keyboard)
        
        # Callback обработчики
        @self.dp.callback_query(lambda c: c.data == "balance")
        async def cb_balance(query: types.CallbackQuery):
            await cmd_balance(query.message)
            await query.answer()
        
        @self.dp.callback_query(lambda c: c.data == "status")
        async def cb_status(query: types.CallbackQuery):
            await cmd_status(query.message)
            await query.answer()
        
        @self.dp.callback_query(lambda c: c.data == "stats")
        async def cb_stats(query: types.CallbackQuery):
            await cmd_stats(query.message)
            await query.answer()
        
        @self.dp.callback_query(lambda c: c.data == "best_spread")
        async def cb_best_spread(query: types.CallbackQuery):
            await query.message.edit_text("🔄 Ищем лучший спред...")
            
            try:
                deal = await self.trading_engine.find_best_deal()
                
                if deal:
                    spread_text = f"""
<b>🚀 ЛУЧШИЙ СПРЕД СЕЙЧАС</b>

<b>Предмет:</b> {deal.item_name}
<b>Куплю на:</b> {deal.source_market}
<b>Продам на:</b> {deal.target_market}
<b>Цена покупки:</b> ${deal.buy_price:.2f}
<b>Цена продажи:</b> ${deal.sell_price:.2f}
<b>Спред:</b> <code>+{deal.spread_percent:.1f}%</code>
<b>Прибыль:</b> <code>${deal.spread_usd:.2f}</code>
                    """
                else:
                    spread_text = "❌ Сейчас нет выгодных спредов"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔄 Обновить", callback_data="best_spread"),
                        InlineKeyboardButton(text="← Назад", callback_data="start")
                    ]
                ])
                
                await query.message.edit_text(spread_text, reply_markup=keyboard)
                
            except Exception as e:
                await query.message.edit_text(f"❌ Ошибка: {str(e)}")
            
            await query.answer()
        
        @self.dp.callback_query(lambda c: c.data == "start_trade")
        async def cb_start_trade(query: types.CallbackQuery):
            self.trading_engine.start()
            
            await query.message.edit_text(
                "✅ <b>АВТОТОРГОВЛЯ ВКЛЮЧЕНА!</b>\n\n"
                "Бот начал искать выгодные спреды и совершать трейды.\n"
                "Следи за уведомлениями!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="← Назад", callback_data="start")]
                ])
            )
            
            await query.answer("✅ Торговля запущена!")
            logger.info("Trading started via Telegram")
        
        @self.dp.callback_query(lambda c: c.data == "stop_trade")
        async def cb_stop_trade(query: types.CallbackQuery):
            self.trading_engine.stop()
            
            await query.message.edit_text(
                "❌ <b>АВТОТОРГОВЛЯ ВЫКЛЮЧЕНА!</b>\n\n"
                "Бот остановил поиск спредов.\n"
                "Текущие трейды будут завершены.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="← Назад", callback_data="start")]
                ])
            )
            
            await query.answer("❌ Торговля остановлена!")
            logger.info("Trading stopped via Telegram")
        
        @self.dp.callback_query(lambda c: c.data == "help")
        async def cb_help(query: types.CallbackQuery):
            help_text = """
<b>❓ СПРАВКА</b>

<b>Команды:</b>
/start - Главное меню
/status - Статус платформ
/balance - Все балансы
/stats - Статистика

<b>Как это работает:</b>
1. Бот ищет разницу в цене между платформами
2. Покупает там где дешевле
3. Продает там где дороже
4. Повторяет бесконечно 🔄

<b>⚠️ Важно:</b>
• Токены Pulse API: ~6 за проверку
• Баланс должен быть ≥ $0.50
• Автоподтверждение трейдов включено
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="← Назад", callback_data="start")]
            ])
            
            await query.message.edit_text(help_text, reply_markup=keyboard)
            await query.answer()
        
        @self.dp.callback_query(lambda c: c.data == "start")
        async def cb_start(query: types.CallbackQuery):
            await cmd_start(query.message)
            await query.answer()
    
    async def send_trade_notification(
        self,
        item_name: str,
        buy_market: str,
        buy_price: float,
        sell_market: str,
        sell_price: float,
        profit: float
    ):
        """Отправить уведомление о завершенном трейде"""
        if not self.admin_chat_id:
            return
        
        text = f"""
✅ <b>ТРЕЙД ЗАВЕРШЕН!</b>

📦 {item_name}
💵 {buy_market}: ${buy_price:.2f}
💰 {sell_market}: ${sell_price:.2f}
📈 Спред: +{((sell_price / buy_price - 1) * 100):.1f}%
💸 Прибыль: <code>${profit:.2f}</code>

⏱️ {datetime.now().strftime("%H:%M:%S")}
        """
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=text
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    async def run(self):
        """Запуск бота"""
        logger.info("Starting Telegram bot...")
        await self.dp.start_polling(self.bot)


# Функция для запуска из main.py
async def start_telegram_bot(trading_engine_instance):
    """Запустить Telegram бота"""
    bot = TradingTelegramBot(BOT_TOKEN, trading_engine_instance)
    await bot.run()


if __name__ == '__main__':
    # Для тестирования
    print("Telegram bot module loaded")
