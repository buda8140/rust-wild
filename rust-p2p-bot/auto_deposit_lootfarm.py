"""
Автоматический депозит на Loot.Farm.
Использует сохранённую сессию браузера и автоподтверждение Steam Guard.
"""
import json
import asyncio
import sys
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from playwright.async_api import async_playwright
from src.steam_guard import SteamGuardManager
from src.lootfarm import LootFarmBot
from loguru import logger

SESSION_DIR = os.path.join(BASE_DIR, 'browser_session')


async def auto_deposit(item_name: str = None):
    """
    Автоматический депозит предмета на Loot.Farm.
    
    Args:
        item_name: Название предмета (если None - депозит всех)
    """
    config_path = os.path.join(BASE_DIR, 'config/settings.json')
    with open(config_path, 'r') as f:
        settings = json.load(f)
    
    mafile_path = settings['steam']['mafile_path']
    if mafile_path.startswith('..'):
        mafile_path = os.path.normpath(os.path.join(BASE_DIR, mafile_path))
    
    guard = SteamGuardManager(mafile_path)
    lootfarm = LootFarmBot()
    
    print("=" * 60)
    print("АВТОМАТИЧЕСКИЙ ДЕПОЗИТ НА LOOT.FARM")
    print("=" * 60)
    
    # Получаем цены Loot.Farm
    prices = await lootfarm.fetch_prices()
    print(f"Загружено {len(prices)} цен Loot.Farm")
    
    if item_name:
        item_price = prices.get(item_name)
        if item_price:
            print(f"\nЦелевой предмет: {item_name}")
            print(f"  Цена: ${item_price.price_usd:.2f}")
            print(f"  Overstock: {item_price.is_overstock}")
        else:
            print(f"\n⚠ Предмет '{item_name}' не найден в базе Loot.Farm")
    
    print("-" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={'width': 1400, 'height': 900}
        )
        
        page = await browser.new_page()
        
        print("\n[1/6] Открываю Loot.Farm...")
        await page.goto('https://loot.farm/ru/index.html', wait_until='load', timeout=60000)
        await asyncio.sleep(3)
        
        # Проверяем авторизацию
        print("[2/6] Проверяю авторизацию...")
        
        # Ищем элементы авторизованного пользователя
        user_el = await page.query_selector('.user-info, .user-name, .profile-name, [class*="user"]')
        balance_el = await page.query_selector('.balance, [class*="balance"]')
        
        if user_el or balance_el:
            print("  ✓ Авторизован на Loot.Farm")
            if balance_el:
                balance_text = await balance_el.inner_text()
                print(f"  Баланс: {balance_text}")
        else:
            print("  ⚠ Возможно не авторизован, продолжаю...")
        
        # Делаем скриншот
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_auto_1.png'))
        
        # Ищем кнопку обновления инвентаря
        print("\n[3/6] Обновляю инвентарь Steam...")
        
        # Разные варианты кнопки обновления
        refresh_selectors = [
            'button:has-text("Обновить")',
            'button:has-text("Refresh")',
            '.refresh-btn',
            '.reload-inventory',
            '[class*="refresh"]',
            'button[title*="Обновить"]',
            'button[title*="Refresh"]'
        ]
        
        refresh_clicked = False
        for selector in refresh_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    print(f"  ✓ Нажал кнопку обновления")
                    refresh_clicked = True
                    await asyncio.sleep(5)
                    break
            except:
                continue
        
        if not refresh_clicked:
            print("  ⚠ Кнопка обновления не найдена, пробую через JS...")
            # Пробуем через JavaScript
            try:
                await page.evaluate('window.refreshInventory && window.refreshInventory()')
            except:
                pass
        
        await asyncio.sleep(3)
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_auto_2.png'))
        
        # Ищем предметы в инвентаре
        print("\n[4/6] Ищу предметы для депозита...")
        
        # Разные селекторы для предметов
        item_selectors = [
            '.user-inventory .item',
            '.my-items .item',
            '.inventory-item',
            '[class*="inventory"] [class*="item"]',
            '.item-card'
        ]
        
        items_found = []
        for selector in item_selectors:
            items = await page.query_selector_all(selector)
            if items:
                print(f"  Найдено {len(items)} предметов (селектор: {selector})")
                items_found = items
                break
        
        if not items_found:
            print("  ⚠ Предметы не найдены в инвентаре")
            print("  Делаю скриншот для анализа...")
            await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_no_items.png'))
        
        # Если указан конкретный предмет - ищем его
        target_item = None
        if item_name and items_found:
            for item in items_found:
                try:
                    text = await item.inner_text()
                    if item_name.lower() in text.lower():
                        target_item = item
                        print(f"  ✓ Найден целевой предмет: {item_name}")
                        break
                except:
                    continue
        
        # Выбираем предмет для депозита
        print("\n[5/6] Выбираю предмет для депозита...")
        
        if target_item:
            await target_item.click()
            print(f"  ✓ Выбран: {item_name}")
        elif items_found:
            # Выбираем первый доступный
            await items_found[0].click()
            print("  ✓ Выбран первый доступный предмет")
        
        await asyncio.sleep(2)
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_auto_3.png'))
        
        # Ищем кнопку депозита
        print("\n[6/6] Нажимаю кнопку депозита...")
        
        deposit_selectors = [
            'button:has-text("Депозит")',
            'button:has-text("Deposit")',
            'button:has-text("Продать")',
            'button:has-text("Sell")',
            '.deposit-btn',
            '[class*="deposit"]',
            'button[class*="trade"]'
        ]
        
        deposit_clicked = False
        for selector in deposit_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    is_visible = await btn.is_visible()
                    is_enabled = await btn.is_enabled()
                    if is_visible and is_enabled:
                        await btn.click()
                        print(f"  ✓ Нажал кнопку депозита")
                        deposit_clicked = True
                        await asyncio.sleep(3)
                        break
            except:
                continue
        
        if not deposit_clicked:
            print("  ⚠ Кнопка депозита не найдена или недоступна")
        
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_auto_4.png'))
        
        # Ждём появления трейд-оффера
        print("\n" + "-" * 60)
        print("Ожидаю трейд-оффер от Loot.Farm...")
        print(f"2FA код: {guard.generate_code()}")
        
        # Мониторим подтверждения Steam
        for i in range(60):  # 60 секунд
            await asyncio.sleep(2)
            
            if i % 10 == 0:
                print(f"  [{i}/60 сек] Проверяю подтверждения Steam...")
                confirmations = await guard.fetch_confirmations()
                
                if confirmations:
                    print(f"  ✓ Найдено {len(confirmations)} подтверждений!")
                    for conf in confirmations:
                        print(f"    - {conf.headline}")
                    
                    print("  Подтверждаю все трейды...")
                    accepted = await guard.accept_all_confirmations()
                    print(f"  ✓ Подтверждено: {accepted}")
                    
                    if accepted > 0:
                        print("\n" + "=" * 60)
                        print("✓ ДЕПОЗИТ УСПЕШНО ПОДТВЕРЖДЁН!")
                        print("=" * 60)
                        break
        
        # Финальный скриншот
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_auto_final.png'))
        
        # Проверяем баланс
        print("\nПроверяю баланс Loot.Farm...")
        await page.reload()
        await asyncio.sleep(3)
        
        balance_el = await page.query_selector('.balance, [class*="balance"]')
        if balance_el:
            balance_text = await balance_el.inner_text()
            print(f"Текущий баланс: {balance_text}")
        
        print(f"\nURL: {page.url}")
        
        await browser.close()
    
    await guard.close()
    await lootfarm.close()
    
    print("\n" + "=" * 60)
    print("ГОТОВО!")
    print("=" * 60)


async def check_lootfarm_balance():
    """Проверка баланса на Loot.Farm"""
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={'width': 1400, 'height': 900}
        )
        
        page = await browser.new_page()
        await page.goto('https://loot.farm/ru/index.html', wait_until='load', timeout=60000)
        await asyncio.sleep(5)
        
        # Скриншот
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_balance.png'))
        
        # Ищем баланс
        balance_el = await page.query_selector('.balance, [class*="balance"]')
        if balance_el:
            balance_text = await balance_el.inner_text()
            print(f"Баланс Loot.Farm: {balance_text}")
        else:
            print("Баланс не найден")
        
        # Получаем HTML для анализа
        html = await page.content()
        
        # Ищем баланс в HTML
        balance_match = re.search(r'balance["\s:>]+\$?([\d.,]+)', html, re.IGNORECASE)
        if balance_match:
            print(f"Найден баланс в HTML: ${balance_match.group(1)}")
        
        print(f"URL: {page.url}")
        
        await browser.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'balance':
            asyncio.run(check_lootfarm_balance())
        else:
            asyncio.run(auto_deposit(sys.argv[1]))
    else:
        # По умолчанию депозит Santa Chest Plate
        asyncio.run(auto_deposit("Santa Chest Plate"))
