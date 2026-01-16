"""
Loot.Farm модуль для торговли скинами.
Использует Playwright для веб-автоматизации + JSON API для цен.
"""

import json
import asyncio
import aiohttp
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from loguru import logger


@dataclass
class LootFarmItem:
    """Предмет на Loot.Farm"""
    name: str
    price_cents: int
    price_usd: float
    have: int  # Количество у ботов
    max_count: int  # Лимит
    rate: float  # Отношение к Steam цене
    is_overstock: bool


class LootFarmBot:
    """
    Автоматизация Loot.Farm через Playwright.
    
    Loot.Farm не имеет публичного API для трейдов,
    поэтому используем веб-автоматизацию.
    """
    
    BASE_URL = "https://loot.farm"
    TRADE_URL = "https://loot.farm/ru/index.html"  # Главная страница для торговли
    PRICES_URL = "https://loot.farm/fullpriceRUST.json"
    
    def __init__(self, steam_cookies: Dict[str, str] = None):
        """
        Инициализация бота.
        
        Args:
            steam_cookies: Куки Steam сессии для авторизации
        """
        self.steam_cookies = steam_cookies or {}
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._prices_cache: Dict[str, LootFarmItem] = {}
        self._prices_cache_time: float = 0
        
    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии для JSON API"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def init_browser(self, headless: bool = True):
        """
        Инициализация браузера.
        
        Args:
            headless: Запуск без GUI
        """
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = await self.context.new_page()
        logger.info("Browser initialized for Loot.Farm")

    async def close(self):
        """Закрытие браузера и сессий"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        logger.info("Loot.Farm bot closed")

    async def fetch_prices(self, force_refresh: bool = False) -> Dict[str, LootFarmItem]:
        """
        Получение цен через JSON API.
        Кэширует результат на 5 минут.
        
        Args:
            force_refresh: Принудительное обновление
            
        Returns:
            Словарь {название: LootFarmItem}
        """
        import time
        
        # Проверяем кэш (5 минут)
        if not force_refresh and self._prices_cache and (time.time() - self._prices_cache_time < 300):
            return self._prices_cache
            
        session = await self._get_http_session()
        
        try:
            async with session.get(self.PRICES_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch Loot.Farm prices: {resp.status}")
                    return self._prices_cache
                    
                data = await resp.json()
                
                self._prices_cache = {}
                for item in data:
                    name = item.get('name', '')
                    price = item.get('price', 0)
                    have = item.get('have', 0)
                    max_count = item.get('max', 0)
                    rate = item.get('rate', 1.0)
                    
                    self._prices_cache[name] = LootFarmItem(
                        name=name,
                        price_cents=price,
                        price_usd=price / 100,
                        have=have,
                        max_count=max_count,
                        rate=rate,
                        is_overstock=have >= max_count if max_count > 0 else False
                    )
                
                self._prices_cache_time = time.time()
                logger.info(f"Fetched {len(self._prices_cache)} Loot.Farm prices")
                return self._prices_cache
                
        except Exception as e:
            logger.error(f"Error fetching Loot.Farm prices: {e}")
            return self._prices_cache

    async def get_item_price(self, item_name: str) -> Optional[LootFarmItem]:
        """
        Получение цены конкретного предмета.
        
        Args:
            item_name: Название предмета
            
        Returns:
            LootFarmItem или None
        """
        prices = await self.fetch_prices()
        return prices.get(item_name)

    async def check_item_availability(self, item_name: str) -> bool:
        """
        Проверка наличия предмета у ботов.
        
        Args:
            item_name: Название предмета
            
        Returns:
            True если есть в наличии и не overstock
        """
        item = await self.get_item_price(item_name)
        if item:
            return item.have > 0 and not item.is_overstock
        return False

    async def login_via_steam(self, username: str, password: str, shared_secret: str):
        """
        Авторизация через Steam.
        
        Args:
            username: Логин Steam
            password: Пароль Steam
            shared_secret: Секрет для 2FA
        """
        if not self.page:
            await self.init_browser()
            
        try:
            # Переходим на Loot.Farm
            await self.page.goto(f"{self.BASE_URL}/ru/index.html", wait_until='networkidle')
            await asyncio.sleep(2)
            
            # Ищем кнопку входа через Steam
            login_btn = await self.page.query_selector('a[href*="steam"], button:has-text("Steam")')
            if login_btn:
                await login_btn.click()
                await asyncio.sleep(3)
                
            # Проверяем, перешли ли на Steam
            if 'steamcommunity.com' in self.page.url:
                # Вводим логин
                username_input = await self.page.query_selector('input[name="username"]')
                if username_input:
                    await username_input.fill(username)
                    
                password_input = await self.page.query_selector('input[name="password"]')
                if password_input:
                    await password_input.fill(password)
                    
                # Нажимаем войти
                submit_btn = await self.page.query_selector('button[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(3)
                    
                # Если нужен 2FA код
                code_input = await self.page.query_selector('input[name="twofactorcode"]')
                if code_input:
                    from .steam_guard import SteamGuardManager
                    # Генерируем код
                    guard = SteamGuardManager('config/mafile.json')
                    code = guard.generate_code()
                    await code_input.fill(code)
                    
                    submit_btn = await self.page.query_selector('button[type="submit"]')
                    if submit_btn:
                        await submit_btn.click()
                        await asyncio.sleep(3)
                        
            logger.info("Logged in to Loot.Farm via Steam")
            
        except Exception as e:
            logger.error(f"Error logging in to Loot.Farm: {e}")

    async def get_balance(self) -> float:
        """
        Получение баланса на Loot.Farm.
        
        Returns:
            Баланс в USD
        """
        if not self.page:
            return 0.0
            
        try:
            # Ищем элемент с балансом
            balance_el = await self.page.query_selector('.balance, .user-balance, [class*="balance"]')
            if balance_el:
                text = await balance_el.inner_text()
                # Парсим число из текста
                import re
                match = re.search(r'[\d.]+', text.replace(',', '.'))
                if match:
                    return float(match.group())
        except Exception as e:
            logger.error(f"Error getting Loot.Farm balance: {e}")
            
        return 0.0

    async def get_my_inventory(self) -> List[Dict[str, Any]]:
        """
        Получение своего инвентаря на сайте.
        
        Returns:
            Список предметов
        """
        if not self.page:
            return []
            
        items = []
        try:
            # Обновляем инвентарь
            refresh_btn = await self.page.query_selector('button:has-text("Обновить"), .refresh-inventory')
            if refresh_btn:
                await refresh_btn.click()
                await asyncio.sleep(3)
                
            # Получаем предметы
            item_elements = await self.page.query_selector_all('.user-inventory .item, .my-items .item-card')
            
            for el in item_elements:
                name_el = await el.query_selector('.item-name, .name')
                price_el = await el.query_selector('.item-price, .price')
                
                if name_el and price_el:
                    name = await name_el.inner_text()
                    price_text = await price_el.inner_text()
                    
                    import re
                    price_match = re.search(r'[\d.]+', price_text.replace(',', '.'))
                    price = float(price_match.group()) if price_match else 0
                    
                    items.append({
                        'name': name.strip(),
                        'price': price
                    })
                    
            logger.info(f"Found {len(items)} items in my Loot.Farm inventory")
            
        except Exception as e:
            logger.error(f"Error getting Loot.Farm inventory: {e}")
            
        return items

    async def get_bot_items(self, search: str = None, max_price: float = 3.0) -> List[Dict[str, Any]]:
        """
        Получение предметов ботов для обмена.
        
        Args:
            search: Поисковый запрос
            max_price: Максимальная цена
            
        Returns:
            Список предметов
        """
        if not self.page:
            return []
            
        items = []
        try:
            # Вводим поиск если нужно
            if search:
                search_input = await self.page.query_selector('input[placeholder*="Поиск"], input.search')
                if search_input:
                    await search_input.fill(search)
                    await asyncio.sleep(1)
                    
            # Получаем предметы ботов
            item_elements = await self.page.query_selector_all('.bot-inventory .item, .store-items .item-card')
            
            for el in item_elements:
                name_el = await el.query_selector('.item-name, .name')
                price_el = await el.query_selector('.item-price, .price')
                
                if name_el and price_el:
                    name = await name_el.inner_text()
                    price_text = await price_el.inner_text()
                    
                    import re
                    price_match = re.search(r'[\d.]+', price_text.replace(',', '.'))
                    price = float(price_match.group()) if price_match else 0
                    
                    if price <= max_price:
                        items.append({
                            'name': name.strip(),
                            'price': price,
                            'element': el
                        })
                        
            logger.info(f"Found {len(items)} bot items on Loot.Farm")
            
        except Exception as e:
            logger.error(f"Error getting Loot.Farm bot items: {e}")
            
        return items

    async def create_trade(
        self,
        my_items: List[str],
        bot_items: List[str]
    ) -> Optional[str]:
        """
        Создание обмена на Loot.Farm.
        
        Args:
            my_items: Названия моих предметов для обмена
            bot_items: Названия предметов ботов
            
        Returns:
            Trade offer ID или None
        """
        if not self.page:
            return None
            
        try:
            # Выбираем свои предметы
            for item_name in my_items:
                item_el = await self.page.query_selector(f'.user-inventory .item:has-text("{item_name}")')
                if item_el:
                    await item_el.click()
                    await asyncio.sleep(0.3)
                    
            # Выбираем предметы ботов
            for item_name in bot_items:
                item_el = await self.page.query_selector(f'.bot-inventory .item:has-text("{item_name}")')
                if item_el:
                    await item_el.click()
                    await asyncio.sleep(0.3)
                    
            # Нажимаем кнопку обмена
            trade_btn = await self.page.query_selector('button:has-text("Обменять"), button:has-text("Trade")')
            if trade_btn:
                await trade_btn.click()
                await asyncio.sleep(3)
                
            # Подтверждаем обмен если нужно
            confirm_btn = await self.page.query_selector('button:has-text("Подтвердить"), button:has-text("Confirm")')
            if confirm_btn:
                await confirm_btn.click()
                await asyncio.sleep(2)
                
            logger.info(f"Trade created on Loot.Farm: {my_items} -> {bot_items}")
            
            # Пытаемся получить trade offer ID из URL или страницы
            # Это зависит от конкретной реализации сайта
            return "trade_created"
            
        except Exception as e:
            logger.error(f"Error creating Loot.Farm trade: {e}")
            return None

    async def withdraw_to_steam(self, item_names: List[str]) -> Optional[str]:
        """
        Вывод предметов в Steam.
        
        Args:
            item_names: Названия предметов для вывода
            
        Returns:
            Trade offer ID или None
        """
        if not self.page:
            return None
            
        try:
            # Переходим в раздел вывода
            withdraw_link = await self.page.query_selector('a:has-text("Вывод"), a:has-text("Withdraw")')
            if withdraw_link:
                await withdraw_link.click()
                await asyncio.sleep(2)
                
            # Выбираем предметы
            for item_name in item_names:
                item_el = await self.page.query_selector(f'.item:has-text("{item_name}")')
                if item_el:
                    await item_el.click()
                    await asyncio.sleep(0.3)
                    
            # Нажимаем вывести
            withdraw_btn = await self.page.query_selector('button:has-text("Вывести"), button:has-text("Withdraw")')
            if withdraw_btn:
                await withdraw_btn.click()
                await asyncio.sleep(3)
                
            logger.info(f"Withdraw initiated on Loot.Farm: {item_names}")
            return "withdraw_initiated"
            
        except Exception as e:
            logger.error(f"Error withdrawing from Loot.Farm: {e}")
            return None


# Тестирование
async def test_lootfarm():
    """Тест Loot.Farm"""
    bot = LootFarmBot()
    
    # Тест получения цен через JSON API
    print("Testing fetch_prices...")
    prices = await bot.fetch_prices()
    print(f"Total items: {len(prices)}")
    
    # Показываем несколько предметов
    count = 0
    for name, item in prices.items():
        if 0.50 <= item.price_usd <= 3.00 and item.have > 0:
            print(f"  {name}: ${item.price_usd:.2f} (have: {item.have}, overstock: {item.is_overstock})")
            count += 1
            if count >= 10:
                break
    
    # Тест проверки наличия
    print("\nTesting check_item_availability...")
    test_item = "Ace Door"
    available = await bot.check_item_availability(test_item)
    print(f"'{test_item}' available: {available}")
    
    await bot.close()


if __name__ == '__main__':
    asyncio.run(test_lootfarm())
