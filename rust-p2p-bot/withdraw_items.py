#!/usr/bin/env python3
"""
Скрипт для вывода предметов из DMarket в Steam инвентарь
"""

import os
import sys
import json
import uuid
import requests
from pathlib import Path
from datetime import datetime

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import DMARKET_PUBLIC_KEY, DMARKET_PRIVATE_KEY
from dmarket_api import DMarketAPI
from logger import get_logger

logger = get_logger("WithdrawItems")

class ItemWithdrawer:
    """Класс для вывода предметов из DMarket"""
    
    def __init__(self):
        self.dmarket = DMarketAPI()
        self.base_url = "https://api.dmarket.com"
    
    def get_user_items(self):
        """Получить все предметы пользователя на DMarket"""
        
        try:
            logger.info("📦 Получаем список предметов...")
            
            # Endpoint для получения предметов (не в продаже)
            url = f"{self.base_url}/exchange/v1/user/items"
            params = {
                'gameId': 'rust',
                'limit': '100',
                'currency': 'USD'
            }
            
            response = self.dmarket.session.get(
                url,
                params=params,
                headers=self.dmarket._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('objects', [])
                logger.success(f"✅ Найдено {len(items)} предметов")
                
                return items
            else:
                logger.error(f"❌ Ошибка получения предметов: {response.status_code}")
                logger.error(response.text)
                return []
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return []
    
    def withdraw_item(self, item_id, link_id):
        """Вывести один предмет"""
        
        try:
            logger.info(f"🚀 Выводим предмет: {item_id}")
            
            # Генерируем уникальный requestId
            request_id = str(uuid.uuid4())
            
            # Формат для вывода - важно правильный!
            payload = {
                "assets": [
                    {
                        "id": item_id,
                        "linkId": link_id
                    }
                ],
                "requestId": request_id
            }
            
            url = f"{self.base_url}/exchange/v1/withdraw-assets"
            
            # Используем POST с правильными заголовками от DMarket API
            response = self.dmarket.session.post(
                url,
                json=payload,
                headers=self.dmarket._get_headers()
            )
            
            logger.info(f"Status: {response.status_code}")
            logger.debug(f"Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                transfer_id = data.get('transferId')
                logger.success(f"✅ Предмет выведен! Transfer ID: {transfer_id}")
                return transfer_id
            else:
                logger.error(f"❌ Ошибка вывода: {response.status_code}")
                logger.error(response.text)
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_withdrawal_status(self, transfer_id):
        """Проверить статус вывода"""
        
        try:
            url = f"{self.base_url}/exchange/v1/withdraw-status/{transfer_id}"
            
            response = self.dmarket.session.get(
                url,
                headers=self.dmarket._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('Status', 'Unknown')
                logger.info(f"📍 Статус: {status}")
                return status
            else:
                logger.warning(f"⚠️ Не удалось получить статус: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return None
    
    def withdraw_all_items(self):
        """Вывести все предметы которые можно"""
        
        logger.info("="*60)
        logger.info("🚀 НАЧИНАЕМ ВЫВОД ВСЕХ ПРЕДМЕТОВ")
        logger.info("="*60)
        
        items = self.get_user_items()
        
        if not items:
            logger.warning("⚠️ Нет предметов для вывода")
            return
        
        success_count = 0
        failed_count = 0
        
        for item in items:
            try:
                item_id = item.get('itemId')
                link_id = item.get('extra', {}).get('linkId')
                title = item.get('title', 'Unknown')
                withdrawable = item.get('extra', {}).get('withdrawable', False)
                
                logger.info(f"\n📦 {title}")
                logger.info(f"   ID: {item_id}")
                logger.info(f"   Можно вывести: {'✅ Да' if withdrawable else '❌ Нет'}")
                
                if withdrawable and link_id:
                    transfer_id = self.withdraw_item(item_id, link_id)
                    
                    if transfer_id:
                        success_count += 1
                        # Проверяем статус
                        import time
                        time.sleep(2)
                        status = self.get_withdrawal_status(transfer_id)
                        logger.info(f"   Статус: {status}")
                    else:
                        failed_count += 1
                else:
                    logger.warning(f"   ⚠️ Нельзя вывести (withdrawable={withdrawable}, linkId={'есть' if link_id else 'нет'})")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"   ❌ Ошибка при обработке: {e}")
                failed_count += 1
        
        logger.info("\n" + "="*60)
        logger.success(f"✅ Успешно: {success_count}")
        logger.error(f"❌ Ошибок: {failed_count}")
        logger.info("="*60)


def main():
    """Главная функция"""
    
    logger.info("🔧 Инициализируем систему вывода...")
    
    # Проверяем ключи
    if not DMARKET_PUBLIC_KEY or not DMARKET_PRIVATE_KEY:
        logger.error("❌ DMarket ключи не найдены в .env")
        return
    
    withdrawer = ItemWithdrawer()
    
    # Вариант 1: Вывести все предметы
    withdrawer.withdraw_all_items()
    
    # Вариант 2: Вывести конкретный предмет (раскомментировать если нужно)
    # item_id = "05a515e0-7b40-5856-bd77-a195f512ec58"
    # link_id = "72b8e329-b5e1-5e59-9f21-ea7065e5555c"
    # withdrawer.withdraw_item(item_id, link_id)


if __name__ == '__main__':
    main()
