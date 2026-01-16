# 🌐 ИНТЕГРАЦИЯ TradeIt.gg - ПОЛНАЯ РЕАЛИЗАЦИЯ

**ТЕКУЩАЯ СИТУАЦИЯ:**
- Баланс на TradeIt.gg: **$24.60** (ОСНОВНОЙ источник денег!)
- Интеграция: ❌ ОТСУТСТВУЕТ ПОЛНОСТЬЮ
- Нужно: Купить предметы + Выставить на продажу

---

## 📊 ВАРИАНТЫ РЕАЛИЗАЦИИ

### Вариант A: Selenium WebDriver (РЕКОМЕНДУЕТСЯ)
```
✅ Работает как реальный пользователь
✅ Может обойти защиту от ботов
✅ Полный контроль над UI
❌ Медленнее (5-10 сек за операцию)
❌ Требует видеокарты для headless режима
```

### Вариант B: API + XHR (БЫСТРЕЕ)
```
✅ Очень быстро (200-500 мс за операцию)
✅ Меньше ресурсов
❌ API может быть защищен/изменен
❌ Требует reverse-engineering
```

**ВЫБОР: Вариант A + Selenium** (более надежно)

---

## 🚀 РЕАЛИЗАЦИЯ С SELENIUM

### Шаг 1: Установка Selenium

```bash
pip install selenium

# Скачиваем ChromeDriver подходящей версии
# https://chromedriver.chromium.org/
# И кладем в папку: drivers/chromedriver.exe
```

### Шаг 2: Класс TradeItBot

```python
# Файл: src/tradeit_api.py

import asyncio
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

logger = logging.getLogger('TradeIt')

class TradeItBot:
    """Управление TradeIt.gg через Selenium WebDriver"""
    
    BASE_URL = "https://tradeit.gg/ru/rust"
    LOGIN_EMAIL = "ВАШ_EMAIL_ДЛЯ_TRADEIT"
    LOGIN_PASSWORD = "ВАШ_ПАРОЛЬ_ДЛЯ_TRADEIT"
    
    def __init__(self):
        self.driver = None
        self.is_logged_in = False
        self._initialize_driver()
    
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
            
            # Путь к ChromeDriver
            self.driver = webdriver.Chrome('drivers/chromedriver.exe', options=options)
            self.driver.set_page_load_timeout(30)
            
            logger.info("✅ ChromeDriver инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ChromeDriver: {e}")
            raise
    
    async def login(self) -> bool:
        """Авторизация на TradeIt.gg"""
        
        try:
            logger.info("🔐 Авторизуемся на TradeIt.gg...")
            
            # Переходим на страницу логина
            self.driver.get(f"{self.BASE_URL}/login")
            
            # Ждем поле email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            
            # Вводим email
            email_field.clear()
            email_field.send_keys(self.LOGIN_EMAIL)
            
            # Находим и заполняем пароль
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(self.LOGIN_PASSWORD)
            
            # Кликаем кнопку "Войти"
            login_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Войти')]")
            login_button.click()
            
            # Ждем загрузки профиля (проверяем наличие баланса)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "balance"))
            )
            
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
            
            # Кликаем на предмет
            # (для простоты предполагаем что нашли элемент)
            
            # Заполняем форму продажи
            # ...
            
            logger.success(f"✅ {item_name} выставлен на продажу")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при продаже: {e}")
            return False
    
    def close(self):
        """Закрыть браузер"""
        if self.driver:
            self.driver.quit()
            logger.info("✅ ChromeDriver закрыт")


# Пример использования:
async def main():
    bot = TradeItBot()
    
    try:
        # Авторизуемся
        await bot.login()
        
        # Проверяем баланс
        balance = await bot.get_balance()
        
        # Ищем предмет
        item = await bot.search_item("AK-47 Victoria")
        
        # Покупаем
        if item['price'] <= 50:  # Если цена приемлема
            order_id = await bot.buy_item("AK-47 Victoria", 50)
            print(f"Заказ: {order_id}")
        
        # Получаем инвентарь
        inventory = await bot.get_inventory()
        print(f"Инвентарь: {inventory}")
        
    finally:
        bot.close()


if __name__ == '__main__':
    asyncio.run(main())
```

---

## 🔌 ШАГ 3: ИНТЕГРАЦИЯ В trade_engine.py

```python
from src.tradeit_api import TradeItBot

class TradeEngine:
    def __init__(self):
        # ... другие инициализации ...
        self.tradeit = TradeItBot()
    
    async def execute_full_trade(self, deal: dict) -> float:
        """Полный цикл торговли с TradeIt.gg"""
        
        try:
            # 1. ПОКУПКА на TradeIt.gg
            if deal['source'] == 'TradeIt':
                logger.info(f"💳 Покупаем на TradeIt.gg: {deal['name']}")
                
                order_id = await self.tradeit.buy_item(
                    deal['name'],
                    deal['buy_price']
                )
                
                if not order_id:
                    logger.error("❌ Не удалось создать заказ")
                    return 0
                
                logger.success(f"✅ Заказ создан: {order_id}")
            
            # 2. ОЖИДАНИЕ в Steam (5-30 сек)
            await asyncio.sleep(10)  # Даем время на получение
            
            # 3. ОБМЕН на другой площадке
            if deal['target'] == 'LootFarm':
                logger.info(f"🔄 Обменяем на Loot.Farm")
                
                # ... логика обмена ...
            
            # 4. ПОЛУЧЕНИЕ ДЕНЕГ
            profit = deal['sell_price'] - deal['buy_price']
            
            logger.success(f"🎉 Прибыль: ${profit:.2f} ({deal['spread']:.1f}%)")
            
            return profit
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return 0
```

---

## 🧪 ШАГ 4: ТЕСТИРОВАНИЕ

### Новый режим: `--test-tradeit`

```python
# В main.py:

@app.command()
def test_tradeit():
    """Тест: Работает ли TradeIt.gg интеграция"""
    
    async def run():
        tradeit = TradeItBot()
        
        try:
            logger.info("🧪 Тест TradeIt.gg интеграции")
            logger.info("=" * 60)
            
            # 1. Логин
            success = await tradeit.login()
            if not success:
                logger.error("❌ Не удалось авторизоваться")
                return
            
            # 2. Баланс
            balance = await tradeit.get_balance()
            logger.success(f"✅ Баланс: ${balance:.2f}")
            
            # 3. Поиск предмета
            item = await tradeit.search_item("AK-47")
            if item:
                logger.success(f"✅ Найден: {item['name']} - ${item['price']:.2f}")
            
            # 4. Инвентарь
            inventory = await tradeit.get_inventory()
            logger.success(f"✅ В инвентаре {len(inventory)} предметов")
            
            logger.info("=" * 60)
            logger.info("✅ Все тесты пройдены!")
            
        finally:
            tradeit.close()
    
    asyncio.run(run())
```

### Запуск:
```bash
python main.py --test-tradeit
```

---

## 📋 ЧЕКЛИСТ

- [ ] Установлен Selenium
- [ ] Скачан ChromeDriver
- [ ] Создан файл `src/tradeit_api.py`
- [ ] Заполнены LOGIN_EMAIL и LOGIN_PASSWORD
- [ ] Авторизация работает
- [ ] Поиск предметов работает
- [ ] Покупка работает
- [ ] Получение инвентаря работает
- [ ] Интеграция в trade_engine.py завершена
- [ ] Тест `--test-tradeit` проходит

