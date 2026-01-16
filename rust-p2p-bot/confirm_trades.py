#!/usr/bin/env python3
"""
Скрипт для подтверждения Steam трейдов через Steam Guard
"""

import os
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import STEAM_USERNAME, STEAM_PASSWORD, MAFILE_PATH
from logger import get_logger

logger = get_logger("SteamConfirm")

def generate_2fa_code_manual():
    """Генерируем 2FA код из maFile вручную"""
    
    try:
        import base64
        import hashlib
        import hmac
        import struct
        
        mafile_path = MAFILE_PATH
        
        logger.info(f"📂 Читаем maFile: {mafile_path}")
        
        with open(mafile_path, 'r', encoding='utf-8') as f:
            mafile = json.load(f)
        
        shared_secret = mafile.get('shared_secret')
        
        if not shared_secret:
            logger.error("❌ shared_secret не найден в maFile")
            return None
        
        # Декодируем base64
        secret_bytes = base64.b64decode(shared_secret + '==')
        
        # HMAC-SHA1
        time_int = int(time.time()) // 30
        time_bytes = struct.pack('>Q', time_int)
        
        hmac_result = hmac.new(
            secret_bytes,
            time_bytes,
            hashlib.sha1
        ).digest()
        
        # Берем последний байт как смещение
        offset = hmac_result[19] & 0xf
        
        # Берем 4 байта с этого смещения
        code_int = struct.unpack('>I', hmac_result[offset:offset+4])[0]
        code_int &= 0x7fffffff
        code_int %= 100000
        
        code = str(code_int).zfill(5)
        
        logger.success(f"🔐 2FA код сгенерирован: {code}")
        return code
        
    except FileNotFoundError:
        logger.error(f"❌ maFile не найден: {mafile_path}")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации кода: {e}")
        return None

def check_steam_trades():
    """Проверяем активные трейды на Steam"""
    
    try:
        logger.info("🔍 Проверяем трейды на Steam...")
        
        # Нужно использовать steam-master или другую библиотеку
        # Или напрямую через веб-запросы Steam API
        
        # Для простоты выводим инструкцию
        logger.info("""
╔════════════════════════════════════════╗
║   ПРОВЕРКА ТРЕЙДОВ НА STEAM            ║
╚════════════════════════════════════════╝

1. Откройте: https://steamcommunity.com/my/tradeoffers/received/
2. Найдите трейд от DMarket
3. Нажмите кнопку "Accept Trade" 
4. Введите 2FA код при запросе:
""")
        
        code = generate_2fa_code_manual()
        
        if code:
            logger.info(f"   Код для ввода: {code}")
            logger.warning(f"   Код действует ~30 сек - поторопитесь!")
        
        logger.info("\nАЛИ используйте Steam Guard приложение на телефоне")
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

def auto_confirm_with_steam_master():
    """Попытка автоподтверждения через steam-master"""
    
    try:
        import sys
        steam_master_path = Path(__file__).parent / "steam-master"
        
        if steam_master_path.exists():
            sys.path.insert(0, str(steam_master_path))
            
            logger.info("📚 Пытаемся использовать steam-master...")
            
            try:
                from steam import SteamClient
                from steam.client import EClientPersonaState
                
                logger.info("✅ steam-master импортирован успешно")
                
                # Инициализируем steam-master
                # (это требует полноценной реализации с паролем)
                logger.warning("""
⚠️  steam-master требует пароля Steam для автоподтверждения
Используйте вместо этого Steam Guard приложение или веб-браузер
""")
                
            except ImportError as e:
                logger.warning(f"⚠️  Не удалось импортировать steam-master: {e}")
        else:
            logger.warning(f"⚠️  steam-master не найден в {steam_master_path}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

def main():
    """Главная функция"""
    
    logger.info("="*60)
    logger.info("🔐 ПОДТВЕРЖДЕНИЕ STEAM ТРЕЙДОВ")
    logger.info("="*60)
    
    # Генерируем 2FA код
    code = generate_2fa_code_manual()
    
    if not code:
        logger.error("❌ Не удалось сгенерировать 2FA код")
        return
    
    logger.info(f"""
╔════════════════════════════════════════╗
║   ГОТОВ К ПОДТВЕРЖДЕНИЮ ТРЕЙДОВ        ║
╚════════════════════════════════════════╝

🔐 2FA Код: {code}
⏱️  Действителен: ~30 сек

ИНСТРУКЦИЯ:
1. Откройте: https://steamcommunity.com/my/tradeoffers/received/
2. Найдите трейд от @DMarket
3. Нажмите "Accept Trade"
4. Введите код: {code}
5. Трейд будет принят!

ИЛИ используйте Steam Guard приложение:
- Откройте приложение Steam Guard
- Найдите DMarket трейд
- Примите его там

ВАЖНО:
- Код действует только 30 секунд
- После подтверждения предмет придет в инвентарь
- Затем его нужно продать или обменять
""")
    
    # Проверяем трейды
    check_steam_trades()
    
    logger.info("="*60)
    logger.info("✅ Готово к подтверждению")
    logger.info("="*60)


if __name__ == '__main__':
    main()
