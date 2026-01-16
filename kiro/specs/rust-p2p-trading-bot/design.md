# P2P Trading Bot - Техническое проектирование

## Архитектура системы

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM BOT (UI)                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Баланс  │ │ Старт/  │ │Статис-  │ │Настрой- │ │  Логи   │           │
│  │         │ │ Стоп    │ │ тика    │ │   ки    │ │         │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
└───────┼──────────┼──────────┼──────────┼──────────┼─────────────────────┘
        │          │          │          │          │
        └──────────┴──────────┴──────────┴──────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      TRADING ENGINE (Core)                               │
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │   PULSE API      │    │  SPREAD ANALYZER │    │  TRADE EXECUTOR  │  │
│  │  (Анализ цен)    │───▶│  (Выбор сделки)  │───▶│  (Исполнение)    │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                           │              │
└───────────────────────────────────────────────────────────┼──────────────┘
                                                            │
        ┌───────────────────────────────────────────────────┼───────────┐
        │                                                   │           │
        ▼                       ▼                           ▼           │
┌───────────────┐    ┌───────────────┐    ┌───────────────┐            │
│   DMARKET     │    │   LOOT.FARM   │    │   TRADEIT.GG  │            │
│   (API)       │    │   (Selenium)  │    │   (Selenium)  │            │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘            │
        │                    │                    │                     │
        └────────────────────┴────────────────────┘                     │
                             │                                          │
                             ▼                                          │
┌─────────────────────────────────────────────────────────────────────────┐
│                      STEAM GUARD (Автоподтверждение)                     │
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  CODE GENERATOR  │    │ CONFIRMATION     │    │  TRADE ACCEPTOR  │  │
│  │  (shared_secret) │    │ FETCHER          │    │  (identity_secret)│  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Модуль 1: Steam Guard (steam_guard.py) ✅ РАБОТАЕТ!

### Описание
Автоматическое подтверждение трейдов и принятие трейд-офферов.
Использует токены из SDA maFile (AccessToken/RefreshToken).

### Ключевые функции

```python
class SteamGuardManager:
    """Управление Steam Guard для автоподтверждения трейдов"""
    
    def __init__(self, sda_mafile_path: str):
        """Загрузка данных из SDA maFile с токенами"""
        
    def generate_code(self) -> str:
        """Генерация 5-значного кода Steam Guard"""
        
    def generate_confirmation_key(self, tag: str, timestamp: int) -> str:
        """Генерация ключа подтверждения"""
        
    async def refresh_access_token(self) -> bool:
        """Обновление access token через refresh token"""
        
    async def accept_trade_offer(self, trade_offer_id: str) -> Optional[str]:
        """Принятие трейд-оффера по ID (из URL)"""
        
    async def fetch_confirmations(self) -> List[Confirmation]:
        """Получение списка ожидающих подтверждений"""
        
    async def accept_confirmation(self, confirmation: Confirmation) -> bool:
        """Подтверждение конкретного трейда"""
        
    async def accept_all_confirmations(self) -> int:
        """Подтверждение всех ожидающих трейдов"""
        
    async def monitor_confirmations(self, interval: int = 5):
        """Фоновый мониторинг и автоподтверждение"""
```

### Алгоритм генерации кода
```python
def generate_twofactor_code(shared_secret: bytes, timestamp: int) -> str:
    """
    1. timestamp // 30 -> получаем chunk
    2. HMAC-SHA1(shared_secret, chunk как big-endian 8 bytes)
    3. Извлекаем 4 байта по offset из последнего байта
    4. Конвертируем в 5-значный код из charset '23456789BCDFGHJKMNPQRTVWXY'
    """
```

### Алгоритм подтверждения
```python
def generate_confirmation_key(identity_secret: bytes, tag: str, timestamp: int) -> bytes:
    """
    1. data = timestamp (8 bytes big-endian) + tag.encode('ascii')
    2. HMAC-SHA1(identity_secret, data)
    3. Base64 encode результат
    
    Tags:
    - 'conf' - загрузка списка подтверждений
    - 'details' - детали трейда
    - 'allow' - подтвердить
    - 'cancel' - отменить
    """
```

### API Endpoints для подтверждений
```
GET https://steamcommunity.com/mobileconf/getlist
    ?p={device_id}
    &a={steam_id}
    &k={confirmation_key_base64}
    &t={timestamp}
    &m=android
    &tag=conf

GET https://steamcommunity.com/mobileconf/ajaxop
    ?op=allow (или cancel)
    &p={device_id}
    &a={steam_id}
    &k={confirmation_key_base64}
    &t={timestamp}
    &m=android
    &tag=allow
    &cid={confirmation_id}
    &ck={confirmation_nonce}
```

---

## Модуль 2: Pulse API (pulse_api.py)

### Описание
Интеграция с TradeOn Pulse для анализа цен и поиска спреда.

### Ключевые функции

```python
class PulseAPI:
    """Работа с Pulse TradeOn API"""
    
    BASE_URL = "https://api-pulse.tradeon.space"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.tokens_used = 0
        
    async def compare_tables(
        self,
        first_market: str,  # "Dmarket", "LootFarm", "TradeItTrade"
        second_market: str,
        game: str = "Rust",
        currency: str = "USD",
        min_price: float = 0.50,
        max_price: float = 3.00,
        skip: int = 0,
        take: int = 100
    ) -> List[CompareResult]:
        """
        Сравнение цен между двумя площадками
        Стоимость: 2 токена
        """
        
    async def get_best_spread_item(
        self,
        min_price: float = 0.50,
        max_price: float = 3.00
    ) -> Optional[BestDeal]:
        """
        Находит предмет с наибольшим спредом среди ВСЕХ комбинаций площадок
        """
        
    def calculate_spread(self, buy_price: float, sell_price: float) -> float:
        """Расчет спреда в процентах"""
        return ((sell_price - buy_price) / buy_price) * 100
```

### Структура запроса CompareTables
```json
{
    "game": "Rust",
    "currency": "USD",
    "firstMarket": "Dmarket",
    "secondMarket": "LootFarm",
    "firstMarketOptions": {
        "firstMarketPriceType": "Sell",
        "firstMarketPriceFilter": {
            "minValue": 0.50,
            "maxValue": 5.00
        }
    },
    "secondMarketOptions": {
        "secondMarketPriceType": "Buy"
    },
    "paginationRequest": {
        "skipCount": 0,
        "takeCount": 100,
        "orderParameters": {
            "key": "profitPercent",
            "sortOrder": "Descending"
        }
    },
    "displaySoldOutItems": false,
    "isOverstock": false
}
```

### Важно о priceType:
- `"Sell"` - цена продажи на маркете (мы ПОКУПАЕМ по этой цене)
- `"Buy"` - цена покупки на маркете (мы ПРОДАЁМ по этой цене)

Логика: firstMarket с Sell = откуда покупаем, secondMarket с Buy = куда продаём
```

### Маркеты для сравнения
- `Dmarket` - DMarket
- `LootFarm` - Loot.Farm
- `TradeItTrade` - TradeIt.gg (Trade режим)
- `TradeItStore` - TradeIt.gg (Store режим)

---

## Модуль 3: DMarket API (dmarket_api.py)

### Описание
Полная интеграция с DMarket Trading API.

### Аутентификация
```python
def sign_request(method: str, path: str, body: str, timestamp: int, private_key: str) -> str:
    """
    Подпись запроса по схеме Ed25519
    
    1. Формируем строку: METHOD + PATH + BODY + TIMESTAMP
    2. Подписываем NACL Ed25519
    3. Hex encode
    """
```

### Ключевые функции

```python
class DMarketAPI:
    """Работа с DMarket Trading API"""
    
    BASE_URL = "https://api.dmarket.com"
    
    def __init__(self, public_key: str, private_key: str):
        self.public_key = public_key
        self.private_key = private_key
        
    async def get_balance(self) -> dict:
        """GET /account/v1/balance"""
        
    async def get_inventory(self, game_id: str = "rust") -> List[Item]:
        """GET /marketplace-api/v1/user-inventory?GameID=Rust"""
        
    async def get_market_items(
        self,
        title: str = None,
        price_from: int = 0,
        price_to: int = 300,  # в центах
        limit: int = 50
    ) -> List[MarketItem]:
        """GET /exchange/v1/market/items"""
        
    async def buy_item(self, offer_id: str, price: int) -> dict:
        """PATCH /exchange/v1/offers-buy"""
        
    async def deposit_to_steam(self, asset_ids: List[str]) -> str:
        """POST /marketplace-api/v1/deposit-assets"""
        
    async def withdraw_to_steam(self, asset_ids: List[str]) -> str:
        """POST /exchange/v1/withdraw-assets"""
        
    async def create_sell_offer(self, asset_id: str, price: int) -> dict:
        """POST /marketplace-api/v1/user-offers/create"""
```

### Game IDs
- CS:GO: `a8db`
- Dota 2: `9a92`
- Rust: `rust`
- TF2: `tf2`

---

## Модуль 4: Loot.Farm (lootfarm.py)

### Описание
Веб-автоматизация через Playwright (нет публичного API для трейдов).

### JSON API для цен
```
GET https://loot.farm/fullpriceRUST.json

Ответ:
[
    {
        "name": "Item Name",
        "price": 1763,  // в центах
        "have": 0,      // количество у ботов
        "max": 4,       // лимит
        "rate": 1.17    // отношение к Steam
    },
    ...
]
```

### Веб-автоматизация

```python
class LootFarmBot:
    """Автоматизация Loot.Farm через Playwright"""
    
    def __init__(self, steam_session: dict):
        self.browser = None
        self.page = None
        
    async def login_via_steam(self):
        """Авторизация через Steam OpenID"""
        
    async def refresh_inventory(self):
        """Обновление инвентаря на сайте"""
        
    async def get_my_items(self) -> List[Item]:
        """Получение своих предметов"""
        
    async def get_bot_items(self, search: str = None) -> List[Item]:
        """Получение предметов ботов с фильтром"""
        
    async def create_trade(
        self,
        my_items: List[str],
        bot_items: List[str]
    ) -> str:
        """
        Создание обмена
        1. Выбрать свои предметы (левая панель)
        2. Выбрать предметы бота (правая панель)
        3. Нажать "Обменять"
        4. Вернуть trade_offer_id
        """
        
    async def check_item_availability(self, item_name: str) -> bool:
        """Проверка наличия у ботов через JSON API"""
```

### Селекторы (примерные)
```python
SELECTORS = {
    "my_inventory": ".user-inventory",
    "bot_inventory": ".bot-inventory",
    "search_input": "input[placeholder*='Поиск']",
    "item_card": ".item-card",
    "trade_button": "button:has-text('Обменять')",
    "balance": ".balance-value"
}
```

---

## Модуль 5: TradeIt.gg (tradeit.py)

### Описание
Веб-автоматизация через Playwright (нет публичного API).

### Веб-автоматизация

```python
class TradeItBot:
    """Автоматизация TradeIt.gg через Playwright"""
    
    def __init__(self, steam_session: dict):
        self.browser = None
        self.page = None
        
    async def login_via_steam(self):
        """Авторизация через Steam"""
        
    async def get_balance(self) -> float:
        """Получение баланса"""
        
    async def search_item(self, name: str) -> List[Item]:
        """Поиск предмета"""
        
    async def buy_item(self, item_id: str) -> bool:
        """Покупка предмета"""
        
    async def create_trade(
        self,
        my_items: List[str],
        their_items: List[str]
    ) -> str:
        """Создание обмена"""
        
    async def withdraw_to_steam(self, item_ids: List[str]) -> str:
        """Вывод в Steam"""
```

---

## Модуль 6: Trading Logic (trading_logic.py)

### Описание
Основная логика трейдинга - координация всех модулей.

```python
class TradingEngine:
    """Основной движок трейдинга"""
    
    def __init__(
        self,
        steam_guard: SteamGuardManager,
        pulse: PulseAPI,
        dmarket: DMarketAPI,
        lootfarm: LootFarmBot,
        tradeit: TradeItBot
    ):
        self.steam_guard = steam_guard
        self.pulse = pulse
        self.dmarket = dmarket
        self.lootfarm = lootfarm
        self.tradeit = tradeit
        self.is_running = False
        
    async def get_all_balances(self) -> dict:
        """Получение балансов со всех площадок"""
        
    async def find_best_deal(
        self,
        min_price: float = 0.50,
        max_price: float = 3.00
    ) -> Optional[Deal]:
        """
        Поиск лучшей сделки:
        1. Сравнить DMarket ↔ LootFarm
        2. Сравнить DMarket ↔ TradeIt
        3. Сравнить LootFarm ↔ TradeIt
        4. Выбрать с максимальным спредом
        5. Проверить наличие у ботов
        """
        
    async def execute_deal(self, deal: Deal) -> DealResult:
        """
        Исполнение сделки:
        1. Купить/обменять на source площадке
        2. Дождаться подтверждения Steam Guard
        3. Дождаться появления в инвентаре
        4. Продать/обменять на target площадке
        5. Дождаться подтверждения
        6. Вернуть результат
        """
        
    async def run_trading_loop(self):
        """Основной цикл трейдинга"""
        while self.is_running:
            deal = await self.find_best_deal()
            if deal:
                result = await self.execute_deal(deal)
                await self.notify_result(result)
            await asyncio.sleep(30)
```

### Структура Deal
```python
@dataclass
class Deal:
    item_name: str
    source_market: str      # откуда покупаем
    target_market: str      # куда продаем
    buy_price: float
    sell_price: float
    spread_percent: float
    item_id: str = None
```

---

## Модуль 7: Telegram Bot (telegram_bot.py)

### Описание
Управление ботом через Telegram с inline кнопками.

### Структура меню

```
🟢 Торговля запущена!
🔍 Бот ищет выгодные сделки...
📊 Уведомления о сделках будут приходить автоматически.

┌─────────────────────────────────┐
│     💰 БАЛАНС И РЕЖИМ           │
├─────────────────────────────────┤
│  ⏹ Остановить торговлю          │
├────────────────┬────────────────┤
│ 📊 Статистика  │ ⚙️ Настройки   │
├────────────────┼────────────────┤
│ 🔄 Авто 24/7   │ 🔃 Обновить    │
├────────────────┼────────────────┤
│ 📝 Логи        │ 🧪 Тест сделки │
├────────────────┼────────────────┤
│ 🎮 Steam       │ ❓ Помощь      │
├─────────────────────────────────┤
│     🔴 ВЫКЛЮЧИТЬ БОТА           │
└─────────────────────────────────┘
```

### Callback handlers
```python
CALLBACKS = {
    "balance": show_balance,
    "stop": stop_trading,
    "start": start_trading,
    "stats": show_statistics,
    "settings": show_settings,
    "auto_mode": toggle_auto_mode,
    "refresh": refresh_data,
    "logs": show_logs,
    "test_trade": run_test_trade,
    "steam": show_steam_info,
    "help": show_help,
    "shutdown": shutdown_bot
}
```

### Уведомления о сделках
```
✅ СДЕЛКА ЗАВЕРШЕНА!

📦 Предмет: Ace Door
💵 Купил на DMarket: $0.92
💰 Продал на LootFarm: $1.35
📈 Профит: $0.43 (+46.7%)

⏱ Время: 2 мин 34 сек
💼 Баланс: $28.43 → $28.86
```

---

## Конфигурация (config/settings.json)

```json
{
    "trading": {
        "min_price": 0.50,
        "max_price": 3.00,
        "min_spread_percent": 10,
        "check_interval_seconds": 30,
        "auto_mode": true
    },
    "steam": {
        "mafile_path": "config/mafile.json",
        "confirmation_check_interval": 5
    },
    "pulse": {
        "api_key": "btpx0x70uq4tqqouw82zsgo4th8bbvc2",
        "max_tokens_per_day": 500
    },
    "dmarket": {
        "public_key": "...",
        "private_key": "..."
    },
    "telegram": {
        "bot_token": "8441168945:AAFjcsas9wObkYwh2TQhLaekj5agix2aBCk",
        "admin_chat_id": null
    }
}
```

---

## Свойства корректности (для тестирования)

### P1: Генерация кода Steam Guard
- Код всегда 5 символов из charset '23456789BCDFGHJKMNPQRTVWXY'
- Код меняется каждые 30 секунд
- Один и тот же timestamp всегда дает один и тот же код

### P2: Расчет спреда
- spread = (sell - buy) / buy * 100
- Спред всегда положительный для прибыльных сделок
- Спред корректно учитывает комиссии площадок

### P3: Подтверждение трейдов
- Все трейды от известных ботов подтверждаются
- Подтверждение происходит в течение 30 секунд
- Логируются все подтвержденные трейды

### P4: Баланс
- Баланс после сделки = баланс до + профит - комиссии
- Баланс никогда не уходит в минус
- Все изменения баланса логируются

---

## Зависимости (requirements.txt)

```
steam>=1.4.4
requests>=2.28.0
aiohttp>=3.8.0
playwright>=1.40.0
python-telegram-bot>=20.0
pynacl>=1.5.0
python-dotenv>=1.0.0
asyncio>=3.4.3
```
