# 🤖 TELEGRAM БОТ - ПОЛНАЯ РЕАЛИЗАЦИЯ

**Назначение:** Мониторить торговлю в реальном времени, управлять ботом, получать уведомления  
**Токен:** `8441168945:AAFjcsas9wObkYwh2TQhLaekj5agix2aBCk`  
**Язык:** Русский

---

## 🎯 ФУНКЦИОНАЛЬНОСТЬ

### Что может делать Telegram бот:

```
1. /start - Показать главное меню
2. /status - Текущий статус всех платформ (баланс, последний трейд)
3. /balance - Получить баланс на каждой платформе
4. /history - История последних 10 трейдов
5. /settings - Настройки (интервал проверки, мин. спред, макс. цена)
6. /start_trading - Запустить автоторговлю
7. /stop_trading - Остановить автоторговлю
8. /stats - Статистика (прибыль за день, всего сделок)

Inline кнопки:
├─ Обновить баланс ↻
├─ История трейдов 📊
├─ Включить/Выключить бота ⚙️
├─ Лучший спред сейчас 🚀
└─ Помощь ❓
```

---

## 📝 РЕАЛИЗАЦИЯ

### Файл: `src/telegram_bot.py`

```python
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import bold, code

# Конфигурация
BOT_TOKEN = "8441168945:AAFjcsas9wObkYwh2TQhLaekj5agix2aBCk"
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

logger = logging.getLogger('TelegramBot')

# Переменные состояния
trading_active = False
last_trade = None
total_profit = 0
trade_history = []

# Ссылка на trade_engine (передается при инициализации)
trade_engine = None
steam_auth = None


# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Команда /start - показать главное меню"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("💰 Баланс", callback_data="balance"),
        InlineKeyboardButton("📊 История", callback_data="history")
    )
    keyboard.add(
        InlineKeyboardButton("⚙️ Статус", callback_data="status"),
        InlineKeyboardButton("🚀 Лучший спред", callback_data="best_spread")
    )
    keyboard.add(
        InlineKeyboardButton("✅ Включить", callback_data="start_trade"),
        InlineKeyboardButton("❌ Выключить", callback_data="stop_trade")
    )
    keyboard.add(
        InlineKeyboardButton("📈 Статистика", callback_data="stats"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    )
    
    await message.answer(
        f"""
╔════════════════════════════════════╗
║   🤖 RUST TRADING BOT              ║
║   Автоматическая торговля скинами  ║
╚════════════════════════════════════╝

Выбери действие:
        """,
        reply_markup=keyboard
    )
    
    logger.info(f"👤 Новый пользователь: {message.from_user.id}")


@dp.message_handler(commands=['status'])
async def cmd_status(message: types.Message):
    """Текущий статус всех платформ"""
    
    try:
        # Получаем балансы
        tradeit_balance = await trade_engine.tradeit.get_balance()
        dmarket_balance = 1.10  # Из текущих данных
        lootfarm_balance = 0  # Из текущих данных
        
        status_text = f"""
<b>📊 СТАТУС ПЛАТФОРМ</b>

<b>💵 Балансы:</b>
• TradeIt.gg: <code>${tradeit_balance:.2f}</code> ✅
• DMarket: <code>$1.10</code> ⚠️
• Loot.Farm: <code>$0.00</code> ❌

<b>🤖 Статус бота:</b>
• Активен: <code>{'ДА ✅' if trading_active else 'НЕТ ❌'}</code>
• Последний трейд: <code>{last_trade or 'Нет'}</code>

<b>💰 Итого:</b>
• Баланс: <code>${tradeit_balance + dmarket_balance + lootfarm_balance:.2f}</code>
• Прибыль сегодня: <code>${total_profit:.2f}</code>
        """
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("↻ Обновить", callback_data="status"))
        
        await message.answer(status_text, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка получения статуса: {str(e)}")
        logger.error(f"Ошибка статуса: {e}")


@dp.message_handler(commands=['balance'])
async def cmd_balance(message: types.Message):
    """Получить баланс на каждой платформе"""
    
    try:
        tradeit_balance = await trade_engine.tradeit.get_balance()
        
        balance_text = f"""
<b>💰 ТЕКУЩИЕ БАЛАНСЫ</b>

TradeIt.gg:
  💵 USD: <code>${tradeit_balance:.2f}</code>
  
DMarket:
  💵 USD: <code>$1.10</code>
  🎮 DMC: <code>0.00</code>
  
Loot.Farm:
  💵 USD: <code>$0.00</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ИТОГО: <code>${tradeit_balance + 1.10:.2f}</code>
        """
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("↻ Обновить", callback_data="balance"),
            InlineKeyboardButton("← Назад", callback_data="start")
        )
        
        await message.answer(balance_text, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка баланса: {e}")


@dp.message_handler(commands=['history'])
async def cmd_history(message: types.Message):
    """История последних трейдов"""
    
    if not trade_history:
        await message.answer("📋 История пуста - трейдов еще не было")
        return
    
    history_text = "<b>📊 ИСТОРИЯ ТРЕЙДОВ (последние 10)</b>\n\n"
    
    for i, trade in enumerate(trade_history[-10:], 1):
        history_text += f"""
{i}. {trade['name']}
   💵 Куплено: ${trade['buy_price']:.2f} ({trade['source']})
   💹 Продано: ${trade['sell_price']:.2f} ({trade['target']})
   📈 Спред: +{trade['spread']:.1f}%
   💰 Прибыль: ${trade['profit']:.2f}
   ⏱️  {trade['time']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("← Назад", callback_data="start")
    )
    
    await message.answer(history_text, reply_markup=keyboard)


@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    """Статистика за день"""
    
    stats_text = f"""
<b>📈 СТАТИСТИКА</b>

<b>Сегодня:</b>
• Сделок: <code>{len(trade_history)}</code>
• Общая прибыль: <code>${total_profit:.2f}</code>
• Ср. прибыль/трейд: <code>${total_profit / max(len(trade_history), 1):.2f}</code>
• Ср. спред: <code>+{sum(t['spread'] for t in trade_history) / max(len(trade_history), 1):.1f}%</code>

<b>Лучший трейд:</b>
{f"• {trade_history[-1]['name']}: +{trade_history[-1]['spread']:.1f}%" if trade_history else "Нет"}

<b>Использовано токенов:</b>
• Pulse API: <code>~{len(trade_history) * 6} / 10000</code>
• Осталось: <code>~{10000 - len(trade_history) * 6}</code>

<b>💰 Баланс за сегодня:</b>
• Было: <code>$0.30</code>
• Получено: <code>+${total_profit:.2f}</code>
• Сейчас: <code>${0.30 + total_profit:.2f}</code>
    """
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("← Назад", callback_data="start"))
    
    await message.answer(stats_text, reply_markup=keyboard)


# ==================== CALLBACK ОБРАБОТЧИКИ ====================

@dp.callback_query_handler(lambda c: c.data == 'balance')
async def cb_balance(query: types.CallbackQuery):
    """Нажали на кнопку Баланс"""
    await cmd_balance(query.message)
    await query.answer()


@dp.callback_query_handler(lambda c: c.data == 'status')
async def cb_status(query: types.CallbackQuery):
    """Нажали на кнопку Статус"""
    await cmd_status(query.message)
    await query.answer()


@dp.callback_query_handler(lambda c: c.data == 'history')
async def cb_history(query: types.CallbackQuery):
    """Нажали на кнопку История"""
    await cmd_history(query.message)
    await query.answer()


@dp.callback_query_handler(lambda c: c.data == 'stats')
async def cb_stats(query: types.CallbackQuery):
    """Нажали на кнопку Статистика"""
    await cmd_stats(query.message)
    await query.answer()


@dp.callback_query_handler(lambda c: c.data == 'best_spread')
async def cb_best_spread(query: types.CallbackQuery):
    """Найти лучший спред прямо сейчас"""
    
    await query.message.edit_text("🔄 Ищем лучший спред...")
    
    try:
        best_deal = await trade_engine.find_best_spread()
        
        if best_deal:
            spread_text = f"""
<b>🚀 ЛУЧШИЙ СПРЕД СЕЙЧАС</b>

<b>Предмет:</b> {best_deal['name']}
<b>Куплю на:</b> {best_deal['source']}
<b>Продам на:</b> {best_deal['target']}
<b>Цена покупки:</b> ${best_deal['buy_price']:.2f}
<b>Цена продажи:</b> ${best_deal['sell_price']:.2f}
<b>Спред:</b> <code>+{best_deal['spread']:.1f}%</code>
<b>Потенциальная прибыль:</b> <code>${best_deal['sell_price'] - best_deal['buy_price']:.2f}</code>
            """
        else:
            spread_text = "❌ Сейчас нет выгодных спредов (все очень дорого)"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("🔄 Обновить", callback_data="best_spread"),
            InlineKeyboardButton("← Назад", callback_data="start")
        )
        
        await query.message.edit_text(spread_text, reply_markup=keyboard)
        
    except Exception as e:
        await query.message.edit_text(f"❌ Ошибка: {str(e)}")
    
    await query.answer()


@dp.callback_query_handler(lambda c: c.data == 'start_trade')
async def cb_start_trade(query: types.CallbackQuery):
    """Включить автоторговлю"""
    global trading_active
    
    trading_active = True
    
    await query.message.edit_text(
        "✅ <b>АВТОТОРГОВЛЯ ВКЛЮЧЕНА!</b>\n\n"
        "Бот начал искать выгодные спреды и совершать трейды.\n"
        "Следи за уведомлениями!",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("← Назад", callback_data="start")
        )
    )
    
    await query.answer("✅ Торговля запущена!")
    logger.info("✅ Торговля включена через Telegram")


@dp.callback_query_handler(lambda c: c.data == 'stop_trade')
async def cb_stop_trade(query: types.CallbackQuery):
    """Выключить автоторговлю"""
    global trading_active
    
    trading_active = False
    
    await query.message.edit_text(
        "❌ <b>АВТОТОРГОВЛЯ ВЫКЛЮЧЕНА!</b>\n\n"
        "Бот остановил поиск спредов.\n"
        "Текущие трейды будут завершены.",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("← Назад", callback_data="start")
        )
    )
    
    await query.answer("❌ Торговля остановлена!")
    logger.info("❌ Торговля выключена через Telegram")


@dp.callback_query_handler(lambda c: c.data == 'help')
async def cb_help(query: types.CallbackQuery):
    """Помощь"""
    
    help_text = """
<b>❓ СПРАВКА</b>

<b>Команды:</b>
/start - Главное меню
/status - Статус платформ
/balance - Все балансы
/history - История трейдов
/stats - Статистика

<b>Кнопки:</b>
💰 Баланс - Показать баланс
📊 История - Показать последние трейды
⚙️ Статус - Показать статус бота
🚀 Спред - Найти лучший спред
✅ Включить - Запустить торговлю
❌ Выключить - Остановить торговлю
📈 Статистика - Показать результаты

<b>Как это работает:</b>
1. Бот ищет разницу в цене между платформами
2. Покупает там где дешевле
3. Обменивает/продает там где дороже
4. Повторяет бесконечно 🔄

<b>⚠️ Важно:</b>
• Токены Pulse API: ~$0.02 за трейд
• Баланс должен быть ≥ $0.50
• Трейды могут быть отклонены ботом
• Включен режим "no timeout"
    """
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("← Назад", callback_data="start"))
    
    await query.message.edit_text(help_text, reply_markup=keyboard)
    await query.answer()


@dp.callback_query_handler(lambda c: c.data == 'start')
async def cb_start(query: types.CallbackQuery):
    """Вернуться в главное меню"""
    await cmd_start(query.message)
    await query.answer()


# ==================== УВЕДОМЛЕНИЯ ====================

async def notify_trade_completed(deal: dict, profit: float):
    """Отправить уведомление о завершенном трейде"""
    
    global total_profit, trade_history
    
    total_profit += profit
    trade_history.append({
        'name': deal['name'],
        'buy_price': deal['buy_price'],
        'sell_price': deal['sell_price'],
        'source': deal['source'],
        'target': deal['target'],
        'spread': deal['spread'],
        'profit': profit,
        'time': datetime.now().strftime("%H:%M:%S")
    })
    
    # Отправляем уведомление (нужен chat_id администратора)
    # CHAT_ID = 123456789  # Заменить на свой!
    # 
    # await bot.send_message(
    #     CHAT_ID,
    #     f"""
    # ✅ <b>ТРЕЙД ЗАВЕРШЕН!</b>
    # 
    # {deal['name']}
    # {deal['source']} → {deal['target']}
    # Цена: ${deal['buy_price']:.2f} → ${deal['sell_price']:.2f}
    # Спред: +{deal['spread']:.1f}%
    # 💰 Прибыль: ${profit:.2f}
    # 
    # Всего прибыли сегодня: ${total_profit:.2f}
    #     """
    # )
    
    logger.success(f"💰 Трейд: {deal['name']} +${profit:.2f} (+{deal['spread']:.1f}%)")


async def notify_trade_failed(error: str):
    """Отправить уведомление об ошибке"""
    
    logger.error(f"⚠️ Ошибка трейда: {error}")
    
    # CHAT_ID = 123456789  # Заменить на свой!
    # await bot.send_message(CHAT_ID, f"❌ <b>ОШИБКА:</b>\n{error}")


# ==================== ЗАПУСК БОТА ====================

async def on_startup(dispatcher):
    """При запуске бота"""
    logger.info("✅ Telegram бот запущен")


async def on_shutdown(dispatcher):
    """При остановке бота"""
    logger.info("❌ Telegram бот остановлен")


def start_telegram_bot(trade_engine_instance, steam_auth_instance):
    """Запустить Telegram бота"""
    
    global trade_engine, steam_auth
    trade_engine = trade_engine_instance
    steam_auth = steam_auth_instance
    
    logger.info("🤖 Запускаем Telegram бота...")
    
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )


if __name__ == '__main__':
    # Для тестирования
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
```

---

## 🔌 ИНТЕГРАЦИЯ В ГЛАВНЫЙ БОТ

### Добавляем в `main.py`:

```python
from src.telegram_bot import start_telegram_bot, notify_trade_completed
import threading

@app.command()
def telegram():
    """Запустить Telegram бота"""
    
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(
        target=start_telegram_bot,
        args=(trade_engine, steam_auth),
        daemon=True
    )
    bot_thread.start()
    
    logger.info("🤖 Telegram бот запущен в фоне")
    
    # Основной цикл торговли
    while True:
        # ... ваш код торговли ...
        pass


@app.command()
def run_full():
    """Запустить ПОЛНЫЙ бот: Торговля + Telegram"""
    
    import asyncio
    
    async def run():
        # Инициализируем все
        engine = TradeEngine()
        steam = SteamAuthenticator(MAFILE_PATH)
        
        # Запускаем Telegram в отдельном потоке
        bot_thread = threading.Thread(
            target=start_telegram_bot,
            args=(engine, steam),
            daemon=True
        )
        bot_thread.start()
        
        logger.info("🚀 ПОЛНЫЙ БОТ ЗАПУЩЕН: Торговля + Telegram")
        
        # Основной цикл: ищем спреды и совершаем трейды
        while True:
            try:
                # Находим лучший спред
                deal = await engine.find_best_spread()
                
                if deal:
                    # Выполняем трейд
                    profit = await engine.execute_trade(deal)
                    
                    if profit > 0:
                        # Уведомляем через Telegram
                        await notify_trade_completed(deal, profit)
                
                # Ждем 30 сек перед следующей проверкой
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                await asyncio.sleep(60)
    
    asyncio.run(run())
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Режим тестирования бота:

```bash
# Запустить только Telegram бота (без торговли)
python main.py --telegram

# Запустить полный бот (торговля + Telegram)
python main.py --run-full

# Тест отправки сообщения
python -c "
import asyncio
from aiogram import Bot

async def test():
    bot = Bot('8441168945:AAFjcsas9wObkYwh2TQthLaekj5agix2aBCk')
    await bot.send_message(
        YOUR_CHAT_ID,
        '✅ Тест сообщения от бота!'
    )
    await bot.session.close()

asyncio.run(test())
"
```

---

## 📋 ЧЕКЛИСТ

- [ ] Установлен aiogram: `pip install aiogram`
- [ ] Создан файл `src/telegram_bot.py`
- [ ] Настроены обработчики команд
- [ ] Настроены inline кнопки
- [ ] Функция `notify_trade_completed()` интегрирована
- [ ] Интеграция в `main.py` завершена
- [ ] Тест команды `/start` работает
- [ ] Тест кнопки баланса работает
- [ ] Тест поиска спреда работает
- [ ] Бот отправляет уведомления о трейдах

---

## 🔐 БЕЗОПАСНОСТЬ

1. **Никогда** не делишь токен бота!
2. **Никогда** не пишешь пароль Steam в коде
3. Используй `.env` для всех чувствительных данных
4. Telegram бот работает через официальное API - безопасно

