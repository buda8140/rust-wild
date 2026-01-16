"""
Полный цикл торговли: DMarket -> Steam -> Loot.Farm
Тестирование на Santa Chest Plate.
"""
import json
import asyncio
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.steam_guard import SteamGuardManager
from src.dmarket_api import DMarketAPI
from src.lootfarm import LootFarmBot
from loguru import logger


async def check_steam_inventory(guard: SteamGuardManager) -> list:
    """Проверка Steam инвентаря через авторизованную сессию"""
    import aiohttp
    
    url = f"https://steamcommunity.com/inventory/{guard.steam_id}/252490/2"
    params = {'l': 'english', 'count': 100}
    
    session = await guard._get_session()
    headers = guard._get_headers()
    cookies = guard._get_cookies()
    
    # Добавляем задержку чтобы избежать rate limit
    await asyncio.sleep(2)
    
    async with session.get(url, params=params, headers=headers, cookies=cookies,
                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status == 200:
            data = await resp.json()
            items = []
            
            descriptions = {d['classid']: d for d in data.get('descriptions', [])}
            
            for asset in data.get('assets', []):
                desc = descriptions.get(asset['classid'], {})
                items.append({
                    'assetid': asset['assetid'],
                    'classid': asset['classid'],
                    'name': desc.get('market_hash_name', desc.get('name', 'Unknown')),
                    'tradable': desc.get('tradable', 0) == 1
                })
            
            return items
        elif resp.status == 429:
            logger.warning("Rate limit, waiting 10 seconds...")
            await asyncio.sleep(10)
            # Retry
            async with session.get(url, params=params, headers=headers, cookies=cookies,
                                   timeout=aiohttp.ClientTimeout(total=30)) as resp2:
                if resp2.status == 200:
                    data = await resp2.json()
                    items = []
                    descriptions = {d['classid']: d for d in data.get('descriptions', [])}
                    for asset in data.get('assets', []):
                        desc = descriptions.get(asset['classid'], {})
                        items.append({
                            'assetid': asset['assetid'],
                            'classid': asset['classid'],
                            'name': desc.get('market_hash_name', desc.get('name', 'Unknown')),
                            'tradable': desc.get('tradable', 0) == 1
                        })
                    return items
            return []
        else:
            logger.error(f"Failed to get inventory: {resp.status}")
            return []


async def deposit_to_lootfarm(guard: SteamGuardManager, item_name: str):
    """
    Депозит предмета на Loot.Farm.
    
    Loot.Farm работает так:
    1. Заходим на сайт через Steam
    2. Выбираем предмет из своего инвентаря
    3. Loot.Farm создает trade offer
    4. Мы принимаем trade offer
    5. Получаем баланс на Loot.Farm
    """
    logger.info(f"Depositing {item_name} to Loot.Farm...")
    
    # Для депозита нужен Playwright
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Видимый режим для отладки
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            # 1. Переходим на Loot.Farm
            logger.info("Opening Loot.Farm...")
            await page.goto('https://loot.farm/ru/index.html', wait_until='networkidle')
            await asyncio.sleep(3)
            
            # 2. Нажимаем "Войти через Steam"
            login_btn = await page.query_selector('a[href*="steam"], .steam-login, button:has-text("Steam")')
            if login_btn:
                logger.info("Clicking Steam login...")
                await login_btn.click()
                await asyncio.sleep(5)
            
            # 3. Если на странице Steam - авторизуемся
            if 'steamcommunity.com' in page.url:
                logger.info("On Steam login page...")
                
                # Вводим логин
                username_input = await page.query_selector('input[name="username"], #input_username')
                if username_input:
                    await username_input.fill(guard.account_name)
                    await asyncio.sleep(0.5)
                
                password_input = await page.query_selector('input[name="password"], #input_password')
                if password_input:
                    # Загружаем пароль из settings
                    config_path = os.path.join(BASE_DIR, 'config/settings.json')
                    with open(config_path, 'r') as f:
                        settings = json.load(f)
                    await password_input.fill(settings['steam']['password'])
                    await asyncio.sleep(0.5)
                
                # Нажимаем войти
                submit_btn = await page.query_selector('button[type="submit"], #login_btn_signin')
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(5)
                
                # Если нужен 2FA код
                code_input = await page.query_selector('input[name="twofactorcode"], #twofactorcode_entry')
                if code_input:
                    code = guard.generate_code()
                    logger.info(f"Entering 2FA code: {code}")
                    await code_input.fill(code)
                    
                    submit_btn = await page.query_selector('button[type="submit"], #login_twofactorauth_buttonset_entercode')
                    if submit_btn:
                        await submit_btn.click()
                        await asyncio.sleep(5)
            
            # 4. Ждем возврата на Loot.Farm
            logger.info("Waiting for Loot.Farm...")
            await asyncio.sleep(5)
            
            # 5. Обновляем инвентарь
            logger.info("Refreshing inventory...")
            refresh_btn = await page.query_selector('button:has-text("Обновить"), .refresh-btn, [class*="refresh"]')
            if refresh_btn:
                await refresh_btn.click()
                await asyncio.sleep(5)
            
            # 6. Ищем наш предмет
            logger.info(f"Looking for {item_name}...")
            
            # Вводим в поиск
            search_input = await page.query_selector('input[placeholder*="Поиск"], input.search, [class*="search"] input')
            if search_input:
                await search_input.fill(item_name)
                await asyncio.sleep(2)
            
            # Кликаем на предмет
            item_el = await page.query_selector(f'.item:has-text("{item_name}"), [class*="item"]:has-text("{item_name}")')
            if item_el:
                await item_el.click()
                logger.info(f"Selected {item_name}")
                await asyncio.sleep(1)
            else:
                logger.warning(f"Item {item_name} not found in inventory")
            
            # 7. Нажимаем "Депозит" или "Обменять"
            deposit_btn = await page.query_selector('button:has-text("Депозит"), button:has-text("Deposit"), button:has-text("Обменять")')
            if deposit_btn:
                await deposit_btn.click()
                logger.info("Deposit initiated!")
                await asyncio.sleep(5)
            
            # 8. Ждем trade offer
            logger.info("Waiting for trade offer...")
            await asyncio.sleep(10)
            
            # Скриншот для отладки
            await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_deposit.png'))
            logger.info("Screenshot saved to logs/lootfarm_deposit.png")
            
            # Держим браузер открытым для ручной проверки
            logger.info("Browser will stay open for 60 seconds for manual verification...")
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Error: {e}")
            await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_error.png'))
        
        finally:
            await browser.close()


async def main():
    """Основная функция"""
    # Загружаем настройки
    config_path = os.path.join(BASE_DIR, 'config/settings.json')
    with open(config_path, 'r') as f:
        settings = json.load(f)
    
    # Путь к maFile
    mafile_path = settings['steam']['mafile_path']
    if mafile_path.startswith('..'):
        mafile_path = os.path.normpath(os.path.join(BASE_DIR, mafile_path))
    
    print("=" * 60)
    print("ПОЛНЫЙ ЦИКЛ ТОРГОВЛИ")
    print("=" * 60)
    
    # Инициализация Steam Guard
    guard = SteamGuardManager(mafile_path)
    print(f"\n📱 Steam: {guard.account_name} ({guard.steam_id})")
    print(f"2FA Code: {guard.generate_code()}")
    
    # Проверяем Steam инвентарь
    print("\n📦 Проверка Steam инвентаря...")
    inventory = await check_steam_inventory(guard)
    
    if inventory:
        print(f"Найдено предметов: {len(inventory)}")
        for item in inventory:
            tradable = "✓" if item['tradable'] else "✗"
            print(f"  [{tradable}] {item['name']} (assetid: {item['assetid']})")
    else:
        print("Инвентарь пуст или недоступен")
    
    # Ищем Santa Chest Plate
    santa = next((i for i in inventory if 'Santa' in i['name']), None)
    
    if santa:
        print(f"\n🎅 Найден Santa Chest Plate!")
        print(f"   AssetID: {santa['assetid']}")
        print(f"   Tradable: {santa['tradable']}")
        
        if santa['tradable']:
            # Проверяем цену на Loot.Farm
            lootfarm = LootFarmBot()
            prices = await lootfarm.fetch_prices()
            lf_price = prices.get('Santa Chest Plate')
            
            if lf_price:
                print(f"\n💰 Цена на Loot.Farm: ${lf_price.price_usd:.2f}")
                print(f"   У ботов: {lf_price.have}")
                print(f"   Overstock: {lf_price.is_overstock}")
                
                if not lf_price.is_overstock:
                    print("\n🚀 Начинаем депозит на Loot.Farm...")
                    await deposit_to_lootfarm(guard, 'Santa Chest Plate')
                else:
                    print("\n⚠️ Предмет в overstock на Loot.Farm!")
            
            await lootfarm.close()
        else:
            print("\n⚠️ Предмет не tradable!")
    else:
        print("\n❌ Santa Chest Plate не найден в инвентаре")
    
    # Проверяем подтверждения
    print("\n📋 Проверка подтверждений Steam...")
    confirmations = await guard.fetch_confirmations()
    print(f"Ожидающих подтверждений: {len(confirmations)}")
    
    for conf in confirmations:
        print(f"  - {conf.headline} ({conf.type_name})")
    
    if confirmations:
        print("\n✅ Подтверждаем все трейды...")
        accepted = await guard.accept_all_confirmations()
        print(f"Подтверждено: {accepted}")
    
    await guard.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
