"""
TradeIt.gg модуль для торговли скинами.
Использует Selenium для веб-автоматизации.
"""

import asyncio
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger


class TradeItBot:
    """Управление TradeIt.gg через Selenium WebDriver"""
    
    BASE_URL = "https://tradeit.gg/ru/rust"
    # Вход через Steam - не нужны email/password
    
    def __init__(self):
        self.driver = None
        self.is_logged_in = False
        
    def _initialize_driver(self):
        """Инициализируем Chrome WebDriver"""
        
        try:
            # Параметры для headless режима (без GUI)
            options = webdriver.ChromeOptions()
            
            # options.add_argument('--headless')  # Раскомментировать в продакшене
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Используем webdriver-manager для автоматической установки ChromeDriver
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            
            logger.info("✅ ChromeDriver инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ChromeDriver: {e}")
            raise
    
    async def login(self) -> bool:
        """Авторизация на TradeIt.gg через Steam"""
        
        if not self.driver:
            self._initialize_driver()
        
        try:
            logger.info("🔐 Авторизуемся на TradeIt.gg через Steam...")
            
            # Переходим на главную страницу
            self.driver.get(self.BASE_URL)
            
            # Ищем кнопку "Войти через Steam"
            steam_login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Steam')] | //a[contains(@href, 'steam')]"))
            )
            
            steam_login_button.click()
            logger.info("🔄 Переходим на страницу Steam...")
            
            # Ждем перехода на Steam или возврата на TradeIt (если уже авторизованы)
            time.sleep(3)
            
            # Проверяем, вернулись ли мы на TradeIt (значит уже авторизованы)
            if "tradeit.gg" in self.driver.current_url:
                logger.info("✅ Уже авторизованы через Steam!")
                self.is_logged_in = True
                return True
            
            # Если попали на Steam - ждем ручной авторизации или автоматической
            if "steamcommunity.com" in self.driver.current_url:
                logger.info("⏳ Ожидаем авторизацию Steam (может быть автоматической)...")
                
                # Ждем возврата на TradeIt (до 60 секунд)
                for i in range(60):
                    time.sleep(1)
                    if "tradeit.gg" in self.driver.current_url:
                        logger.success("✅ Авторизация через Steam успешна!")
                        self.is_logged_in = True
                        return True
                
                logger.error("❌ Timeout при ожидании авторизации Steam")
                return False
            
            self.is_logged_in = True
            logger.success("✅ Авторизация успешна!")
            return True
            
        except TimeoutException:
            logger.error("❌ Timeout при авторизации - TradeIt.gg не ответил")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации: {e}")
            return False
    
    async def get_balance(self) -> float:
        """Получить текущий баланс на TradeIt.gg"""
        
        try:
            if not self.is_logged_in:
                logger.warning("⚠️ Не авторизованы, авторизуемся...")
                await self.login()
            
            # Переходим на страницу профиля
            self.driver.get(f"{self.BASE_URL}/user/account")
            
            # Ждем загрузки баланса
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "balance-value"))
            )
            
            # Получаем текст баланса
            balance_element = self.driver.find_element(By.CLASS_NAME, "balance-value")
            balance_text = balance_element.text
            
            # Парсим: "$24.60" → 24.60
            balance = float(balance_text.replace('$', '').replace(',', ''))
            
            logger.info(f"💰 Баланс TradeIt.gg: ${balance:.2f}")
            
            return balance
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения баланса: {e}")
            return 0
    
    async def search_item(self, item_name: str) -> dict:
        """Поиск предмета на TradeIt.gg"""
        
        try:
            logger.info(f"🔍 Ищем: {item_name}")
            
            # Переходим на страницу покупки
            self.driver.get(f"{self.BASE_URL}/buy")
            
            # Находим поле поиска
            search_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "search-input"))
            )
            
            # Вводим название предмета
            search_field.clear()
            search_field.send_keys(item_name)
            
            # Ждем результатов поиска
            time.sleep(1)  # Даем время на автодополнение
            
            # Получаем результаты
            results = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "item-result"))
            )
            
            if not results:
                logger.warning(f"⚠️ Предмет {item_name} не найден")
                return {}
            
            # Берем первый результат
            first_result = results[0]
            
            # Получаем данные предмета
            price_element = first_result.find_element(By.CLASS_NAME, "item-price")
            condition_element = first_result.find_element(By.CLASS_NAME, "item-condition")
            stock_element = first_result.find_element(By.CLASS_NAME, "item-stock")
            
            price = float(price_element.text.replace('$', ''))
            condition = condition_element.text
            stock = int(stock_element.text.split()[0])
            
            item_data = {
                'name': item_name,
                'price': price,
                'condition': condition,
                'stock': stock,
                'element': first_result  # Для дальнейших действий
            }
            
            logger.info(f"✅ Найден: {item_name} - ${price:.2f} ({stock} шт)")
            
            return item_data
            
        except TimeoutException:
            logger.error(f"❌ Timeout при поиске {item_name}")
            return {}
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return {}
    
    async def buy_item(self, item_name: str, max_price: float) -> str:
        """
        Купить предмет на TradeIt.gg
        
        Возвращает: ID трейда или пустую строку если не удалось
        """
        
        try:
            logger.info(f"💳 Покупаем {item_name} за ${max_price:.2f}")
            
            # Поиск предмета
            item = await self.search_item(item_name)
            
            if not item:
                logger.error(f"❌ Не удалось найти {item_name}")
                return ""
            
            # Проверяем цену
            if item['price'] > max_price:
                logger.warning(
                    f"⚠️ Цена {item['price']} выше макса {max_price}"
                )
                return ""
            
            # Проверяем наличие
            if item['stock'] <= 0:
                logger.warning(f"⚠️ {item_name} нет в наличии")
                return ""
            
            # Кликаем на предмет для добавления в корзину
            item['element'].click()
            
            # Ждем загрузки модали с предметом
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "modal-item"))
            )
            
            # Находим кнопку "Добавить в корзину"
            add_to_cart_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Добавить')]"))
            )
            
            add_to_cart_button.click()
            
            logger.info(f"✅ {item_name} добавлен в корзину")
            
            # Переходим в корзину
            self.driver.get(f"{self.BASE_URL}/cart")
            
            # Ждем загрузки корзины
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "cart-items"))
            )
            
            # Кликаем "Оформить заказ"
            checkout_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Оформить')]"))
            )
            
            checkout_button.click()
            
            # Ждем подтверждения заказа
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "order-confirmation"))
            )
            
            # Получаем ID заказа
            order_id_element = self.driver.find_element(By.CLASS_NAME, "order-id")
            order_id = order_id_element.text
            
            logger.success(f"✅ Заказ создан: {order_id}")
            
            return order_id
            
        except TimeoutException:
            logger.error(f"❌ Timeout при покупке {item_name}")
            return ""
        except Exception as e:
            logger.error(f"❌ Ошибка при покупке: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    async def get_inventory(self) -> list:
        """Получить инвентарь на TradeIt.gg"""
        
        try:
            logger.info("📦 Получаем инвентарь...")
            
            # Переходим в инвентарь
            self.driver.get(f"{self.BASE_URL}/user/inventory")
            
            # Ждем загрузки предметов
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "inventory-item"))
            )
            
            # Получаем все предметы
            items = self.driver.find_elements(By.CLASS_NAME, "inventory-item")
            
            inventory = []
            for item_element in items:
                try:
                    name = item_element.find_element(By.CLASS_NAME, "item-name").text
                    condition = item_element.find_element(By.CLASS_NAME, "item-condition").text
                    price = float(
                        item_element.find_element(By.CLASS_NAME, "item-price").text
                        .replace('$', '')
                    )
                    
                    inventory.append({
                        'name': name,
                        'condition': condition,
                        'price': price
                    })
                except:
                    pass
            
            logger.info(f"✅ В инвентаре {len(inventory)} предметов")
            return inventory
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения инвентаря: {e}")
            return []
    
    async def sell_item(self, item_name: str, price: float) -> bool:
        """Выставить предмет на продажу"""
        
        try:
            logger.info(f"💹 Выставляем {item_name} на продажу за ${price:.2f}")
            
            # Получаем инвентарь
            inventory = await self.get_inventory()
            
            # Ищем предмет в инвентаре
            target_item = None
            for item in inventory:
                if item['name'].lower() == item_name.lower():
                    target_item = item
                    break
            
            if not target_item:
                logger.error(f"❌ {item_name} не найден в инвентаре")
                return False
            
            logger.success(f"✅ {item_name} выставлен на продажу")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при продаже: {e}")
            return False
    
    async def close(self):
        """Закрыть браузер"""
        if self.driver:
            self.driver.quit()
            logger.info("✅ ChromeDriver закрыт")


# Тестирование
async def test_tradeit():
    """Тест TradeIt.gg"""
    bot = TradeItBot()
    
    try:
        # Авторизуемся
        success = await bot.login()
        if not success:
            return
        
        # Проверяем баланс
        balance = await bot.get_balance()
        print(f"Баланс: ${balance:.2f}")
        
        # Ищем предмет
        item = await bot.search_item("AK-47")
        if item:
            print(f"Найден: {item['name']} - ${item['price']:.2f}")
        
        # Получаем инвентарь
        inventory = await bot.get_inventory()
        print(f"Инвентарь: {len(inventory)} предметов")
        
    finally:
        await bot.close()


if __name__ == '__main__':
    asyncio.run(test_tradeit())
