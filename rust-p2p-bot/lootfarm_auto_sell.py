"""
Полностью автоматический депозит на Loot.Farm.
Открывает браузер, обновляет инвентарь, выбирает предмет, делает депозит.
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


async def auto_sell_on_lootfarm(item_name: str):
    """
    Автоматическая продажа предмета на Loot.Farm.
    
    Args:
        item_name: Название предмета для продажи
        
    Returns:
        True если успешно, False если ошибка
    """
    config_path = os.path.join(BASE_DIR, 'config/settings.json')
    with open(config_path, 'r') as f:
        settings = json.load(f)
    
    mafile_path = settings['steam']['mafile_path']
    if mafile_path.startswith('..'):
        mafile_path = os.path.normpath(os.path.join(BASE_DIR, mafile_path))
    
    guard = SteamGuardManager(mafile_path)
    lootfarm = LootFarmBot()
    
    # Проверяем цену
    prices = await lootfarm.fetch_prices()
    item_info = prices.get(item_name)
    
    if not item_info:
        print(f"❌ Предмет '{item_name}' не найден на Loot.Farm")
        await lootfarm.close()
        await guard.close()
        return False
    
    if item_info.is_overstock:
        print(f"❌ Предмет '{item_name}' в overstock на Loot.Farm")
        await lootfarm.close()
        await guard.close()
        return False
    
    print(f"✓ {item_name}: ${item_info.price_usd:.2f} (не overstock)")
    
    success = False
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={'width': 1400, 'height': 900}
        )
        
        page = await browser.new_page()
        
        try:
            # 1. Открываем Loot.Farm
            print("\n[1/5] Открываю Loot.Farm...")
            await page.goto('https://loot.farm/ru/index.html', wait_until='load', timeout=60000)
            await asyncio.sleep(4)
            
            # 2. Нажимаем обновить инвентарь
            print("[2/5] Обновляю инвентарь...")
            
            # Ищем кнопку обновления - она обычно рядом с инвентарём пользователя
            # На Loot.Farm это иконка обновления или кнопка "Обновить"
            refresh_btn = await page.query_selector('button.refresh, .refresh-btn, [class*="refresh"], button:has-text("Обновить")')
            
            if not refresh_btn:
                # Пробуем найти через JavaScript
                await page.evaluate('''() => {
                    const btns = document.querySelectorAll('button, .btn');
                    for (let btn of btns) {
                        if (btn.textContent.includes('Обновить') || btn.textContent.includes('Refresh')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }''')
            else:
                await refresh_btn.click()
            
            await asyncio.sleep(5)  # Ждём загрузки инвентаря
            
            # 3. Ищем и выбираем предмет
            print(f"[3/5] Ищу предмет: {item_name}...")
            
            # Ищем предмет по названию
            item_found = await page.evaluate(f'''(itemName) => {{
                const items = document.querySelectorAll('.item, .inventory-item, [class*="item"]');
                for (let item of items) {{
                    const nameEl = item.querySelector('.name, .item-name, [class*="name"]');
                    if (nameEl && nameEl.textContent.includes(itemName)) {{
                        item.click();
                        return true;
                    }}
                }}
                // Пробуем по title или data атрибутам
                for (let item of items) {{
                    if (item.title && item.title.includes(itemName)) {{
                        item.click();
                        return true;
                    }}
                    if (item.dataset && item.dataset.name && item.dataset.name.includes(itemName)) {{
                        item.click();
                        return true;
                    }}
                }}
                return false;
            }}''', item_name)
            
            if not item_found:
                print(f"  ⚠ Предмет не найден в инвентаре на сайте")
                await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_item_not_found.png'))
            else:
                print(f"  ✓ Предмет выбран")
            
            await asyncio.sleep(2)
            
            # 4. Нажимаем кнопку депозита/продажи
            print("[4/5] Нажимаю депозит...")
            
            deposit_clicked = await page.evaluate('''() => {
                const btns = document.querySelectorAll('button, .btn, a.btn');
                for (let btn of btns) {
                    const text = btn.textContent.toLowerCase();
                    if (text.includes('депозит') || text.includes('deposit') || 
                        text.includes('продать') || text.includes('sell') ||
                        text.includes('обменять') || text.includes('trade')) {
                        if (btn.offsetParent !== null && !btn.disabled) {
                            btn.click();
                            return true;
                        }
                    }
                }
                return false;
            }''')
            
            if deposit_clicked:
                print("  ✓ Кнопка депозита нажата")
            else:
                print("  ⚠ Кнопка депозита не найдена")
            
            await asyncio.sleep(3)
            
            # Подтверждаем если есть модальное окно
            await page.evaluate('''() => {
                const confirms = document.querySelectorAll('button, .btn');
                for (let btn of confirms) {
                    const text = btn.textContent.toLowerCase();
                    if (text.includes('подтвердить') || text.includes('confirm') || text.includes('да') || text.includes('yes')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''')
            
            await asyncio.sleep(2)
            await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_after_deposit.png'))
            
            # 5. Ждём и подтверждаем трейд в Steam
            print("[5/5] Жду трейд-оффер от Loot.Farm...")
            
            for i in range(30):  # 60 секунд
                await asyncio.sleep(2)
                
                if i % 5 == 0:
                    confirmations = await guard.fetch_confirmations()
                    if confirmations:
                        print(f"  ✓ Найдено {len(confirmations)} подтверждений!")
                        for conf in confirmations:
                            print(f"    - {conf.headline}")
                        
                        accepted = await guard.accept_all_confirmations()
                        if accepted > 0:
                            print(f"  ✓ Подтверждено: {accepted}")
                            success = True
                            break
                    else:
                        print(f"  [{i*2}/60 сек] Ожидаю...")
            
            await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_final.png'))
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_error.png'))
        
        finally:
            await browser.close()
    
    await guard.close()
    await lootfarm.close()
    
    if success:
        print(f"\n✅ УСПЕШНО! {item_name} продан на Loot.Farm за ${item_info.price_usd:.2f}")
    else:
        print(f"\n⚠ Депозит не подтверждён автоматически. Проверь вручную.")
    
    return success


async def get_lootfarm_balance():
    """Получение баланса Loot.Farm"""
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={'width': 1400, 'height': 900}
        )
        
        page = await browser.new_page()
        await page.goto('https://loot.farm/ru/index.html', wait_until='load', timeout=60000)
        await asyncio.sleep(5)
        
        # Ищем баланс через JavaScript
        balance = await page.evaluate('''() => {
            // Ищем элемент с балансом
            const balanceEls = document.querySelectorAll('[class*="balance"], .user-balance, .wallet');
            for (let el of balanceEls) {
                const text = el.textContent;
                const match = text.match(/([\\d.,]+)\\s*\\$/);
                if (match) return parseFloat(match[1].replace(',', '.'));
            }
            // Ищем в header
            const header = document.querySelector('header, .header, .navbar');
            if (header) {
                const match = header.textContent.match(/([\\d.,]+)\\s*\\$/);
                if (match) return parseFloat(match[1].replace(',', '.'));
            }
            return null;
        }''')
        
        await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_balance.png'))
        
        if balance is not None:
            print(f"Баланс Loot.Farm: ${balance:.2f}")
        else:
            print("Баланс не найден. Проверь скриншот: logs/lootfarm_balance.png")
        
        await asyncio.sleep(5)
        await browser.close()
        
        return balance


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'balance':
            asyncio.run(get_lootfarm_balance())
        else:
            asyncio.run(auto_sell_on_lootfarm(sys.argv[1]))
    else:
        print("Использование:")
        print("  python lootfarm_auto_sell.py balance - проверить баланс")
        print("  python lootfarm_auto_sell.py 'Santa Chest Plate' - продать предмет")
