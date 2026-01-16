"""
Депозит предмета на Loot.Farm используя сохранённую сессию.
"""
import json
import asyncio
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from playwright.async_api import async_playwright
from src.steam_guard import SteamGuardManager
from src.lootfarm import LootFarmBot
from loguru import logger

SESSION_DIR = os.path.join(BASE_DIR, 'browser_session')


async def deposit_item(item_name: str = "Santa Chest Plate"):
    """Депозит предмета на Loot.Farm"""
    
    config_path = os.path.join(BASE_DIR, 'config/settings.json')
    with open(config_path, 'r') as f:
        settings = json.load(f)
    
    mafile_path = settings['steam']['mafile_path']
    if mafile_path.startswith('..'):
        mafile_path = os.path.normpath(os.path.join(BASE_DIR, mafile_path))
    
    guard = SteamGuardManager(mafile_path)
    
    # Проверяем цену на Loot.Farm
    lootfarm = LootFarmBot()
    prices = await lootfarm.fetch_prices()
    item_price = prices.get(item_name)
    
    print("=" * 60)
    print(f"ДЕПОЗИТ: {item_name}")
    print("=" * 60)
    
    if item_price:
        print(f"Цена на Loot.Farm: ${item_price.price_usd:.2f}")
        print(f"Overstock: {item_price.is_overstock}")
    else:
        print("Предмет не найден в базе Loot.Farm!")
    
    print("-" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={'width': 1400, 'height': 900}
        )
        
        page = await browser.new_page()
        
        print("\nОткрываю Loot.Farm...")
        await page.goto('https://loot.farm/ru/index.html', wait_until='load', timeout=60000)
        await asyncio.sleep(5)
        
        print("Ищу кнопку обновления инвентаря...")
        
        # Ждём загрузки и ищем кнопку обновления
        await asyncio.sleep(3)
        
        # Делаем скриншот
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_deposit_1.png'))
        print("Скриншот 1 сохранён")
        
        print("\nБраузер открыт. Выполните депозит вручную:")
        print("1. Нажмите 'Обновить инвентарь'")
        print("2. Выберите Santa Chest Plate")
        print("3. Нажмите 'Депозит'")
        print(f"\n2FA код: {guard.generate_code()}")
        print("\nЖду 120 секунд...")
        
        for i in range(120):
            await asyncio.sleep(1)
            if i % 30 == 0 and i > 0:
                print(f"  {i}/120 сек, 2FA: {guard.generate_code()}")
        
        # Финальный скриншот
        try:
            await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_deposit_2.png'))
            print("\nСкриншот 2 сохранён")
            print(f"URL: {page.url}")
        except:
            pass
        
        await browser.close()
    
    # Проверяем подтверждения Steam
    print("\nПроверяю подтверждения Steam...")
    confirmations = await guard.fetch_confirmations()
    print(f"Найдено подтверждений: {len(confirmations)}")
    
    if confirmations:
        print("Подтверждаю все трейды...")
        accepted = await guard.accept_all_confirmations()
        print(f"Подтверждено: {accepted}")
    
    await guard.close()
    await lootfarm.close()
    
    print("\n" + "=" * 60)
    print("ГОТОВО!")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(deposit_item())
