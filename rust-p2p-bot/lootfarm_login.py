"""
Авторизация на Loot.Farm с сохранением сессии.
Сессия сохраняется в файл и переиспользуется.
"""
import json
import asyncio
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from playwright.async_api import async_playwright
from src.steam_guard import SteamGuardManager
from loguru import logger

# Путь для сохранения сессии браузера
SESSION_DIR = os.path.join(BASE_DIR, 'browser_session')


async def login_and_save_session():
    """Авторизация на Loot.Farm и сохранение сессии"""
    
    # Загружаем настройки
    config_path = os.path.join(BASE_DIR, 'config/settings.json')
    with open(config_path, 'r') as f:
        settings = json.load(f)
    
    mafile_path = settings['steam']['mafile_path']
    if mafile_path.startswith('..'):
        mafile_path = os.path.normpath(os.path.join(BASE_DIR, mafile_path))
    
    guard = SteamGuardManager(mafile_path)
    
    print("=" * 60)
    print("LOOT.FARM - АВТОРИЗАЦИЯ И СОХРАНЕНИЕ СЕССИИ")
    print("=" * 60)
    print(f"Steam: {guard.account_name}")
    print(f"2FA Code: {guard.generate_code()}")
    print("-" * 60)
    
    async with async_playwright() as p:
        # Создаем директорию для сессии
        os.makedirs(SESSION_DIR, exist_ok=True)
        
        # Запускаем браузер с сохранением состояния
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,  # Видимый режим для авторизации
            viewport={'width': 1400, 'height': 900},
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await browser.new_page()
        
        try:
            # Переходим на Loot.Farm
            print("\n🌐 Открываю Loot.Farm...")
            await page.goto('https://loot.farm/ru/index.html', wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(5)
            
            # Проверяем, авторизованы ли уже
            logged_in = await page.query_selector('.user-balance, .balance, [class*="user-info"], .header-user')
            
            if logged_in:
                print("✅ Уже авторизован! Сессия сохранена.")
                try:
                    balance_text = await logged_in.inner_text()
                    print(f"💰 Баланс: {balance_text}")
                except:
                    pass
            else:
                print("\n🔐 Нужна авторизация через Steam...")
                print("   Браузер открыт - авторизуйтесь вручную!")
                print("   После авторизации сессия сохранится автоматически.")
                print("\n   Ожидаю 120 секунд для ручной авторизации...")
                
                # Ждем пока пользователь авторизуется вручную
                for i in range(120):
                    await asyncio.sleep(1)
                    
                    # Проверяем каждые 5 секунд
                    if i % 5 == 0:
                        logged_in = await page.query_selector('.user-balance, .balance, [class*="user-info"], .header-user')
                        if logged_in:
                            print(f"\n✅ Авторизация обнаружена на секунде {i}!")
                            break
                        else:
                            remaining = 120 - i
                            print(f"   Осталось {remaining} сек...")
                
                # Финальная проверка
                logged_in = await page.query_selector('.user-balance, .balance, [class*="user-info"], .header-user')
                if logged_in:
                    print("\n✅ Авторизация успешна! Сессия сохранена.")
                else:
                    print("\n⚠️ Авторизация не обнаружена, но сессия всё равно сохранена.")
            
            # Делаем скриншот
            screenshot_path = os.path.join(BASE_DIR, 'logs/lootfarm_session.png')
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            await page.screenshot(path=screenshot_path)
            print(f"\n📸 Скриншот: {screenshot_path}")
            
            # Показываем текущий URL
            print(f"🔗 URL: {page.url}")
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            try:
                await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_error.png'))
            except:
                pass
        
        finally:
            print("\n" + "=" * 60)
            print("Сессия сохранена в:", SESSION_DIR)
            print("При следующем запуске авторизация не потребуется!")
            print("=" * 60)
            await browser.close()
    
    await guard.close()


async def test_saved_session():
    """Проверка сохраненной сессии и работа с инвентарем"""
    
    if not os.path.exists(SESSION_DIR):
        print("❌ Сессия не найдена! Сначала запустите: python lootfarm_login.py")
        return False
    
    print("=" * 60)
    print("ПРОВЕРКА СОХРАНЕННОЙ СЕССИИ LOOT.FARM")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={'width': 1400, 'height': 900}
        )
        
        page = await browser.new_page()
        
        try:
            print("\n🌐 Открываю Loot.Farm...")
            await page.goto('https://loot.farm/ru/index.html', wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(5)
            
            # Проверяем авторизацию
            logged_in = await page.query_selector('.user-balance, .balance, [class*="user-info"], .header-user')
            
            if logged_in:
                print("✅ Сессия активна!")
                
                # Пробуем получить баланс
                try:
                    balance_el = await page.query_selector('.balance, .user-balance, [class*="balance"]')
                    if balance_el:
                        balance_text = await balance_el.inner_text()
                        print(f"💰 Баланс: {balance_text}")
                except:
                    pass
                
                # Ищем кнопку обновления инвентаря
                print("\n📦 Ищу инвентарь...")
                await asyncio.sleep(2)
                
                # Скриншот текущего состояния
                await page.screenshot(path=os.path.join(BASE_DIR, 'logs/lootfarm_test.png'))
                print("📸 Скриншот сохранен: logs/lootfarm_test.png")
                
                # Держим браузер открытым для проверки
                print("\n⏳ Браузер открыт 30 секунд для проверки...")
                await asyncio.sleep(30)
                
                return True
            else:
                print("❌ Сессия истекла, нужна повторная авторизация")
                print("   Запустите: python lootfarm_login.py")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return False
            
        finally:
            await browser.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        asyncio.run(test_saved_session())
    else:
        asyncio.run(login_and_save_session())
